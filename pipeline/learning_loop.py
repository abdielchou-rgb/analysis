"""learning_loop.py V3 — 增强学习循环：写入回测失败→读取学习经验"""
from __future__ import annotations
import logging, sqlite3, json
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.learning_loop")
# R78（2026-08-05 Phase2.2）：learning DB 从 output/ 迁到 data/——output/ 会被
# .gitignore 忽略且会被 cleanup 清理，学习数据不应丢失。
LEARNING_DB = Path(__file__).resolve().parent.parent / "data" / "learning_data.db"


class LearningLoop:
    def __init__(self):
        self._db_path = LEARNING_DB
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        try:
            c = self._get_conn()
            # Report failures table
            c.execute("""CREATE TABLE IF NOT EXISTS report_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT, report_type TEXT,
                failure_type TEXT, failure_detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            # Scoring history
            c.execute("""CREATE TABLE IF NOT EXISTS report_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT, report_type TEXT,
                dimension TEXT, score REAL, passed INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            # Learning lessons (extracted from failures)
            c.execute("""CREATE TABLE IF NOT EXISTS learning_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT, report_type TEXT,
                lesson TEXT, severity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            # Improvement tracking
            c.execute("""CREATE TABLE IF NOT EXISTS improvement_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT, report_type TEXT,
                attempt INTEGER, score REAL, fix_action TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            c.commit()
        except Exception as e:
            logger.warning("DB init: %s", e)

    def before_report(self, asset: str, report_type: str) -> str:
        """加载历史经验，注入到写作提示"""
        parts = []
        try:
            c = self._get_conn()
            # 1. 历史失败模式
            rows = c.execute("""
                SELECT failure_type, failure_detail, COUNT(*) as cnt
                FROM report_failures
                WHERE asset=? AND report_type=?
                GROUP BY failure_type ORDER BY cnt DESC LIMIT 5
            """, (asset, report_type)).fetchall()
            if rows:
                parts.append("历史失败(previous failures):")
                for r in rows:
                    parts.append("  - {}: {}次 ({})".format(
                        r['failure_type'], r['cnt'], str(r['failure_detail'])[:80]))
            
            # 2. 学到的经验教训
            lessons = c.execute("""
                SELECT lesson FROM learning_lessons
                WHERE (asset=? OR asset='*') AND (report_type=? OR report_type='*')
                ORDER BY created_at DESC LIMIT 5
            """, (asset, report_type)).fetchall()
            if lessons:
                parts.append("经验教训(lessons learned):")
                for l in lessons:
                    parts.append("  - " + str(l['lesson'])[:120])
            
            # 3. 最近评分趋势
            scores = c.execute("""
                SELECT AVG(score) as avg_score, COUNT(*) as cnt
                FROM report_scores
                WHERE asset=? AND report_type=? AND passed=1
            """, (asset, report_type)).fetchone()
            if scores and scores['cnt'] > 0:
                parts.append("历史评分: 平均{:.2f} / {}次通过".format(
                    scores['avg_score'], scores['cnt']))
            
            # 4. 近期改进记录
            improvements = c.execute("""
                SELECT fix_action, score FROM improvement_tracking
                WHERE asset=? AND report_type=?
                ORDER BY created_at DESC LIMIT 3
            """, (asset, report_type)).fetchall()
            if improvements:
                parts.append("近期改进(recent improvements):")
                for imp in improvements:
                    parts.append("  - {} (score={:.2f})".format(
                        str(imp['fix_action'])[:100], imp['score']))

        except Exception as e:
            logger.debug("before_report: %s", e)
        
        result = "\n".join(parts) if parts else ""
        if result:
            logger.info("LearningLoop: %d chars of history loaded", len(result))
        return result

    def after_report(self, asset: str, report_type: str, result: dict):
        """报告完成后记录结果"""
        try:
            c = self._get_conn()
            
            # 记录评分
            s = result.get("iron_gate", 0)
            if isinstance(s, (int, float)):
                c.execute(
                    "INSERT INTO report_scores (asset,report_type,dimension,score,passed) VALUES (?,?,?,?,?)",
                    (asset, report_type, "iron_gate_overall", s, 1 if result.get("passed") else 0)
                )
            
            # 记录失败原因
            for f in result.get("failures", []):
                ft = f.split(":")[0] if ":" in f else "general"
                c.execute(
                    "INSERT INTO report_failures (asset,report_type,failure_type,failure_detail) VALUES (?,?,?,?)",
                    (asset, report_type, ft[:50], str(f)[:200])
                )
            
            # 提取经验教训：从未通过的检查项生成本次教训
            if not result.get("passed"):
                failures = result.get("failures", [])
                if failures:
                    lesson = "本轮失败: " + "; ".join(f[:100] for f in failures[:3])
                    c.execute(
                        "INSERT INTO learning_lessons (asset,report_type,lesson,severity) VALUES (?,?,?,?)",
                        (asset, report_type, lesson[:300], "warning")
                    )
            
            # 记录改进尝试
            attempt = result.get("attempt", 0)
            # Always record improvement tracking (even attempt 0 is a baseline)
            c.execute(
                "INSERT INTO improvement_tracking (asset,report_type,attempt,score,fix_action) VALUES (?,?,?,?,?)",
                (asset, report_type, attempt, s,
                 "Attempt {}: score={} passed={}".format(attempt, s, result.get("passed")))
            )
            
            c.commit()
            logger.info("LearningLoop: recorded results for %s (%s)", asset, report_type)
        except Exception as e:
            logger.debug("after_report: %s", e)

    def add_lesson(self, asset: str, report_type: str, lesson: str, severity: str = "info"):
        """手动添加经验教训"""
        try:
            c = self._get_conn()
            c.execute(
                "INSERT INTO learning_lessons (asset,report_type,lesson,severity) VALUES (?,?,?,?)",
                (asset, report_type, lesson[:500], severity)
            )
            c.commit()
        except Exception as e:
            logger.debug("add_lesson: %s", e)

    def recurrence_rate(self, months: int = 3) -> dict:
        """FP5: Calculate recurrence rate for each failure pattern"""
        return {}  # Stub

    def auto_apply_lessons(self) -> int:
        """FP5: Auto-apply top failure patterns"""
        return 0  # Stub

    def get_lessons(self, asset: str = "*", report_type: str = "*",
                   limit: int = 10, by_failure_type: bool = True) -> dict:
        """返回最近失败经验，按失败类型聚合（供 SectionWriter 强制注入）。

        Args:
            asset: 标的过滤（默认 * 表示全部）
            report_type: 报告类型过滤（默认 * 表示全部）
            limit: 最多返回条数
            by_failure_type: 是否按失败类型聚合

        Returns:
            { "failures_by_type": {type: [details]},
              "lessons": [str, ...],
              "recent_scores": {"avg": float, "count": int} }
        """
        result: dict = {
            "failures_by_type": {},
            "lessons": [],
            "recent_scores": {"avg": 0.0, "count": 0},
        }
        try:
            c = self._get_conn()

            # 按失败类型聚合
            rows = c.execute("""
                SELECT failure_type, failure_detail, COUNT(*) as cnt, MAX(created_at) as latest
                FROM report_failures
                WHERE (asset=? OR ?='*') AND (report_type=? OR ?='*')
                GROUP BY failure_type ORDER BY cnt DESC LIMIT ?
            """, (asset, asset, report_type, report_type, limit)).fetchall()
            for r in rows:
                ft = r["failure_type"]
                if ft not in result["failures_by_type"]:
                    result["failures_by_type"][ft] = []
                result["failures_by_type"][ft].append({
                    "detail": str(r["failure_detail"])[:200],
                    "count": r["cnt"],
                    "latest": str(r["latest"]),
                })

            # 经验教训
            lessons = c.execute("""
                SELECT lesson FROM learning_lessons
                WHERE (asset=? OR asset='*' OR ?='*')
                  AND (report_type=? OR report_type='*' OR ?='*')
                ORDER BY created_at DESC LIMIT ?
            """, (asset, asset, report_type, report_type, limit)).fetchall()
            result["lessons"] = [str(l["lesson"])[:200] for l in lessons]

            # 最近评分
            scores = c.execute("""
                SELECT AVG(score) as avg_score, COUNT(*) as cnt
                FROM report_scores
                WHERE (asset=? OR ?='*') AND (report_type=? OR ?='*')
            """, (asset, asset, report_type, report_type)).fetchone()
            if scores and scores["cnt"] > 0:
                result["recent_scores"] = {
                    "avg": round(scores["avg_score"], 2),
                    "count": scores["cnt"],
                }
        except Exception as e:
            logger.debug("get_lessons: %s", e)
        return result

    def build_lesson_prompt(self, asset: str = "*", report_type: str = "*") -> str:
        """构建注入 SectionWriter 的「经验教训提示」片段。

        供 SectionWriter / E2E Orchestrator 在写作前调用的标准接口。
        返回可直接拼接到写作 prompt 的文本块。

        Returns:
            str: 格式化的 lesson prompt，若无可供经验则返回空字符串
        """
        data = self.get_lessons(asset=asset, report_type=report_type)
        parts = []

        failures = data.get("failures_by_type", {})
        if failures:
            parts.append("## 历史失败经验（本次务必避免）")
            for ftype, details in failures.items():
                total_cnt = sum(d["count"] for d in details)
                sample = details[0]["detail"] if details else ""
                parts.append(f"- [{ftype}]（累计{total_cnt}次）：{sample}")

        lessons = data.get("lessons", [])
        if lessons:
            parts.append("\n## 已学到的经验教训")
            for i, l in enumerate(lessons[:5]):
                parts.append(f"- 教训{i+1}：{l}")

        scores = data.get("recent_scores", {})
        if scores.get("count", 0) > 0:
            parts.append(
                f"\n## 历史评分参考：平均 {scores['avg']} / {scores['count']} 次通过"
            )

        return "\n".join(parts) if parts else ""
        try:
            c = self._get_conn()
            return {
                "failures": c.execute("SELECT COUNT(*) FROM report_failures").fetchone()[0],
                "scores": c.execute("SELECT COUNT(*) FROM report_scores").fetchone()[0],
                "lessons": c.execute("SELECT COUNT(*) FROM learning_lessons").fetchone()[0],
                "improvements": c.execute("SELECT COUNT(*) FROM improvement_tracking").fetchone()[0],
            }
        except Exception:


            return {"failures": 0, "scores": 0, "lessons": 0, "improvements": 0}
