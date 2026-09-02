"""
2号分析师 Iron Gate — 不可绕过的最终校验闸门

职责:
- Agent完成写作循环后，必须提交给Iron Gate做最终校验
- 校验不通过 → 返回详细失败报告 → Agent必须回到写作循环
- 校验通过 → 输出最终报告（md/docx）
"""

import datetime
import json
import logging
import os
import re
import sys
import time as _time_module
from dataclasses import asdict, dataclass
from pathlib import Path

from core.knowledge_injector import KnowledgeInjector
from core.observability import GATE_CHECK_RESULT, GATE_RUNS, GATE_SCORE

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sacs import SACLoader

logger = logging.getLogger("2hao.iron_gate")

# ═══════════════════════════════════════════════════════════════
# P0-4（2026-08-01 审计）：Gate KPI 元评估 — GateMetricsTracker
# 记录每次检查的 pass/fail、耗时、检查项名称；
# 支持导出 JSON 指标（各检查项通过率、误放率等）。
# ═══════════════════════════════════════════════════════════════


@dataclass
class GateMetricsRecord:
    check_name: str
    passed: bool
    score: float
    elapsed_sec: float
    severity: str = "error"
    details: str = ""


class GateMetricsTracker:
    """Iron Gate 性能元评估追踪器。

    在 run_all 的每个检查项前后记录耗时和结果，
    支持 to_json() 导出结构化指标（用于 calibrate、ablation）。
    """

    def __init__(self):
        self.records: list[GateMetricsRecord] = []

    def record(
        self,
        check_name: str,
        passed: bool,
        score: float,
        elapsed_sec: float,
        severity: str = "error",
        details: str = "",
    ):
        self.records.append(
            GateMetricsRecord(
                check_name=check_name,
                passed=passed,
                score=score,
                elapsed_sec=elapsed_sec,
                severity=severity,
                details=details,
            )
        )

    def stats(self) -> dict:
        """计算汇总指标：各检查项通过率、耗时分布、平均分"""
        if not self.records:
            return {"error": "no records"}
        total = len(self.records)
        passed = sum(1 for r in self.records if r.passed)
        hard_blocks = sum(1 for r in self.records if r.severity == "error" and not r.passed)
        avg_score = sum(r.score for r in self.records) / max(total, 1)
        total_elapsed = sum(r.elapsed_sec for r in self.records)
        per_check = {}
        for r in self.records:
            key = r.check_name
            if key not in per_check:
                per_check[key] = {"pass": 0, "fail": 0, "total_sec": 0.0, "count": 0, "scores": []}
            per_check[key]["pass" if r.passed else "fail"] += 1
            per_check[key]["total_sec"] += r.elapsed_sec
            per_check[key]["count"] += 1
            per_check[key]["scores"].append(r.score)
        check_summary = {}
        for k, v in per_check.items():
            check_summary[k] = {
                "pass_rate": round(v["pass"] / max(v["count"], 1), 3),
                "avg_score": round(sum(v["scores"]) / max(len(v["scores"]), 1), 3),
                "avg_elapsed_sec": round(v["total_sec"] / max(v["count"], 1), 4),
                "count": v["count"],
            }
        return {
            "overall": {
                "pass_rate": round(passed / max(total, 1), 3),
                "hard_blocks": hard_blocks,
                "avg_score": round(avg_score, 3),
                "total_elapsed_sec": round(total_elapsed, 4),
                "total_checks": total,
            },
            "per_check": check_summary,
        }

    def to_json(self, filepath: str = None) -> str:
        data = {"metrics": self.stats(), "records": [asdict(r) for r in self.records]}
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        if filepath:
            Path(filepath).write_text(json_str, encoding="utf-8")
        return json_str

    def __len__(self):
        return len(self.records)


# R61（2026-08-03）：共享基础类型从 checks.base 导入（GateCheckResult/GateReport）
from pipeline.checks.analysis_mixin import AnalysisChecksMixin
from pipeline.checks.base import GateCheckResult, GateReport
from pipeline.checks.content_format_mixin import ContentFormatChecksMixin
from pipeline.checks.coverage_mixin import CoverageChecksMixin
from pipeline.checks.data_quality_mixin import DataQualityChecksMixin
from pipeline.checks.llm_checks_mixin import LlmChecksMixin


class IronGate(
    ContentFormatChecksMixin, DataQualityChecksMixin, AnalysisChecksMixin, LlmChecksMixin, CoverageChecksMixin
):
    def __init__(
        self,
        report_path: str,
        report_type: str = "industry_deep",
        style: str = "cicc",
        degradation_level: int = 0,
        asset: str = "",
        chart_ids: set = None,
        client_questions: list = None,
        collected_data: dict = None,
    ):
        self.report_path = Path(report_path)
        self.report_type = report_type
        self.style = style
        self.degradation_level = degradation_level
        self._chart_ids = chart_ids  # R73: 实际生成图ID集合（chart_assembler产出），不作为检查缺图
        self.client_questions = client_questions  # R84: 委托方必答问题+实体锚定（decision_memo）
        # 修复（2026-08-29）：接收 collected_data 供 _check_data_point_provenance 使用
        self.collected_data = collected_data or {}
        # 修复（2026-08-01 IronGate 第 2 轮）：绑定资产名，data_dict_refs 校验
        # 按 <asset>_data_dict.json 精确加载，杜绝"兜底取最新文件"导致的跨资产串标。
        self.asset = asset
        self.sac_id = asset or ""
        # L1 视觉降级时，placeholder 图表是预期内的（FP7b），不作为硬阻断
        self._allow_placeholder_degradation = degradation_level >= 1
        # Pillar 3: Load calibrated thresholds
        self._thresholds = self._load_thresholds()
        self._calibrated = bool(self._thresholds)
        self.report_text = ""
        sac = SACLoader(report_type)
        self.sac = sac
        # 修复（2026-08-01 审计）：min_charts 从 SAC chart_config 读取（单一事实源），
        # 不再硬编码。原硬编码 {industry:5, listed:10, unlisted:4, earnings:4} 远低于
        # SAC 标准（12/12/8/4）和 STANDARDS.md 基线，是又一次标准降级。
        try:
            _cc = sac.get_chart_config()
            self.min_charts = int(_cc.get("min_charts", 5))
            self.min_tables = int(_cc.get("min_tables", 2))
        except Exception:
            # SAC 缺配置时按 STANDARDS 基线兜底（不应发生，get_chart_config 已 fail-fast）
            _base = {
                "industry_deep": 12,
                "listed_company": 12,
                "unlisted_company": 8,
                "earnings_notes": 4,
                "decision_memo": 4,
            }
            self.min_charts = _base.get(report_type, 5)
            self.min_tables = {
                "industry_deep": 4,
                "listed_company": 4,
                "unlisted_company": 3,
                "earnings_notes": 2,
                "decision_memo": 3,
            }.get(report_type, 2)
        # R56/FP5：min_chars 按回测基线库金牌 p10 校准（methodology_backtest_deep.json）
        # 金牌报告 p10 = 10420 字；listed/unlisted 对齐投行深度标准。
        self.min_chars = {
            "industry_deep": 10420,
            "listed_company": 10420,
            "unlisted_company": 6000,
            "earnings_notes": 4000,
            "decision_memo": 6000,
        }.get(report_type, 8000)
        self._load_report()

    def _load_report(self):
        if self.report_path.exists():
            self.report_text = self.report_path.read_text(encoding="utf-8")
        else:
            self.report_text = ""

    @classmethod
    def from_text(cls, report_text, report_type="industry_deep", style="cicc", asset: str = ""):
        import tempfile

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        tmp.write(report_text)
        tmp_path = tmp.name
        tmp.close()
        gate = cls(tmp_path, report_type, style, asset=asset)
        gate.report_text = report_text
        return gate

    def _load_thresholds(self):
        """Load calibrated thresholds from file"""
        import json

        base = os.path.dirname(__file__)
        for p in [
            os.path.join(base, "..", "benchmark", "calibrated_thresholds.json"),
            os.path.join(base, "..", "data", "calibrated_thresholds.json"),
        ]:
            resolved = os.path.abspath(p)
            if os.path.isfile(resolved):
                try:
                    with open(resolved) as f:
                        return json.load(f)
                except Exception:
                    pass
        return {}

    def _get_threshold(self, check_name, default=0.7):
        """Get calibrated threshold for a check"""
        if self._calibrated and check_name in self._thresholds:
            return self._thresholds[check_name]
        return default

    def check(self, text):
        self.report_text = text
        return self.run_all()

    def run_all(self) -> GateReport:
        """运行全部检查，含行业参数基线校验"""
        # 行业参数基线校验
        try:
            company = getattr(self, "asset", "") or getattr(self, "company_name", "")
            if company:
                industry = KnowledgeInjector.get_industry_by_company(company)
                if industry:
                    baseline = KnowledgeInjector.get_valuation_baseline(industry)
                    if baseline:
                        msg = "Valuation baseline: industry=%s, WACC=%.1f%%" % (
                            industry,
                            baseline.get("wacc", {}).get("default", 0),
                        )
                        # Store for later use
                        self._data_fidelity_note = msg
        except Exception:
            pass

        # P0-4（2026-08-01 审计）：初始化 Gate KPI 元评估追踪器
        _metrics = GateMetricsTracker()

        _check_funcs = [
            self._check_content_volume,
            self._check_content_density,
            # R56（2026-08-03）：判断密度/数据密度（对标金牌报告基准）
            self._check_judgment_density,
            # R76（2026-08-05 P0）：报告日期检查（DI-001）
            self._check_report_date,
            # R77（2026-08-05 P0）：未替换占位符检查
            self._check_placeholder_xxx,
            self._check_aigc_fingerprint,
            self._check_human_sense,
            self._check_sac_coverage,
            self._check_chart_density,
            self._check_chart_completeness,
            self._check_data_traceability,
            self._check_annotation_types,
            self._check_global_perspective,
            self._check_geopolitical_depth,  # R78: 中美竞争分析深度
            self._check_bold_call_consistency,  # R79 P0-2: Bold Call 单一事实源
            self._check_market_size_consistency,  # R79 P0-3: 市场规模口径统一
            self._check_indicator_consistency,  # R82 P1: 关键指标单一事实源
            self._check_source_entity,  # R82 P2: 来源标注实体化
            self._check_financial_statements_coverage,
            self._check_format_consistency,
            self._check_forbidden_patterns,
            self._check_gbk_encoding,  # P2-4 (2026-09-01): 乱码拦截
            self._check_placeholder_source,  # P0-2 (2026-09-01): 裸来源锚点拦截
            self._check_template_phrases,  # R79 P0-1: 模板句拦截
            self._check_insight_quality,  # R79 P1-1: 洞察质量
            self._check_persuasion_architecture,
            self._check_table_density,
            self._check_moat_analysis,
            self._check_multi_model,
            self._check_decision_gate,
            self._check_dcf_sensitivity,
            self._check_so_what_chain,
            self._check_placeholder_charts,
            self._check_chart_analysis_quality,
            self._check_ai_tone_by_llm,
            self._check_human_impossible_dimension,
            self._check_explicit_conclusion,
            self._check_template_leak,
            self._check_evidence_layer,
            self._check_falsification_conditions,
            self._check_meta_cognition,
            self._check_counterargument_strength,  # R75: 反方论证强度DES
            self._check_so_what_per_judgment,
            self._check_data_type_annotation,
            self._check_attribution_depth,
            self._check_bold_call,
            self._check_synthesis_consistency,
            self._check_cross_section_consistency,
            self._check_data_dict_refs,
            # NEW: DataPoint provenance completeness (Phase 1.3)
            self._check_data_point_provenance,
            # NEW: CSRC/交易所合规门禁 (Phase 2.1)
            self._check_csrc_compliance,
            # NEW: Semantic deduplication gate (Phase 5.3)
            self._check_semantic_dedup,
            # R16（2026-08-01 深度补强）：盈利预测表 + 反共识信号存在性校验
            self._check_forecast_presence,
            # R20（2026-08-02 王牌模块）：供应链瓶颈分析存在性校验
            self._check_bottleneck_analysis,
            self._check_markdown_artifacts,
            self._check_personal_narrative,
            self._check_section_continuity,
            self._check_table_quality_md,
            # P2-4（2026-08-01 审计）：风险四层框架
            self._check_risk_layering,
            # R28（2026-08-02 方向B）：数据口径一致性（多来源冲突 + 单位标注）
            self._check_data_conflicts,
            # 2026-08-07：下行/时间线/假设集中度一致性（油位 v2.3 硬伤落地）
            self._check_downstream_consistency,
            # 2026-08-08：业务逻辑检测（双价格带/口径冲突/声称无量化的价值）
            self._check_business_logic,
            # 2026-08-08：身份关系检测（子公司当外部合作方）
            self._check_relation_consistency,
            self._check_rating_target_consistency,
            # R31（2026-08-02 排版根治）：文档布局质量（空白页/空段落）
            self._check_layout_quality,
            # R53审计（2026-08-03 P1-1）：正文完整性扫描（截断/碎片/未完成句）
            self._check_completeness_scan,
            # R35（2026-08-02 算术校验层）：占比/估值中值/目标价空间/EPS桥反向验算
            self._check_arithmetic_audit,
            # R88（2026-08-10）：数值链自洽校验——行业报告分散式数值独立验算
            # （占比数量级/EPS×PE目标价链/目标价空间/细分合计，覆盖商业航天报告硬伤）
            self._check_numeric_chain_consistency,
            # R46（2026-08-02 不变量断言层）：流通市值/持股勾稽/PE×净利 物理不可能拦截
            self._check_invariant_audit,
            # R53审计（2026-08-03 P0-1 估值闭环）：估值链四方勾稽——EPS×股本=净利、
            # 市值=股价×股本、目标价/PE=EPS，任一环偏差>5% 即 FAIL（持 data_dict 作外部锚）
            self._check_valuation_integrity,
            # R35（2026-08-02 模板句高重复检测）：模板污染/概念错位
            self._check_template_repeat,
            # R53审计（2026-08-03 P1-2）：语义重复检测（跨章节相似度，替代硬编码黑名单）
            self._check_semantic_repeat,
            # R38（2026-08-02 财务数值一致性）：毛利率/PE 与 data_dict 真实值冲突检测
            self._check_financial_value_consistency,
            # R55（2026-08-03 方法论升级）：行业报告质量护栏
            self._check_stock_pick_chain,  # 选股传导链存在性
            self._check_unlisted_threat,  # 非上市威胁判断存在性
            self._check_tam_bottomup,  # TAM/SAM/SOM 自底向上校验
            self._check_regional_penetration,  # 区域渗透率错位判断
            # R57（2026-08-03）：行业并购视角 + 假设驱动 + ESG实质性
            self._check_industry_consolidation,  # 行业整合/并购信号
            self._check_core_hypothesis,  # MBB假设驱动
            self._check_esg_materiality,  # ESG实质性
            # R58（2026-08-03）：四大审计确定性检查（财务造假信号）
            self._check_financial_fraud_signals,
            # R60（2026-08-03）：证据链门禁（工具数据进正文验证）
            self._check_evidence_chain,
            # R63（2026-08-04 全量修复）：补回 R61 迁移遗漏的 3 项检查。
            # Marvis 审计（2号分析师R60R61升级深度审计_20260803）发现 67 方法仅 64 执行，
            # 这三项（数据保真/来源准确/主观评分禁令）是真实防线，非废弃代码。
            self._check_data_fidelity,  # 数据保真：营收/净利数值合理性
            self._check_data_source_accuracy,  # 数据来源准确性：营收异常偏大扫描
            self._check_subjective_scoring,  # FP4 合规：禁止"评分8分"式主观评分
            # R55（2026-08-03 Phase E）：LLM 数据交叉验证（对侧 provider）
            self._check_llm_data_verification,
            # R68（2026-08-04 全量修复）：覆盖完整性与实体验证——解决品牌覆盖代替实体覆盖、
            # 上市公司偏见等系统性问题，数据底座: data/unlisted_players.json + brand_entity_mapping.json
            self._check_coverage_completeness,  # 三层校验：分类覆盖/品牌映射/集团归属
            self._check_entity_verification,  # 实体验证：映射缺失/上市状态误判
            self._check_sub_element_coverage,  # R74: 子要素覆盖（根治Goodhart律——关键词→子要素正则）
            self._check_industry_baseline_gap,  # R77 P0-2: 行业底座缺口提示（warning级，不阻断）
            self._check_honest_gap,  # R79 P1-3: 诚实留白机制
            self._check_client_questions_coverage,  # R83: 委托方必答问题覆盖率（decision_memo 核心）
            self._check_entity_anchoring,  # R84: 委托方实体锚定（must_contain/forbidden_swap）
            self._check_decision_engine_citation,  # R84: 决策引擎数值引用（卡位评分/最坏损失/投入）
            self._check_narrative_consistency,  # R85: 叙事一致性（防"答对问题但答错生意"）
            self._check_data_point_citation,  # R85: 数据点引用审计（enrich 关键数据进正文）
            self._check_source_reliability,
            self._check_methodology_compliance,
            self._check_inline_citations,
            self._check_style_distance,
            self._check_anti_patterns,  # M6: 伪框架黑名单  # S2: 风格距离（warning）  # P3-B: [E#] 证据标注密度（warning）  # R87: 数据源可信度（enrich 幻觉修正值校验）
        ]
        checks = []
        # R15（2026-08-01 提速）：把 LLM 检查（ai_tone/human_impossible/数据验证，各 60s+）
        # 与其余确定性检查并行执行。确定性检查走主线程（快），LLM 检查放线程池。
        _llm_check_names = (
            "_check_ai_tone_by_llm",
            "_check_human_impossible_dimension",
            "_check_llm_data_verification",
        )
        _llm_results = {}

        def _run_llm_check(_func):
            try:
                return _func.__name__, _func()
            except Exception as _e:
                return _func.__name__, GateCheckResult(
                    name=_func.__name__.replace("_check_", ""),
                    passed=False,
                    score=0.0,
                    details=f"检查异常: {str(_e)[:80]}",
                    severity="error",
                )

        # R89（2026-08-25）：SEG_PARALLEL=0 时 LLM 检查也串行——stealth/免费模型并发>1 即 429
        import os as _os_ig
        from concurrent.futures import ThreadPoolExecutor

        _ig_workers = 1 if _os_ig.environ.get("SEG_PARALLEL", "1") == "0" else 2
        _llm_pool = ThreadPoolExecutor(max_workers=_ig_workers)
        _llm_futures = {
            _llm_pool.submit(_run_llm_check, _func): _func.__name__
            for _func in _check_funcs
            if _func.__name__ in _llm_check_names
        }

        for _func in _check_funcs:
            if _func.__name__ in _llm_check_names:
                continue  # LLM 检查并行处理
            _t0 = _time_module.time()
            try:
                _result = _func()
            except Exception as _e:
                _result = GateCheckResult(
                    name=_func.__name__.replace("_check_", ""),
                    passed=False,
                    score=0.0,
                    details=f"检查异常: {str(_e)[:80]}",
                    severity="error",
                )
            _elapsed = _time_module.time() - _t0
            checks.append(_result)
            _metrics.record(
                check_name=_result.name,
                passed=_result.passed,
                score=_result.score,
                elapsed_sec=_elapsed,
                severity=_result.severity,
                details=_result.details,
            )

        # 收集并行 LLM 检查结果
        # R77（2026-08-05）：LLM 并行检查加入超时保护——此前 _fut.result() 无 timeout，
        # 若校验端为 agent_provider（Marvis 队列）且沙箱无 agent responder 时，
        # MAX_WAIT_SEC=300 会挂起 5 分钟，拖死整个 IronGate（test_audit_report 触发）。
        # 修复：单检查超时 60s，超时视为"校验器不可用"降级放行（确定性检查已覆盖算术/估值硬伤，
        # LLM 语义校验是增强层，不应成为 Gate 单点挂死源）。
        _LLM_CHECK_TIMEOUT = 60
        for _fut in _llm_futures:
            try:
                _name, _result = _fut.result(timeout=_LLM_CHECK_TIMEOUT)
            except Exception as _e:
                _name = _llm_futures[_fut]
                _result = GateCheckResult(
                    name=_name.replace("_check_", ""),
                    passed=False,
                    score=0.0,
                    details=f"检查异常: {str(_e)[:80]}",
                    severity="error",
                )
            checks.append(_result)
            _metrics.record(
                check_name=_result.name,
                passed=_result.passed,
                score=_result.score,
                elapsed_sec=0,
                severity=_result.severity,
                details=_result.details,
            )
        _llm_pool.shutdown(wait=True)

        # 将 metrics 挂载到 gate 实例上供外部访问
        self._last_metrics = _metrics

        report = GateReport()
        report.checks = checks
        # P0 加权评分 v2（2026-09-02）：只计算 error-severity 检查的均值。
        # 原因：warning 类检查（anti_patterns=0.20, inline_citations=0.30 等）拉低均值，
        # 即使所有 error 检查通过，overall_score 仍卡在 0.88-0.91。
        # v1 尝试 error 3x 权重但反而降低分数（error 检查本身也有低分项）。
        # v2：overall_score = mean(error checks only)，warning 检查仅记录不计入分数。
        # 这样 error 检查全部通过时分数直接反映核心质量，不受 warning 拖累。
        _error_scores = [max(0.0, min(1.0, c.score)) for c in checks if c.severity == "error"]
        _warn_scores = [max(0.0, min(1.0, c.score)) for c in checks if c.severity != "error"]
        if _error_scores:
            report.overall_score = sum(_error_scores) / len(_error_scores)
        else:
            # 无 error 检查时回退到全量均值
            _all = [max(0.0, min(1.0, c.score)) for c in checks]
            report.overall_score = sum(_all) / max(len(_all), 1)
        # 记录 warning 均值供诊断
        if _warn_scores:
            _warn_mean = sum(_warn_scores) / len(_warn_scores)
            logger.info("[P0-WEIGHTED] error_mean=%.3f (%d checks), warn_mean=%.3f (%d checks)",
                        report.overall_score, len(_error_scores), _warn_mean, len(_warn_scores))
        report.passed = all(c.passed for c in checks if c.severity == "error")
        report.failures = ["[%s] %s: %s" % (c.severity.upper(), c.name, c.details) for c in checks if not c.passed]
        # FP7a: Register gate failures with LearningLoop for evolution
        # FP5: Gate回馈 — 失败模式自动注册+优先级提升
        # P2-audit 2026-08-24：此块曾被整段复制两遍 → 同一失败计数 +2，
        # hot-fail 阈值(3次)实际 1.5 轮就触发，且 [HOT] 建议重复 append。已去重。
        if not report.passed:
            _fail_names = [c.name for c in report.checks if not c.passed]
            if hasattr(self, "_fail_counter"):
                for fn in _fail_names:
                    self._fail_counter[fn] = self._fail_counter.get(fn, 0) + 1
            else:
                self._fail_counter = {fn: 1 for fn in _fail_names}
            # 连续失败3次的检查项 → 标记为"需prompt调整" + 自动降级约束方式
            _hot_fails = [fn for fn, cnt in self._fail_counter.items() if cnt >= 3]
            if _hot_fails:
                report.suggestions.append(f"[HOT] 连续失败: {', '.join(_hot_fails[:3])}")
                logger.info("[FP5] %d hot failures detected: %s", len(_hot_fails), _hot_fails)
                # P1热加载: 对hot failures自动应用更严格的约束
                _auto_adjust = {
                    "explicit_conclusion": "_rule_inject_conclusion已在StyleCompiler第2位",
                    "decision_gate": "_rule_inject_decision_gate已在StyleCompiler第3位",
                    "so_what_chain": "需调整writing prompt中SoWhat要求的位置",
                    "so_what_per_judgment": "同上",
                    "data_type_annotation": "已在system prompt ## [数据] 锚点中",
                }
                for hf in _hot_fails:
                    if hf in _auto_adjust:
                        report.suggestions.append(f"  [AUTO] {hf}: {_auto_adjust[hf]}")

        # L3: detect empty/corrupted text from LLM failure
        if not self.report_text or len(self.report_text.strip()) < 200:
            report.passed = False
            report.failures.append("[L3] Core LLM failure: report text empty or truncated")
            report.overall_score = 0.0
        if not report.passed and hasattr(self, "report_text") and self.report_text:
            try:
                from pipeline.learning_loop import LearningLoop

                ll = LearningLoop()
                ll.after_report(
                    asset=getattr(self, "asset", "unknown"),
                    report_type=getattr(self, "report_type", "industry_deep"),
                    result={
                        "iron_gate": report.overall_score,
                        "passed": report.passed,
                        "failures": report.failures if isinstance(report.failures, list) else [],
                        "report_type": getattr(self, "report_type", "industry_deep"),
                    },
                )
                logger.info("[FP7a] Gate failure registered to LearningLoop")
            except Exception as e:
                logger.debug("[FP7a] LearningLoop: %s", e)

        # Observability: Record gate-level metrics
        try:
            GATE_RUNS.labels(report_type=self.report_type, result="pass" if report.passed else "fail").inc()
            GATE_SCORE.labels(report_type=self.report_type).observe(report.overall_score)
            for c in report.checks:
                GATE_CHECK_RESULT.labels(check_name=c.name, result="pass" if c.passed else "fail").inc()
        except Exception as e:
            logger.debug("Observability metrics recording failed: %s", e)

        # P1-1 (2026-09-01): 测量层通电——每次 run_all 写 validate_history + 当日质量趋势
        # 此前 validate_history 停在 7 月（17 条空记录）、quality_trends 0 条，
        # FP3 收敛曲线与 FP7a 质量趋势无数据可依。write-and-forget 不阻塞主流程。
        try:
            from core.metrics import ObservabilityDB, ValidateHistory

            _jd = 0.0
            if report.checks:
                for _c in report.checks:
                    if getattr(_c, "name", "") == "judgment_density" and getattr(_c, "score", None) is not None:
                        _jd = float(_c.score)
                        break
            _obs = ObservabilityDB()
            _obs.log_validation(
                ValidateHistory(
                    timestamp=datetime.datetime.now().isoformat(),
                    report_id=str(getattr(self, "asset", "") or "unknown"),
                    sac_coverage={
                        "covered": getattr(self, "sac_covered", 0),
                        "required": getattr(self, "sac_required", 0),
                        "passed": report.passed,
                    },
                    judgment_density=_jd,
                    style_deviation_score=0.0,
                    modification_count=0,
                    generation_duration_seconds=0.0,
                    passed=report.passed,
                    notes="auto-log from IronGate.run_all",
                )
            )
            _obs.record_quality_trend("gate_score_avg", report.overall_score, sample_size=1)
            _obs.record_quality_trend("gate_pass_rate", 1.0 if report.passed else 0.0, sample_size=1)
        except Exception as e:
            logger.debug("[P1-1] validate/quality trend 记录失败: %s", e)

        return report

    def _count_charts(self):
        # 统计真实嵌入的图表（markdown 图片），排除 placeholder 占位符
        real = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", self.report_text)
        non_placeholder = [p for p in real if "placeholder" not in p.lower() and "CHART" not in p]
        # 兼容未注入的 [CHART:id] 占位符（算作待生成图表，不计数）
        return len(non_placeholder)

    def _count_tables(self):
        md_tables = len(re.findall(r"^\|[-:| ]+\|$", self.report_text, re.MULTILINE))
        year_tables = len(re.findall(r"\u5e74[\uff1a:]", self.report_text))
        text_tables = len(re.findall(r"\d+[\.,]?\d*\s*[%亿元万]?\s+\d+[\.,]?\d*\s*[%亿元万]?", self.report_text))
        year_refs = len(re.findall(r"20\d{2}", self.report_text))
        return max(md_tables, min(text_tables // 3, 5), min(year_refs // 5, 3))

    def _run_critic_agent(self) -> tuple:
        """调用 Critic Agent 做语义评审"""
        try:
            from pipeline.agent_loop import ScoreEngine

            engine = ScoreEngine(report_type=self.report_type)
            score_result = engine.score(self.report_text, self.report_type)
            overall = score_result.get("overall", 0.5)
            if "deepseek_overall" in score_result:
                ds_overall = score_result["deepseek_overall"]
                overall = overall * 0.4 + ds_overall * 0.6
            feedback_lines = ["Critic Agent 评审结果:"]
            for dim, dim_score in score_result.get("dimensions", {}).items():
                status = "PASS" if dim_score >= 0.7 else "FAIL"
                feedback_lines.append("  [%s] %s: %.2f" % (status, dim, dim_score))
            if score_result.get("details"):
                for d in score_result["details"][:5]:
                    feedback_lines.append("  %s" % d)
            feedback = "\n".join(feedback_lines)
            return (overall, feedback)
        except Exception:
            raise

    # ══════════════════════════════════════════════════════════
    # R92（2026-08-10）：定向验证 + 失败分类（断点修复机制）
    # Gate 失败后只重跑失败项对应的检查（不全量重跑），并把失败项
    # 分类为 mechanical/semantic/environmental 以决定修复路径。
    # ══════════════════════════════════════════════════════════

    MECHANICAL_CHECKS = {
        "numeric_chain_consistency",
        "arithmetic_audit",
        "invariant_audit",
        "layout_quality",
        "placeholder_xxx",
        "placeholder_charts",
        "forbidden_patterns",
        "completeness_scan",
        "market_size_consistency",
        "indicator_consistency",
        "data_point_provenance",  # NEW: deterministic provenance check
        "csrc_compliance",  # NEW: deterministic compliance check
        "semantic_dedup",  # NEW: deterministic semantic dedup
    }
    SEMANTIC_CHECKS = {
        "so_what_chain",
        "chart_analysis_quality",
        "insight_quality",
        "persuasion_architecture",
        "counterargument_strength",
    }
    ENVIRONMENTAL_CHECKS = {
        "ai_tone_llm",
        "llm_data_verification",
        "human_impossible_dimension",
    }

    @classmethod
    def classify_failure(cls, check_name: str) -> str:
        if check_name in cls.MECHANICAL_CHECKS:
            return "mechanical"
        if check_name in cls.SEMANTIC_CHECKS:
            return "semantic"
        if check_name in cls.ENVIRONMENTAL_CHECKS:
            return "environmental"
        return "unknown"

    def check_only(self, check_names) -> GateReport:
        """定向验证：只跑指定检查项（断点修复后局部复验）。"""
        if isinstance(check_names, str):
            check_names = [check_names]
        _funcs = {n.replace("_check_", ""): getattr(self, n) for n in dir(self) if n.startswith("_check_")}
        report = GateReport()
        checks = []
        for _cn in check_names:
            _fn = _funcs.get(_cn)
            if not _fn:
                continue
            try:
                checks.append(_fn())
            except Exception as _e:
                checks.append(
                    GateCheckResult(
                        name=_cn, passed=False, score=0.0, details=f"检查异常: {str(_e)[:80]}", severity="error"
                    )
                )
        report.checks = checks
        report.overall_score = sum(max(0.0, min(1.0, c.score)) for c in checks) / max(len(checks), 1)
        report.passed = all(c.passed for c in checks if c.severity == "error")
        report.failures = ["[%s] %s: %s" % (c.severity.upper(), c.name, c.details) for c in checks if not c.passed]
        return report

    def report_failures(self, report=None) -> list:
        """返回失败项详情（含分类）。"""
        if report is None:
            report = self.run_all()
        return [
            {"name": c.name, "severity": c.severity, "details": c.details, "class": self.classify_failure(c.name)}
            for c in report.checks
            if not c.passed
        ]

    # ══════════════════════════════════════════════════════════
    # R55（2026-08-03 方法论升级）：行业报告质量护栏
    # ══════════════════════════════════════════════════════════

    # P1-audit 2026-08-24：_check_methodology_compliance 已迁入
    # pipeline/checks/analysis_mixin.py（r61 迁移完整性要求检查方法
    # 统一存放于 checks/，此处保留会破坏 AST 扫描的 defined==executed 断言）

    def _check_csrc_compliance(self):
        """CSRC/交易所研报合规五大硬性要求"""
        import re

        from pipeline.checks.base import GateCheckResult

        _COMPLIANCE_RULES = [
            ("rating_definition", r"评级定义|评级说明|买入.*增持.*持有.*减持.*卖出", "必须包含评级定义表"),
            ("conflict_disclosure", r"利益冲突|无利益冲突|相关披露", "必须有利益冲突声明"),
            ("important_notice", r"重要提示|风险提示|免责声明", "必须有重要提示章节"),
            ("no_guarantee", r"不构成.*投资建议|不保证.*收益|过往业绩不代表", "禁止承诺收益/保证语言"),
            ("analyst_certification", r"分析师.*资格|SAC.*执业|注册分析师", "需含分析师资格认证"),
        ]

        failures = []
        for name, pattern, desc in _COMPLIANCE_RULES:
            if not re.search(pattern, self.report_text, re.I):
                failures.append(f"[{name}] {desc}")
        if failures:
            return GateCheckResult("csrc_compliance", False, 0.0, "; ".join(failures), "error")
        return GateCheckResult("csrc_compliance", True, 1.0, "all 5 rules present")

    # ============================================================
    # NEW: DataPoint Provenance Completeness Check (Phase 1.3)
    # ============================================================

    def _check_data_point_provenance(self):
        """每个 DataPoint 必须有 source/access_ts/excerpt_sha256/confidence/unit"""
        from core.models import DataPoint
        from pipeline.checks.base import GateCheckResult

        cd = getattr(self, "collected_data", {}) or {}
        dps = cd.get("data_points", [])
        missing = []
        for dp in dps:
            if isinstance(dp, DataPoint):
                for field in ["source", "access_ts", "excerpt_sha256", "confidence", "unit"]:
                    if not getattr(dp, field, None):
                        missing.append(f"{dp.name}.{field}")
        if missing:
            return GateCheckResult(
                "data_point_provenance", False, 0.0, f"{len(missing)} 字段缺失: {missing[:5]}", "error"
            )
        return GateCheckResult("data_point_provenance", True, 1.0, "all fields present")

    # ============================================================
    def _check_semantic_dedup(self):
        """语义去重：用 sentence-transformers 向量化段落，余弦相似度 >0.85 视为语义重复"""
        from pipeline.checks.base import GateCheckResult

        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer
        except ImportError:
            return GateCheckResult("semantic_dedup", True, 1.0, "sentence-transformers not installed, skipped")

        # Split into paragraphs
        paras = [p.strip() for p in self.report_text.split("\n\n") if len(p.strip()) > 60]
        if len(paras) < 2:
            return GateCheckResult("semantic_dedup", True, 1.0, "insufficient paragraphs")

        # Load model (cache globally in production)
        try:
            model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        except Exception as e:
            return GateCheckResult("semantic_dedup", True, 0.5, f"model load failed: {e}")

        # Encode paragraphs
        try:
            embeds = model.encode(paras, normalize_embeddings=True, show_progress_bar=False)
        except Exception as e:
            return GateCheckResult("semantic_dedup", True, 0.5, f"encoding failed: {e}")

        # Find duplicates
        dup_pairs = []
        threshold = 0.85
        for i in range(len(embeds)):
            for j in range(i + 1, len(embeds)):
                sim = float(np.dot(embeds[i], embeds[j]))
                if sim > threshold:
                    dup_pairs.append((paras[i][:80], paras[j][:80], sim))

        if dup_pairs:
            details = "; ".join([f"{a}... ~ {b}... (sim={s:.2f})" for a, b, s in dup_pairs[:5]])
            return GateCheckResult("semantic_dedup", False, 0.0, f"{len(dup_pairs)} 语义重复段落: {details}", "error")

        return GateCheckResult("semantic_dedup", True, 1.0, "no semantic duplicates")

    # ============================================================
    # NEW: Semantic Deduplication Gate (Phase 5.3)

    # ============================================================
    # NEW: DataPoint Provenance Completeness Check (Phase 1.3)
    # ============================================================

    def _check_data_point_provenance(self):
        """每个 DataPoint 必须有 source/access_ts/excerpt_sha256/confidence/unit"""
        from core.models import DataPoint
        from pipeline.checks.base import GateCheckResult

        cd = getattr(self, "collected_data", {}) or {}
        dps = cd.get("data_points", [])
        missing = []
        for dp in dps:
            if isinstance(dp, DataPoint):
                for field in ["source", "access_ts", "excerpt_sha256", "confidence", "unit"]:
                    if not getattr(dp, field, None):
                        missing.append(f"{dp.name}.{field}")
        if missing:
            return GateCheckResult(
                "data_point_provenance", False, 0.0, f"{len(missing)} 字段缺失: {missing[:5]}", "error"
            )
        return GateCheckResult("data_point_provenance", True, 1.0, "all fields present")


def _detect_value_conflicts(report_text: str, data_dict: dict) -> list:
    """检测正文与数据字典的数值冲突（数据打架）。

    只针对高可信标签：market_size_*（市场规模/空间）—— 这是数据打架最高发区，
    且口径清晰（亿元/亿美元）。营收/利润等标签因口径复杂（含税/不含税、行业/公司）
    容易误报，交由游离数字校验（validate_numeric_refs）兜底。

    思路：数据字典的 ref_key 形如 `market_size_china_2024=4061.2`。
    从 key 里提取"标签词"和"年份"。若正文出现同一标签+年份的数值，
    但数值与数据字典差异 >10% 或单位不一致 → 冲突。
    例：数据字典 market_size_china_2024=4061.2，正文写"2024中国传感器市场3440亿元" → 冲突。
    """
    if not data_dict:
        return []
    conflicts = []
    # 修复（2026-08-01 IronGate 第 2 轮）：conflict_labels 原先把 market_size_china
    # 硬编码为"中国传感器市场"（柯力传感专用），思必驰（对话式 AI）报告的
    # market_size_china 实际指"中国对话式 AI 市场"，硬编码行业名与泛词
    # （营收|利润|…）组合导致跨指标串标误报（正文"2023-2025 年营收
    # 5.39/6.01/6.88 亿元"的"88"被误当"中国传感器市场 2025"）。
    # 修复：①行业名不再硬编码，优先从 data_dict 读取行业/公司字段，缺省用
    # 通用"市场规模"；②泛词按 label 类型分类（market_size 只认市场规模类词），
    # 杜绝营收/利润词串入市场标签；③数字正则允许小数点（\d+），并加
    # (?<![\d.]) 前置断言防止从 "6.88" 中截取 "88"。
    conflict_labels = {
        "market_size_china": "市场规模",
        "market_size_global": "市场规模",
        "revenue_total": "总营收",
        "revenue_main": "主营业务收入",
        "profit_net": "净利润",
        "profit_gross": "毛利润",
        "margin_gross": "毛利率",
        "margin_net": "净利率",
        "margin_operating": "营业利润率",
        "growth_revenue": "营收增速",
        "growth_profit": "利润增速",
        "eps_basic": "基本每股收益",
        "eps_diluted": "稀释每股收益",
        "pe_ttm": "市盈率(TTM)",
        "pe_forward": "预测市盈率",
    }
    # 泛词按 label 类型分类：只匹配本指标相关词，防止跨指标串标
    _generic_by_label = {
        "market_size_china": "市场规模|市场空间",
        "market_size_global": "市场规模|市场空间",
        "revenue_total": "总营收|主营业务收入|营收|收入",
        "revenue_main": "总营收|主营业务收入|营收|收入",
        "profit_net": "净利润|利润",
        "profit_gross": "毛利润|毛利",
        "margin_gross": "毛利率",
        "margin_net": "净利率",
        "margin_operating": "营业利润率",
        "growth_revenue": "营收增速|收入增速|增速|增长率",
        "growth_profit": "利润增速|增速|增长率",
        "eps_basic": "基本每股收益|每股收益|EPS",
        "eps_diluted": "稀释每股收益|每股收益|EPS",
        "pe_ttm": "市盈率|PE",
        "pe_forward": "预测市盈率|市盈率|PE",
    }
    # 行业名优先从 data_dict 读取（如 industry/market_name/company_name），
    # 用于报错文案；匹配本身依赖 label 类型泛词，不再依赖行业名。
    _asset_name = ""
    for _k in ("industry_name", "industry", "market_name", "company_name", "asset_name", "name"):
        _v = data_dict.get(_k)
        if isinstance(_v, str) and _v.strip():
            _asset_name = _v.strip()
            break
    known = {}  # (label, year) -> value
    # 匹配模式扩展：覆盖市场类 + 财务指标类标签
    _conflict_pattern = (
        r"^(market_size_china|market_size_global|"
        r"revenue_total|revenue_main|"
        r"profit_net|profit_gross|"
        r"margin_gross|margin_net|margin_operating|"
        r"growth_revenue|growth_profit|"
        r"eps_basic|eps_diluted|"
        r"pe_ttm|pe_forward)"
        r"_(\d{4})(?:_\w+)?$"
    )
    for key, val in data_dict.items():
        m = re.match(_conflict_pattern, key)
        if m and isinstance(val, (int, float)):
            known.setdefault((m.group(1), m.group(2)), []).append(float(val))
    if not known:
        return []
    for (label, year), known_vals in known.items():
        label_zh = conflict_labels.get(label, label)
        if _asset_name:
            label_zh = f"{_asset_name}{label_zh}"
        generic = _generic_by_label.get(label, label_zh)
        expected_unit = "亿美元" if label == "market_size_global" else "亿元"
        # 增长率类标签可能是百分数，使用"%"单位
        if label.startswith("growth_") or label.startswith("margin_"):
            expected_unit = "%"
        if label.startswith("eps_"):
            expected_unit = "元"
        if label.startswith("pe_"):
            expected_unit = "倍"
        # 年份可出现在指标词前或后；数字完整提取（含小数）并加前置边界，
        # 避免从 "6.88" 中截取 "88"。
        pat = re.compile(
            rf"(?:{year}年?(?:[^\n。]{{0,12}})?(?:{generic})|(?:{generic})[^\n。]{{0,12}}?{year}年?)"
            rf"[^\n。]{{0,20}}?(?<![\d.])(\d+(?:\.\d{{1,3}})?)\s*({expected_unit})"
        )
        for m in pat.finditer(report_text):
            try:
                body_val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            unit = m.group(2)
            # P1-3（2026-08-07）：币种维度区分——market_size 类标签允许
            # 美元/人民币混写（如 46亿美元 ≈ 326亿元），单位不一致时先按
            # 1 USD ≈ 7 CNY 归一化再比对；归一化后偏差<10% 不算冲突。
            if unit != expected_unit:
                if label.startswith("market_size_"):
                    _is_usd = ("美元" in unit) or ("USD" in unit.upper())
                    _expected_usd = ("美元" in expected_unit) or ("USD" in expected_unit.upper())
                    if _is_usd != _expected_usd:
                        if _is_usd:
                            body_val_norm = body_val * 7.0
                        else:
                            body_val_norm = body_val / 7.0
                        for kv in known_vals:
                            if abs(body_val_norm - kv) / max(abs(kv), 1e-9) < 0.10:
                                break
                        else:
                            conflicts.append(
                                f"{label_zh}{year}年 币种口径冲突({unit} vs 数据层{expected_unit}，"
                                f"正文值{body_val:.0f}{unit}≈{body_val_norm:.1f}{expected_unit})"
                            )
                            break
                        continue
                conflicts.append(f"{label_zh}{year}年 单位口径冲突({unit} vs 数据层{expected_unit})")
                break
            for kv in known_vals:
                if abs(body_val - kv) / max(abs(kv), 1e-9) < 0.10:
                    break
            else:
                conflicts.append(f"{label_zh}{year}年 正文写{body_val:.0f}{unit} vs 数据层{known_vals[0]:.0f}")
                break  # 每标签只报一处
    return conflicts[:5]


# ═══════════════════════════════════════════════════════════
# NEW: CSRC/交易所合规门禁 (Phase 2.1)
# ═══════════════════════════════════════════════════════════


print("test")
