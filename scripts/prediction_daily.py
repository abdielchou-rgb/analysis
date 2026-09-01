"""S1-1: 每日预测验证调度

作为每日调度入口：
1. 到期判定：created_at + 12M <= today → 到期待验
2. 对到期 pending 项，用 yfinance 回填验证结果
3. 对 ForwardPicksDB 做同样的到期验证
4. 输出 output/prediction_daily_<date>.md
5. 写 learning_data.db 的 improvement_tracking 事件
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("prediction_daily")

OUTPUT_DIR = _ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# ForwardPicksDB 到期验证
# ═══════════════════════════════════════════════════════════════

def _verify_forward_picks() -> dict:
    """对 ForwardPicksDB 中到期的 pending 项做验证。"""
    from core.forward_picks import ForwardPicksDB
    from core.benchmark_client import get_best_benchmark_return

    db = ForwardPicksDB()
    picks = db.load_all()
    today = datetime.now()
    due_window = timedelta(days=365)  # 12M

    stats = {"total": len(picks), "pending": 0, "due": 0, "verified": 0, "skipped": 0}
    newly_verified = []

    for p in picks:
        if p.verification_status != "pending":
            continue
        stats["pending"] += 1

        # 到期判定
        try:
            created = datetime.fromisoformat(p.created_at)
        except Exception:
            stats["skipped"] += 1
            continue

        if not p.created_at or (today - created) < due_window:
            continue  # 未到期

        stats["due"] += 1

        # 获取当前净值（用 anchor_nav 的基准对齐）
        # 使用 yfinance 获取当前价格
        try:
            import yfinance as yf
            from core.data_backends import _to_yfinance_ticker

            ticker = _to_yfinance_ticker(p.asset_code)
            if not ticker:
                stats["skipped"] += 1
                continue

            df = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
            if df is None or df.empty or "Close" not in df.columns:
                stats["skipped"] += 1
                continue

            current_nav = float(df["Close"].iloc[-1])

            # 获取基准收益
            _, bench_return = get_best_benchmark_return(p.created_at)

            # 更新验证
            updated = db.update_verification(p.pick_id, current_nav, bench_return)
            if updated:
                stats["verified"] += 1
                newly_verified.append({
                    "pick_id": p.pick_id,
                    "asset": p.asset_code,
                    "direction": p.direction,
                })
            else:
                stats["skipped"] += 1
        except Exception as e:
            logger.warning("验证 %s 失败: %s", p.pick_id, e)
            stats["skipped"] += 1

    return {"forward_picks": stats, "newly_verified": newly_verified}


# ═══════════════════════════════════════════════════════════════
# track_record.json 到期验证（复用 verify_predictions 逻辑）
# ═══════════════════════════════════════════════════════════════

def _verify_track_record() -> dict:
    """对 track_record.json 中到期的 pending 项做验证。"""
    from scripts.verify_predictions import load_track_record, save_track_record, verify_prediction

    predictions = load_track_record()
    if not predictions:
        return {"track_record": {"total": 0, "verified": 0}}

    updated = [verify_prediction(p) for p in predictions]
    save_track_record(updated)

    verified = [p for p in updated if p.get("outcome") != "pending"]
    return {
        "track_record": {
            "total": len(updated),
            "verified": len(verified),
        }
    }


# ═══════════════════════════════════════════════════════════════
# 归因写入 learning_loop
# ═══════════════════════════════════════════════════════════════

def _write_attribution_to_learning(newly_verified: list[dict]) -> int:
    """将新验证的 miss/partial 预测归因写入 learning_loop。"""
    if not newly_verified:
        return 0

    from core.forward_picks import ForwardPicksDB

    db = ForwardPicksDB()
    picks = db.load_all()
    pick_map = {p.pick_id: p for p in picks}

    written = 0
    for item in newly_verified:
        p = pick_map.get(item["pick_id"])
        if not p or p.verification_status in ("hit", "pending"):
            continue

        # 构建归因教训
        attribution = _attribute_pick(p)
        if not attribution:
            continue

        try:
            from pipeline.learning_loop import LearningLoop
            loop = LearningLoop()
            lesson = {
                "asset": p.asset_code,
                "industry": p.report_type,
                "bold_call_type": p.direction,
                "made_date": p.created_at,
                "outcome": p.verification_status,
                "attribution": attribution["tag"],
                "attribution_cn": attribution["tag_cn"],
                "alpha": p.alpha or 0,
                "key_variables": [p.key_variable] if p.key_variable else [],
                "falsification": [p.falsification] if p.falsification else [],
                "lesson": f"{p.asset_code} 预测{attribution['tag_cn']}：{attribution['note']}",
                "created_at": datetime.now().isoformat(),
            }
            loop.add_failure_pattern(lesson)
            written += 1
        except Exception as e:
            logger.debug("写入 learning_loop 失败: %s", e)

    return written


def _attribute_pick(pick) -> dict | None:
    """对单条 ForwardPick 做规则化归因。"""
    if pick.verification_status == "hit":
        return None

    actual = pick.actual_return or 0

    if pick.direction == "bull" and actual < -0.10:
        return {"tag": "direction_wrong", "tag_cn": "方向错", "note": "看多但大幅下跌"}
    elif pick.direction == "bear" and actual > 0.10:
        return {"tag": "direction_wrong", "tag_cn": "方向错", "note": "看空但大幅上涨"}
    elif abs(actual) < 0.05:
        return {"tag": "timing_off", "tag_cn": "时间错", "note": "方向可能对但时机不对"}
    elif pick.key_variable and pick.key_variable not in ("", "N/A"):
        return {"tag": "key_var_missed", "tag_cn": "关键变量未兑现", "note": f"关注变量: {pick.key_variable}"}
    else:
        return {"tag": "magnitude_off", "tag_cn": "幅度错", "note": "方向对但幅度偏差大"}


# ═══════════════════════════════════════════════════════════════
# 报告生成
# ═══════════════════════════════════════════════════════════════

def _generate_daily_report(fp_stats: dict, tr_stats: dict, lessons_written: int) -> str:
    """生成每日预测验证报告。"""
    now = datetime.now()
    lines = [
        f"# 每日预测验证 {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## ForwardPicksDB",
        f"- 总记录: {fp_stats.get('total', 0)}",
        f"- 待验证: {fp_stats.get('pending', 0)}",
        f"- 到期待验: {fp_stats.get('due', 0)}",
        f"- 本次验证: {fp_stats.get('verified', 0)}",
        f"- 跳过: {fp_stats.get('skipped', 0)}",
        "",
        "## Track Record",
        f"- 总记录: {tr_stats.get('total', 0)}",
        f"- 本次验证: {tr_stats.get('verified', 0)}",
        "",
        f"## 学习回流",
        f"- 写入归因教训: {lessons_written} 条",
    ]

    newly = fp_stats.get("newly_verified", [])
    if newly:
        lines.extend(["", "## 新验证明细"])
        for item in newly[:20]:
            lines.append(f"- {item['asset']} [{item['direction']}] {item['pick_id']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    logger.info("=== 每日预测验证调度 开始 ===")

    # 1. 验证 ForwardPicksDB
    fp_result = _verify_forward_picks()
    fp_stats = fp_result["forward_picks"]
    logger.info("ForwardPicksDB: %s", fp_stats)

    # 2. 验证 track_record.json
    tr_result = _verify_track_record()
    tr_stats = tr_result["track_record"]
    logger.info("Track Record: %s", tr_stats)

    # 3. 归因写入 learning_loop
    lessons_written = _write_attribution_to_learning(fp_result["newly_verified"])
    logger.info("归因教训写入: %d 条", lessons_written)

    # 4. 生成每日报告
    report = _generate_daily_report(fp_stats, tr_stats, lessons_written)
    report_file = OUTPUT_DIR / f"prediction_daily_{datetime.now().strftime('%Y%m%d')}.md"
    report_file.write_text(report, encoding="utf-8")
    logger.info("每日报告: %s", report_file)

    # 5. 记录 improvement_tracking 事件
    _log_improvement_event(fp_stats, tr_stats, lessons_written)

    logger.info("=== 每日预测验证调度 完成 ===")


def _log_improvement_event(fp_stats: dict, tr_stats: dict, lessons_written: int):
    """写入 learning_data.db 的 improvement_tracking 表。"""
    import sqlite3

    db_path = _ROOT / "data" / "learning_data.db"
    if not db_path.exists():
        return

    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS improvement_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                event_date TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        details = json.dumps({
            "fp_verified": fp_stats.get("verified", 0),
            "tr_verified": tr_stats.get("verified", 0),
            "lessons_written": lessons_written,
        }, ensure_ascii=False)
        conn.execute(
            "INSERT INTO improvement_tracking (event_type, event_date, details) VALUES (?, ?, ?)",
            ("prediction_verified", datetime.now().strftime("%Y-%m-%d"), details),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("写入 improvement_tracking 失败: %s", e)


if __name__ == "__main__":
    main()
