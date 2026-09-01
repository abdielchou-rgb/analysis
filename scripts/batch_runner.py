"""batch_runner.py — 批量报告生成 + 归档（支持并行）。

用途：一次性跑多份报告，自动归档到 output/archive/，生成索引。

用法:
    python scripts/batch_runner.py --assets "宁德时代,比亚迪,中芯国际" --type listed_company
    python scripts/batch_runner.py --config batch_config.json
    python scripts/batch_runner.py --from-track-record  # 从 track_record 批量补跑
    python scripts/batch_runner.py --assets "宁德时代,比亚迪" --parallel 2  # 并行2路
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("batch_runner")

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
ARCHIVE_DIR = OUTPUT_DIR / "archive"
INDEX_FILE = ARCHIVE_DIR / "index.json"

# LLM 限流：防止并行请求压垮 provider
_rate_lock = Lock()
_last_request_time = 0.0
_min_interval = 2.0  # 最小请求间隔秒数


def _rate_limit():
    """简单令牌桶限流：确保并行请求之间有最小间隔。"""
    global _last_request_time
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < _min_interval:
            time.sleep(_min_interval - elapsed)
        _last_request_time = time.time()


def run_single(asset: str, report_type: str, timeout: int = 900) -> dict:
    """运行单份报告，返回结果摘要。"""
    _rate_limit()  # 并行限流
    logger.info("[BATCH] 开始: %s (%s)", asset, report_type)
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), asset, "--type", report_type],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start
        success = result.returncode == 0
        # 找输出文件
        output_files = list(OUTPUT_DIR.glob(f"*{asset}*")) + list(OUTPUT_DIR.glob(f"*{asset.replace('/', '_')}*"))
        docx_files = [f for f in output_files if f.suffix == ".docx"]
        md_files = [f for f in output_files if f.suffix == ".md"]

        return {
            "asset": asset,
            "report_type": report_type,
            "success": success,
            "elapsed": round(elapsed, 1),
            "docx": str(docx_files[-1]) if docx_files else "",
            "md": str(md_files[-1]) if md_files else "",
            "error": (result.stderr or result.stdout)[-500:] if not success else "",
            "timestamp": datetime.now().isoformat(),
        }
    except subprocess.TimeoutExpired:
        return {
            "asset": asset,
            "report_type": report_type,
            "success": False,
            "elapsed": timeout,
            "error": f"TIMEOUT ({timeout}s)",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "asset": asset,
            "report_type": report_type,
            "success": False,
            "elapsed": time.time() - start,
            "error": str(e)[:500],
            "timestamp": datetime.now().isoformat(),
        }


def archive_report(result: dict) -> str:
    """归档报告到 archive/ 目录，返回归档路径。"""
    if not result.get("success"):
        return ""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    asset_safe = result["asset"].replace("/", "_").replace("\\", "_")
    dest_dir = ARCHIVE_DIR / f"{ts}_{asset_safe}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 复制 docx 和 md
    for key in ("docx", "md"):
        src = result.get(key, "")
        if src and Path(src).exists():
            shutil.copy2(src, dest_dir / Path(src).name)

    # 写入元数据
    meta = {k: v for k, v in result.items() if k != "error"}
    meta["archive_dir"] = str(dest_dir)
    (dest_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(dest_dir)


def update_index(results: list[dict]):
    """更新归档索引。"""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    index = {}
    if INDEX_FILE.exists():
        try:
            index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            index = {"reports": []}

    reports = index.get("reports", [])
    for r in results:
        reports.append(
            {
                "asset": r["asset"],
                "report_type": r["report_type"],
                "success": r["success"],
                "elapsed": r.get("elapsed", 0),
                "timestamp": r.get("timestamp", ""),
            }
        )
    index["reports"] = reports[-200:]  # 保留最近 200 条
    index["last_updated"] = datetime.now().isoformat()
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="批量报告生成 + 归档")
    parser.add_argument("--assets", help="逗号分隔的标的列表")
    parser.add_argument("--type", default="listed_company", help="报告类型")
    parser.add_argument("--config", help="JSON 配置文件路径")
    parser.add_argument("--from-track-record", action="store_true", help="从 track_record 补跑")
    parser.add_argument("--timeout", type=int, default=900, help="单份超时秒数")
    parser.add_argument("--parallel", type=int, default=1, help="并行数（暂不支持）")
    args = parser.parse_args()

    # 构建任务列表
    tasks = []
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
        tasks = cfg.get("tasks", cfg.get("assets", []))
    elif args.from_track_record:
        track_file = ROOT / "core" / "data" / "forward_picks" / "track_record.json"
        if track_file.exists():
            data = json.loads(track_file.read_text(encoding="utf-8"))
            seen = set()
            for p in data.get("predictions", []):
                asset = p.get("asset", "")
                if asset and asset not in seen:
                    seen.add(asset)
                    tasks.append({"asset": asset, "type": args.type})
    elif args.assets:
        for a in args.assets.split(","):
            a = a.strip()
            if a:
                tasks.append({"asset": a, "type": args.type})

    if not tasks:
        logger.error("没有任务。用法: --assets '宁德时代,比亚迪' 或 --config batch_config.json")
        return

    logger.info("批量任务: %d 份报告 (并行=%d)", len(tasks), args.parallel)
    results = []

    def _run_and_archive(task):
        asset = task.get("asset", task) if isinstance(task, dict) else task
        rtype = task.get("type", args.type) if isinstance(task, dict) else args.type
        result = run_single(asset, rtype, timeout=args.timeout)
        archive_dir = archive_report(result)
        if archive_dir:
            result["archive_dir"] = archive_dir
        return result

    if args.parallel > 1 and len(tasks) > 1:
        # 并行模式
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures = {pool.submit(_run_and_archive, t): t for t in tasks}
            for i, future in enumerate(as_completed(futures), 1):
                result = future.result()
                results.append(result)
                logger.info(
                    "[%d/%d] %s: %s (%.1fs)",
                    i,
                    len(tasks),
                    result["asset"],
                    "OK" if result["success"] else "FAIL",
                    result.get("elapsed", 0),
                )
    else:
        # 串行模式
        for i, task in enumerate(tasks, 1):
            asset = task.get("asset", task) if isinstance(task, dict) else task
            logger.info("[%d/%d] %s", i, len(tasks), asset)
            result = _run_and_archive(task)
            results.append(result)
            logger.info(
                "[%d/%d] %s: %s (%.1fs)",
                i,
                len(tasks),
                result["asset"],
                "OK" if result["success"] else "FAIL",
                result.get("elapsed", 0),
            )

    # 更新索引
    update_index(results)

    # 汇总
    succeeded = sum(1 for r in results if r["success"])
    failed = len(results) - succeeded
    total_time = sum(r.get("elapsed", 0) for r in results)
    print(f"\n{'=' * 50}")
    print(f"批量完成: {succeeded}/{len(results)} 成功, 总耗时 {total_time:.0f}s")
    for r in results:
        status = "✓" if r["success"] else "✗"
        print(f"  {status} {r['asset']} ({r.get('elapsed', 0):.0f}s)")


if __name__ == "__main__":
    main()
