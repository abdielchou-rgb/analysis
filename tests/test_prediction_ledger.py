# -*- coding: utf-8 -*-
"""预测账本提取 + 来源分层 单元测试（P3-A）。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.prediction_extract import extract_predictions
from core.source_tier import evidence_pool_stats, high_confidence_ratio, score_source

SAMPLE = (
    "# 宁德时代业绩点评\n\n投资评级：增持。12个月目标价：312.00元"
    "（数据来源：公司公告）。\n2026E EPS 20.77元，2027E EPS 23.17 元。\n"
)


class TestPredictionExtract:
    @pytest.mark.unit
    def test_extracts_all_three_kinds(self):
        preds = extract_predictions(SAMPLE)
        kinds = {p["kind"] for p in preds}
        assert {"rating", "target_price", "eps_forecast"} <= kinds

    @pytest.mark.unit
    def test_target_price_value(self):
        preds = [p for p in extract_predictions(SAMPLE) if p["kind"] == "target_price"]
        assert preds and preds[0]["value"] == 312.0

    @pytest.mark.unit
    def test_dedup_eps_years(self):
        preds = [p for p in extract_predictions(SAMPLE) if p["kind"] == "eps_forecast"]
        years = [p["statement"][:5] for p in preds]
        assert len(years) == len(set(years))

    @pytest.mark.unit
    def test_garbage_filtered(self):
        preds = extract_predictions("目标价：999999元。")
        assert not [p for p in preds if p["kind"] == "target_price"]

    @pytest.mark.unit
    def test_record_never_raises(self, tmp_path, monkeypatch):
        """账本写失败必须静默——绝不阻塞交付。"""
        import core.prediction_extract as pe

        class _Boom:
            def record(self, *a, **k):
                raise RuntimeError("db locked")

        monkeypatch.setattr(pe, "PredictionLoop", _Boom, raising=False)
        # record_predictions 内部 from-import 真模块 → 直接调用应吞异常返回 0
        assert pe.record_predictions(SAMPLE, "300750") >= 0


class TestSourceTier:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "src,tier",
        [
            ("宁德时代2025年三季报", "official"),
            ("巨潮资讯网", "official"),
            ("中金公司2026-08研报", "broker"),
            ("财联社快讯", "media"),
            ("雪球用户讨论", "social"),
        ],
    )
    def test_known_sources(self, src, tier):
        assert score_source(src)[0] == tier

    @pytest.mark.unit
    def test_unknown_mid_weight(self):
        assert score_source("") == ("unknown", 0.5)

    @pytest.mark.unit
    def test_pool_stats_and_hi_ratio(self):
        cd = {
            "items": [
                {"source": "公司年报"},
                {"source": "高盛研报"},
                {"source": "雪球"},
            ]
        }
        stats = evidence_pool_stats(cd)
        assert stats.get("official") == 1 and stats.get("social") == 1
        assert high_confidence_ratio(cd) > 0.6
