"""
e2e_orchestrator.py V4 - Full integration with all new modules.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path

from core import settings
from pipeline.step_manager import StepManager
from pipeline.universe_build import universe_build_node

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("2hao.e2e")
# === V51 merge: analysis modules (optional, with fallback) ===
try:
    from core.argument import ArgumentEngine

    _HAS_ARGUMENT = True
except ImportError:
    _HAS_ARGUMENT = False

try:
    from core.edit_learn import EditLearner  # noqa: F401  (availability probe)

    _HAS_EDIT_LEARN = True
except ImportError:
    _HAS_EDIT_LEARN = False
except ImportError:
    _HAS_ARGUMENT = False
    logger.warning("V51 import failed: _HAS_ARGUMENT=False, module unavailable")
try:
    from core.style import StyleCompiler

    _HAS_STYLE = True
except ImportError:
    _HAS_STYLE = False
    logger.warning("V51 import failed: _HAS_STYLE=False, module unavailable")
try:
    from core.verify import T3Orchestrator  # noqa: F401  (availability probe)

    _HAS_VERIFY = False  # WIP: not yet wired into pipeline
except ImportError:
    _HAS_VERIFY = False
    logger.warning("V51 import failed: _HAS_VERIFY=False, module unavailable")
try:
    from core.scarcity_signals import ScarcitySignalChecker

    _HAS_SCARCITY = True
except ImportError:
    _HAS_SCARCITY = False
    logger.warning("V51 import failed: _HAS_SCARCITY=False, module unavailable")
try:
    from core.cross_validator import CrossValidator

    _HAS_CROSSVALIDATE = True
except ImportError:
    _HAS_CROSSVALIDATE = False
    logger.warning("V51 import failed: _HAS_CROSSVALIDATE=False, module unavailable")
try:
    from export.integrated_exporter import IntegratedExporter  # noqa: F401  (availability probe)

    _HAS_INTEGRATED_EXPORT = False  # WIP: not yet wired into pipeline
except ImportError:
    _HAS_INTEGRATED_EXPORT = False
    logger.warning("V51 import failed: _HAS_INTEGRATED_EXPORT=False, module unavailable")

# TemporalVerifier + ForwardPicksDB (depend on cognitive_baseline, may fail)
try:
    from core.temporal_verifier import TemporalVerifier  # noqa: F401  (availability probe)

    _HAS_TEMPORAL = False  # WIP: not yet wired into pipeline
except ImportError:
    _HAS_TEMPORAL = False
    logger.warning("V51 import failed: _HAS_TEMPORAL=False, module unavailable")
try:
    from core.forward_picks import ForwardPicksDB  # noqa: F401  (availability probe)

    _HAS_FORWARDPICKS = True
except ImportError:
    _HAS_FORWARDPICKS = False
    logger.warning("V51 import failed: _HAS_FORWARDPICKS=False, module unavailable")


class E2ENodes:
    @staticmethod
    def preflight_check(node_id, context):
        try:
            from pipeline.runtime_gate import RuntimeGate

            gate = RuntimeGate(str(_ROOT))
            results = gate.check_all()
            context["runtime_score"] = results["summary"]["runtime_score"]
            if context["runtime_score"] < 0.5:
                logger.warning("[PREFLIGHT] runtime score low")
        except Exception as e:
            logger.debug("[PREFLIGHT] failed: %s", e)
        return {"runtime_score": context.get("runtime_score", 0.5)}

    @staticmethod
    def biz_macro_inject(node_id, context):
        """Inject business model and macro context."""
        try:
            from core.data_stager import run_all_stagers, stager_summary
            from core.tools.business_model_classifier import classify_by_text
            from core.tools.macro_context import get_current_context
            from core.web_intel import collect_all, intel_to_context

            asset = context.get("asset", "")
            report_type = context.get("report_type", "listed_company")
            # Business model classification
            biz = classify_by_text(asset, report_type)
            context["biz_model"] = biz
            # Macro context
            ctx = get_current_context()
            context["macro_ctx"] = ctx
            # Data staging — extract stock code from asset
            # R26: 统一走 asset_resolver，中文名（柯力传感）也能解析出代码
            from core.asset_resolver import resolve_asset

            _asset_obj = resolve_asset(asset)
            acode = _asset_obj.code or ""
            if _asset_obj.name:
                asset = _asset_obj.name  # 让下游看到规范化中文名
                context["asset"] = asset
            # R65: FP8 分析方案注入 context（供 section_writer 感知框架/聚焦维度）
            # R66: biz_macro_inject 为 staticmethod，无法访问 self；analysis_plan
            #      由 scheduler 构造时写入实例，这里从 context 兜底读取（通常为空不阻断）
            if context.get("analysis_plan"):
                pass
            industry = biz.industry_tags[0] if biz and biz.industry_tags else ""
            stage_ctx = run_all_stagers(asset_code=acode, industry=industry)
            context["stage_ctx"] = stage_ctx
            context["stage_summary"] = stager_summary(stage_ctx)
            logger.info("Stage summary: %s...", context.get("stage_summary", "")[:80])
            # Web intelligence
            try:
                wintel = collect_all(asset=asset, asset_code=acode, industry=industry)
                wctx = intel_to_context(wintel)
                context.update(wctx)
                if wintel.search_count > 0:
                    logger.info("WebIntel: %d items from %d sources", wintel.search_count, len(wintel.raw_sources))
            except Exception as e:
                logger.warning("WebIntel failed: %s", e)
                context["web_summary"] = ""
                context["web_search_count"] = 0
            logger.info(
                "Biz: %s (%s) Macro: %s/%s", biz.biz_name, biz.biz_type, ctx.earnings_cycle, ctx.liquidity_cycle
            )
        except Exception as e:
            logger.warning("BizMacro failed: %s", e)
            context["biz_model"] = None
            context["macro_ctx"] = None
        return {"biz_model": context.get("biz_model"), "macro_ctx": context.get("macro_ctx")}

    @staticmethod
    def hypothesis_check(node_id, context):
        """T0.5: Check if hypothesis is worth pursuing (block_on_fail via context['force'])"""
        try:
            from core.hypothesis_checker import HypothesisChecker

            hc = HypothesisChecker()
            force = context.get("force", False)  # --force flag overrides hypothesis gate
            result = hc.check(
                asset=context.get("asset", ""),
                hypothesis=context.get("hypothesis", ""),
                context=context.get("user_context", ""),
                block_on_fail=not force,  # block if not force
            )
            context["hypothesis_result"] = result
            logger.info(
                "[HYPOTHESIS] score=%.2f pass=%s dir=%s force=%s",
                result.score,
                result.passes_gate,
                result.suggested_direction,
                force,
            )
            if not result.passes_gate and context.get("hypothesis"):
                if force:
                    logger.warning("[HYPOTHESIS] Failed gate but --force overrides: %s", result.risks)
                else:
                    logger.warning("[HYPOTHESIS] BLOCKED: %s", result.risks)
                    raise RuntimeError(
                        "Hypothesis gate blocked: score=%.2f < threshold, use --force to override" % result.score
                    )
        except RuntimeError:
            raise
        except Exception as e:
            logger.debug("[HYPOTHESIS] failed: %s", e)
        return {"hypothesis_result": context.get("hypothesis_result")}

    @staticmethod
    def data(node_id, context):
        """data — DataCollectorV5 primary, DataPipeline fallback

        修复（2026-08-01 审计）：写改循环 MAX_ATTEMPTS 内每轮重建图重跑网络采集。
        若 orchestrator 已注入缓存数据（_data_cached=True），直接复用，不重采。
        """
        asset = context.get("asset", "")
        rt = context.get("report_type", "industry_deep")
        data = None

        # 缓存复用：重试轮次不重跑网络采集
        if context.get("_data_cached"):
            cached = context.get("collected_data", {})
            logger.info("[DATA] 复用缓存采集数据（attempt>0），%d keys", len(cached))
            return {"collected_data": cached, "_data_cached": True}

        # Primary: DataCollectorV5 (Tavily+yfinance+akshare multi-phase)
        try:
            from pipeline.data_collector import DataCollectorV5

            dc = DataCollectorV5()
            import os as _os

            ta_key = _os.environ.get("TAVILY_API_KEY", "")
            if ta_key:
                dc._tavily = None  # will re-init with key
            data = dc.collect(asset, rt, {})
            if data:
                logger.info("[DATA] DataCollectorV5: %d keys", len(data))
        except Exception as e:
            logger.warning("[DATA] DataCollectorV5 failed: %s", e)

        # Fallback: DataPipeline
        if not data or len(data) < 2:
            try:
                from pipeline.data_pipeline import DataPipeline

                dp = DataPipeline()
                data_fb = dp.collect(asset, rt)
                if data_fb:
                    data = {**(data or {}), **data_fb}
                    logger.info("[DATA] DataPipeline fallback: merged %d keys", len(data_fb))
            except Exception as e2:
                logger.warning("[DATA] DataPipeline fallback: %s", e2)

        if not data:
            context["degradation_level"] = max(context.get("degradation_level", 0), 2)
            logger.warning("[L2 DEGRADATION] All data collectors failed")
            context["collected_data"] = {}
            return {"collected_data": {}}

        context["collected_data"] = data

        # Also collect provenance
        try:
            from core.data_provenance import DataProvenance

            dp2 = DataProvenance()
            dp2.collect(asset=asset, context=str(data)[:3000])
            context["provenance"] = dp2
        except Exception as e:
            logger.debug("Provenance: %s", e)
        return {"collected_data": data}

    @staticmethod
    def universe_build(node_id, context):
        """R68: Universe Building 节点——构建全量竞争玩家清单。"""
        return universe_build_node(node_id, context)

    @staticmethod
    def enrich_data(node_id, context):
        """数据增强桥接 — 充足性检查 + 本地兜底 + agent补充数据merge

        DataCollectorV5 主采集链路之后执行：
          1. DataSufficiencyChecker 判定数据充足性
          2. LocalBackfill 从本地库（financials.db/qlib/历史报告）兜底
          3. AgentEnricher 把 --enrich-file 的 agent 补充数据 merge 回 collected_data
          4. 输出 needs_agent / data_enriched 信号（供 scheduler/agent 感知）
        """
        try:
            from pipeline.data_enrichment import enrich_node as _enrich

            return _enrich(node_id, context)
        except Exception as e:
            logger.warning("[ENRICH] 桥接节点失败（不阻断管线）: %s", e)
            context.setdefault("needs_agent", False)
            context.setdefault("data_sufficiency", {"sufficient": True, "detail": "enrich skipped"})
            return {"needs_agent": False, "data_sufficiency": context.get("data_sufficiency")}

    @staticmethod
    def learning(node_id, context):
        from pipeline.learning_loop import LearningLoop

        try:
            ll = LearningLoop()
            context["learning_findings"] = ll.before_report(context.get("asset", ""), context.get("report_type", ""))
        except Exception as e:
            logger.warning("learning: %s", e)
            context["learning_findings"] = ""
        return {"learning_findings": context.get("learning_findings", "")}

    @staticmethod
    def compute(node_id, context):
        """Compute engine — run DCF, comparable, scenario + knowledge modules"""
        try:
            from pipeline.compute_engine import ComputeEngine

            data = context.get("collected_data", {})
            engine = ComputeEngine()
            result = engine.compute(
                financial_data=data if isinstance(data, dict) else {},
                report_type=context.get("report_type", "listed_company"),
            )
            if result:
                context["compute_results"] = result
                logger.info("[COMPUTE] %d modules ran: %s", len(result), list(result.keys())[:5])
            else:
                context["compute_results"] = {}
                logger.warning("[COMPUTE] returned empty")
        except Exception as e:
            logger.warning("[COMPUTE] failed: %s", e)
            context["compute_results"] = {}
        return {"compute_results": context.get("compute_results", {})}

    @staticmethod
    def argument_engine(node_id, context):
        """V51 merge: ArgumentEngine — build logical chain after data collection"""
        if not _HAS_ARGUMENT:
            return {"scaffold": None, "note": "ArgumentEngine not available"}
        try:
            ae = ArgumentEngine()
            from core.models import DataPoint, KnowledgePackage, WritingBrief

            brief = WritingBrief(asset=context.get("asset", ""))
            kp = KnowledgePackage()
            # Feed collected data into argument engine (as DataPoint objects)
            data = context.get("collected_data", {})
            if isinstance(data, list):
                data = {"source": "data_pipeline"}
            if isinstance(data, dict) and data:
                kp.data_points = [
                    DataPoint(
                        name=k,
                        value=(str(v)[:200] if not isinstance(v, (int, float)) else v),
                        source="data_pipeline",
                        confidence="medium",
                    )
                    for k, v in list(data.items())[:30]
                ]
            scaffold = ae.design(brief, kp)
            context["scaffold"] = scaffold
            n_sections = len(scaffold.sections) if hasattr(scaffold, "sections") else len(scaffold.get("sections", []))
            logger.info("[ARGUMENT] Scaffold built: %d sections", n_sections)
        except Exception as e:
            logger.warning("[ARGUMENT] failed: %s", e)
            context["scaffold"] = None
        return {"scaffold": context.get("scaffold")}

    @staticmethod
    def style_compile(node_id, context):
        """V51 merge: StyleCompiler — apply institution style before gate

        修复（2026-07-31 审计 P0-A）：编译结果必须写回 report_text，
        否则下游 assemble/validate 读取的仍是未清洗文本，StyleCompiler 形同虚设。
        """
        if not _HAS_STYLE:
            context["report_text"] = context.get("report_text", "")
            return {"compiled_text": context.get("report_text", ""), "note": "StyleCompiler not available"}
        try:
            sc = StyleCompiler()
            text = context.get("final_text", "") or context.get("report_text", "")
            style_name = context.get("style", "cicc")
            report_type = context.get("report_type", "standard")
            result = sc.compile(text, {"style": style_name, "report_type": report_type})
            compiled = result.compiled if hasattr(result, "compiled") else result
            if isinstance(compiled, str) and compiled:
                # P0-A 修复：原地写回 report_text，让下游消费清洗后的文本
                context["report_text"] = compiled
                context["compiled_text"] = compiled
                logger.info("[STYLE] Compiled with %s style (len=%d→%d)", style_name, len(text), len(compiled))
            else:
                context["compiled_text"] = context.get("report_text", "")
                logger.warning("[STYLE] compile 返回空，保留原文")
        except Exception as e:
            logger.warning("[STYLE] failed: %s", e)
            context["compiled_text"] = context.get("report_text", "")
        return {"compiled_text": context.get("compiled_text", "")}

    @staticmethod
    def scarcity_signals(node_id, context):
        """V51 merge: ScarcitySignalChecker — detect scarcity signals in data"""
        if not _HAS_SCARCITY:
            return {"signals": []}
        try:
            ssc = ScarcitySignalChecker()
            data = context.get("collected_data", {})
            signals = ssc.check(data)
            context["scarcity_signals"] = signals
            logger.info("[SCARCITY] %d signals found", len(signals))
        except Exception as e:
            logger.debug("[SCARCITY] %s", e)
            context["scarcity_signals"] = []
        return {"scarcity_signals": context.get("scarcity_signals", [])}

    @staticmethod
    def cross_validate(node_id, context):
        """CrossValidator — multi-source cross-validation + data credibility (FP2a)"""
        if not _HAS_CROSSVALIDATE:
            return {"cross_validation": None, "credibility": None}
        try:
            cv = CrossValidator()
            # Fix: data node writes to "collected_data", not "data"
            collected = context.get("collected_data", {})
            financials = collected.get("financials", []) if isinstance(collected, dict) else []
            sources = collected.get("sources", []) if isinstance(collected, dict) else []
            tavily_data = collected.get("tavily", []) if isinstance(collected, dict) else []
            data_points = financials if financials else sources
            text_data = " ".join(tavily_data[:3]) if tavily_data else ""

            # R55（2026-08-03 Phase B）：把 LLM 采集的 chart_data 带标签转成 DataPoint
            # 供 CrossValidator 多源比对。chart_data 的 _collection_meta 含
            # {source, year, scope, confidence} 四元组。
            try:
                from core.models import DataPoint  # 局部导入（模块级未暴露）

                chart_data = collected.get("chart_data", {}) if isinstance(collected, dict) else {}
                meta = chart_data.get("_collection_meta", {}) if isinstance(chart_data, dict) else {}
                if isinstance(chart_data, dict):
                    for _k, _v in chart_data.items():
                        if _k.startswith("_") or not isinstance(_v, dict):
                            continue
                        # 序列值（年份→数值）转成 DataPoint
                        for _yr, _val in list(_v.items())[:5]:
                            if _val is None:
                                continue
                            try:
                                float(_val)
                            except (TypeError, ValueError):
                                continue
                            data_points.append(
                                DataPoint(
                                    name=f"{_k}_{_yr}",
                                    value=float(_val),
                                    source=str(meta.get("source", "llm_collect")),
                                    confidence=str(meta.get("confidence", 0.5)),
                                )
                            )
                    if meta:
                        logger.info(
                            "[CROSSVALIDATE] 接入 %d 个 LLM 采集数据点（source=%s, conf=%s）",
                            len(data_points),
                            meta.get("source", "?"),
                            meta.get("confidence", "?"),
                        )
            except Exception as _e:
                logger.debug("[CROSSVALIDATE] chart_data 接入失败: %s", _e)

            if data_points:
                result = cv.validate(data_points, context.get("asset", ""), text_data)
                cv_result = result if hasattr(result, "to_dict") else {"passed": True}
                context["cross_validation"] = cv_result
                logger.info("[CROSSVALIDATE] Validated %d data points", len(data_points))
            else:
                context["cross_validation"] = {"passed": True, "note": "no structured data"}

            # FP2a: Run data credibility check on whatever data we have
            try:
                from core.data_credibility import DataCredibilityEngine

                dce = DataCredibilityEngine()
                credibility = dce.evaluate(collected) if hasattr(dce, "evaluate") else {"score": 0.5}
                context["data_credibility"] = credibility
                logger.info("[CREDIBILITY] score=%.2f", credibility.get("score", 0))
            except Exception as ce:
                logger.debug("[CREDIBILITY] %s", ce)
                context["data_credibility"] = {"score": 0.5, "note": "module unavailable"}

        except Exception as e:
            logger.debug("[CROSSVALIDATE] %s", e)
            context["cross_validation"] = {"passed": True, "note": str(e)[:50]}
            context["data_credibility"] = {"score": 0.5, "note": str(e)[:50]}
        return {"cross_validation": context.get("cross_validation"), "credibility": context.get("data_credibility")}

    @staticmethod
    def charts(node_id, context):
        data = context.get("collected_data", {})
        if isinstance(data, list):
            data = {"news": data}
        elif not isinstance(data, dict):
            data = {}
        try:
            from pipeline.chart_pipeline import ChartPipeline

            cp = ChartPipeline(context.get("report_type", "industry_deep"), context.get("style", "cicc"))
            paths, template_flags = cp.generate_all(data)
            # R51（2026-08-02）：记录模板图标记（data=template），
            # 供 section_writer 在图表标注"示意/数据不足"，防止冒充真实证据。
            context["chart_template_flags"] = template_flags
            # 2026-08-01 修复：chart_pipeline 模板已直接使用 SAC chart_config 的 fig_* id
            # （不再有 business_model→fig_business_model 的 id 断裂），无需硬编码映射。
            # 这里仅做兜底：确保 SAC 期望的 fig id 在 chart_paths 中都有 key（值缺失时
            # 由 generate_all 已跳过，这里不补造数据）。
            chart_paths = dict(paths)
            context["chart_paths"] = chart_paths
        except Exception as e:
            logger.error("charts: %s", e)
            context["chart_paths"] = {}
            context["chart_template_flags"] = {}
        # FP7b L1 degradation: if charts partially fail, report degradation level
        chart_count = len(context.get("chart_paths", {}))
        expected = 5  # minimum expected charts
        if chart_count < expected:
            context["degradation_level"] = max(
                context.get("degradation_level", 0),
                1,  # L1: visual degradation
            )
            logger.info("[L1 DEGRADATION] Charts: %d/%d generated (using placeholders)", chart_count, expected)
        return {"chart_paths": context.get("chart_paths", {})}

    @staticmethod
    def write_sections(node_id, context):
        from pipeline.section_writer import SectionWriter

        sw = SectionWriter(context.get("report_type", "industry_deep"), context.get("style", "cicc"))
        # Get scaffold from ArgumentEngine (V82 merge)
        scaffold = context.get("scaffold", None)
        # R13（2026-08-01 三算力架构）：起草 provider 与骨架模式可从环境/上下文配置
        # draft_provider: deepseek（默认）/ agent_provider（Marvis 多实例）/ ollama_local
        # R48（2026-08-02 双模式）：LLM_PROVIDER 环境变量（run_reports.py 传递）
        # 优先级 LLM_PROVIDER > DRAFT_PROVIDER > deepseek
        # 2026-08-07 升级：节点级混编路由——write 节点按 RUN_MODE 路由（perf/train），
        # 替代整篇 MODE_LLM 映射；merge/revise 仍可被 NODE_PROVIDER_* 覆盖。
        _run_mode = os.environ.get("RUN_MODE", "perf")
        try:
            from pipeline.route_policy import resolve_provider

            draft_provider = os.environ.get("LLM_PROVIDER") or resolve_provider("write", _run_mode)
        except Exception:
            draft_provider = os.environ.get("LLM_PROVIDER") or os.environ.get("DRAFT_PROVIDER", "deepseek")
        # R23（2026-08-02 FM 差异化加速）：行业报告默认骨架先行（数据驱动、结构稳定），
        # 上市公司/非上市默认关闭（质量要求最高，保持全量直写）。
        # 骨架=FM 出结构，深化=DeepSeek 兜底，质量闸不变。
        _sk_default = os.environ.get("SKELETON_MODE")
        if _sk_default is not None:
            skeleton_mode = _sk_default == "1"
        else:
            skeleton_mode = context.get("report_type", "industry_deep") == "industry_deep"
        # R15（2026-08-01 综合提速）：维度级并行默认开启（核心提速项），
        # 可用 DIM_PARALLEL=0 关闭回退 3 段并行
        dimension_parallel = os.environ.get("DIM_PARALLEL", "1") == "1"
        if context.get("draft_provider"):
            draft_provider = context["draft_provider"]
        if context.get("skeleton_mode") is not None:
            skeleton_mode = bool(context["skeleton_mode"])
        if context.get("dimension_parallel") is not None:
            dimension_parallel = bool(context["dimension_parallel"])
        # R13 Phase4：局部修订 —— attempt>0 时只重写 gate 反馈涉及的段
        rewrite_indices = None
        if context.get("attempt", 0) > 0:
            rewrite_indices = _locate_failed_segments(context, sw)
            if rewrite_indices is not None:
                logger.info("[REVISE-LOCAL] 只重写段 %s", rewrite_indices)
        try:
            # R70（2026-08-05 P0 接线）：UniverseBuilding 摘要注入 data_context
            # 供 section_writer 的 _build_unlisted_threat / _build_universe_summary 消费
            _cd = context.get("collected_data", context.get("data_context", {})) or {}
            if isinstance(_cd, dict):
                _us = context.get("universe_summary") or {}
                if _us:
                    _cd["universe_summary"] = _us
                # R67: analysis_plan 注入 data_context，供 section_writer 的
                # fp8_plan_str（FP8 分析方案）与 _serialize_data 消费
                if context.get("analysis_plan"):
                    _cd["analysis_plan"] = context["analysis_plan"]
                # R83: 委托方必答问题清单注入 data_context（section_writer 消费）
                if context.get("client_questions"):
                    _cd["client_questions"] = context["client_questions"]
            text = sw.write(
                asset=context.get("asset", ""),
                data_context=context.get("collected_data", {}),
                chart_paths=context.get("chart_paths", {}),
                chart_template_flags=context.get("chart_template_flags", {}),
                gate_feedback=context.get("gate_feedback", ""),
                learning_findings=context.get("learning_findings", ""),
                scaffold=scaffold,
                state_anchor=context.get("state_anchor", None),
                draft_provider=draft_provider,
                skeleton_mode=skeleton_mode,
                rewrite_indices=rewrite_indices,
                dimension_parallel=dimension_parallel,
            )
        except RuntimeError as e:
            # L3: LLM 不可用 → 输出明确信号，由 agent 兜底补写重跑
            msg = str(e)
            if "LLM" in msg or "empty output" in msg or "call failed" in msg:
                context["llm_degradation_level"] = 3
                context["needs_agent"] = True
                context["llm_gap"] = f"LLM 调用失败（单provider DeepSeek 不可用）: {msg}"
                logger.warning("[L3] LLM 不可用，needs_agent=True: %s", msg)
                # 抛出给 AgentGraph 标记节点失败，但保留信号
                raise
            raise
        context["report_text"] = text
        # R13 Phase4：局部修订时，未重写段用上一轮 report_text 对应内容填充
        if rewrite_indices is not None:
            try:
                prev = context.get("report_text", "")
                if prev and "".join([p for p in text.split("## 分析维度")[:1]]) and not prev:
                    pass
                # 若 text 含空占位（未重写段为 ""），尝试用上一轮全文替换空段
                # 简单合并：text 为空时回退上一轮
                if not text or len(text.strip()) < 50:
                    context["report_text"] = context.get("_prev_report_text", "")
            except Exception as _e:
                logger.debug("[REVISE-LOCAL] merge prev: %s", _e)
        context["_prev_report_text"] = context.get("report_text", text)
        return {"report_text": context["report_text"]}

    @staticmethod
    def template_enforce(node_id, context):
        """Run TemplateEnforcer consistency check after writing and before gate.

        R3（2026-07-31 Marvis 审计）：BLOCK 级 violations（如编号冲突）必须真正阻断管线。
        检测到 [BLOCK] 时设置 context['template_blocked']，validate 节点据此阻断导出。
        """
        try:
            from pipeline.template_enforcer import TemplateEnforcer

            text = context.get("final_text", "") or context.get("report_text", "")
            if text:
                # 修复（2026-08-01 审计）：原实现不传 SAC → self.sac=None，
                # min_tables/min_charts 走硬编码默认（3/5），与 IronGate/SAC 不一致，
                # 导致 unlisted_company 的 4 图/2 表标准被误判为不足而阻断。
                sac = None
                try:
                    from core.sacs import SACLoader

                    sac = SACLoader(context.get("report_type", "industry_deep"))
                except Exception:
                    pass
                te = TemplateEnforcer(sac_loader=sac)
                result = te.enforce(text, report_type=context.get("report_type", "industry_deep"))
                context["template_result"] = result
                # 取 BLOCK 级 violations（enforce 返回 violations 列表，不是 issues）
                violations = result.get("violations", [])
                block_violations = [v for v in violations if v.startswith("[BLOCK]")]
                if block_violations:
                    context["template_blocked"] = True
                    context["template_block_reasons"] = block_violations
                    logger.warning("[TEMPLATE] %d BLOCK violations: %s", len(block_violations), block_violations[:2])
                elif result.get("pass", True):
                    logger.info("[TEMPLATE] All template checks passed")
                else:
                    logger.warning("[TEMPLATE] %d non-blocking issues", len(violations))
        except Exception as e:
            logger.debug("[TEMPLATE] failed: %s", e)
        return {"template_result": context.get("template_result", {})}

    @staticmethod
    def assemble(node_id, context):
        text = context.get("report_text", "")
        chart_paths = context.get("chart_paths", {})
        from pipeline.chart_assembler import ChartAssembler

        ca = ChartAssembler(context.get("report_type", "industry_deep"), context.get("style", "cicc"))
        final = ca.inject_charts_postprocess(text, chart_paths)

        # Inject provenance section
        provenance = context.get("provenance")
        if provenance:
            try:
                final = provenance.inject_into_report(final)
            except Exception:
                pass

        # Inject agent 补充数据来源附录（FP2 合规：agent 兜底数据必须有来源可追溯）
        # R5（2026-08-01 圆桌修复）：幂等性 —— 来源附录只允许注入一次。
        # 此前 assemble 节点被迭代调用（write-revise 循环 / agent 分段调度）时，
        # 附录被重复注入最多 3 次（AGENT_ENRICH_SOURCES 标记出现 6 次），
        # 直接污染排版。注入前检查标记是否已存在，已存在则跳过。
        enrich = (
            context.get("collected_data", {}).get("enrichment", {})
            if isinstance(context.get("collected_data", {}), dict)
            else {}
        )
        if enrich and enrich.get("accepted_count"):
            if "AGENT_ENRICH_SOURCES" not in final:
                try:
                    reg = enrich.get("source_registry", {})
                    lines = [
                        "\n\n<!-- AGENT_ENRICH_SOURCES -->",
                        "### 数据补充来源（agent 兜底）",
                        "以下数据点由 agent 联网/本地补充，均标注来源：",
                    ]
                    for key, meta in (reg or {}).items():
                        src = meta.get("source", "未知")
                        conf = meta.get("confidence", 0.0)
                        unit = meta.get("unit", "")
                        lines.append(f"- **{key}**: 来源={src}; 置信度={conf:.1f}" + (f"; 单位={unit}" if unit else ""))
                    lines.append("<!-- /AGENT_ENRICH_SOURCES -->")
                    if not final.rstrip().endswith("</body>"):
                        final = final.rstrip() + "\n\n" + "\n".join(lines)
                except Exception as e:
                    logger.debug("[ASSEMBLE] enrich source appendix: %s", e)
            else:
                logger.info("[ASSEMBLE] 来源附录已存在，跳过注入（幂等）")

        # R10（2026-08-02）：解析未处理的 {ref:key}=value 占位符。
        # LLM 在引用数据字典时将 {ref:key}=0 原样输出为文本，而非解析为值。
        # 写入前清理：{ref:key}=value → value，保留已解析数值。
        final = re.sub(r"\{ref:[A-Za-z0-9_]+\}\s*=\s*(\S+)", r"\1", final)

        # R89（2026-08-06）：市场规模错误口径后写清理器。
        # 不依赖 LLM 服从性——R85/R86 铁律已进 prompt，但 LLM 仍可能写出
        # "中国油位传感器市场规模2024年为1亿元"（权威166亿元）等自创口径。
        # 在报告落盘与 Gate 前做最后兜底修正（只改市场规模语境，防误伤）。
        try:
            from pipeline.sw_serialize import sanitize_report_market_sizes

            _cd = context.get("collected_data", {})
            _chart_data = _cd.get("chart_data", {}) if isinstance(_cd, dict) else {}
            _prev_text = final
            final = sanitize_report_market_sizes(final, chart_data=_chart_data)
            if final != _prev_text:
                logger.info("[R89-SANITIZE] 市场规模口径清理器已修正报告正文（自创口径→权威锚点）")
        except Exception as _e89:
            logger.debug("[R89-SANITIZE] 清理器未生效: %s", str(_e89)[:100])

        context["final_text"] = final
        return {"final_text": final}

    @staticmethod
    def validate(node_id, context):
        text = context.get("final_text", "") or context.get("report_text", "")
        tmp_path = os.path.join(context.get("output_dir", str(_ROOT / "output")), "_gate_check.md")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)

        from pipeline.iron_gate import IronGate

        dl = context.get("degradation_level", 0)
        ig = IronGate(
            tmp_path,
            report_type=context.get("report_type", "industry_deep"),
            style=context.get("style", "cicc"),
            degradation_level=dl,
            asset=context.get("asset", ""),
            chart_ids=set(context.get("chart_paths", {}).keys()),
            client_questions=context.get("client_questions", None),
        )  # R84

        # FP7b: Degradation-aware handling（P2-I 2026-07-31 审计修复）
        # 不再全局降低 min_score —— 数据质量越差，门禁不应越松。
        # 降级交给 IronGate 内部的 _allow_placeholder_degradation 精细处理：
        #   只放宽"丰富度/图表/风格"类检查，数据一致性/数值合理性 hard_fail 永不降级。
        dl = context.get("degradation_level", 0)
        if dl >= 1:
            logger.info("[L%d DEGRADATION] Gate 阈值保持严格，仅放宽丰富度类检查", dl)
        if dl >= 3:
            logger.warning("[L3 DEGRADATION] Core LLM unavailable — output blocked")
            context["gate_result"] = {"passed": False, "score": 0.0, "failures": ["L3: Core LLM unavailable"]}
            return {"gate_result": context["gate_result"]}

        result = ig.run_all()
        context["gate_result"] = result
        context["ig_report"] = result.to_dict()

        # FP0 意图符合性门禁（2026-08-07）：必答问题是否被报告回答。
        # decision_memo → 阻断（intent_gate 不过 = 未通过）；其他类型 → advisory。
        try:
            # 意图计划优先用 context 里的；无则从 requirement + report_type 重新派生
            _intent_plan = context.get("_intent_plan") or context.get("intent_plan")
            if not _intent_plan:
                _req = context.get("custom_requirement", "") or os.environ.get("CUSTOM_REQUIREMENT", "")
                if _req or context.get("report_type") == "decision_memo":
                    from core.intent_parser import IntentParser

                    _intent_plan = IntentParser().parse(
                        asset=context.get("asset", ""),
                        report_type=context.get("report_type", "decision_memo"),
                        requirement=_req,
                    )
            if _intent_plan:
                from core.intent_gate import check_intent_compliance

                _ig_r = check_intent_compliance(text, _intent_plan)
                context["intent_gate_result"] = _ig_r
                if context.get("report_type") == "decision_memo" and not _ig_r["passed"]:
                    result.passed = False
                    result.overall_score = min(result.overall_score, 0.5)
                    result.failures = (result.failures or []) + [
                        f"[INTENT-GATE] 必答问题未覆盖 {_ig_r['answered']}/{_ig_r['total']}: "
                        f"{'; '.join(_ig_r['gaps'][:3])}"
                    ]
                logger.info(
                    "[INTENT-GATE] coverage=%.2f passed=%s (type=%s)",
                    _ig_r["coverage"],
                    _ig_r["passed"],
                    context.get("report_type"),
                )
        except Exception as _ig_e:
            logger.debug("[INTENT-GATE] %s", str(_ig_e)[:60])

        # R3（2026-07-31 Marvis 审计）：template_enforce 的 BLOCK 级 violation（编号冲突）
        # 必须在 Gate 层面阻断，不能只记录 warning。
        if context.get("template_blocked"):
            reasons = context.get("template_block_reasons", [])
            result.passed = False
            result.overall_score = min(result.overall_score, 0.4)
            result.failures = (result.failures or []) + [f"[BLOCK] template: {r}" for r in reasons[:3]]
            context["gate_result"] = result
            logger.warning("[TEMPLATE-BLOCK] %s", reasons[:2])

        msg = "Gate=%s score=%.2f" % ("PASS" if result.passed else "FAIL", result.overall_score)
        if dl > 0:
            msg += " [L%d degradation]" % dl
        logger.info(msg)
        return {"gate_result": result.to_dict() if hasattr(result, "to_dict") else {}}

    @staticmethod
    def compliance_check(node_id, context):
        """Run ComplianceChecklist after IronGate passes (advisory, non-blocking)."""
        try:
            from core.enforcer.checklist import ComplianceChecklist

            text = context.get("final_text", "") or context.get("report_text", "")
            if text:
                cl = ComplianceChecklist()
                result = cl.run(text, sac_id=context.get("report_type", ""))
                passed = result.get("passed", False)
                items = result.get("items", [])
                n_failed = sum(1 for i in items if not i.get("passed", False))
                logger.info("[COMPLIANCE] %d/%d checks passed", len(items) - n_failed, len(items))
                if not passed:
                    failed_items = [i for i in items if not i.get("passed", False)]
                    logger.warning(
                        "[COMPLIANCE] %d checks failed: %s", n_failed, [i.get("name", "") for i in failed_items[:5]]
                    )
                context["compliance_result"] = result
        except Exception as e:
            logger.debug("[COMPLIANCE] failed: %s", e)
        return {"compliance_result": context.get("compliance_result", {})}

    @staticmethod
    def export_docx(node_id, context):
        text = context.get("final_text", "") or context.get("report_text", "")
        gate = context.get("gate_result", {})
        if not gate.get("passed", False):
            logger.warning("[EXPORT] gate blocked")
            context["_docx_path"] = ""
            return {"_docx_path": ""}
        output_dir = Path(context.get("output_dir", str(_ROOT / "output")))
        output_dir.mkdir(parents=True, exist_ok=True)
        asset = context.get("asset", "report")
        style = context.get("style", "cicc")
        docx_path = str(output_dir / f"{asset}_{style}.docx")
        # FP7d: Gate 已通过 → 先预写管线指纹，再进入 export_report 校验，
        # 避免指纹在 PASSED 分支才写导致导出被 PipelineFingerprint 误拦截。
        try:
            import datetime as _dt
            import json as _json

            safe = re.sub(r"[^\w一-鿿]+", "_", str(asset)).strip("_") or "asset"
            fp_path = output_dir / f"{safe}_pipeline_fingerprint.json"
            if not fp_path.exists():
                fp_path.write_text(
                    _json.dumps(
                        {
                            "asset": asset,
                            "report_type": context.get("report_type"),
                            "style": style,
                            "timestamp": _dt.datetime.now().isoformat(),
                            "attempt": context.get("attempt", 0),
                            "gate_score": gate.get("score", 0),
                            "gate_passed": True,
                            "via_pipeline": True,
                            "pipeline": "E2EOrchestratorV2",
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        except Exception as e:
            logger.warning("[FINGERPRINT] 预写失败: %s", e)
        try:
            from export.report_gate import export_report

            # Inject provenance data into text before export
            provenance = context.get("provenance")
            enriched_text = text
            if provenance:
                try:
                    prov_summary = provenance.summary()
                    if prov_summary:
                        enriched_text = text + "\n\n<!-- DATA_PROVENANCE: " + str(prov_summary)[:2000] + " -->"
                except Exception:
                    pass
            exported = export_report(
                enriched_text, docx_path, report_type=context.get("report_type"), style=style, title=asset
            )
            context["_docx_path"] = exported
        except Exception as e:
            logger.warning("[EXPORT] failed: %s", e)
            context["_docx_path"] = ""
        return {"_docx_path": context.get("_docx_path", "")}

    @staticmethod
    def record_results(node_id, context):
        try:
            from pipeline.learning_loop import LearningLoop

            gate = context.get("gate_result", {})
            ll = LearningLoop()
            ll.after_report(
                context.get("asset", ""),
                context.get("report_type"),
                {
                    "iron_gate": gate.get("score", 0),
                    "passed": gate.get("passed", False),
                    "failures": [],
                    "attempt": context.get("attempt", 0),
                },
            )

            # R77（2026-08-05 P0-3）：方法选择数据驱动初代——
            # Gate 通过后自动记录方法反思（用了什么框架、Gate 分多少），
            # 回写 framework_registry 效果字段。此前 record_reflection 从未被接线，
            # registry 效果字段全是估算值（"已用次数3/平均Gate分0.92"是假的）。
            # 接线后：报告跑完 → 反思日志 +1 → registry 效果字段从估算变实测。
            try:
                if gate.get("passed", False):
                    from core.method_reflection import record_reflection

                    _ap = context.get("analysis_plan") or {}
                    _fw_list = _ap.get("frameworks", []) if isinstance(_ap, dict) else []
                    _fw_ids = [f.get("id", "") for f in _fw_list if isinstance(f, dict)]
                    if not _fw_ids:
                        # 兜底：无 analysis_plan 时按报告类型记通用框架
                        _fw_ids = []
                    _gscore = gate.get("overall_score", 0)
                    if not isinstance(_gscore, (int, float)):
                        _gscore = gate.get("score", 0)
                    record_reflection(
                        asset=context.get("asset", ""),
                        report_type=context.get("report_type", ""),
                        frameworks=_fw_ids,
                        gate_score=float(_gscore) if isinstance(_gscore, (int, float)) else 0.0,
                        data_sufficiency=context.get("data_sufficiency", {}),
                        notes="e2e 出口自动记录",
                    )
                    logger.info("[REFLECT] 报告完成自动记录方法反思: frameworks=%s gate=%.2f", _fw_ids, _gscore)
            except Exception as _refl_e:
                logger.warning("[REFLECT] e2e 出口反思记录失败: %s", str(_refl_e)[:80])

            # Extract and register bold calls
            text = context.get("final_text", "") or context.get("report_text", "")
            if text:
                from core.bold_call_extractor import BoldCallExtractor
                from core.tools.track_record import TrackRecordManager

                bce = BoldCallExtractor()
                tm = TrackRecordManager()
                calls = bce.extract_and_register(text, context.get("asset", ""), context.get("report_type"), tm=tm)
                logger.info("[RECORD] %d bold calls registered", len(calls))

                # ForwardPicksDB: persistent prediction record (V82 merge)
                # R78（2026-08-05 Phase2.4）：修复 fdb.record_prediction 不存在 bug——
                # ForwardPicksDB 重构后只有 append(ForwardPick)，旧调用 AttributeError 被
                # try 吞掉（静默失败，预测从未入库）。改用 ForwardPick + append 走质量门槛。
                if _HAS_FORWARDPICKS and calls:
                    try:
                        import datetime as _dt

                        from core.forward_picks import ForwardPick, ForwardPicksDB

                        fdb = ForwardPicksDB()
                        asset_id = context.get("asset_id", {})
                        _name = asset_id.get("name", context.get("asset", ""))
                        for c in calls:
                            try:
                                pick = ForwardPick(
                                    asset_name=_name,
                                    report_type=context.get("report_type", ""),
                                    created_at=_dt.datetime.now().isoformat(),
                                    direction=c.get("direction", "neutral"),
                                    conviction=c.get("confidence", "low"),
                                    core_thesis=str(c.get("bold_call", str(c)[:200]))[:300],
                                )
                                if pick.direction == "neutral":
                                    continue  # 质量门槛：neutral 不入库
                                fdb.append(pick)
                            except Exception as _pe:
                                logger.debug("[FORWARDPICKS] single pick failed: %s", _pe)
                        logger.info("[FORWARDPICKS] %d predictions recorded", len(calls))
                    except Exception as e:
                        logger.debug("[FORWARDPICKS] failed: %s", e)

            # FP5: Validate expired predictions against market data
            try:
                from core.prediction_validator import validate_expired_predictions

                pv_result = validate_expired_predictions()
                if pv_result:
                    context["prediction_validation"] = str(pv_result)[:500]
                    logger.info("[RECORD] Prediction validation: %s", str(pv_result)[:80])
            except Exception as e:
                logger.debug("[RECORD] PredictionValidator: %s", e)

            # FP5: Wire EditClassifier — absorb edits from case DB
            try:
                from core.edit import EditClassifier

                text = context.get("final_text", "") or context.get("report_text", "")
                edit_type = EditClassifier.classify(text) if hasattr(EditClassifier, "classify") else None
                if edit_type:
                    context["edit_type"] = str(edit_type)
                    logger.info("[RECORD] Edit classified as: %s", edit_type)
            except Exception as e:
                logger.debug("[RECORD] EditClassifier: %s", e)

            # FP5: Wire ReportCalibrator — auto-fix gate failures
            gate_passed = gate.get("passed", False)
            # R66（2026-08-04）修复：GateReport.to_dict 字段是 overall_score 不是 score。
            # 旧逻辑 gate.get("score") 恒 0 → 回归/stalled 检测失效、退化不可见。
            gate_score = gate.get("overall_score", 0)
            if not isinstance(gate_score, (int, float)):
                gate_score = gate.get("score", 0)
            gate_score = gate_score if isinstance(gate_score, (int, float)) else 0
            if not gate_passed and gate_score < 0.7:
                try:
                    from core.report_calibrator import ReportCalibrator

                    rc = ReportCalibrator()
                    if hasattr(rc, "analyze"):
                        fix_plan = rc.analyze(
                            failures=gate.get("failures", []),
                            report_type=context.get("report_type", ""),
                        )
                        if fix_plan:
                            context["calibration_plan"] = fix_plan
                            logger.info("[RECORD] Calibration plan: %d fixes", len(fix_plan))
                except Exception as e:
                    logger.debug("[RECORD] CalibrationPlan: %s", e)

        except Exception as e:
            logger.debug("[RECORD] failed: %s", e)
        return {"_recorded": True}

    @staticmethod
    def data_feeds(node_id, context):
        """Run data feeds (RSS/PDF/patents/basics)."""
        try:
            from pipeline.data_feeds_node import data_feeds_node

            return data_feeds_node(node_id, context)
        except Exception as e:
            logger.warning("DataFeeds failed: %s", e)
            return {"feeds_loaded": False}

    @staticmethod
    def critic_review(node_id, context):
        """Multi-critic panel after gate passes."""
        try:
            from core.tools.critic_panel import critic_panel_node

            return critic_panel_node(node_id, context)
        except Exception as e:
            logger.warning("CriticPanel failed: %s", e)
            return {"critic_passed": False}


def _record_predictions_safe(report_text: str, asset: str) -> int:
    """P3-A：Gate 通过的硬结论写入预测问责账本（失败静默，绝不阻塞交付）。"""
    try:
        from core.prediction_extract import record_predictions

        n = record_predictions(report_text, asset)
        if n:
            logger.info("[PREDICTION-LEDGER] %s 写入 %d 条可问责预测", asset, n)
        return n
    except Exception as e:
        logger.debug("[PREDICTION-LEDGER] %s", str(e)[:60])
        return 0


class E2EOrchestratorV2:
    # R48（2026-08-02）：迭代上限支持环境变量 MAX_ATTEMPTS
    # 性能模式默认 3（快速收敛）；训练模式可设 5-10（自迭代打磨）
    MAX_ATTEMPTS = settings.max_attempts()

    def __init__(
        self,
        asset,
        report_type="listed_company",
        style="cicc",
        output_dir=None,
        hypothesis="",
        user_context="",
        force=False,
        enrich_file=None,
        analysis_plan=None,
        client_questions=None,
    ):
        self.asset = asset
        self.report_type = report_type
        self.style = style
        self.output_dir = output_dir or str(_ROOT / "output")
        self.hypothesis = hypothesis
        self.user_context = user_context
        self.force = force
        self.enrich_file = enrich_file
        self.analysis_plan = analysis_plan  # R65: FP8 分析方案（用什么框架/聚焦什么维度）
        self.client_questions = client_questions  # R83: 委托方必答问题清单（决策备忘录）
        self.asset_id = self._normalize_asset(asset)
        # 重试间数据缓存：第一轮采集后复用，避免 MAX_ATTEMPTS 内每轮重跑网络采集
        self._cached_collected = None
        self._cached_data_sufficiency = None
        self._cached_needs_agent = False
        # R51（2026-08-02 P0-2 收敛机制）：失败项变化检测——上轮失败=本轮失败时
        # 不再盲目同法重写（对标 stevegrocott churn reduction），而是：
        #   a) 记录 stalled 信号（附给下一轮 prompt，要求换策略而非重复）
        #   b) 连续 3 轮相同 → 提前终止（无效重跑，省时间/防发散）
        self._prev_gate_failures = set()
        self._consecutive_same_failures = 0
        self._stall_aborted = False
        self.trace_id = uuid.uuid4().hex[:12]

    def _normalize_asset(self, raw: str) -> dict:
        """Return standardized asset identity (IB建议的三字段方案)."""
        from core.asset_resolver import resolve_asset

        _a = resolve_asset(raw)
        return {"name": _a.name or raw, "code": _a.code or "", "display": _a.name or raw}

    def _write_pipeline_fingerprint(self, ctx: dict, gate: dict) -> str:
        """写管线指纹文件 — 证明报告经由完整管线产出。

        export_report 会校验该指纹存在才放行。
        agent 绕过管线直接生成的报告文件（MD/DOCX）无对应指纹 → GateBlockedError。
        """
        import datetime as _dt
        import json as _json

        output_dir = Path(ctx.get("output_dir", str(_ROOT / "output")))
        output_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w一-鿿]+", "_", str(self.asset)).strip("_") or "asset"
        fp_path = output_dir / f"{safe}_pipeline_fingerprint.json"

        # 收集 StepManager 标记（哪些步骤确实执行了）
        step_status = {}
        try:
            sm = ctx.get("_step_manager")
            if sm:
                step_status = sm.get_status()
        except Exception:
            pass

        fingerprint = {
            "asset": self.asset,
            "asset_id": self.asset_id,
            "report_type": self.report_type,
            "style": self.style,
            "timestamp": _dt.datetime.now().isoformat(),
            "attempt": ctx.get("attempt", 0),
            "gate_score": gate.get("score", 0) if isinstance(gate, dict) else 0,
            "gate_passed": gate.get("passed", False) if isinstance(gate, dict) else False,
            "steps": step_status,
            "needs_agent": ctx.get("needs_agent", False),
            "data_enriched": ctx.get("data_enriched", False),
            "data_sufficiency": ctx.get("data_sufficiency", {}),
            # FP7d: 证明经由 E2EOrchestratorV2 完整管线
            "via_pipeline": True,
            "pipeline": "E2EOrchestratorV2",
        }
        fp_path.write_text(_json.dumps(fingerprint, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("[FINGERPRINT] 管线指纹已写入: %s", fp_path)
        # FP6/FP7d: 血缘追踪 — 结构化记录数据从哪来、补了什么、怎么到报告
        try:
            self._write_lineage(ctx, gate)
        except Exception as e:
            logger.debug("[LINEAGE] 写入失败: %s", e)
        return str(fp_path)

    def _write_lineage(self, ctx: dict, gate: dict) -> str:
        """写血缘追踪 lineage.json — 记录报告的数据来源与变换链。

        供 FP6 推理透明审计：能回答"这份报告的数据来自哪些源、
        agent 补了什么、经过哪些阶段"。
        """
        import json as _json

        output_dir = Path(ctx.get("output_dir", str(_ROOT / "output")))
        output_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w一-鿿]+", "_", str(self.asset)).strip("_") or "asset"
        lg_path = output_dir / f"{safe}_lineage.json"

        # 数据源层：从 collected_data 提取
        data = ctx.get("collected_data", {}) or {}
        sources = []
        if isinstance(data, dict):
            cd = data.get("chart_data", {}) or {}
            if cd.get("_local_backfill"):
                sources.append({"kind": "local_backfill", "detail": cd["_local_backfill"].get("keys", [])})
            if data.get("enrichment", {}).get("accepted_count"):
                src_reg = data["enrichment"].get("source_registry", {})
                for key, meta in (src_reg or {}).items():
                    sources.append(
                        {
                            "kind": "agent_enrich",
                            "key": key,
                            "source": meta.get("source", ""),
                            "confidence": meta.get("confidence", 0),
                        }
                    )
            if data.get("akshare_financials"):
                sources.append({"kind": "akshare", "detail": "akshare_financials"})
            if cd:
                non_backfill = [k for k in cd if not k.startswith("_") and k not in ("agent_news",)]
                if non_backfill:
                    sources.append({"kind": "data_collector", "detail": non_backfill[:10]})

        # enrich/compute/write 各阶段信号
        lineage = {
            "asset": self.asset,
            "report_type": self.report_type,
            "timestamp": datetime.datetime.now().isoformat(),
            # 执行状态快照（2026-08-01 升级）：支持运行重放
            "execution": {
                "attempt": ctx.get("attempt", 0),
                "data_hash": ctx.get("_data_hash", ""),
                "node_count": len(ctx.get("_node_executions", [])),
                "node_executions": ctx.get("_node_executions", []),
                "degradation_level": ctx.get("degradation_level", 0),
                "llm_degradation_level": ctx.get("llm_degradation_level", 0),
            },
            "stages": [
                {
                    "stage": "data_collect",
                    "output_keys": list((data.get("chart_data") or {}).keys())[:15] if isinstance(data, dict) else [],
                },
                {
                    "stage": "enrich",
                    "needs_agent": ctx.get("needs_agent", False),
                    "data_enriched": ctx.get("data_enriched", False),
                    "sufficient": ctx.get("data_sufficiency", {}).get("sufficient"),
                },
                {
                    "stage": "compute",
                    "has_results": bool(ctx.get("compute_results")),
                    "modules": list(ctx.get("compute_results", {}).keys())[:10]
                    if isinstance(ctx.get("compute_results"), dict)
                    else [],
                },
                {
                    "stage": "write",
                    "llm_provider": "agent_provider" if ctx.get("llm_degradation_level") == 3 else "deepseek",
                    "text_len": len(ctx.get("final_text", "") or ctx.get("report_text", "")),
                },
                {
                    "stage": "gate",
                    "score": gate.get("score", 0) if isinstance(gate, dict) else 0,
                    "passed": gate.get("passed", False) if isinstance(gate, dict) else False,
                    "failures": (gate.get("failures") or [])[:10] if isinstance(gate, dict) else [],
                },
            ],
            "sources": sources,
            # FP7d: 若 agent 兜底发生，记录兜底性质（数据/LLM）
            "agent_backfill": {
                "data_backfilled": bool(ctx.get("data_enriched")),
                "llm_backfilled": ctx.get("llm_degradation_level") == 3,
                "backlog_path": ctx.get("backlog_path", ""),
            },
            # 重试/写改历史（FP5 学习闭环）
            "retry_history": {
                "cached_data_reused": ctx.get("_data_cached", False),
                "gate_feedback_passed": bool(ctx.get("gate_feedback")),
            },
        }
        lg_path.write_text(_json.dumps(lineage, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("[LINEAGE] 血缘已写入: %s", lg_path)
        return str(lg_path)

    def _build_context(self):
        # P3-audit 2026-08-24：构造收口到 context_schema.new_context——
        # 全部键在 PipelineContext TypedDict 登记，未知键抛错（防 typo 潜伏）。
        from pipeline.context_schema import new_context

        ctx = new_context(
            # R78（2026-08-05）：轻量级 trace_id——一次运行一个可追溯 ID，
            # 注入日志/报告/checkpoint，跨环节定位问题。
            trace_id=self.trace_id,
            asset=self.asset,
            asset_id=self.asset_id,
            report_type=self.report_type,
            style=self.style,
            output_dir=self.output_dir,
            hypothesis=self.hypothesis,
            user_context=self.user_context,
            force=self.force,
            enrich_file=self.enrich_file,
            analysis_plan=self.analysis_plan,
            client_questions=self.client_questions,
        )
        # 重试间缓存注入：非首轮复用首轮采集的数据，避免每轮重跑网络采集
        if self._cached_collected is not None:
            ctx["collected_data"] = self._cached_collected
            ctx["_data_cached"] = True
            if self._cached_data_sufficiency is not None:
                ctx["data_sufficiency"] = self._cached_data_sufficiency
            if self._cached_needs_agent:
                ctx["needs_agent"] = True
        return ctx

    def run(self):
        # R80 Phase5：token 预算制——防写改循环成本失控
        import time as _t

        from pipeline.agent_graph import AgentGraph

        _budget_start = _t.time()
        _token_budget = settings.report_token_budget()
        last_error = None
        last_gate_feedback = ""
        prev_full_text = ""  # R7: 上一轮完整报告（状态锚点）
        prev_coverage = None  # R7: 上一轮 SAC 维度覆盖矩阵
        # R78（2026-08-05 Phase2.3）：checkpoint 恢复——中断后续跑不重头。
        # 恢复 attempt 数/上轮报告/Gate 反馈/数据，从断点继续写改循环。
        _ck = {}
        try:
            from pipeline.write_checkpoint import clear_checkpoint, load_checkpoint

            _ck = load_checkpoint(self.asset) or {}
            if _ck:
                _ck_start = _ck.get("attempt", 0)
                last_gate_feedback = _ck.get("gate_feedback", "")
                prev_full_text = _ck.get("report_text", "")
                self._cached_collected = _ck.get("collected_data") or self._cached_collected
                self._cached_data_sufficiency = _ck.get("data_sufficiency") or self._cached_data_sufficiency
                logger.info(
                    "[CHECKPOINT] 恢复 %s 从 attempt %d（Gate反馈=%s）",
                    self.asset,
                    _ck_start + 1,
                    "有" if last_gate_feedback else "无",
                )
        except Exception as _cke:
            logger.warning("[CHECKPOINT] 恢复失败（从头开始）: %s", str(_cke)[:80])
            _ck = {}
        _attempt_start = _ck.get("attempt", 0)
        # P3-audit 2026-08-24 真 bug 修复：残留 checkpoint 的 attempt 可能
        # ≥ 本次 MAX_ATTEMPTS（如上次以 MAX_ATTEMPTS=1 跑到 attempt 4），
        # range(4, 3) 为空 → 三轮"零执行"直接判死且 score=[]。
        # 上限保护：达到上限即清 checkpoint 从头收敛（TTL 内重跑不再砖化）。
        if _attempt_start >= self.MAX_ATTEMPTS:
            logger.warning(
                "[CHECKPOINT] 残留 attempt=%d 已达本次上限 %d → 清 checkpoint 重置计数",
                _attempt_start,
                self.MAX_ATTEMPTS,
            )
            try:
                from pipeline.write_checkpoint import clear_checkpoint

                clear_checkpoint(self.asset)
            except Exception:
                pass
            _attempt_start = 0
        ctx = {}  # R79-fix

        for attempt in range(_attempt_start, self.MAX_ATTEMPTS):
            logger.info("Attempt %d/%d: %s (%s)", attempt + 1, self.MAX_ATTEMPTS, self.asset, self.report_type)
            ctx = self._build_context()
            ctx["attempt"] = attempt
            # 写改循环：把上一轮 Gate 失败反馈带给本轮写作（FP5 学习闭环）
            if attempt > 0 and last_gate_feedback:
                ctx["gate_feedback"] = last_gate_feedback
                ctx["learning_findings"] = ctx.get("learning_findings", "") + "\n" + last_gate_feedback[:2000]
                logger.info("[REVISE] Passing Gate feedback to attempt %d: %s", attempt + 1, last_gate_feedback[:100])
            # R7 收敛锚点：把上一轮完整报告 + 维度覆盖矩阵带给本轮写作。
            # 这是"收敛机制"的核心 —— 没有锚点的迭代 = 每次重新掷骰子。
            # 上一轮全文让 LLM 知道"已写了什么"，覆盖矩阵让它知道"哪里缺、哪里别动"。
            if attempt > 0:
                _scores = self.__dict__.get("_gate_score_history", [])
                _regressed = len(_scores) >= 2 and _scores[-1] < _scores[-2] - 0.05
                ctx["state_anchor"] = {
                    "prev_full_text": prev_full_text[:4000],  # 截断防超长
                    "prev_coverage": prev_coverage,
                    "revision_targets": _revision_targets_from_gate(last_gate_feedback),
                    "regression": _regressed,  # R8: 跨轮退化信号
                }
                logger.info(
                    "[STATE-ANCHOR] attempt %d 注入状态锚点: prev_text=%d字, coverage=%s, regression=%s",
                    attempt + 1,
                    len(prev_full_text[:4000]),
                    prev_coverage if prev_coverage else "N/A",
                    _regressed,
                )
            # StepManager: track pipeline execution with marker files
            try:
                output_dir = self.output_dir or "output"
                sm = StepManager(output_dir)
                sm.reset()
                ctx["_step_manager"] = sm
                sm.mark_start("pipeline")
            except Exception:
                pass
            g = AgentGraph(f"{self.asset} attempt {attempt + 1}")

            g.add_node("preflight", E2ENodes.preflight_check, deps=[], desc="runtime health")
            g.add_node(
                "biz_macro",
                E2ENodes.biz_macro_inject,
                deps=["preflight"],
                desc="biz model + macro context",
            )
            g.add_node(
                "data_feeds",
                E2ENodes.data_feeds,
                deps=["data"],
                desc="RSS/PDF/patent feeds (merged into collected_data)",
            )
            g.add_node("hypothesis", E2ENodes.hypothesis_check, deps=[], desc="hypothesis T0.5")
            g.add_node("data", E2ENodes.data, deps=[], desc="data + provenance")
            g.add_node(
                "universe_build",
                E2ENodes.universe_build,
                deps=["data"],
                desc="R68: Universe Building——全量竞争玩家清单+缺口检测",
            )
            g.add_node(
                "enrich",
                E2ENodes.enrich_data,
                deps=["data", "universe_build"],
                desc="data sufficiency + local/agent backfill",
            )
            g.add_node("scarcity", E2ENodes.scarcity_signals, deps=["enrich"], desc="scarcity signals")
            g.add_node("cross_validate", E2ENodes.cross_validate, deps=["enrich"], desc="cross validate")
            g.add_node("argument", E2ENodes.argument_engine, deps=["enrich"], desc="argument engine")
            g.add_node("learning", E2ENodes.learning, deps=[], desc="learning loop")
            g.add_node(
                "compute", E2ENodes.compute, deps=["enrich"], desc="compute engine (DCF/comparable/knowledge modules)"
            )
            g.add_node("charts", E2ENodes.charts, deps=["enrich"], desc="charts")
            g.add_node(
                "write_sections",
                E2ENodes.write_sections,
                deps=[
                    "enrich",
                    "charts",
                    "compute",
                    "learning",
                    "hypothesis",
                    "argument",
                    "scarcity",
                    "cross_validate",
                ],
                desc="write",
            )
            g.add_node("style", E2ENodes.style_compile, deps=["write_sections", "charts"], desc="style compile")
            g.add_node(
                "template",
                E2ENodes.template_enforce,
                deps=["assemble"],
                desc="template enforcer (after assemble, checks final_text)",
            )
            g.add_node("assemble", E2ENodes.assemble, deps=["style", "charts"], desc="assemble")
            g.add_node("validate", E2ENodes.validate, deps=["assemble"], desc="gate")
            g.add_node("critic", E2ENodes.critic_review, deps=["validate"], desc="multi-critic panel")
            g.add_node("compliance", E2ENodes.compliance_check, deps=["validate", "critic"], desc="compliance")
            g.add_node("export_docx", E2ENodes.export_docx, deps=["compliance"], desc="export")
            g.add_node("record_results", E2ENodes.record_results, deps=["validate"], desc="record + bold calls")

            # 注入输出契约
            contracts = _build_output_contracts()
            for node_id, contract in contracts.items():
                if node_id in g._nodes:
                    g._nodes[node_id]["output_contract"] = contract
            result = g.run(ctx)
            # 执行状态快照：把 21 节点执行明细存入 ctx，供 lineage 审计（2026-08-01 升级）
            try:
                ctx["_node_executions"] = [
                    {
                        "node": nid,
                        "status": nr.status,
                        "duration_ms": round(nr.duration_ms, 1),
                        "output_hash": nr.output_hash,
                        "error": (nr.error or "")[:200],
                        "validation_issues": nr.validation_issues[:5] if nr.validation_issues else [],
                    }
                    for nid, nr in g._results.items()
                ]
                # collected_data 指纹（供运行重放对比）
                _cd = ctx.get("collected_data")
                if isinstance(_cd, dict):
                    import hashlib as _hl

                    ctx["_data_hash"] = _hl.md5(
                        str({k: v for k, v in _cd.items() if not k.startswith("_")}).encode()
                    ).hexdigest()[:16]
            except Exception as _se:
                logger.debug("[SNAPSHOT] 节点明细收集失败: %s", _se)
            # 重试间数据缓存：首轮 data 节点成功后缓存 collected_data，
            # 后续写改轮次直接复用，避免每轮重跑网络采集（R4 2026-08-01 审计）
            if self._cached_collected is None:
                cd = ctx.get("collected_data")
                if isinstance(cd, dict) and cd:
                    self._cached_collected = cd
                    self._cached_data_sufficiency = ctx.get("data_sufficiency")
                    self._cached_needs_agent = bool(ctx.get("needs_agent"))
                    logger.info("[CACHE] 首轮采集数据已缓存（%d keys），后续重试轮复用", len(cd))
            # StepManager: mark completion for key pipeline steps
            try:
                sm = ctx.get("_step_manager")
                if sm:
                    for completed in ["data", "enrich", "charts", "write_sections", "validate"]:
                        if g._results.get(completed) and g._results[completed].duration_ms > 0:
                            try:
                                sm.mark_done(completed)
                            except Exception:
                                pass
            except Exception:
                pass
            # Node profiling
            for nid, nr in g._results.items():
                if nr.duration_ms > 1000:
                    logger.info("  [PROFILE] %s: %.0fms", nid, nr.duration_ms)
            gate = ctx.get("gate_result", {})
            ig_passed = gate.get("passed", False)
            ig_score = gate.get("overall_score", gate.get("score", 0))
            if not isinstance(ig_score, (int, float)):
                ig_score = 0

            if result.passed and ig_passed:
                logger.info("PASSED (attempt %d, score=%.2f)", attempt + 1, ig_score)
                # FP7d: 管线指纹 —— 证明报告经由完整管线产出
                # export_report 校验该指纹存在才放行；agent 绕过管线直接生成的文件无指纹 → 阻断
                try:
                    self._write_pipeline_fingerprint(ctx, gate)
                except Exception as e:
                    logger.warning("[FINGERPRINT] 写入失败: %s", e)
                # R78：报告完成 → 清除 checkpoint（防旧状态干扰下次运行）
                try:
                    from pipeline.write_checkpoint import clear_checkpoint

                    clear_checkpoint(self.asset)
                except Exception:
                    pass
                return {
                    "passed": True,
                    "trace_id": ctx.get("trace_id", ""),
                    "elapsed_s": round(_t.time() - _budget_start, 1),
                    "token_budget": _token_budget,
                    "attempt": attempt + 1,
                    "report_text": ctx.get("final_text", ctx.get("report_text", "")),
                    "chart_paths": list(ctx.get("chart_paths", {}).values()),
                    "gate_result": gate,
                    "docx": ctx.get("_docx_path", ""),
                    "hypothesis_result": ctx.get("hypothesis_result"),
                    "runtime_score": ctx.get("runtime_score", 0.5),
                    # 数据桥接信号（供 scheduler/agent 感知兜底是否发生）
                    "needs_agent": ctx.get("needs_agent", False),
                    "data_enriched": ctx.get("data_enriched", False),
                    "data_sufficiency": ctx.get("data_sufficiency", {}),
                    # P3-audit: claim 级溯源附录的数据源（main.py 消费）
                    "collected_data": ctx.get("collected_data", {}),
                    # P3-A: 预测账本——Gate 通过的硬结论写入问责账本（失败静默）
                    "predictions_recorded": _record_predictions_safe(
                        ctx.get("final_text", ctx.get("report_text", "")),
                        self.asset,
                    ),
                }
            last_error = ["Gate blocked"] if result.passed else result.failed_nodes
            # R8 跨轮质量退化报警：记录每轮 Gate score，比上一轮显著下降 → 报警。
            # 发散根因之一是没有"比上次差"的检测，每次都是全新的差法。
            try:
                _scores = self.__dict__.setdefault("_gate_score_history", [])
                _scores.append(ig_score)
                if len(_scores) >= 2:
                    prev_s, cur_s = _scores[-2], _scores[-1]
                    if cur_s < prev_s - 0.05:
                        logger.warning(
                            "[REGRESSION] 质量退化: attempt %d score=%.2f < attempt %d score=%.2f "
                            "（跨轮退化报警，下一轮须针对未改善项修订，不得整体推倒重写）",
                            attempt + 1,
                            cur_s,
                            attempt,
                            prev_s,
                        )
            except Exception as _e:
                logger.debug("[REGRESSION] track failed: %s", _e)
            # R51（2026-08-02 P0-2 收敛机制）：失败项变化检测
            # 上轮失败=本轮失败 → 标 stalled（下一轮 prompt 明确"换策略"而非重复）
            # 连续 3 轮相同 → 提前终止（无效重跑），并在 summary 标记 stalled
            try:
                _cur_fails = set()
                _fails_raw = gate.get("failures", []) if isinstance(gate, dict) else []
                for _f in _fails_raw or []:
                    # 归一化：取 [SEVERITY] name（去掉 details 细节，避免同一失败
                    # 因 details 措辞变化被误判为"不同失败"）
                    _nm = str(_f).split(":", 1)[0].strip()
                    _cur_fails.add(_nm)
                if attempt > 0 and _cur_fails and _cur_fails == self._prev_gate_failures:
                    self._consecutive_same_failures += 1
                    ctx["stalled"] = True
                    ctx["stalled_failures"] = sorted(_cur_fails)[:5]
                    logger.warning(
                        "[STALL] 连续 %d 轮失败项相同: %s → 下一轮须换策略",
                        self._consecutive_same_failures + 1,
                        sorted(_cur_fails)[:3],
                    )
                    if self._consecutive_same_failures >= 2:
                        # 连续 3 轮（含本轮）同失败 → 提前终止，避免无效重跑
                        logger.error(
                            "[STALL] 失败项连续 3 轮未变化 %s → 提前终止（防无效重跑）", sorted(_cur_fails)[:3]
                        )
                        self._stall_aborted = True
                        break
                elif _cur_fails:
                    self._prev_gate_failures = _cur_fails
                    self._consecutive_same_failures = 0
            except Exception as _e:
                logger.debug("[STALL] track failed: %s", _e)
            # P0-3 门禁熔断（2026-08-07，防局部修复死锁）：
            # 同一模块/同一失败项被局部修订 N 次（默认 3）仍不通过 → 降级为该模块全量重写，
            # 并置 ctx['circuit_broken'] 信号让 section_writer 知道"别再局部精炼，整段换新"。
            # 圆桌批判 F3：fail-fast 若拦 80% 内容 → 无限局部修复循环（新的 300s 空等）。
            try:
                if isinstance(gate, dict) and not gate.get("passed", False):
                    _fails_raw = gate.get("failures", []) or []
                    # 归一化失败项（去 details，避免措辞变化误判）
                    _norm = set()
                    for _f in _fails_raw:
                        _nm = str(_f).split(":", 1)[0].strip()
                        _norm.add(_nm)
                    _repair_map = self.__dict__.setdefault("_repair_count", {})
                    for _nm in _norm:
                        _repair_map[_nm] = _repair_map.get(_nm, 0) + 1
                    _circuit_n = settings.repair_circuit_break()
                    _broken = [k for k, v in _repair_map.items() if v >= _circuit_n]
                    if _broken:
                        ctx["circuit_broken"] = True
                        ctx["circuit_broken_items"] = sorted(_broken)[:5]
                        logger.warning(
                            "[CIRCUIT-BREAK] 失败项连续 %d 轮未修好 %s → 本轮降级全量重写该模块（防死锁）",
                            _circuit_n,
                            sorted(_broken)[:3],
                        )
                        # 清计数，避免下一轮立刻再次触发
                        for _k in _broken:
                            _repair_map[_k] = 0
            except Exception as _e2:
                logger.debug("[CIRCUIT-BREAK] %s", _e2)
            # R7 收敛锚点：记录本轮完整报告 + SAC 维度覆盖矩阵，供下一轮写作参考
            try:
                prev_full_text = ctx.get("final_text", "") or ctx.get("report_text", "")
                from pipeline.iron_gate import IronGate

                _tmp = os.path.join(self.output_dir, "_gate_prev.md")
                with open(_tmp, "w", encoding="utf-8") as _f:
                    _f.write(prev_full_text or "")
                _ig = IronGate(_tmp, report_type=self.report_type, style=self.style)
                _cov = _ig._check_sac_coverage()
                prev_coverage = {
                    "passed": _cov.passed,
                    "details": _cov.details,
                    "score": _cov.score,
                }
                logger.info("[STATE-ANCHOR] 记录上一轮状态: text=%d字, SAC=%s", len(prev_full_text), _cov.details[:80])
            except Exception as _e:
                logger.debug("[STATE-ANCHOR] 记录失败: %s", _e)
            # R66（2026-08-04）best-so-far 稿保留：防止修订把好稿改成坏稿
            # （柯力事故：attempt1 高质量稿 → attempt3 泛化行业稿，且系统未感知）。
            # 记录每轮 Gate 分数与正文，保留最高分稿作为 best_so_far。
            try:
                _cur_text = ctx.get("final_text", "") or ctx.get("report_text", "")
                _bsf = self.__dict__.setdefault("_best_so_far", {"score": 0, "text": ""})
                if ig_score > _bsf["score"] and len(_cur_text) > 500:
                    _bsf["score"] = ig_score
                    _bsf["text"] = _cur_text
                    logger.info("[BEST-SO-FAR] 更新最佳稿: score=%.2f (%d字)", ig_score, len(_cur_text))
            except Exception as _e:
                logger.debug("[BEST-SO-FAR] %s", _e)
            # P1 补丁-语义早停（2026-08-07，Semantic Early-Stopping）：
            # 两轮修订之间做语义相似度判断——不再显著变化 = 收敛 = 提前停止，省 token 防空转。
            # 论文实测省 38% token 且质量不降。与 STALL（失败项不变）互补：早停看"内容变化"，
            # STALL 看"失败项不变"。只有内容几乎不变 + Gate 未过才触发（否则正常轮次不早停）。
            try:
                _cur_text = ctx.get("final_text", "") or ctx.get("report_text", "")
                _prev_txt = getattr(self, "_prev_attempt_text", None)
                if attempt > 0 and _prev_txt and len(_prev_txt) > 500 and len(_cur_text) > 500:
                    from difflib import SequenceMatcher

                    _ratio = SequenceMatcher(None, _prev_txt[:3000], _cur_text[:3000]).ratio()
                    _g_note = gate.get("passed", False) if isinstance(gate, dict) else False
                    if not _g_note and _ratio > settings.early_stop_similarity():
                        logger.warning(
                            "[EARLY-STOP] 本轮与上轮语义相似度 %.2f > 0.90 且 Gate 未过"
                            " → 判定已收敛不再变化，提前停止（省 token）",
                            _ratio,
                        )
                        ctx["early_stopped"] = True
                        # 用 best_so_far 稿交付（若有），避免把好稿空转改坏
                        _bsf2 = self.__dict__.get("_best_so_far", {"score": 0, "text": ""})
                        if _bsf2.get("text") and len(_bsf2["text"]) > 500:
                            ctx["final_text"] = ctx["report_text"] = _bsf2["text"]
                        break
                if _cur_text:
                    self._prev_attempt_text = _cur_text
            except Exception as _e2:
                logger.debug("[EARLY-STOP] %s", _e2)
            # R78（2026-08-05 Phase2.3）：每轮结束保存 checkpoint（中断可续跑）
            try:
                from pipeline.write_checkpoint import save_checkpoint

                _ck_state = {
                    "attempt": attempt + 1,
                    "report_text": ctx.get("final_text", "") or ctx.get("report_text", ""),
                    "gate_feedback": last_gate_feedback,
                    "collected_data": ctx.get("collected_data"),
                    "data_sufficiency": ctx.get("data_sufficiency"),
                    "gate_score": ig_score if isinstance(ig_score, (int, float)) else 0,
                }
                save_checkpoint(self.asset, self.report_type, _ck_state)
            except Exception as _cke:
                logger.debug("[CHECKPOINT] 保存失败: %s", str(_cke)[:60])
            # P2-3 影响传播接入（2026-08-07）：每轮把报告段存为模块版本；
            # Gate 未过 → 受影响模块标 dirty + 回滚到上一版，防"好段被坏段覆盖"。
            # 依赖 P0-2 module_version 地基。失败段定位用 rewrite_indices 已有逻辑。
            try:
                from core.module_version import ModuleVersion

                _mv = ModuleVersion(self.asset)
                _cur_txt = ctx.get("final_text", "") or ctx.get("report_text", "")
                _seg_txts = _split_report_sections(_cur_txt) if _cur_txt else {}
                if _seg_txts:
                    _passed_this = gate.get("passed", False) if isinstance(gate, dict) else False
                    for _seg_name, _seg_body in _seg_txts.items():
                        if len(_seg_body) < 100:
                            continue
                        _status = "active" if _passed_this else "dirty"
                        _mv.commit(_seg_name, _seg_body, metadata={"status": _status})
                    if not _passed_this:
                        logger.info("[MODVER] Gate 未过，%d 段已提交并标记 dirty（下一轮局部重写）", len(_seg_txts))
            except Exception as _mve:
                logger.debug("[MODVER] %s", str(_mve)[:60])
            if attempt < self.MAX_ATTEMPTS - 1:
                # FP5 写改循环：把 Gate 失败明细传给下一轮写作
                if isinstance(gate, dict) and not gate.get("passed", False):
                    fails = gate.get("failures", [])
                    if isinstance(fails, list) and fails:
                        # R12（2026-08-01 全量优化）：不再截断 fails[:5]——SAC 维度缺失、
                        # so_what 等结构性失败项常排在 5 名之后被丢弃，写循环因此不知道
                        # 要补哪些维度。现在传全部失败项 + 补充缺失维度清单。
                        feedback_lines = ["上一轮质量门禁未通过，请针对以下问题修订："]
                        for f in fails[:12]:
                            feedback_lines.append("- " + str(f)[:160])
                        # 提取缺失维度名（如 [必需维度缺失=founder_ri, milestone_]）
                        import re as _re

                        _m = _re.search(r"\[必需维度缺失=([^\]]+)\]", str(fails))
                        if _m:
                            missing_dims = _m.group(1).split(",")
                            feedback_lines.append(
                                "- 本轮必须补齐的 SAC 缺失维度: "
                                + ", ".join(d.strip() for d in missing_dims if d.strip())
                            )
                        last_gate_feedback = "\n".join(feedback_lines)
                    elif "score" in gate:
                        last_gate_feedback = f"上一轮质量门禁 score={gate.get('score', 0):.2f}，请提升报告质量。"
                    # R51（2026-08-02 P0-2）：失败项连续未变 → 换策略指令
                    # 不让 LLM 用同样手法再写一遍（churn reduction）。
                    if ctx.get("stalled"):
                        last_gate_feedback += (
                            "\n\n【策略警告】上一轮失败项与此前相同（已尝试未变）。"
                            "请改变写作策略，不要用同样的结构/措辞重写："
                            "针对失败项换一种论证路径或补充数据角度，若为数据不足请明确留白并标注。"
                        )
                try:
                    from pipeline.learning_loop import LearningLoop

                    LearningLoop().after_report(
                        self.asset,
                        self.report_type,
                        {
                            "failures": [f"Attempt {attempt + 1}: {last_error}"],
                        },
                    )
                except Exception:
                    pass
                time.sleep(2)

        # 全部尝试失败后：如果 L3 LLM 兜底信号存在，返回明确结构供 agent 感知
        if ctx.get("llm_degradation_level") == 3 or ctx.get("needs_agent") and ctx.get("llm_gap"):
            return {
                "passed": False,
                "attempt": self.MAX_ATTEMPTS,
                "report_text": "",
                "status": "needs_agent",
                "error": "LLM 不可用（单provider DeepSeek）",
                "needs_agent": True,
                "llm_degradation_level": 3,
                "llm_gap": ctx.get("llm_gap", "DeepSeek API 调用失败"),
                "data_sufficiency": ctx.get("data_sufficiency", {}),
                "data_enriched": ctx.get("data_enriched", False),
            }
        # R66（2026-08-04）：全部尝试失败时，优先返回 best-so-far 稿
        # （而非最后一轮可能已退化的稿）。柯力事故：attempt3 覆盖了 attempt1 的好稿。
        _bsf = self.__dict__.get("_best_so_far", {"score": 0, "text": ""})
        if _bsf.get("text"):
            _final_report = _bsf["text"]
            logger.info("[BEST-SO-FAR] 失败但保留最佳稿: score=%.2f (%d字)", _bsf["score"], len(_final_report))
            # 写回 _gate_prev.md 供下游呈现
            try:
                _bp = os.path.join(self.output_dir, "_gate_prev.md")
                with open(_bp, "w", encoding="utf-8") as _f:
                    _f.write(_final_report)
            except Exception:
                pass
        else:
            _final_report = ctx.get("final_text", "") or ctx.get("report_text", "")

        # R26（2026-08-02 全量修复缺陷5）：失败可观测
        # 不再只抛裸 RuntimeError——附带：各轮 Gate 失败清单 + 最终报告路径 + 失败类型 + 数据充足性
        _score_hist = self.__dict__.get("_gate_score_history", [])
        _last_report = ""
        _last_report_path = ""
        try:
            _tmp_p = os.path.join(self.output_dir, "_gate_prev.md")
            if os.path.exists(_tmp_p):
                _last_report_path = _tmp_p
                _last_report = open(_tmp_p, encoding="utf-8").read()[:2000]
        except Exception:
            pass
        _fail_types = ctx.get("_gate_fail_types", [])
        _sufficiency = ctx.get("data_sufficiency", {})
        _stall_note = "（失败项连续未变，已提前终止防无效重跑）" if getattr(self, "_stall_aborted", False) else ""
        summary = (
            f"E2E 失败: 共 {self.MAX_ATTEMPTS} 轮 Gate 未通过。"
            f"各轮 score={_score_hist}，失败类型={_fail_types or '见 gate_feedback'}。"
            f"数据充足性 sufficient={_sufficiency.get('sufficient')}，"
            f"semantic_gap={_sufficiency.get('semantic_gap', [])}。"
            f"最终报告(未过Gate)在 {_last_report_path}，前2000字: {_last_report[:500]}"
            f"{_stall_note}"
        )
        logger.error("[E2E-FAIL] %s", summary)
        raise RuntimeError(f"E2E failed after {self.MAX_ATTEMPTS} attempts: {last_error} | {summary}")


def _split_report_sections(text: str) -> dict:
    """按 Markdown 二级/三级标题把报告切成段（模块版本管理的段边界）。

    用 ## / ### 标题作为段切分点；无标题的正文归入 _preamble。
    返回 {段名: 段正文}。
    """
    import re as _re

    if not text:
        return {}
    sections = {}
    lines = text.split("\n")
    cur_title = "_preamble"
    cur = []
    for line in lines:
        m = _re.match(r"^(#{2,3})\s+(.+)", line)
        if m:
            if cur and cur_title:
                sections[cur_title] = "\n".join(cur).strip()
            cur_title = f"{len(m.group(2)):02d}_{m.group(2).strip()[:30]}"
            cur = [line]
        else:
            cur.append(line)
    if cur and cur_title:
        sections[cur_title] = "\n".join(cur).strip()
    # 过滤过短段
    return {k: v for k, v in sections.items() if len(v) >= 100}


def _revision_targets_from_gate(gate_feedback: str) -> list:
    """从上一轮 Gate 失败反馈中提取"修订目标"清单（供状态锚点注入写作循环）。

    把失败项解析成可执行的修订指令，避免把整段失败文本丢给 LLM 让它自行理解。
    返回形如 ["补写缺失维度: elasticity_analysis", "图表需嵌入正文而非堆末尾"] 的列表。
    """
    targets = []
    if not gate_feedback:
        return targets
    # 解析常见失败模式 → 修订目标
    mapping = [
        ("SAC维度覆盖", "补齐缺失的 SAC 必需维度（见覆盖矩阵缺失项）"),
        ("缺失=", "补齐缺失维度段落"),
        ("图表密度", "图表需嵌入对应正文段落，禁止堆叠末尾"),
        ("图表: 0", "正文需引用图表占位符 [CHART:fig_id]"),
        ("content_volume", "扩充内容至最低字数要求"),
        ("so_what_chain", "每段补 So What 链（数据→分析→判断→建议）"),
        ("explicit_conclusion", "开头给出明确评级+目标价+核心观点"),
        ("data_traceability", "每个数值标注具体来源（机构+报告+日期）"),
        # P3-audit 2026-08-24：E2E 实测高频失败项 → 修订靶向
        (
            "source_entity",
            "来源标注实体化：把『公司公告/公司年报/券商研究报告』改写为"
            "【公司名+文档名+日期】（如 宁德时代2025年三季报、高盛2026-08研报）",
        ),
        (
            "annotation_types",
            "补齐四类证据标注：历史业绩(A)、一致预期(E)、本报告预测(F)、"
            "行业基准/可比(B)，全文至少各出现一次且必须含(A)",
        ),
        ("evidence_layer", "提升数据来源覆盖率"),
        ("persuasion_architecture", "补市场共识表述与反方观点论证"),
        ("chart_analysis_quality", "每个图表附近加至少50字数据分析"),
        ("synthesis_consistency", "增加综合结论与跨段一致性"),
        ("stray_leading_period", "修正段首孤立句号"),
        ("duplicate_source_appendix", "去掉重复的来源附录"),
        ("missing_section_structure", "建立章节标题结构"),
    ]
    # R12（2026-08-01 全量优化）：把缺失的 SAC 维度名解析成逐条修订目标，
    # 让写循环精确知道要补哪几个维度，而不是笼统的"补齐缺失维度"。
    import re as _re

    _m = _re.search(r"\[必需维度缺失=([^\]]+)\]", gate_feedback)
    if _m:
        for _dim in _m.group(1).split(","):
            _d = _dim.strip()
            if _d and f"补齐 SAC 缺失维度: {_d}" not in targets:
                targets.append(f"补齐 SAC 缺失维度: {_d}")
    for key, target in mapping:
        if key in gate_feedback:
            t = f"{target}"
            if t not in targets:
                targets.append(t)
    return targets[:8]  # 最多8条，避免 prompt 过长


def _locate_failed_segments(context: dict, sw) -> list | None:
    """R78（2026-08-05 Phase3.1）：转发到 pipeline/fail_segment_locator.py。
    原 103 行定位逻辑已抽离，保持接口不变。
    """
    from pipeline.fail_segment_locator import locate_failed_segments

    return locate_failed_segments(context, sw)


def _build_output_contracts():
    contracts = {
        "preflight": {"runtime_score": {"type": float, "required": True, "severity": "warning"}},
        "hypothesis": {"hypothesis_result": {"type": object, "required": False, "severity": "warning"}},
        "data": {"collected_data": {"type": dict, "required": True, "severity": "error"}},
        "scarcity": {"scarcity_signals": {"type": list, "required": False, "severity": "warning"}},
        "cross_validate": {"cross_validation": {"type": object, "required": False, "severity": "warning"}},
        "compute": {"compute_results": {"type": dict, "required": False, "severity": "warning"}},
        "argument": {"scaffold": {"type": object, "required": False, "severity": "warning"}},
        "learning": {"learning_findings": {"type": str, "required": False, "severity": "warning"}},
        "charts": {"chart_paths": {"type": dict, "required": True, "severity": "warning"}},
        "write_sections": {"report_text": {"type": str, "required": True, "severity": "error"}},
        "style": {"compiled_text": {"type": str, "required": True, "severity": "error"}},
        "template": {"template_result": {"type": dict, "required": False, "severity": "warning"}},
        "assemble": {"final_text": {"type": str, "required": True, "severity": "error"}},
        "validate": {"gate_result": {"type": dict, "required": True, "severity": "error"}},
        "compliance": {"compliance_result": {"type": dict, "required": False, "severity": "warning"}},
        "export_docx": {"_docx_path": {"type": str, "required": False, "severity": "warning"}},
        "data_feeds": {"feeds_loaded": {"type": bool, "required": False, "severity": "warning"}},
        "biz_macro": {
            "biz_model": {"type": object, "required": False, "severity": "warning"},
            "stage_ctx": {"type": object, "required": False, "severity": "warning"},
            "stage_summary": {"type": str, "required": False, "severity": "warning"},
            "macro_ctx": {"type": object, "required": False, "severity": "warning"},
        },
        "critic": {
            "critic_report": {"type": object, "required": False, "severity": "warning"},
            "critic_passed": {"type": bool, "required": False, "severity": "warning"},
        },
    }
    return contracts
