"""
可比公司估值引擎 — 纯 Python 计算。
支持 PE / PB / PS / EV/EBITDA 多倍数隐含估值。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.irongate import GateReport, IronGateEngine
from engine.schemas import ComparableAssumptions


@dataclass
class ComparableResult:
    """可比估值结果"""

    implied_prices: Dict[str, float] = field(default_factory=dict)
    # {method: implied_price}，如 {"PE": 45.2, "PB": 38.1}

    peer_stats: Dict[str, dict] = field(default_factory=dict)
    # {metric: {mean, median, min, max, count}}

    target_price: float = 0.0
    # 综合目标价（各方法均值）

    confidence: str = "medium"
    warnings: List[str] = field(default_factory=list)
    gate_report: Optional[GateReport] = None


class ComparableEngine:
    """可比公司估值引擎"""

    def __init__(self, assumptions: ComparableAssumptions, skip_gates: bool = False) -> None:
        self.a = assumptions
        self.gate_report: Optional[GateReport] = None

        if not skip_gates:
            gate = IronGateEngine()
            self.gate_report = gate.validate_comparable(assumptions)
            if not self.gate_report.passed:
                errs = "; ".join(r.message for r in self.gate_report.errors)
                raise ValueError(f"IronGate Comparable 校验失败:\n{errs}")

    def run(self) -> ComparableResult:
        a = self.a
        result = ComparableResult(gate_report=self.gate_report)

        # ── PE 隐含估值 ─────────────────────────────────────────────────
        pe_stats = self._calc_stats(a.peer_pe_ratios)
        result.peer_stats["PE"] = pe_stats
        if a.company_eps > 0 and pe_stats["mean"] > 0:
            result.implied_prices["PE"] = round(a.company_eps * pe_stats["mean"], 2)

        # ── PB 隐含估值 ─────────────────────────────────────────────────
        if a.peer_pb_ratios and len(a.peer_pb_ratios) >= 2:
            pb_stats = self._calc_stats(a.peer_pb_ratios)
            result.peer_stats["PB"] = pb_stats
            if a.company_bvps > 0 and pb_stats["mean"] > 0:
                result.implied_prices["PB"] = round(a.company_bvps * pb_stats["mean"], 2)

        # ── PS 隐含估值 ─────────────────────────────────────────────────
        if a.peer_ps_ratios and len(a.peer_ps_ratios) >= 2:
            ps_stats = self._calc_stats(a.peer_ps_ratios)
            result.peer_stats["PS"] = ps_stats
            if a.company_revenue_per_share > 0 and ps_stats["mean"] > 0:
                result.implied_prices["PS"] = round(a.company_revenue_per_share * ps_stats["mean"], 2)

        # ── EV/EBITDA 隐含估值 ──────────────────────────────────────────
        if a.peer_ev_ebitda and len(a.peer_ev_ebitda) >= 2:
            ebitda_stats = self._calc_stats(a.peer_ev_ebitda)
            result.peer_stats["EV/EBITDA"] = ebitda_stats
            if a.company_ebitda_per_share > 0 and ebitda_stats["mean"] > 0:
                result.implied_prices["EV/EBITDA"] = round(a.company_ebitda_per_share * ebitda_stats["mean"], 2)

        # ── 综合目标价 ──────────────────────────────────────────────────
        if result.implied_prices:
            values = list(result.implied_prices.values())
            result.target_price = round(sum(values) / len(values), 2)
        else:
            result.warnings.append("无有效可比估值结果")

        # ── 置信度 ──────────────────────────────────────────────────────
        if len(result.implied_prices) >= 3:
            prices = list(result.implied_prices.values())
            spread = (max(prices) - min(prices)) / min(prices) if min(prices) > 0 else 0
            if spread > 0.30:
                result.confidence = "low"
                result.warnings.append(f"多方法估值差异 {spread:.0%} > 30%")
            elif spread > 0.15:
                result.confidence = "medium"
            else:
                result.confidence = "high"
        else:
            result.confidence = "low"
            result.warnings.append("仅有单一估值方法")

        return result

    @staticmethod
    def _calc_stats(values: List[float]) -> dict:
        s = sorted(values)
        n = len(s)
        mean = sum(s) / n
        median = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
        return {
            "mean": round(mean, 2),
            "median": round(median, 2),
            "min": round(s[0], 2),
            "max": round(s[-1], 2),
            "count": n,
        }
