# -*- coding: utf-8 -*-
"""R85（2026-08-07）P0 治理回归测试 — decision_memo 图表层修复。

覆盖：
1. DataSufficiencyChecker 按 report_type 区分关键图键：
   - decision_memo 用 SAC 图集（6 图），允许缺失 ≤2 张仍判 sufficient（min 4/6）；
   - listed_company 等类型严格判定（fig_revenue_trend + fig_profitability 齐备）不变；
   - 默认参数兼容旧调用（report_type="listed_company"）。
2. chart_pipeline._extract_real_data fig_map 含 fig_production_path / fig_roadmap
   兜底映射（防回归：decision_memo 图集整体被拖入模板降级）。
"""

from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
from pipeline.data_enrichment import (  # noqa: E402
    DataSufficiencyChecker,
    DECISION_MEMO_CRITICAL_FIG_KEYS,
    DECISION_MEMO_MIN_FIG_KEYS,
)


def _dm_chart_data(real_count: int, with_empty: bool = False) -> dict:
    """构造 decision_memo 图集数据：前 real_count 张为真实数据，其余缺失。

    real_count=4 → 缺 fig_production_path / fig_roadmap（内部规划类）。
    with_empty=True 时把部分图置为空结构（模拟占位/空 dict）。
    """
    real = {
        "fig_market_size_global": {"2024": 300, "2025": 360},
        "fig_market_size_china": {"2024": 90, "2025": 110},
        "fig_industry_chain": {"上游": 30, "中游": 40, "下游": 30},
        "fig_competitive_landscape": {"A": 25, "B": 20, "其他": 55},
        "fig_production_path": {"自制": 1, "外协": 2},
        "fig_roadmap": {"Q1": "验收", "Q2": "量产"},
    }
    chart = {}
    for i, key in enumerate(DECISION_MEMO_CRITICAL_FIG_KEYS):
        if i < real_count:
            chart[key] = real[key]
        elif with_empty:
            # 键存在但为空结构：非空 dict 且内部无有效标量（如嵌套空 dict）
            chart[key] = {"_placeholder": {}}
    return {"chart_data": chart}


def test_dm_4_of_6_sufficient():
    """decision_memo：图集 4/6 真实数据（缺内部规划类 2 图）→ sufficient。"""
    r = DataSufficiencyChecker.check(_dm_chart_data(4), report_type="decision_memo")
    assert r["sufficient"] is True
    assert "fig_production_path" in r["missing"] and "fig_roadmap" in r["missing"]
    assert r["score"] > 0.5


def test_dm_3_of_6_insufficient():
    """decision_memo：图集仅 3/6 → insufficient（超过宽容阈值）。"""
    r = DataSufficiencyChecker.check(_dm_chart_data(3), report_type="decision_memo")
    assert r["sufficient"] is False


def test_dm_empty_structure_insufficient():
    """decision_memo：图集键存在但 2 张为空结构 + 2 张缺失 → 真实数 2/6 → insufficient。"""
    chart = {
        "fig_market_size_global": {"2024": 300, "2025": 360},
        "fig_market_size_china": {"2024": 90, "2025": 110},
        "fig_industry_chain": {"_placeholder": {}},       # 空结构（无有效标量）
        "fig_competitive_landscape": {"_placeholder": {}},  # 空结构
        # fig_production_path / fig_roadmap 缺失
    }
    r = DataSufficiencyChecker.check({"chart_data": chart},
                                     report_type="decision_memo")
    assert r["sufficient"] is False


def test_dm_all_6_sufficient():
    """decision_memo：图集 6/6 齐备 → sufficient 且无 missing。"""
    r = DataSufficiencyChecker.check(_dm_chart_data(6), report_type="decision_memo")
    assert r["sufficient"] is True
    assert r["missing"] == []


def test_listed_company_strict_unchanged():
    """listed_company：缺 fig_profitability → insufficient（严格判定不变）。"""
    data = {"chart_data": {"fig_revenue_trend": {"2023": 10, "2024": 12}}}
    r = DataSufficiencyChecker.check(data)  # 默认 report_type="listed_company"
    assert r["sufficient"] is False
    assert "fig_profitability" in str(r["missing"])


def test_listed_company_full_sufficient():
    """listed_company：双图齐备 → sufficient（行为不变）。"""
    data = {"chart_data": {
        "fig_revenue_trend": {"2023": 10, "2024": 12},
        "fig_profitability": {"2023": 1, "2024": 1.5},
    }}
    r = DataSufficiencyChecker.check(data)
    assert r["sufficient"] is True


def test_default_report_type_compat():
    """默认参数兼容旧调用：check(data) 等同 listed_company 严格判定。"""
    r = DataSufficiencyChecker.check({})
    assert r["sufficient"] is False
    assert "fig_revenue_trend" in r["missing"]


def test_dm_constants_align_sac():
    """decision_memo 关键图键常量与 SAC chart_config 图集一致（6 图）。"""
    assert len(DECISION_MEMO_CRITICAL_FIG_KEYS) == 6
    assert set(DECISION_MEMO_CRITICAL_FIG_KEYS) == {
        "fig_market_size_global", "fig_market_size_china",
        "fig_industry_chain", "fig_competitive_landscape",
        "fig_production_path", "fig_roadmap",
    }
    assert DECISION_MEMO_MIN_FIG_KEYS == 4


def test_chart_pipeline_fig_map_has_dm_fallback():
    """chart_pipeline fig_map 含 fig_production_path / fig_roadmap 兜底映射。"""
    from pipeline.chart_pipeline import ChartPipeline
    import inspect
    src = inspect.getsource(ChartPipeline._extract_real_data)
    assert '"fig_production_path"' in src and '"fig_roadmap"' in src
    # 兜底来源指向可用测算类键
    assert '"fig_revenue_trend"' in src
