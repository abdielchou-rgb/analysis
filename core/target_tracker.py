"""
目标价追踪台账（Target Tracker）— R30 模块2：对标投行分析师考核

**问题**：2hao 报告给目标价（如柯力 48 元），但从没人回头验证"到了吗？差多少？"
对标投行：分析师每发目标价，内部系统追踪达成率，计入考核。

**方案**：从 forward_picks.csv 提取目标价 → 到期自动对照实际价 → 误差+达成率档案。

达成率分级：误差<5%=命中 / <15%=接近 / >15%=miss
聚合：按标的/行业/报告类型 → 分析师能力档案 → 回流 prompt（"我过去命中率X%"）
"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger("2hao.target_tracker")

_ROOT = Path(__file__).resolve().parent.parent
TRACKER_DIR = _ROOT / "data" / "forward_picks"


def _load_picks() -> list[dict]:
    """加载 forward_picks.csv。"""
    path = TRACKER_DIR / "forward_picks.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _get_latest_price(code: str) -> float | None:
    """获取标的最近价格（本地 qlib，离线）。"""
    try:
        from core.data_backends import _query_local_qlib_price

        q = _query_local_qlib_price(code)
        if q and q.get("prices"):
            return float(q["prices"][-1])
    except Exception:
        pass
    return None


def grade_target_error(target: float, actual: float) -> str:
    """误差分级。"""
    if target <= 0 or actual <= 0:
        return "unknown"
    err = abs(actual - target) / target * 100
    if err < 5:
        return "hit"
    if err < 15:
        return "close"
    return "miss"


def compute_tracker(horizon_days: int = 365) -> dict:
    """计算目标价追踪台账。

    返回 {total, verified, hit/close/miss 计数, by_industry, by_report_type,
          accuracy_by_industry}
    """
    picks = _load_picks()
    if not picks:
        return {
            "total": 0,
            "verified": 0,
            "hit": 0,
            "close": 0,
            "miss": 0,
            "by_industry": {},
            "by_report_type": {},
            "accuracy": 0,
        }

    today = date.today()
    results = []
    for p in picks:
        # 到期判定：created_at + horizon_days
        created = p.get("created_at", "")[:10]
        base_target = float(p.get("base_target") or 0)
        code = p.get("asset_code", "")
        if not created or base_target <= 0:
            continue
        try:
            made = datetime.strptime(created, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - made).days < horizon_days:
            continue  # 未到期
        # 若已验证（actual_price 有值）直接用，否则拉最新价
        actual_price = float(p["actual_price"]) if p.get("actual_price") else _get_latest_price(code)
        if not actual_price:
            continue
        grade = grade_target_error(base_target, actual_price)
        results.append(
            {
                "asset": p.get("asset_name", p.get("asset_code", "")),
                "code": code,
                "target": base_target,
                "actual": actual_price,
                "grade": grade,
                "direction": p.get("direction", ""),
                "industry": p.get("industry", p.get("report_type", "unknown")),
                "report_type": p.get("report_type", "unknown"),
            }
        )

    verified = len(results)
    hit = sum(1 for r in results if r["grade"] == "hit")
    close = sum(1 for r in results if r["grade"] == "close")
    miss = sum(1 for r in results if r["grade"] == "miss")

    # 按行业聚合
    by_industry = {}
    for r in results:
        ind = r["industry"]
        by_industry.setdefault(ind, {"total": 0, "hit": 0, "close": 0, "miss": 0})
        by_industry[ind]["total"] += 1
        by_industry[ind][r["grade"]] += 1

    # 按报告类型聚合
    by_report_type = {}
    for r in results:
        rt = r["report_type"]
        by_report_type.setdefault(rt, {"total": 0, "hit": 0, "close": 0, "miss": 0})
        by_report_type[rt]["total"] += 1
        by_report_type[rt][r["grade"]] += 1

    return {
        "total": len(picks),
        "verified": verified,
        "hit": hit,
        "close": close,
        "miss": miss,
        "accuracy": hit / verified if verified else 0,
        "details": results,
        "by_industry": by_industry,
        "by_report_type": by_report_type,
    }


def format_tracker(t: dict) -> str:
    """格式化为可读台账。"""
    lines = [
        "=== 目标价追踪台账 ===",
        f"总预测: {t['total']} | 已到期验证: {t['verified']}",
        f"命中(误差<5%): {t['hit']} | 接近(<15%): {t['close']} | 未中(>15%): {t['miss']}",
        f"目标价达成率: {t['accuracy']:.0%}" if t["verified"] else "达成率: N/A",
    ]
    if t.get("by_report_type"):
        lines.append("\n按报告类型:")
        for rt, s in t["by_report_type"].items():
            lines.append(f"  {rt}: {s['hit']}/{s['total']} 命中")
    if t.get("by_industry"):
        lines.append("\n按行业:")
        for ind, s in list(t["by_industry"].items())[:8]:
            lines.append(f"  {ind}: {s['hit']}/{s['total']} 命中")
    return "\n".join(lines)


def build_analyst_profile(t: dict) -> str:
    """生成分析师能力档案（回流 prompt）。

    格式：'我过去对 {report_type} 类报告目标价达成率 X%'
    """
    if not t["verified"]:
        return "过去目标价样本不足，暂无法评估达成率"
    lines = [f"分析师目标价历史达成率: {t['accuracy']:.0%}（基于 {t['verified']} 次到期验证）"]
    for rt, s in t["by_report_type"].items():
        if s["total"] >= 3:
            lines.append(f"- {rt} 类: {s['hit']}/{s['total']} 命中")
    return "\n".join(lines)


if __name__ == "__main__":
    t = compute_tracker()
    print(format_tracker(t))
