# -*- coding: utf-8 -*-
"""reviewer_reputation.py — 圆桌信誉机制（P3-3，2026-08-07）

治圆桌激励倒挂（圆桌批判 I3）：评审不担责 → 评审宽松 → "看起来对"替代"真的对"。

机制：
  1. 记录每次终局圆桌的评审结论（各角色对报告的 overall_score + 关键判断）
  2. 报告关键判断进 prediction_loop（30 天回测）
  3. 回测结果回来后，比对评审当时的判断 → 正确计正分，错误计负分
  4. 信誉分影响下次评审权重（信誉高 → 权重高）

用法：
  rr = ReviewerReputation()
  rr.record_review(role_id, report_id, overall_score, key_claims)
  rr.update_from_backtest(report_id, backtest_accuracy)   # 回测后调
  w = rr.get_weight(role_id)                               # 信誉加权
"""
from __future__ import annotations
import json, sqlite3, logging, time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.reviewer_reputation")

_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "data" / "reviewer_reputation.db"

# 信誉分参数
BASE_CREDIT = 100        # 初始信誉分
CORRECT_BONUS = 5        # 判断正确加分
WRONG_PENALTY = 8        # 判断错误扣分（扣比加多，防"乱猜无害"）
FLOOR = 20               # 信誉分下限（防归零但保留参与）

INIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    role_id TEXT,
    report_id TEXT,
    overall_score REAL,
    key_claims TEXT,
    verified INTEGER DEFAULT 0,
    backtest_accuracy REAL DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS reputation (
    role_id TEXT PRIMARY KEY,
    credit INTEGER DEFAULT 100,
    reviews_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    last_updated TEXT
);
"""


class ReviewerReputation:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript(INIT_SCHEMA)
        conn.commit()
        conn.close()

    def record_review(self, role_id: str, report_id: str,
                      overall_score: float, key_claims: Optional[list] = None) -> None:
        """记录一次评审。key_claims 是该角色本次的关键判断（待回测）。"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO reviews (timestamp, role_id, report_id, overall_score, key_claims)
            VALUES (?, ?, ?, ?, ?)
        """, (time.strftime("%Y-%m-%dT%H:%M:%S"), role_id, report_id,
              float(overall_score), json.dumps(key_claims or [], ensure_ascii=False)))
        # 同步信誉表
        conn.execute("""
            INSERT INTO reputation (role_id, credit, reviews_count) VALUES (?, ?, 1)
            ON CONFLICT(role_id) DO UPDATE SET
                reviews_count = reviews_count + 1,
                last_updated = excluded.last_updated
        """, (role_id, BASE_CREDIT))
        conn.commit()
        conn.close()

    def update_from_backtest(self, report_id: str, accuracy: float) -> None:
        """回测后更新信誉分：按该报告所有评审的准确率调整。
        accuracy 0-1：>0.6 视为判断正确（加分），<0.4 视为错误（扣分），中间不调整。
        """
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, role_id FROM reviews WHERE report_id=? AND verified=0",
            (report_id,)).fetchall()
        for rid, role_id in rows:
            delta = 0
            if accuracy >= 0.6:
                delta = CORRECT_BONUS
            elif accuracy < 0.4:
                delta = -WRONG_PENALTY
            if delta:
                conn.execute("""
                    UPDATE reputation SET
                        credit = MAX(?, credit + ?),
                        correct_count = correct_count + ?,
                        wrong_count = wrong_count + ?,
                        last_updated = ?
                    WHERE role_id = ?
                """, (FLOOR, delta,
                      1 if delta > 0 else 0,
                      1 if delta < 0 else 0,
                      time.strftime("%Y-%m-%dT%H:%M:%S"), role_id))
            conn.execute("UPDATE reviews SET verified=1, backtest_accuracy=? WHERE id=?",
                         (accuracy, rid))
        conn.commit()
        conn.close()
        logger.info("[REPUTATION] 报告 %s 回测完成，%d 条评审已更新信誉分", report_id, len(rows))

    def get_credit(self, role_id: str) -> int:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT credit FROM reputation WHERE role_id=?", (role_id,)).fetchone()
        conn.close()
        return row[0] if row else BASE_CREDIT

    def get_weight(self, role_id: str) -> float:
        """信誉加权：credit 相对基准的权重（0.5 - 1.5）。"""
        c = self.get_credit(role_id)
        return max(0.5, min(1.5, c / BASE_CREDIT))

    def get_stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT role_id, credit, reviews_count, correct_count, wrong_count FROM reputation"
        ).fetchall()
        conn.close()
        return [{"role": r[0], "credit": r[1], "reviews": r[2],
                 "correct": r[3], "wrong": r[4]} for r in rows]


def apply_reputation_weight(verdicts: list, weights: Optional[dict] = None) -> float:
    """按信誉分加权计算圆桌最终分（替代等权平均）。"""
    if not verdicts:
        return 0.0
    rr = ReviewerReputation()
    total_w = 0.0
    weighted = 0.0
    for v in verdicts:
        role_id = getattr(v, "role_id", "unknown")
        w = (weights or {}).get(role_id) or rr.get_weight(role_id)
        score = getattr(v, "overall_score", 0.5)
        weighted += score * w
        total_w += w
    return weighted / total_w if total_w else 0.0
