"""R53审计 (2026-08-03) 回归测试 — 正则漏洞修复：市占率 + 同义词簇归一化。

问题：RATIO_PATTERN 只匹配"渗透率|占比|份额"，"市占率"不命中。
      执行者把"市场份额"→"市占率"即绕过一致性检测。
修复：RATIO_PATTERN 加"市占率|市场占有率"；同义词簇归一化
      （市占率/市场份额/市场占有率/份额 → 市占率）。
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_ratioshizhanlv_detected():
    """市占率表述应被占比簇提取（此前漏检）。"""
    from pipeline.consistency_engine import ConsistencyEngine
    text = (
        "公司市占率约为45%，位居行业前列。"
        "公司市占率约30%，出现明显下滑。"
    )
    r = ConsistencyEngine().check(text)
    # 两个市占率 45% vs 30% 应归入同一簇并检出矛盾（偏差33%>30%）
    assert not r["passed"], f"市占率矛盾应检出: {r['conflicts']}"
    # 簇名应含"市占率"
    assert any("市占率" in k for k in r["clusters"]), f"簇应含市占率: {r['clusters']}"


def test_synonym_normalization_conflict():
    """同义词归一化：市场份额 vs 市占率 应归入同一簇并检出矛盾。"""
    from pipeline.consistency_engine import ConsistencyEngine
    text = (
        "公司市场份额约为45%，位居行业前列。"
        "公司市占率约30%，出现明显下滑。"
    )
    r = ConsistencyEngine().check(text)
    assert not r["passed"], f"同义词矛盾应检出: {r['conflicts']}"
    # 簇名应归一化到同一 canonical 词
    assert any("市占率" in k for k in r["clusters"]), f"簇应归一化到市占率: {r['clusters']}"


def test_consistent_ratio_passes():
    """相同占比值（无矛盾）应通过。"""
    from pipeline.consistency_engine import ConsistencyEngine
    text = (
        "公司市场份额约为45%，位居行业前列。"
        "公司市占率约为45%，保持稳定。"
    )
    r = ConsistencyEngine().check(text)
    assert r["passed"], f"一致占比不应检出冲突: {r['conflicts']}"


def test_penetration_still_detected():
    """原有渗透率检测不受影响。"""
    from pipeline.consistency_engine import ConsistencyEngine
    text = (
        "行业渗透率约为25%。"
        "行业渗透率约40%。"
    )
    r = ConsistencyEngine().check(text)
    assert not r["passed"], f"渗透率矛盾应检出: {r['conflicts']}"


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
