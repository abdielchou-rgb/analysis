"""R53 审计 (2026-08-03) 回归测试 — P0-2 组级局部重写死代码修复。

问题：_locate_failed_segments 遇全局失败（content_volume/annotation_types/排版/
      data_conflicts/template_repeat/so_what_chain）必 return None → rewrite_indices=None
      → 组级局部重写永不触发 → 每轮全量重写 → 3 轮 Gate 全堵。

修复：sac_dims + 全局失败并存时返回段索引（触发组级局部重写），
      纯全局失败才全量重写。组级 prompt 附加 gate_feedback。
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _make_sw(rt="industry_deep"):
    from pipeline.section_writer import SectionWriter
    return SectionWriter(rt, "cicc")


def _mock_segments(sw):
    """构造含 dimension_ids 的伪 segments（与真实 SegmentWriter.segments 同构）。"""
    segs = []
    for i, seg in enumerate(sw.segments):
        segs.append(seg)
    return segs


# ── 1. sac_dims + 全局失败并存 → 返回段索引（组级局部重写可触发）──
def test_global_fail_with_sac_dims_returns_segments():
    """sac_dims + 全局失败并存时，_locate_failed_segments 应返回段索引而非 None。

    核心场景：gas 报告 Gate 反馈 = sac_dims 缺失（decision_gate）+ content_volume 不足。
    修复前：全局失败短路 → None → 全量重写 → 3 轮无效。
    修复后：返回段索引 → 组级局部重写触发。
    """
    from pipeline.e2e_orchestrator import _locate_failed_segments
    sw = _make_sw("industry_deep")
    fb = ("[必需维度缺失=decision_gate] "
          "content_volume: 内容量不足，需扩充至 10000 字")
    ctx = {"gate_feedback": fb}
    idx = _locate_failed_segments(ctx, sw)
    assert idx is not None, "sac_dims+全局失败不应短路为 None"
    assert isinstance(idx, list) and len(idx) > 0
    # R59（2026-08-03）：logic_chain 调整后 decision_gate 归段1（竞争层）
    assert 1 in idx, "decision_gate 属段1(竞争层)"
    # 应记录两类失败，供 section_writer prompt 使用
    assert "sac_dims" in ctx["_gate_fail_types"]
    assert "content_volume" in ctx["_gate_fail_types"]


def test_pure_global_fail_still_full_rewrite():
    """纯全局失败（无 sac_dims）仍触发全量重写（return None）。"""
    from pipeline.e2e_orchestrator import _locate_failed_segments
    sw = _make_sw("industry_deep")
    fb = "content_volume: 字数不足，需扩充至 10000 字以上"
    ctx = {"gate_feedback": fb}
    idx = _locate_failed_segments(ctx, sw)
    assert idx is None, "纯全局失败应触发全量重写"
    assert "content_volume" in ctx["_gate_fail_types"]


def test_global_fail_types_recorded():
    """_gate_fail_types 应记录全部失败类型（含全局）。"""
    from pipeline.e2e_orchestrator import _locate_failed_segments
    sw = _make_sw("industry_deep")
    fb = "[必需维度缺失=decision_gate] content_volume: 不足 data_conflicts: 冲突"
    ctx = {"gate_feedback": fb}
    _locate_failed_segments(ctx, sw)
    types = ctx["_gate_fail_types"]
    assert "sac_dims" in types
    assert "content_volume" in types
    assert "data_conflicts" in types


# ── 2. 组级重写：非目标组从上一轮复用（含全局失败时仍在）──
def test_rewrite_group_names_when_mixed_failures():
    """组级局部重写目标组计算：只重写含失败段维度的组。"""
    from pipeline.section_writer import SectionWriter
    from pipeline.dimension_grouper import group_dimensions
    sw = SectionWriter("industry_deep", "cicc")
    all_dims = sw.sac.get_dimension_ids()
    groups = group_dimensions("industry_deep", all_dims)
    # 假设失败段=段0（战略层，含 decision_gate）
    seg0_dims = set(sw.segments[0].get("dimension_ids", []))
    target = {g["group_name"] for g in groups if set(g["dimensions"]) & seg0_dims}
    assert target, "段0 应映射到至少一个组"
    # 至少存在非目标组（否则无"复用"可言）
    all_groups = {g["group_name"] for g in groups}
    assert len(all_groups - target) > 0, "应存在非目标组用于复用"


def test_group_prompt_includes_gate_feedback():
    """组级 prompt 应包含上一轮评审反馈（gate_feedback）。"""
    src = (Path(__file__).parent.parent / "pipeline" / "section_writer.py").read_text(encoding="utf-8")
    assert "上一轮评审反馈" in src, "组级 prompt 应包含 gate_feedback"


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
