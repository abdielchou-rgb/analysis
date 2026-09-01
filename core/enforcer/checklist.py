"""10-item compliance checklist for methodology enforcement."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ComplianceChecklistItem:
    check_id: str = ""
    name: str = ""
    passed: bool = False
    detail: str = ""


class ComplianceChecklist:
    """10-post-processing compliance checks."""

    CHECKS = [
        ("aigc_metadata", "AIGC 元数据已切除"),
        ("core_disagreement", "核心分歧已写"),
        ("dimensions_covered", "SAC 维度覆盖"),
        ("falsification", "证伪条件已写"),
        ("counter_case", "反方观点存在"),
        ("forbidden_patterns", "禁止模式未出现"),
        ("evidence_sources", "数据来源已标注"),
        ("no_first_person_system", "无第一人称系统指代"),
        ("no_self_evaluation", "无自我评价"),
        ("no_internal_methodology", "无内部方法论术语泄露"),
        ("ai_disclaimer", "无AI免责声明"),
        ("source_credibility", "数据来源可信度判断"),
        ("number_consistency", "数值百分比上下文"),
    ]

    def run(self, text: str, sac_id: str = "", required_dims: list[str] = None) -> dict:
        """Run all checks, return results."""
        items = []
        for check_id, check_name in self.CHECKS:
            method = getattr(self, f"_check_{check_id}", None)
            if method:
                result = method(text, sac_id=sac_id, required_dims=required_dims)
                items.append(result)
            else:
                items.append(ComplianceChecklistItem(check_id, check_name, True, "check not implemented"))

        passed = all(item.passed for item in items)
        return {"passed": passed, "items": [i.__dict__ for i in items]}

    def _check_aigc_metadata(self, text, **kw) -> ComplianceChecklistItem:
        """Check that no AIGC metadata block remains."""
        text_head = text[:800]
        patterns = [r"^---\\s*\nAIGC:", r"ContentProducer:", r"ReservedCode", r"^AIGC:\\s*\\S+"]
        found = [p for p in patterns if re.search(p, text_head, re.IGNORECASE)]
        return ComplianceChecklistItem(
            check_id="aigc_metadata",
            name="AIGC 元数据已切除",
            passed=len(found) == 0,
            detail=f"仍然发现: {', '.join(found)}" if found else "通过",
        )

    def _check_core_disagreement(self, text, **kw) -> ComplianceChecklistItem:
        # 2026-08-01 修复：原实现只检查第二个 "## " 章节前 300 字，
        # 但核心分歧常写在开篇决策门/【证伪与共识】段（无 "## " 前缀），
        # 导致报告明明写了分歧仍被误判。改为全文检测关键词。
        has = any(m in text for m in ["核心分歧", "分歧", "共识", "不同于", "市场认为", "核心矛盾"])
        return ComplianceChecklistItem(
            check_id="core_disagreement",
            name="核心分歧已写",
            passed=has,
            detail=("检测到" if has else "未检测到核心分歧表述"),
        )

    def _check_dimensions_covered(self, text, **kw) -> ComplianceChecklistItem:
        required_dims = kw.get("required_dims", [])
        if not required_dims:
            return ComplianceChecklistItem("dimensions_covered", "SAC 维度覆盖", True, "无 required_dims 约束")
        titles = [s.split("\n")[0].strip().lower() for s in text.split("\n## ")[1:]]
        missing = [d for d in required_dims if not any(d.lower() in t for t in titles)]
        return ComplianceChecklistItem(
            check_id="dimensions_covered",
            name="SAC 维度覆盖",
            passed=len(missing) == 0,
            detail=f"缺少: {', '.join(missing)}" if missing else f"{len(required_dims)} 维度全部覆盖",
        )

    def _check_falsification(self, text, **kw) -> ComplianceChecklistItem:
        has = any(m in text for m in ["如果", "假设", "证伪", "条件", "如果...那么"])
        return ComplianceChecklistItem(
            check_id="falsification", name="证伪条件已写", passed=has, detail="检测到" if has else "未检测到证伪条件"
        )

    def _check_counter_case(self, text, **kw) -> ComplianceChecklistItem:
        has = any(m in text for m in ["反方", "反对", "不同观点", "另一方", "批评者", "看空"])
        return ComplianceChecklistItem(
            check_id="counter_case", name="反方观点存在", passed=has, detail="检测到" if has else "未检测到反方观点"
        )

    def _check_forbidden_patterns(self, text, **kw) -> ComplianceChecklistItem:
        # P0 patterns from ai_fingerprints.py
        p0 = ["值得注意的是", "从某种程度上说", "综上所述", "不可否认的是"]
        found = [p for p in p0 if p in text]
        return ComplianceChecklistItem(
            check_id="forbidden_patterns",
            name="禁止模式未出现",
            passed=len(found) == 0,
            detail=f"发现: {', '.join(found)}" if found else "未发现 P0 禁止模式",
        )

    def _check_evidence_sources(self, text, **kw) -> ComplianceChecklistItem:
        count = len(re.findall(r"(来源[：:]|据[^。，]{2,15})", text))
        return ComplianceChecklistItem(
            check_id="evidence_sources",
            name="数据来源已标注",
            passed=count > 0,
            detail=f"{count} 处来源标注" if count > 0 else "无来源标注",
        )

    def _check_no_first_person_system(self, text, **kw) -> ComplianceChecklistItem:
        found = re.findall(r"(?<!\\w)本系统(?!\\w)", text)
        return ComplianceChecklistItem(
            check_id="no_first_person_system",
            name="无第一人称系统指代",
            passed=len(found) == 0,
            detail=f"发现 '本系统' {len(found)} 次" if found else "通过",
        )

    def _check_no_self_evaluation(self, text, **kw) -> ComplianceChecklistItem:
        found = re.findall(r"本报告已[达到经过][^。]*标准", text)
        return ComplianceChecklistItem(
            check_id="no_self_evaluation",
            name="无自我评价",
            passed=len(found) == 0,
            detail=f"发现: {', '.join(found)}" if found else "通过",
        )

    def _check_no_internal_methodology(self, text, **kw) -> ComplianceChecklistItem:
        tags = ["SAC", "MECE", "Writing Scaffold", "Research Protocol", "Serenity"]
        found = [t for t in tags if re.search(rf"\\b{t}\\b", text)]
        return ComplianceChecklistItem(
            check_id="no_internal_methodology",
            name="无内部方法论术语泄露",
            passed=len(found) == 0,
            detail=f"发现: {', '.join(found)}" if found else "通过",
        )

    def _check_ai_disclaimer(self, text, **kw) -> ComplianceChecklistItem:
        """Check that no AI disclaimer phrases appear in the report body."""
        # These phrases directly violate FP4 (Turing test)
        patterns = [
            "由AI生成",
            "AI生成",
            "本报告由AI",
            "本内容由AI",
            "AI分析",
            "以上内容由AI",
        ]
        found = [p for p in patterns if p in text]
        return ComplianceChecklistItem(
            check_id="ai_disclaimer",
            name="无AI免责声明",
            passed=len(found) == 0,
            detail=f"发现: {', '.join(found)}" if found else "通过",
        )

    def _check_source_credibility(self, text, **kw) -> ComplianceChecklistItem:
        """Check that sources have credibility signals (distinguish company data from estimates)."""
        # 官方/高可信度信号：公司公告/披露/年报/季报/招股书/监管文件/交易所公告
        OFFICIAL_SIGNALS = [
            "可信度", "公司公告", "官方数据", "公司披露", "公司披露",
            "年报", "三季报", "半年报", "一季报", "招股书",
            "年报披露", "季报披露", "半年报披露", "一季报披露",
            "监管公告", "交易所公告", "官方公告", "监管披露",
            "公司年报", "公司季报", "公司半年报", "公司一季报",
            "正式披露", "正式公告", "披露公告",
        ]
        has_credibility_signal = any(m in text for m in OFFICIAL_SIGNALS)
        has_estimation_signal = any(m in text for m in [
            "测算", "估算", "推测", "假设", "预测", "预期", "一致预期",
            "机构预测", "券商预测", "共识预测", "市场预期"
        ])
        # Only meaningful if there are data sources AND some credibility distinction
        source_count = len(re.findall(r"来源[：:]", text))
        if source_count < 2:
            return ComplianceChecklistItem("source_credibility", "数据来源可信度判断", True, "来源较少，无需分档")
        # PASS if both credibility and estimation signals exist (sources are differentiated)
        # Also pass if we have official company disclosures (high credibility)
        passed = (has_credibility_signal and has_estimation_signal) or has_credibility_signal
        detail = ""
        if passed:
            detail = f"检测到可信度分级 ({source_count} 处来源)"
        else:
            detail = f"未区分可信度等级 ({source_count} 处来源均无分级判断)"
        return ComplianceChecklistItem(
            check_id="source_credibility", name="数据来源可信度判断", passed=passed, detail=detail
        )

    def _check_number_consistency(self, text, **kw) -> ComplianceChecklistItem:
        """Check that numbers with % in report have a clear base reference nearby."""
        import re

        # Find percentage statements without clear base: "增长15%" without "同比增长" or "环比" nearby
        lines = text.split("\n")
        suspect = 0
        total_pct = 0
        for line in lines:
            pct_matches = re.findall(r"(\d+\.?\d*%)", line)
            if pct_matches:
                total_pct += len(pct_matches)
                # Check if the line has context words
                has_context = any(
                    w in line for w in ["同比", "环比", "占比", "毛利率", "净利率", "增长率", "增速", "率"]
                )
                if not has_context:
                    suspect += len(pct_matches)
        if total_pct == 0:
            return ComplianceChecklistItem("number_consistency", "数值百分比上下文", True, "无比分比数据")
        ratio = suspect / total_pct
        passed = ratio < 0.3
        detail = f"{total_pct} 处百分比, {suspect} 处缺少上下文" if suspect > 0 else f"{total_pct} 处百分比均有上下文"
        return ComplianceChecklistItem(
            check_id="number_consistency", name="数值百分比上下文", passed=passed, detail=detail
        )
