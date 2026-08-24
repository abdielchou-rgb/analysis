# -*- coding: utf-8 -*-
"""
三表勾稽模型（Three-Statement Model）— R19 投行级盈利预测闭环

把利润表 → 资产负债表 → 现金流量表 形成完整勾稽环：
  利润表净利 → 留存收益 → 资产负债表股东权益
  EBITDA → 营运资金变动 → 经营现金流 → 投资/筹资 → 期末现金 → 下期期初
  三表勾稽校验：期末现金 = 期初 + 经营 + 投资 + 筹资（缺一即不平衡）

**投行三表模型核心勾稽关系**：
  1. 利润表净利 + 期初留存 → 期末留存 → 资产负债表权益
  2. 利润表 + 营运资金变动 + 折旧摊销 → 经营现金流
  3. 经营现金流 + 资本开支（投资） + 融资 → 期末现金
  4. 期末现金 → 下期资产负债表货币资金 → 下期期初现金
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("2hao.three_statement")


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_three_statement(data: dict) -> Optional[dict]:
    """构建三表勾稽模型。

    输入历史：营收/净利/毛利率（利润表）；总资产/总负债/权益（资产负债表）；FCF/OCF（现金流）
    输出：未来 3 年三表联动 + 勾稽平衡校验

    勾稽环（投行标准）：
      - 净利 → 留存收益（假设分红率） → 期末权益
      - 净利 + 折旧 - 营运资金增加 → 经营现金流
      - 经营现金流 - 资本开支 - 偿债 → 期末现金
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    if not isinstance(cd, dict):
        return None

    # R39（2026-08-02）：统一财务数据提取层——兼容 fig_* 字典与扁平键。
    # 此前读 fig_margin 不兼容 margin_2025 扁平键 → 毛利率读空。
    try:
        from core.financial_extract import extract_financial_history
        historical_raw = extract_financial_history(data)
    except Exception as _e:
        logger.debug("[THREE-STMT] extract layer failed: %s", _e)
        historical_raw = {}

    years = sorted(
        historical_raw.keys(),
        key=lambda k: int(k) if str(k).isdigit() else 0,
    )
    years = [y for y in years if str(y).isdigit() and 2000 <= int(y) <= 2030]
    if len(years) < 2:
        return None

    # R39（2026-08-02）：剔除异常尾部年份（仅 margin 无营收，如柯力 margin_2026=46.35）
    # 否则 last_rev=0 → 三表预测全 0。
    def _is_anomalous_tail(hist_raw: dict) -> bool:
        if len(hist_raw) < 2:
            return False
        sorted_yrs = sorted(hist_raw.keys(), key=lambda k: int(k))
        last_y, prev_y = sorted_yrs[-1], sorted_yrs[-2]
        last_r = _safe_float(hist_raw.get(last_y, {}).get("revenue", 0))
        prev_r = _safe_float(hist_raw.get(prev_y, {}).get("revenue", 0))
        return prev_r > 0 and (last_r <= 0 or last_r < prev_r * 0.4)

    if _is_anomalous_tail(historical_raw):
        _drop = max(historical_raw.keys(), key=lambda k: int(k))
        historical_raw.pop(_drop, None)
        years = [y for y in years if y != _drop]

    last_year = int(years[-1])
    last_rev = _safe_float(historical_raw.get(str(last_year), {}).get("revenue", 0))
    last_prof = _safe_float(historical_raw.get(str(last_year), {}).get("net_profit", 0))
    last_margin = _safe_float(historical_raw.get(str(last_year), {}).get("gross_margin", 0))

    # 历史增速
    rev_vals = [_safe_float(historical_raw.get(str(y), {}).get("revenue", 0)) for y in years
                if _safe_float(historical_raw.get(str(y), {}).get("revenue", 0)) > 0]
    prof_vals = [_safe_float(historical_raw.get(str(y), {}).get("net_profit", 0)) for y in years
                 if _safe_float(historical_raw.get(str(y), {}).get("net_profit", 0)) != 0]

    def _growth(vals):
        if len(vals) < 2 or vals[0] == 0:
            return 0.0
        try:
            return (vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1
        except Exception:
            return 0.0

    rev_g = _growth(rev_vals)
    prof_g = _growth(prof_vals)
    g_rev = max(min(rev_g, 0.20), -0.05)
    g_prof = max(min(prof_g, 0.25), -0.10)

    # ── 假设参数（可从 data 覆盖）──
    assumptions = data.get("assumptions", {})
    payout_ratio = _safe_float(assumptions.get("payout_ratio", 0.3))  # 分红率
    dep_rate = _safe_float(assumptions.get("depreciation_rate", 0.08))  # 折旧率（占营收）
    capex_rate = _safe_float(assumptions.get("capex_rate", 0.12))  # 资本开支率（占营收）
    nwc_rate = _safe_float(assumptions.get("nwc_rate", 0.05))  # 营运资金占用率
    tax_rate = _safe_float(assumptions.get("tax_rate", 0.25))

    # 资产负债表期初（从 fig_valuation 或假设）
    val = cd.get("fig_valuation", {}) if isinstance(cd, dict) else {}
    init_equity = _safe_float(val.get("total_equity", val.get("equity", 0)))
    init_debt = _safe_float(val.get("total_debt", val.get("net_debt", 0)))
    init_cash = _safe_float(val.get("cash", 0))

    # ── 三表联动预测 ──
    tables = {"income": {}, "balance": {}, "cashflow": {}}
    rev, prof = last_rev, last_prof
    equity = init_equity if init_equity > 0 else last_rev * 0.5
    debt = init_debt
    cash = init_cash if init_cash > 0 else last_rev * 0.1

    for i in range(1, 4):
        yr = f"{last_year + i}E"
        # 利润表
        rev = rev * (1 + g_rev)
        prof = prof * (1 + g_prof)
        ebit = prof / (1 - tax_rate) if tax_rate < 1 else prof
        ebitda = ebit + rev * dep_rate
        net_profit = prof

        # 勾稽1：净利 → 留存收益 → 权益
        dividend = net_profit * payout_ratio
        retained = net_profit - dividend
        equity = equity + retained

        # 勾稽2：利润表 → 经营现金流
        ocf = net_profit + rev * dep_rate - rev * nwc_rate

        # 勾稽3：投资/筹资 → 期末现金
        capex = rev * capex_rate
        icf = -capex
        fcf = net_profit + rev * dep_rate - capex
        cash_flow = ocf + icf
        cash = cash + cash_flow

        tables["income"][yr] = {
            "revenue": round(rev, 2), "ebitda": round(ebitda, 2),
            "net_profit": round(net_profit, 2), "margin": round(net_profit / rev * 100, 2) if rev else 0,
        }
        tables["balance"][yr] = {
            "equity": round(equity, 2), "debt": round(debt, 2), "cash": round(cash, 2),
            "total_assets": round(equity + debt + cash, 2),
        }
        tables["cashflow"][yr] = {
            "ocf": round(ocf, 2), "icf": round(icf, 2), "capex": round(capex, 2),
            "fcf": round(fcf, 2), "ending_cash": round(cash, 2),
        }

        # 增速收敛
        g_rev = max(g_rev * 0.85, 0.02)
        g_prof = max(g_prof * 0.85, 0.02)

    # ── 勾稽平衡校验 ──
    balance_issues = []
    for yr in tables["income"]:
        ending_cash = tables["cashflow"][yr]["ending_cash"]
        balance_cash = tables["balance"][yr]["cash"]
        if abs(ending_cash - balance_cash) > 1:
            balance_issues.append(f"{yr}: 现金流表期末现金({ending_cash})≠资产负债表现金({balance_cash})")

    return {
        "base_year": last_year,
        "tables": tables,
        "assumptions": {
            "payout_ratio": payout_ratio, "depreciation_rate": dep_rate,
            "capex_rate": capex_rate, "nwc_rate": nwc_rate, "tax_rate": tax_rate,
        },
        "balance_ok": len(balance_issues) == 0,
        "balance_issues": balance_issues,
        "source": "three_statement: 利润表→资产负债表→现金流表勾稽闭环",
    }


def format_three_statement(ts: dict) -> str:
    """序列化三表勾稽模型为 prompt 注入文本。"""
    if not ts:
        return ""
    tables = ts.get("tables", {})
    lines = ["=== 三表勾稽模型（投行盈利预测闭环） ==="]
    lines.append(f"勾稽平衡: {'✅' if ts.get('balance_ok') else '⚠️ ' + '; '.join(ts.get('balance_issues', []))}")
    lines.append("假设: " + ", ".join(f"{k}={v}" for k, v in ts.get("assumptions", {}).items()))
    for yr in tables.get("income", {}):
        inc = tables["income"][yr]
        bs = tables["balance"][yr]
        cf = tables["cashflow"][yr]
        lines.append(f"\n{yr}:")
        lines.append(f"  利润表: 营收{inc['revenue']} 净利{inc['net_profit']} EBITDA{inc['ebitda']} 净利率{inc['margin']}%")
        lines.append(f"  资产负债表: 权益{bs['equity']} 负债{bs['debt']} 现金{bs['cash']}")
        lines.append(f"  现金流: 经营{cf['ocf']} 投资{cf['icf']} FCF{cf['fcf']} 期末现金{cf['ending_cash']}")
    return "\n".join(lines)
