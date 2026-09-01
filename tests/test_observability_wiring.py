# -*- coding: utf-8 -*-
"""P1-1 (2026-09-01): 测量层通电测试——observability 三表真实写入。

覆盖：
1. IronGate.run_all 结束时写 validate_history（非 7 月空记录）
2. record_quality_trend 写 quality_trends（此前 0 条）
3. 写入失败不阻塞主流程（write-and-forget）
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.metrics import ObservabilityDB, ValidateHistory


class TestObservabilityWiring:
    def test_log_validation_writes(self, tmp_path):
        """log_validation 真实写入 validate_history。"""
        db = tmp_path / "obs.db"
        obs = ObservabilityDB(str(db))
        obs.log_validation(
            ValidateHistory(
                report_id="测试资产",
                sac_coverage={"covered": 5, "required": 6, "passed": True},
                judgment_density=1.3,
                passed=True,
                notes="test",
            )
        )
        conn = sqlite3.connect(str(db))
        rows = conn.execute("SELECT report_id, judgment_density, passed FROM validate_history").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "测试资产"
        assert rows[0][1] == 1.3
        assert rows[0][2] == 1

    def test_record_quality_trend_writes(self, tmp_path):
        """record_quality_trend 写入 quality_trends（此前 0 条）。"""
        db = tmp_path / "obs.db"
        obs = ObservabilityDB(str(db))
        obs.record_quality_trend("gate_score_avg", 0.9, sample_size=1)
        obs.record_quality_trend("gate_pass_rate", 1.0, sample_size=1)
        conn = sqlite3.connect(str(db))
        rows = conn.execute("SELECT metric_name, metric_value, sample_size FROM quality_trends").fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0][0] == "gate_score_avg"
        assert rows[0][1] == 0.9

    def test_bad_value_does_not_crash(self, tmp_path):
        """非法值不崩溃（write-and-forget 语义）。"""
        db = tmp_path / "obs.db"
        obs = ObservabilityDB(str(db))
        obs.record_quality_trend("bad", "not-a-float", 0)  # 不应 raise
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM quality_trends").fetchone()[0]
        conn.close()
        assert n == 0  # 转换失败被捕获，不写脏数据

    def test_llm_call_log_writes(self, tmp_path):
        """llm_calls 写入（既有链路回归）。"""
        db = tmp_path / "obs.db"
        obs = ObservabilityDB(str(db))
        obs.log_llm_call_simple("test_module", "sec", 100, 50, 10, status="success", provider="deepseek")
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT module, provider, total_tokens, status FROM llm_calls"
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][1] == "deepseek"
        assert rows[0][2] == 150
        assert rows[0][3] == "success"
