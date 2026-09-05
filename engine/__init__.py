"""
engine — 独立估值计算引擎（零内部依赖）

核心设计：
1. 意图与数值解耦：LLM 仅抽取 Pydantic Schema 假设，不参与四则运算
2. IronGate 预检网关：拦截逻辑倒错、极端估值异常
3. 三表联动引擎：IS→BS→CF 单向推演，财务不变量校验
4. Decimal 精度层：全链路确定性计算
5. 多方法估值：DCF/Comps/Scenario/SOTP + 20+ 方法目录
6. 可审计 Excel 动态生成：原生公式，非静态数字

Usage:
    from engine import DCFEngine, ThreeStatementEngine, AuditExcelWriter
    from engine.schemas import DCFAssumptions
    from engine.three_statement import ThreeStatementAssumptions

    assumptions = DCFAssumptions(**llm_json_output)
    result = DCFEngine(assumptions).run()
    AuditExcelWriter(dcf_assumptions=assumptions).export("output.xlsx")
"""

# Core schemas
from engine.comparable_model import ComparableEngine, ComparableResult

# Core engines
from engine.dcf_model import DCFEngine, DCFResult

# P1: Debate
from engine.debate import (
    AgentArgument,
    DebateOrchestrator,
    DebateResult,
    DevilAdvocateAgent,
)

# Excel
from engine.excel_writer import AuditExcelWriter

# P1: FCFF Path + Market-Implied + Diagnostics
from engine.fcff_path import (
    Diagnostic,
    DiagnosticEngine,
    DiagnosticLevel,
    DiagnosticReport,
    FCFFPath,
    FCFFPathEngine,
    FCFFPathResult,
    MarketImpliedResult,
    MarketImpliedSolver,
)

# IronGate
from engine.irongate import GateReport, GateResult, IronGateEngine

# P2: Knowledge + Memory + Scenarios
from engine.knowledge import (
    DamodaranEntry,
    DamodaranRAG,
    DamodaranRAGQuery,
    DamodaranRAGResult,
    DeepMergeScenarioEngine,
    TickerMemory,
    TickerMemoryStore,
    TornadoEngine,
    TornadoResult,
)

# P3: MCP + Docker
from engine.mcp_tools import (
    MCPEngine,
    MCPTool,
    MCPToolResult,
    generate_dockerfiles,
)

# P2: Monte Carlo
from engine.monte_carlo import (
    BoxMullerTransform,
    CorrelationEngine,
    MonteCarloAssumptions,
    MonteCarloEngine,
    MonteCarloResult,
)

# P3: Orchestrator + Report
from engine.orchestrator import (
    IBGradeOrchestrator,
    PipelineResult,
    PipelineStep,
    ReportPipeline,
    ResearchReport,
    StepResult,
)

# P1: Precision
from engine.precision import D, Decimal, PreciseValuation, ddiv, dfmt, dmul, dsum

# P1: Regime-Conditional DCF + Synthetic Peers
from engine.regime import (
    EconomicRegime,
    RegimeAssumptions,
    RegimeDCFEngine,
    RegimeDCFResult,
    RegimeProfile,
    SyntheticPeerAssumptions,
    SyntheticPeerEngine,
    SyntheticPeerResult,
)
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

# Phase 1: Unified schemas + precision
from engine.schemas_v2 import (
    CellProvenance,
    DCFAssumptionsV2,
    MonteCarloAssumptionsV2,
    ReverseDCFAssumptions,
    SensitivitySurface,
    ThreeStatementAssumptionsV2,
    ValuationResultV2,
)
from engine.sotp_model import SOTPEngine, SOTPResult

# Three-statement
from engine.three_statement import (
    BalanceSheet,
    CashFlowStatement,
    FreeCashFlowResult,
    IncomeStatement,
    ThreeStatementAssumptions,
    ThreeStatementEngine,
    ThreeStatementResult,
)

# P2: Valuation Catalog + Quality Scoring
from engine.valuation_catalog import (
    IndustryType,
    IndustryValuationAssumptions,
    IndustryValuationEngine,
    IndustryValuationResult,
    ValuationCatalog,
    ValuationCategory,
)

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
    # Core engines
    "DCFEngine",
    "DCFResult",
    "ComparableEngine",
    "ComparableResult",
    "ScenarioEngine",
    "ScenarioResult",
    "SOTPEngine",
    "SOTPResult",
    # Three-statement
    "ThreeStatementAssumptions",
    "ThreeStatementEngine",
    "ThreeStatementResult",
    "IncomeStatement",
    "BalanceSheet",
    "CashFlowStatement",
    "FreeCashFlowResult",
    # P1: Precision
    "D",
    "Decimal",
    "PreciseValuation",
    "ddiv",
    "dfmt",
    "dmul",
    "dsum",
    # P1: Regime
    "EconomicRegime",
    "RegimeAssumptions",
    "RegimeDCFEngine",
    "RegimeDCFResult",
    "RegimeProfile",
    "SyntheticPeerAssumptions",
    "SyntheticPeerEngine",
    "SyntheticPeerResult",
    # P1: FCFF + Diagnostics
    "Diagnostic",
    "DiagnosticEngine",
    "DiagnosticLevel",
    "DiagnosticReport",
    "FCFFPath",
    "FCFFPathEngine",
    "FCFFPathResult",
    "MarketImpliedResult",
    "MarketImpliedSolver",
    # P2: Monte Carlo
    "BoxMullerTransform",
    "CorrelationEngine",
    "MonteCarloAssumptions",
    "MonteCarloEngine",
    "MonteCarloResult",
    # P2: Valuation Catalog
    "ValuationCatalog",
    "IndustryType",
    "IndustryValuationEngine",
    "IndustryValuationAssumptions",
    "IndustryValuationResult",
    "ValuationCategory",
    # P2: Knowledge
    "DamodaranEntry",
    "DamodaranRAG",
    "DamodaranRAGQuery",
    "DamodaranRAGResult",
    "DeepMergeScenarioEngine",
    "TickerMemory",
    "TickerMemoryStore",
    "TornadoEngine",
    "TornadoResult",
    # P1: Debate
    "AgentArgument",
    "DebateOrchestrator",
    "DebateResult",
    "DevilAdvocateAgent",
    # P3: Orchestrator
    "IBGradeOrchestrator",
    "PipelineResult",
    "PipelineStep",
    "ReportPipeline",
    "ResearchReport",
    "StepResult",
    # P3: MCP
    "MCPEngine",
    "MCPTool",
    "MCPToolResult",
    "generate_dockerfiles",
    # Excel
    "AuditExcelWriter",
    # Phase 1: Unified schemas + precision
    "DCFAssumptionsV2",
    "ThreeStatementAssumptionsV2",
    "ReverseDCFAssumptions",
    "MonteCarloAssumptionsV2",
    "SensitivitySurface",
    "CellProvenance",
    "ValuationResultV2",
]

__version__ = "3.0.0"
