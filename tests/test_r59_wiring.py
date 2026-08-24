"""R59 (2026-08-03) 回归测试 — 接线验收 + 工具可调用性。

覆盖：
  - SAC 脏 ID 修复（elasticity_analysis【新增】→ 干净 ID）
  - 5 个新工具接线（compute_engine._run_tool_modules）
  - 接线验收脚本（check_wiring.py）
  - decision_gate 段位同步
"""

import os  # noqa: F401  (dead-import debt)
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── R59-1: SAC 脏 ID ─────────────────────────────
def test_sac_clean_ids():
    """SAC 维度不应含脏 ID（【新增】后缀）。"""
    from pipeline.section_writer import SectionWriter

    for rt in ["industry_deep", "listed_company", "unlisted_company"]:
        sw = SectionWriter(rt, "cicc")
        dims = sw.sac.get_dimension_ids()
        dirty = [d for d in dims if "【" in d or "】" in d]
        assert not dirty, f"{rt} 含脏ID: {dirty}"


def test_get_dimension_clean_hit():
    """get_dimension 干净 id 应命中。"""
    from pipeline.section_writer import SectionWriter

    sw = SectionWriter("industry_deep", "cicc")
    for d in ["elasticity_analysis", "signal_chain"]:
        assert sw.sac.get_dimension(d) is not None, f"get_dimension({d}) 应命中"


# ── R59-3: 工具接线 ──────────────────────────────
def test_tool_modules_wired():
    """compute_engine._run_tool_modules 应存在并接线 5 工具。"""
    from pipeline.compute_engine import ComputeEngine

    ce = ComputeEngine()
    data = {
        "chart_data": {
            "fig_valuation": {"industry": "半导体", "company": "中芯国际", "penetration_pct": 0.3, "growth_rate": 0.2}
        }
    }
    r = ce._run_tool_modules(data)
    assert r.get("status") == "ok", f"应ok: {r.get('status')}"
    assert r.get("ok_count", 0) >= 4, f"应≥4工具ok: {r.get('ok_count')}"
    # 关键工具应返回结构化数据
    assert "elasticity" in r["modules"], "应含弹性分析"
    assert "signal_chain" in r["modules"], "应含信号链"
    assert "life_cycle" in r["modules"], "应含生命周期"
    assert "moat" in r["modules"], "应含护城河"


def test_tool_modules_graceful_skip():
    """无行业/公司数据时工具应优雅 skip 不抛异常。"""
    from pipeline.compute_engine import ComputeEngine

    ce = ComputeEngine()
    r = ce._run_tool_modules({})
    assert r is not None, "应返回 dict"
    assert isinstance(r.get("modules"), dict), "应含 modules dict"


# ── R59-2: 接线验收脚本 ──────────────────────────
def test_check_wiring_script_exists():
    """check_wiring.py 应存在。"""
    assert (_ROOT / "scripts" / "check_wiring.py").exists()


def test_check_wiring_passes():
    """接线验收脚本应全部通过（数据底座维度视为已接线）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_wiring", _ROOT / "scripts" / "check_wiring.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    report = mod.check()
    results = report["results"]
    unwired = [r for r in results if r["status"] == "unwired"]
    missing = [r for r in results if r["status"] == "missing"]
    assert not unwired, f"存在未接线维度: {unwired}"
    assert not missing, f"存在工具缺失: {missing}"


# ── R59-5: decision_gate 段位 ────────────────────
def test_decision_gate_segment():
    """decision_gate 应在段1（竞争层）。"""
    from pipeline.section_writer import SectionWriter

    sw = SectionWriter("industry_deep", "cicc")
    found = None
    for i, s in enumerate(sw.segments):
        if "decision_gate" in s.get("dimension_ids", []):
            found = i
            break
    assert found == 1, f"decision_gate 应在段1: {found}"


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
