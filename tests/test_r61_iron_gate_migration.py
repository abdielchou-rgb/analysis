"""R61 (2026-08-03) 回归测试 — iron_gate 完整迁移。

验证：
  - IronGate 继承 4 个 mixin（MRO 正确）
  - 67 项检查方法全部可调用（方法从 mixin 解析）
  - GateCheckResult/GateReport 从 checks.base 导入
  - run_all 完整运行
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_iron_gate_mro():
    """IronGate 应继承 4 个 mixin。"""
    from pipeline.iron_gate import IronGate
    mro = [c.__name__ for c in IronGate.__mro__]
    for m in ["ContentFormatChecksMixin", "DataQualityChecksMixin",
              "AnalysisChecksMixin", "LlmChecksMixin"]:
        assert m in mro, f"MRO 缺 {m}"


def test_iron_gate_shrunk():
    """iron_gate.py 应大幅缩小（<1000行）。"""
    lines = len((_ROOT / "pipeline" / "iron_gate.py").read_text(encoding="utf-8").splitlines())
    assert lines < 1000, f"iron_gate.py 应<1000行: {lines}"


def test_all_checks_callable():
    """67 项检查方法应全部可调用。"""
    from pipeline.iron_gate import IronGate
    gate = IronGate.from_text("测试文本", report_type="industry_deep", style="cicc")
    # 从各组抽代表性方法
    checks = [
        # content_format
        "_check_content_volume", "_check_judgment_density", "_check_completeness_scan",
        # data_quality
        "_check_valuation_integrity", "_check_financial_fraud_signals",
        "_check_data_conflicts", "_check_arithmetic_audit",
        # analysis
        "_check_sac_coverage", "_check_so_what_chain", "_check_evidence_chain",
        "_check_bold_call", "_check_industry_consolidation",
        # llm
        "_check_llm_data_verification",
    ]
    for m in checks:
        assert hasattr(gate, m), f"{m} 缺失"
        # 调用（短文本应跳过/通过，不抛异常）
        try:
            r = getattr(gate, m)()
            assert r is not None, f"{m} 返回 None"
        except Exception as e:
            # llm_data_verification 可能因无 provider 降级，不算失败
            if "降级" not in str(e):
                raise


def test_gate_check_result_from_base():
    """GateCheckResult 应从 checks.base 导入（dataclass）。"""
    from pipeline.iron_gate import GateCheckResult
    import dataclasses
    assert dataclasses.is_dataclass(GateCheckResult), "应为 dataclass"


def test_run_all_works():
    """run_all 应完整运行返回 GateReport。"""
    from pipeline.iron_gate import IronGate
    gate = IronGate.from_text(
        "本报告分析某行业。市场规模45亿元，增速12%。我们判断成长期，预计渗透率提升。"
        "我们看好龙头。风险提示：需求波动。" * 10,
        report_type="industry_deep", style="cicc")
    report = gate.run_all()
    assert hasattr(report, "passed"), "应返回 GateReport"
    assert hasattr(report, "overall_score")


def test_checks_dir_exists():
    """checks/ 目录应有 base + 4 mixin。"""
    checks_dir = _ROOT / "pipeline" / "checks"
    for f in ["base.py", "content_format_mixin.py", "data_quality_mixin.py",
              "analysis_mixin.py", "llm_checks_mixin.py"]:
        assert (checks_dir / f).exists(), f"{f} 缺失"


def test_run_all_covers_all_check_methods():
    """R63 全量修复：run_all 必须执行全部 _check_* 方法（治本防迁移遗漏）。

    Marvis 审计（2号分析师R60R61升级深度审计_20260803）发现 R61 迁移时
    3 项检查（data_fidelity/data_source_accuracy/subjective_scoring）漏进
    _check_funcs，67 方法仅 64 执行。原 test_all_checks_callable 只抽样验证
    "方法可调用"，未验证"方法被 run_all 执行"——测试与实现脱节。

    本测试用 AST 反射：
      1. 扫描 checks/*.py 全部 _check_* 方法定义 → defined
      2. 扫描 iron_gate.py 的 _check_funcs 列表 → executed
      3. 断言 executed == defined，任何新增检查未接线 → 测试失败
    """
    import ast

    def defined_checks() -> set:
        checks_dir = _ROOT / "pipeline" / "checks"
        defined = set()
        for f in checks_dir.glob("*.py"):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("_check_"):
                        defined.add(node.name)
        return defined

    def executed_checks() -> set:
        src = (_ROOT / "pipeline" / "iron_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        executed = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_all":
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Attribute):
                        if isinstance(sub.value, ast.Name) and sub.value.id == "self":
                            if sub.attr.startswith("_check_"):
                                executed.add(sub.attr)
        return executed

    defined = defined_checks()
    executed = executed_checks()
    missing = sorted(defined - executed)
    extra = sorted(executed - defined)
    assert not missing, f"以下 {len(missing)} 项检查未接线进 run_all（迁移遗漏）: {missing}"
    assert not extra, f"run_all 执行了未定义的方法: {extra}"
    # 完整性：67 项全部接线
    assert len(defined) >= 67, f"检查方法总数异常: {len(defined)}"
    assert len(executed) == len(defined), f"执行数 {len(executed)} != 定义数 {len(defined)}"


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
