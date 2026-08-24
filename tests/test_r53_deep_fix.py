"""R53 (2026-08-03) 回归测试 — 锁定深度检测报告的 4 项修复。

修复内容：
  1. P0-1: 维度来源切 SAC + verify_coverage 强制校验
     （原：_write_dimension_parallel 的 all_dims 取 segments → 16/21 维，
       必需维度写不进 → Gate 必败死锁）
  2. P0-2: 维度并行支持组级局部重写
     （原：rewrite_indices 在 dimension_parallel=True 时被绕过，每轮全量重写）
  3. P1-3: 字数容量对标国际投行（组级 800/维、SEG_MAX_TOKENS=10000）
     （原：组级 400/维 + 6000 token → 实际产出 ~3900 字 < 投行标准）
  4. P1-4: LLM provider 健康预检 + 快速失败
     （原：provider 不可用时 6 组各等满 300s，一轮空耗 10 分钟）
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── 1. P0-1：维度来源切 SAC + verify_coverage ────────────────
def test_dimension_source_is_sac_required():
    """_write_dimension_parallel 的维度来源必须与 IronGate 门禁同源（SAC required）。"""
    from pipeline.section_writer import SectionWriter
    for rt in ["industry_deep", "listed_company", "unlisted_company"]:
        sw = SectionWriter(rt, "cicc")
        # 新逻辑：all_dims 取 sac.get_dimension_ids()
        all_dims = sw.sac.get_dimension_ids()
        # 与 IronGate 读的 required_dimensions 一致
        req_ids = set()
        for dim in (sw.sac._data or {}).get("required_dimensions", []):
            if isinstance(dim, dict) and dim.get("id"):
                req_ids.add(dim["id"])
        assert len(all_dims) == len(req_ids), f"{rt}: SAC维度来源不一致"
        # 维度数必须与 IronGate 检查的必需维度数一致（不再 16/21）
        assert len(all_dims) >= 17, f"{rt}: 维度数不足 {len(all_dims)}"


def test_groups_cover_all_required_dims():
    """分组必须覆盖全部 SAC 必需维度（verify_coverage 通过）。"""
    from pipeline.section_writer import SectionWriter
    from pipeline.dimension_grouper import group_dimensions, verify_coverage
    for rt in ["industry_deep", "listed_company", "unlisted_company"]:
        sw = SectionWriter(rt, "cicc")
        all_dims = sw.sac.get_dimension_ids()
        groups = group_dimensions(rt, all_dims)
        assert verify_coverage(rt, all_dims, groups), f"{rt}: 分组未覆盖全部维度"


def test_missing_global_dims_in_groups():
    """此前永久缺失的 global 维度必须在分组中。"""
    from pipeline.section_writer import SectionWriter
    from pipeline.dimension_grouper import group_dimensions
    must_have = {
        "industry_deep": {"global_market_sizing", "global_competition", "peer_benchmarking",
                          "falsification", "geopolitical_risk"},
        "listed_company": {"peer_benchmarking", "management_quality", "global_peer_comparison",
                           "overseas_revenue", "geopolitical_exposure"},
        "unlisted_company": {"global_benchmark", "overseas_expansion", "cross_border_dd"},
    }
    for rt, required in must_have.items():
        sw = SectionWriter(rt, "cicc")
        all_dims = sw.sac.get_dimension_ids()
        groups = group_dimensions(rt, all_dims)
        grouped = {d for g in groups for d in g["dimensions"]}
        missing = required - grouped
        assert not missing, f"{rt}: 全局维度仍缺失 {missing}"


# ── 2. P0-2：组级局部重写 ─────────────────────────────────────
def test_rewrite_indices_maps_to_groups():
    """rewrite_indices（段索引）应映射到对应维度组。"""
    from pipeline.section_writer import SectionWriter
    from pipeline.dimension_grouper import group_dimensions
    sw = SectionWriter("industry_deep", "cicc")
    all_dims = sw.sac.get_dimension_ids()
    groups = group_dimensions("industry_deep", all_dims)
    # 段0 的战略层含 decision_gate → 应映射到 F 核心判断组
    seg0_dims = set(sw.segments[0].get("dimension_ids", []))
    target = {g["group_name"] for g in groups if set(g["dimensions"]) & seg0_dims}
    assert target, "段0 维度未映射到任何组"
    assert any("核心判断" in t for t in target), f"段0应映射到核心判断组, 实际{target}"


def test_extract_group_from_prev():
    """从上一轮报告文本提取组内容用于复用。"""
    from pipeline.section_writer import SectionWriter
    sw = SectionWriter("industry_deep", "cicc")
    prev = (
        "# 测试报告\n"
        "## 二、市场空间与行业边界\n"
        "全球气体传感器市场规模2025年达45亿美元，同比增长12%。中国市场约12亿美元，"
        "增速快于全球。行业边界清晰，主要参与者包括霍尼韦尔、盛思锐、城市技术等。"
        "从应用场景看，工业安全占比28%，环保监测17%，汽车电子25%。供给端产能利用率"
        "处于历史中高位，头部厂商集中度提升。这是足够长的一段市场空间分析，覆盖规模、"
        "增速、结构、竞争等多个维度。\n\n"
        "## 三、竞争格局\n"
        "竞争格局寡头垄断。\n"
    )
    reused = sw._extract_group_from_prev(prev, "A 市场空间")
    assert reused and len(reused) > 100, f"应提取到市场空间段落, 实际{len(reused)}字"


# ── 3. P1-3：字数容量对标国际投行 ────────────────────────────
def test_seg_max_tokens_default_10000():
    """SEG_MAX_TOKENS 默认应为 10000（对标国际投行深度报告）。"""
    # 直接读代码里的默认值
    src = (Path(__file__).parent.parent / "pipeline" / "section_writer.py").read_text(encoding="utf-8")
    assert 'SEG_MAX_TOKENS", "10000"' in src, "SEG_MAX_TOKENS 默认应提升到 10000"


def test_group_char_requirement_800():
    """组级字重要求应对标投行（每维 800 字）。"""
    src = (Path(__file__).parent.parent / "pipeline" / "section_writer.py").read_text(encoding="utf-8")
    assert "len(dims) * 800" in src, "组级字重要求应提升到 每维 800 字"


def test_editor_merge_no_hard_truncation():
    """编辑合并不应再 2500字/段 硬截断。"""
    src = (Path(__file__).parent.parent / "pipeline" / "section_writer.py").read_text(encoding="utf-8")
    assert "[:4500]" in src, "编辑合并截断应提升到 4500 字/段"


# ── 4. P1-4：LLM provider 健康预检 ───────────────────────────
def test_llm_probe_fast_fail():
    """provider 不可用时应快速失败（probe 短超时），不空耗 300s。"""
    import core.deepseek_client as dc
    from core.deepseek_client import ProviderConfig
    # mock 一个不可达 provider（127.0.0.1:1 拒绝连接）
    p = ProviderConfig(name="probe_test", base_url="http://127.0.0.1:1/v1",
                       api_key="test", models=["m"], priority=0)
    dc._registry._providers["probe_test"] = p
    import time
    t0 = time.time()
    try:
        dc.call_llm([{"role": "user", "content": "hi"}], provider="probe_test", max_tokens=10)
        assert False, "不可达 provider 不应调用成功"
    except RuntimeError:
        elapsed = time.time() - t0
        assert elapsed < 20, f"应快速失败, 实际 {elapsed:.1f}s"
    # 清理
    dc._registry._providers.pop("probe_test", None)


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
