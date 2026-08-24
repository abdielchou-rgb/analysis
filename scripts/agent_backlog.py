#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2hao Agent 兜底待办队列 — agent 启动时的第一件事

当管线数据不足（needs_agent）时，enrich 节点会把待办写入 data/backlog/<asset>_task.json。
agent 在开始分析前必须先检查本队列，接手待办并完成兜底，避免"需要 agent 时 agent 没起作用"。

多 Agent 支持：
    本队列是 Agent 无关的（文件协议），Claude / Marvis / Codex 均可处理。
    当前配置的兜底 agent 是 Marvis（见 INSTRUCTIONS_FOR_AGENT.md）。

用法:
    python scripts/agent_backlog.py list                 # 查看所有待办（含超时升级）
    python scripts/agent_backlog.py take "标的"          # 接手某标的待办
    python scripts/agent_backlog.py complete "标的"      # 完成（兜底后重跑管线成功）
    python scripts/agent_backlog.py done                 # 完成所有
"""

from __future__ import annotations
import argparse, json, sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
BACKLOG_DIR = _ROOT / "data" / "backlog"


def _tasks() -> list:
    if not BACKLOG_DIR.exists():
        return []
    tasks = []
    for f in sorted(BACKLOG_DIR.glob("*_task.json")):
        try:
            tasks.append((f, json.loads(f.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return tasks


def _check_escalation(t: dict, f: Path = None) -> bool:
    """TTL 看门狗：pending 超过 ttl_seconds → 升级为 escalated + 写回。

    返回是否本次发生了升级。
    """
    if t.get("status") != "pending" or t.get("escalated"):
        return False
    from datetime import datetime
    ttl = t.get("ttl_seconds", 3600)
    try:
        created = datetime.fromisoformat(t.get("created_at", ""))
    except Exception:
        return False
    age_sec = (datetime.now() - created).total_seconds()
    if age_sec > ttl:
        t["status"] = "escalated"
        t["escalated"] = True
        t["escalated_at"] = datetime.now().isoformat()
        if f:
            f.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[⚠ 升级] {t.get('asset','')} 待办超过 TTL（{age_sec:.0f}s）未接手，已升级")
        return True
    return False


def cmd_list() -> int:
    tasks = _tasks()
    if not tasks:
        print("(空) 无 agent 兜底待办")
        return 0
    # TTL 看门狗：先检测超时
    escalated = 0
    for f, t in tasks:
        if _check_escalation(t, f):
            escalated += 1
    if escalated:
        print(f"[⚠] {escalated} 项待办超时升级，请优先处理！\n")
    print(f"{'标的':<20} {'状态':<12} {'缺口':<30} 创建时间")
    print("-" * 80)
    pending = 0
    for f, t in tasks:
        missing = ",".join(t.get("missing_core", [])) or "见 detail"
        status = t.get("status", "pending")
        if status == "pending":
            pending += 1
        created = t.get("created_at", "")[:16]
        marker = " ⚠" if status == "escalated" else ""
        print(f"{t.get('asset',''):<20} {status:<12} {missing:<30} {created}{marker}")
    print(f"\n待办 {pending} 项。接手: python scripts/agent_backlog.py take \"标的\"")
    return 0


def _find_task(asset: str):
    for f, t in _tasks():
        if t.get("asset") == asset or asset in str(t.get("asset", "")):
            return f, t
    return None, None


def cmd_take(asset: str) -> int:
    f, t = _find_task(asset)
    if f is None:
        print(f"[!!] 未找到 {asset} 的待办。先跑管线让它生成 backlog。")
        return 1
    if t.get("status") == "completed":
        print(f"[!!] {asset} 待办已完成")
        return 1
    t["status"] = "in_progress"
    t["taken_at"] = datetime.now().isoformat()
    f.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[✓] 已接手 {asset}。兜底步骤：")
    for step in t.get("how_to_fix", []):
        print(f"    {step}")
    print(f"    完成后: python scripts/agent_backlog.py complete \"{asset}\"")
    return 0


def cmd_complete(asset: str) -> int:
    f, t = _find_task(asset)
    if f is None:
        print(f"[!!] 未找到 {asset} 的待办")
        return 1
    t["status"] = "completed"
    t["completed_at"] = datetime.now().isoformat()
    f.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[✓] {asset} 待办已完成")
    return 0


def cmd_done_all() -> int:
    n = 0
    for f, t in _tasks():
        if t.get("status") != "completed":
            t["status"] = "completed"
            t["completed_at"] = datetime.now().isoformat()
            f.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
            n += 1
    print(f"[✓] 完成 {n} 项待办")
    return 0


def main():
    parser = argparse.ArgumentParser(description="2hao Agent 兜底待办队列")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="查看待办")
    p_take = sub.add_parser("take", help="接手待办")
    p_take.add_argument("asset")
    p_comp = sub.add_parser("complete", help="完成待办")
    p_comp.add_argument("asset")
    sub.add_parser("done", help="完成所有")
    args = parser.parse_args()

    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "take":
        return cmd_take(args.asset)
    if args.cmd == "complete":
        return cmd_complete(args.asset)
    if args.cmd == "done":
        return cmd_done_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
