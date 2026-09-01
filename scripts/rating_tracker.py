"""S6-1: 评级变更追踪

对比历史报告评级（data/ratings_history.json）：
- 同标的评级变化 → 输出 output/rating_changes_<date>.md + 变更说明模板
"""

from __future__ import annotations

import json
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
logger = logging.getLogger("rating_tracker")

OUTPUT_DIR = _ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RATINGS_HISTORY = _ROOT / "data" / "ratings_history.json"

RATING_ORDER = {"strong_buy": 5, "buy": 4, "hold": 3, "sell": 2, "strong_sell": 1}


def _load_ratings_history() -> dict[str, list[dict]]:
    """加载评级历史。"""
    if not RATINGS_HISTORY.exists():
        return {}
    with open(RATINGS_HISTORY, encoding="utf-8") as f:
        data = json.load(f)
    return data


def detect_rating_changes(history: dict[str, list[dict]]) -> list[dict]:
    """检测评级变更。"""
    changes = []

    for code, ratings in history.items():
        if len(ratings) < 2:
            continue

        sorted_ratings = sorted(ratings, key=lambda r: r.get("date", ""))
        latest = sorted_ratings[-1]
        previous = sorted_ratings[-2]

        latest_rating = latest.get("rating", "").lower()
        previous_rating = previous.get("rating", "").lower()

        if latest_rating != previous_rating:
            # 计算方向
            latest_val = RATING_ORDER.get(latest_rating, 0)
            previous_val = RATING_ORDER.get(previous_rating, 0)
            direction = "上调" if latest_val > previous_val else "下调"

            changes.append({
                "code": code,
                "name": latest.get("name", code),
                "previous_rating": previous_rating,
                "latest_rating": latest_rating,
                "direction": direction,
                "previous_date": previous.get("date", ""),
                "latest_date": latest.get("date", ""),
                "analyst": latest.get("analyst", ""),
            })

    return changes


def generate_change_template(change: dict) -> str:
    """生成评级变更说明模板。"""
    return f"""## 评级变更说明

**标的**: {change['name']} ({change['code']})
**变更方向**: {change['previous_rating']} → {change['latest_rating']} ({change['direction']})
**变更日期**: {change['latest_date']}
**分析师**: {change['analyst']}

### 变更原因

[请填写具体原因，例如:]
- 基本面变化：
- 估值调整：
- 行业环境：
- 风险因素：

### 风险提示

本报告基于公开信息，不构成投资建议。评级变更反映了分析师对标的最新评估，投资者应独立判断。
"""


def main():
    logger.info("=== 评级变更追踪 ===")
    history = _load_ratings_history()
    changes = detect_rating_changes(history)
    logger.info("检测到 %d 条评级变更", len(changes))

    lines = [
        f"# 评级变更追踪 {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"总计 {len(changes)} 条评级变更",
        "",
    ]

    for c in changes:
        lines.append(f"- **{c['name']}** ({c['code']}): {c['previous_rating']} → {c['latest_rating']} ({c['direction']}, {c['latest_date']})")

    if changes:
        lines.extend(["", "## 变更说明模板"])
        for c in changes[:5]:
            lines.append(generate_change_template(c))

    report = "\n".join(lines)
    report_file = OUTPUT_DIR / f"rating_changes_{datetime.now().strftime('%Y%m%d')}.md"
    report_file.write_text(report, encoding="utf-8")
    logger.info("评级变更报告: %s", report_file)


if __name__ == "__main__":
    main()
