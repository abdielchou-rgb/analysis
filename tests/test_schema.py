"""P0: core.models core data model tests"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import (
    ArgumentScaffold,
    ArgumentSection,
    Deliverable,
    Direction,
    EditCase,
    EditingType,
    EvidenceItem,
    EvidenceLevel,
    InputMode,
    KnowledgePackage,
    ReportType,
    SectionType,
    WritingBrief,
)


def test_writing_brief_creation():
    b = WritingBrief()
    assert b.asset == ""
    assert b.brief_id != ""
    assert b.created_at != ""
    print("  [PASS] test_writing_brief_creation")


def test_writing_brief_roundtrip():
    orig = WritingBrief(
        asset="贵州茅台 600519.SH",
        report_type=ReportType.EARNINGS_NOTES,
        input_mode=InputMode.STRUCTURED,
        core_thesis_direction=Direction.BULL,
        core_thesis_point="i茅台直销占比超预期",
        style_profile="cicc",
        hypothesis="茅台直销占比能否突破50%",
    )
    d = orig.to_dict()
    assert d["hypothesis"] == "茅台直销占比能否突破50%"
    restored = WritingBrief.from_dict(d)
    assert restored.hypothesis == orig.hypothesis
    print("  [PASS] test_writing_brief_roundtrip")


def test_argument_scaffold_creation():
    sections = [
        ArgumentSection(
            section_id="s1",
            title="核心分歧",
            section_type=SectionType.JUDGMENT,
            thesis="市场认为45%是天花板，但我们认为可突破50%",
            counter_thesis="直销占比提升边际递减是合理的",
            evidence_ids=["ev_001", "ev_002"],
            counter_evidence_ids=["ev_003"],
            required_citations=2,
            has_alternative_view=True,
        ),
    ]
    scaffold = ArgumentScaffold(
        brief_id="WB_test_001",
        title="茅台：直销占比的结构性突破",
        core_disagreement={"market": "45%天花板", "our": "可突破50%"},
        sections=sections,
    )
    assert len(scaffold.sections) == 1
    assert scaffold.sections[0].required_citations == 2
    assert len(scaffold.sections[0].evidence_ids) >= 1
    print("  [PASS] test_argument_scaffold_creation")


def test_evidence_level_ordering():
    assert EvidenceLevel.FILING.value == "L1_filing"
    assert EvidenceLevel.PENDING.value == "L9_pending"
    print("  [PASS] test_evidence_level_ordering")


def test_edit_case_creation():
    ec = EditCase(
        case_id="EC_test_001",
        correction_type=EditingType.BIASED_JUDGMENT,
        original_text="直销占比必将突破50%",
        correction_action="必将 -> 有望",
        corrected_text="直销占比有望突破50%",
    )
    assert ec.correction_type == EditingType.BIASED_JUDGMENT
    print("  [PASS] test_edit_case_creation")


def test_knowledge_package():
    kp = KnowledgePackage()
    assert len(kp.evidence_items) == 0
    kp.evidence_items.append(
        EvidenceItem(
            content="2024H1 直销占比 42%",
            source="年报",
            level=EvidenceLevel.FILING,
            support_direction="for",
        )
    )
    assert len(kp.evidence_items) == 1
    print("  [PASS] test_knowledge_package")


def test_deliverable_creation():
    d = Deliverable(report_md="# Test Report", export_paths={"md": "outputs/test.md"})
    assert d.report_md == "# Test Report"
    print("  [PASS] test_deliverable_creation")


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
