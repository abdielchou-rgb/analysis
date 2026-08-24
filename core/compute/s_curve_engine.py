# -*- coding: utf-8 -*-
"""s_curve_engine.py — 渗透率 S 曲线 + 实物期权（2026-08-08 框架优化 P1）

顶级打法：
  - S 曲线：BCG/麦肯锡用渗透率 S 曲线定位阶段（导入/起飞/饱和），比"成熟/成长"定性精确
  - 实物期权：大摩区分扩张/放弃/延迟/转换期权（多阶段投资）

用法：
  from core.compute.s_curve_engine import s_curve_stage, build_s_curve_prompt
  from core.compute.s_curve_engine import real_option_value, RealOption
"""
from __future__ import annotations
import math
import logging

logger = logging.getLogger("2hao.s_curve")


# ── S 曲线阶段定位 ─────────────────────────────────────

def s_curve_stage(penetration: float, growth: float) -> dict:
    """按渗透率 + 增速定位 S 曲线阶段。

    Args:
        penetration: 当前渗透率（0-1）
        growth: 年增速（0-1）

    阶段：导入(<10%) / 起飞(10-50% 高增速) / 扩张(50-80%) / 饱和(>80%)
    """
    p = penetration
    g = growth
    if p < 0.10:
        stage = "导入期"
        strategy = "技术验证 + 早期客户培育，增速依赖渗透率突破"
    elif p < 0.50 and g > 0.20:
        stage = "起飞期"
        strategy = "跑马圈地 + 产能扩张 + 渠道卡位（增速最高，资源倾斜）"
    elif p < 0.80:
        stage = "扩张期"
        strategy = "份额争夺 + 规模成本 + 竞争洗牌"
    else:
        stage = "饱和期"
        strategy = "降本 + 存量替换 + 寻找第二曲线"
    return {
        "penetration": round(p, 3),
        "growth": round(g, 3),
        "stage": stage,
        "strategy": strategy,
    }


def build_s_curve_prompt(data: dict) -> str:
    """生成注入行业分析的 S 曲线说明。"""
    stage = s_curve_stage(data.get("penetration", 0), data.get("growth", 0))
    return (f"渗透率 S 曲线定位：渗透率 {stage['penetration']:.0%}，增速 {stage['growth']:.0%}"
            f" → {stage['stage']}（策略：{stage['strategy']}）")


# ── 实物期权 ───────────────────────────────────────────

def real_option_value(option_type: str, s: float, x: float, t: float,
                      sigma: float, r: float = 0.05) -> dict:
    """实物期权价值（Black-Scholes 近似）。

    Args:
        option_type: expansion(扩张)/abandon(放弃)/delay(延迟)/convert(转换)
        s: 标的资产现值
        x: 行权价/投入
        t: 期权年限
        sigma: 波动率
        r: 无风险利率

    简化：扩张/延迟期权 = 看涨 BS；放弃期权 = 看跌 BS；转换期权 = 价差。
    """
    if s <= 0 or x <= 0:
        return {"option_type": option_type, "value": 0.0, "note": "参数不足"}

    def _bs_call():
        d1 = (math.log(s / x) + (r + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
        nd1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2)))
        nd2 = 0.5 * (1 + math.erf(d2 / math.sqrt(2)))
        return s * nd1 - x * math.exp(-r * t) * nd2

    def _bs_put():
        d1 = (math.log(s / x) + (r + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
        nd1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2)))
        nd2 = 0.5 * (1 + math.erf(d2 / math.sqrt(2)))
        return x * math.exp(-r * t) * (1 - nd2) - s * (1 - nd1)

    value = 0.0
    note = ""
    if option_type == "expansion":
        value = _bs_call()
        note = "扩张期权（看涨）：现在小投入，未来按条件放大"
    elif option_type == "delay":
        value = _bs_call()
        note = "延迟期权（看涨）：等待更有利条件再进入"
    elif option_type == "abandon":
        value = _bs_put()
        note = "放弃期权（看跌）：投入后可按残值退出（下行保护）"
    elif option_type == "convert":
        # 转换期权 ≈ 看涨 - 看跌（价差）
        value = _bs_call() - _bs_put()
        note = "转换期权（价差）：在不同用途/市场间切换"
    else:
        value = _bs_call()
        note = "默认按扩张期权"

    return {
        "option_type": option_type,
        "value": round(value, 2),
        "s": s, "x": x, "t": t, "sigma": sigma,
        "note": note,
    }


def build_real_options_prompt(options: list) -> str:
    """生成注入估值的实物期权说明。"""
    lines = ["=== 实物期权评估 ==="]
    for o in options:
        lines.append(f"- {o['note']}: 价值 {o['value']:,.0f}（S={o['s']:,.0f}, X={o['x']:,.0f}, "
                     f"t={o['t']}y, σ={o['sigma']}）")
    lines.append("=== 期权结束 ===")
    return "\n".join(lines)
