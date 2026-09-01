#!/usr/bin/env python3
"""quality_trends_report.py — 质量趋势收敛曲线报告。

读取 observability.db 的 quality_trends 表，生成收敛趋势报告。
支持：gate_score_avg / gate_pass_rate / failure_count / recurrence_rate。

用法:
    python scripts/quality_trends_report.py
    python scripts/quality_trends_report.py --days 30
    python scripts/quality_trends_report.py --metric gate_score_avg
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "observability.db"
OUTPUT_DIR = ROOT / "output" / "prediction_health"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def query_trends(days: int = 30, metric: str = "") -> list[dict]:
    """查询 quality_trends 数据。"""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        # 检查表是否存在
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "quality_trends" not in tables:
            return []
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        if metric:
            rows = conn.execute(
                "SELECT date, metric_name, metric_value, sample_size FROM quality_trends "
                "WHERE date >= ? AND metric_name = ? ORDER BY date",
                (cutoff, metric),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT date, metric_name, metric_value, sample_size FROM quality_trends "
                "WHERE date >= ? ORDER BY date, metric_name",
                (cutoff,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def compute_stats(rows: list[dict]) -> dict:
    """计算各指标的统计摘要。"""
    metrics = {}
    for r in rows:
        name = r["metric_name"]
        if name not in metrics:
            metrics[name] = {"values": [], "dates": []}
        metrics[name]["values"].append(r["metric_value"])
        metrics[name]["dates"].append(r["date"])

    stats = {}
    for name, data in metrics.items():
        vals = data["values"]
        if not vals:
            continue
        n = len(vals)
        avg = sum(vals) / n
        first_half = vals[: n // 2] if n > 2 else vals[:1]
        second_half = vals[n // 2 :] if n > 2 else vals[1:]
        first_avg = sum(first_half) / len(first_half) if first_half else 0
        second_avg = sum(second_half) / len(second_half) if second_half else 0
        trend = "improving" if second_avg > first_avg else ("declining" if second_avg < first_avg else "stable")
        # 特殊处理：failure_count 越低越好
        if "failure" in name:
            trend = "improving" if second_avg < first_avg else ("declining" if second_avg > first_avg else "stable")

        stats[name] = {
            "count": n,
            "avg": round(avg, 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "latest": round(vals[-1], 4),
            "first_avg": round(first_avg, 4),
            "second_avg": round(second_avg, 4),
            "trend": trend,
            "first_date": data["dates"][0],
            "last_date": data["dates"][-1],
        }
    return stats


def generate_report(stats: dict, days: int) -> str:
    """生成 markdown 报告。"""
    lines = [
        "# 质量趋势收敛报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**统计窗口**: 最近 {days} 天",
        "",
    ]

    if not stats:
        lines.append("**无数据** — quality_trends 表为空。每次 Gate 运行后会自动写入。")
        return "\n".join(lines)

    lines.append("## 指标摘要")
    lines.append("")
    lines.append("| 指标 | 样本数 | 均值 | 最新 | 最小 | 最大 | 趋势 |")
    lines.append("|------|--------|------|------|------|------|------|")

    trend_icons = {"improving": "📈", "declining": "📉", "stable": "➡️"}
    for name, s in sorted(stats.items()):
        icon = trend_icons.get(s["trend"], "")
        lines.append(
            f"| {name} | {s['count']} | {s['avg']:.4f} | {s['latest']:.4f} | "
            f"{s['min']:.4f} | {s['max']:.4f} | {icon} {s['trend']} |"
        )

    lines.append("")
    lines.append("## 收敛分析")
    lines.append("")

    for name, s in sorted(stats.items()):
        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"- 前半期均值: {s['first_avg']:.4f} ({s['first_date']})")
        lines.append(f"- 后半期均值: {s['second_avg']:.4f} ({s['last_date']})")
        delta = s["second_avg"] - s["first_avg"]
        if "failure" in name:
            delta_pct = abs(delta) / s["first_avg"] * 100 if s["first_avg"] else 0
            lines.append(f"- 变化: {delta:+.4f} ({delta_pct:+.1f}%)")
        else:
            delta_pct = delta / s["first_avg"] * 100 if s["first_avg"] else 0
            lines.append(f"- 变化: {delta:+.4f} ({delta_pct:+.1f}%)")
        lines.append(f"- 判定: **{s['trend']}**")
        lines.append("")

    lines.append("---")
    lines.append("*数据来源: observability.db quality_trends*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="质量趋势收敛报告")
    parser.add_argument("--days", type=int, default=30, help="统计窗口天数")
    parser.add_argument("--metric", default="", help="指定指标名（空=全部）")
    args = parser.parse_args()

    rows = query_trends(days=args.days, metric=args.metric)
    stats = compute_stats(rows)
    report = generate_report(stats, args.days)

    out_path = OUTPUT_DIR / f"quality_trends_{datetime.now().strftime('%Y%m%d')}.md"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n报告已写入: {out_path}")


if __name__ == "__main__":
    main()
