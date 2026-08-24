"""2hao-analyst Harness — 验证层 (Import Chain / P0 Scan / Contract Check)

这是系统的"安全带"：在每次管线运行前验证环境完整性。
设计原则：所有检查必须是确定性的（zero-LLM），在 500ms 内完成。
"""

import sys
import os
import ast
import re
import importlib
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("2hao.harness")

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── 数据类型 ──

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    severity: str = "P0"  # P0=blocking, P1=warning

@dataclass
class HarnessReport:
    """验证报告 — 整体通过/失败"""
    passed: bool = False
    checks: list[CheckResult] = field(default_factory=list)
    duration_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": [{"name": c.name, "passed": c.passed, "severity": c.severity, "detail": c.detail} for c in self.checks],
            "failed": [c.name for c in self.checks if not c.passed and c.severity == "P0"],
        }

    def print_report(self):
        print(f"\n{'='*60}")
        print(f"  Harness 验证报告")
        print(f"{'='*60}")
        for c in self.checks:
            icon = "✓" if c.passed else "✗"
            tag = f"[{c.severity}]" if not c.passed else ""
            print(f"  {icon} {tag} {c.name}: {c.detail[:80]}")
        print(f"{'='*60}")
        print(f"  结果: {'通过' if self.passed else '阻断'} ({len([c for c in self.checks if not c.passed])}/{len(self.checks)} 项失败)")
        return self.passed


# ── 检查器 ──

class ImportChainValidator:
    """验证关键模块的 import 链路是否完整"""

    CRITICAL_MODULES = [
        "core.sacs",
        "core.deepseek_client",
        "core.style",
        "pipeline.e2e_orchestrator",
        "pipeline.iron_gate",
        "pipeline.section_writer",
        "export.report_gate",
        "export.exporter",
    ]
    # P1-warn (audit 2026-08-01): step_manager 已从 CRITICAL 移除
    # （审计标记为"形同虚设"，降级为非阻断模块）
    # chart_runner 降级为非阻断（matplotlib 依赖可能导致环境差异）
    OPTIONAL_MODULES = [
        "pipeline.chart_runner",
        "pipeline.step_manager",
    ]

    def check(self) -> CheckResult:
        failed = []
        for mod in self.CRITICAL_MODULES:
            try:
                importlib.import_module(mod)
            except Exception as e:
                failed.append(f"{mod}: {e}")
        if failed:
            return CheckResult("import_chain", False, "; ".join(failed[:3]))
        return CheckResult("import_chain", True, f"{len(self.CRITICAL_MODULES)} modules OK")


class SyntaxValidator:
    """验证所有 .py 文件语法正确"""

    def __init__(self, root: Path = _ROOT):
        self.root = root

    def check(self) -> CheckResult:
        bad = []
        for py_file in self.root.rglob("*.py"):
            rel = py_file.relative_to(self.root)
            # Skip __pycache__ and output dirs
            if any(p in py_file.parts for p in ("__pycache__", "output", "outputs")):
                continue
            try:
                ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError as e:
                bad.append(f"{rel}: {e}")
        if bad:
            return CheckResult("syntax_check", False, f"{len(bad)} files failed: {bad[0]}")
        return CheckResult("syntax_check", True, "ALL OK")


class ApiKeyLeakScanner:
    """扫描硬编码的 API key"""

    PATTERNS = [
        re.compile(r'sk-[a-zA-Z0-9]{20,}'),
        re.compile(r'tvly-dev-[a-zA-Z0-9]{20,}'),
    ]

    def check(self) -> CheckResult:
        leaks = []
        for py_file in _ROOT.rglob("*.py"):
            rel = py_file.relative_to(_ROOT)
            if any(p in py_file.parts for p in ("__pycache__", "output", "outputs", ".env")):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                for pattern in self.PATTERNS:
                    if pattern.search(content):
                        leaks.append(str(rel))
                        break
            except Exception:
                pass
        for bat_file in _ROOT.glob("*.bat"):
            if bat_file.exists():
                content = bat_file.read_text(encoding="utf-8", errors="ignore")
                for pattern in self.PATTERNS:
                    if pattern.search(content):
                        leaks.append(str(bat_file.relative_to(_ROOT)))
                        break
        if leaks:
            return CheckResult("api_key_leak", False, f"Keys in: {', '.join(leaks)}", severity="P0")
        return CheckResult("api_key_leak", True, "No leaks found")


class PipelineContractChecker:
    """验证管线合约 — 每个步骤的真实模块可导入且导出关键符号

    P0-audit 2026-08-24 修复：原实现把节点短名（"preflight"/"charts"...）
    直接传给 importlib.import_module()，这些模块不存在 → 永久红灯。
    现映射到真实模块 + 该模块必须暴露的关键符号（类/函数）。
    """

    CONTRACTS = {
        "pipeline.preflight_check": ["PreflightChecker", "check"],
        "pipeline.data_collector": ["DataCollectorV5"],
        "pipeline.chart_pipeline": ["ChartPipeline"],
        "pipeline.section_writer": ["SectionWriter", "write_report"],
        "pipeline.iron_gate": ["IronGate"],
        "export.report_gate": ["export_report", "GateBlockedError"],
    }

    def check_module(self, module_name: str, expected: list[str]) -> CheckResult:
        try:
            mod = importlib.import_module(module_name)
            for attr in expected:
                if not hasattr(mod, attr):
                    return CheckResult(f"contract.{module_name}", False,
                                       f"Missing: {attr}", severity="P1")
            return CheckResult(f"contract.{module_name}", True, f"All {len(expected)} attrs OK")
        except Exception as e:
            return CheckResult(f"contract.{module_name}", False, str(e), severity="P0")


# ── 主入口 ──

def run_all() -> HarnessReport:
    """运行全部 Harness 检查"""
    import time
    start = time.time()
    checks = []

    # 1. Syntax check all .py files
    v = SyntaxValidator()
    checks.append(v.check())

    # 2. Import chain
    ic = ImportChainValidator()
    checks.append(ic.check())

    # 3. API key leak
    ak = ApiKeyLeakScanner()
    checks.append(ak.check())

    # 4. Pipeline contracts
    pc = PipelineContractChecker()
    for mod, attrs in pc.CONTRACTS.items():
        checks.append(pc.check_module(mod, attrs))

    # 5. Entry point sanity
    scheduler_py = _ROOT / "pipeline" / "scheduler.py"
    exists = scheduler_py.exists()
    checks.append(CheckResult("entry_scheduler", exists, f"scheduler.py {'exists' if exists else 'MISSING'}"))

    report = HarnessReport(
        passed=all(c.passed or c.severity == "P1" for c in checks),
        checks=checks,
        duration_ms=(time.time() - start) * 1000,
    )
    return report


if __name__ == "__main__":
    # P0-audit 2026-08-24: Windows GBK 控制台无法编码 ✓/✗ → 强制 UTF-8 输出
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    r = run_all()
    r.print_report()
    sys.exit(0 if r.passed else 1)
