# -*- coding: utf-8 -*-
"""Evidence-Grounded Writing + Delta-Only Rewrite 测试。

覆盖：
- research_planner._build_dim_kb_map
- research_planner.plan() 输出 dim_kb_map
- section_writer._mkb_for_group
- e2e_orchestrator._locate_failed_dims
- e2e_orchestrator._build_dim_kb_hints
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── _locate_failed_dims ─────────────────────────────────────────


class TestLocateFailedDims:
    def test_gate_feedback_dim_marker(self):
        from pipeline.e2e_orchestrator import _locate_failed_dims

        gf = "[ERROR] [DIM:business_model] 商业模式分析缺少护城河论证"
        dims = _locate_failed_dims(gf, "", {})
        assert "business_model" in dims

    def test_review_comments_keywords(self):
        from pipeline.e2e_orchestrator import _locate_failed_dims

        rc = "估值章节缺少 DCF 敏感性分析，目标价未给出"
        dims = _locate_failed_dims("", rc, {})
        assert "valuation_assessment" in dims

    def test_context_explicit(self):
        from pipeline.e2e_orchestrator import _locate_failed_dims

        ctx = {"failed_dims": ["risk", "catalyst"]}
        dims = _locate_failed_dims("", "", ctx)
        assert "risk" in dims
        assert "catalyst" in dims

    def test_combined_sources(self):
        from pipeline.e2e_orchestrator import _locate_failed_dims

        gf = "[DIM:financial_analysis] 财务数据不完整"
        rc = "竞争格局分析需要点名具体玩家"
        ctx = {"failed_dims": ["growth_drivers"]}
        dims = _locate_failed_dims(gf, rc, ctx)
        assert "financial_analysis" in dims
        assert "competitive_position" in dims
        assert "growth_drivers" in dims

    def test_empty_returns_empty(self):
        from pipeline.e2e_orchestrator import _locate_failed_dims

        dims = _locate_failed_dims("", "", {})
        assert dims == []


# ── _build_dim_kb_hints ─────────────────────────────────────────


class TestBuildDimKBHints:
    def test_with_dim_kb_map(self):
        from pipeline.e2e_orchestrator import _build_dim_kb_hints

        ctx = {
            "collected_data": {
                "_dim_kb_map": {
                    "valuation_assessment": [
                        {
                            "title": "DCF估值方法论",
                            "topic": "估值",
                            "body": "DCF估值核心步骤...",
                        }
                    ]
                }
            }
        }
        hints = _build_dim_kb_hints(["valuation_assessment"], ctx)
        assert "valuation_assessment" in hints
        assert "DCF" in hints

    def test_empty_when_no_map(self):
        from pipeline.e2e_orchestrator import _build_dim_kb_hints

        hints = _build_dim_kb_hints(["valuation_assessment"], {})
        assert hints == ""

    def test_empty_when_no_failed_dims(self):
        from pipeline.e2e_orchestrator import _build_dim_kb_hints

        ctx = {"collected_data": {"_dim_kb_map": {"valuation_assessment": []}}}
        hints = _build_dim_kb_hints([], ctx)
        assert hints == ""


# ── _build_dim_kb_map ───────────────────────────────────────────


class TestBuildDimKBMap:
    def test_returns_dict(self):
        from pipeline.research_planner import _build_dim_kb_map

        result = _build_dim_kb_map(
            ["valuation_assessment", "financial_analysis"],
            "测试公司",
            "listed_company",
        )
        assert isinstance(result, dict)

    def test_empty_dims_returns_empty(self):
        from pipeline.research_planner import _build_dim_kb_map

        result = _build_dim_kb_map([], "测试公司", "listed_company")
        assert result == {}


# ── plan() 输出 dim_kb_map ──────────────────────────────────────


class TestPlanOutputHasDimKBMap:
    def test_dim_kb_map_in_output(self):
        from pipeline.research_planner import plan

        result = plan(
            asset="测试公司",
            dims=["valuation_assessment", "financial_analysis"],
            collected_data={},
            report_type="listed_company",
            use_llm=False,
        )
        assert "dim_kb_map" in result
        assert isinstance(result["dim_kb_map"], dict)
