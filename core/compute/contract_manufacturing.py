"""contract_manufacturing.py — 代工/合作生产测算（2026-08-07）

柯力油位场景直接需要：算清"接不接久通的油位传感器代工"的投入产出。

四块测算（同行启发：投入产出比要算到盈亏平衡 + 战略期权）：
  1. 代工成本拆分：设备/产线/认证/良率爬坡
  2. 盈亏平衡：固定成本 / 单位毛利 → 平衡量
  3. 转移定价合规：关联交易毛利区间（独立交易原则 ALP）
  4. 战略期权价值：进入油位市场的真实期权（非简单 NPV）

用法：
  from core.compute.contract_manufacturing import calculate_contract_manufacturing, format_summary
  result = calculate_contract_manufacturing({
      "capacity_units": 50000,        # 年产目标（只）
      "unit_price": 2000,             # 单价（元/只）
      "variable_cost": 1400,          # 单位变动成本（元/只）
      "fixed_capex": 30000000,        # 初始固定资产投入（元）
      "fixed_opex_year": 5000000,     # 年固定运营成本（元）
      "ramp_years": 2,                # 良率爬坡年限
      "target_margin": 0.15,          # 目标毛利率
      "option_volatility": 0.35,      # 战略期权波动率
      "option_horizon_years": 3,      # 期权行权年限
      "discount_rate": 0.10,          # 折现率
  })
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.contract_manufacturing")


@dataclass
class CMResult:
    """代工测算结果。"""

    # 成本与盈亏平衡
    unit_contribution: float = 0.0  # 单位贡献（售价-变动成本）
    contribution_margin: float = 0.0  # 贡献毛利率
    breakeven_units: float = 0.0  # 盈亏平衡量（只/年）
    breakeven_capacity_util: float = 0.0  # 盈亏平衡产能利用率
    payback_years: float = 0.0  # 静态回收期（年）
    # 投入产出
    total_investment: float = 0.0  # 总投入（capex+首年opex）
    year5_revenue: float = 0.0  # 第5年收入（满产）
    year5_gross_profit: float = 0.0  # 第5年毛利
    year5_net_contribution: float = 0.0  # 第5年净贡献（毛利-固定opex）
    npv: float = 0.0  # 5年 NPV（折现）
    irr: float = 0.0  # IRR
    # 转移定价（ALP 独立交易原则）
    transfer_price_range: tuple = (0.0, 0.0)  # 关联交易合理价格区间
    # 战略期权
    option_value: float = 0.0  # 战略期权价值（BS 近似）
    strategic_total: float = 0.0  # NPV + 期权
    # 结论
    verdict: str = ""  # 建议
    reasons: list = field(default_factory=list)
    assumptions: dict = field(default_factory=dict)


def calculate_contract_manufacturing(params: dict) -> CMResult:
    """代工测算主入口。"""
    r = CMResult()
    # 输入解析
    capacity = float(params.get("capacity_units", 0))
    price = float(params.get("unit_price", 0))
    vcost = float(params.get("variable_cost", 0))
    capex = float(params.get("fixed_capex", 0))
    opex_year = float(params.get("fixed_opex_year", 0))
    ramp = int(params.get("ramp_years", 2))
    target_margin = float(params.get("target_margin", 0.15))
    vol = float(params.get("option_volatility", 0.35))
    horizon = float(params.get("option_horizon_years", 3))
    disc = float(params.get("discount_rate", 0.10))
    r.assumptions = dict(params)

    if capacity <= 0 or price <= 0:
        r.verdict = "参数不足，无法测算"
        return r

    # 1. 成本与贡献
    r.unit_contribution = price - vcost
    r.contribution_margin = r.unit_contribution / price if price else 0

    # 2. 盈亏平衡
    total_fixed = capex / max(ramp, 1) + opex_year  # 年化固定成本
    if r.unit_contribution > 0:
        r.breakeven_units = total_fixed / r.unit_contribution
        r.breakeven_capacity_util = r.breakeven_units / capacity if capacity else 0
    else:
        r.breakeven_units = float("inf")
        r.breakeven_capacity_util = float("inf")

    # 3. 投入产出（5 年，含爬坡）
    r.total_investment = capex + opex_year
    # 爬坡曲线：ramp 年内线性爬升到满产
    yearly = []
    for yr in range(1, 6):
        util = min(1.0, yr / max(ramp, 1)) if yr <= ramp else 1.0
        units = capacity * util
        rev = units * price
        gross = units * r.unit_contribution
        net = gross - opex_year
        yearly.append({"year": yr, "units": units, "revenue": rev, "gross_profit": gross, "net_contribution": net})
    r.year5_revenue = yearly[-1]["revenue"]
    r.year5_gross_profit = yearly[-1]["gross_profit"]
    r.year5_net_contribution = yearly[-1]["net_contribution"]

    # NPV（首年为 capex 投入，后续为净贡献折现）
    cf = [-capex]
    for y in yearly:
        cf.append(y["net_contribution"])
    r.npv = sum(cf[t] / (1 + disc) ** t for t in range(len(cf)))
    r.irr = _calc_irr(cf)

    # 静态回收期（含首年）
    cum = -capex
    r.payback_years = 0
    for y in yearly:
        cum += y["net_contribution"]
        if cum >= 0:
            r.payback_years = y["year"] + (1 - (cum / max(y["net_contribution"], 1e-9)))
            break
    if r.payback_years == 0:
        r.payback_years = float("inf")

    # 4. 转移定价（ALP：合理毛利区间 10%-25%，用目标毛利校准）
    low = price * (1 - 0.10)
    high = price * (1 - 0.25)
    r.transfer_price_range = (round(low, 2), round(high, 2))

    # 5. 战略期权（Black-Scholes 近似，进入新市场的真实期权）
    # 用第5年净贡献作为行权收益基准，波动率驱动期权价值
    s = r.year5_net_contribution  # 标的资产现值近似
    x = opex_year  # 行权价（维持经营的固定成本）
    if s > 0 and x > 0:
        t = horizon
        d1 = (math.log(s / x) + (disc + 0.5 * vol**2) * t) / (vol * math.sqrt(t))
        d2 = d1 - vol * math.sqrt(t)
        nd1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2)))
        nd2 = 0.5 * (1 + math.erf(d2 / math.sqrt(2)))
        r.option_value = s * nd1 - x * math.exp(-disc * t) * nd2
    r.strategic_total = r.npv + r.option_value

    # 6. 结论
    reasons = []
    if r.breakeven_capacity_util <= 0.7:
        reasons.append(f"盈亏平衡产能利用率 {r.breakeven_capacity_util:.0%} 低于70%，可行性高")
    else:
        reasons.append(f"盈亏平衡需 {r.breakeven_capacity_util:.0%} 产能，爬坡有压力")
    if r.payback_years <= 3:
        reasons.append(f"静态回收期 {r.payback_years:.1f} 年，回收快")
    else:
        reasons.append(f"回收期 {r.payback_years:.1f} 年偏长")
    if r.npv > 0:
        reasons.append(f"NPV {r.npv / 1e4:.0f}万为正，5年创造价值")
    else:
        reasons.append(f"NPV {r.npv / 1e4:.0f}万为负，5年净投入")
    if r.option_value > abs(r.npv):
        reasons.append(f"战略期权价值 {r.option_value / 1e4:.0f}万 > 5年NPV，期权属性强（进入新市场）")
    r.reasons = reasons

    if r.npv > 0 and r.payback_years <= 4:
        r.verdict = "建议进入（条件性：订单承诺≥盈亏平衡量）"
    elif r.npv > 0 and r.option_value > 0:
        r.verdict = "建议以期权视角进入（容忍短期NPV为负，赌战略卡位）"
    else:
        r.verdict = "谨慎：测算不支持当前参数下进入，需重谈条件"
    return r


def format_summary(r: CMResult) -> str:
    """格式化测算摘要（供写作注入）。"""
    lines = [
        "=== 代工/合作生产测算 ===",
        f"盈亏平衡量: {r.breakeven_units:,.0f}只/年（产能利用率 {r.breakeven_capacity_util:.0%}）",
        f"单位贡献: {r.unit_contribution:,.0f}元/只（贡献毛利率 {r.contribution_margin:.0%}）",
        f"总投入: {r.total_investment / 1e4:,.0f}万元",
        f"第5年收入: {r.year5_revenue / 1e4:,.0f}万元，净贡献 {r.year5_net_contribution / 1e4:,.0f}万元",
        f"NPV(5年,10%折现): {r.npv / 1e4:,.0f}万元，IRR: {r.irr:.1%}",
        f"静态回收期: {r.payback_years:.1f}年",
        f"转移定价合理区间: {r.transfer_price_range[0]:,.0f}~{r.transfer_price_range[1]:,.0f}元/只",
        f"战略期权价值: {r.option_value / 1e4:,.0f}万元（总价值 NPV+期权 = {r.strategic_total / 1e4:,.0f}万元）",
        f"结论: {r.verdict}",
    ]
    if r.reasons:
        lines.append("依据:")
        for x in r.reasons:
            lines.append(f"  - {x}")
    lines.append("=== 测算结束 ===")
    return "\n".join(lines)


def _calc_irr(cf: list, guess: float = 0.1, max_iter: int = 100) -> float:
    """IRR 计算（优先 numpy-financial，回退牛顿迭代）。"""
    try:
        import numpy_financial as npf

        return float(npf.irr(cf))
    except Exception:
        pass

    def npv_at(rate):
        return sum(cf[t] / (1 + rate) ** t for t in range(len(cf)))

    r0 = guess
    for _ in range(max_iter):
        f = npv_at(r0)
        f_prime = sum(-t * cf[t] / (1 + r0) ** (t + 1) for t in range(len(cf)))
        if abs(f_prime) < 1e-9:
            break
        r1 = r0 - f / f_prime
        if abs(r1 - r0) < 1e-6:
            return r1
        r0 = r1
    return npv_at(r0)
