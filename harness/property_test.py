"""2hao-analyst Property-Based Test (PBT) 框架

将 IronGate 的 24 项检查提取为通用的 property-based test。
可以同时用于：
  1. 报告质量检验（原有用途）
  2. 代码质量检验（新用途：确保每次代码改动不破坏系统性质）

设计原则（SRLabs Verification Bottleneck 解法）：
  - 不写 "输入X → 应该输出Y" 的测试
  - 写 "所有输出都应该满足属性 P" 的测试
  - 属性 = 可自动验证的不变量 (invariant)
"""

import sys
import re
import importlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── Property 定义 ──

@dataclass
class PropertyResult:
    """单个属性的验证结果"""
    name: str
    passed: bool
    target: str = ""  # 检验对象：report / code / import_chain
    detail: str = ""
    score: float = 0.0

    def __bool__(self):
        return self.passed


@dataclass
class PropertySuite:
    """一组属性测试的结果"""
    name: str
    results: list[PropertyResult] = field(default_factory=list)
    target: str = ""

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def score(self) -> float:
        if not self.results:
            return 1.0
        return sum(r.score for r in self.results) / len(self.results)


PropertyCheck = Callable[..., PropertyResult]


# ── 内置属性定义 ──

# === A. 报告属性 (Report Properties) ===
# 直接调用 IronGate 的 24 项检查

def run_report_properties(text: str, report_type: str = "industry_deep",
                          style: str = "cicc") -> PropertySuite:
    """运行全套报告属性测试"""
    from pipeline.iron_gate import IronGate
    gate = IronGate.from_text(text, report_type, style)
    report = gate.run_all()
    suite = PropertySuite(
        name="Report Properties",
        results=[
            PropertyResult(c.name, c.passed, "report", c.details[:100], c.score)
            for c in report.checks
        ],
        target="report",
    )
    return suite


# === B. 代码属性 (Code Properties) ===

def property_all_py_files_compile(root: Path = _ROOT) -> PropertyResult:
    """属性：所有 .py 文件必须语法正确"""
    import ast
    bad = []
    for f in root.rglob("*.py"):
        if any(p in f.parts for p in ("__pycache__", "output", "outputs")):
            continue
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as e:
            bad.append(f"{f.relative_to(root)}: {e}")
    return PropertyResult(
        "all_py_files_compile", len(bad) == 0, "code",
        f"{len(bad)} files failed" if bad else "ALL OK",
        0.0 if bad else 1.0,
    )


def property_no_hardcoded_api_keys(root: Path = _ROOT) -> PropertyResult:
    """属性：不得有硬编码 API key"""
    import re as _re
    patterns = [_re.compile(r'sk-[a-zA-Z0-9]{20,}'), _re.compile(r'tvly-dev-[a-zA-Z0-9]{20,}')]
    leaks = []
    for f in root.rglob("*"):
        if f.suffix not in (".py", ".bat", ".sh"):
            continue
        if any(p in f.parts for p in ("__pycache__", ".env", "output", "outputs")):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            for pat in patterns:
                if pat.search(content):
                    leaks.append(str(f.relative_to(root)))
                    break
        except Exception:
            pass
    return PropertyResult(
        "no_hardcoded_api_keys", len(leaks) == 0, "code",
        f"Leaks in: {', '.join(leaks)}" if leaks else "Clean",
        0.0 if leaks else 1.0,
    )


def property_entry_points_resolve(root: Path = _ROOT) -> PropertyResult:
    """属性：所有入口文件的 import 链必须完整"""
    import importlib
    critical = [
        "core.sacs", "core.deepseek_client", "core.style",
        "pipeline.e2e_orchestrator", "pipeline.iron_gate",
        "pipeline.section_writer", "pipeline.chart_runner",
        "pipeline.step_manager", "export.report_gate",
    ]
    failed = []
    for mod in critical:
        try:
            importlib.import_module(mod)
        except Exception as e:
            failed.append(f"{mod}: {e}")
    return PropertyResult(
        "entry_points_resolve", len(failed) == 0, "import_chain",
        "; ".join(failed[:3]) if failed else f"All {len(critical)} OK",
        0.0 if failed else 1.0,
    )


def property_no_import_inside_bare_except(root: Path = _ROOT) -> PropertyResult:
    """属性：import 语句不得放在 bare `except:` 块内"""
    import ast
    bad = []
    for f in root.rglob("*.py"):
        if any(p in f.parts for p in ("__pycache__", "output", "outputs")):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                # Check if any import in this handler
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        bad.append(f"{f.relative_to(root)}: line {child.lineno}")
                        break
    return PropertyResult(
        "no_import_in_bare_except", len(bad) == 0, "code",
        f"{bad[0]}" if bad else "Clean",
        0.0 if bad else 1.0,
    )


def _find_same_scope_duplicates(source: str) -> list[tuple[str, int]]:
    """在同级作用域内找重复函数定义（跨类/模块级的同名不视为重复）"""
    import ast
    issues = []
    def _walk_scope(scope_name: str, nodes: list):
        seen = {}
        for node in nodes:
            if isinstance(node, ast.FunctionDef):
                if node.name in seen:
                    issues.append((f"{scope_name}.{node.name}", node.lineno))
                seen[node.name] = node.lineno
            elif isinstance(node, ast.ClassDef):
                _walk_scope(f"{scope_name}.{node.name}", node.body)
    _walk_scope("<module>", ast.parse(source).body)
    return issues

def property_no_duplicate_function_defs(root: Path = _ROOT) -> PropertyResult:
    """属性：同作用域内不得有重复函数定义"""
    bad = []
    for f in root.rglob("*.py"):
        if any(p in f.parts for p in ("__pycache__", "output", "outputs")):
            continue
        try:
            issues = _find_same_scope_duplicates(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for scope_name, lineno in issues:
            bad.append(f"{f.relative_to(root)}: {scope_name} (line {lineno})")
    return PropertyResult(
        "no_duplicate_function_defs", len(bad) == 0, "code",
        f"{bad[0]}" if bad else "Clean",
        0.0 if bad else 1.0,
    )


# === C. 管线属性 (Pipeline Properties) ===

def property_step_manager_used(root: Path = _ROOT) -> PropertyResult:
    """属性：StepManager 至少被一个管线模块 import"""
    import ast
    references = []
    for f in root.rglob("*.py"):
        if any(p in f.parts for p in ("__pycache__", "output", "outputs")):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if "StepManager" in alias.name:
                        references.append(str(f.relative_to(root)))
    return PropertyResult(
        "step_manager_used", len(references) > 0, "pipeline",
        f"Used by: {', '.join(references)}" if references else "NOT USED ANYWHERE",
        1.0 if references else 0.0,
    )


# ── 运行器 ──

def run_code_properties(root: Path = _ROOT) -> PropertySuite:
    """运行全套代码属性测试"""
    return PropertySuite(
        name="Code Properties",
        results=[
            property_all_py_files_compile(root),
            property_no_hardcoded_api_keys(root),
            property_entry_points_resolve(root),
            property_no_import_inside_bare_except(root),
            property_no_duplicate_function_defs(root),
        ],
        target="code",
    )


def run_pipeline_properties(root: Path = _ROOT) -> PropertySuite:
    """运行全套管线属性测试"""
    return PropertySuite(
        name="Pipeline Properties",
        results=[
            property_step_manager_used(root),
        ],
        target="pipeline",
    )


def run_all_properties(text: str = "", report_type: str = "",
                       style: str = "") -> list[PropertySuite]:
    """运行全部属性测试"""
    suites = []

    # Code properties (always run)
    suites.append(run_code_properties())

    # Pipeline properties (always run)
    suites.append(run_pipeline_properties())

    # Report properties (only if text provided)
    if text and report_type:
        suites.append(run_report_properties(text, report_type, style))

    return suites


def print_suite_report(suites: list[PropertySuite]):
    """打印属性测试报告"""
    print(f"\n{'='*60}")
    print(f"  Property-Based Test 报告")
    print(f"{'='*60}")
    all_pass = True
    for suite in suites:
        icon = "✓" if suite.passed else "✗"
        print(f"\n  {icon} [{suite.target}] {suite.name}: "
              f"score={suite.score:.2f}")
        for r in suite.results:
            pi = "✓" if r.passed else "✗"
            print(f"    {pi} {r.name}: {r.detail[:80]}")
            if not r.passed:
                all_pass = False
    print(f"\n{'='*60}")
    print(f"  总结果: {'全部通过' if all_pass else '有失败项'}")
    return all_pass


if __name__ == "__main__":
    suites = run_all_properties()
    print_suite_report(suites)
    sys.exit(0 if all(s.passed for s in suites) else 1)
