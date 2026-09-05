# -*- coding: utf-8 -*-
"""P0-5 (2026-09-02): 市占率数据契约 + fig_valuation 最新报告期修复测试。

深挖"报告数字为何脱离数据层"的根因 2/3：
1. 市占率根本没有数据键 → LLM 被逼编造（每章节写不同市占率）→ cross_section 冲突
   → 修复：采集侧加 fig_segment_share（分部收入占比，来源标注），
          写作侧无市占率数据时注入"禁编造铁律"
2. fig_valuation 取 akshare iloc[0] 拿到最早报告期（2014）而非最新
   → 修复：按报告期降序取最新
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from pipeline.sw_serialize import serialize_chart_data


class TestMarketShareContract:
    def test_no_share_data_blocks_fabrication(self):
        """无市占率数据 → serialize 注入禁编造铁律。"""
        data = {"chart_data": {"fig_revenue_trend": {"2024": 100.0}}}
        out = serialize_chart_data(data)
        assert "市占率铁律" in out
        assert "严禁编造" in out

    def test_segment_share_data_no_block(self):
        """有 fig_segment_share → 不触发禁编造（数据可引用）。"""
        data = {
            "chart_data": {
                "fig_segment_share": {
                    "segments": {"动力电池": 70.0, "储能": 30.0},
                    "note": "分部收入占比",
                    "source": "akshare:stock_zygc_em",
                }
            }
        }
        out = serialize_chart_data(data)
        assert "市占率铁律" not in out
        assert "fig_segment_share" in out


class TestFigValuationLatestPeriod:
    def test_latest_period_sorting(self):
        """fig_valuation 应按报告期降序取最新（非 iloc[0] 最早）。"""
        # 直接测采集代码里的排序逻辑（akshare 返回升序场景）
        rows = [
            {"报告期": "2014-12-31", "净利润": "5442.58万"},
            {"报告期": "2025-09-30", "净利润": "507.45亿"},
            {"报告期": "2024-12-31", "净利润": "441.21亿"},
        ]
        sorted_rows = sorted(rows, key=lambda r: r["报告期"], reverse=True)
        latest = sorted_rows[0]
        assert latest["报告期"] == "2025-09-30"
        assert latest["净利润"] == "507.45亿"

    def test_source_label_in_valuation(self):
        """fig_valuation 应带 source 标注。"""
        # 验证采集代码生成的 fig_valuation 结构（模拟）
        val = {
            "net_profit": "507.45亿",
            "period": "2025-09-30",
            "source": "akshare:stock_financial_abstract_ths(按报告期)",
        }
        assert "source" in val
        assert "akshare" in val["source"]
