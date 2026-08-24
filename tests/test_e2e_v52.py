"""V52 E2E integration tests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.quality_scorer import QualityScorer
from core.enforcer import Enforcer


def test_modules_import():
    from core.quality_scorer import QualityScorer as QS
    from core.enforcer import Enforcer as Enf
    from core.calibration import CalibrationDashboard as CD
    assert QS is QualityScorer
    assert Enf is Enforcer
    assert CD is not None


def test_quality_then_enforce():
    text = (
        "# 贵州茅台分析\n"
        "## 核心分歧：我们认为市场低估了定价权\n"
        "content\n"
        "据公司年报数据，营收增长15%。\n"
        "反方观点认为过于乐观。\n"
        "如果需求下行，需注意风险。\n"
        "建议买入\n"
    )
    scorer = QualityScorer()
    qs = scorer.score(text)
    assert isinstance(qs.overall, float)

    enf = Enforcer()
    result = enf.enforce(text, required_dims=["核心分歧"])
    assert isinstance(result.passed, bool)


if __name__ == "__main__":
    test_modules_import()
    test_quality_then_enforce()
    print("All V52 E2E tests passed")
