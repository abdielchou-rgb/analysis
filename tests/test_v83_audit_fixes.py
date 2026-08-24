"""V83 审计修复 (2026-08-03) 回归测试 — tool_modules 消费链。

覆盖：
  - section_writer._build_tool_modules_injection（compute→写作 消费链）
  - cleanup_workspace.py 清理脚本存在
  - hard_fail_errors 改 @property
"""

import os  # noqa: F401  (dead-import debt)
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── 1. tool_modules 消费链 ───────────────────────
def test_tool_modules_injection_exists():
    """section_writer 应有 _build_tool_modules_injection 方法。"""
    from pipeline.section_writer import SectionWriter

    assert hasattr(SectionWriter, "_build_tool_modules_injection")


def test_tool_modules_injection_by_segment():
    """tool_modules 应按 segment 注入对应工具数据。"""
    from pipeline.section_writer import SectionWriter

    sw = SectionWriter("industry_deep", "cicc")
    cr = {
        "tool_modules": {
            "modules": {
                "elasticity": {"demand_type": "investment", "is_cyclical": True},
                "signal_chain": {"triggered": 2, "total": 6, "confidence": "中"},
                "moat": {"overall": "中等"},
                "life_cycle": {"stage": "growth"},
                "multi_model": {"models": ["周期"]},
            }
        }
    }
    sw._prompt_compute_results = cr
    # seg0 → 生命周期
    inj0 = sw._build_tool_modules_injection(0)
    assert "生命周期" in inj0, f"seg0应注入生命周期: {inj0}"
    # seg1 → 护城河 + 信号链
    inj1 = sw._build_tool_modules_injection(1)
    assert "护城河" in inj1 and "信号链" in inj1, f"seg1应注入护城河+信号链: {inj1}"
    # seg2 → 弹性 + 多模型
    inj2 = sw._build_tool_modules_injection(2)
    assert "弹性分析" in inj2 and "多模型" in inj2, f"seg2应注入弹性+多模型: {inj2}"


def test_tool_modules_empty_returns_empty():
    """无 tool_modules 时应返回空串（不报错）。"""
    from pipeline.section_writer import SectionWriter

    sw = SectionWriter("industry_deep", "cicc")
    sw._prompt_compute_results = {}
    assert sw._build_tool_modules_injection(1) == ""


# ── 2. 清理脚本 ─────────────────────────────────
def test_cleanup_script_exists():
    """cleanup_workspace.py 应存在。"""
    assert (_ROOT / "scripts" / "cleanup_workspace.py").exists()


def test_cleanup_detects_sensitive():
    """清理脚本应检测 .env.bak 和 .fuse_hidden。

    R63（2026-08-04）修订：卫生债已实际清理（.env.bak/.fuse_hidden 已删除），
    原断言"collect_targets 应检测到存在文件"落空。改为临时创建敏感文件验证
    检测逻辑，测完清理——不再依赖仓库当前是否存在垃圾。
    """
    import importlib.util
    from pathlib import Path as _P  # noqa: F401  (dead-import debt)

    spec = importlib.util.spec_from_file_location("cleanup", _ROOT / "scripts" / "cleanup_workspace.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 临时创建敏感文件验证检测能力
    tmp_env = _ROOT / ".env.bak"
    tmp_fuse = _ROOT / "data" / ".fuse_hidden_test_probe"
    created = []
    try:
        if not tmp_env.exists():
            tmp_env.write_text("probe", encoding="utf-8")
            created.append(tmp_env)
        if not tmp_fuse.exists():
            tmp_fuse.write_text("probe", encoding="utf-8")
            created.append(tmp_fuse)
        targets = mod.collect_targets()
        names = [str(t.name) for t in targets]
        assert any("env.bak" in n for n in names), "应检测 .env.bak"
        assert any(".fuse_hidden" in n for n in names), "应检测 .fuse_hidden"
    finally:
        for p in created:
            try:
                p.unlink()
            except OSError:
                pass


# ── 3. hard_fail_errors @property ────────────────
def test_hard_fail_errors_is_property():
    """hard_fail_errors 应为 @property。"""
    from pipeline.iron_gate import GateReport

    assert isinstance(GateReport.__dict__.get("hard_fail_errors"), property), "应为property"


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
