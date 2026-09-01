#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2-1c (2026-09-01): 学习健康度/复发率曲线——FP5 收敛指标可视化。

产出：近 N 周每周 top 失败项的复发率曲线（output/learning_health_<date>.md）。
FP5 宪法要求："同类型 Gate 失败的复发率必须逐月下降（目标月环比降 50%）"——
此前无任何工具测量此指标（learning_loop.recurrence_rate 是 stub，现已真实现）。

本脚本把 recurrence_rate 聚合到周粒度，画出：
1. 每周总失败数（量）
2. 每周 top 失败项出现次数（复发监测）
3. 复发率周趋势（最近周 vs 前一周 → 是否在收敛）

用法：
    python scripts/learning_health.py                  # 近 8 周
    python scripts/learning_health.py --weeks 12
    python scripts/learning_health.py --out report.md
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _safe_db():
    """复制 learning_data.db 到临时文件（防 Windows 文件锁 disk I/O error）。"""
    import shutil
    import tempfile

    src = _ROOT / "data" / "learning_data.db"
    tmp = Path(tempfile.mkdtemp()) / "learning_health.db"
    try:
        shutil.copy2(str(src), str(tmp))
        return tmp
    except Exception as e:
        print(f"[HEALTH] db 复制失败: {e}")
        return src


def weekly_failures(weeks: int) -> list[dict]:
    """按 ISO 周聚合失败数。返回 [{week_start, total, top: {type: count}}, ...]。"""
    db = _safe_db()
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    # 用 sqlite 的 strftime 按周聚合（ISO 周）
    rows = conn.execute(
        """
        SELECT strftime('%Y-W%W', created_at) as wk,
               failure_type,
               COUNT(*) as cnt
        FROM report_failures
        WHERE created_at >= datetime('now', ?)
        GROUP BY wk, failure_type
        ORDER BY wk
        """,
        (f"-{weeks * 7 + 7} days",),
    ).fetchall()
    conn.close()

    by_week: dict[str, dict] = {}
    for r in rows:
        wk = r["wk"]
        w = by_week.setdefault(wk, {"week": wk, "total": 0, "top": {}})
        w["total"] += r["cnt"]
        w["top"][r["failure_type"]] = r["cnt"]
    return list(by_week.values())


def render_md(weeks_data: list[dict], weeks: int) -> str:
    lines = [
        "# 学习健康度 / 复发率曲线",
        "",
        f"**日期**：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**窗口**：近 {weeks} 周（数据源：data/learning_data.db report_failures）",
        "",
        "## 周失败总量趋势",
        "",
        "| 周 | 失败总数 | top 失败项 |",
        "|---|---|---|",
    ]
    for w in weeks_data:
        top_items = sorted(w["top"].items(), key=lambda x: -x[1])[:3]
        top_str = "; ".join(f"{t}({c})" for t, c in top_items)
        lines.append(f"| {w['week']} | {w['total']} | {top_str} |")

    lines.append("")
    lines.append("## 复发率评估（FP5 收敛指标）")
    lines.append("")
    if len(weeks_data) >= 2:
        last = weeks_data[-1]["total"]
        prev = weeks_data[-2]["total"]
        delta = (last - prev) / prev * 100 if prev else 0
        trend = "📉 下降（收敛）" if delta < 0 else "📈 上升（发散）" if delta > 0 else "➡️ 持平"
        lines.append(f"- 最近周（{weeks_data[-1]['week']}）：{last} 次 vs 前周（{weeks_data[-2]['week']}）：{prev} 次")
        lines.append(f"- 周环比：{delta:+.1f}% → **{trend}**")
        if delta > 0:
            lines.append("- ⚠️ 失败数上升——需对照 failure_triage 报告归因，优先处理复发项")
        lines.append("")
        # 判断密度/数据密度的每周均分（从 report_scores）
        db = _safe_db()
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        scores = conn.execute(
            """
            SELECT strftime('%Y-W%W', created_at) as wk, AVG(score) as avg_score, COUNT(*) as n
            FROM report_scores
            WHERE created_at >= datetime('now', ?)
            GROUP BY wk ORDER BY wk
            """,
            (f"-{weeks * 7 + 7} days",),
        ).fetchall()
        conn.close()
        if scores:
            lines.append("## 周均 Gate 分趋势")
            lines.append("")
            lines.append("| 周 | 均分 | 样本数 |")
            lines.append("|---|---|---|")
            for s in scores:
                lines.append(f"| {s['wk']} | {s['avg_score']:.3f} | {s['n']} |")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(
        "> FP5 要求复发率逐月下降 50%。本曲线是收敛指标的第一份基线——后续每周跑一次，观察 top 失败项是否随修复递减。"
    )
    lines.append("> 铁律：复发项必须先归因（gate_failure_triage.py）再修，禁止盲改。")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="学习健康度/复发率曲线")
    parser.add_argument("--weeks", type=int, default=8)
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()

    data = weekly_failures(args.weeks)
    if not data:
        print("[HEALTH] 无失败数据")
        return
    md = render_md(data, args.weeks)
    out_path = (
        Path(args.out) if args.out else _ROOT / "output" / f"learning_health_{datetime.now().strftime('%Y%m%d')}.md"
    )
    out_path.write_text(md, encoding="utf-8")
    print(f"[HEALTH] 报告已写入: {out_path}")
    # 控制台摘要
    if len(data) >= 2:
        last, prev = data[-1]["total"], data[-2]["total"]
        delta = (last - prev) / prev * 100 if prev else 0
        print(f"[HEALTH] 最近周 {last} vs 前周 {prev} → {delta:+.1f}% ({'收敛' if delta < 0 else '发散'})")
        top = sorted(data[-1]["top"].items(), key=lambda x: -x[1])[:3]
        print("[HEALTH] top 失败项:", "; ".join(f"{t}={c}" for t, c in top))


if __name__ == "__main__":
    main()
