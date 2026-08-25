#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2号分析师 Agent 数据兜底执行器

用途：自动化「agent 兜底数据」三步流程，供 Claude/agent 在数据不足时调用。

三步流程（对应 CLAUDE.md 第〇原则）：
  1. 检查：跑到 enrich 节点，看缺口清单（缺什么一目了然）
  2. 模板：生成 enrich-file 模板（agent 用 WebSearch/akshare-MCP 填数据）
  3. 重跑：带 --enrich-file 重新调度完整管线

用法：
    python scripts/agent_backfill.py check "标的"                # 只查缺口
    python scripts/agent_backfill.py template "标的" --out e.json  # 生成模板
    python scripts/agent_backfill.py run "标的" --enrich-file e.json  # 带数据重跑管线
    python scripts/agent_backfill.py auto "标的"                # 检查→若有缺口提示 agent 补

合规：本脚本不自己编数据。数据真实性由 enrich-file 的 source 字段 + Iron Gate 保障。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("2hao.agent_backfill")

PY = sys.executable or "python"


def _cmd(args: list) -> subprocess.CompletedProcess:
    return subprocess.run([PY] + args, capture_output=True, text=True, cwd=str(_ROOT))


def cmd_check(
    asset: str, report_type: str = "listed_company", output_dir: str = "output", enrich_file: str = None
) -> dict:
    """跑到 enrich 节点，返回缺口清单"""
    print(f"\n{'=' * 60}")
    print("  Agent 数据兜底 — 检查缺口")
    print(f"{'=' * 60}")
    r = subprocess.run(
        [PY, "pipeline/scheduler.py", asset, "--type", report_type, "--output", output_dir, "--data-check-only"],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
    )
    print(r.stdout)
    if r.stderr:
        print(r.stderr[-2000:], file=sys.stderr)
    # 解析缺口清单文件
    gap_path = Path(output_dir) / f"{asset.split()[0]}_gaps.json"
    if not gap_path.exists():
        gap_path = Path(output_dir) / f"{asset}_gaps.json"
    if gap_path.exists():
        return json.loads(gap_path.read_text(encoding="utf-8"))
    return {"error": "gap manifest not found", "output": r.stdout[-1000:]}


def cmd_template(asset: str, out: str = "enrich.json") -> str:
    """生成 enrich-file 模板"""
    from pipeline.data_enrichment import make_enrich_template

    p = make_enrich_template(asset, out)
    print(f"[TEMPLATE] 已生成: {p}")
    print("  用 WebSearch/akshare-MCP 补数据，每条必须带 source 字段。")
    return str(p)


def cmd_run(
    asset: str,
    report_type: str = "listed_company",
    style: str = "cicc",
    output_dir: str = "output",
    enrich_file: str = None,
) -> int:
    """带 enrich-file 重跑完整管线"""
    print(f"\n{'=' * 60}")
    print("  Agent 数据兜底 — 带补充数据重跑管线")
    print(f"{'=' * 60}")
    args = [PY, "pipeline/scheduler.py", asset, "--type", report_type, "--style", style, "--output", output_dir]
    if enrich_file:
        args += ["--enrich-file", enrich_file]
    r = subprocess.run(args, capture_output=True, text=True, cwd=str(_ROOT))
    print(r.stdout)
    if r.stderr:
        print(r.stderr[-2000:], file=sys.stderr)
    return 0 if r.returncode == 0 else r.returncode


def cmd_auto(
    asset: str, report_type: str = "listed_company", output_dir: str = "output", enrich_file: str = None
) -> int:
    """检查缺口 → 若缺则提示 agent 补数据 → 带数据重跑"""
    result = cmd_check(asset, report_type, output_dir, enrich_file)
    if result.get("error"):
        print(f"\n[!!] 检查失败: {result['error']}")
        return 1
    if result.get("sufficient"):
        print(f"\n[✓] 数据充足（{result.get('detail', '')}），无需补充，直接跑完整管线。")
        return cmd_run(asset, report_type, "cicc", output_dir, enrich_file)
    print(f"\n[!] 数据不足，缺口: {result.get('missing_core', [])}")
    print("    请用 WebSearch/akshare-MCP 补充数据并生成 enrich-file，然后运行:")
    print(f'    python scripts/agent_backfill.py run "{asset}" --enrich-file <enrich.json>')
    # 自动生成模板供 agent 填写
    tpl = cmd_template(asset, f"{asset.split()[0]}_enrich.json")
    print(f"\n[✓] 已生成模板: {tpl} — 填入数据后重跑即可。")
    return 2  # 需要 agent 补数据


def main():
    import argparse

    parser = argparse.ArgumentParser(description="2hao Agent 数据兜底执行器")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="检查数据缺口（不写报告）")
    p_check.add_argument("asset")
    p_check.add_argument("--type", default="listed_company")
    p_check.add_argument("--output", default="output")
    p_check.add_argument("--enrich-file", default=None)

    p_tpl = sub.add_parser("template", help="生成 enrich-file 模板")
    p_tpl.add_argument("asset")
    p_tpl.add_argument("--out", default="enrich.json")

    p_run = sub.add_parser("run", help="带 enrich-file 重跑完整管线")
    p_run.add_argument("asset")
    p_run.add_argument("--type", default="listed_company")
    p_run.add_argument("--style", default="cicc")
    p_run.add_argument("--output", default="output")
    p_run.add_argument("--enrich-file", required=True)

    p_auto = sub.add_parser("auto", help="检查→提示→（有模板）")
    p_auto.add_argument("asset")
    p_auto.add_argument("--type", default="listed_company")
    p_auto.add_argument("--output", default="output")

    args = parser.parse_args()
    if args.cmd == "check":
        r = cmd_check(args.asset, args.type, args.output, args.enrich_file)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if not r.get("error") else 1
    if args.cmd == "template":
        cmd_template(args.asset, args.out)
        return 0
    if args.cmd == "run":
        return cmd_run(args.asset, args.type, args.style, args.output, args.enrich_file)
    if args.cmd == "auto":
        return cmd_auto(args.asset, args.type, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
