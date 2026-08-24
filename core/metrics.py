"""
V50+ 可观测性基础设施（第一性原理新增）

三项最低可行可观测性：
1. LLM 调用日志（谁、何时、多少 token、成功/失败）
2. validate 历史库（每次验证结果存入 SQLite）
3. 修改学习库（EditCase 持久化——在 T2x_edit 中实现）
"""

from __future__ import annotations

import json  # noqa: F401  (dead-import debt)
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.metrics")

OBSERVABILITY_DIR = Path(__file__).resolve().parent


@dataclass
class LLMCallLog:
    """一次 LLM 调用的完整记录"""

    timestamp: str = ""
    module: str = ""  # "T2b_prose_engine", "T0_hypothesis", etc.
    section_id: str = ""  # 哪个段
    model: str = ""  # "claude-3.5-sonnet", "gpt-4", etc.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    status: str = ""  # "success" / "error" / "timeout"
    error: str = ""
    style_profile: str = ""
    provider: str = ""  # 2026-08-07：通道标记 deepseek/openrouter/agent_provider


@dataclass
class ValidateHistory:
    """一次 validate 的历史记录"""

    timestamp: str = ""
    report_id: str = ""
    sac_coverage: dict = field(default_factory=dict)
    judgment_density: float = 0.0
    style_deviation_score: float = 0.0
    modification_count: int = 0
    generation_duration_seconds: float = 0.0
    passed: bool = True
    notes: str = ""


class ObservabilityDB:
    """
    可观测性数据库——SQLite 存储三个流的数据。

    设计原则：
    - 单文件 SQLite，零部署依赖
    - 所有写入不阻塞主流程（write-and-forget）
    - 支持趋势查询和基线计算
    """

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            db_path = str(OBSERVABILITY_DIR / "observability.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化三张表"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)

        # LLM 调用日志
        conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                module TEXT,
                section_id TEXT,
                model TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                latency_ms INTEGER,
                status TEXT,
                error TEXT,
                style_profile TEXT,
                provider TEXT
            )
        """)

        # Validate 历史
        conn.execute("""
            CREATE TABLE IF NOT EXISTS validate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                report_id TEXT,
                sac_dimensions_covered INTEGER,
                sac_dimensions_required INTEGER,
                sac_passed INTEGER,
                judgment_density REAL,
                style_deviation_score REAL,
                modification_count INTEGER,
                generation_duration_seconds REAL,
                passed INTEGER,
                notes TEXT
            )
        """)

        # 质量趋势
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quality_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                metric_name TEXT,
                metric_value REAL,
                sample_size INTEGER
            )
        """)

        # 迁移：旧库 llm_calls 表无 provider 列 → ALTER 添加（幂等）
        try:
            _cols = [r[1] for r in conn.execute("PRAGMA table_info(llm_calls)").fetchall()]
            if "provider" not in _cols:
                conn.execute("ALTER TABLE llm_calls ADD COLUMN provider TEXT")
                logger.info("llm_calls 表迁移：添加 provider 列")
        except sqlite3.Error as _me:
            logger.debug("[METRICS] provider 列迁移跳过: %s", _me)

        conn.commit()
        conn.close()

    # ─── LLM 调用日志 ──────────────────────

    def log_llm_call(self, entry: LLMCallLog):
        """记录一次 LLM 调用"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO llm_calls
            (timestamp, module, section_id, model,
             prompt_tokens, completion_tokens, total_tokens,
             latency_ms, status, error, style_profile, provider)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entry.timestamp or datetime.now().isoformat(),
                entry.module,
                entry.section_id,
                entry.model,
                entry.prompt_tokens,
                entry.completion_tokens,
                entry.prompt_tokens + entry.completion_tokens,
                entry.latency_ms,
                entry.status,
                entry.error,
                entry.style_profile,
                entry.provider,
            ),
        )
        conn.commit()
        conn.close()

    def log_llm_call_simple(
        self,
        module: str,
        section_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        status: str = "success",
        provider: str = "",
    ):
        """简化版 LLM 调用记录（2026-08-07 增 provider 通道标记）"""
        self.log_llm_call(
            LLMCallLog(
                timestamp=datetime.now().isoformat(),
                module=module,
                section_id=section_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status=status,
                style_profile="",
                provider=provider,
            )
        )

    # ─── Validate 历史 ─────────────────────

    def log_validation(self, entry: ValidateHistory):
        """记录一次 validate"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO validate_history
            (timestamp, report_id,
             sac_dimensions_covered, sac_dimensions_required, sac_passed,
             judgment_density, style_deviation_score,
             modification_count, generation_duration_seconds,
             passed, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entry.timestamp or datetime.now().isoformat(),
                entry.report_id,
                entry.sac_coverage.get("covered", 0),
                entry.sac_coverage.get("required", 0),
                int(entry.sac_coverage.get("passed", False)),
                entry.judgment_density,
                entry.style_deviation_score,
                entry.modification_count,
                entry.generation_duration_seconds,
                int(entry.passed),
                entry.notes,
            ),
        )
        conn.commit()
        conn.close()

    # ─── 查询 ────────────────────────────

    def get_llm_usage_today(self) -> dict:
        """今日 LLM 用量统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            """
            SELECT
                COUNT(*) as calls,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) as errors
            FROM llm_calls
            WHERE timestamp LIKE ?
        """,
            (f"{today}%",),
        ).fetchone()
        conn.close()

        return {
            "calls": row[0],
            "total_tokens": row[1],
            "avg_latency_ms": round(row[2], 1),
            "errors": row[3],
        }

    def cost_audit(self, module_filter: str = "") -> dict:
        """P3-2 成本审计（2026-08-07）：按模块/通道聚合 token 与耗时，交付附审计报告。

        module_filter 传资产名（如 '柯力传感'）时只看该报告；空则全量。
        返回：每模块 token 分布 + 每通道分布 + TOP 成本节点。
        """
        conn = sqlite3.connect(self.db_path)
        _where = " WHERE module LIKE ?" if module_filter else ""
        _args = (f"%{module_filter}%",) if module_filter else ()

        # 按模块聚合
        by_module = conn.execute(
            f"""
            SELECT module, COUNT(*) as calls,
                   COALESCE(SUM(prompt_tokens),0) as prompt_tk,
                   COALESCE(SUM(completion_tokens),0) as comp_tk,
                   COALESCE(SUM(total_tokens),0) as total_tk,
                   COALESCE(AVG(latency_ms),0) as avg_latency
            FROM llm_calls{_where}
            GROUP BY module ORDER BY total_tk DESC
        """,
            _args,
        ).fetchall()

        # 按通道聚合
        by_provider = conn.execute(
            f"""
            SELECT COALESCE(provider,'unknown') as p,
                   COUNT(*) as calls, COALESCE(SUM(total_tokens),0) as total_tk
            FROM llm_calls{_where}
            GROUP BY p ORDER BY total_tk DESC
        """,
            _args,
        ).fetchall()

        # 汇总
        total_row = conn.execute(
            f"""
            SELECT COUNT(*), COALESCE(SUM(total_tokens),0),
                   COALESCE(SUM(latency_ms),0)
            FROM llm_calls{_where}
        """,
            _args,
        ).fetchone()
        conn.close()

        modules = [
            {
                "module": r[0] or "?",
                "calls": r[1],
                "prompt_tokens": r[2],
                "completion_tokens": r[3],
                "total_tokens": r[4],
                "avg_latency_ms": round(r[5], 1),
            }
            for r in by_module
        ]
        channels = [
            {
                "channel": r[0],
                "calls": r[1],
                "total_tokens": r[2],
            }
            for r in by_provider
        ]
        return {
            "filter": module_filter or "all",
            "total_calls": total_row[0],
            "total_tokens": total_row[1],
            "total_latency_ms": total_row[2],
            "top_modules": modules[:8],
            "by_channel": channels,
        }

    def get_validate_trend(self, days: int = 7) -> list[dict]:
        """最近 N 天的 validate 趋势"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """
            SELECT date(timestamp) as day,
                   COUNT(*) as reports,
                   AVG(CASE WHEN passed THEN 1 ELSE 0 END) * 100 as pass_rate,
                   AVG(judgment_density) as avg_density,
                   AVG(modification_count) as avg_modifications
            FROM validate_history
            WHERE timestamp >= date('now', ?)
            GROUP BY date(timestamp)
            ORDER BY day
        """,
            (f"-{days} days",),
        ).fetchall()
        conn.close()

        return [
            {
                "day": r[0],
                "reports": r[1],
                "pass_rate": round(r[2], 1),
                "avg_density": round(r[3], 2),
                "avg_modifications": round(r[4], 1),
            }
            for r in rows
        ]

    def get_quality_summary(self) -> dict:
        """质量摘要"""
        conn = sqlite3.connect(self.db_path)
        # 最近 30 条 validate 记录
        recent = conn.execute("""
            SELECT passed, judgment_density, modification_count
            FROM validate_history
            ORDER BY timestamp DESC
            LIMIT 30
        """).fetchall()
        conn.close()

        if not recent:
            return {"status": "no_data", "message": "尚无 validate 数据"}

        pass_count = sum(1 for r in recent if r[0])
        densities = [r[1] for r in recent if r[1] is not None]
        modifications = [r[2] for r in recent if r[2] is not None]

        return {
            "total_reports": len(recent),
            "pass_rate": f"{pass_count / len(recent) * 100:.1f}%",
            "avg_judgment_density": round(sum(densities) / len(densities), 2) if densities else 0,
            "avg_modifications": round(sum(modifications) / len(modifications), 1) if modifications else 0,
            "reports_sampled": 30,
        }


class FailureRegistry:
    """璺熻釜鍚勬ā鍧楃殑杩炵画澶辫触娆℃暟锛?3 娆¤繛缁け璐ユ椂鎻愪緵鍛婅銆?
    鐢ㄦ硶锛堝湪琚?try/except 鍖呰９鐨?except 鍧楀唴璋冪敤锛?
        from core.metrics import FailureRegistry
        except Exception as e:
            FailureRegistry.record("compute_pipeline", str(e))
            ...

    鍦?workflow.run() 鏈熬缁熶竴鎷夊彇鍛婅锛?        fails = FailureRegistry.report()
        if fails:
            for f in fails:
                logger.warning(...)
    """

    _failures: dict[str, dict] = {}

    @classmethod
    def record(cls, module: str, error: str = ""):
        if module not in cls._failures:
            cls._failures[module] = {
                "count": 0,
                "consecutive": 0,
                "last_error": "",
                "first_at": datetime.now().isoformat(),
            }
        cls._failures[module]["count"] += 1
        cls._failures[module]["consecutive"] += 1
        cls._failures[module]["last_error"] = str(error)[:300]
        cls._failures[module]["last_at"] = datetime.now().isoformat()

    @classmethod
    def success(cls, module: str):
        """閲嶇疆杩炵画澶辫触璁℃暟"""
        if module in cls._failures:
            cls._failures[module]["consecutive"] = 0

    @classmethod
    def report(cls) -> list[dict]:
        """杩斿洖鎵€鏈夎繛缁け璐?>= 3 娆＄殑妯″潡"""
        return [{"module": m, **v} for m, v in cls._failures.items() if v["consecutive"] >= 3]

    @classmethod
    def snapshot(cls) -> dict:
        """杩斿洖鍏ㄩ噺蹇収锛堜笉鍚繛缁憡璀﹂槇鍊艰繃婊わ級"""
        return dict(cls._failures)

    @classmethod
    def clear(cls, module: str = None):
        if module:
            cls._failures.pop(module, None)
        else:
            cls._failures.clear()
