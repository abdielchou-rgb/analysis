"""Tests for V52 Enforcer."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.enforcer import Enforcer, EnforcerConfig
from core.enforcer.checklist import ComplianceChecklist
from core.enforcer.schema import EnforcementResult


def _compliant():
    return (
        "# Test\n"
        "## 核心分歧：我们认为市场低估了风险\n"
        "content\n"
        "## 估值分析\n"
        "（来源：年报）数据\n"
        "## 风险提示\n"
        "如果市场下行，需注意风险。\n"
        "反方观点认为过于乐观。\n"
        "建议买入\n"
    )


def test_enforcer_passes_good():
    enf = Enforcer()
    text = _compliant()
    result = enf.enforce(text, sac_id="test", required_dims=["估值", "风险"])
    assert isinstance(result, EnforcementResult)
    assert result.passed, f"Fail: {result.schema_issues}"


def test_enforcer_fails_empty():
    enf = Enforcer()
    result = enf.enforce("")
    assert not result.passed


def test_enforcer_fails_no_sections():
    enf = Enforcer()
    result = enf.enforce("plain text")
    assert not result.schema_passed


def test_checklist_has_10_items():
    cl = ComplianceChecklist()
    text = _compliant()
    result = cl.run(text, required_dims=["风险"])
    assert len(result["items"]) >= 10


def test_checklist_detects_forbidden():
    cl = ComplianceChecklist()
    text = "值得注意的是，从某种程度上说，质量不错。\n## 核心分歧\ncontent\n"
    result = cl.run(text)
    failed = [i for i in result["items"] if not i.get("passed")]
    assert len(failed) > 0


def test_checklist_detects_no_disagreement():
    cl = ComplianceChecklist()
    text = "# Report\n## Section\ncontent\n"
    result = cl.run(text)
    cd = [i for i in result["items"] if i.get("check_id") == "core_disagreement"]
    assert cd and not cd[0]["passed"]


def test_enforcer_config():
    cfg = EnforcerConfig(require_schema=False, run_checklist=True)
    enf = Enforcer(config=cfg)
    assert enf.config == cfg


def test_enforce_section():
    enf = Enforcer()
    r = enf.enforce_section("## Test\n我们认为这是好标的\n", "test")
    assert isinstance(r, dict)
    assert "passed" in r


if __name__ == "__main__":
    test_enforcer_passes_good()
    test_enforcer_fails_empty()
    test_enforcer_fails_no_sections()
    test_checklist_has_10_items()
    test_checklist_detects_forbidden()
    test_checklist_detects_no_disagreement()
    test_enforcer_config()
    test_enforce_section()
    print("All enforcer tests passed")
