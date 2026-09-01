#!/usr/bin/env python3
"""test_verify_dryrun.py — verify_predictions.py dry-run 测试。

测试解析、到期判定、归因分析逻辑（不拉取价格）。

用法:
    python scripts/test_verify_dryrun.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.verify_predictions import (
    generate_attribution_analysis,
    is_due,
    parse_time_horizon,
)


def test_parse_time_horizon():
    """测试时间跨度解析。"""
    assert parse_time_horizon("3m") == 90
    assert parse_time_horizon("6m") == 180
    assert parse_time_horizon("12m") == 360
    assert parse_time_horizon("24m") == 720
    assert parse_time_horizon("unknown") is None
    assert parse_time_horizon("") is None
    print("[OK] parse_time_horizon")


def test_is_due():
    """测试到期判定。"""
    # 3m 预测，60天前建仓 → 未到期
    made = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    assert not is_due(made, 90)  # 3m = 90 days

    # 3m 预测，100天前建仓 → 已到期
    made = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
    assert is_due(made, 90)

    # 12m 预测，400天前建仓 → 已到期
    made = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    assert is_due(made, 360)  # 12m = 360 days

    # unknown → 永不到期
    made = (datetime.now() - timedelta(days=999)).strftime("%Y-%m-%d")
    assert not is_due(made, None)

    print("[OK] is_due")


def test_attribution_analysis():
    """测试归因分析生成。"""
    predictions = [
        {
            "asset": "A",
            "bold_call": "test",
            "industry": "tech",
            "made_date": "2026-01-01",
            "outcome": "miss",
            "attribution_tags": ["direction_wrong"],
            "alpha": -0.15,
            "key_variables": ["x"],
            "falsification_conditions": ["y"],
            "outcome_detail": "下跌15%",
        },
        {
            "asset": "B",
            "bold_call": "test2",
            "industry": "finance",
            "made_date": "2026-02-01",
            "outcome": "hit",
            "attribution_tags": [],
            "alpha": 0.10,
            "key_variables": [],
            "falsification_conditions": [],
            "outcome_detail": "上涨10%",
        },
    ]

    lessons = generate_attribution_analysis(predictions)
    assert len(lessons) == 1  # 只有 miss 有归因
    assert lessons[0]["attribution"] == "direction_wrong"
    assert lessons[0]["asset"] == "A"
    print("[OK] attribution_analysis")


def test_outcome_scenarios():
    """测试不同场景的归因标签。"""
    # 场景1: 看多但大幅下跌 → direction_wrong
    pred1 = {
        "asset": "X",
        "bold_call": "",
        "industry": "",
        "made_date": "",
        "outcome": "miss",
        "attribution_tags": ["direction_wrong"],
        "alpha": -0.15,
        "key_variables": [],
        "falsification_conditions": [],
        "outcome_detail": "",
    }
    lessons1 = generate_attribution_analysis([pred1])
    assert lessons1[0]["attribution"] == "direction_wrong"

    # 场景2: 看多但小幅震荡 → timing_off
    pred2 = {
        "asset": "Y",
        "bold_call": "",
        "industry": "",
        "made_date": "",
        "outcome": "partial",
        "attribution_tags": ["timing_off"],
        "alpha": 0.02,
        "key_variables": [],
        "falsification_conditions": [],
        "outcome_detail": "",
    }
    lessons2 = generate_attribution_analysis([pred2])
    assert lessons2[0]["attribution"] == "timing_off"

    # 场景3: 命中 → 无归因
    pred3 = {
        "asset": "Z",
        "bold_call": "",
        "industry": "",
        "made_date": "",
        "outcome": "hit",
        "attribution_tags": [],
        "alpha": 0.10,
        "key_variables": [],
        "falsification_conditions": [],
        "outcome_detail": "",
    }
    lessons3 = generate_attribution_analysis([pred3])
    assert len(lessons3) == 0

    print("[OK] outcome_scenarios")


def main():
    print("=== verify_predictions dry-run tests ===\n")
    test_parse_time_horizon()
    test_is_due()
    test_attribution_analysis()
    test_outcome_scenarios()
    print("\nAll tests passed")


if __name__ == "__main__":
    main()
