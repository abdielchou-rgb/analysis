# Architecture Restructure Plan — 2hao-analyst

**Version**: 1.0 | **Date**: 2026-09-06
**Scope**: Consolidate `engine/` + `core/` into unified 4-subsystem architecture

---

## 0. Problem Statement

The repository contains two parallel, incomplete systems:

| System | Location | Reality |
|--------|----------|---------|
| `engine/` | `engine/orchestrator.py`, `engine/dcf_model.py`, `engine/three_statement.py` | Well-designed Pydantic schemas, clean interfaces, 28 IronGate pre-checks — but orchestrator is **ALL STUBS**, `precision.py` unused, Decimal layer decorative |
| `core/` + `pipeline/` | `core/compute/valuation/`, `pipeline/e2e_orchestrator.py`, `pipeline/iron_gate.py` | Real production system: E2EOrchestratorV2 (2645 lines), 102 post-generation checks, section_writer, style compiler — but float precision, no cell-level provenance, flat IronGate |

Key duplication: two DCF models (`engine/dcf_model.py` vs `core/compute/valuation/dcf.py`), two three-statement models, two IronGate systems.

## 1. Target Architecture — 4 Subsystems

```
┌─────────────────────────────────────────────────────────────────────┐
│                        E2EOrchestratorV2                           │
│  (pipeline/e2e_orchestrator.py — preserved, adapted)               │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│ Intent Engine│ Numerical    │ IronGate 2.0 │ Evidence Layer        │
│              │ Compute      │              │                       │
│ • IssueTree  │ • ThreeStmt  │ • L1: Hard   │ • CellProvenance     │
│ • ReverseDCF │   DAG        │   Stop       │ • XBRLAlignment      │
│ • Expectation│ • Circular   │ • L2: Econ   │ • AuditTrail         │
│   Investing  │   Resolver   │   Physics    │                       │
│              │ • Sensitivity│ • L3: Text   │                       │
│              │ • MonteCarlo │   Contract   │                       │
└──────────────┴──────────────┴──────────────┴───────────────────────┘
         ↓                    ↓              ↓              ↓
    engine/schemas.py   engine/precision  pipeline/iron   core/evidence.py
    core/intent_*       core/compute/*    _gate.py (v2)   core/data_provenance
```

## 2. Consolidation Strategy

**Principle**: Strangler-fig migration. Never delete `core/` or `pipeline/` working code. Adapt `engine/` to wire into it.

```
engine/  (thin wrappers + Pydantic schemas + Decimal precision)
    ↓ imports
core/compute/valuation/ (real implementations, Decimal-upgraded)
    ↓ called by
pipeline/e2e_orchestrator.py (preserved entry point)
```

The `engine/` package becomes the **public API surface** (schemas, interfaces, entry points). The `core/compute/` package becomes the **implementation** (actual math). The `pipeline/` package remains the **orchestration layer**.

---

## Phase 1: Precision + Schema Consolidation (Foundation)

**Goal**: Wire `engine/precision.py` Decimal layer into the compute core; eliminate duplicate schemas.

### 1.1 Create `engine/precision_registry.py`

Central registry that all compute modules import from. Enables global Decimal context.

```python
# engine/precision_registry.py
"""
Global Decimal precision registry — all compute modules MUST import D/dsum/dmul/ddiv from here.
"""
from engine.precision import D, dsum, dmul, ddiv, dpct, dfmt, dto_float, PreciseValuation

__all__ = ["D", "dsum", "dmul", "ddiv", "dpct", "dfmt", "dto_float", "PreciseValuation"]
```

### 1.2 Create `engine/schemas_v2.py` — Unified Schema Layer

Merge `engine/schemas.py` (Pydantic, clean) with the implicit schemas in `core/compute/valuation/dcf.py` (function params). One source of truth.

```python
# engine/schemas_v2.py
"""
Unified Pydantic schemas — replaces engine/schemas.py.
All compute modules read assumptions from these schemas.
"""

class DCFAssumptionsV2(BaseModel):
    """Consolidated DCF assumptions — merges engine/schemas.py DCFAssumptions
    with core/compute/valuation/dcf.py function parameters."""
    # Keep ALL fields from existing DCFAssumptions (validated)
    # Add fields from core/compute/valuation/dcf.py:
    terminal_method: Literal["ggm", "exit_multiple"] = "ggm"
    exit_ebitda_multiple: float = 10.0
    # Ensure current_price is present for upside calculation
    # Decimal-compatible: all float fields, converted at compute time

class ThreeStatementAssumptionsV2(BaseModel):
    """Consolidated three-statement assumptions.
    Merges engine/three_statement.py ThreeStatementAssumptions (dataclass)
    with core/compute/three_statement.py dict input."""

class ReverseDCFAssumptions(BaseModel):
    """NEW: Reverse-DCF input — from current_price solve for implied growth."""
    ticker: str
    company_name: str
    current_price: float = Field(..., gt=0)
    shares_outstanding: float = Field(..., gt=0)
    net_debt: float = 0.0
    fcf_ttm: float | None = None
    revenue_ttm: float | None = None
    wacc: float = 0.10
    tax_rate: float = 0.25

class MonteCarloAssumptionsV2(BaseModel):
    """Consolidated MC assumptions — merges engine/monte_carlo.py and core/compute/valuation/monte_carlo.py."""

class SensitivityAssumptions(BaseModel):
    """NEW: Sensitivity surface parameters."""
    base_wacc: float
    base_terminal_growth: float
    wacc_range_pp: float = 2.0  # ±2 percentage points
    growth_range_pp: float = 1.0  # ±1 percentage point
    steps: int = 5
```

### 1.3 Modify `engine/dcf_model.py` — Import from precision

Replace `float` arithmetic with `D()` calls throughout.

```python
# Before (line 83-104):
curr_rev = a.base_revenue  # float
curr_rev = curr_rev * (1 + a.revenue_growth_rates[i])  # float math

# After:
from engine.precision import D
curr_rev = D(a.base_revenue)  # Decimal
curr_rev = curr_rev * (1 + D(a.revenue_growth_rates[i]))  # Decimal math
```

**Files to modify in `engine/`**:
- `engine/dcf_model.py` — all arithmetic → Decimal
- `engine/three_statement.py` — all arithmetic → Decimal
- `engine/comparable_model.py` — all arithmetic → Decimal
- `engine/scenario_model.py` — all arithmetic → Decimal
- `engine/sotp_model.py` — all arithmetic → Decimal
- `engine/monte_carlo.py` — keep numpy for simulation (float), convert at boundary

**Files to create**:
- `engine/precision_registry.py` — centralized import
- `engine/schemas_v2.py` — unified schemas

### 1.4 Modify `core/compute/valuation/dcf.py` — Bridge to engine

Add thin adapter that wraps `core/compute/valuation/dcf.py` to accept `DCFAssumptionsV2` and return Decimal-precise results.

```python
# core/compute/valuation/dcf_bridge.py (NEW)
from engine.schemas_v2 import DCFAssumptionsV2
from engine.precision import D, PreciseValuation
from core.compute.valuation.dcf import compute_dcf

def compute_dcf_v2(assumptions: DCFAssumptionsV2) -> "DCFResult":
    """Bridge: accepts unified schema, calls existing compute_dcf, wraps result with provenance."""
    # Convert schema to existing function params
    # Call compute_dcf
    # Wrap result in PreciseValuation provenance tracker
```

### 1.5 Tests

```
tests/test_phase1_precision.py
  - test_decimal_dcf_basic: DCF with Decimal produces same result as float (within tolerance)
  - test_decimal_three_statement: Three-statement invariant checks pass with Decimal
  - test_schema_v2_backward_compat: DCFAssumptionsV2 accepts all existing DCFAssumptions inputs
  - test_reverse_dcf_schema: ReverseDCFAssumptions validates correctly
  - test_provenance_tracking: PreciseValuation records source/formula for every cell
```

### 1.6 Acceptance Criteria

- [ ] All `engine/` compute modules use `D()` for arithmetic
- [ ] `engine/schemas_v2.py` covers all fields from both systems
- [ ] Existing `engine/dcf_model.py` tests pass unchanged (float results within 1e-10 of Decimal)
- [ ] `pipeline/compute_engine.py` can import from `engine/schemas_v2.py`
- [ ] `core/compute/valuation/dcf.py` still works standalone (no breaking changes)

---

## Phase 2: Wire Orchestrator + Reverse-DCF + Intent Engine

**Goal**: Replace stubs in `engine/orchestrator.py` with real computation calls; add Reverse-DCF solver; build Intent Engine skeleton.

### 2.1 Modify `engine/orchestrator.py` — Wire to real computation

Replace the 16 stub methods with actual calls to `engine/` compute modules.

```python
class IBGradeOrchestrator:
    def _step_income_statement(self, a: Dict) -> Dict:
        """Wire to engine.three_statement.ThreeStatementEngine"""
        from engine.three_statement import ThreeStatementAssumptions, ThreeStatementEngine
        assumptions = ThreeStatementAssumptions(**self._extract_ts_params(a))
        result = ThreeStatementEngine(assumptions, skip_gates=False).run()
        return {"status": "income_statement_built", "result": result}

    def _step_dcf(self, a: Dict) -> Dict:
        """Wire to engine.dcf_model.DCFEngine"""
        from engine.dcf_model import DCFEngine
        from engine.schemas_v2 import DCFAssumptionsV2
        assumptions = DCFAssumptionsV2(**a)
        result = DCFEngine(assumptions).run()
        return {"status": "dcf_computed", "result": result}

    def _step_monte_carlo(self, a: Dict) -> Dict:
        """Wire to engine.monte_carlo.MonteCarloEngine"""
        from engine.monte_carlo import MonteCarloEngine, MonteCarloAssumptions
        assumptions = MonteCarloAssumptions(**self._extract_mc_params(a))
        result = MonteCarloEngine(assumptions).run()
        return {"status": "monte_carlo_completed", "result": result}

    def _step_sensitivity(self, a: Dict) -> Dict:
        """Wire to sensitivity surface computation"""
        from engine.dcf_model import DCFEngine
        dcf_result = self.results.get("09_dcf", {}).output
        if dcf_result and "result" in dcf_result:
            # Sensitivity already computed in DCFEngine.run()
            return {"status": "sensitivity_computed", "result": dcf_result["result"].sensitivity_matrix}
        return {"status": "sensitivity_skipped"}

    def _step_comps(self, a: Dict) -> Dict:
        """Wire to engine.comparable_model.ComparableEngine"""
        from engine.comparable_model import ComparableEngine
        from engine.schemas_v2 import ComparableAssumptionsV2
        assumptions = ComparableAssumptionsV2(**self._extract_comp_params(a))
        result = ComparableEngine(assumptions).run()
        return {"status": "comps_computed", "result": result}

    # ... remaining steps wired similarly
```

### 2.2 Create `engine/reverse_dcf.py` — Enhanced Reverse-DCF Solver

Build on existing `core/compute/valuation/reverse_dcf.py` with multi-variable solver.

```python
# engine/reverse_dcf.py
"""
Reverse-DCF Solver — from current_price, solve for implied growth/ROIC/margin.

Enhances core/compute/valuation/reverse_dcf.py with:
1. Multi-variable solver (implied growth + implied margin simultaneously)
2. Scenario decomposition (what % of price is growth vs value vs quality)
3. Expectations gap analysis (our estimate vs market implied)
"""

from engine.precision import D
from engine.schemas_v2 import ReverseDCFAssumptions

class ReverseDCFSolver:
    """Solve for market-implied assumptions from current price."""

    def __init__(self, assumptions: ReverseDCFAssumptions):
        self.a = assumptions

    def solve_implied_growth(self) -> dict:
        """Single-variable: solve for g given EV/WACC/FCF."""
        # Use existing core logic but with Decimal precision
        from core.compute.valuation.reverse_dcf import ReverseDCF
        rd = ReverseDCF(
            market_cap=D(self.a.current_price) * D(self.a.shares_outstanding),
            net_debt=D(self.a.net_debt),
            fcf_ttm=D(self.a.fcf_ttm) if self.a.fcf_ttm else None,
            revenue_ttm=D(self.a.revenue_ttm) if self.a.revenue_ttm else None,
            wacc=D(self.a.wacc),
        )
        return rd.solve_implied_growth()

    def solve_implied_margin_and_growth(self) -> dict:
        """Two-variable: solve for (FCF margin, growth) simultaneously.
        Uses Newton-Raphson on the DCF identity."""
        # System of equations:
        # EV = FCF_ttm * (1+g) / (WACC - g)
        # FCF_ttm = revenue_ttm * margin
        # → Solve for (margin, g) given EV
        ...

    def expectation_gap_analysis(self, our_growth: float, our_margin: float) -> dict:
        """Compare our assumptions vs market-implied."""
        implied = self.solve_implied_growth()
        return {
            "our_growth_pct": our_growth * 100,
            "implied_growth_pct": implied.get("implied_growth_pct", 0),
            "gap_pct": our_growth * 100 - implied.get("implied_growth_pct", 0),
            "interpretation": self._interpret_gap(our_growth, implied),
        }
```

### 2.3 Create `engine/intent_engine.py` — Intent Engine Skeleton

MECE Issue Tree + Expectations Investing framework.

```python
# engine/intent_engine.py
"""
Intent Engine — structured decomposition of research intent.

Components:
1. MECE Issue Tree: recursive decomposition of investment question
2. Expectations Investing: map price → implied assumptions → gap
3. Research Plan Generator: Issue Tree → data needs → computation steps
"""

from enum import Enum
from dataclasses import dataclass, field

class IssueNodeType(str, Enum):
    THESIS = "thesis"
    HYPOTHESIS = "hypothesis"
    DATA_NEED = "data_need"
    FALSIFIER = "falsifier"

@dataclass
class IssueNode:
    id: str
    label: str
    node_type: IssueNodeType
    children: list["IssueNode"] = field(default_factory=list)
    data_source: str | None = None
    status: str = "pending"  # pending / confirmed / refuted / partial

class MECEIssueTree:
    """MECE Issue Tree builder — decompose any investment question."""

    def __init__(self, thesis: str, company_context: dict):
        self.thesis = thesis
        self.context = company_context
        self.root = IssueNode(id="root", label=thesis, node_type=IssueNodeType.THESIS)

    def decompose(self, max_depth: int = 3) -> IssueNode:
        """Recursively decompose thesis into testable hypotheses."""
        # Pre-built templates for common patterns:
        # - Revenue growth → volume × price × mix
        # - Margin expansion → scale + operating leverage
        # - Multiple re-rating → risk premium + growth premium
        # Template selection based on company_context["biz_model"]
        ...

    def to_research_plan(self) -> dict:
        """Convert Issue Tree to ordered research plan with data needs."""
        ...

class ExpectationsInvesting:
    """Map stock price → implied assumptions → gap analysis."""

    def analyze(self, current_price: float, reverse_dcf_result: dict, our_assumptions: dict) -> dict:
        """Three-step analysis:
        1. What does the market price assume? (reverse DCF)
        2. What do we assume? (our model)
        3. What's the gap and what would change it?
        """
        ...
```

### 2.4 Wire Intent Engine into `engine/orchestrator.py`

Add Step 00 (intent decomposition) before the 16-step pipeline.

```python
class IBGradeOrchestrator:
    def __init__(self):
        self.steps = [PipelineStep.STEP_00_INTENT] + list(PipelineStep)
        # ...

    def _step_intent(self, a: Dict) -> Dict:
        """Step 00: Decompose research intent into MECE Issue Tree."""
        from engine.intent_engine import MECEIssueTree, ExpectationsInvesting
        tree = MECEIssueTree(
            thesis=a.get("research_question", f"分析 {a.get('company_name', '')}"),
            company_context=a,
        )
        root = tree.decompose()
        plan = tree.to_research_plan()
        return {"status": "intent_decomposed", "issue_tree": root, "research_plan": plan}
```

### 2.5 Tests

```
tests/test_phase2_orchestrator.py
  - test_orchestrator_step_01_wired: Step 01 calls ThreeStatementEngine
  - test_orchestrator_step_09_wired: Step 09 calls DCFEngine
  - test_orchestrator_full_16_steps: All 16 steps execute without stubs
  - test_orchestrator_step_00_intent: Intent decomposition produces IssueTree

tests/test_reverse_dcf.py
  - test_solve_implied_growth: Known EV/FCF → implied g matches formula
  - test_expectation_gap: Our 10% vs market 5% → gap = 5pp
  - test_decimal_precision: Reverse-DCF with Decimal vs float within tolerance

tests/test_intent_engine.py
  - test_mece_decomposition: Thesis → 3-5 hypotheses
  - test_research_plan: IssueTree → ordered data needs
  - test_expectations_investing: Price → implied → gap analysis
```

### 2.6 Acceptance Criteria

- [ ] `engine/orchestrator.py` `_execute_step` calls real engines (no stub returns)
- [ ] `ReverseDCFSolver.solve_implied_growth()` matches `core/compute/valuation/reverse_dcf.py` output
- [ ] `MECEIssueTree.decompose()` produces non-empty tree for 3 different company types
- [ ] Full 16-step pipeline runs end-to-end with real data
- [ ] Existing `pipeline/e2e_orchestrator.py` still works (backward compat)

---

## Phase 3: IronGate 2.0 — L1/L2/L3 Layered Architecture

**Goal**: Restructure flat IronGate into three distinct layers with clear responsibilities.

### 3.1 Architecture

```
IronGate 2.0
├── L1_hard_stop.py        — Conservation laws, structural integrity (BLOCK)
├── L2_economic_physics.py  — Economic relationships, parameter pruning (WARN/PRUNE)
├── L3_text_numeric.py      — Text-numeric contract, LLM rewrite triggers (REPORT)
└── registry.py             — Unified registration + execution
```

### 3.2 Create `engine/irongate_v2/__init__.py`

```python
from engine.irongate_v2.registry import IronGateV2
from engine.irongate_v2.layers import L1HardStop, L2EconomicPhysics, L3TextNumeric
```

### 3.3 Create `engine/irongate_v2/registry.py`

```python
"""
IronGate 2.0 — Layered validation registry.

Layers execute in order: L1 → L2 → L3
- L1 failure → BLOCK (halt pipeline, no computation)
- L2 failure → WARN + PRUNE (remove bad parameters, continue with defaults)
- L3 failure → REPORT (log for section_writer to address)
"""

from dataclasses import dataclass, field

class GateSeverity(str, Enum):
    BLOCK = "block"      # L1: Pipeline halts
    PRUNE = "prune"      # L2: Bad parameter removed, default substituted
    REPORT = "report"    # L3: Issue flagged for text layer

@dataclass
class GateVerdict:
    gate_id: str
    layer: str  # L1 / L2 / L3
    passed: bool
    severity: GateSeverity
    message: str
    param_key: str | None = None  # For L2 PRUNE: which parameter to fix
    suggested_default: float | None = None  # For L2 PRUNE: replacement value
    rewrite_hint: str | None = None  # For L3: suggestion for LLM rewrite

class IronGateV2:
    """Unified IronGate 2.0 — runs L1, L2, L3 in sequence."""

    def __init__(self):
        self.l1 = L1HardStop()
        self.l2 = L2EconomicPhysics()
        self.l3 = L3TextNumeric()

    def validate(self, assumptions: dict, report_text: str = "") -> "GateV2Report":
        report = GateV2Report()

        # L1: Hard stops — if any fail, halt
        l1_results = self.l1.validate(assumptions)
        report.add_layer("L1", l1_results)
        if not all(r.passed for r in l1_results if r.severity == GateSeverity.BLOCK):
            report.blocked = True
            return report

        # L2: Economic physics — prune bad params, continue
        l2_results = self.l2.validate(assumptions)
        pruned = self.l2.apply_prunes(assumptions, l2_results)
        report.add_layer("L2", l2_results)
        report.pruned_params = pruned

        # L3: Text-numeric contract — report issues for section_writer
        if report_text:
            l3_results = self.l3.validate(assumptions, report_text)
            report.add_layer("L3", l3_results)

        return report
```

### 3.4 Create `engine/irongate_v2/layers.py`

```python
"""
L1: Hard Stop — Conservation laws, structural integrity.
These MUST pass or computation is blocked.
"""

class L1HardStop:
    """L1 checks — conservation/structural constraints."""

    def validate(self, assumptions: dict) -> list[GateVerdict]:
        results = []
        # Port from engine/irongate.py existing L1 checks
        # + new checks:
        results.append(self._check_balance_sheet_identity(assumptions))
        results.append(self._check_wacc_gt_growth(assumptions))
        results.append(self._check_positive_revenue(assumptions))
        results.append(self._check_terminal_growth_cap(assumptions))
        return results

class L2EconomicPhysics:
    """L2 checks — economic relationships, parameter pruning.
    Failed checks → parameter pruned to safe default."""

    def validate(self, assumptions: dict) -> list[GateVerdict]:
        results = []
        # Port existing L2 checks
        # + new: parameter correlation checks
        results.append(self._check_margin_growth_correlation(assumptions))
        results.append(self._check_capex_vs_depreciation(assumptions))
        results.append(self._check_working_capital_reasonability(assumptions))
        return results

    def apply_prunes(self, assumptions: dict, results: list[GateVerdict]) -> dict:
        """For PRUNE-severity failures, substitute safe defaults."""
        pruned = {}
        for r in results:
            if r.severity == GateSeverity.PRUNE and not r.passed and r.param_key:
                old_val = assumptions.get(r.param_key)
                assumptions[r.param_key] = r.suggested_default
                pruned[r.param_key] = {"old": old_val, "new": r.suggested_default, "reason": r.message}
        return pruned

class L3TextNumeric:
    """L3 checks — text-numeric consistency.
    Report-only: flags mismatches for section_writer to address."""

    def validate(self, assumptions: dict, report_text: str) -> list[GateVerdict]:
        results = []
        results.append(self._check_target_price_mentioned(assumptions, report_text))
        results.append(self._check_growth_rate_consistent(assumptions, report_text))
        results.append(self._check_no_placeholder_numbers(assumptions, report_text))
        return results
```

### 3.5 Create `engine/irongate_v2/l1_checks.py`, `l2_checks.py`, `l3_checks.py`

Separate files for each layer's check implementations. Port existing checks from:
- `engine/irongate.py` (28 pre-computation checks) → L1/L2
- `pipeline/iron_gate.py` (102 post-generation checks) → L3
- `pipeline/checks/base.py` → shared types

### 3.6 Create `engine/irongate_v2/provenance.py`

```python
"""
Cell-level provenance tracking — every computed value has a source trail.
"""

from dataclasses import dataclass, field

@dataclass
class CellProvenance:
    """Provenance for a single computed cell."""
    cell_id: str  # e.g., "dcf.year3.fcf"
    value: float | Decimal
    formula: str  # e.g., "NOPAT + D&A - CapEx - ΔWC"
    inputs: dict[str, str] = field(default_factory=dict)  # {input_key: source}
    source: str = ""  # "engine/dcf_model.py:92" or "user_input"
    timestamp: str = ""

class ProvenanceTracker:
    """Tracks provenance for all computed values in a pipeline run."""

    def __init__(self):
        self._cells: dict[str, CellProvenance] = {}

    def record(self, cell_id: str, value, formula: str, inputs: dict, source: str = ""):
        self._cells[cell_id] = CellProvenance(
            cell_id=cell_id, value=value, formula=formula,
            inputs=inputs, source=source,
        )

    def get_trace(self, cell_id: str) -> list[CellProvenance]:
        """Get full dependency chain for a cell."""
        ...

    def to_audit_report(self) -> str:
        """Generate human-readable audit trail."""
        ...
```

### 3.7 Modify `engine/dcf_model.py` — Add provenance tracking

```python
class DCFEngine:
    def __init__(self, assumptions, skip_gates=False, tracker=None):
        self.tracker = tracker or ProvenanceTracker()

    def run(self):
        result = DCFResult(...)
        # After computing each cell:
        self.tracker.record(
            cell_id=f"dcf.year{i+1}.fcf",
            value=fcf_val,
            formula="NOPAT + D&A - CapEx - ΔWC",
            inputs={"nopat": f"ebit × (1-tax)", "da": f"rev × da_pct", ...},
            source="engine/dcf_model.py:92",
        )
```

### 3.8 Tests

```
tests/test_phase3_irongate_v2.py
  - test_l1_blocks_on_wacc_le_growth: WACC=5%, g=6% → BLOCKED
  - test_l1_passes_valid: Standard assumptions → all pass
  - test_l2_prunes_extreme_margin: Margin=90% → pruned to 60%
  - test_l2_preserves_valid_params: Normal params → no pruning
  - test_l3_detects_price_mismatch: Report says 50 but model says 30 → REPORT
  - test_l3_no_false_positive: Consistent text/numbers → all pass
  - test_provenance_chain: DCF year 3 FCF → trace back to base revenue
  - test_backward_compat_pipeline: pipeline/iron_gate.py still works

tests/test_phase3_integration.py
  - test_irongate_v2_in_orchestrator: Orchestrator calls IronGateV2
  - test_l1_blocks_pipeline: L1 fail → pipeline halts at step 01
  - test_l2_prune_continues: L2 prune → pipeline continues with defaults
```

### 3.9 Acceptance Criteria

- [ ] `IronGateV2.validate()` executes L1 → L2 → L3 in order
- [ ] L1 BLOCK stops pipeline (no computation after L1 fail)
- [ ] L2 PRUNE modifies assumptions dict and logs changes
- [ ] L3 REPORT generates rewrite hints for section_writer
- [ ] ProvenanceTracker records source for every DCF cell
- [ ] Existing `pipeline/iron_gate.py` still passes its own tests (no breaking changes)
- [ ] `engine/irongate.py` (v1) still works for backward compat

---

## Phase 4: Evidence Layer + Full Integration

**Goal**: Cell-level provenance in exports; XBRL alignment hooks; full integration test.

### 4.1 Create `core/evidence_layer.py`

```python
"""
Evidence Layer — cell-level provenance for all exports.

Integrates:
- ProvenanceTracker (from Phase 3)
- data_provenance.py (existing)
- claim_citation.py (existing)
- evidence_chain.py (existing)
"""

class EvidenceLayer:
    """Unified evidence tracking across computation → report → export."""

    def __init__(self):
        self.provenance = ProvenanceTracker()
        self.claim_tracker = ClaimTracker()
        self.xbrl_aligner = XBRLAligner()

    def wrap_computation(self, engine_result, assumptions):
        """Attach provenance to computation results."""
        ...

    def wrap_section(self, section_text, numeric_claims):
        """Attach evidence to report sections."""
        ...

    def generate_audit_trail(self) -> str:
        """Full audit trail: input → computation → report → export."""
        ...

class ClaimTracker:
    """Track every numeric claim in the report back to its source."""

    def extract_claims(self, report_text: str) -> list[dict]:
        """Extract all numeric claims: 'revenue grew 15%', 'PE of 25x', etc."""
        ...

    def validate_claims(self, claims: list[dict], provenance: ProvenanceTracker) -> list[dict]:
        """Check each claim against provenance data."""
        ...

class XBRLAligner:
    """Map computed values to XBRL taxonomy elements."""

    def align(self, computed_values: dict) -> dict:
        """Map engine output keys to XBRL standard tags."""
        # Revenue → gaap:Revenues
        # NetIncome → gaap:NetIncomeLoss
        # etc.
        ...
```

### 4.2 Modify `export/docx_exporter.py` — Add provenance footnotes

```python
class DocxExporter:
    def export_with_provenance(self, report, evidence_layer):
        """Export DOCX with cell-level provenance footnotes."""
        # For each numeric claim in report:
        # 1. Look up in evidence_layer.provenance
        # 2. Add footnote: "Source: DCF Model, Year 3 FCF = 5.2B (NOPAT + D&A - CapEx - ΔWC)"
        ...
```

### 4.3 Create `engine/sensitivity_surface.py`

```python
"""
Sensitivity Surface — multi-dimensional what-if analysis.
Extends existing sensitivity matrix to full surface.
"""

from engine.precision import D

class SensitivitySurface:
    """Compute sensitivity across multiple parameter dimensions."""

    def __init__(self, base_engine, base_assumptions):
        self.engine = base_engine
        self.base = base_assumptions

    def compute_2d(self, param_x: str, param_y: str, range_x: list, range_y: list) -> dict:
        """2D sensitivity: param_x × param_y → target metric."""
        matrix = {}
        for x in range_x:
            row = {}
            modified = {**self.base, param_x: x}
            for y in range_y:
                modified[param_y] = y
                result = self.engine.run_with(modified)
                row[y] = result.target_price
            matrix[x] = row
        return matrix

    def compute_3d(self, param_x: str, param_y: str, param_z: str,
                   range_x: list, range_y: list, range_z: list) -> dict:
        """3D surface: for tornado/surface plots."""
        ...
```

### 4.4 Modify `engine/orchestrator.py` — Add provenance to all steps

```python
class IBGradeOrchestrator:
    def __init__(self):
        self.evidence = EvidenceLayer()

    def run(self, assumptions):
        for step in self.steps:
            output = self._execute_step(step, assumptions)
            # Attach provenance
            self.evidence.provenance.record(
                cell_id=f"{step.value}.output",
                value=output,
                formula=f"step:{step.value}",
                inputs=assumptions,
            )
```

### 4.5 Integration Tests

```
tests/test_phase4_evidence.py
  - test_provenance_full_chain: Input → DCF → report → DOCX footnote
  - test_claim_validation: Report says "15% growth" → provenance confirms
  - test_xbrl_alignment: Revenue maps to gaap:Revenues
  - test_sensitivity_surface_2d: 5×5 matrix matches manual computation
  - test_full_pipeline_evidence: E2E run produces audit trail
  - test_backward_compat_export: Existing DOCX export still works

tests/test_full_integration.py
  - test_full_16_step_with_all_subsystems: Intent → Compute → IronGate → Evidence → Export
  - test_pipeline_e2e_compatibility: pipeline/e2e_orchestrator.py produces same output
  - test_engine_orchestrator_matches_pipeline: Both orchestrators give same DCF result
```

### 4.6 Acceptance Criteria

- [ ] Every numeric claim in DOCX has provenance footnote
- [ ] `ClaimTracker` extracts and validates 90%+ of numeric claims
- [ ] `XBRLAligner` maps all standard financial metrics
- [ ] Sensitivity surface computes 5×5 matrix in <1s
- [ ] Full pipeline run produces `audit_trail.md` with complete chain
- [ ] `pipeline/e2e_orchestrator.py` produces identical results (backward compat)
- [ ] All existing tests pass (zero regressions)

---

## 3. Migration Safety Rules

### Backward Compatibility Checklist

| Component | Must Still Work | How |
|-----------|-----------------|-----|
| `pipeline/e2e_orchestrator.py` | Yes | New engine is imported BY the pipeline, not replacing it |
| `pipeline/iron_gate.py` | Yes | IronGateV2 is additive; old `IronGateEngine` still importable |
| `core/compute/valuation/dcf.py` | Yes | Bridge wrapper calls existing function |
| `core/compute/three_statement.py` | Yes | Not modified; engine/three_statement.py is the enhanced version |
| `engine/schemas.py` | Yes | `schemas_v2.py` imports from it; old schema still importable |
| Existing tests | Yes | New tests added; old tests unchanged |

### Import Rules

```python
# Allowed:
from engine.schemas_v2 import DCFAssumptionsV2  # New unified schema
from engine.schemas import DCFAssumptions        # Old schema (backward compat)

# NOT allowed (during migration):
# Modifying core/compute/valuation/dcf.py function signatures
# Deleting engine/schemas.py
# Removing pipeline/iron_gate.py
```

### Strangler-Fig Pattern

```
Phase 1: engine/precision.py → wired into engine/ compute modules
Phase 2: engine/orchestrator.py stubs → replaced with real calls
Phase 3: engine/irongate_v2/ → new layer alongside old engine/irongate.py
Phase 4: core/evidence_layer.py → wraps existing export pipeline
```

Each phase delivers working code. No phase depends on future phases.

---

## 4. File Inventory Summary

### Files to Create (Phase 1)
- `engine/precision_registry.py`
- `engine/schemas_v2.py`
- `tests/test_phase1_precision.py`

### Files to Modify (Phase 1)
- `engine/dcf_model.py` (float → Decimal)
- `engine/three_statement.py` (float → Decimal)
- `engine/comparable_model.py` (float → Decimal)
- `engine/scenario_model.py` (float → Decimal)
- `engine/sotp_model.py` (float → Decimal)

### Files to Create (Phase 2)
- `engine/reverse_dcf.py`
- `engine/intent_engine.py`
- `tests/test_phase2_orchestrator.py`
- `tests/test_reverse_dcf.py`
- `tests/test_intent_engine.py`

### Files to Modify (Phase 2)
- `engine/orchestrator.py` (wire stubs)
- `engine/__init__.py` (add new exports)

### Files to Create (Phase 3)
- `engine/irongate_v2/__init__.py`
- `engine/irongate_v2/registry.py`
- `engine/irongate_v2/layers.py`
- `engine/irongate_v2/l1_checks.py`
- `engine/irongate_v2/l2_checks.py`
- `engine/irongate_v2/l3_checks.py`
- `engine/irongate_v2/provenance.py`
- `engine/sensitivity_surface.py`
- `tests/test_phase3_irongate_v2.py`
- `tests/test_phase3_integration.py`

### Files to Create (Phase 4)
- `core/evidence_layer.py`
- `tests/test_phase4_evidence.py`
- `tests/test_full_integration.py`

### Files to Modify (Phase 4)
- `export/docx_exporter.py` (provenance footnotes)
- `engine/orchestrator.py` (evidence wiring)

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Decimal performance regression | Medium | Low | Profile before/after; keep numpy for Monte Carlo |
| Schema migration breaks existing consumers | Low | High | `schemas_v2.py` imports old schemas; both available |
| IronGateV2 blocks valid assumptions | Medium | High | Port existing checks exactly; add new checks with WARN not BLOCK |
| Provenance tracker memory usage | Low | Medium | Cap at 10k cells; flush to disk for long runs |
| Pipeline backward compat broken | Low | Critical | Integration test runs old and new orchestrator, compares outputs |

---

## 6. Estimated Effort

| Phase | Scope | Estimated Time |
|-------|-------|---------------|
| Phase 1 | Precision + Schema | 2-3 days |
| Phase 2 | Orchestrator + Reverse-DCF + Intent | 3-4 days |
| Phase 3 | IronGate 2.0 + Provenance | 3-4 days |
| Phase 4 | Evidence Layer + Integration | 2-3 days |
| **Total** | | **10-14 days** |

---

## 7. Verification

After each phase, run:
```bash
# Existing tests must pass
python -m pytest tests/ -x -q

# New phase tests must pass
python -m pytest tests/test_phase{N}_*.py -v

# Type checking
mypy engine/ core/compute/ --ignore-missing-imports

# Lint
ruff check engine/ core/compute/

# Full pipeline smoke test
python -c "from engine import IBGradeOrchestrator; r = IBGradeOrchestrator().run({'ticker':'600000','base_revenue':100,'wacc':0.09,...}); print(r.summary())"
```

---

## 8. Completion Status

**All 4 phases completed and pushed.**

| Phase | Commit | Status |
|-------|--------|--------|
| Phase 1: Precision + Schema | `c045d62` | ✅ Done |
| Phase 2: Orchestrator + Reverse-DCF + Intent | `9a8e522` | ✅ Done |
| Phase 3: IronGate 2.0 | `9a8e522` | ✅ Done |
| Phase 4: Evidence Layer | `9a8e522` | ✅ Done |

### Test Results
- **41/41 tests pass** (21 Phase 1 + 20 Phase 2-4)
- **Lint**: all checks passed (ruff + harness + P0 block)
- **Demo**: 16/16 orchestrator steps complete (was all stubs)

### Files Created/Modified
- `engine/precision_registry.py` — centralized Decimal import
- `engine/schemas_v2.py` — unified Pydantic schemas (DCFAssumptionsV2, ReverseDCFAssumptions, MonteCarloAssumptionsV2, etc.)
- `engine/reverse_dcf.py` — Newton-Raphson implied growth solver + expectation gap analysis
- `engine/intent_engine.py` — MECE Issue Tree + Expectations Investing + persona-based research plans
- `engine/irongate_v2/` — L1/L2/L3 layered validation + ProvenanceTracker
- `engine/sensitivity_surface.py` — 2D grid + tornado analysis
- `core/evidence_layer.py` — ClaimTracker, XBRLAligner, EvidenceLayer
- `engine/orchestrator.py` — 16-step pipeline wired to real computation
- `engine/__init__.py` — v3.0.0 exports
- `tests/test_phase1_precision.py` — 21 tests
- `tests/test_phase2_4_integration.py` — 20 tests
