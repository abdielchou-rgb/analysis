"""
engine — 独立估值计算引擎（零内部依赖）

三大核心设计：
1. 意图与数值解耦：LLM 仅抽取 Pydantic Schema 假设，不参与四则运算
2. IronGate 预检网关：拦截逻辑倒错、极端估值异常
3. 可审计 Excel 动态生成：原生公式，非静态数字

Usage:
    from engine import DCFEngine, AuditExcelWriter
    from engine.schemas import DCFAssumptions

    assumptions = DCFAssumptions(**llm_json_output)
    result = DCFEngine(assumptions).run()
    AuditExcelWriter(dcf_assumptions=assumptions).export("output.xlsx")
"""

from engine.comparable_model import ComparableEngine, ComparableResult
from engine.dcf_model import DCFEngine, DCFResult
from engine.excel_writer import AuditExcelWriter
from engine.irongate import GateReport, GateResult, IronGateEngine
from engine.scenario_model import ScenarioEngine, ScenarioResult
from engine.schemas import (
    ComparableAssumptions,
    DCFAssumptions,
    ScenarioAssumptions,
    ScenarioDetail,
    SOTPAssumptions,
    SOTPSegment,
    ValuationMethod,
    ValuationResult,
)
from engine.sotp_model import SOTPEngine, SOTPResult

__all__ = [
    # Schemas
    "DCFAssumptions",
    "ComparableAssumptions",
    "ScenarioAssumptions",
    "ScenarioDetail",
    "SOTPAssumptions",
    "SOTPSegment",
    "ValuationMethod",
    "ValuationResult",
    # IronGate
    "IronGateEngine",
    "GateReport",
    "GateResult",
    # Engines
    "DCFEngine",
    "DCFResult",
    "ComparableEngine",
    "ComparableResult",
    "ScenarioEngine",
    "ScenarioResult",
    "SOTPEngine",
    "SOTPResult",
    # Excel
    "AuditExcelWriter",
]

__version__ = "1.0.0"
