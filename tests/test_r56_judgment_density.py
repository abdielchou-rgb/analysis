"""R56 (2026-08-03) 回归测试 — Gate 判断密度/数据密度阈值升级。

对标 methodology_backtest_deep.json 金牌报告基准：
  min_judgment_density = 1.2 判断/千字（金牌 p10）
  min_data_density = 5.0 数据/千字（金牌 p10）
"""

import os  # noqa: F401  (dead-import debt)
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _run(text, report_type="industry_deep"):
    from pipeline.iron_gate import IronGate

    gate = IronGate.from_text(text, report_type=report_type, style="cicc")
    return gate._check_judgment_density()


# 判断密集 + 数据密集的优质报告文本
_GOOD = (
    "我们判断行业处于成长期，预计2025年市场规模达45亿元，同比增长12%。"
    "我们认为龙头企业市占率有望提升至30%，给予增持评级，目标价25元。"
    "我们预计毛利率维持在40%以上，净利润增速超预期。"
    "风险提示：下游需求波动。催化剂：新产品放量。"
    "行业拐点临近，我们看好国产替代逻辑，建议关注龙头。"
    "营收从2023年12亿增至2025年18亿元，净利率15%。"
) * 6  # ~1000字


def test_judgment_density_registered():
    """检查应注册为类方法。"""
    from pipeline.iron_gate import IronGate

    assert hasattr(IronGate, "_check_judgment_density")


def test_good_report_passes():
    """判断密集+数据密集报告应通过。"""
    r = _run(_GOOD)
    assert r.passed, f"优质报告应通过: {r.details}"


def test_no_judgment_fails():
    """无判断词报告应拦截（只描述不判断）。"""
    text = (
        "本报告对行业进行分析。行业包括上游、中游、下游。上游提供原材料，"
        "中游进行加工制造，下游面向终端客户。产业链各环节相互关联。"
        "行业历史发展沿革清晰，经历了多轮周期。当前行业处于稳定状态。"
        "各方面数据表明行业运行平稳。综合来看行业保持常态。"
        "需要注意的是行业发展受多种因素影响。我们保持观察。"
    ) * 5
    r = _run(text)
    assert not r.passed, f"无判断应拦截: {r.details}"


def test_no_data_fails():
    """无数据点报告应拦截（判断无数据支撑）。"""
    text = (
        "我们判断行业前景良好，预计将保持增长。我们认为龙头优势明显，"
        "看好其长期发展。我们建议投资者关注，给予积极评价。"
        "我们预计趋势延续，判断拐点临近。我们认为风险可控，"
        "建议增持。我们看好行业格局优化。"
    ) * 8
    r = _run(text)
    assert not r.passed, f"无数据支撑应拦截: {r.details}"


def test_short_text_skipped():
    """短文本应跳过。"""
    r = _run("太短了")
    assert r.passed, "短文本应跳过"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
