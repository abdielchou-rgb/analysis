"""test_module_version.py — P0-2 模块版本管理单测（2026-08-07）"""

import tempfile
from pathlib import Path

from core.module_version import ModuleVersion


def _mv():
    td = tempfile.mkdtemp()
    return ModuleVersion("测试标的", version_dir=Path(td))


def test_commit_version_increment():
    mv = _mv()
    v1 = mv.commit("founder_ri", "正文v1", {"frozen_facts": {"PE": 65}})
    v2 = mv.commit("founder_ri", "正文v2修复", {"frozen_facts": {"PE": 65}})
    assert v1["version"] == 1 and v2["version"] == 2
    assert mv.latest("founder_ri")["version"] == 2


def test_rollback():
    mv = _mv()
    mv.commit("founder_ri", "v1")
    mv.commit("founder_ri", "v2")
    rb = mv.rollback("founder_ri")
    assert rb["version"] == 1
    assert mv.latest("founder_ri")["version"] == 1


def test_dependents_impact_propagation():
    mv = _mv()
    dep_map = {"biz_model": ["founder_ri"], "valuation": ["biz_model", "founder_ri"]}
    deps = mv.dependents("founder_ri", dep_map)
    assert set(deps) == {"biz_model", "valuation"}


def test_mark_dirty_and_rollback_restore():
    mv = _mv()
    mv.commit("biz_model", "商业模型v1")
    mv.mark_dirty("biz_model", reason="上游founder_ri变更")
    assert mv.latest("biz_model")["status"] == "dirty"
    assert mv.latest("biz_model")["dirty_reason"].startswith("上游")
    mv.rollback("biz_model")
    assert mv.latest("biz_model")["status"] == "active"


def test_frozen_facts_preserved():
    mv = _mv()
    mv.commit("valuation", "估值段", {"frozen_facts": {"PE": 79.79, "target": 51.6}})
    latest = mv.latest("valuation")
    assert latest["frozen_facts"]["PE"] == 79.79
