"""
Phase 2-4 测试 — Reverse-DCF, Intent Engine, IronGate 2.0, Evidence Layer
"""


class TestReverseDCF:
    """Reverse-DCF 求解器测试"""

    def test_solve_implied_growth_basic(self):
        from engine.reverse_dcf import ReverseDCFSolver

        solver = ReverseDCFSolver(
            current_price=20.0,
            shares_outstanding=10.0,
            net_debt=0.0,
            fcf_ttm=16.0,
            wacc=0.10,
            terminal_growth_rate=0.025,
            forecast_years=10,
        )
        result = solver.solve_implied_growth()
        assert result.converged
        assert -0.05 < result.implied_growth_rate < 0.15
        assert result.ev_to_fcf > 0

    def test_solve_high_price_implies_high_growth(self):
        from engine.reverse_dcf import ReverseDCFSolver

        # 使用 FCF=16，不同价格测试隐含增长率差异
        low = ReverseDCFSolver(current_price=10, shares_outstanding=10, fcf_ttm=16, wacc=0.10)
        high = ReverseDCFSolver(current_price=25, shares_outstanding=10, fcf_ttm=16, wacc=0.10)
        r_low = low.solve_implied_growth()
        r_high = high.solve_implied_growth()
        assert r_high.implied_growth_rate >= r_low.implied_growth_rate

    def test_bound_saturation_detected(self):
        """极高EV/FCF触发边界饱和警告"""
        from engine.reverse_dcf import ReverseDCFSolver

        solver = ReverseDCFSolver(current_price=100, shares_outstanding=10, fcf_ttm=8, wacc=0.10)
        result = solver.solve_implied_growth()
        assert not result.converged
        assert len(result.warnings) > 0

    def test_expectation_gap_analysis(self):
        from engine.reverse_dcf import ReverseDCFSolver

        solver = ReverseDCFSolver(
            current_price=100.0,
            shares_outstanding=10.0,
            fcf_ttm=8.0,
            wacc=0.10,
        )
        result = solver.expectation_gap_analysis(our_growth=0.15)
        assert result.our_growth == 0.15
        assert result.expectation_gap_pp is not None
        assert result.price_drop_to_fair_value_pct is not None

    def test_missing_fcf_returns_warning(self):
        from engine.reverse_dcf import ReverseDCFSolver

        solver = ReverseDCFSolver(current_price=100, shares_outstanding=10)
        result = solver.solve_implied_growth()
        assert not result.converged
        assert len(result.warnings) > 0


class TestIntentEngine:
    """Intent Engine 测试"""

    def test_mece_decomposition(self):
        from engine.intent_engine import MECEIssueTree

        tree = MECEIssueTree("茅台长期投资价值分析", {"biz_model": "revenue_growth"})
        root = tree.decompose()
        assert root.node_type.value == "thesis"
        assert len(root.children) >= 3
        # 每个假设有数据需求和证伪条件
        for child in root.children:
            assert len(child.children) >= 2

    def test_research_plan_generation(self):
        from engine.intent_engine import DecisionPersona, MECEIssueTree

        tree = MECEIssueTree("新能源行业深度", {"biz_model": "margin_expansion"})
        tree.decompose()
        plan = tree.to_research_plan(DecisionPersona.PE_FUND)
        assert len(plan.hypotheses) >= 3
        assert len(plan.computation_steps) > 0
        assert plan.persona == DecisionPersona.PE_FUND

    def test_expectations_investing(self):
        from engine.intent_engine import ExpectationsInvesting

        ei = ExpectationsInvesting()
        result = ei.analyze(
            current_price=100.0,
            reverse_dcf_result={"implied_growth_rate": 0.08},
            our_assumptions={"revenue_growth": 0.15},
        )
        assert result["expectation_gap_pp"] > 0
        assert "BULLISH" in result["stance"]

    def test_different_personas_different_steps(self):
        from engine.intent_engine import DecisionPersona, MECEIssueTree

        tree = MECEIssueTree("test")
        tree.decompose()

        pe_plan = tree.to_research_plan(DecisionPersona.PE_FUND)
        er_plan = tree.to_research_plan(DecisionPersona.EQUITY_RESEARCH)
        assert pe_plan.computation_steps != er_plan.computation_steps


class TestIronGateV2:
    """IronGate 2.0 三层校验测试"""

    def test_l1_blocks_on_wacc_le_growth(self):
        from engine.irongate_v2 import IronGateV2

        gate = IronGateV2()
        report = gate.validate(
            {"wacc": 0.05, "terminal_growth_rate": 0.06, "base_revenue": 100, "shares_outstanding": 10}
        )
        assert report.blocked

    def test_l1_passes_valid(self):
        from engine.irongate_v2 import IronGateV2

        gate = IronGateV2()
        report = gate.validate(
            {"wacc": 0.09, "terminal_growth_rate": 0.025, "base_revenue": 100, "shares_outstanding": 10}
        )
        assert not report.blocked

    def test_l2_prunes_extreme_margin(self):
        from engine.irongate_v2 import IronGateV2

        gate = IronGateV2()
        a = {
            "wacc": 0.09,
            "terminal_growth_rate": 0.025,
            "base_revenue": 100,
            "shares_outstanding": 10,
            "ebit_margins": [0.70, 0.75, 0.80],
        }
        report = gate.validate(a)
        assert "ebit_margins" in report.pruned_params

    def test_l3_detects_growth_mismatch(self):
        from engine.irongate_v2 import IronGateV2

        gate = IronGateV2()
        a = {
            "wacc": 0.09,
            "terminal_growth_rate": 0.025,
            "base_revenue": 100,
            "shares_outstanding": 10,
            "revenue_growth_rates": [-0.10, -0.08, -0.06],
        }
        text = "公司营收将稳步增长，未来前景光明"
        report = gate.validate(a, report_text=text)
        l3 = report.layer_results.get("L3", [])
        fails = [v for v in l3 if not v.passed]
        assert len(fails) > 0


class TestSensitivitySurface:
    """Sensitivity Surface 测试"""

    def test_2d_sensitivity(self):
        from engine.sensitivity_surface import SensitivitySurface

        def simple_dcf(params):
            rev = params.get("base_revenue", 100)
            margin = params.get("ebit_margin", 0.20)
            wacc = params.get("wacc", 0.09)
            g = params.get("terminal_growth", 0.025)
            if wacc <= g:
                return 0
            fcf = rev * margin
            tv = fcf * (1 + g) / (wacc - g)
            return (fcf / wacc + tv) / 10

        surface = SensitivitySurface(
            simple_dcf, {"base_revenue": 100, "ebit_margin": 0.20, "wacc": 0.09, "terminal_growth": 0.025}
        )
        result = surface.compute_2d("wacc", "terminal_growth", steps=2)
        assert len(result.matrix) == 3  # steps+1 points
        assert len(result.matrix[0]) == 3
        assert result.base_value > 0

    def test_tornado(self):
        from engine.sensitivity_surface import SensitivitySurface

        def simple_dcf(params):
            return params.get("base_revenue", 100) * params.get("margin", 0.20) / params.get("wacc", 0.09)

        surface = SensitivitySurface(simple_dcf, {"base_revenue": 100, "margin": 0.20, "wacc": 0.09})
        result = surface.tornado({"wacc": (0.07, 0.11), "margin": (0.15, 0.25)})
        assert len(result.tornado) == 2
        assert result.tornado[0]["swing"] >= result.tornado[1]["swing"]


class TestEvidenceLayer:
    """Evidence Layer 测试"""

    def test_claim_extraction(self):
        from core.evidence_layer import ClaimTracker

        tracker = ClaimTracker()
        claims = tracker.extract_claims("营收增长15%，毛利率提升至35%，目标价50元")
        assert len(claims) >= 2

    def test_xbrl_alignment(self):
        from core.evidence_layer import XBRLAligner

        aligner = XBRLAligner()
        aligned = aligner.align({"revenue": 100, "net_income": 20, "total_assets": 500})
        assert aligned["revenue"] == "gaap:Revenues"
        assert aligned["net_income"] == "gaap:NetIncomeLoss"

    def test_provenance_tracker(self):
        from engine.irongate_v2.provenance import ProvenanceTracker

        pt = ProvenanceTracker()
        pt.record("dcf.fair_value", 42.5, formula="equity / shares", source_file="dcf_model.py:100")
        assert pt.get("dcf.fair_value").value == 42.5
        trace = pt.get_trace("dcf.fair_value")
        assert len(trace) == 1


class TestOrchestratorWiring:
    """Orchestrator 真实计算接入测试"""

    def test_full_pipeline_runs(self):
        from engine.orchestrator import IBGradeOrchestrator

        obs = IBGradeOrchestrator()
        a = {
            "ticker": "TEST",
            "company_name": "测试公司",
            "base_revenue": 100,
            "revenue_growth_rates": [0.10, 0.08, 0.06, 0.05, 0.04],
            "base_ebit_margin": 0.20,
            "wacc": 0.09,
            "terminal_growth_rate": 0.025,
            "shares_outstanding": 10,
            "net_debt": 50,
            "current_price": 100,
        }
        result = obs.run(a)
        assert result.success
        assert "01_income_statement" in result.steps
        assert result.steps["01_income_statement"].status == "completed"
        assert result.steps["09_dcf"].status == "completed"

    def test_dcf_output_has_fair_value(self):
        from engine.orchestrator import IBGradeOrchestrator

        obs = IBGradeOrchestrator()
        a = {
            "ticker": "TEST",
            "company_name": "测试",
            "base_revenue": 100,
            "revenue_growth_rates": [0.10, 0.08, 0.06, 0.05, 0.04],
            "base_ebit_margin": 0.20,
            "wacc": 0.09,
            "terminal_growth_rate": 0.025,
            "shares_outstanding": 10,
            "net_debt": 50,
        }
        result = obs.run(a)
        dcf_output = result.steps["09_dcf"].output
        assert dcf_output["fair_value"] > 0
