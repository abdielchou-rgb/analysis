#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-1 (2026-09-01): R 规则注册表扫描——docs+代码的 R 编号 vs 注册表。

用法：
    python scripts/scan_rules.py                 # 扫描并输出对比
    python scripts/scan_rules.py --strict        # 未登记规则以非零退出（CI 可接）

输出：
    1. 代码/文档中引用但注册表未登记的 R 编号（失联规则）
    2. 注册表已登记但代码/文档无引用的 R 编号（可能已废弃——需人工确认）

目的：R1-R99 规则散落 40+ docs 文档与代码注释的历史债务，
"废弃规则机械可查"（AUDIT_20260901 Phase 4）。本脚本不判定废弃与否，
只暴露"引用与登记不一致"让治理决策有据。
"""
import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def collect_registered() -> set[str]:
    """从 config/rules_registry.yaml 收集已登记 R 编号。"""
    reg_path = _ROOT / "config" / "rules_registry.yaml"
    if not reg_path.exists():
        print("[SCAN-RULES] 注册表不存在:", reg_path)
        return set()
    text = reg_path.read_text(encoding="utf-8")
    return set(re.findall(r"^\s*(R\d{1,3}):", text, re.MULTILINE))


def collect_referenced() -> set[str]:
    """扫描 docs/ 与 pipeline/core/scripts 中的 R 编号引用。"""
    refs: set[str] = set()
    for base in ("docs", "pipeline", "core", "scripts", "export"):
        d = _ROOT / base
        if not d.exists():
            continue
        for p in d.rglob("*.py"):
            try:
                refs.update(re.findall(r"\bR(\d{1,3})\b", p.read_text(encoding="utf-8", errors="ignore")))
            except Exception:
                pass
        for p in d.rglob("*.md"):
            try:
                refs.update(re.findall(r"\bR(\d{1,3})\b", p.read_text(encoding="utf-8", errors="ignore")))
            except Exception:
                pass
    # 归一化为 R 前缀
    return {"R" + n for n in refs}


def main():
    parser = argparse.ArgumentParser(description="R 规则注册表扫描")
    parser.add_argument("--strict", action="store_true", help="有未登记规则时非零退出")
    args = parser.parse_args()

    registered = collect_registered()
    referenced = collect_referenced()

    unregistered = sorted(referenced - registered, key=lambda x: int(x[1:]))
    unref_registered = sorted(registered - referenced, key=lambda x: int(x[1:]))

    print(f"[SCAN-RULES] 注册表登记: {len(registered)} 条")
    print(f"[SCAN-RULES] 代码/文档引用: {len(referenced)} 个 R 编号")
    print(f"[SCAN-RULES] 未登记引用（失联规则）: {len(unregistered)} 个")
    for r in unregistered:
        print(f"  [ORPHAN] {r} -- referenced in code/docs but not in registry")
    print(f"[SCAN-RULES] registered but unreferenced: {len(unref_registered)}")
    for r in unref_registered:
        print(f"  [UNUSED] {r} -- registered but no current reference")

    if args.strict and unregistered:
        print("[SCAN-RULES] STRICT: 存在未登记规则 → 非零退出")
        sys.exit(1)
    print("[SCAN-RULES] 完成")


if __name__ == "__main__":
    main()
