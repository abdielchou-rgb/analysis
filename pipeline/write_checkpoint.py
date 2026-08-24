"""写改循环 checkpoint — R78 Phase2.3 可恢复状态机。

背景：E2EOrchestratorV2 的写改循环（最多 MAX_ATTEMPTS 轮）在中断
（进程崩溃/超时/断电）后从头重跑——已采集的数据、已写的稿子、已得的
Gate 反馈全部丢失。这对长任务（单份报告 40+ 分钟）是致命浪费。

本模块：每轮 attempt 结束时把状态写入 SQLite checkpoint，
中断后 run() 开头恢复，续跑不重头。

用法：
    from pipeline.write_checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("2hao.checkpoint")

_ROOT = Path(__file__).resolve().parent.parent
_CHECKPOINT_DB = _ROOT / "data" / "write_checkpoints.db"
_TTL_DAYS = 7  # checkpoint 保留 7 天


def _connect():
    conn = sqlite3.connect(str(_CHECKPOINT_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            asset TEXT PRIMARY KEY,
            report_type TEXT,
            data_json TEXT,
            updated_at TEXT
        )
    """)
    return conn


def save_checkpoint(asset: str, report_type: str, state: dict) -> bool:
    """保存一轮 checkpoint。state 含 attempt/report_text/gate_feedback 等。"""
    try:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO checkpoints (asset, report_type, data_json, updated_at) VALUES (?, ?, ?, ?)",
            (asset, report_type, json.dumps(state, ensure_ascii=False), datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("[CHECKPOINT] 保存失败: %s", str(e)[:80])
        return False


def load_checkpoint(asset: str) -> dict | None:
    """读取 checkpoint。不存在/过期返回 None。"""
    try:
        conn = _connect()
        row = conn.execute("SELECT data_json, updated_at FROM checkpoints WHERE asset=?", (asset,)).fetchone()
        conn.close()
        if row is None:
            return None
        # 过期检查
        try:
            from datetime import datetime as _dt

            updated = _dt.fromisoformat(row["updated_at"])
            if (datetime.now() - updated).days > _TTL_DAYS:
                return None
        except Exception:
            pass
        return json.loads(row["data_json"])
    except Exception as e:
        logger.warning("[CHECKPOINT] 读取失败: %s", str(e)[:80])
        return None


def clear_checkpoint(asset: str) -> bool:
    """清除 checkpoint（报告完成或确认失败后）。"""
    try:
        conn = _connect()
        conn.execute("DELETE FROM checkpoints WHERE asset=?", (asset,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def _maintenance() -> None:
    """清理过期 checkpoint（防 DB 膨胀）。"""
    try:
        conn = _connect()
        conn.execute("DELETE FROM checkpoints WHERE updated_at < datetime('now', '-7 days')")
        conn.commit()
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--maintenance":
        _maintenance()
        print("checkpoint 过期清理完成")
    elif len(sys.argv) > 2 and sys.argv[1] == "--show":
        ck = load_checkpoint(sys.argv[2])
        print(json.dumps(ck, ensure_ascii=False, indent=2)[:500] if ck else "无 checkpoint")
    else:
        print("用法: python pipeline/write_checkpoint.py --show <asset> | --maintenance")
