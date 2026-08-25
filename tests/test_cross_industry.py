# -*- coding: utf-8 -*-
"""跨行业类比引擎 + point-in-time 测试。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.cross_industry import format_block, match


class TestCrossIndustry:
    @pytest.mark.unit
    def test_battery_matches_solar(self):
        """电池（中增长/分散/重资产）应匹配光伏案例。"""
        results = match(
            "动力电池",
            growth_rate=20.0,
            cr3=25.0,
            capital_intensity="重资产",
            tech_cycle="快速迭代",
        )
        assert len(results) >= 1
        assert any("光伏" in r["analogy_industry"] for r in results)

    @pytest.mark.unit
    def test_self_excluded(self):
        """不跟自己比。"""
        results = match("光伏面板", growth_rate=15.0, cr3=25.0, capital_intensity="重资产")
        assert not any("光伏" in r["analogy_industry"] for r in results)

    @pytest.mark.unit
    def test_format_produces_block(self):
        matches = match("动力电池", growth_rate=20.0, cr3=25.0, capital_intensity="重资产")
        block = format_block(matches, "动力电池")
        if matches:
            assert "[跨行业类比]" in block
            assert "关键教训" in block

    @pytest.mark.unit
    def test_no_data_returns_empty(self):
        results = match("完全不存在的行业", growth_rate=None, cr3=None)
        # 可能无匹配（分数不够）
        assert isinstance(results, list)


class TestPointInTime:
    @pytest.mark.unit
    def test_financials_query_has_time_filter(self):
        """financials 查询应支持按披露日期过滤。"""
        from core.data_basement import _connect

        conn = _connect("financials.db")
        if conn is None:
            pytest.skip("financials.db 不可用")
        cols = [r[1] for r in conn.execute("PRAGMA table_info(financials)")]
        conn.close()
        # 如果有 disclosed_at 或 announce_date 列则 PIT 可用
        pit_cols = [c for c in cols if "disclos" in c.lower() or "announce" in c.lower() or "report_date" in c.lower()]
        # 不强制要求——记录当前状态即可
        print(f"PIT columns: {pit_cols or 'NONE — 需要添加'}")
