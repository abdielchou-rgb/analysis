"""
分部加总 (SOTP) 估值引擎 — 纯 Python 计算。
支持 PE / PS / EV-EBITDA / DCF 四种分部估值方法。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from engine.irongate import GateReport, IronGateEngine
from engine.precision import D, PreciseValuation, dto_float
from engine.schemas import SOTPAssumptions, SOTPSegment, ValuationMethod


@dataclass
class SOTPResult:
    """SOTP 估值结果"""

    segment_values: List[dict] = field(default_factory=list)
    # [{"name": "新能源", "method": "PE", "multiple": 25, "value": 500}, ...]

    total_segments_value: float = 0.0
    cash_and_equivalents: float = 0.0
    net_debt: float = 0.0
    non_core_assets: float = 0.0
    enterprise_value: float = 0.0
    equity_value: float = 0.0
    target_price: float = 0.0
    upside_pct: Optional[float] = None

    confidence: str = "medium"
    warnings: List[str] = field(default_factory=list)
    gate_report: Optional[GateReport] = None


class SOTPEngine:
    """分部加总估值引擎 — Decimal 精度"""

    def __init__(self, assumptions: SOTPAssumptions, skip_gates: bool = False) -> None:
        self.a = assumptions
        self.gate_report: Optional[GateReport] = None
        self.provenance = PreciseValuation()

        if not skip_gates:
            gate = IronGateEngine()
            self.gate_report = gate.validate_sotp(assumptions)
            if not self.gate_report.passed:
                errs = "; ".join(r.message for r in self.gate_report.errors)
                raise ValueError(f"IronGate SOTP 校验失败:\n{errs}")

    def run(self) -> SOTPResult:
        a = self.a
        result = SOTPResult(gate_report=self.gate_report)
        result.cash_and_equivalents = a.cash_and_equivalents
        result.net_debt = a.net_debt
        result.non_core_assets = a.non_core_assets

        # ── 分部估值 (Decimal) ──────────────────────────────────────────
        total_d = D(0)
        for seg in a.segments:
            value = self._value_segment(seg)
            value_d = D(value)
            total_d += value_d
            result.segment_values.append(
                {
                    "name": seg.name,
                    "method": seg.valuation_method.value,
                    "multiple": seg.peer_multiple,
                    "value": round(value, 2),
                    "revenue": seg.revenue,
                    "profit": seg.profit,
                    "description": seg.description,
                }
            )

        result.total_segments_value = dto_float(total_d)

        # ── 企业价值 → 股权价值 → 目标价 (Decimal) ─────────────────────
        result.enterprise_value = result.total_segments_value
        equity_d = total_d + D(a.cash_and_equivalents) - D(a.net_debt) + D(a.non_core_assets)
        result.equity_value = dto_float(equity_d)
        result.target_price = dto_float(equity_d / D(a.total_shares))

        self.provenance.set("sotp_total", result.total_segments_value, formula="Σ(segment values)")
        self.provenance.set("sotp_equity", result.equity_value, formula="EV + Cash - Debt + NonCore")
        self.provenance.set("sotp_target", result.target_price, formula="Equity / Shares")

        if a.current_price and a.current_price > 0:
            result.upside_pct = round((result.target_price / a.current_price - 1) * 100, 1)

        # ── 置信度 ──────────────────────────────────────────────────────
        if len(a.segments) == 1:
            result.confidence = "low"
            result.warnings.append("仅单一估值分部")
        elif any(s["value"] <= 0 for s in result.segment_values):
            result.confidence = "low"
            result.warnings.append("存在非正分部价值")
        else:
            values = [s["value"] for s in result.segment_values]
            max_v = max(values)
            min_v = min(values)
            if max_v > 0 and min_v / max_v < 0.01:
                result.confidence = "low"
                result.warnings.append("分部价值极度集中，权重失衡")

        return result

    @staticmethod
    def _value_segment(seg: SOTPSegment) -> float:
        """根据估值方法计算分部价值（亿元）"""
        method = seg.valuation_method

        if method == ValuationMethod.PE:
            return seg.profit * seg.peer_multiple

        elif method == ValuationMethod.PS:
            return seg.revenue * seg.peer_multiple

        elif method == ValuationMethod.EV_EBITDA:
            # EBITDA 估算：净利润 × 1.2（粗略近似）
            ebitda_est = seg.profit * 1.2 if seg.profit > 0 else seg.revenue * 0.15
            return ebitda_est * seg.peer_multiple

        elif method == ValuationMethod.DCF:
            # DCF 方法直接使用 peer_multiple 字段传入 DCF 估值结果
            return seg.peer_multiple

        return 0.0
