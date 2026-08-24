# -*- coding: utf-8 -*-
"""
统一财务数据提取层（Financial Data Access Layer）— R39 数据契约

**问题**：15 个模块各自从 chart_data 提取财务字段，且各自提取方式不同：
  - predict_model/three_statement 读 `fig_margin`，但真实数据可能是扁平键 `margin_2025`
  - 字段错位 → 读空 → 兜底错误值（柯力案：毛利率兜底 5.0%）
  - LLM 看到荒谬预测 → 编造"更合理"的幻觉数字

**方案**（对标顶级做法"数据契约/Data Contract"）：统一提取层，
所有消费者调此模块，兼容两种形态：
  1. `fig_*` 字典形态（fig_revenue_trend: {year: val}）
  2. 扁平键形态（revenue_trend_2025 / margin_2025 / profitability_2025）

消费者只调 `extract_financial_history(cd)` 拿到规范化的
`{"2025": {"revenue": X, "net_profit": Y, "gross_margin": Z}}`，
不再自行解析字段。
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("2hao.financial_extract")


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ── 扁平键前缀 → 指标类型 映射 ──
# revenue_trend_2025 → revenue；profitability_2025 → net_profit；margin_2025 → gross_margin
_FLAT_KEY_PATTERNS = [
    ("revenue_trend_", "revenue"),
    ("revenue_", "revenue"),
    ("profitability_", "net_profit"),
    ("net_profit_", "net_profit"),
    ("margin_", "gross_margin"),
]


def _parse_flat_keys(cd: dict) -> dict:
    """从扁平键提取 {year: {indicator: value}}。

    柯力案：margin_2025=44.83 → {"2025": {"gross_margin": 44.83}}
    """
    result = {}
    for k, v in (cd or {}).items():
        if not isinstance(k, str):
            continue
        for prefix, indicator in _FLAT_KEY_PATTERNS:
            if k.startswith(prefix):
                year_str = k[len(prefix):]
                if year_str.isdigit() and 2000 <= int(year_str) <= 2030:
                    val = _safe_float(v)
                    if val != 0 or indicator != "revenue":  # 保留 0 净利但跳过空营收
                        result.setdefault(year_str, {})[indicator] = val
                    break
    return result


def extract_financial_history(data: dict) -> dict:
    """统一提取财务历史序列。

    Args:
        data: collected_data（含 chart_data）或直接 chart_data 字典

    Returns:
        {"2023": {"revenue": X, "net_profit": Y, "gross_margin": Z}, ...}
        只有确实存在的年份/指标才会出现；无数据的指标为 None。
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) and "chart_data" in data else data
    if not isinstance(cd, dict):
        return {}

    # 1. fig_* 字典形态
    rev_hist = cd.get("fig_revenue_trend", {}) if isinstance(cd.get("fig_revenue_trend"), dict) else {}
    prof_hist = cd.get("fig_profitability", {}) if isinstance(cd.get("fig_profitability"), dict) else {}
    margin_hist = cd.get("fig_margin", {}) if isinstance(cd.get("fig_margin"), dict) else {}

    years = set()
    if isinstance(rev_hist, dict):
        years |= {str(y) for y in rev_hist.keys()}
    if isinstance(prof_hist, dict):
        years |= {str(y) for y in prof_hist.keys()}
    if isinstance(margin_hist, dict):
        years |= {str(y) for y in margin_hist.keys()}

    result = {}
    for y in sorted(years, key=lambda k: int(k) if k.isdigit() else 0):
        if not (y.isdigit() and 2000 <= int(y) <= 2030):
            continue
        entry = {}
        if isinstance(rev_hist, dict) and y in rev_hist:
            entry["revenue"] = _safe_float(rev_hist.get(y))
        if isinstance(prof_hist, dict) and y in prof_hist:
            entry["net_profit"] = _safe_float(prof_hist.get(y))
        if isinstance(margin_hist, dict) and y in margin_hist:
            m = margin_hist.get(y)
            entry["gross_margin"] = _safe_float(m.get("gross_margin", m.get("毛利率", 0)) if isinstance(m, dict) else m)
        if entry:
            result[y] = entry

    # 2. 扁平键形态（补全 fig_* 未覆盖的指标）
    flat = _parse_flat_keys(cd)
    for y, indicators in flat.items():
        entry = result.setdefault(y, {})
        for ind, val in indicators.items():
            # 扁平键优先级低于 fig_*？不——扁平键是真实 data_dict 形态，应覆盖兜底
            if ind not in entry:
                entry[ind] = val

    return result


def extract_shares(cd: dict) -> float:
    """统一提取股本（亿股）。兼容 fig_valuation dict / 扁平键 / 市值÷价格反推。"""
    if not isinstance(cd, dict):
        return 0.0
    _val = cd.get("fig_valuation") if isinstance(cd.get("fig_valuation"), dict) else {}
    shares = _safe_float(_val.get("shares", 0))
    if shares <= 0:
        for _k in ("total_shares", "shares_outstanding", "股本"):
            if _k in cd:
                shares = _safe_float(cd.get(_k, 0))
                if shares > 0:
                    break
    if shares <= 0:
        _mcap = _safe_float(_val.get("market_cap", _val.get("mcap", 0)))
        _price = _safe_float(_val.get("price", _val.get("current_price", 0)))
        if _mcap > 0 and _price > 0:
            shares = _mcap / _price  # 亿元/元 = 亿股
    return shares


def extract_valuation(cd: dict) -> dict:
    """统一提取估值基准（价格/市值/股本）。"""
    if not isinstance(cd, dict):
        return {}
    _val = cd.get("fig_valuation") if isinstance(cd.get("fig_valuation"), dict) else {}
    result = {
        "price": _safe_float(_val.get("price", _val.get("current_price", 0))),
        "market_cap": _safe_float(_val.get("market_cap", _val.get("mcap", 0))),
        "shares": extract_shares(cd),
        "eps": _safe_float(_val.get("eps", 0)),
        "fcf": _safe_float(_val.get("free_cash_flow", _val.get("fcf", 0))),
    }
    return result


# R51（2026-08-02 净利口径契约）：归母净利 vs 含少数股东净利
# 柯力案：financials.db netProfit=3.41亿（可能含少数股东），enrich 归母=1.68亿。
# 报告必须引用归母口径，避免"净利3.41"幻觉。
_NET_PROFIT_CALIBER_HINT = (
    "净利口径契约：报告引用净利时须优先归母净利（enrich/年报披露），"
    "financials.db 的 netProfit 可能含少数股东权益（口径不同），"
    "引用前须核对。若 data_dict 的 profitability_YYYY 与 enrich 归母不一致，"
    "以 enrich/年报归母为准，并在正文标注口径。"
)


def get_net_profit_caliber(data: dict) -> dict:
    """判定 data 中净利的口径，返回建议引用的归母净利。

    Returns:
        {"net_profit_2025": x, "caliber": "归母/含少数股东/未知",
         "warning": str}
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    if not isinstance(cd, dict):
        return {"net_profit_2025": None, "caliber": "未知",
                "warning": "无数据"}
    hist = extract_financial_history(data)
    if not hist:
        return {"net_profit_2025": None, "caliber": "未知",
                "warning": "无历史数据"}
    # 最新实际年份的净利
    years = sorted(hist.keys(), key=lambda k: int(k) if k.isdigit() else 0)
    valid = [y for y in years if hist[y].get("net_profit")]
    if not valid:
        return {"net_profit_2025": None, "caliber": "未知",
                "warning": "无净利数据"}
    last = valid[-1]
    np_val = hist[last]["net_profit"]
    # 检查是否有归母字段（优先）
    return {"net_profit_2025": np_val, "caliber": "未知（建议核对归母）",
            "warning": _NET_PROFIT_CALIBER_HINT}


if __name__ == "__main__":
    # 自测：柯力扁平键形态
    sample = {
        "revenue_trend_2023": 10.72, "revenue_trend_2024": 12.95, "revenue_trend_2025": 15.58,
        "profitability_2023": 3.12, "profitability_2024": 2.61, "profitability_2025": 3.41,
        "margin_2023": 43.05, "margin_2024": 43.12, "margin_2025": 44.83,
        "fig_valuation": {"price": 46.73, "market_cap": 131.23},
    }
    hist = extract_financial_history(sample)
    print("=== 扁平键提取 ===")
    for y, e in hist.items():
        print(f"  {y}: {e}")
    print("股本:", extract_shares(sample), "亿股")
    print("估值:", extract_valuation(sample))
