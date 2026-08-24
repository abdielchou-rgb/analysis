"""golden eval 门禁回归测试。

P3-audit 2026-08-24：黄金样本必须永远通过自己的基线——
若门禁逻辑变更导致 golden 集失败，说明生产报告也将被阻断，CI 拦下。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from tests.golden.eval_gate import evaluate_report

GOLDEN_SAMPLES = sorted(f for f in (_ROOT / "tests" / "golden").glob("*.md") if f.stat().st_size > 1000)


@pytest.mark.golden
@pytest.mark.parametrize("md", GOLDEN_SAMPLES, ids=lambda p: p.name)
def test_golden_sample_passes_eval_gate(md):
    r = evaluate_report(md)
    assert r["passed"], f"golden 样本未过门禁: {r['failures']}"


@pytest.mark.unit
def test_eval_gate_rejects_degenerate_report(tmp_path):
    """退化报告（超短/无判断）必须被门禁拦截——gate 必须有牙齿。"""
    bad = tmp_path / "bad.md"
    bad.write_text("# 标题\n\n太短了，什么都没有。" * 10, encoding="utf-8")
    r = evaluate_report(bad)
    assert not r["passed"]
    assert any("absolute" in f for f in r["failures"])
