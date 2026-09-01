"""S1-4: 月度预测命中率报告

聚合月度预测业绩：
- 命中率（hit/总）
- alpha 均值/中位数
- 平均收益/最大回撤
- 按行业/方向/信心分组
输出 output/prediction_monthly_<YYYY-MM>.md
"""

from __future__ import annotations

import logging
import statistics
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
logger = logging.getLogger("prediction_monthly")

OUTPUT_DIR = _ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _collect_verified_this_month() -> list[dict]:
    """收集本月已验证的预测（ForwardPicksDB + track_record.json）。"""
    now = datetime.now()
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    month_end = now.strftime("%Y-%m-%d")

    results = []

    # 从 ForwardPicksDB
    try:
        from core.forward_picks import ForwardPicksDB
        db = ForwardPicksDB()
        for p in db.load_all():
            if p.verification_status == "pending":
                continue
            if p.verified_at and p.verified_at[:7] == now.strftime("%Y-%m"):
                results.append({
                    "asset": p.asset_code,
                    "direction": p.direction,
                    "outcome": p.verification_status,
                    "actual_return": p.actual_return or 0,
                    "alpha": p.alpha or 0,
                    "conviction": p.conviction,
                    "report_type": p.report_type,
                    "source": "forward_picks",
                })
    except Exception as e:
        logger.debug("ForwardPicksDB 读取失败: %s", e)

    # 从 track_record.json
    try:
        from scripts.verify_predictions import load_track_record
        for pred in load_track_record():
            if pred.get("outcome") in ("pending", "unverifiable"):
                continue
            va = pred.get("verified_at", "")
            if va and va[:7] == now.strftime("%Y-%m"):
                results.append({
                    "asset": pred.get("asset", ""),
                    "direction": pred.get("direction", ""),
                    "outcome": pred.get("outcome", ""),
                    "actual_return": pred.get("actual_return", 0),
                    "alpha": pred.get("alpha", 0),
                    "conviction": pred.get("conviction", ""),
                    "report_type": pred.get("report_type", ""),
                    "source": "track_record",
                })
    except Exception as e:
        logger.debug("track_record 读取失败: %s", e)

    return results


def _compute_monthly_stats(items: list[dict]) -> dict:
    """计算月度统计。"""
    if not items:
        return {"total": 0}

    hit = [i for i in items if i["outcome"] == "hit"]
    miss = [i for i in items if i["outcome"] == "miss"]
    partial = [i for i in items if i["outcome"] == "partial"]

    alphas = [i["alpha"] for i in items]
    returns = [i["actual_return"] for i in items]

    stats = {
        "total": len(items),
        "hit_count": len(hit),
        "miss_count": len(miss),
        "partial_count": len(partial),
        "hit_rate": len(hit) / len(items) if items else 0,
        "avg_alpha": statistics.mean(alphas) if alphas else 0,
        "median_alpha": statistics.median(alphas) if alphas else 0,
        "avg_return": statistics.mean(returns) if returns else 0,
        "max_drawdown": min(returns) if returns else 0,
        "best_alpha": max(alphas) if alphas else 0,
        "worst_alpha": min(alphas) if alphas else 0,
    }

    # 按行业分组
    by_industry = {}
    for i in items:
        ind = i.get("report_type", "未知")
        by_industry.setdefault(ind, []).append(i)
    stats["by_industry"] = {}
    for ind, group in by_industry.items():
        hr = sum(1 for g in group if g["outcome"] == "hit") / len(group)
        avg_a = statistics.mean([g["alpha"] for g in group])
        stats["by_industry"][ind] = {"count": len(group), "hit_rate": hr, "avg_alpha": avg_a}

    # 按方向分组
    by_dir = {}
    for i in items:
        d = i.get("direction", "unknown")
        by_dir.setdefault(d, []).append(i)
    stats["by_direction"] = {}
    for d, group in by_dir.items():
        hr = sum(1 for g in group if g["outcome"] == "hit") / len(group)
        stats["by_direction"][d] = {"count": len(group), "hit_rate": hr}

    # 按信心分组
    by_conv = {}
    for i in items:
        c = i.get("conviction", "unknown")
        by_conv.setdefault(c, []).append(i)
    stats["by_conviction"] = {}
    for c, group in by_conv.items():
        hr = sum(1 for g in group if g["outcome"] == "hit") / len(group)
        stats["by_conviction"][c] = {"count": len(group), "hit_rate": hr}

    return stats


def generate_monthly_report() -> str:
    """生成月度预测报告 Markdown。"""
    now = datetime.now()
    items = _collect_verified_this_month()
    stats = _compute_monthly_stats(items)

    if stats["total"] == 0:
        return f"# 月度预测报告 {now.strftime('%Y-%m')}\n\n本月暂无已验证预测。"

    lines = [
        f"# 月度预测报告 {now.strftime('%Y-%m')}",
        "",
        "## 核心指标",
        f"- 验证样本: {stats['total']}",
        f"- 命中率: {stats['hit_rate']:.1%} ({stats['hit_count']}/{stats['total']})",
        f"- 平均 Alpha: {stats['avg_alpha']:.2%}",
        f"- 中位 Alpha: {stats['median_alpha']:.2%}",
        f"- 平均收益: {stats['avg_return']:.2%}",
        f"- 最大回撤: {stats['max_drawdown']:.2%}",
        f"- 最佳 Alpha: {stats['best_alpha']:.2%}",
        f"- 最差 Alpha: {stats['worst_alpha']:.2%}",
        "",
        "## 行业分布",
    ]
    for ind, s in sorted(stats.get("by_industry", {}).items(), key=lambda x: -x[1]["count"]):
        lines.append(f"- {ind}: {s['count']} 单，命中率 {s['hit_rate']:.1%}，平均 Alpha {s['avg_alpha']:.2%}")

    lines.extend(["", "## 方向分布"])
    for d, s in stats.get("by_direction", {}).items():
        lines.append(f"- {d}: {s['count']} 单，命中率 {s['hit_rate']:.1%}")

    lines.extend(["", "## 信心分组"])
    for c, s in stats.get("by_conviction", {}).items():
        lines.append(f"- {c}: {s['count']} 单，命中率 {s['hit_rate']:.1%}")

    lines.extend(["", "## 逐笔明细"])
    for i in sorted(items, key=lambda x: -x["alpha"]):
        lines.append(
            f"- {i['asset']} [{i['outcome']}] "
            f"收益 {i['actual_return']:.1%} "
            f"Alpha {i['alpha']:.1%} "
            f"({i['source']})"
        )

    return "\n".join(lines)


def main():
    logger.info("=== 月度预测报告 生成 ===")
    report = generate_monthly_report()
    report_file = OUTPUT_DIR / f"prediction_monthly_{datetime.now().strftime('%Y-%m')}.md"
    report_file.write_text(report, encoding="utf-8")
    logger.info("月度报告: %s", report_file)
    print(report)


if __name__ == "__main__":
    main()
