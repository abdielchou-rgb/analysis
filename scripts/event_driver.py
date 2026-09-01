"""S2-3: 事件驱动更新

扫描 company_events 近 7 天事件（收购/定增/评级变动）：
- 命中标的的已交付报告 → 标记需刷新
- 输出 output/stale_reports_<date>.md：需刷新报告清单
"""

from __future__ import annotations

import json
import logging
import sqlite3
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
logger = logging.getLogger("event_driver")

OUTPUT_DIR = _ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 事件类型关键词
EVENT_KEYWORDS = {
    "acquisition": ["收购", "并购", "重组"],
    "placement": ["定增", "非公开发行", "增发"],
    "rating_change": ["评级", "下调", "上调", "调低", "调高"],
    "pledge": ["质押", "解押"],
    "shareholder": ["减持", "增持", "举牌"],
    "regulatory": ["处罚", "立案", "警示", "问询"],
}


def _scan_company_events(days: int = 7) -> list[dict]:
    """扫描公司事件数据库近 N 天事件。"""
    db_path = _ROOT / "data" / "company_events.db"
    if not db_path.exists():
        logger.warning("company_events.db 不存在")
        return []

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    events = []

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 查询近 N 天事件
        tables = [row[0] for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]

        for table in tables:
            try:
                # 尝试多种可能的表结构
                rows = cursor.execute(
                    f"SELECT * FROM [{table}] WHERE date >= ? ORDER BY date DESC",
                    (cutoff,)
                ).fetchall()
                cols = [desc[0] for desc in cursor.description] if cursor.description else []

                for row in rows:
                    row_dict = dict(zip(cols, row))
                    row_dict["_source_table"] = table
                    events.append(row_dict)
            except Exception:
                # 表结构不匹配，跳过
                continue

        conn.close()
    except Exception as e:
        logger.warning("扫描公司事件失败: %s", e)

    return events


def _classify_events(events: list[dict]) -> dict[str, list[dict]]:
    """按事件类型分类。"""
    classified = {k: [] for k in EVENT_KEYWORDS}
    classified["other"] = []

    for event in events:
        text = json.dumps(event, ensure_ascii=False).lower()
        matched = False
        for etype, keywords in EVENT_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                classified[etype].append(event)
                matched = True
                break
        if not matched:
            classified["other"].append(event)

    return classified


def _find_affected_reports(events: list[dict]) -> list[dict]:
    """查找受影响的已交付报告。"""
    affected = []
    output_dir = _ROOT / "output"

    # 扫描已有报告
    if output_dir.exists():
        for f in output_dir.glob("**/*.md"):
            content = f.read_text(encoding="utf-8", errors="ignore")[:2000]
            for event in events:
                # 简单匹配：报告中出现事件相关代码
                code = event.get("code", event.get("stock_code", ""))
                if code and code in content:
                    affected.append({
                        "report_path": str(f),
                        "event": event,
                        "reason": f"报告涉及 {code}，近期有事件",
                    })
                    break

    return affected


def main():
    """扫描事件并生成刷新清单。"""
    logger.info("=== 事件驱动更新 扫描 ===")

    events = _scan_company_events(days=7)
    logger.info("近7天事件: %d 条", len(events))

    if not events:
        logger.info("无近期事件，无需刷新")
        return

    classified = _classify_events(events)
    for etype, elist in classified.items():
        if elist:
            logger.info("  %s: %d 条", etype, len(elist))

    affected = _find_affected_reports(events)
    logger.info("受影响报告: %d 份", len(affected))

    # 生成刷新清单
    lines = [
        f"# 需刷新报告清单 {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"## 事件概览",
        f"- 近7天事件总数: {len(events)}",
    ]

    for etype, elist in classified.items():
        if elist:
            lines.append(f"- {etype}: {len(elist)}")

    if affected:
        lines.extend(["", "## 需刷新报告"])
        for item in affected:
            lines.append(f"- {item['report_path']}: {item['reason']}")
    else:
        lines.extend(["", "## 无受影响报告"])

    report = "\n".join(lines)
    report_file = OUTPUT_DIR / f"stale_reports_{datetime.now().strftime('%Y%m%d')}.md"
    report_file.write_text(report, encoding="utf-8")
    logger.info("刷新清单: %s", report_file)


if __name__ == "__main__":
    main()
