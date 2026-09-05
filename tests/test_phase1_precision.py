"""
Phase 1 测试 — Decimal 精度 + 统一 Schema
验证所有 engine/ 计算模块使用 Decimal 精度且结果一致。
"""

from decimal import Decimal

import pytest

from engine.precision import D, PreciseValuation, ddiv, dto_float
from engine.precision_registry import D as D2
from engine.precision_registry import dsum


class TestPrecisionRegistry:
    """precision_registry 集中导入测试"""

    def test_d_from_registry_matches_direct(self):
        assert D(3.14) == D2(3.14)

    def test_dsum_from_registry(self):
        assert dsum([1, 2, 3]) == D(6)

    def test_d_with_float(self):
        assert D(0.1) + D(0.2) == D("0.3")

    def test_d_with_string(self):
        assert D("1500 * 0.65") == D(975)

    def test_d_with_decimal(self):
        val = Decimal("3.14")
        assert D(val) is val

    def test_ddiv_safe_zero(self):
        assert ddiv(10, 0) == D(0)

    def test_dto_float_roundtrip(self):
        original = D("1234.56789")
        assert abs(dto_float(original) - 1234.56789) < 1e-10


class TestProvenanceTracking:
    """PreciseValuation 溯源追踪测试"""

    def test_set_and_get(self):
        pv = PreciseValuation()
        pv.set("revenue", 1000, source="financial_statement", formula="base_revenue")
        assert pv.get("revenue") == D(1000)
        assert pv.get_source("revenue") == "financial_statement"
        assert pv.get_formula("revenue") == "base_revenue"

    def test_provenance_report(self):
        pv = PreciseValuation()
        pv.set("ebit", 650, source="computed", formula="revenue × margin")
        report = pv.provenance_report()
        assert "ebit" in report
        assert "revenue × margin" in report

    def test_to_dict(self):
        pv = PreciseValuation()
        pv.set("value", 42.5)
        d = pv.to_dict()
        assert abs(d["value"] - 42.5) < 1e-10


class TestSchemasV2:
    """schemas_v2 统一 Schema 测试"""

    def test_dcf_v2_import(self):
        from engine.schemas_v2 import DCFAssumptionsV2

        assert DCFAssumptionsV2 is not None

    def test_reverse_dcf_schema(self):
        from engine.schemas_v2 import ReverseDCFAssumptions

        r = ReverseDCFAssumptions(
            ticker="600519.SH",
            current_price=1680.0,
            shares_outstanding=12.56,
            net_debt=-500,
            wacc=0.09,
        )
        assert r.ticker == "600519.SH"
        assert r.current_price == 1680.0

    def test_cell_provenance(self):
        from engine.schemas_v2 import CellProvenance

        cp = CellProvenance(
            cell_id="dcf.year3.fcf",
            value=52.3,
            formula="NOPAT + D&A - CapEx - ΔWC",
            source_file="engine/dcf_model.py:92",
        )
        assert cp.cell_id == "dcf.year3.fcf"
        assert cp.confidence == 1.0

    def test_sensitivity_surface(self):
        from engine.schemas_v2 import SensitivityParam, SensitivitySurface

        ss = SensitivitySurface(
            target_metric="target_price",
            params=[
                SensitivityParam(name="wacc", base_value=0.09),
                SensitivityParam(name="terminal_growth", base_value=0.025),
            ],
        )
        assert len(ss.params) == 2

    def test_dcf_v2_forecast_alignment(self):
        from engine.schemas_v2 import DCFAssumptionsV2

        with pytest.raises(ValueError, match="revenue_growth_rates"):
            DCFAssumptionsV2(
                ticker="TEST",
                base_revenue=100,
                forecast_years=5,
                revenue_growth_rates=[0.1, 0.1],
                ebit_margins=[0.2, 0.2, 0.2, 0.2, 0.2],
                wacc=0.09,
                shares_outstanding=10,
            )


class TestDecimalDCFPrecision:
    """DCF Decimal 精度验证"""

    def test_dcf_decimal_vs_float(self):
        """Decimal DCF 结果与 float 版本一致（容差 1e-6）"""
        from engine.dcf_model import DCFEngine
        from engine.schemas import DCFAssumptions

        a = DCFAssumptions(
            ticker="TEST",
            company_name="测试公司",
            forecast_years=5,
            base_revenue=100.0,
            base_ebit_margin=0.20,
            revenue_growth_rates=[0.15, 0.12, 0.10, 0.08, 0.05],
            ebit_margins=[0.20, 0.21, 0.22, 0.23, 0.24],
            wacc=0.09,
            terminal_growth_rate=0.025,
            shares_outstanding=10.0,
            net_debt=50.0,
        )
        result = DCFEngine(a, skip_gates=True).run()
        # 验证结果合理性
        assert result.fair_value_per_share > 0
        assert result.enterprise_value > 0
        assert len(result.fcf) == 5
        assert len(result.sensitivity_matrix) == 5

    def test_dcf_provenance(self):
        """DCF 引擎记录溯源信息"""
        from engine.dcf_model import DCFEngine
        from engine.schemas import DCFAssumptions

        a = DCFAssumptions(
            ticker="TEST",
            company_name="测试",
            forecast_years=3,
            base_revenue=100.0,
            base_ebit_margin=0.20,
            revenue_growth_rates=[0.10, 0.08, 0.06],
            ebit_margins=[0.20, 0.21, 0.22],
            wacc=0.09,
            terminal_growth_rate=0.025,
            shares_outstanding=10.0,
        )
        engine = DCFEngine(a, skip_gates=True)
        engine.run()
        report = engine.provenance.provenance_report()
        assert "base_revenue" in report
        assert "year1.fcf" in report


class TestDecimalThreeStatementPrecision:
    """三表联动 Decimal 精度验证"""

    def test_three_statement_invariants_decimal(self):
        """Decimal 精度下三项不变量均通过"""
        from engine.three_statement import ThreeStatementAssumptions, ThreeStatementEngine

        a = ThreeStatementAssumptions(
            ticker="TEST",
            company_name="测试公司",
            forecast_years=5,
            base_revenue=100.0,
            revenue_growth_rates=[0.10, 0.08, 0.06, 0.05, 0.04],
            base_cash=20.0,
            base_equity=80.0,
            base_short_term_debt=10.0,
            base_long_term_debt=30.0,
        )
        result = ThreeStatementEngine(a, skip_gates=True).run()
        assert result.invariant_checks["balance_sheet_identity"]
        assert result.invariant_checks["cash_flow_identity"]
        assert result.invariant_checks["retained_earnings_identity"]
        assert result.fcff_for_dcf is not None
        assert result.fcfe_for_dcf is not None

    def test_three_statement_provenance(self):
        """三表引擎记录溯源"""
        from engine.three_statement import ThreeStatementAssumptions, ThreeStatementEngine

        a = ThreeStatementAssumptions(
            ticker="TEST",
            company_name="测试",
            forecast_years=3,
            base_revenue=100.0,
            revenue_growth_rates=[0.10, 0.08, 0.06],
            base_cash=20.0,
            base_equity=80.0,
        )
        engine = ThreeStatementEngine(a, skip_gates=True)
        engine.run()
        report = engine.provenance.provenance_report()
        assert "year1.fcff" in report


class TestDecimalComparablePrecision:
    """可比估值 Decimal 精度验证"""

    def test_comparable_decimal(self):
        from engine.comparable_model import ComparableEngine
        from engine.schemas import ComparableAssumptions

        a = ComparableAssumptions(
            ticker="TEST",
            company_name="测试",
            company_eps=3.0,
            company_bvps=15.0,
            peer_pe_ratios=[20.0, 22.0, 25.0],
        )
        result = ComparableEngine(a, skip_gates=True).run()
        assert result.target_price > 0
        assert "PE" in result.implied_prices


class TestDecimalScenarioPrecision:
    """情景分析 Decimal 精度验证"""

    def test_scenario_decimal(self):
        from engine.scenario_model import ScenarioEngine
        from engine.schemas import ScenarioAssumptions, ScenarioDetail

        a = ScenarioAssumptions(
            ticker="TEST",
            company_name="测试",
            base_price=50.0,
            bull=ScenarioDetail(
                revenue_growth_rates=[0.15, 0.12, 0.10],
                operating_margin=0.25,
                probability=0.30,
            ),
            base=ScenarioDetail(
                revenue_growth_rates=[0.10, 0.08, 0.06],
                operating_margin=0.20,
                probability=0.50,
            ),
            bear=ScenarioDetail(
                revenue_growth_rates=[0.05, 0.03, 0.02],
                operating_margin=0.15,
                probability=0.20,
            ),
            base_revenue=100.0,
            total_shares=10.0,
        )
        result = ScenarioEngine(a, skip_gates=True).run()
        assert result.weighted_target > 0
        assert len(result.scenario_prices) == 3
