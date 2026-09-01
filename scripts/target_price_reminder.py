"""S6-2: 目标价到期提醒

扫描 forward_picks + 报告，目标价 12M 到期：
- 到期前 30/7 天提醒
- 输出 output/target_price_due_<date>.md
"""

from __future__ import annotations

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
logger = logging.getLogger("target_price_reminder")

OUTPUT_DIR = _ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def check_target_price_due() -> list[dict]:
    """检查目标价到期情况。"""
    from core.forward_picks import ForwardPicksDB

    db = ForwardPicksDB()
    picks = db.load_all()
    today = datetime.now()

    due_items = []

    for p in picks:
        if not p.created_at:
            continue

        try:
            created = datetime.fromisoformat(p.created_at)
        except Exception:
            continue

        # 计算到期日（创建日 + 12M）
        due_date = created + timedelta(days=365)
        days_until = (due_date - today).days

        if -30 <= days_until <= 30:  # 到期前后30天内
            status = "overdue" if days_until < 0 else "due_soon" if days_until <= 7 else "upcoming"
            due_items.append({
                "pick_id": p.pick_id,
                "asset": p.asset_code,
                "direction": p.direction,
                "base_target": p.base_target,
                "current_price": p.current_price,
                "created_at": p.created_at,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "days_until": days_until,
                "status": status,
                "verification_status": p.verification_status,
            })

    return due_items


def main():
    logger.info("=== 目标价到期提醒 ===")
    items = check_target_price_due()

    if not items:
        logger.info("无目标价到期提醒")
        return

    lines = [
        f"# 目标价到期提醒 {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"总计 {len(items)} 条目标价到期/即将到期",
        "",
    ]

    # 按紧急程度分组
    overdue = [i for i in items if i["status"] == "overdue"]
    due_soon = [i for i in items if i["status"] == "due_soon"]
    upcoming = [i for i in items if i["status"] == "upcoming"]

    if overdue:
        lines.append("## 已过期")
        for i in overdue:
            price_note = f"目标 {i['base_target']}" if i['base_target'] else ""
            lines.append(f"- **{i['asset']}** ({i['direction']}) {price_note} — 过期 {abs(i['days_until'])} 天, 状态 {i['verification_status']}")
        lines.append("")

    if due_soon:
        lines.append("## 7天内到期")
        for i in due_soon:
            price_note = f"目标 {i['base_target']}" if i['base_target'] else ""
            lines.append(f"- **{i['asset']}** ({i['direction']}) {price_note} — {i['days_until']} 天后到期")
        lines.append("")

    if upcoming:
        lines.append("## 30天内到期")
        for i in upcoming[:20]:
            price_note = f"目标 {i['base_target']}" if i['base_target'] else ""
            lines.append(f"- **{i['asset']}** ({i['direction']}) {price_note} — {i['days_until']} 天后到期")

    report = "\n".join(lines)
    report_file = OUTPUT_DIR / f"target_price_due_{datetime.now().strftime('%Y%m%d')}.md"
    report_file.write_text(report, encoding="utf-8")
    logger.info("目标价到期提醒: %s", report_file)


if __name__ == "__main__":
    main()
