"""
Evidence Layer — 穿透式溯源系统。
从计算核 → 报告文本 → 导出文件，全链路追踪每个数值的来源。

组件:
1. ClaimTracker: 从报告文本提取数值声明
2. XBRLAligner: 将计算值映射到 XBRL 标准标签
3. EvidenceLayer: 统一包装器
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from engine.irongate_v2.provenance import ProvenanceTracker


@dataclass
class NumericClaim:
    """报告中的数值声明"""

    text: str
    value: Optional[float] = None
    unit: str = ""
    context: str = ""
    verified: bool = False
    source_cell_id: Optional[str] = None


class ClaimTracker:
    """从报告文本提取并验证数值声明"""

    # 数值声明正则模式
    PATTERNS = [
        r"(?:营收|收入|利润|净利润|EPS|ROE|ROIC|WACC|增长率|增速|毛利率|净利率)"
        r".*?[\d,.]+[%亿元元股倍xX]",
        r"[\d,.]+[%亿元元股倍xX].*?(?:增长|下降|提升|下滑|扩张|收缩)",
        r"(?:目标价|公允价值|估值|合理价格)[\s:：]*[\d,.]+",
        r"(?:PE|PB|PS|EV/EBITDA|P/E|P/B)[\s:：]*[\d,.]+[xX倍]?",
        r"(?:IRR|MOIC|NPV|DSCR|ICR)[\s:：]*[\d,.]+",
    ]

    def extract_claims(self, text: str) -> list[NumericClaim]:
        """提取所有数值声明"""
        claims = []
        for pattern in self.PATTERNS:
            matches = re.finditer(pattern, text)
            for m in matches:
                claim = NumericClaim(text=m.group())
                # 尝试提取数值
                num_match = re.search(r"[\d,.]+", claim.text)
                if num_match:
                    try:
                        claim.value = float(num_match.group().replace(",", ""))
                    except ValueError:
                        pass
                claims.append(claim)
        return claims

    def validate_claims(
        self,
        claims: list[NumericClaim],
        provenance: ProvenanceTracker,
    ) -> list[NumericClaim]:
        """验证每个声明是否有溯源支持"""
        for claim in claims:
            if claim.value is not None:
                # 在 provenance 中查找匹配
                for cell_id, record in provenance._cells.items():
                    if isinstance(record.value, (int, float)):
                        if abs(record.value - claim.value) / max(abs(record.value), 1) < 0.01:
                            claim.verified = True
                            claim.source_cell_id = cell_id
                            break
        return claims


# XBRL 标准标签映射
XBRL_MAPPING = {
    "revenue": "gaap:Revenues",
    "net_income": "gaap:NetIncomeLoss",
    "total_assets": "gaap:Assets",
    "total_liabilities": "gaap:Liabilities",
    "equity": "gaap:StockholdersEquity",
    "operating_income": "gaap:OperatingIncomeLoss",
    "ebitda": "us-gaap:EBITDA",
    "cash": "gaap:CashAndCashEquivalentsAtCarryingValue",
    "receivables": "gaap:AccountsReceivableNetCurrent",
    "inventory": "gaap:InventoryNet",
    "ppe": "gaap:PropertyPlantAndEquipmentNet",
    "debt_current": "gaap:LongTermDebtCurrentPortion",
    "debt_noncurrent": "gaap:LongTermDebtNoncurrent",
    "capex": "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
    "depreciation": "us-gaap:DepreciationDepletionAndAmortization",
    "interest_expense": "us-gaap:InterestExpense",
    "income_tax": "us-gaap:IncomeTaxExpenseBenefit",
    "dividends": "us-gaap:PaymentsOfDividends",
    "shares_outstanding": "us-gaap:CommonStockSharesOutstanding",
}


class XBRLAligner:
    """将计算值映射到 XBRL 标准标签"""

    def align(self, computed_values: dict[str, Any]) -> dict[str, str]:
        """映射 engine 输出键到 XBRL 标准标签"""
        aligned = {}
        for key, value in computed_values.items():
            key_lower = key.lower()
            for pattern, xbrl_tag in XBRL_MAPPING.items():
                if pattern in key_lower:
                    aligned[key] = xbrl_tag
                    break
            else:
                aligned[key] = f"custom:{key}"
        return aligned

    def get_standard_tags(self) -> dict[str, str]:
        """返回所有标准标签"""
        return XBRL_MAPPING.copy()


class EvidenceLayer:
    """统一证据追踪层 — 包装计算→报告→导出全链路"""

    def __init__(self):
        self.provenance = ProvenanceTracker()
        self.claim_tracker = ClaimTracker()
        self.xbrl_aligner = XBRLAligner()

    def wrap_computation(
        self,
        engine_name: str,
        result: Any,
        assumptions: dict,
    ) -> None:
        """包装计算结果，记录溯源"""
        if hasattr(result, "fair_value_per_share"):
            self.provenance.record(
                f"{engine_name}.fair_value",
                result.fair_value_per_share,
                formula="equity / shares",
                inputs={"engine": engine_name},
            )
        if hasattr(result, "enterprise_value"):
            self.provenance.record(
                f"{engine_name}.ev",
                result.enterprise_value,
                formula="sum_pv_fcf + pv_terminal",
            )
        if hasattr(result, "fcff_for_dcf") and result.fcff_for_dcf:
            self.provenance.record(
                f"{engine_name}.fcff",
                result.fcff_for_dcf,
                formula="NOPAT + D&A - CapEx - ΔWC",
            )

    def wrap_section(self, section_text: str) -> list[NumericClaim]:
        """包装报告章节，提取并验证数值声明"""
        claims = self.claim_tracker.extract_claims(section_text)
        verified_claims = self.claim_tracker.validate_claims(claims, self.provenance)
        return verified_claims

    def generate_audit_trail(self) -> str:
        """生成完整审计报告"""
        return self.provenance.to_audit_report()

    def summary(self) -> dict:
        prov_summary = self.provenance.summary()
        return {
            "provenance": prov_summary,
            "xbrl_mapped": len(XBRL_MAPPING),
        }
