"""Tests for QualityScorer."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.quality_scorer import QualityScorer


def _report(urgency=True, surprise=True, numbers=True, reasoning=True,
            sections=True, evidence=True, action=True, precision=True):
    parts = ["# Report\n"]
    if urgency:
        parts.append("关键分歧在于市场忽略了茅台的定价能力。\n")
    else:
        parts.append("这是一个分析报告。\n")
    if surprise:
        parts.append("但我们的判断不同：市场共识认为有限，我们认为不同。\n")
    else:
        parts.append("整体来看，表现较好。\n")
    if numbers:
        parts.append("2025年营收达1500亿元，同比增长15%。\n")
    else:
        parts.append("营收有较大幅度增长。\n")
    if reasoning:
        parts.append("因为产能受限导致供给不足，因此批价持续上行。\n")
    else:
        parts.append("产能和价格是因素。\n")
    if sections:
        parts.extend([
            "## 核心分歧：我们认为市场低估了定价权\n",
            "## 估值分析：我们认为估值合理\n",
            "## 风险提示：我们认为需关注风险\n",
        ])
    else:
        parts.append("## 单一章节\n")
    if evidence:
        parts.append("从我的行业经验来看，公司年报数据（来源：年报），直销收入占比45%。从历史规律来看，白酒行业十年周期上行期批价持续创新高。\n")
    else:
        parts.append("直销收入表现良好。\n")
    if action:
        parts.append("建议买入，预计目标价2500元。\n")
    else:
        parts.append("需持续关注。\n")
    if precision:
        parts.append("目标价区间2500+/-200元，概率85%，测算假设为2026年PE 25x，模型计算结果。\n")
    else:
        parts.append("目标价有待观察。\n")
    return "".join(parts)


def test_full_report_passes():
    scorer = QualityScorer()
    text = _report()
    result = scorer.score(text)
    assert result.overall >= 0.60, f"Expected >= 0.60, got {result.overall}"
    assert result.passed
    for dim in scorer.WEIGHTS:
        ds = getattr(result, dim, None)
        assert ds is not None, f"Missing dim {dim}"
        assert 0 <= ds.score <= 1.0, f"{dim} score {ds.score} out of range"


def test_poor_report_fails():
    scorer = QualityScorer()
    text = _report(urgency=False, surprise=False, numbers=False, reasoning=False,
                   evidence=False, action=False, precision=False)
    result = scorer.score(text)
    assert result.overall <= 0.65, f"Expected <= 0.65, got {result.overall}"


def test_empty_text():
    scorer = QualityScorer()
    result = scorer.score("")
    assert isinstance(result.overall, float)
    assert not result.passed


def test_short_text():
    scorer = QualityScorer()
    result = scorer.score("Hello world.")
    assert isinstance(result.overall, float)


def test_report_output():
    scorer = QualityScorer()
    result = scorer.score("key分歧 我们认为观点\n据年报来源数据\n建议买入\n")
    report = scorer.report(result)
    assert "Quality Score" in report


def test_per_section():
    scorer = QualityScorer()
    text = "## Section A\ncontent\n## Section B\ncontent\n"
    result = scorer.score(text)
    assert isinstance(result.per_section, dict)


def test_all_dims_positive_good_report():
    scorer = QualityScorer()
    text = _report()
    result = scorer.score(text)
    for dim in scorer.WEIGHTS:
        ds = getattr(result, dim)
        assert ds.score > 0, f"{dim} scored 0 on good report"


if __name__ == "__main__":
    test_full_report_passes()
    test_poor_report_fails()
    test_empty_text()
    test_short_text()
    test_report_output()
    test_per_section()
    test_all_dims_positive_good_report()
    print("All quality_scorer tests passed")
