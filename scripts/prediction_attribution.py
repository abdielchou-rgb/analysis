"""S1-3: 预测误差归因

对 miss/partial 预测做规则化归因：
- 方向错：actual_return 与 direction 相反
- 幅度错：方向对但 |actual|<|target| 的 50%
- 时间错：方向对但幅度小
- 关键变量错：从 core_thesis/key_variable 提取的指标未兑现
→ 归因标签写回 learning_loop（作为写作规避信号）
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("prediction_attribution")

# 归因标签定义
ATTRIBUTION_TAGS = {
    "direction_wrong": "方向错",
    "magnitude_off": "幅度错",
    "timing_off": "时间错",
    "key_var_missed": "关键变量未兑现",
    "black_swan": "黑天鹅事件",
    "sector_rotation": "板块轮动",
    "policy_shift": "政策转向",
    "earnings_miss": "业绩不及预期",
    "unknown": "未知原因",
}


def attribute(pick) -> dict | None:
    """对单条 ForwardPick 做规则化归因。

    Returns:
        {"tag": str, "tag_cn": str, "note": str} 或 None（hit 无需归因）
    """
    if pick.verification_status == "hit":
        return None

    actual = pick.actual_return or 0
    base_target = pick.base_target or 0

    # 方向错
    if pick.direction == "bull" and actual < -0.10:
        return {
            "tag": "direction_wrong",
            "tag_cn": "方向错",
            "note": f"看多但下跌 {actual:.1%}",
        }
    if pick.direction == "bear" and actual > 0.10:
        return {
            "tag": "direction_wrong",
            "tag_cn": "方向错",
            "note": f"看空但上涨 {actual:.1%}",
        }

    # 时间错（方向可能对但幅度太小）
    if abs(actual) < 0.05:
        return {
            "tag": "timing_off",
            "tag_cn": "时间错",
            "note": f"收益仅 {actual:.1%}，时机不对",
        }

    # 幅度错（方向对但偏差大）
    if pick.direction == "bull" and actual > 0:
        expected_min = abs(base_target - pick.current_price) / pick.current_price * 0.5 if pick.current_price > 0 else 0.1
        if actual < expected_min:
            return {
                "tag": "magnitude_off",
                "tag_cn": "幅度错",
                "note": f"看多上涨但仅 {actual:.1%}，不及预期幅度",
            }
    elif pick.direction == "bear" and actual < 0:
        expected_min = abs(base_target - pick.current_price) / pick.current_price * 0.5 if pick.current_price > 0 else 0.1
        if abs(actual) < expected_min:
            return {
                "tag": "magnitude_off",
                "tag_cn": "幅度错",
                "note": f"看空下跌但仅 {actual:.1%}，不及预期幅度",
            }

    # 关键变量错
    if pick.key_variable and pick.key_variable not in ("", "N/A"):
        return {
            "tag": "key_var_missed",
            "tag_cn": "关键变量未兑现",
            "note": f"关键变量「{pick.key_variable}」未兑现",
        }

    # 默认归因
    return {
        "tag": "magnitude_off",
        "tag_cn": "幅度错",
        "note": f"方向对但幅度偏差：{actual:.1%}",
    }


def attribute_all_pending() -> list[dict]:
    """对所有 miss/partial 的 ForwardPick 做归因，返回归因结果列表。"""
    from core.forward_picks import ForwardPicksDB

    db = ForwardPicksDB()
    picks = db.load_all()

    results = []
    for p in picks:
        if p.verification_status not in ("miss", "partial"):
            continue
        attr = attribute(p)
        if attr:
            results.append({
                "pick_id": p.pick_id,
                "asset": p.asset_code,
                "direction": p.direction,
                "status": p.verification_status,
                "actual_return": p.actual_return,
                "alpha": p.alpha,
                **attr,
            })

    return results


def write_back_to_learning(results: list[dict]) -> int:
    """将归因结果写入 learning_loop（prediction_miss 教训）。"""
    if not results:
        return 0

    try:
        from pipeline.learning_loop import LearningLoop
        loop = LearningLoop()
    except Exception as e:
        logger.warning("无法加载 LearningLoop: %s", e)
        return 0

    written = 0
    for r in results:
        lesson = {
            "asset": r.get("asset", ""),
            "industry": "",
            "bold_call_type": r.get("direction", ""),
            "made_date": "",
            "outcome": r.get("status", ""),
            "attribution": r.get("tag", ""),
            "attribution_cn": r.get("tag_cn", ""),
            "alpha": r.get("alpha", 0),
            "key_variables": [],
            "falsification": [],
            "lesson": f"prediction_miss: {r.get('tag_cn', '')} — {r.get('note', '')}",
            "created_at": datetime.now().isoformat(),
        }
        try:
            loop.add_failure_pattern(lesson)
            written += 1
        except Exception as e:
            logger.debug("写入失败: %s", e)

    return written


def main():
    """独立运行归因分析。"""
    logger.info("=== 预测归因分析 开始 ===")

    results = attribute_all_pending()
    logger.info("归因结果: %d 条", len(results))

    for r in results:
        logger.info("  %s [%s] %s: %s", r["asset"], r["status"], r["tag_cn"], r["note"])

    written = write_back_to_learning(results)
    logger.info("写入 learning_loop: %d 条", written)

    # 输出归因报告
    from scripts.prediction_daily import OUTPUT_DIR
    report_file = OUTPUT_DIR / f"prediction_attribution_{datetime.now().strftime('%Y%m%d')}.md"

    lines = [
        f"# 预测归因报告 {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"总计 {len(results)} 条 miss/partial 预测",
        f"写入学习库 {written} 条教训",
        "",
        "## 归因明细",
    ]
    for r in results:
        lines.append(f"- **{r['asset']}** [{r['status']}] {r['tag_cn']}: {r['note']} (Alpha: {r.get('alpha', 0):.1%})")

    # 归因分布
    tag_counts = {}
    for r in results:
        tag_counts[r["tag_cn"]] = tag_counts.get(r["tag_cn"], 0) + 1
    lines.extend(["", "## 归因分布"])
    for tag, cnt in sorted(tag_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {tag}: {cnt}")

    report_file.write_text("\n".join(lines), encoding="utf-8")
    logger.info("归因报告: %s", report_file)


if __name__ == "__main__":
    main()
