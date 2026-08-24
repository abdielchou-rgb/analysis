"""cache_manager.py — 持久化数据缓存层

所有数据引擎在 get_data() 前先查缓存。缓存过期自动失效。
支持 SQLite + 可选的 Redis 后端。

用法:
    from legacy.data_platform.cache_manager import PersistentCache
    cache = PersistentCache()
    # 写缓存
    cache.set("consensus_600519", {"revenue": 1725}, ttl=86400)
    # 读缓存（过期返回 None）
    data = cache.get("consensus_600519")
"""

from __future__ import annotations
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("v57.data.cache")

CACHE_TTL = {
    "realtime": 60,
    "kline": 3600,
    "consensus": 86400,
    "macro": 86400,
    "industry": 43200,
    "policy": 3600,
    "cvc": 604800,
    "news": 1800,
}


def _default_cache_path() -> str:
    return str(Path(__file__).resolve().parent / "data_cache.db")


class PersistentCache:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, db_path: str | None = None):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self.db_path = db_path or _default_cache_path()
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                data_type TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON data_cache(expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_type ON data_cache(data_type)")
        conn.commit()

    def _ttl_for(self, key: str) -> int:
        for prefix, ttl in CACHE_TTL.items():
            if key.startswith(prefix):
                return ttl
        return 3600

    def get(self, key: str) -> Optional[Any]:
        conn = self._get_conn()
        now = time.time()
        row = conn.execute("SELECT data, expires_at FROM data_cache WHERE cache_key = ?", (key,)).fetchone()
        if row is None:
            return None
        if row["expires_at"] < now:
            conn.execute("DELETE FROM data_cache WHERE cache_key = ?", (key,))
            conn.commit()
            return None
        try:
            return json.loads(row["data"])
        except (json.JSONDecodeError, TypeError):
            return None

    def set(self, key: str, data: Any, ttl: int | None = None):
        conn = self._get_conn()
        now = time.time()
        if ttl is None:
            ttl = self._ttl_for(key)
        data_type = key.split("_")[0] if "_" in key else ""
        conn.execute(
            """INSERT OR REPLACE INTO data_cache (cache_key, data, data_type, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (key, json.dumps(data, ensure_ascii=False, default=str), data_type, now, now + ttl),
        )
        conn.commit()

    def delete(self, key: str):
        conn = self._get_conn()
        conn.execute("DELETE FROM data_cache WHERE cache_key = ?", (key,))
        conn.commit()

    def clear_expired(self):
        conn = self._get_conn()
        now = time.time()
        cursor = conn.execute("DELETE FROM data_cache WHERE expires_at < ?", (now,))
        conn.commit()
        return cursor.rowcount

    def clear_type(self, data_type: str):
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM data_cache WHERE data_type = ?", (data_type,))
        conn.commit()
        return cursor.rowcount

    def clear_all(self):
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM data_cache")
        conn.commit()
        return cursor.rowcount

    def stats(self) -> dict:
        conn = self._get_conn()
        now = time.time()
        total = conn.execute("SELECT COUNT(*) as c FROM data_cache").fetchone()["c"]
        expired = conn.execute("SELECT COUNT(*) as c FROM data_cache WHERE expires_at < ?", (now,)).fetchone()["c"]
        by_type = {}
        for row in conn.execute("SELECT data_type, COUNT(*) as c FROM data_cache GROUP BY data_type").fetchall():
            by_type[row["data_type"]] = row["c"]
        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "by_type": by_type,
        }

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


persistent_cache = PersistentCache()
