"""R26 中文名标的全链路回归测试（柯力传感）

背景（2026-08-02 全量修复缺陷1/2）：
  柯力传感用中文名跑 2 小时失败，根因是中文名→代码匹配失败致 0 图。
  本测试固化"中文名标的"为回归资产，防止复发：
    1. resolve_asset 中文名→代码解析
    2. _local_search 中文名能拿到核心财务
    3. enrich 历史报告提取 company_intro（防身份编造）
    4. DataSufficiencyChecker 语义键检查
    5. _locate_failed_segments 三类失败定位

本测试不跑完整 E2E（避免慢），聚焦 R26 修复的链路断点。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── 测试 1：resolve_asset 中文名→代码 ───────────────────────────
def test_resolve_asset_chinese_name():
    from core.asset_resolver import resolve_asset

    a = resolve_asset("柯力传感")
    assert a.code == "603662", f"柯力传感应解析为 603662, got {a.code}"
    assert a.market == "CN"
    assert a.has_name and a.has_code

    # 代码反查名字
    b = resolve_asset("603662")
    assert b.name == "柯力传感", f"603662 应反查为柯力传感, got {b.name}"

    # 混合形态
    c = resolve_asset("柯力传感(603662.SH)")
    assert c.code == "603662" and c.name == "柯力传感"

    # 港股
    d = resolve_asset("腾讯控股")
    assert d.market == "HK"


# ── 测试 2：_local_search 中文名能拿到核心财务 ──────────────────
def test_local_search_chinese_name():
    from pipeline.data_collector import DataCollectorV5

    local = DataCollectorV5()._local_search("柯力传感")
    assert isinstance(local, dict), "应返回 dict"
    assert local.get("fig_revenue_trend"), "中文名应能拿到营收趋势"
    assert local.get("fig_profitability"), "中文名应能拿到净利趋势"


# ── 测试 3：enrich 历史报告提取 company_intro ───────────────────
def test_enrich_company_intro_from_history():
    from pipeline.data_enrichment import LocalBackfill

    data = {"asset": "603662", "chart_data": {"fig_revenue_trend": {"2024": 12.95}, "fig_profitability": {"2024": 3.0}}}
    out = LocalBackfill.run("603662", data)
    cd = out.get("chart_data", {})
    intro = cd.get("company_intro", "")
    # 柯力传感历史报告有"应变式传感器"
    assert intro, "应从历史报告提取 company_intro"
    assert "传感器" in intro, f"company_intro 应含传感器业务描述, got: {intro[:60]}"


# ── 测试 4：DataSufficiencyChecker 语义键 ───────────────────────
def test_sufficiency_semantic_gap():
    from pipeline.data_enrichment import DataSufficiencyChecker

    # 无 company_intro → semantic_gap
    data_bad = {
        "asset": "603662",
        "chart_data": {"fig_revenue_trend": {"2024": 12.95}, "fig_profitability": {"2024": 3.0}},
    }
    r_bad = DataSufficiencyChecker.check(data_bad)
    assert "company_intro" in r_bad["semantic_gap"], "缺 company_intro 应报语义缺口"

    # 有 company_intro → 无 gap
    data_ok = {
        "asset": "603662",
        "chart_data": {
            "fig_revenue_trend": {"2024": 12.95},
            "fig_profitability": {"2024": 3.0},
            "company_intro": "应变式传感器龙头",
        },
    }
    r_ok = DataSufficiencyChecker.check(data_ok)
    assert "company_intro" not in r_ok["semantic_gap"], "有 company_intro 不应报语义缺口"


# ── 测试 5：_locate_failed_segments 三类失败定位 ────────────────
def test_locate_failed_segments_types():
    from pipeline.e2e_orchestrator import _locate_failed_segments

    class FakeSW:
        def __init__(self):
            self.segments = [
                {"dimension_ids": ["company_profile"], "label": "A 公司概况"},
                {"dimension_ids": ["core_disagreement", "bold_call"], "label": "B 核心判断"},
                {"dimension_ids": ["governance_esg"], "label": "C 治理"},
            ]

    sw = FakeSW()
    # SAC 维度缺失 → 定位段
    r1 = _locate_failed_segments({"gate_feedback": "[必需维度缺失=governance_esg]"}, sw)
    assert r1 == [2], f"SAC 维度缺失应定位到段 2, got {r1}"
    # 图表失败 → R66(2026-08-04): 不再短路全量重写，返回全段索引做局部补图引用
    r2 = _locate_failed_segments({"gate_feedback": "chart_completeness: 图嵌入 15/21"}, sw)
    assert r2 == [0, 1, 2], f"图表失败应全段局部重写, got {r2}"
    # 核心分歧 → 定位判断段
    r3 = _locate_failed_segments({"gate_feedback": "COMPLIANCE: 1 checks failed ['核心分歧已写']"}, sw)
    assert r3 == [1], f"核心分歧应定位到段 1, got {r3}"


if __name__ == "__main__":
    import traceback

    passed = 0
    failed = 0
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
