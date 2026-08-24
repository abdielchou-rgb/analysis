"""标准一致性回归测试 — 防止图表/表格标准系统性降级

背景（2026-08-01 审计）：
  发现图表标准系统性降级——listed_company 有完整 chart_config（21图/15表），
  而 unlisted/industry/earnings 靠硬编码回退只有 4-5 图，且 IronGate 的
  min_charts 也是硬编码（低于 SAC）。"对标顶级机构"仅存在于注册表。

本测试锁定修复后的标准（见 docs/STANDARDS.md）：
  1. 每类报告 SAC 有 chart_config 且 min_charts ≥ 基线
  2. get_chart_config 缺配置时抛错（fail-fast，不静默回退）
  3. IronGate min_charts 与 SAC 一致（单一事实源）
  4. chart_pipeline 模板 id 与 SAC chart_config id 对齐（无映射层）
  5. IronGate 有 A/E/F/B 标注检查
"""

import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.sacs import SACLoader
from pipeline.iron_gate import IronGate

# STANDARDS.md 基线
STANDARDS_BASE = {
    "industry_deep": {"min_charts": 12, "min_tables": 4},
    "listed_company": {"min_charts": 12, "min_tables": 4},
    "unlisted_company": {"min_charts": 8, "min_tables": 3},
    "earnings_notes": {"min_charts": 4, "min_tables": 2},
}
REPORT_TYPES = list(STANDARDS_BASE.keys())


# ── 1. 每类报告 SAC 有 chart_config 且 min_charts ≥ 基线 ──────
def test_sac_chart_config_meets_standards():
    for rt in REPORT_TYPES:
        sac = SACLoader(rt)
        cc = sac.get_chart_config()
        assert cc.get("charts"), f"{rt} chart_config 缺 charts"
        assert cc.get("min_charts", 0) >= STANDARDS_BASE[rt]["min_charts"], (
            f"{rt} min_charts={cc.get('min_charts')} < 基线 {STANDARDS_BASE[rt]['min_charts']}"
        )
        assert cc.get("min_tables", 0) >= STANDARDS_BASE[rt]["min_tables"], (
            f"{rt} min_tables={cc.get('min_tables')} < 基线 {STANDARDS_BASE[rt]['min_tables']}"
        )
        # 模板 id 唯一
        ids = [c["id"] for c in cc["charts"]]
        assert len(ids) == len(set(ids)), f"{rt} 图表 id 重复: {ids}"
        # 每张图有 id/type/caption
        for c in cc["charts"]:
            for k in ("id", "type", "caption"):
                assert k in c, f"{rt} 图 {c.get('id')} 缺 {k}"


# ── 2. get_chart_config 缺配置时抛错（fail-fast）──────────────
def test_get_chart_config_fails_fast_without_config():
    import core.sacs as sacs

    class FakeSAC(sacs.SACLoader):
        def __init__(self):
            self._data = {"id": "fake"}
            self.report_type = "fake_type"
            self._loaded = True

    try:
        FakeSAC().get_chart_config()
        assert False, "缺配置应抛 ValueError，不能静默回退"
    except ValueError as e:
        assert "chart_config" in str(e)


# ── 3. IronGate min_charts 与 SAC 一致 ────────────────────────
def test_irongate_min_charts_matches_sac():
    for rt in REPORT_TYPES:
        sac = SACLoader(rt)
        sac_mc = sac.get_chart_config()["min_charts"]
        tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8")
        tmp.write("# test\ncontent")
        tmp.close()
        try:
            ig = IronGate(tmp.name, rt, "cicc")
        finally:
            os.unlink(tmp.name)
        assert ig.min_charts == sac_mc, f"{rt} IronGate.min_charts={ig.min_charts} != SAC {sac_mc}"
        assert ig.min_charts >= STANDARDS_BASE[rt]["min_charts"], f"{rt} IronGate.min_charts={ig.min_charts} < 基线"


# ── 4. chart_pipeline 模板 id 与 SAC chart_config id 对齐 ─────
def test_chart_pipeline_ids_match_sac():
    import pipeline.chart_pipeline as cp_mod

    for rt in REPORT_TYPES:
        sac = SACLoader(rt)
        sac_ids = {c["id"] for c in sac.get_chart_config()["charts"]}
        tmpl_ids = {t["id"] for t in cp_mod.CHART_TEMPLATES.get(rt, [])}
        # 模板 id 应是 SAC id 的子集（模板只实现 SAC 声明的图）
        extra = tmpl_ids - sac_ids
        assert not extra, f"{rt} chart_pipeline 有模板 id 不在 SAC 中: {extra}"


# ── 5. IronGate 有 A/E/F/B 标注检查 ──────────────────────────
def test_irongate_has_annotation_check():
    tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8")
    tmp.write("# 报告\n内容")
    tmp.close()
    try:
        ig = IronGate(tmp.name, "unlisted_company", "cicc")
    finally:
        os.unlink(tmp.name)
    names = [c.name for c in ig.run_all().checks]
    assert "annotation_types" in names, f"IronGate 缺 annotation_types 检查: {names}"
    assert hasattr(ig, "_check_annotation_types")


# ── 6. 缺 SAC 时 IronGate 用基线兜底（不应依赖硬编码降级）─────
def test_irongate_baseline_fallback():
    """SAC 缺配置时 IronGate 应使用 STANDARDS 基线，而非旧硬编码 4/5。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8")
    tmp.write("# 报告\n内容")
    tmp.close()
    try:
        # 模拟 SAC 加载失败 → get_chart_config 抛错 → 用基线兜底
        orig = SACLoader.get_chart_config
        SACLoader.get_chart_config = lambda self: (_ for _ in ()).throw(ValueError("SAC 缺 chart_config"))
        try:
            ig = IronGate(tmp.name, "unlisted_company", "cicc")
        finally:
            SACLoader.get_chart_config = orig
        # 基线：unlisted = 8
        assert ig.min_charts == 8, f"fallback min_charts={ig.min_charts} 应为 8"
    finally:
        os.unlink(tmp.name)


# ── 7. 图真实生成（mock 数据 → generate_all → PNG 存在）────────
def test_charts_actually_generate():
    """配置存在 ≠ 图能生成。用 mock 数据跑 generate_all，断言 SAC 声明的每张图 PNG 存在。

    2026-08-01 修复：原标准测试只验证 id 对齐，未验证数据格式匹配——
    导致 fig_financial_trends（dual_axis 需 revenue+profit）实际生成失败。
    """
    import matplotlib

    matplotlib.use("Agg")
    from pipeline.chart_pipeline import ChartPipeline

    # 构造覆盖所有图型的 mock 数据
    mock_chart_data = {
        # 财务趋势（dual_axis）
        "fig_revenue_trend": {"2023": 5.39, "2024": 6.01, "2025": 6.88},
        "fig_profitability": {"2023": -1.36, "2024": -1.58, "2025": -0.80},
        # 业务模型（bar）
        "fig_business_model": {"业务A": 40, "业务B": 35, "业务C": 25},
        # 市场定位（radar）
        "fig_market_positioning": {"技术": 9, "市场": 7, "客户": 8},
        # 增长驱动（line）
        "fig_growth_drivers": {"驱动1": 4, "驱动2": 3, "驱动3": 2},
        # 竞争格局（bar_cluster）
        "fig_competitive_landscape": {"技术": 9, "市占": 7, "研发": 8},
        # 市场规模（bar）
        "fig_market_size_global": {"2020": 134, "2025": 465, "2030E": 1264},
        "fig_market_size_china": {"2020": 52, "2025": 192, "2030E": 473},
        # 融资历史（bar）
        "fig_funding_history": {"B轮": 20, "C轮": 30, "增资": 64},
        # 产业链（waterfall）
        "fig_industry_chain": {"芯片": 5, "算法": 9, "终端": 4},
        # industry_deep SAC 12图补齐（2026-08-03）
        "fig_supply_demand": {"2020供给": 100, "2020需求": 85, "2025供给": 180, "2025需求": 220},
        "fig_profit_pool": {"环节A": 45, "环节B": 30, "环节C": 15, "环节D": 10},
        "fig_market_share": {"公司A": 35, "公司B": 25, "公司C": 15, "其他": 25},
        "fig_tech_trend": {"2020": 20, "2022": 45, "2024": 75, "2026E": 95},
        "fig_tech_segments": {"路线A": 50, "路线B": 30, "路线C": 15, "其他": 5},
        "fig_policy_impact": {"补贴": 8, "准入": 6, "关税": -3, "环保": 4},
        "fig_peer_comparison": {"公司A": {"营收增速": 25, "毛利率": 40}, "公司B": {"营收增速": 18, "毛利率": 35}},
        "fig_life_cycle": {"导入期": 5, "成长期": 40, "成熟期": 35, "衰退期": 20},
    }
    for rt in ["unlisted_company", "industry_deep"]:
        sac = SACLoader(rt)
        sac_ids = [c["id"] for c in sac.get_chart_config()["charts"]]
        cp = ChartPipeline(rt, "cicc")
        cp.output_dir = Path(tempfile.mkdtemp())
        paths, _tf = cp.generate_all({"chart_data": mock_chart_data, "sources": {"mock": "ok"}})
        missing = [i for i in sac_ids if i not in paths]
        assert not missing, f"{rt} 有图未生成: {missing}"
        # 断言 PNG 文件真实存在
        for i in sac_ids:
            p = Path(cp.output_dir) / f"{i}.png"
            assert p.exists() and p.stat().st_size > 0, f"{rt} 图 {i} PNG 不存在或为空"


# ── 8. 图表 schema 一致性（SAC/pipeline/enrich 对齐 chart_schema.json）──
def test_chart_schema_consistency():
    """chart_schema.json 是权威定义，SAC/pipeline/enrich 必须对齐。"""
    import subprocess

    r = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "check_chart_schema.py"), "--strict"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        cwd=str(_ROOT),
    )
    assert r.returncode == 0, f"图表 schema 不一致:\n{r.stdout}\n{r.stderr}"


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
