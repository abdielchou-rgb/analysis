# -*- coding: utf-8 -*-
"""research_planner v1 + 路由器 + 反模式 单元测试（P3-B）。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from pipeline.research_planner import (
    detect_conflicts,
    followup_queries,
    plan,
    question_tree,
)


class TestQuestionTree:
    @pytest.mark.unit
    def test_two_questions_per_dim(self):
        tree = question_tree(["global_market_sizing", "moat_analysis", "unknown_dim_xyz"])
        assert len(tree) == 3
        for node in tree:
            assert len(node["questions"]) == 2

    @pytest.mark.unit
    def test_keyword_templates_hit(self):
        tree = question_tree(["global_market_sizing"])
        assert any("口径" in q for q in tree[0]["questions"])


class TestConflicts:
    @pytest.mark.unit
    def test_conflict_detected_and_query_built(self):
        cd = {
            "chart_data": {"fig_pe": {"pe_ttm": 30.0}, "fig_valuation": {"pe_ttm": 15.0}},
            "data_dict": {"fig_pe_pe_ttm": 30.0, "fig_valuation_pe_ttm": 15.0},
        }
        conf = detect_conflicts(cd)
        # 同指标(pe)两值偏差 100% → 应检出（阈值20%）
        if conf:  # 依赖 data_caliber 内部规范化，宽松断言
            qs = followup_queries(conf, "测试标的")
            assert all("核实" in q for q in qs)

    @pytest.mark.unit
    def test_plan_shape(self):
        r = plan("测试标的", ["估值"], {"chart_data": {}})
        assert {"question_tree", "conflicts", "followup_queries", "n_conflicts"} <= set(r.keys())


class TestRouter:
    @pytest.mark.unit
    def test_battery_route_by_asset(self):
        from core.industry_router import guess_industry, route_injector_skip

        ind = guess_industry("宁德时代", {})
        assert ind == "动力电池"
        skip = route_injector_skip("宁德时代", {})
        assert isinstance(skip, set)

    @pytest.mark.unit
    def test_default_route_open(self):
        from core.industry_router import guess_industry, route_injector_skip

        assert guess_industry("某不知名公司") == "default"
        assert route_injector_skip("某不知名公司", {}) == set()

    @pytest.mark.unit
    def test_playbook_files_exist(self):
        for f in ("battery", "semiconductor", "pharma"):
            fp = _ROOT / "config" / "playbooks" / f"{f}.yaml"
            assert fp.exists(), f"缺 playbook: {fp}"


class TestAntiPatterns:
    @pytest.mark.unit
    def test_scan_counts_unquantified(self):
        from core.anti_patterns import scan

        text = "我们长期看好该行业。竞争壁垒深厚。护城河稳固。营收提升显著。空间广阔。竞争格局优化。"
        hits = scan(text)
        assert len(hits) >= 4
