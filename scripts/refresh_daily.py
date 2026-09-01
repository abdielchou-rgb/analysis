"""S2-1: 每日增量刷新

轻量级每日数据刷新，区别于 sync_all_data.py 的全量重跑：
- financials.db：只拉最近 N 天新增（按 code 增量 upsert）
- qlib：补最新交易日 close
- consensus_estimates：只刷报告期最新
- 输出 data/refresh_log.json 记录每次增量范围
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("refresh_daily")

REFRESH_LOG = _ROOT / "data" / "refresh_log.json"


def _load_refresh_log() -> list[dict]:
    if REFRESH_LOG.exists():
        with open(REFRESH_LOG, encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_refresh_log(log: list[dict]):
    REFRESH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(REFRESH_LOG, "w", encoding="utf-8") as f:
        json.dump(log[-100:], f, ensure_ascii=False, indent=2)  # 保留最近100条


def _run_script(script_name: str, timeout: int = 300) -> dict:
    """运行单个 sync 脚本，返回结果。"""
    script_path = _ROOT / "scripts" / script_name
    if not script_path.exists():
        return {"script": script_name, "status": "missing", "duration_s": 0}

    start = time.time()
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(_ROOT),
        )
        duration = time.time() - start
        return {
            "script": script_name,
            "status": "ok" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "duration_s": round(duration, 1),
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"script": script_name, "status": "timeout", "duration_s": timeout}
    except Exception as e:
        return {"script": script_name, "status": "error", "error": str(e), "duration_s": 0}


def refresh_financials_incremental() -> dict:
    """增量刷新财务数据（最近30天）。"""
    logger.info("增量刷新财务数据...")
    return _run_script("sync_financials.py", timeout=600)


def refresh_qlib_latest() -> dict:
    """补充最新交易日 close 数据。"""
    logger.info("补充 qlib 最新数据...")
    return _run_script("sync_qlib_data.py", timeout=300)


def refresh_consensus() -> dict:
    """刷新一致预期（最新报告期）。"""
    logger.info("刷新一致预期...")
    return _run_script("sync_consensus_estimates.py", timeout=300)


def main():
    logger.info("=== 每日增量刷新 开始 ===")
    start_time = time.time()

    results = []

    # 按依赖顺序执行
    steps = [
        ("financials", refresh_financials_incremental),
        ("qlib", refresh_qlib_latest),
        ("consensus", refresh_consensus),
    ]

    for name, fn in steps:
        logger.info("执行: %s", name)
        result = fn()
        results.append(result)
        logger.info("  结果: %s (%.1fs)", result["status"], result.get("duration_s", 0))

    total_duration = time.time() - start_time

    # 记录刷新日志
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "duration_s": round(total_duration, 1),
        "results": results,
        "success_count": sum(1 for r in results if r["status"] == "ok"),
        "fail_count": sum(1 for r in results if r["status"] in ("failed", "error", "timeout")),
    }

    log = _load_refresh_log()
    log.append(log_entry)
    _save_refresh_log(log)

    logger.info("=== 每日增量刷新 完成 (%.1fs) ===", total_duration)
    logger.info("成功: %d, 失败: %d", log_entry["success_count"], log_entry["fail_count"])

    return log_entry


if __name__ == "__main__":
    main()
