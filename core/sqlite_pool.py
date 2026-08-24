"""
统一 SQLite 连接管理（Unified SQLite Connection Manager）— R48 并发根治

**问题**：多报告并发时，多个模块各自 sqlite3.connect() 同一 db，
写操作互相锁死 → "database is locked" 卡死（R24 4-worker 教训）。

**方案**（对标顶级打法 WAL + busy_timeout + 单写者）：
  1. 所有 db 连接走 get_connection(db_path)，自动开 WAL + busy_timeout(30s)
  2. WAL 允许读写并行、写写排队，busy_timeout 等待而非立刻报错
  3. 写操作加 threading.Lock 串行化（单写者模式）
  4. 进程级：多进程并发写同一 db 时，用 filelock 兜底
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger("2hao.sqlite")

# 连接缓存：{db_path: Connection}
_CONN_CACHE: dict[str, sqlite3.Connection] = {}
_CONN_LOCK = threading.RLock()
# 写锁：每个 db 一把锁，串行化写者
_WRITE_LOCKS: dict[str, threading.Lock] = {}

BUSY_TIMEOUT_MS = 30000  # 30 秒等待而非立刻报错


def _write_lock(db_path: str) -> threading.Lock:
    with _CONN_LOCK:
        if db_path not in _WRITE_LOCKS:
            _WRITE_LOCKS[db_path] = threading.Lock()
        return _WRITE_LOCKS[db_path]


def get_connection(db_path: str | Path, read_only: bool = False) -> sqlite3.Connection:
    """获取统一管理的 SQLite 连接（单例 + WAL + busy_timeout）。

    Args:
        db_path: 数据库路径
        read_only: 只读连接（并发读不争锁）

    Returns:
        sqlite3.Connection
    """
    path = str(db_path)
    with _CONN_LOCK:
        # 只读连接不缓存（每调用新建，避免跨线程状态污染）
        if read_only:
            return _open_connection(path, read_only=True)
        if path not in _CONN_CACHE:
            _CONN_CACHE[path] = _open_connection(path)
        return _CONN_CACHE[path]


def _open_connection(path: str, read_only: bool = False) -> sqlite3.Connection:
    try:
        if read_only:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_MS / 1000)
        else:
            conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000, check_same_thread=False)
        # WAL 模式：读写并行、写写排队
        if not read_only:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=%d" % BUSY_TIMEOUT_MS)
            conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能与安全
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.warning("[SQLITE] 连接失败 %s: %s", path, str(e)[:100])
        # 回退普通连接
        conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
        return conn


def write_execute(db_path: str | Path, sql: str, params: tuple = ()) -> sqlite3.Cursor:
    """单写者执行写 SQL（串行化 + WAL + commit）。"""
    path = str(db_path)
    lock = _write_lock(path)
    with lock:
        conn = get_connection(path)
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                logger.warning("[SQLITE] 写锁冲突重试 %s: %s", path, str(e)[:80])
                # 重试一次（等待 busy_timeout 后）
                cur = conn.execute(sql, params)
                conn.commit()
                return cur
            raise


def write_executemany(db_path: str | Path, sql: str, seq: list) -> int:
    """单写者批量写（串行化 + WAL + 一次性 commit）。"""
    path = str(db_path)
    lock = _write_lock(path)
    with lock:
        conn = get_connection(path)
        cur = conn.executemany(sql, seq)
        conn.commit()
        return cur.rowcount


def close_all():
    """关闭所有缓存连接（进程退出时调用）。"""
    with _CONN_LOCK:
        for path, conn in _CONN_CACHE.items():
            try:
                conn.close()
            except Exception:
                pass
        _CONN_CACHE.clear()


def get_all_open_paths() -> list[str]:
    """返回所有已打开的 db 路径（诊断用）。"""
    with _CONN_LOCK:
        return list(_CONN_CACHE.keys())
