"""PipelineContext 类型化契约守护测试。

P3-audit 2026-08-24：21 节点共享裸 dict 的键名约定从此有单一事实源。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from pipeline.context_schema import (
    CONTEXT_KEYS,
    new_context,
    unknown_keys,
)


@pytest.mark.unit
def test_contract_covers_core_keys():
    """核心数据流键必须登记。"""
    required = {
        "asset",
        "report_type",
        "collected_data",
        "chart_data",
        "chart_paths",
        "compute_results",
        "report_text",
        "final_text",
        "gate_result",
        "gate_feedback",
    }
    missing = required - CONTEXT_KEYS
    assert not missing, f"契约缺核心键: {missing}"


@pytest.mark.unit
def test_new_context_defaults_and_overrides():
    ctx = new_context(asset="柯力传感", report_type="decision_memo")
    assert ctx["asset"] == "柯力传感"
    assert ctx["attempt"] == 0 and ctx["report_text"] == ""
    ctx2 = new_context(attempt=2)
    assert ctx2["attempt"] == 2


@pytest.mark.unit
def test_unknown_key_rejected():
    with pytest.raises(KeyError, match="未登记键"):
        new_context(asst_typo="x")


@pytest.mark.unit
def test_unknown_keys_detector():
    ctx = dict(new_context())
    ctx["_private_cache"] = True  # 私有键豁免
    ctx["totally_new_key"] = 1  # 未登记 → 应报
    drift = unknown_keys(ctx)
    assert drift == ["totally_new_key"]
