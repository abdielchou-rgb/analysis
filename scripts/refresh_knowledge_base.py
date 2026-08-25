#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库维护自动化 — 检测新增知识库文件并重跑吸收。

R58（2026-08-03）：知识库吸收固化成流程——
  1. 扫描 data/知识库/ 各板块，对比上次扫描记录，找出新增/修改文件
  2. 对新增文件重跑规则式吸收（absorb_knowledge_base.py）
  3. 输出"新主题建议深读"清单（供子代理深度吸收）

用法：
  python scripts/refresh_knowledge_base.py           # 检测+吸收
  python scripts/refresh_knowledge_base.py --dry-run # 只检测不写
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = _ROOT / "data" / "知识库"
STATE_FILE = _ROOT / "data" / "knowledge_base_scan_state.json"

# 已深度吸收的主题（有 methodology_*_deep.json 产物）
_DEEP_ABSORBED = {
    "宏观分析": "methodology_macro_deep.json",
    "行业与公司研究": "methodology_industry_deep.json",
    "估值与测算": "methodology_valuation_deep.json",
    "回测基线库": "methodology_backtest_deep.json",
    "研报范式": "methodology_reports_deep.json",
    "咨询方法论": "methodology_consulting_deep.json",
    "审计方法论": "methodology_audit_deep.json",
}


def scan_files() -> dict:
    """扫描知识库各板块 → {相对路径: (mtime, size)}"""
    result = {}
    if not KB_DIR.exists():
        return result
    for md in KB_DIR.rglob("*.md"):
        if md.name == "INDEX.md":
            continue
        rel = str(md.relative_to(KB_DIR))
        result[rel] = (md.stat().st_mtime, md.stat().st_size)
    return result


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def detect_changes(current: dict, prev: dict) -> dict:
    """对比前后状态 → {new: [...], modified: [...], removed: [...]}"""
    new = [f for f in current if f not in prev]
    modified = [f for f in current if f in prev and current[f] != prev[f]]
    removed = [f for f in prev if f not in current]
    return {"new": new, "modified": modified, "removed": removed}


def suggest_deep_read(changes: dict) -> list[str]:
    """对新增/修改文件给出深度吸收建议。"""
    suggestions = []
    for f in changes["new"] + changes["modified"]:
        # 按文件路径判断所属板块
        sector = f.split("/")[0] if "/" in f else "根目录"
        topic = "未知主题"
        if "宏观" in f:
            topic = "宏观分析"
        elif "行业" in f or "研报" in f:
            topic = "行业与公司研究"
        elif "估值" in f or "Excel" in f:
            topic = "估值与测算"
        elif "回测" in f:
            topic = "回测基线库"
        suggestions.append(f"{f}（{sector}）→ 建议深度吸收为 {topic}")
    return suggestions


def main():
    ap = argparse.ArgumentParser(description="知识库维护自动化")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    current = scan_files()
    prev = load_state()
    changes = detect_changes(current, prev)

    print(f"知识库文件总数: {len(current)}（上次 {len(prev)}）")
    print(f"新增: {len(changes['new'])} | 修改: {len(changes['modified'])} | 移除: {len(changes['removed'])}")

    if not changes["new"] and not changes["modified"]:
        print("[OK] 无新增/修改文件，知识库无需刷新")
        return

    if args.dry_run:
        print("[DRY-RUN] 未执行吸收")
        for s in suggest_deep_read(changes)[:5]:
            print(f"  建议: {s}")
        return

    # 重跑规则式吸收
    print("[ABSORB] 重跑规则式吸收...")
    import subprocess

    r = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "absorb_knowledge_base.py")], capture_output=True, text=True
    )
    print(r.stdout[-500:] if r.stdout else r.stderr[-500:])

    # 更新状态
    save_state(current)
    print("[STATE] 扫描状态已更新")

    # 深度吸收建议
    suggestions = suggest_deep_read(changes)
    if suggestions:
        print("\n[深读建议] 以下文件建议子代理深度吸收:")
        for s in suggestions[:8]:
            print(f"  - {s}")


if __name__ == "__main__":
    main()
