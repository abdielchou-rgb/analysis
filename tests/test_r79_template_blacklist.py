"""R79 P0-1 — 模板句黑名单回归测试。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_blacklist_detects_repeat():
    """模板句重复应被拦截。"""
    from core.template_blacklist import scan

    text = (
        "这一趋势若被证实，将显著改变我们对行业格局的既有认知。这一趋势若被证实，将显著改变我们对行业格局的既有认知。"
    )
    r = scan(text)
    assert r["total_exact"] >= 2, f"应检测到重复模板句: {r}"


def test_normal_text_no_hits():
    """正常文本不应误报。"""
    from core.template_blacklist import scan

    text = "2025年营收15.58亿元，磁致伸缩良率92%突破，招标量环比+20%，执行率从62%升至85%。"
    r = scan(text)
    assert r["total_exact"] == 0, f"正常文本不应命中: {r}"


def test_gate_blocks_template():
    """IronGate 模板句检查应拦截污染报告。"""
    from pipeline.iron_gate import IronGate

    ig = IronGate.__new__(IronGate)
    ig.report_text = (
        "这一趋势若被证实，将显著改变我们对行业格局的既有认知。上述判断仍面临需求端波动带来的下行风险扰动。" * 5
    )
    r = ig._check_template_phrases()
    assert not r.passed, "模板污染应被拦截"
    assert r.severity == "error", f"应 error 级: {r.severity}"


def test_gate_passes_clean():
    """干净文本应通过。"""
    from pipeline.iron_gate import IronGate

    ig = IronGate.__new__(IronGate)
    ig.report_text = "2025年营收15.58亿元，磁致伸缩良率92%，招标量+20%。" * 8
    r = ig._check_template_phrases()
    assert r.passed, f"干净文本应通过: {r.details}"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  OK {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
