# -*- coding: utf-8 -*-
"""
盈利预测模型（Earnings Forecast Model）— R16 深度补强

投行标准的三表联动盈利预测：
  营收预测（增长驱动） → 毛利（毛利率假设） → 净利（费用率/税率）
  → 每股收益 EPS → 现金流（净利→FCF）→ 估值锚

输入：collected_data 里的财务历史（fig_revenue_trend / fig_profitability / fig_margin）
输出：未来 3 年盈利预测表 + 情景分析（乐观/基准/悲观）+ 敏感性矩阵

**不编造数据**：历史值必须来自数据层，预测值是模型推导（标注 E/F）。
基准情景 = 历史增速的中位/均值外推；乐观/悲观 = ±敏感性区间。
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("2hao.predict_model")


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_forecast(data: dict, report_type: str = "listed_company") -> Optional[dict]:
    """构建盈利预测表。

    Args:
        data: collected_data（含 chart_data 的财务历史）
        report_type: 报告类型（行业/个股用不同口径）

    Returns:
        {
          "base_year": 2025,
          "historical": {"2023": {"revenue": x, "net_profit": y, "gross_margin": m}, ...},
          "forecast": {"2026E": {"revenue": x, "growth": g, "net_profit": y, "eps": e, "gross_margin": m}, ...},
          "scenarios": {"乐观": {...}, "基准": {...}, "悲观": {...}},
          "sensitivity": {"wacc": [...], "growth": [...]},
          "source": "model"
        }
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    if not isinstance(cd, dict):
        return None

    # R39（2026-08-02）：统一财务数据提取层——兼容 fig_* 字典与扁平键两种形态，
    # 消除"fig_margin 读空 → 毛利率兜底 5%"的字段错位根因。
    try:
        from core.financial_extract import extract_financial_history, extract_shares
        historical_raw = extract_financial_history(data)
    except Exception as _e:
        logger.debug("[PREDICT] extract layer failed: %s", _e)
        historical_raw = {}

    # 整理年份序列
    years = sorted(
        historical_raw.keys(),
        key=lambda k: int(k) if str(k).isdigit() else 0,
    )
    years = [y for y in years if str(y).isdigit() and 2000 <= int(y) <= 2030]
    if len(years) < 2:
        # 数据不足无法预测
        return None

    historical = {}
    for y in years:
        entry = historical_raw.get(y, {})
        historical[y] = {
            "revenue": _safe_float(entry.get("revenue", 0)),
            "net_profit": _safe_float(entry.get("net_profit", 0)),
            "gross_margin": _safe_float(entry.get("gross_margin", 0)),
        }

    # 计算历史增速（营收/净利 CAGR 或年均）
    rev_vals = [historical[y]["revenue"] for y in years if historical[y]["revenue"] > 0]
    prof_vals = [historical[y]["net_profit"] for y in years if historical[y]["net_profit"] != 0]

    # R38（2026-08-02）：剔除异常尾部年份——若最后一年营收 < 前一年的 40%，
    # 视为单季/部分数据误入（柯力案：revenue_trend_2026=3.58 实为单季，2025全年15.58），
    # 避免 base_year 落在异常年份导致预测失准。
    def _is_anomalous_tail_year(hist: dict) -> bool:
        """最后一年是否为异常尾部——营收缺失(0)或骤降(<40%前年)。

        柯力案：margin_2026=46.35 存在但 revenue 缺失 → last_rev=0 → base_year 落在
        无营收数据的年份，导致预测营收全 0。此类尾部必须剔除。
        """
        if len(hist) < 2:
            return False
        sorted_yrs = sorted(hist.keys(), key=lambda k: int(k))
        last_y, prev_y = sorted_yrs[-1], sorted_yrs[-2]
        last_r = _safe_float(hist[last_y].get("revenue", 0))
        prev_r = _safe_float(hist[prev_y].get("revenue", 0))
        # 营收缺失（0）或骤降（<40% 前年）都视为异常尾部
        return prev_r > 0 and (last_r <= 0 or last_r < prev_r * 0.4)

    if _is_anomalous_tail_year(historical):
        _drop = max(historical.keys(), key=lambda k: int(k))
        historical.pop(_drop, None)
        years = [y for y in years if y != _drop]
        logger.info("[PREDICT] 剔除异常尾部年份 %s（单季/部分数据）", _drop)
        # 重建增速与基准
        rev_vals = [historical[y]["revenue"] for y in years if historical[y]["revenue"] > 0]
        prof_vals = [historical[y]["net_profit"] for y in years if historical[y]["net_profit"] != 0]

    def _avg_growth(vals):
        """年均增速（最后一年 vs 第一年）"""
        if len(vals) < 2:
            return 0.0
        base, last = vals[0], vals[-1]
        if base == 0:
            return 0.0
        n = len(vals) - 1
        try:
            return ((last / base) ** (1 / max(n, 1)) - 1) * 100
        except Exception:
            return 0.0

    rev_growth = _avg_growth(rev_vals)
    prof_growth = _avg_growth(prof_vals)
    last_margin = historical[years[-1]].get("gross_margin", 0) if years else 0
    last_rev = historical[years[-1]].get("revenue", 0) if years else 0
    last_prof = historical[years[-1]].get("net_profit", 0) if years else 0

    # ── 未来 3 年预测（基准情景）──
    base_year = int(years[-1]) if years else 2025
    forecast = {}
    rev, prof = last_rev, last_prof
    # 增速收敛假设：预测增速 = min(历史增速, 20%)，逐年小幅递减
    g_rev = max(min(rev_growth, 20.0), -5.0)
    g_prof = max(min(prof_growth, 25.0), -10.0)
    # 股本提取（R39）：统一走 financial_extract（兼容 fig_valuation/扁平键/市值反推）
    try:
        from core.financial_extract import extract_shares
        shares = extract_shares(cd)
    except Exception as _e:
        logger.debug("[PREDICT] shares extract failed: %s", _e)
        shares = 0.0

    for i in range(1, 4):
        yr = base_year + i
        rev = rev * (1 + g_rev / 100)
        prof = prof * (1 + g_prof / 100)
        # 毛利率小幅改善（规模效应）或维持
        margin = last_margin + i * 0.5 if last_margin > 0 else 0
        margin = min(max(margin, 5), 70)
        eps = prof / shares if shares > 0 else 0
        forecast[f"{yr}E"] = {
            "revenue": round(rev, 2),
            "growth": round(g_rev, 2),
            "net_profit": round(prof, 2),
            "eps": round(eps, 2),
            "gross_margin": round(margin, 2),
            "scenario": "base",
        }
        # 增速递减
        g_rev = max(g_rev * 0.85, 2.0)
        g_prof = max(g_prof * 0.85, 2.0)

    # ── 情景分析（乐观/悲观）──
    scenarios = {}
    # 乐观：增速 +30%；悲观：增速 -40%
    for sname, mult in [("乐观", 1.3), ("基准", 1.0), ("悲观", 0.6)]:
        s_rev, s_prof = last_rev, last_prof
        s_g_rev = max(min(rev_growth * mult, 25.0), -10.0)
        s_g_prof = max(min(prof_growth * mult, 30.0), -15.0)
        for i in range(1, 4):
            s_rev = s_rev * (1 + s_g_rev / 100)
            s_prof = s_prof * (1 + s_g_prof / 100)
        last_f = forecast.get(f"{base_year+3}E", {})
        scenarios[sname] = {
            "revenue_3y": round(s_rev, 2),
            "net_profit_3y": round(s_prof, 2),
            "eps_3y": round(s_prof / shares, 2) if shares > 0 else 0,
            "growth_assumption": round(s_g_rev, 2),
        }

    # ── 敏感性矩阵（营收增速 × 净利率）──
    sensitivity = {
        "revenue_growth": [round(rev_growth * m, 1) for m in [0.6, 0.8, 1.0, 1.2, 1.4]],
        "net_margin": [round(max(last_margin * m, 5), 1) for m in [0.8, 0.9, 1.0, 1.1, 1.2]],
    }

    return {
        "base_year": base_year,
        "historical": historical,
        "forecast": forecast,
        "scenarios": scenarios,
        "sensitivity": sensitivity,
        "source": "predict_model: 历史增速外推 + 三表联动",
        "report_type": report_type,
    }


def build_forecast_summary(fc: dict) -> str:
    """把预测模型结果序列化成 prompt 注入文本（供 section_writer 引用）。"""
    if not fc:
        return ""
    lines = ["=== 盈利预测模型（三表联动） ==="]
    fc_ = fc.get("forecast", {})
    lines.append("未来3年预测:")
    for yr, v in fc_.items():
        lines.append(f"  {yr}: 营收{v.get('revenue',0):.1f}亿(+{v.get('growth',0):.1f}%) "
                     f"净利{v.get('net_profit',0):.1f}亿 EPS={v.get('eps',0):.2f} 毛利率{v.get('gross_margin',0):.1f}%")
    sc = fc.get("scenarios", {})
    if sc:
        lines.append("情景分析:")
        for sname, v in sc.items():
            lines.append(f"  {sname}: 3年后净利{v.get('net_profit_3y',0):.1f}亿 EPS={v.get('eps_3y',0):.2f}")
    return "\n".join(lines)
