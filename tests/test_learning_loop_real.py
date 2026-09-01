# -*- coding: utf-8 -*-
"""P1-2 (2026-09-01): Learning Loop stub 真实现回归测试。

验证 recurrence_rate / auto_apply_lessons 从真实数据库计算而非返回空 stub，
并确认 FP5 收敛指标（复发率）可被测量。
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

import pipeline.learning_loop as ll


@pytest.fixture()
def ll_env(tmp_path, monkeypatch):
    """指向临时 DB 的 LearningLoop，预置跨月失败数据。"""
    db_path = tmp_path / "learning_test.db"
    monkeypatch.setattr(ll, "LEARNING_DB", db_path)
    loop = ll.LearningLoop()
    c = loop._get_conn()
    # 近 3 个月失败：judgment_density 频繁（应被识别为复发）
    c.executemany(
        "INSERT INTO report_failures (asset,report_type,failure_type,failure_detail,created_at) VALUES (?,?,?,?,?)",
        [
            ("标的A", "listed_company", "judgment_density", "判断密度0.8<1.2", "2026-08-01 10:00:00"),
            ("标的A", "listed_company", "judgment_density", "判断密度0.9<1.2", "2026-08-15 10:00:00"),
            ("标的B", "listed_company", "so_what_chain", "缺SoWhat链", "2026-08-20 10:00:00"),
            ("标的C", "industry_deep", "inline_citations", "标注不足", "2026-07-10 10:00:00"),
            # 6 个月前（超出 3 个月窗口，且不在 prev 窗口内）
            ("标的D", "listed_company", "old_pattern", "历史问题", "2026-03-01 10:00:00"),
        ],
    )
    # 3-6 个月前窗口：judgment_density 也在（上期出现 → 复发）
    # 注意：SQLite datetime('now','-3 months') 取 UTC（现为 2026-05-31），
    # 上期窗口 = [now-6m, now-3m) = [2026-03-03, 2026-05-31)，用 2026-04-15
    c.execute(
        "INSERT INTO report_failures (asset,report_type,failure_type,failure_detail,created_at) VALUES (?,?,?,?,?)",
        ("标的E", "listed_company", "judgment_density", "上期判断密度问题", "2026-04-15 10:00:00"),
    )
    c.commit()
    return loop, db_path


class TestRecurrenceRate:
    def test_recurrence_rate_real_computation(self, ll_env):
        """复发率从真实数据计算，非空 stub。"""
        loop, _ = ll_env
        rates = loop.recurrence_rate(months=3)
        assert rates != {}
        assert "_summary" in rates
        assert rates["_summary"]["total_recent"] > 0

    def test_judgment_density_identified_recurred(self, ll_env):
        """judgment_density 近 3 月出现 2 次、上期也出现 → 应标记为复发。"""
        loop, _ = ll_env
        rates = loop.recurrence_rate(months=3)
        jd = rates.get("judgment_density")
        assert jd is not None
        assert jd["recent"] >= 2
        assert jd["recurred"] is True

    def test_old_pattern_not_counted(self, ll_env):
        """6 个月前的失败不在窗口内 → 不计入。"""
        loop, _ = ll_env
        rates = loop.recurrence_rate(months=3)
        assert "old_pattern" not in rates

    def test_summary_rate_between_0_and_1(self, ll_env):
        """整体复发率 ∈ [0, 1]。"""
        loop, _ = ll_env
        rates = loop.recurrence_rate(months=3)
        r = rates["_summary"]["recurrence_rate"]
        assert 0.0 <= r <= 1.0


class TestAutoApplyLessons:
    def test_auto_apply_returns_positive(self, ll_env):
        """有复发模式 → auto_apply_lessons 返回 > 0（不再返回 0 stub）。"""
        loop, _ = ll_env
        applied = loop.auto_apply_lessons(months=3)
        assert applied > 0

    def test_auto_applied_written_to_db(self, ll_env):
        """auto-applied 标记真实写入 learning_lessons。"""
        loop, db_path = ll_env
        loop.auto_apply_lessons(months=3)
        c = loop._get_conn()
        rows = c.execute("SELECT * FROM learning_lessons WHERE severity='auto'").fetchall()
        assert len(rows) > 0
        assert "auto-applied:judgment_density" in rows[0]["lesson"]

    def test_idempotent_no_duplicate(self, ll_env):
        """重复调用不产生重复标记（幂等）。"""
        loop, _ = ll_env
        loop.auto_apply_lessons(months=3)
        n1 = loop.auto_apply_lessons(months=3)
        c = loop._get_conn()
        rows = c.execute("SELECT * FROM learning_lessons WHERE severity='auto'").fetchall()
        assert n1 == 0
        # 每个失败类型最多一个 auto 标记
        types = [r["lesson"].split(":")[1] for r in rows]
        assert len(types) == len(set(types))
