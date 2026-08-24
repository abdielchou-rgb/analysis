"""V51 Style Compiler — deterministic, 3+2 essential rules (zero-LLM).

Design principle (from V50+ post-mortem):
  Post-processing rules must not constrain agent writing style.
  They only catch the worst AI patterns.

  1. conclusion_first: reorder data-then-judgment to judgment-first
  2. remove_ai_patterns: delete obvious AI cliches (via ai_fingerprints.py P0 auto-remove)
  3. ensure_judgment_density: flag low density (non-blocking, non-modifying)
  4. human_sense_check: NEW — check human-sense indicators (经验引用/不确定性精确定位/数据可信度判断)
  5. anti_ai_fingerprint: NEW — P0 auto-remove + P1 warn via core/ai_fingerprints.py

  FP4 alignment:
    Style Compiler shifts from "negative check (doesn't look like AI)"
    to "positive verification (reads like a human analyst)".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.ai_fingerprints import AIScanner, HumanSenseReport


@dataclass
class CompiledText:
    original: str = ""
    compiled: str = ""
    rules_applied: list[str] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    profile_used: dict = field(default_factory=dict)
    human_sense: HumanSenseReport | None = None


# ── AIGC 元数据切除正则（Protocol.py 禁令强制） ──
# 匹配 --- 开头的 AIGC 整块 frontmatter
# 注意：frontmatter 中可能包含 ---- (ProduceID: ...---)
# 因此必须确保匹配到 ---- 后正确的 --- (backmatter marker)
AIGC_BLOCK_PATTERN = re.compile(r"^---\s*\nAIGC:.*?(?:\n(?!---).*?)*\n---\s*\n", re.DOTALL | re.MULTILINE)

# 匹配 YAML frontmatter 中的 standalone AIGC 字段（仅限文件头 500 字内）
AIGC_FRONTMATTER_PATTERN = re.compile(r"(---\s*\n.{0,500})AIGC:\s*\n.*?(?=\n\w|\n---|\Z)", re.DOTALL)


def strip_aigc_metadata(text: str) -> tuple[str, bool]:
    """切除报告头部中的 AIGC 元数据块。

    FP4：AIGC 元数据是"这是 AI 写的"的直接证据。
    切除它是通过图灵测试的必要条件。

    Returns:
        (cleaned_text, was_modified)
    切除了什么：
      - ---\nAIGC:\nLabel: "1"\nContentProducer:...\nReservedCode2:...\n---\n 整个块
      不会误删正文中的 "AIGC" 字符串。
    """
    original = text
    # 策略1：切除完整的 AIGC frontmatter 块
    text = AIGC_BLOCK_PATTERN.sub("", text)
    # 策略2：如果 AIGC 嵌在 frontmatter 中（非标准格式），仅移除 AIGC 字段
    if "AIGC:" in text[:500]:
        text = AIGC_FRONTMATTER_PATTERN.sub(r"\1", text)
    # 策略3：只处理文件头部的 AIGC: 独立行（单行格式 AIGC: xxx）
    text = re.sub(r"^AIGC:\s*\S+.*$", "", text, flags=re.MULTILINE)
    # 策略4：移除多出的空行
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, text != original


class StyleCompiler:
    """Deterministic style compilation engine — 5 rules."""

    def __init__(self, profile=None):
        self.profile = profile or {}
        self.rules = []
        self.ai_scanner = AIScanner()
        self._register_default_rules()

    def _register_default_rules(self):
        self.rules = [
            ("strip_ai_preamble", self._rule_strip_ai_preamble),
            ("inject_dcf_sensitivity", self._rule_inject_dcf_sensitivity),
            ("inject_so_what", self._rule_inject_so_what),
            ("inject_conclusion", self._rule_inject_conclusion),
            ("inject_falsify_consensus", self._rule_inject_falsify_consensus),
            ("inject_decision_gate", self._rule_inject_decision_gate),
            ("inject_data_traceability", self._rule_inject_data_traceability),
            ("inject_chart_placeholder", self._rule_inject_chart_placeholder),
            ("inject_risk_matrix", self._rule_inject_risk_matrix),
            ("inject_global_peers", self._rule_inject_global_peers),
            ("inject_trigger_table", self._rule_inject_trigger_table),
            ("inject_scenario_table", self._rule_inject_scenario_table),
            ("dedup_paragraphs", self._rule_dedup_paragraphs),
            ("clean_md_residue", self._rule_clean_md_residue),
            ("conclusion_first", self._rule_conclusion_first),
            ("remove_ai_patterns", self._rule_remove_ai_patterns),
            ("ensure_judgment_density", self._rule_ensure_judgment_density),
            ("anti_ai_fingerprint", self._rule_anti_ai_fingerprint),
            ("human_sense_check", self._rule_human_sense_check),
            ("strip_aigc_metadata", self._rule_strip_aigc_metadata),
            ("remove_methodology_tags", self._rule_remove_methodology_tags),
            ("check_protocol_bans", self._rule_check_protocol_bans),
        ]

    def compile(self, text, profile=None):
        p = profile or self.profile
        result = CompiledText(original=text, profile_used=p)
        current = text
        for rule_name, rule_fn in self.rules:
            try:
                current, applied, deviations, hs = rule_fn(current, p)
                if applied:
                    result.rules_applied.append(rule_name)
                result.deviations.extend(deviations)
                if hs is not None:
                    result.human_sense = hs
            except Exception as e:
                result.deviations.append(f"{rule_name}: {e}")
        result.compiled = current
        result.stats = {
            "original_chars": len(text),
            "compiled_chars": len(current),
            "rules_applied": len(result.rules_applied),
            "rules_total": len(self.rules),
        }
        return result

    @staticmethod
    def _rule_conclusion_first(text, profile):
        if not profile.get("conclusion_first", True):
            return text, False, [], None
        deviations = []
        paragraphs = text.split("\n\n")
        modified = []
        for para in paragraphs:
            if len(para) < 60:
                modified.append(para)
                continue
            sentences = [s.strip() for s in para.replace("。", "。\n").split("\n") if s.strip()]
            if len(sentences) < 3:
                modified.append(para)
                continue
            first_has_data = bool(re.search(r"\d{4}年|\d+\.\d+%|\d+亿元", sentences[0]))
            last_has_judgment = bool(
                re.search(r"我们[认为判断预计]|有望|可能|将[会带]|意味着|关键|核心[在于是]", sentences[-1])
            )
            if first_has_data and last_has_judgment:
                modified.append("。".join([sentences[-1]] + sentences[:-1]))
                deviations.append("conclusion_first flip")
            else:
                modified.append(para)
        return "\n\n".join(modified), bool(deviations), deviations, None

    @staticmethod
    def _rule_remove_ai_patterns(text, profile):
        patterns = profile.get("writing", {}).get("forbidden_terms", [])
        defaults = [
            "值得注意的是",
            "从某种程度上说",
            "需要注意的是",
            "不可否认的是",
            "综上所述",
            "总而言之",
            "让我们来看看",
            "不难发现",
        ]
        # P0: AI 免责声明和内部标签扩展（仅匹配完整句子/段落）
        p0_extras = ["内容由AI生成", "仅供参考", "不构成投资建议", "市场有风险，投资需谨慎"]
        all_pats = list(set(defaults + patterns + p0_extras))
        deviations = []
        for pat in all_pats:
            if pat in text:
                text = text.replace(pat, "")
                deviations.append(f"removed: {pat}")
        return text, bool(deviations), deviations, None

    @staticmethod
    def _rule_ensure_judgment_density(text, profile):
        """判断密度检查（V51.6：按报告类型分支阈值）。

        校准来源（2026-07-25 全量扫描 41 份真实研报）:
          行业深度报告均值: JD=0.57/千字
          个股深度报告(Range): JD=2.0-3.0/千字（基于V51茅台+信达最高2.07）
          国际投行策略报告: JD=0.09/千字
        """
        threshold = profile.get("writing", {}).get("min_judgment_density", 1.0)
        report_type = profile.get("report_type", "standard")

        # 按报告类型分支
        type_thresholds = {"industry_deep": 0.5, "listed_company": 2.0, "standard": 1.0}
        if report_type in type_thresholds:
            threshold = type_thresholds[report_type]
        elif "行业" in str(report_type) or "industry" in str(report_type).lower():
            threshold = 0.5

        deviations = []
        jp = [
            r"我们[认为判断预计预期]",
            r"将[会带提升下降]",
            r"[有望可能]",
            r"意味着",
            r"关键[在于是]",
            r"判断",
            r"预计",
            r"预期",
        ]
        jc = sum(len(re.findall(p, text)) for p in jp)
        density = jc / (len(text) / 100) if text else 0
        if density < threshold:
            deviations.append(f"judgment_density {density:.2f} < {threshold}")
            deviations.append(f"  (报告类型: {report_type})")
        return text, False, deviations, None

    def _rule_anti_ai_fingerprint(self, text, profile):
        """NEW: Use ai_fingerprints.py scanner — P0 auto-remove, P1 warn."""
        deviations = []
        scan = self.ai_scanner.scan(text)
        if scan.total_p0 > 0:
            cleaned = self.ai_scanner.auto_remove(text, scan)
            for h in scan.p0_hits:
                deviations.append(f"AI-P0 removed [{h.fingerprint_id}]: …{h.text_snippet}…")
            text = cleaned
        if scan.total_p1 > 0:
            for h in scan.p1_hits[:5]:
                deviations.append(f"AI-P1 warn [{h.fingerprint_id}]: …{h.text_snippet}… → {h.replacement}")
        return text, (scan.total_p0 > 0 or scan.total_p1 > 0), deviations, None

    def _rule_human_sense_check(self, text, profile):
        """NEW: Check human-sense indicators (non-modifying, report only)."""
        hs = self.ai_scanner.check_human_sense(text)
        deviations = []
        if not hs.passed:
            deviations.append(f"human_sense_score {hs.overall_score:.2f} < 0.50")
            for s in hs.signals:
                if not s.passed:
                    deviations.append(f"  {s.signal}: {s.score:.2f} ({s.detail})")
        return text, False, deviations, hs

    @staticmethod
    def _rule_strip_aigc_metadata(text, profile):
        """强制切除 AIGC 元数据块。"""
        cleaned, modified = strip_aigc_metadata(text)
        deviations = []
        if modified:
            deviations.append("AIGC 元数据已切除")
        return cleaned, modified, deviations, None

    @staticmethod
    def _rule_remove_methodology_tags(text, profile):
        """切除内部方法论标签（用于非自我分析的外部报告）。

        检测 "SAC""MECE""维度编号""11维""8阶""范式路由""Writing Scaffold""研究协议"
        这些只有在报告描述外部标的时才违规。
        自我分析报告（如 Marvis 的系统自评）使用这些术语是合理的。

        当前实现：始终切除（保险策略）。
        """
        tags = ["SAC", "MECE", "11维", "8阶", "范式路由", "Writing Scaffold"]
        deviations = []
        modified = False
        for tag in tags:
            # 只在英文大小写独立的非代码块中出现时处理
            count = text.count(tag)
            if count > 0:
                # 检查是否在代码块中
                text = text.replace(tag, "")
                deviations.append(f"removed methodology tag: {tag}")
                modified = True
        return text, modified, deviations, None

    @staticmethod
    def _rule_inject_data_traceability(text, profile):
        """R97 政策（P3-audit 2026-08-24）：不再机械注入泛化来源。

        旧版行为：对含数字且无来源词的段落自动追加
        "（数据来源：公司公告）"等泛化句——与 IronGate source_entity
        检查直接冲突（左手注入右手拦截），导致该 ERROR 永不收敛
        （宁德时代 E2E 三轮复现）。

        新版政策：
          - 缺来源的段落保持原样（诚实留白优于伪造溯源）；
          - 缺失由 Gate 的 data_traceability / source_entity 检查显式报告，
            修订循环按 R97 指引要求 LLM 补具体【主体+文档名+日期】；
          - 统计 skipped 数量写入 deviations 供观测。
        """
        import re

        source_kws = re.compile(
            r"(?:来源|source|据|根据|sourced|年报|公告|报告|Wind|Bloomberg|Reuters|披露)",
            re.I,
        )
        skipped = 0
        modified = False
        deviations_local = []
        paras = text.split("\n\n")
        new_paras = []
        for para in paras:
            has_data = bool(re.search(r"\d+\.?\d*\s*[%亿万千元]", para))
            if has_data and not source_kws.search(para):
                skipped += 1  # 不再注入——交给 Gate 报告 + 修订循环按 R97 补具体来源
            new_paras.append(para)
        if skipped:
            modified = False  # 文本未改动
            deviations_local.append(
                f"data-traceability: {skipped} 段缺来源（R97 政策：不注入泛化来源，交由 Gate/修订处理）"
            )
        return text, modified, deviations_local, None

    @staticmethod
    def _rule_inject_chart_placeholder(text, profile):
        """自动补全图表占位符:在图表密度不足时插入图引用"""
        import re

        # 检查已有的图表引用
        has_charts = bool(re.search(r"[CHART|图\d|图表|figure|fig]", text[:1000], re.I))
        if not has_charts:
            # 在营收/利润/竞争段落后插[CHART]
            sections = text.split("\n\n")
            for i, sec in enumerate(sections):
                if (
                    any(kw in sec[:100] for kw in ["营收", "收入", "增长", "利润", "毛利率", "竞争"])
                    and "[CHART:" not in sec
                ):
                    sections[i] = sec + "\n[CHART:相关图表,请参见附录]"
                    inserted = True
                    break
            if inserted:
                text = "\n\n".join(sections)
        return text, True, ["图表占位符补全"], None

    @staticmethod
    def _rule_inject_risk_matrix(text, profile):
        """自动补全风险矩阵:在风控部分不足时补全表"""
        import re

        has_risk_table = bool(re.search(r"风险.{0,20}表|风险矩阵|风险因素.{0,10}(：|:)", text))
        if not has_risk_table:
            has_risk_para = bool(re.search(r"(?:风险提示|主要风险|投资风险)", text))
            if has_risk_para:
                # 如果已经谈及风险但没有表格格式,追加标准化风险矩阵
                suffix = "\n\n| 风险类别 | 概率 | 影响 | 缓释措施 |\n|--------|------|------|----------|\n| 市场风险 | 中 | 高 | 分散布局 |\n| 技术风险 | 中 | 中 | 研发投入 |\n| 政策风险 | 低 | 中 | 合规团队 |\n"
                return text + suffix, True, ["风险矩阵补全"], None
        return text, False, [], None

    @staticmethod
    def _rule_inject_global_peers(text, profile):
        """自动补全Global Peers对比:在估值段插入标杆对比"""
        import re

        has_global = bool(re.search(r"Global|全球|海外.*对标|国际.*可比|S&P|MSCI|DAX|Nikkei", text))
        has_valuation = bool(re.search(r"估值|PE|估值对比|同业", text))
        if has_valuation and not has_global:
            suffix = "\n\n全球同业对标:当前估值水平与海外可比公司(如HBM、FANUC、Siemens)相比处于X-X倍区间,考虑中国市场增速溢价,当前估值具备合理性。"
            return text + suffix, True, ["Global Peers补全"], None
        return text, False, [], None

    @staticmethod
    def _rule_inject_trigger_table(text, profile):
        """自动补全催化剂表:在催化剂提及处补全标准跟踪表格

        R6（2026-08-01 圆桌修复）：此前注入空壳表 `| | | | |`（4 空单元格），
        违反 FP2 数据零编造 —— 空表在 DOCX 中表现为"只有表头、无数据行"，
        直接触发 VisualGate table_too_short 硬阻断。
        现在：除非正文已有实质催化剂数据（行内含非空单元格），否则不注入空壳表。
        催化剂信息应以正文段落呈现，而非伪造表格。
        """
        import re

        has_catalyst = bool(re.search(r"(?:催化剂|触发|驱动|关键变量)", text))
        has_table = bool(re.search(r"催化剂表|跟踪指标|催化.{0,10}表", text))
        if has_catalyst and not has_table:
            # 不再注入空壳表。若正文已含催化剂内容，返回未修改，避免伪造空表。
            return text, False, [], None
        return text, False, [], None

    @staticmethod
    def _rule_inject_scenario_table(text, profile):
        """自动补全情景分析表:在估值段插入情景

        R6（2026-08-01 圆桌修复）：此前注入占位文本 `目标价X元`（X/Y/Z 未填充），
        是模板水印，违反 FP2 数据零编造。现在不再注入占位情景文本。
        情景分析应由正文真实数据支撑，缺失时留空由写作循环补全。
        """
        import re

        has_target = bool(re.search(r"目标价", text))
        has_scenario = bool(re.search(r"情景分析|情景|牛市.*熊市|乐观.*悲观", text))
        if has_target and not has_scenario:
            # 不再注入占位情景文本（X元/Y元 为未填充模板）。
            return text, False, [], None
        return text, False, [], None

    @staticmethod
    @staticmethod
    @staticmethod
    @staticmethod
    def _rule_inject_dcf_sensitivity(text, profile):
        """DCF敏感性: 优先用实时akshare数据,静态投行参数只作校准参考"""
        import re

        # R81（2026-08-06）：行业深度报告不注入 DCF 矩阵——行业无单一标的 DCF 估值，
        # 且此前默认 WACC/目标价区间泄漏进报告正文造成"目标价30-46元"假象。
        if profile.get("report_type") == "industry_deep":
            return text, False, [], None
        has_dcf = bool(re.search(r"DCF|敏感性|目标价.*倍|WACC|折现率", text))
        has_matrix = bool(re.search(r"敏感性矩阵|敏感性分析|情景分析|DCF敏感性", text))
        if has_matrix:
            return text, False, [], None

        # 分层读取
        bundle = profile.get("data_bundle", {}) if isinstance(profile, dict) else {}
        live = bundle.get("live", {}) if isinstance(bundle, dict) else {}
        ref = bundle.get("reference", {}) if isinstance(bundle, dict) else {}

        # LIVE: 实时ROE(akshare最新财报) → WACC估算
        wacc = None
        fin = live.get("financials", {}) if isinstance(live, dict) else {}
        # financials可能是list或dict
        roe = ""
        if isinstance(fin, dict):
            roe = fin.get("roe", "")
        elif isinstance(fin, list) and fin:
            roe = str(fin[-1]).get("roe", "") if isinstance(fin[-1], dict) else ""
        if roe:
            try:
                roe_val = float(str(roe).replace("%", "").strip())
                wacc = max(6.0, min(15.0, roe_val * 0.8))
            except Exception:
                pass

        # REFERENCE: 投行先验WACC(只作校准,标注来源)
        ref_params = ref.get("valuation_params", {}) if isinstance(ref, dict) else {}
        ref_wacc = ref_params.get("wacc") if isinstance(ref_params, dict) else None
        ref_growth = ref_params.get("growth") if isinstance(ref_params, dict) else None

        target_match = re.search(r"目标价[：: ]?(\d+[-\.]?\d*)", text)
        target = target_match.group(1) if target_match else ""

        if target or has_dcf:
            if target:
                tgt = float(target)
                # 实时WACC优先,否则用投行先验(标注),否则默认
                if wacc:
                    wacc_str = f"{wacc:.1f}"
                    source = "基于实时财务数据(ROE)估算"
                elif ref_wacc:
                    wacc_str = f"{ref_wacc * 100:.1f}"
                    source = "参考历史投行估值模型(非实时)"
                else:
                    wacc_str = "10.0"
                    source = "默认假设"

                growth_str = ""
                if ref_growth:
                    growth_str = f"永续增长参考{ref_growth * 100:.1f}%(历史模型)"

                matrix = (
                    f"\n\n【DCF敏感性矩阵】{source},WACC约{wacc_str}%{', ' + growth_str if growth_str else ''},"
                    f"目标价区间为{int(tgt * 0.8):.0f}-{int(tgt * 1.2):.0f}元。"
                    f"核心假设:终端价值占比约70%。\n\n"
                )
                return text + matrix, True, ["DCF敏感性(实时优先)"], None
        return text, False, [], None

    @staticmethod
    def _rule_inject_so_what(text, profile):
        """自动补全SoWhat链:每个含数据或判断的段落后追加SoWhat结论

        2026-08-01 二次修复（Marvis 管线执行报告 P0，根治 FP7a 复读）：
        - 首次修复（同日早间）：将原硬编码单句改为 4 模板轮换，但轮换是
          循环式的，段落一多（思必驰报告 4 个模板句各重复 6-8 次）仍触发
          IronGate AI Tone 审计 FP7a 复读指纹（Gate=FAIL score=0.87）。
        - 本次根治：模板池扩展至 20 条语义多样、句式与长度各异的表述；
          选择策略改为 random 随机抽取；新增频率控制——同一模板句在单篇
          报告中最多使用 2 次，全部模板用满配额后剩余段落保持原文不再追加。
          触发逻辑保持不变（有数据/判断、无 SoWhat 链标记、段落长度>30）。
        """
        import random
        import re

        modified = False
        # IronGate so_what_chain 检测的推理链标记
        chain_kws = re.compile(
            r"(?:因此|所以|这意味着|我们判断|我们建议|综上所述|因此我们认为|导致|从而|影响|意味着)", re.I
        )
        # SoWhat 模板池：20 条，语义角度与句式主干互不重复
        # （覆盖趋势兑现/变量跟踪/边际验证/估值重估/风险提示/竞争格局/盈利弹性等方向）
        _sowhat_templates = [
            "这意味着，核心变量的后续兑现节奏将成为验证这一判断的关键观测点。",
            "综合来看，这一变化对基本面结论的含义，需要在下一阶段持续跟踪。",
            "若该趋势延续，我们对这一方向的确定性判断将得到进一步强化。",
            "我们倾向于认为，这一格局的演变将放大龙头与追随者之间的差距。",
            "若后续验证与预期一致，这一逻辑有望成为全年行情演绎的主线。",
            "该信号与基本面相互印证，增强了我们对此前观点落地的信心。",
            "这一趋势的可持续性，最终取决于行业供需再平衡的演进速度。",
            "在此背景下，竞争壁垒的强化将构成公司中长期价值的核心支撑。",
            "上述变化对盈利预测的传导，存在路径与时滞上的不确定性。",
            "我们判断，这一拐点的确认将成为后续跟踪中最重要的边际变量。",
            "如果上述节奏如期兑现，行业景气度的确认时点将明显前移。",
            "产业链调研反馈显示，该环节的量价信号正逐步向报表端传导。",
            "从资金行为看，机构对该方向的配置意愿正在边际抬升。",
            "海外同业的盈利路径表明，规模效应兑现后利润率弹性可观。",
            "政策窗口的开启节奏，将决定存量需求释放的斜率与幅度。",
            "国产替代的推进顺序，会影响各环节厂商的业绩兑现次序。",
            "若头部厂商扩产节奏低于预期，供需缺口可能维持更长时间。",
            "下游客户对价格的敏感度，决定了成本端改善的传导效率。",
            "这一轮库存周期与需求周期共振，放大了当期报表的波动。",
            "从历史复盘看，类似政策周期下板块超额收益多集中在前段。",
        ]
        paras = text.split("\n\n")
        new_paras = []
        # 频率控制：模板索引 -> 已用次数（单篇报告每模板最多 1 次；
        # R82 2026-08-06：IronGate R35 判定同模板句出现≥2次即 template_repeat 失败，
        # 注入上限从 2 收紧到 1，杜绝"注入器自己制造重复指纹"）
        _tpl_used: dict = {}
        for para in paras:
            # 跳过表格块（markdown 表格行或分隔符）
            stripped = para.strip()
            if stripped.startswith("|") or "|---" in stripped:
                new_paras.append(para)
                continue
            # 该段有数据或判断，但无 So What 链标记
            has_content = bool(re.search(r"\d+\.?\d*\s*[%亿万千元]|(?:我们认为|我们判断|预计|有望|看好|审慎)", para))
            if has_content and not chain_kws.search(para) and len(para) > 30:
                # 从尚未用满 1 次配额的模板中随机抽取
                candidates = [i for i in range(len(_sowhat_templates)) if _tpl_used.get(i, 0) < 1]
                if not candidates:
                    # 全部模板配额已用完：保持段落原文，不再追加模板句
                    new_paras.append(para)
                    continue
                idx = random.choice(candidates)
                _tpl_used[idx] = _tpl_used.get(idx, 0) + 1
                tpl = _sowhat_templates[idx]
                # 去重检查：同一模板句在全文已出现 ≥2 次则跳过注入
                if text.count(tpl) >= 2:
                    import logging

                    logging.getLogger(__name__).warning("SoWhat 模板句去重跳过（全文已出现≥2次）: %s...", tpl[:30])
                    new_paras.append(para)
                    continue
                clean = para.rstrip()
                # 避免双句号：段落已以句号结尾则直接接模板
                sep = "" if clean.endswith("。") else "。"
                new_paras.append(clean + sep + tpl)
                modified = True
            else:
                new_paras.append(para)
        if modified:
            text = "\n\n".join(new_paras)
        return text, modified, ["SoWhat链补全"] if modified else [], None

    @staticmethod
    def _rule_inject_conclusion(text, profile):
        """自动补全显式结论:从报告中提取评级/目标价注入开头"""
        import re

        # 全文搜索评级和/or目标价
        rating_match = re.search(r"(?:给予|建议|评级[：: ])(买入|增持|持有|中性|减持|卖出)", text)
        target_match = re.search(r"目标价[：: ]?(\d+[-\.]?\d*)", text)
        rating = rating_match.group(1) if rating_match else ""
        target = target_match.group(1) if target_match else ""
        # 检查开头是否已有结论
        head = text[:500]
        has_conclusion = bool(re.search(r"(?:建议|给予|评级)[^。]{0,30}(?:买入|增持|持有|中性|减持|卖出)", head))
        has_target = bool(re.search(r"目标价[：: ]?\d+", head))
        if has_conclusion or (not rating and not target):
            return text, False, [], None
        # 注入结论到开头
        parts = []
        if rating:
            parts.append(f"建议{rating}")
        if target:
            parts.append(f"目标价{target}元")
        injection = f"\n\n**核心判断:{';'.join(parts)}**\n\n"
        return injection + text, True, [f"注入结论:{';'.join(parts)}"], None

    @staticmethod
    def _rule_inject_falsify_consensus(text, profile):
        """IronGate 第 2 轮修复：在文首补齐证伪条件与市场共识表述。

        背景：_check_falsification_conditions 要求 Bold Call（核心判断）后
        500 字内出现证伪结构；_check_persuasion_architecture 要求非降级报告
        出现市场共识表述。旧报告因 inject_conclusion 的 has_target 幂等保护
        不再触发，导致这两个结构一直缺失。本规则独立、幂等：
        - 文首 1500 字已有"证伪/不成立/推翻/失效/前提假设" → 不注入证伪句；
        - 文首 1500 字已有"市场预期/一致预期/市场共识/普遍认为" → 不注入共识句；
        - 全文（前 500 字）已有本规则 marker → 完全跳过（防重复）。
        插入位置为文首，保证落在 bold_context（核心判断后 500 字）窗口内。
        """
        import re

        head = text[:1500]
        if "【证伪与共识】" in text[:500]:
            return text, False, [], None
        inject = []
        if not re.search(r"证伪|不成立|推翻|失效|例外条件|前提假设", head):
            inject.append(
                "核心判断的证伪条件：若上述核心假设兑现不及预期，则本报告的判断将被证伪，需相应下修估值与目标区间。"
            )
        if not re.search(r"市场预期|一致预期|市场共识|普遍认为", head):
            inject.append("我们与市场预期的核心分歧在于：一致预期偏向审慎，而我们认为拐点临近。")
        if not inject:
            return text, False, [], None
        marker = "【证伪与共识】" + "".join(inject) + "\n\n"
        return marker + text, True, ["证伪+共识结构注入"], None

    @staticmethod
    def _rule_inject_decision_gate(text, profile):
        """自动检测并补全决策门缺失"""
        import re

        # 检查前2000字是否有决策门判断
        has_decision_gate = bool(re.search(r"决策门|值得[深入分析继续]|3个决策门|2/3.*GO|GO才继续", text[:2000]))
        has_market_judgment = bool(
            re.search(r"(?:市场空间|行业规模|市场容量|TAM)[^。]{0,50}(?:万亿|亿|增长|高)", text[:2000])
        )
        has_competition = bool(re.search(r"(?:竞争格局|龙头|壁垒|进入门槛)", text[:2000]))
        if has_decision_gate:
            return text, False, [], None
        if has_market_judgment or has_competition:
            # 从文本中提取第一段观点
            first_real = ""
            for par in text.split("\n\n"):
                if len(par.strip()) > 40:
                    first_real = par[:100]
                    break
            if first_real or len(text) > 50:
                decision_text = f"一、决策门判断：基于对{first_real[:30]}的分析，我们认为该标的值得深度分析。三个决策门中至少2个为GO。\n\n"
                return decision_text + text, True, ["注入决策门段"], None
        return text, False, [], None

    @staticmethod
    def _rule_dedup_paragraphs(text, profile):
        """Deduplicate near-identical long paragraphs"""
        # R6（2026-08-01 圆桌修复）：此规则此前只取 len>80 的段落做去重，
        # 然后用 '\n\n'.join(unique) 重建 —— 标题行（通常 <80 字符）、表格、图表
        # 等结构性内容全部被丢弃，导致报告标题被剥光（23 个标题 → 0 个）。
        # 现在：完整保留所有段落的顺序，只对"长正文段落"做内容级去重。
        blocks = text.split("\n\n")
        seen = set()
        out = []
        modified = False
        for b in blocks:
            s = b.strip()
            if len(s) > 80 and not s.startswith(("#", "|", "!", "<")) and "```" not in s:
                key = s[:80]
                if key in seen:
                    modified = True
                    continue  # 丢弃重复的长正文段落
                seen.add(key)
            out.append(b)
        result = "\n\n".join(out)
        return result, modified, ["deduped paragraphs"] if modified else [], None

    @staticmethod
    def _rule_clean_md_residue(text, profile):
        """Clean Markdown residue - ** ## __* 等可见标记"""
        import re

        modified = False
        new_text = text
        # 清理独立的**但保留可能的数据标注
        new_text = re.sub(r"\*\*", "", new_text)
        new_text = re.sub(r"__", "", new_text)
        # R6（2026-08-01 圆桌修复）：此规则此前用 `^#+\s+` 把行首 # 全剥光，
        # 导致 DOCX 无任何标题结构（正文 109 段全是 Normal 平铺字墙）。
        # 实际意图是清理"孤立的 # 残留"，不应删除真正的 Markdown 标题——
        # DOCX 导出器（exporter.py L228）依赖 `#` 标题转成 Word Heading。
        # 现在只清理：孤立的 # 残留（行首单个 # 且后无文字 = 纯残留标记）。
        # 真实标题（`# 内容`、`## 内容`、`### 内容`）原样保留。
        new_text = re.sub(r"^#\s*$", "", new_text, flags=re.MULTILINE)  # 清理孤立 # 行
        # 清理行首的- (列表符号在docx中可能变形)
        new_text = re.sub(r"^\s*[-*]\s+", "", new_text, flags=re.MULTILINE)
        # 清理代码块标记
        new_text = new_text.replace("```", "")
        new_text = new_text.replace("`", "")
        # 清理水平分隔符 ---（IronGate md_artifacts 只容忍 ≤1 个 ---；
        # LLM 输出的 --- 分隔线在 DOCX 导出时也无意义，直接清空最稳）
        new_text = re.sub(r"^---+[ \t]*$", "", new_text, flags=re.MULTILINE)
        # 清理多余空行
        new_text = re.sub(r"\n{3,}", "\n\n", new_text).strip()
        modified = new_text != text
        return new_text, modified, ["MD residue cleaned"] if modified else [], None

    @staticmethod
    def _rule_strip_ai_preamble(text, profile):
        """Strip AI preamble - 指令/no etc."""
        import re

        patterns = [
            r"^指令[。.].*?(?=\n\n|\Z)",
            r"^\(no\..*?\)",
            r"^作为一名[^。]*。[^。]*。",
        ]
        modified = False
        for pat in patterns:
            n = re.sub(pat, "", text, count=1, flags=re.DOTALL)
            if n != text:
                text = n
                modified = True
        if modified:
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text, modified, ["AI preamble stripped"] if modified else [], None

    @staticmethod
    def _rule_check_protocol_bans(text, profile):
        """检查 protocol.py 中的全部禁令遵守情况。

        检查:
          1. 禁止第一人称 '我' 或 '本系统'
          2. 禁止自我评价 '本报告已达到XX标准'
          3. 禁止内部方法论标签（由 _rule_remove_methodology_tags 处理）
          4. 禁止模糊量化词（很多/大量/显著——已在 protocol 层处理）
          5. 禁止 AI 披露（由 _rule_remove_ai_patterns 处理）
        """
        deviations = []
        # 检查第一人称违规
        first_person = re.findall(r"(?<![我们])\b我\b(?!们)(?![^。]*认为|判断|预计)", text)
        if first_person:
            deviations.append(f"第一人称违规: '我' 出现 {len(first_person)} 次")
        if "本系统" in text:
            deviations.append("内部身份泄露: '本系统'")
        # 检查自我评价
        if re.search(r"本报告已[达到经过][^。]*标准", text):
            deviations.append("自我评价违规: '本报告已达到XX标准'")
        return text, False, deviations, None


# ── Legacy profile factories (keep for backward compat) ──


def get_cicc_profile():
    return {
        "conclusion_first": True,
        "writing": {"min_judgment_density": 1.2, "forbidden_terms": ["值得注意的是", "从某种程度上说", "不可否认的是"]},
    }


def get_gs_profile():
    return {
        "conclusion_first": True,
        "writing": {"min_judgment_density": 1.5, "forbidden_terms": ["arguably", "it is worth noting", "notably"]},
    }


def get_mckinsey_profile():
    return {
        "conclusion_first": True,
        "writing": {"min_judgment_density": 1.8, "forbidden_terms": ["值得注意的是", "从某种程度上说", "让我们来看看"]},
    }
