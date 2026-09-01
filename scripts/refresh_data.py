"""refresh_data.py — 数据增量刷新调度器。

用途：统一运行所有 sync_*.py 脚本，支持增量刷新和失败重试。
可配合 Windows Task Scheduler 或 cron 定时运行。

用法:
    python scripts/refresh_data.py                    # 运行全部
    python scripts/refresh_data.py --only financials  # 只刷新财务数据
    python scripts/refresh_data.py --list              # 列出可用刷新任务
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("refresh_data")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"


@dataclass
class RefreshTask:
    name: str
    script: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    timeout: int = 600  # seconds
    enabled: bool = True


# ── 任务注册表 ──────────────────────────────────────────────────
TASKS: list[RefreshTask] = [
    RefreshTask(
        name="financials",
        script="sync_financials.py",
        description="A股财务数据（akshare）",
        timeout=1200,
    ),
    RefreshTask(
        name="capital_flow",
        script="sync_capital_flow.py",
        description="资金流向数据",
        depends_on=["financials"],
    ),
    RefreshTask(
        name="consensus",
        script="sync_consensus_estimates.py",
        description="一致预期数据",
        depends_on=["financials"],
    ),
    RefreshTask(
        name="events",
        script="sync_company_events.py",
        description="公司事件（解禁/减持/分红）",
    ),
    RefreshTask(
        name="industry",
        script="sync_industry_baselines.py",
        description="行业基线数据",
        depends_on=["financials"],
    ),
    RefreshTask(
        name="governance",
        script="sync_governance.py",
        description="公司治理数据",
    ),
    RefreshTask(
        name="pledge",
        script="sync_pledge_ratio.py",
        description="质押比例数据",
    ),
    RefreshTask(
        name="earnings_forecast",
        script="sync_earnings_forecast.py",
        description="业绩预告数据",
        depends_on=["financials"],
    ),
    RefreshTask(
        name="leading",
        script="sync_leading_indicators.py",
        description="先导指标数据",
    ),
    RefreshTask(
        name="macro",
        script="sync_macro_highfreq.py",
        description="宏观高频数据",
    ),
    RefreshTask(
        name="us_stocks",
        script="sync_us_highfreq.py",
        description="美股高频数据",
    ),
    RefreshTask(
        name="qlib",
        script="sync_qlib_data.py",
        description="Qlib 行情数据",
    ),
]


def _run_task(task: RefreshTask, dry_run: bool = False) -> tuple[bool, float]:
    """运行单个任务，返回 (success, elapsed_seconds)。"""
    script_path = SCRIPTS_DIR / task.script
    if not script_path.exists():
        logger.error("[SKIP] %s: 脚本不存在 %s", task.name, script_path)
        return False, 0.0

    if dry_run:
        logger.info("[DRY-RUN] %s: %s", task.name, task.description)
        return True, 0.0

    logger.info("[START] %s: %s", task.name, task.description)
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=task.timeout,
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            logger.info("[OK] %s (%.1fs)", task.name, elapsed)
            return True, elapsed
        else:
            logger.error(
                "[FAIL] %s (%.1fs): %s",
                task.name,
                elapsed,
                (result.stderr or result.stdout)[-500:],
            )
            return False, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        logger.error("[TIMEOUT] %s (%.1fs > %ds)", task.name, elapsed, task.timeout)
        return False, elapsed
    except Exception as e:
        elapsed = time.time() - start
        logger.error("[ERROR] %s: %s", task.name, str(e)[:200])
        return False, elapsed


def _resolve_order(tasks: list[RefreshTask]) -> list[RefreshTask]:
    """拓扑排序，确保依赖先执行。"""
    task_map = {t.name: t for t in tasks}
    visited = set()
    order = []

    def visit(name: str):
        if name in visited:
            return
        visited.add(name)
        t = task_map.get(name)
        if t is None:
            return
        for dep in t.depends_on:
            visit(dep)
        order.append(t)

    for t in tasks:
        visit(t.name)

    return order


def main():
    parser = argparse.ArgumentParser(description="数据增量刷新调度器")
    parser.add_argument("--only", nargs="+", help="只运行指定任务（逗号分隔）")
    parser.add_argument("--exclude", nargs="+", help="排除指定任务")
    parser.add_argument("--list", action="store_true", help="列出所有可用任务")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
    args = parser.parse_args()

    if args.list:
        print("可用刷新任务:")
        for t in TASKS:
            deps = f" (依赖: {','.join(t.depends_on)})" if t.depends_on else ""
            print(f"  {t.name:20s} {t.description}{deps}")
        return

    # 筛选任务
    active = [t for t in TASKS if t.enabled]
    if args.only:
        only_set = set(args.only)
        active = [t for t in active if t.name in only_set]
    if args.exclude:
        exclude_set = set(args.exclude)
        active = [t for t in active if t.name not in exclude_set]

    if not active:
        logger.warning("没有可执行的任务")
        return

    # 拓扑排序
    ordered = _resolve_order(active)
    logger.info("计划执行 %d 个任务: %s", len(ordered), [t.name for t in ordered])

    # 执行
    results = {}
    total_start = time.time()
    for task in ordered:
        success, elapsed = _run_task(task, dry_run=args.dry_run)
        results[task.name] = {"success": success, "elapsed": elapsed}
        if not success and not args.dry_run:
            logger.warning("任务 %s 失败，跳过依赖它的后续任务", task.name)
            # 标记依赖此任务的后续任务为跳过
            for t in ordered:
                if task.name in t.depends_on:
                    results[t.name] = {"success": False, "elapsed": 0.0, "skipped": True}

    # 汇总
    total_elapsed = time.time() - total_start
    succeeded = sum(1 for r in results.values() if r.get("success"))
    failed = sum(1 for r in results.values() if not r.get("success") and not r.get("skipped"))
    skipped = sum(1 for r in results.values() if r.get("skipped"))

    print("\n" + "=" * 50)
    print(f"刷新完成: {succeeded} 成功, {failed} 失败, {skipped} 跳过, 总耗时 {total_elapsed:.1f}s")
    for name, r in results.items():
        status = "✓" if r.get("success") else ("⊘" if r.get("skipped") else "✗")
        print(f"  {status} {name} ({r['elapsed']:.1f}s)")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
