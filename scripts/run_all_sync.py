#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2hao-analyst 全量数据同步一键脚本

按序执行三个阶段，补全到最新（2026-07-31）：
  Stage 1: Baostock 财务历史层（全量 5250 只沪深活跃股）
  Stage 2: akshare 财务查漏补缺（补最新季度 + 历史缺口）
  Stage 3: qlib 行情增量（补到最新交易日）

特性：
  - 断点续跑：每阶段完成后写标记文件，中断后重跑自动跳过已完成阶段
  - 阶段日志：logs/sync_full_YYYYmmdd.log
  - 进度汇总：结束时打印各阶段结果

用法:
    python scripts/run_all_sync.py                 # 全量三阶段
    python scripts/run_all_sync.py --workers 6     # 调并发数
    python scripts/run_all_sync.py --stage 2       # 只跑某阶段
    python scripts/run_all_sync.py --dry-run       # 只预览（不实际写入）

注意：长任务，预计 1-3 小时。中途可 Ctrl+C，重跑自动续跑已完成阶段。
"""

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
MARK_DIR = _ROOT / "data" / "sync_marks"
LOG_DIR = _ROOT / "logs"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("run_all_sync")

PY = sys.executable or "python"

# 阶段定义
STAGES = {
    "1_baostock_fin": {
        "desc": "Baostock 财务历史层（全量增量）",
        "cmd": ["scripts/sync_financials.py", "--all", "--incremental", "--workers"],
    },
    "2_akshare_fin": {
        "desc": "akshare 财务查漏补缺",
        "cmd": ["scripts/sync_akshare_financials.py", "--all", "--workers"],
    },
    "3_qlib_price": {
        "desc": "qlib 行情增量补到最新",
        "cmd": ["scripts/sync_qlib_data.py", "--all", "--incremental", "--workers"],
    },
}


def _log_path() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"sync_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def _mark_path(stage: str) -> Path:
    MARK_DIR.mkdir(parents=True, exist_ok=True)
    return MARK_DIR / f"{stage}.done"


def _is_done(stage: str) -> bool:
    return _mark_path(stage).exists()


def _mark_done(stage: str) -> None:
    p = _mark_path(stage)
    p.write_text(datetime.now().isoformat(), encoding="utf-8")
    logger.info("[DONE] %s 完成标记已写入 %s", stage, p)


def _run_stage(stage: str, workers: int, dry_run: bool, log_fp) -> int:
    spec = STAGES[stage]
    if not dry_run and _is_done(stage):
        logger.info("[SKIP] %s 已完成（断点续跑）", stage)
        return 0
    logger.info("=" * 60)
    logger.info("[STAGE %s] %s", stage, spec["desc"])
    logger.info("=" * 60)

    cmd = [PY] + spec["cmd"] + [str(workers)]
    if dry_run and stage == "2_akshare_fin":
        cmd.append("--dry-run")
    logger.info("执行: %s", " ".join(cmd))

    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           cwd=str(_ROOT), timeout=None)
        # 实时写日志
        if log_fp:
            log_fp.write(r.stdout)
            log_fp.write(r.stderr)
            log_fp.flush()
        # 打印最近输出（控制台可见进度）
        tail = (r.stdout or "")[-2000:]
        if tail:
            print(tail)
        elapsed = (time.time() - t0) / 60
        logger.info("[STAGE %s] 用时 %.1f 分钟, returncode=%d",
                    stage, elapsed, r.returncode)
        if r.returncode != 0 and not dry_run:
            # 部分失败也标记完成（脚本内部有失败统计），但记录警告
            logger.warning("[STAGE %s] returncode=%d（可能有部分失败）",
                           stage, r.returncode)
        if not dry_run:
            _mark_done(stage)
        return r.returncode
    except FileNotFoundError as e:
        logger.error("[STAGE %s] 脚本不存在: %s", stage, e)
        return 1
    except KeyboardInterrupt:
        logger.warning("[STAGE %s] 被中断。重跑可续跑该阶段。", stage)
        return 130


def main():
    parser = argparse.ArgumentParser(description="2hao 全量数据同步一键脚本")
    parser.add_argument("--workers", type=int, default=4, help="并发数（默认4）")
    parser.add_argument("--stage", choices=list(STAGES.keys()) + ["all"], default="all",
                        help="只跑某阶段或全部")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览模式（akshare阶段加--dry-run，不写入）")
    parser.add_argument("--reset-marks", action="store_true",
                        help="清除所有完成标记（强制重跑全部）")
    args = parser.parse_args()

    if args.reset_marks:
        for p in MARK_DIR.glob("*.done"):
            p.unlink()
        logger.info("[RESET] 已清除 %d 个完成标记", len(list(MARK_DIR.glob('*.done'))))

    log_path = _log_path()
    log_fp = open(log_path, "w", encoding="utf-8")
    logger.info("全量同步开始: workers=%d, 日志=%s", args.workers, log_path)

    stages = list(STAGES.keys()) if args.stage == "all" else [args.stage]
    results = {}
    for stage in stages:
        rc = _run_stage(stage, args.workers, args.dry_run, log_fp)
        results[stage] = rc

    log_fp.close()

    # 汇总
    print("\n" + "=" * 60)
    print("  全量同步汇总")
    print("=" * 60)
    all_ok = True
    for stage, rc in results.items():
        status = "✓" if rc == 0 else ("(预览)" if args.dry_run else "⚠ 部分失败")
        if rc not in (0, 130):
            all_ok = False
        print(f"  {stage}: {status}")
    print(f"\n  日志: {log_path}")
    print(f"  完成标记: {MARK_DIR}")
    print("=" * 60)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
