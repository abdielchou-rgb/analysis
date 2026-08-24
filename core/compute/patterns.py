"""Phase B: Pattern Library — deterministic pattern detectors for financial data.

5 pure-Python pattern detectors (no numpy/pandas dependency):
  1. growth_inflection — 增速拐点检测
  2. margin_structure — 利润率驱动力分解
  3. peer_deviation — 同业偏离检测
  4. signal_convergence — 多信号叠加判断
  5. valuation_sensitivity — 隐含增长预期反推

Each detector has:
  - pure function interface: (data: dict) -> PatternResult
  - zero external dependencies
  - confidence score (0.0-1.0)
  - human-readable reasoning

Usage:
    from compute.patterns import detect_all
    results = detect_all(financial_data)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("v51.patterns")


@dataclass
class PatternResult:
    """单个模式检测结果。"""
    pattern_id: str = ""
    pattern_name: str = ""
    signal: str = "neutral"  # "bull" | "bear" | "neutral" | "inflection"
    confidence: float = 0.0  # 0.0-1.0
    reasoning: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)


# ═══════════════════════════════════════
# 1. 增速拐点检测
# ═══════════════════════════════════════

def detect_growth_inflection(revenue_series: list[dict],
                               years: Optional[list] = None) -> PatternResult:
    """Detect inflection points in revenue growth.

    Args:
        revenue_series: List of {"year": int, "revenue": float} or flat values
        years: Optional list of year labels

    Returns:
        PatternResult with signal: "accelerating" | "decelerating" | "stable" | "inflection"
    """
    result = PatternResult(pattern_id="growth_inflection", pattern_name="增速拐点检测")

    if not revenue_series or len(revenue_series) < 3:
        result.reasoning = ["数据不足（需要至少3期数据）"]
        result.confidence = 0.0
        return result

    # Extract values
    if isinstance(revenue_series[0], dict):
        vals = [r["revenue"] for r in revenue_series if "revenue" in r]
    else:
        vals = [float(v) for v in revenue_series if v is not None]

    if len(vals) < 3:
        result.reasoning = ["数据不足"]
        result.confidence = 0.0
        return result

    # Calculate YoY growth rates
    growth_rates = []
    for i in range(1, len(vals)):
        prev = vals[i - 1]
        if prev and prev != 0:
            growth_rates.append((vals[i] - prev) / abs(prev) * 100)
        else:
            growth_rates.append(0.0)

    if len(growth_rates) < 2:
        result.reasoning = ["增长趋势数据不足"]
        return result

    # Detect patterns
    recent_3 = growth_rates[-3:] if len(growth_rates) >= 3 else growth_rates

    # 1. Deceleration: each successive rate lower
    if all(recent_3[i] > recent_3[i + 1] for i in range(len(recent_3) - 1)):
        result.signal = "bear"
        result.confidence = 0.7
        result.reasoning = [
            f"连续{len(recent_3)}期增速下降（{'%→'.join(f'{r:.1f}' for r in recent_3)}%）",
            "增速进入下行通道",
        ]

    # 2. Acceleration: each successive rate higher
    elif all(recent_3[i] < recent_3[i + 1] for i in range(len(recent_3) - 1)):
        result.signal = "bull"
        result.confidence = 0.7
        result.reasoning = [
            f"连续{len(recent_3)}期增速上升（{'%→'.join(f'{r:.1f}' for r in recent_3)}%）",
            "增速进入上行通道",
        ]

    # 3. Sharp drop (>50% of previous rate)
    elif len(growth_rates) >= 2 and growth_rates[-1] < growth_rates[-2] * 0.5:
        result.signal = "inflection"
        result.confidence = 0.6
        result.reasoning = [
            f"增速从{growth_rates[-2]:.1f}%骤降至{growth_rates[-1]:.1f}%",
            "可能存在结构性问题",
        ]

    # 4. Stable
    else:
        spread = max(growth_rates) - min(growth_rates)
        if spread < 5:
            result.signal = "neutral"
            result.confidence = 0.6
            result.reasoning = [f"增速在{abs(growth_rates[-1]):.1f}%附近窄幅波动（区间{spread:.1f}pct）"]
        else:
            result.signal = "neutral"
            result.confidence = 0.4
            result.reasoning = [f"增速波动较大（{min(growth_rates):.1f}%-{max(growth_rates):.1f}%），趋势不明确"]

    result.data = {
        "growth_rates": [round(r, 2) for r in growth_rates],
        "latest_rate": round(growth_rates[-1], 2),
        "n_periods": len(vals),
    }
    return result


# ═══════════════════════════════════════
# 2. 利润率驱动力分解
# ═══════════════════════════════════════

def analyze_margin_structure(margin_series: list[dict]) -> PatternResult:
    """Decompose margin drivers: gross margin -> operating margin -> net margin.

    Args:
        margin_series: List of {"year": int, "gross_margin": float,
                                "operating_margin": float, "net_margin": float}

    Returns:
        PatternResult identifying dominant margin driver.
    """
    result = PatternResult(pattern_id="margin_structure", pattern_name="利润率驱动力分解")

    if len(margin_series) < 2:
        result.reasoning = ["数据不足"]
        return result

    # Calculate the gap between margin layers (cost structure)
    gaps = []
    for m in margin_series:
        gm = m.get("gross_margin", 0) or 0
        om = m.get("operating_margin", 0) or 0
        nm = m.get("net_margin", 0) or 0
        gaps.append({
            "year": m.get("year", 0),
            "sga_gap": gm - om,        # SG&A as % of revenue
            "tax_gap": om - nm,         # Tax + interest as % of revenue
            "gm": gm,
            "nm": nm,
        })

    # Trend analysis
    first, last = gaps[0], gaps[-1]
    gm_change = last["gm"] - first["gm"]
    sga_change = last["sga_gap"] - first["sga_gap"]
    nm_change = last["nm"] - first["nm"]

    # Determine dominant driver
    drivers = []
    if abs(gm_change) >= abs(sga_change):
        if abs(gm_change) > 1.0:
            drivers.append(("毛利率变化", gm_change, f"毛利{'改善' if gm_change > 0 else '承压'} {abs(gm_change):.1f}pct"))
    else:
        if abs(sga_change) > 1.0:
            drivers.append(("费用率变化", -sga_change, f"费用率{'下降' if sga_change < 0 else '上升'} {abs(sga_change):.1f}pct"))

    if not drivers:
        result.signal = "neutral"
        result.confidence = 0.3
        result.reasoning = ["利润率结构稳定，无明显驱动力变化"]
    else:
        driver = drivers[0]
        result.signal = "bull" if driver[1] > 0 else "bear"
        result.confidence = 0.6
        result.reasoning = [f"利润率主要驱动因素: {driver[2]}"]

    result.data = {
        "gm_change": round(gm_change, 2),
        "sga_change": round(sga_change, 2),
        "nm_change": round(nm_change, 2),
        "latest_gm": round(last["gm"], 2),
        "latest_nm": round(last["nm"], 2),
    }
    return result


# ═══════════════════════════════════════
# 3. 同业偏离检测
# ═══════════════════════════════════════

def detect_peer_deviation(company_metrics: dict,
                           peer_metrics: list[dict]) -> PatternResult:
    """Detect where the company significantly deviates from peers.

    Args:
        company_metrics: {"pe": float, "pb": float, "gross_margin": float, "roe": float, ...}
        peer_metrics: List of {"name": str, "pe": float, "pb": float, ...}

    Returns:
        PatternResult with signals for each deviation.
    """
    result = PatternResult(pattern_id="peer_deviation", pattern_name="同业偏离检测")

    if not company_metrics or not peer_metrics:
        result.reasoning = ["数据不足"]
        return result

    deviations = []
    metrics_to_check = ["pe", "pb", "gross_margin", "net_margin", "roe", "revenue_growth"]

    for metric in metrics_to_check:
        comp_val = company_metrics.get(metric)
        if comp_val is None:
            continue

        peer_vals = [p.get(metric) for p in peer_metrics if p.get(metric) is not None]
        if not peer_vals:
            continue

        avg = sum(peer_vals) / len(peer_vals)
        if avg == 0:
            continue

        deviation_pct = (comp_val - avg) / abs(avg) * 100

        if abs(deviation_pct) > 30:  # >30% deviation threshold
            direction = "above" if deviation_pct > 0 else "below"
            deviations.append({
                "metric": metric,
                "company_value": comp_val,
                "peer_mean": round(avg, 2),
                "deviation_pct": round(deviation_pct, 1),
                "direction": direction,
            })

    if not deviations:
        result.signal = "neutral"
        result.confidence = 0.4
        result.reasoning = ["各指标与同业均值偏差在30%以内"]
    else:
        most_sig = max(deviations, key=lambda d: abs(d["deviation_pct"]))
        result.signal = "bull" if most_sig["deviation_pct"] > 0 else "bear"
        result.confidence = 0.5
        result.reasoning = [
            f"偏离最显著: {most_sig['metric']}（{most_sig['company_value']} vs 同业{most_sig['peer_mean']}，偏离{most_sig['deviation_pct']:+.1f}%）",
            f"共有 {len(deviations)} 个指标偏离同业超过30%",
        ]

    result.data = {"deviations": deviations}
    return result


# ═══════════════════════════════════════
# 4. 多信号叠加
# ═══════════════════════════════════════

def stack_signals(signals: list[dict]) -> PatternResult:
    """Stack multiple signals and determine convergence/diversion.

    Args:
        signals: List of {"name": str, "signal": "bull"|"bear"|"neutral", "weight": float}

    Returns:
        PatternResult with aggregated signal.
    """
    result = PatternResult(pattern_id="signal_convergence", pattern_name="多信号叠加")

    if not signals:
        result.reasoning = ["无信号输入"]
        return result

    bull_weight = sum(s.get("weight", 1.0) for s in signals if s.get("signal") == "bull")
    bear_weight = sum(s.get("weight", 1.0) for s in signals if s.get("signal") == "bear")
    total_weight = bull_weight + bear_weight

    if total_weight == 0:
        result.signal = "neutral"
        result.confidence = 0.3
        result.reasoning = ["信号方向不明确或全部为中性"]
        return result

    # Convergence: strong majority
    net = (bull_weight - bear_weight) / total_weight

    if abs(net) > 0.6:
        result.signal = "bull" if net > 0 else "bear"
        result.confidence = min(0.8, 0.4 + abs(net) * 0.5)
        n_bull = sum(1 for s in signals if s.get("signal") == "bull")
        n_bear = sum(1 for s in signals if s.get("signal") == "bear")
        result.reasoning = [
            f"多信号{'一致看多' if net > 0 else '一致看空'}（看多{n_bull}个/看空{n_bear}个）",
            f"信号强度: {abs(net)*100:.0f}%",
        ]
    # Divergence: mixed
    else:
        result.signal = "neutral"
        result.confidence = 0.3
        n_bull = sum(1 for s in signals if s.get("signal") == "bull")
        n_bear = sum(1 for s in signals if s.get("signal") == "bear")
        result.reasoning = [
            f"信号分歧（看多{n_bull}个/看空{n_bear}个）",
            "方向不明确，需要更多信息",
        ]

    result.data = {
        "bull_weight": round(bull_weight, 2),
        "bear_weight": round(bear_weight, 2),
        "net_signal": round(net, 3),
        "n_signals": len(signals),
    }
    return result


# ═══════════════════════════════════════
# 5. 隐含增长预期反推
# ═══════════════════════════════════════

def estimate_implied_growth(pe: float, pb: float, roe: float,
                             wacc: float = 0.10, terminal_growth: float = 0.03) -> PatternResult:
    """Estimate what growth rate the market is pricing in.

    Uses simplified PEG-like logic and PB/ROE framework.

    Args:
        pe: Current P/E ratio
        pb: Current P/B ratio
        roe: Return on Equity (as decimal, e.g. 0.15)
        wacc: Cost of capital (default 10%)
        terminal_growth: Terminal growth rate (default 3%)

    Returns:
        PatternResult with implied growth estimate.
    """
    result = PatternResult(pattern_id="valuation_sensitivity", pattern_name="隐含增长反推")

    if not pe or pe <= 0:
        result.reasoning = ["PE数据无效"]
        return result

    # Method 1: PEG-like (PE / expected growth = 1 is "fair")
    peg_fair_growth = 1.0 / max(pe, 1) * 100  # rough: g = 100/PE
    peg_fair_growth = round(peg_fair_growth, 1)

    # Method 2: PB/ROE framework (implied g = ROE - (PB-1)/PE)
    if pb and pb > 0 and pe > 0 and roe and roe > 0:
        implied_g = roe - (pb - 1) / pe
        implied_g_pct = round(implied_g * 100, 1)
    else:
        implied_g_pct = peg_fair_growth
        implied_g_pct = round(implied_g_pct, 1)

    # Assessment
    if implied_g_pct > 20:
        result.signal = "bear"
        result.confidence = 0.5
        result.reasoning = [
            f"当前价格隐含 {implied_g_pct}% 的长期增长率",
            "这显著高于GDP增速+通胀，预期过于乐观",
        ]
    elif implied_g_pct < 2:
        result.signal = "bull"
        result.confidence = 0.5
        result.reasoning = [
            f"当前价格隐含 {implied_g_pct}% 的长期增长率",
            "接近于零增长假设，可能过度悲观",
        ]
    else:
        result.signal = "neutral"
        result.confidence = 0.4
        result.reasoning = [
            f"当前价格约隐含 {implied_g_pct}% 的长期增长率",
            "处于合理区间",
        ]

    result.data = {
        "implied_growth_pct": implied_g_pct,
        "peg_fair_growth_pct": peg_fair_growth,
        "input_pe": pe,
        "input_pb": pb,
        "input_roe": roe,
    }
    return result


# ═══════════════════════════════════════
# Aggregator
# ═══════════════════════════════════════

def detect_all(financial_data: dict) -> dict[str, PatternResult]:
    """Run all pattern detectors on a financial data dict.

    Args:
        financial_data: Dict with keys:
          - "revenue_series": list of {"year", "revenue"}
          - "margin_series": list of {"year", "gross_margin", ...}
          - "company_metrics": {"pe": ..., "pb": ..., ...}
          - "peer_metrics": [{"name": ..., "pe": ..., ...}]

    Returns:
        Dict mapping pattern_id -> PatternResult
    """
    results = {}

    # 1. Growth inflection
    rev = financial_data.get("revenue_series", [])
    if rev:
        results["growth_inflection"] = detect_growth_inflection(rev)

    # 2. Margin structure
    margin = financial_data.get("margin_series", [])
    if margin:
        results["margin_structure"] = analyze_margin_structure(margin)

    # 3. Peer deviation
    comp = financial_data.get("company_metrics", {})
    peers = financial_data.get("peer_metrics", [])
    if comp and peers:
        results["peer_deviation"] = detect_peer_deviation(comp, peers)

    # 4. Valuation sensitivity
    pe = comp.get("pe") if comp else None
    pb = comp.get("pb") if comp else None
    roe = comp.get("roe") if comp else None
    if pe:
        results["valuation_sensitivity"] = estimate_implied_growth(
            pe=pe, pb=pb or 0, roe=roe or 0
        )

    # 5. Signal stacking (from all above)
    signals = []
    for pid, pr in results.items():
        if pr.signal != "neutral":
            weight = pr.confidence
            signals.append({"name": pid, "signal": pr.signal, "weight": weight})
    if signals:
        results["signal_convergence"] = stack_signals(signals)

    return results


def format_pattern_brief(results: dict[str, PatternResult]) -> str:
    """Format pattern detection results for inclusion in Watchdog/evidence chain."""
    if not results:
        return "模式检测：无可用数据"

    lines = ["### 模式检测摘要\n"]
    for pid, pr in results.items():
        signal_icon = {"bull": "📈", "bear": "📉", "inflection": "🔄", "neutral": "➡️"}.get(pr.signal, "➡️")
        lines.append(f"{signal_icon} **{pr.pattern_name}**：{pr.signal}（置信度{pr.confidence:.0%}）")
        for r in pr.reasoning[:2]:
            lines.append(f"  - {r}")
        lines.append("")
    return "\n".join(lines)
    def detect_mean_reversion(self, data):
        result = {}
        pe_pct = data.get('pe_percentile')
        if pe_pct is not None:
            p = float(pe_pct)
            if p < 0.15:
                result['pe_mean_reversion'] = {'signal':'bullish','confidence':min(1.0,(0.15-p)*5),
                    'detail':'PE at {:.0%} percentile, below avg, mean reversion likely upward'.format(p)}
            elif p > 0.85:
                result['pe_mean_reversion'] = {'signal':'bearish','confidence':min(1.0,(p-0.85)*5),
                    'detail':'PE at {:.0%} percentile, above avg, mean reversion likely downward'.format(p)}
        gm = data.get('gross_margin')
        ga = data.get('gross_margin_5y_avg')
        if gm and ga:
            d = float(gm) - float(ga)
            if abs(d) > 10:
                result['margin_mean_reversion'] = {'signal':'reversion_risk','confidence':min(1.0,abs(d)/20),
                    'detail':'Gross margin {:.1f}% deviates {:+} from 5y avg'.format(gm,d)}
        result['_status'] = 'ok' if result else 'no_data'
        return result


# ══════════════════════════════════════════════════════════════════
# 6. 反向 DCF / 市场隐含预期（Reverse DCF / Expectations Investing）
# R23（2026-08-02）王牌方法：从当前市值反推市场隐含假设，找预期差
# ══════════════════════════════════════════════════════════════════

def estimate_implied_growth_full(
    market_cap: float = 0.0,          # 总市值（亿元）
    current_fcf: float = 0.0,         # 当前自由现金流（亿元）
    fcf_growth_rates: Optional[list] = None,  # 我方预测的逐年 FCF 增速（0-1）
    wacc: float = 0.10,               # 折现率
    terminal_growth: float = 0.03,    # 终值增长率
    projection_years: int = 5,        # 预测期年数
    shares: float = 1.0,              # 总股本（亿股），用于算每股
    current_price: float = 0.0,       # 当前股价
) -> dict:
    """完整版反向 DCF：反推市场隐含的 FCF 增速，与我方预测对比找预期差。

    方法（New Constructs / Bernstein 打法）：
      1. 正向：用我方 fcf_growth_rates 预测 → 得到"我们的目标市值"
      2. 反向：给定当前市值，倒解"市场隐含的恒定 FCF 增速 g_implied"
         EV = Σ FCF_t / (1+wacc)^t + FCF_n*(1+g)/(wacc-g)/(1+wacc)^n
         用二分法在 [0, 40%] 区间解 g
      3. 预期差：g_implied vs 我方预测的稳态增速 → 谁更乐观
      4. 敏感性表：不同 wacc × terminal_growth 下的隐含 g

    返回 dict，含 implied_g / expectation_gap / sensitivity / 判断。
    """
    def _solve_implied_g(mcap: float, fcf0: float, w: float, g_term: float,
                         years: int) -> float:
        """二分法解恒定增速 g，使得 DCF 值 = mcap。"""
        if mcap <= 0 or fcf0 <= 0:
            return 0.0

        def _pv(g):
            total = 0.0
            fcf = fcf0
            for t in range(1, years + 1):
                fcf = fcf * (1 + g)
                total += fcf / (1 + w) ** t
            # 终值（从第 n 年起永续）
            tv = fcf * (1 + g_term) / max(w - g_term, 0.05)
            total += tv / (1 + w) ** years
            return total

        lo, hi = 0.0, 0.40
        for _ in range(50):
            mid = (lo + hi) / 2
            if _pv(mid) < mcap:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    result = PatternResult(pattern_id="reverse_dcf", pattern_name="反向DCF/市场隐含预期")

    if market_cap <= 0 or current_fcf <= 0:
        result.reasoning = ["缺少市值或 FCF 数据，无法反向 DCF"]
        return result

    # 1. 反推市场隐含增速
    g_implied = _solve_implied_g(market_cap, current_fcf, wacc, terminal_growth,
                                 projection_years)

    # 2. 我方预测的稳态增速（取预测期平均，或最后一年）
    if fcf_growth_rates and len(fcf_growth_rates) > 0:
        our_g = sum(float(g) for g in fcf_growth_rates) / len(fcf_growth_rates)
    else:
        our_g = 0.10  # 默认假设
    our_g = min(max(our_g, -0.1), 0.5)

    # 3. 预期差 = 市场隐含 - 我方预测
    gap = g_implied - our_g  # 正 = 市场比我方乐观；负 = 市场比我方悲观

    if gap > 0.05:
        signal = "bear"
        conf = min(0.9, 0.4 + abs(gap) * 2)
        judgement = f"市场隐含 {g_implied*100:.1f}% 增速，高于我们预测的 {our_g*100:.1f}%"
        action = "若我们判断正确，当前估值偏贵，等待回调或证伪"
    elif gap < -0.05:
        signal = "bull"
        conf = min(0.9, 0.4 + abs(gap) * 2)
        judgement = f"市场隐含 {g_implied*100:.1f}% 增速，低于我们预测的 {our_g*100:.1f}%"
        action = "若我们判断正确，当前估值便宜，存在预期差机会"
    else:
        signal = "neutral"
        conf = 0.4
        judgement = f"市场隐含 {g_implied*100:.1f}% 增速，与我们预测的 {our_g*100:.1f}% 接近"
        action = "估值合理，预期差不大，需其他维度支撑"

    result.signal = signal
    result.confidence = round(conf, 2)
    result.reasoning = [judgement, action, f"(反向DCF: 市值{market_cap:.0f}亿 / 当前FCF{current_fcf:.1f}亿 / WACC{wacc:.0%})"]

    # 4. 敏感性表：wacc × terminal_growth → 隐含 g
    sensitivity = {}
    for w in [round(wacc - 0.01, 3), wacc, round(wacc + 0.01, 3)]:
        for gt in [round(terminal_growth - 0.005, 3),
                   round(terminal_growth + 0.005, 3),
                   round(terminal_growth, 3)]:
            key = f"wacc={w:.1%}|g={gt:.1%}"
            sensitivity[key] = round(_solve_implied_g(market_cap, current_fcf, w, gt,
                                                      projection_years) * 100, 1)
    sensitivity = dict(sorted(sensitivity.items()))

    result.data = {
        "implied_growth_pct": round(g_implied * 100, 1),
        "our_growth_pct": round(our_g * 100, 1),
        "expectation_gap_pct": round(gap * 100, 1),
        "market_cap": market_cap, "current_fcf": current_fcf,
        "wacc": wacc, "terminal_growth": terminal_growth,
        "per_share_implied_price": round(current_fcf * (1 + g_implied) / max(shares, 1e-9) * 15, 1),
        "sensitivity": sensitivity,
    }
    return result


# ══════════════════════════════════════════════════════════════════
# R30 模块8：隐含 FCF margin 反推（对标 New Constructs）
# 给定市值 + 营收，反推需要多高的 FCF margin 才支撑当前估值
# ══════════════════════════════════════════════════════════════════
def estimate_implied_fcf_margin(
    market_cap: float = 0.0,        # 总市值（亿元）
    revenue: float = 0.0,           # 当前营收（亿元）
    fcf_growth: float = 0.10,       # 假设的 FCF 增速
    wacc: float = 0.10,             # 折现率
    terminal_growth: float = 0.03,  # 终值增速
    projection_years: int = 5,      # 预测期
) -> dict:
    """反推市场隐含的稳态 FCF margin。

    方法：给定市值，倒解需要多大的 FCF（作为营收比例）才使 DCF 价值=市值。
      EV = Σ (rev*fcf_margin*(1+g)^t)/(1+wacc)^t + 终值
    二分法解 fcf_margin ∈ [0, 0.4]。

    返回 {implied_fcf_margin, implied_fcf, revenue, signal}
    """
    def _solve_margin(mcap, rev, g, w, g_term, years):
        if mcap <= 0 or rev <= 0:
            return 0.0

        def _pv(margin):
            total = 0.0
            fcf = rev * margin
            for t in range(1, years + 1):
                fcf = fcf * (1 + g)
                total += fcf / (1 + w) ** t
            tv = fcf * (1 + g_term) / max(w - g_term, 0.05)
            total += tv / (1 + w) ** years
            return total

        lo, hi = 0.0, 0.40
        for _ in range(50):
            mid = (lo + hi) / 2
            if _pv(mid) < mcap:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    result = PatternResult(pattern_id="reverse_fcf_margin",
                           pattern_name="隐含FCF利润率反推")
    if market_cap <= 0 or revenue <= 0:
        result.reasoning = ["缺少市值或营收数据"]
        return result

    margin = _solve_margin(market_cap, revenue, fcf_growth, wacc,
                           terminal_growth, projection_years)
    implied_fcf = revenue * margin

    # 判断
    if margin > 0.20:
        signal = "bear"
        conf = min(0.9, 0.4 + (margin - 0.15) * 2)
        judgement = f"市场隐含 {margin:.0%} 的稳态 FCF 利润率（营收{revenue:.1f}亿→FCF{implied_fcf:.1f}亿）"
        action = "该利润率高于多数制造业公司（通常5-15%），预期偏乐观"
    elif margin < 0.05:
        signal = "bull"
        conf = min(0.8, 0.4 + (0.05 - margin) * 2)
        judgement = f"市场隐含仅 {margin:.0%} 的 FCF 利润率"
        action = "该利润率低于制造业平均，若公司实际盈利质量更好则存在低估"
    else:
        signal = "neutral"
        conf = 0.4
        judgement = f"市场隐含 {margin:.0%} 的 FCF 利润率，处于合理区间"
        action = "估值与盈利质量匹配"

    result.signal = signal
    result.confidence = round(conf, 2)
    result.reasoning = [judgement, action]
    result.data = {
        "implied_fcf_margin": round(margin, 4),
        "implied_fcf": round(implied_fcf, 1),
        "revenue": revenue,
        "market_cap": market_cap,
        "fcf_growth_assumed": fcf_growth,
    }
    return result


def build_fcf_margin_prompt(rd) -> str:
    """序列化隐含 FCF margin 反推结果。"""
    if not rd:
        return ""
    if isinstance(rd, PatternResult):
        data = rd.data or {}
        signal = rd.signal
        reasoning = rd.reasoning or []
    else:
        data = rd.get("data", {}) or {}
        signal = rd.get("signal", "")
        reasoning = rd.get("reasoning", []) or []
    if not data:
        return ""
    lines = ["=== 隐含FCF利润率反推（New Constructs 法） ===",
             f"市场隐含稳态FCF利润率: **{data.get('implied_fcf_margin', 0):.1%}**"
             f"（营收{data.get('revenue', 0):.1f}亿→FCF{data.get('implied_fcf', 0):.1f}亿）",
             f"信号: {signal}"]
    for r in reasoning[:2]:
        lines.append(f"- {r}")
    return "\n".join(lines)


def build_reverse_dcf_prompt(rd) -> str:
    """序列化为 prompt 注入文本（估值章节引用）。

    rd 为 PatternResult 或 dict。
    """
    if not rd:
        return ""
    if isinstance(rd, PatternResult):
        data = rd.data or {}
        signal = rd.signal
        conf = rd.confidence
        reasoning = rd.reasoning or []
    else:
        data = rd.get("data", {}) or {}
        signal = rd.get("signal", "")
        conf = rd.get("confidence", 0)
        reasoning = rd.get("reasoning", []) or []
    if not data:
        return ""
    sens = data.get("sensitivity", {})
    lines = ["=== 反向DCF/市场隐含预期（预期差核心） ===",
             f"市场隐含增速: **{data.get('implied_growth_pct')}%** vs 我方预测: {data.get('our_growth_pct')}%",
             f"预期差: {data.get('expectation_gap_pct'):+}%（正=市场比我方乐观，负=市场比我方悲观）",
             f"信号: {signal} / 置信度: {conf}"]
    for r in reasoning[:3]:
        lines.append(f"- {r}")
    if sens:
        lines.append("敏感性（WACC×终值增速 → 隐含增速）:")
        items = list(sens.items())[:6]
        lines.append("  " + "  ".join(f"{k}={v}%" for k, v in items))
    return "\n".join(lines)


