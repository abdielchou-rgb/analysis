"""
IronGate 2.0 — 注册表与执行器。
三层依次执行: L1 → L2 → L3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GateSeverity(str, Enum):
    BLOCK = "block"  # L1: 管线阻断
    PRUNE = "prune"  # L2: 参数修正
    REPORT = "report"  # L3: 文本层报告


@dataclass
class GateVerdict:
    gate_id: str
    layer: str  # L1 / L2 / L3
    passed: bool
    severity: GateSeverity
    message: str
    param_key: Optional[str] = None
    suggested_default: Optional[float] = None
    rewrite_hint: Optional[str] = None


@dataclass
class GateV2Report:
    """IronGate 2.0 校验报告"""

    layer_results: dict[str, list[GateVerdict]] = field(default_factory=dict)
    blocked: bool = False
    pruned_params: dict[str, dict] = field(default_factory=dict)
    all_verdicts: list[GateVerdict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.blocked

    @property
    def errors(self) -> list[GateVerdict]:
        return [v for v in self.all_verdicts if not v.passed and v.severity == GateSeverity.BLOCK]

    @property
    def warnings(self) -> list[GateVerdict]:
        return [v for v in self.all_verdicts if not v.passed and v.severity != GateSeverity.BLOCK]

    def summary(self) -> str:
        lines = [f"IronGate V2: {'BLOCKED' if self.blocked else 'PASSED'}"]
        for layer, verdicts in self.layer_results.items():
            n_pass = sum(1 for v in verdicts if v.passed)
            n_fail = sum(1 for v in verdicts if not v.passed)
            lines.append(f"  {layer}: {n_pass} pass, {n_fail} fail")
        if self.pruned_params:
            lines.append(f"  Pruned: {list(self.pruned_params.keys())}")
        return "\n".join(lines)


class IronGateV2:
    """IronGate 2.0 — 三层分级校验执行器"""

    def __init__(self):
        from engine.irongate_v2.layers import L1HardStop, L2EconomicPhysics, L3TextNumeric

        self.l1 = L1HardStop()
        self.l2 = L2EconomicPhysics()
        self.l3 = L3TextNumeric()

    def validate(
        self,
        assumptions: dict[str, Any],
        report_text: str = "",
    ) -> GateV2Report:
        report = GateV2Report()

        # L1: Hard stops — 任一失败则阻断
        l1_results = self.l1.validate(assumptions)
        report.layer_results["L1"] = l1_results
        report.all_verdicts.extend(l1_results)
        if any(not v.passed for v in l1_results if v.severity == GateSeverity.BLOCK):
            report.blocked = True
            return report

        # L2: Economic physics — 修正参数后继续
        l2_results = self.l2.validate(assumptions)
        report.layer_results["L2"] = l2_results
        report.all_verdicts.extend(l2_results)
        pruned = self.l2.apply_prunes(assumptions, l2_results)
        report.pruned_params = pruned

        # L3: Text-numeric contract — 报告给文本层
        if report_text:
            l3_results = self.l3.validate(assumptions, report_text)
            report.layer_results["L3"] = l3_results
            report.all_verdicts.extend(l3_results)

        return report
