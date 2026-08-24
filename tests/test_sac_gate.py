"""P0: SAC Gate structured verification tests"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import (
    ArgumentScaffold, ArgumentSection, KnowledgePackage, SACEntry, SectionType,
)
from core.verify import SACGate


def _make_scaffold(sections: list[ArgumentSection]) -> ArgumentScaffold:
    return ArgumentScaffold(
        brief_id="test", title="test",
        core_disagreement={},
        sections=sections,
    )


def _make_kp_with_sac(sac_id: str = "sac_test", dimensions: list[dict] | None = None) -> KnowledgePackage:
    kp = KnowledgePackage()
    kp.sac = SACEntry(
        sac_id=sac_id,
        applies_to=["listed_company"],
        required_dimensions=dimensions or [],
        evidence_requirements={"min_sources": 1, "counter_evidence_required": False},
        forbidden_patterns=["SAC"],
    )
    return kp


def test_no_sac_config():
    """No SAC → check fails gracefully."""
    gate = SACGate()
    scaffold = _make_scaffold([])
    kp = KnowledgePackage()
    result = gate.check(scaffold, kp)
    assert result.get("passed") is False
    assert "no SAC" in result.get("error", "")
    print(f"  [PASS] test_no_sac_config")


def test_empty_dimensions():
    """No dimensions → check passes (nothing to check)."""
    gate = SACGate()
    scaffold = _make_scaffold([ArgumentSection(section_id="s1", title="主营业务")])
    kp = _make_kp_with_sac()
    result = gate.check(scaffold, kp)
    assert result.get("passed") is True
    print(f"  [PASS] test_empty_dimensions")


def test_dimension_covered():
    """Section matches SAC dimension → check passes."""
    gate = SACGate()
    scaffold = _make_scaffold([
        ArgumentSection(section_id="s1", title="商业模式", thesis="公司的商业模式是什么",
                        evidence_ids=["ev_001"]),
    ])
    kp = _make_kp_with_sac(dimensions=[
        {"id": "business_model", "question": "公司的商业模式是什么", "evidence_min": 1},
    ])
    result = gate.check(scaffold, kp)
    assert result.get("passed") is True
    chk = result["checks"]
    assert chk[0]["dim"] == "business_model"
    assert chk[0]["passed"] is True
    print(f"  [PASS] test_dimension_covered")


def test_dimension_missing():
    """No matching section → check fails."""
    gate = SACGate()
    scaffold = _make_scaffold([
        ArgumentSection(section_id="s1", title="无关话题", thesis="不相关内容"),
    ])
    kp = _make_kp_with_sac(dimensions=[
        {"id": "business_model", "question": "公司的商业模式是什么", "evidence_min": 1},
    ])
    result = gate.check(scaffold, kp)
    assert result.get("passed") is False
    print(f"  [PASS] test_dimension_missing")


def test_insufficient_evidence():
    """Section found but evidence count < min → check fails."""
    gate = SACGate()
    scaffold = _make_scaffold([
        ArgumentSection(section_id="s1", title="商业模式", thesis="商业模式分析", evidence_ids=[]),
    ])
    kp = _make_kp_with_sac(dimensions=[
        {"id": "business_model", "question": "商业模式", "evidence_min": 2},
    ])
    result = gate.check(scaffold, kp)
    assert result.get("passed") is False
    chk = result["checks"]
    assert chk[0]["ecnt"] == 0
    assert chk[0]["emin"] == 2
    print(f"  [PASS] test_insufficient_evidence")


def test_multiple_dimensions_mixed():
    """Mixed: one dimension covered, one missing."""
    gate = SACGate()
    scaffold = _make_scaffold([
        ArgumentSection(section_id="s1", title="商业模式", thesis="商业模式分析",
                        evidence_ids=["ev_001"]),
    ])
    kp = _make_kp_with_sac(dimensions=[
        {"id": "bm", "question": "商业模式", "evidence_min": 1},
        {"id": "finance", "question": "财务表现", "evidence_min": 1},
    ])
    result = gate.check(scaffold, kp)
    assert result.get("passed") is False
    checks = result["checks"]
    bm = [c for c in checks if c["dim"] == "bm"]
    fn = [c for c in checks if c["dim"] == "finance"]
    assert len(bm) == 1 and bm[0]["passed"] is True
    assert len(fn) == 1 and fn[0]["passed"] is False
    print(f"  [PASS] test_multiple_dimensions_mixed")


if __name__ == "__main__":
    n_pass = 0
    n_fail = 0
    for name in sorted(dir()):
        if name.startswith("test_"):
            try:
                globals()[name]()
                n_pass += 1
            except Exception as e:
                import traceback
                print(f"  [FAIL] {name}: {e}")
                traceback.print_exc()
                n_fail += 1
    print(f"\n=== {n_pass} passed, {n_fail} failed ===")
