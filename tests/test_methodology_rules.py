# -*- coding: utf-8 -*-
"""M1 规则库扩容回归：13 个 topic_map 主题必须全部非空。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.methodology_rules import serialize_rules_for_prompt

ALL_TOPICS = [
    "industry_lifecycle",
    "business_model",
    "profit_pool",
    "competitive_forces",
    "elasticity_analysis",
    "signal_chain",
    "policy_transmission",
    "global_competition",
    "technology_roadmap",
    "capital_market",
    "reference_class",
    "unit_economics",
    "exit_pathways",
]


@pytest.mark.unit
@pytest.mark.parametrize("topic", ALL_TOPICS)
def test_topic_has_rules(topic):
    txt = serialize_rules_for_prompt([topic])
    assert "【" in txt, f"主题 {topic} 规则为空"


@pytest.mark.unit
def test_new_schema_fields_present():
    import json

    d = json.loads((_ROOT / "data" / "methodology_rules.json").read_text(encoding="utf-8"))
    for topic in ("profit_pool", "reference_class"):
        for r in d[topic]:
            assert "applicability" in r, f"{topic}/{r.get('rule_id')} 缺 applicability"
            assert isinstance(r.get("failure_modes"), list), f"{topic} 缺 failure_modes"
