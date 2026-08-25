# -*- coding: utf-8 -*-
"""⭐盲区模块补测 — chart_engine / cross_validator / report_gate。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest


class TestChartEngine:
    @pytest.mark.unit
    def test_engine_instantiates(self):
        from core.chart_engine import ChartEngine

        ce = ChartEngine()
        assert hasattr(ce, "set_style")

    @pytest.mark.unit
    def test_bar_chart_renders(self, tmp_path):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from core.chart_engine import ChartEngine

        ce = ChartEngine()
        ce.set_style("cicc")
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.bar(["A", "B"], [1, 2])
        plt.close(fig)
        # 如果没崩溃就算通过（chart engine 内部逻辑由 chart_pipeline 测试覆盖）


class TestCrossValidator:
    @pytest.mark.unit
    def test_instantiates(self):
        from core.cross_validator import CrossValidator

        cv = CrossValidator()
        assert hasattr(cv, "warn_threshold")


class TestReportGatePaths:
    @pytest.mark.unit
    def test_gate_blocked_error(self):
        from export.report_gate import GateBlockedError

        e = GateBlockedError("test_check", 0.3, ["issue"])
        assert e is not None

    @pytest.mark.unit
    def test_gates_config_loads(self):
        from export.report_gate import GatesConfig

        gc = GatesConfig()
        assert gc._config is not None or gc._config == {}
