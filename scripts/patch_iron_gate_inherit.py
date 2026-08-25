#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iron_gate 补丁 — IronGate 继承 mixin + 删除已迁移方法。

R61（2026-08-03）：在 migrate_iron_gate.py 生成 mixin 后，本脚本：
  1. IronGate 改为继承 4 个 mixin
  2. 从 IronGate 删除已迁移到 mixin 的检查方法（避免 MRO 重复定义）
  3. GateCheckResult/GateReport 改为从 checks.base 导入
"""

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
IRON_GATE = _ROOT / "pipeline" / "iron_gate.py"
CHECKS_DIR = _ROOT / "pipeline" / "checks"

# 4 个 mixin 的方法集（从生成的文件读取）
MIXIN_METHODS = {}


def collect_mixin_methods():
    for f in ["content_format", "data_quality", "analysis", "llm_checks"]:
        p = CHECKS_DIR / f"{f}_mixin.py"
        if not p.exists():
            print(f"⚠️ {p.name} 不存在")
            continue
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Mixin"):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("_check_"):
                        MIXIN_METHODS[item.name] = f
    print(f"Mixin 方法总数: {len(MIXIN_METHODS)}")


def patch_iron_gate():
    src = IRON_GATE.read_text(encoding="utf-8")

    # 1. 改 import：GateCheckResult/GateReport 从 base 导入
    # 原: from dataclasses import dataclass, field, asdict 等
    # 需加: from pipeline.checks.base import GateCheckResult, GateReport, detect_value_conflicts, logger
    base_import = "from pipeline.checks.base import GateCheckResult, GateReport, detect_value_conflicts, logger\n"
    if "from pipeline.checks.base" not in src:
        # 在 IronGate class 定义前插入
        m = re.search(r"^class IronGate:", src, re.MULTILINE)
        if m:
            src = src[: m.start()] + base_import + "\n" + src[m.start() :]
            print("已插入 checks.base import")

    # 2. IronGate 继承 mixin
    mixin_names = ["ContentFormatChecksMixin", "DataQualityChecksMixin", "AnalysisChecksMixin", "LlmChecksMixin"]
    # 先加 import mixin
    mixin_import = (
        "from pipeline.checks.content_format_mixin import ContentFormatChecksMixin\n"
        "from pipeline.checks.data_quality_mixin import DataQualityChecksMixin\n"
        "from pipeline.checks.analysis_mixin import AnalysisChecksMixin\n"
        "from pipeline.checks.llm_checks_mixin import LlmChecksMixin\n"
    )
    if "content_format_mixin" not in src:
        m = re.search(r"^class IronGate:", src, re.MULTILINE)
        if m:
            src = src[: m.start()] + mixin_import + "\n" + src[m.start() :]
            print("已插入 mixin imports")

    # 改 class IronGate: → class IronGate(...)
    m = re.search(r"^class IronGate:", src, re.MULTILINE)
    if m:
        src = src[: m.start()] + "class IronGate(" + ", ".join(mixin_names) + "):" + src[m.end() :]
        print("IronGate 已继承 4 个 mixin")

    # 3. 删除已迁移的方法（保留未迁移的）
    # 用 AST 定位方法行范围，从后往前删
    tree = ast.parse(src)
    to_remove = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "IronGate":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name in MIXIN_METHODS:
                    # 含装饰器起始行
                    start = item.lineno
                    for dec in item.decorator_list:
                        dl = getattr(dec, "lineno", None)
                        if dl:
                            start = min(start, dl)
                    to_remove.append((start - 1, item.end_lineno))  # 0-indexed

    # 从后往前删（保持行号有效）
    lines = src.split("\n")
    for start, end in sorted(to_remove, reverse=True):
        # 删除方法体 + 前后空行（保守：只删方法体）
        del lines[start:end]

    # 清理连续空行（方法删除后可能留下多余空行）
    out = "\n".join(lines)
    out = re.sub(r"\n{4,}", "\n\n\n", out)
    IRON_GATE.write_text(out, encoding="utf-8")
    print(f"已删除 {len(to_remove)} 个已迁移方法，iron_gate.py 现在 {len(out.splitlines())} 行")


if __name__ == "__main__":
    collect_mixin_methods()
    patch_iron_gate()
    print("✅ 补丁完成。请运行 pytest 验证。")
