"""
非上市反向定价 + 里程碑时间轴（Unlisted Reverse Valuation & Milestone Timeline）— R23

**核心**：非上市标的没有股价，无法做反向 DCF。但它的等价物是**反向定价**——
倒推"要达到什么营收/利润/里程碑，才支撑当前估值"。这是 VC 尽调的核心打法：
先有估值，反推需要兑现的业绩，再看是否可行。

**与上市反向DCF的区别**：
  - 上市：市值 → 反推隐含 FCF 增速
  - 非上市：投后估值 → 反推隐含营收/利润目标 → 对照里程碑可行性

**数据源**：
  - prospectus_findings.json（招股书：营收/利润/轮次）
  - 参考类预测（reference_class_forecast）
  - 生命周期（渗透率）

输出：隐含营收目标 / 隐含利润目标 / 里程碑时间轴 / 可行性判断。
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger("2hao.unlisted_reverse")

_ROOT = Path(__file__).resolve().parent.parent


def _sf(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def load_ps_findings(asset: str) -> dict | None:
    """读取 prospectus_findings.json 该标的数据。"""
    try:
        path = _ROOT / "data" / "prospectus_findings.json"
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(d, dict) and asset:
            for k, v in d.items():
                if asset in str(k) or str(k) in asset:
                    return v if isinstance(v, dict) else None
        return None
    except Exception as _e:
        logger.debug("[UNLISTED-REV] load: %s", _e)
        return None


def _extract_revenue(ps: dict) -> float:
    """提取最近营收（万元→亿元）。"""
    try:
        revs = ps.get("revenues_by_year", {}) or {}
        if isinstance(revs, dict) and revs:
            latest = list(revs.values())[-1]
            if isinstance(latest, dict):
                val = _sf(latest.get("value", 0))
                unit = str(latest.get("unit", ""))
                return val / 10000 if "万" in unit else val  # 统一为亿元
        # 直接 revenue 字段
        rv = ps.get("revenue")
        if rv:
            return _sf(rv) / 10000 if _sf(rv) > 100 else _sf(rv)
    except Exception:
        pass
    return 0.0


def _extract_profit(ps: dict) -> float:
    """提取最近利润（万元→亿元）。"""
    try:
        profs = ps.get("profits", []) or []
        if isinstance(profs, list) and profs:
            last = profs[-1]
            if isinstance(last, dict):
                val = _sf(last.get("value", 0))
                unit = str(last.get("unit", ""))
                return val / 10000 if "万" in unit else val
        return 0.0
    except Exception:
        return 0.0


def build_unlisted_reverse_valuation(data: dict) -> dict:
    """非上市反向定价 + 里程碑时间轴。"""
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    if not isinstance(cd, dict):
        cd = {}
    asset = data.get("asset", "") if isinstance(data, dict) else ""
    asset_name = asset.split()[0] if asset else ""

    ps = load_ps_findings(asset_name) or {}
    rev = _extract_revenue(ps)
    profit = _extract_profit(ps)

    # 估值：优先 chart_data 给的估值，否则用参考类推断
    valuation = _sf(cd.get("valuation", cd.get("post_money", cd.get("mcap", 0))))
    valuation_source = "数据输入"
    if not valuation:
        try:
            from core.reference_class_prediction import get_baserate

            br = get_baserate(stage="成长期", industry=asset_name)
            if br and getattr(br, "median_exit_value", 0):
                valuation = _sf(br.median_exit_value)
                valuation_source = "参考类预测"
        except Exception:
            pass

    # 估值 fallback：营收×PS 推断（非上市标准法）
    # 成长期未上市 PS 通常 5-10x；有招股书（IPO推进中）可给 8-12x
    if not valuation and rev > 0:
        ps_multiple = 8.0 if ps.get("file") else 6.0
        valuation = rev * ps_multiple
        valuation_source = f"营收×PS{ps_multiple:.0f}x 推断（当前营收{rev:.1f}亿）"

    # ── 反向定价：估值 → 隐含营收/利润目标 ──
    # 常用非上市估值倍数：PS 5-10x（成长期）、PE 20-40x
    implied_rev_low = valuation / 10 if valuation else 0  # 高PS(10x) → 低营收目标
    implied_rev_high = valuation / 5 if valuation else 0  # 低PS(5x) → 高营收目标
    implied_profit = valuation / 30 if valuation else 0  # 中性PE(30x)

    # 可行性：当前营收 vs 隐含营收目标
    rev_gap_ok = None
    if rev > 0 and implied_rev_high > 0:
        gap_ratio = implied_rev_high / rev
        if gap_ratio <= 2:
            rev_gap_ok = True
        elif gap_ratio <= 5:
            rev_gap_ok = "需高增长"  # 需 2-5 倍增长
        else:
            rev_gap_ok = False  # 需 >5 倍，极难

    # ── 里程碑时间轴（非上市专属）──
    now = date.today()
    y = now.year
    milestones = []
    if ps.get("file"):
        milestones.append({"time": f"{y + 1}H1", "type": "退出", "desc": "IPO 申报/注册推进", "source": "A/招股书"})
    milestones.append({"time": f"{y}H2", "type": "融资", "desc": "下一轮融资窗口（估值抬升验证）", "source": "E/假设"})
    if rev > 0:
        milestones.append(
            {
                "time": f"{y + 1}H1",
                "type": "业绩",
                "desc": f"营收目标 {implied_rev_high:.1f}亿（当前 {rev:.1f}亿）验证",
                "source": "E/反向定价",
            }
        )
    milestones.append({"time": f"{y + 1}H2", "type": "里程碑", "desc": "关键客户/产品里程碑", "source": "E/假设"})

    # 判断
    if rev_gap_ok is True:
        feasibility = "当前营收已接近隐含目标，估值有支撑"
    elif rev_gap_ok == "需高增长":
        feasibility = f"需高增长（营收 {rev:.1f}亿 → {implied_rev_high:.1f}亿，{implied_rev_high / rev:.1f}x），依赖融资+里程碑兑现"
    elif rev_gap_ok is False:
        feasibility = f"营收差距过大（当前 {rev:.1f}亿 vs 隐含 {implied_rev_high:.1f}亿），估值偏高或营收高估"
    else:
        feasibility = "缺营收数据，无法判断可行性"

    return {
        "status": "ok",
        "valuation": round(valuation, 1) if valuation else 0,
        "valuation_source": valuation_source,
        "current_revenue": round(rev, 2) if rev else 0,
        "current_profit": round(profit, 2) if profit else 0,
        "implied_revenue_target": {"low_ps": round(implied_rev_low, 1), "high_ps": round(implied_rev_high, 1)},
        "implied_profit_target": round(implied_profit, 1) if implied_profit else 0,
        "revenue_gap_ratio": round(implied_rev_high / rev, 1) if rev and implied_rev_high else None,
        "feasibility": feasibility,
        "milestones": milestones,
        "note": "反向定价=估值/PS倍数→隐含营收目标。PS 5-10x(成长期)/PE 30x 为行业常用假设。",
    }


def serialize_unlisted_reverse(ur: dict, max_chars: int = 900) -> str:
    """序列化为 prompt 注入文本。"""
    if not ur or ur.get("status") != "ok":
        return ""
    lines = [
        "=== 非上市反向定价 + 里程碑时间轴 ===",
        f"估值: **{ur.get('valuation')}**（{ur.get('valuation_source')}）",
        f"当前营收: {ur.get('current_revenue')}亿 / 利润: {ur.get('current_profit')}亿",
        f"隐含营收目标(PS 5-10x): {ur.get('implied_revenue_target', {}).get('low_ps')} ~ {ur.get('implied_revenue_target', {}).get('high_ps')}亿",
        f"隐含利润目标(PE 30x): {ur.get('implied_profit_target')}亿",
    ]
    if ur.get("revenue_gap_ratio"):
        lines.append(f"营收差距: 需增长 {ur.get('revenue_gap_ratio')}x")
    lines.append(f"可行性: {ur.get('feasibility')}")
    lines.append("\n里程碑时间轴:")
    for m in ur.get("milestones", [])[:4]:
        lines.append(f"- [{m.get('source')}] {m.get('time')} {m.get('desc', '')[:40]}")
    return "\n".join(lines)[:max_chars]


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    for asset in ["尚水智能", "思必驰", "未知标的"]:
        ur = build_unlisted_reverse_valuation({"asset": asset, "chart_data": {}})
        print(f"\n=== {asset} ===")
        print(serialize_unlisted_reverse(ur))
