"""审计辅助工具包 — 收入确认规则(IFRS15/ASC606) + 异常检测 + 底稿骨架

用法：
  from core.audit_toolkit import RevenueRecognition, AnomalyDetector, AuditWorkpaper

收入确认风险判断（IFRS15五步法）：
  1. 识别客户合同
  2. 识别履约义务
  3. 确定交易价格
  4. 分摊交易价格
  5. 确认收入

常见红旗信号：
  - 收入增速远高于行业/应收账款增速
  - 四季度收入占比异常偏高
  - 关联交易收入占比高
  - 收入确认政策变更
"""
from __future__ import annotations
import json, re, logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.audit_toolkit")


@dataclass
class RevenueRiskFlag:
    flag: str
    severity: str  # high / medium / low
    detail: str
    ifrs_standard: str


class RevenueRecognition:
    """IFRS15 / ASC606 收入确认五步法检查。"""

    RED_FLAGS = [
        ("收入增速 > 应收增速 2倍", "high", "收入可能被提前确认", "IFRS15.9"),
        ("Q4收入占比 > 40%", "medium", "四季度集中确认需关注", "IFRS15.B86"),
        ("关联交易 > 营收20%", "medium", "关联交易真实性存疑", "IFRS15.BC305"),
        ("收入确认政策变更", "high", "政策变更可能为调节利润", "IAS8"),
        ("毛利率与同行偏差 > 10pp", "medium", "毛利率异常需核查", "IFRS15.50"),
        ("营收增长但经营性现金流下降", "high", "利润质量存疑", "IAS7"),
    ]

    def check(self, report_text: str) -> list[RevenueRiskFlag]:
        flags = []
        text_lower = report_text.lower()
        for flag, sev, detail, standard in self.RED_FLAGS:
            keywords = flag.split(">")[0].strip() if ">" in flag else flag
            # 简单关键词匹配，后续可升级为 NLP
            if any(kw.lower() in text_lower for kw in ["收入增速", "应收", "q4", "四季度",
                                                         "关联交易", "收入确认", "毛利率异常"]):
                flags.append(RevenueRiskFlag(flag=flag, severity=sev, detail=detail,
                                             ifrs_standard=standard))
        return flags[:5]

    def to_report(self, flags: list[RevenueRiskFlag]) -> str:
        lines = ["=== 收入确认风险检查（IFRS15/ASC606）==="]
        if not flags:
            lines.append("  未发现明显红旗信号")
        else:
            for f in flags:
                lines.append(f"  [{f.severity.upper()}] {f.flag}")
                lines.append(f"    {f.detail}（{f.ifrs_standard}）")
        return "\n".join(lines)


class AuditWorkpaper:
    """审计底稿骨架模板。"""

    SECTIONS = [
        "一、审计概况",
        "  1.1 审计范围与方法",
        "  1.2 重要性水平确定",
        "二、风险评估",
        "  2.1 固有风险评估",
        "  2.2 控制风险评估",
        "三、实质性程序",
        "  3.1 收入测试",
        "  3.2 应收账款函证",
        "  3.3 存货盘点",
        "  3.4 截止性测试",
        "四、结论与建议",
    ]

    def generate(self, company: str, year: str) -> str:
        lines = [f"审计底稿 - {company} - {year}会计年度", "=" * 40]
        for s in self.SECTIONS:
            lines.append(f"\n{s}")
            lines.append("  [待填写]")
        lines.append("\n---")
        lines.append("编制人: [姓名]  复核人: [姓名]  日期: [日期]")
        return "\n".join(lines)


class AnomalyDetector:
    """财务异常检测。"""
    def check_ratio_consistency(self, ratios: dict) -> list[str]:
        issues = []
        # 毛利率波动检查
        margins = [ratios.get(f"margin_{y}") for y in ["2022","2023","2024"] if ratios.get(f"margin_{y}")]
        if len(margins) >= 3:
            volatility = max(margins) - min(margins)
            if volatility > 0.10:
                issues.append(f"毛利率波动 {volatility:.1%} > 10%（可能异常）")
        # 应收/收入比检查
        ar_ratio = ratios.get("ar_to_revenue", 0)
        if ar_ratio and ar_ratio > 0.5:
            issues.append(f"应收/收入比 {ar_ratio:.0%} > 50%（回款风险）")
        return issues
