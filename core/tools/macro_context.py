# -*- coding: utf-8 -*-
# Macro Context Injector (DDM三要素框架)
from __future__ import annotations
import logging
from dataclasses import dataclass

logger = logging.getLogger("2hao.macro_context")

@dataclass
class MacroContext:
    earnings_cycle: str = ""
    liquidity_cycle: str = ""
    risk_preference: str = ""
    inventory_position: str = ""
    credit_cycle: str = ""
    policy_orientation: str = ""

CYCLES = {
    "earnings": {"trough": "盈利底部期 - 最差时候已过", "expansion": "盈利扩张期 - 营收增长",
                 "peak": "盈利顶部期 - 增速放缓", "contraction": "盈利收缩期 - 营收下降"},
    "liquidity": {"loose": "流动性宽松期 - 利率下行", "tightening": "流动性收紧期 - 利率企稳",
                  "tight": "流动性紧缩期 - 利率高位", "easing": "流动性放松期 - 利率回落"},
    "risk": {"risk_on": "风险偏好高 - 成长占优", "neutral": "风险偏好中性 - 均衡配置",
             "risk_off": "风险偏好低 - 防御占优"},
    "inventory": {"active_replenish": "主动补库 - 需求旺盛", "passive_replenish": "被动补库 - 需求回落",
                  "active_destock": "主动去库 - 需求走弱", "passive_destock": "被动去库 - 需求企稳"},
    "credit": {"expansion": "信用扩张 - 社融回升", "stable": "信用平稳 - 社融持平",
               "contraction": "信用收缩 - 社融回落"},
    "policy": {"stimulus": "政策刺激 - 财政扩张", "neutral": "政策中性 - 结构调整",
               "tightening": "政策收紧 - 去杠杆"},
}

NL = chr(10)

def get_current_context():
    return MacroContext(earnings_cycle="trough", liquidity_cycle="loose",
                        risk_preference="risk_on", inventory_position="passive_destock",
                        credit_cycle="expansion", policy_orientation="stimulus")

def macro_context_prompt(ctx):
    p = ["[宏观背景板]"]
    p.append("盈利周期: " + CYCLES["earnings"].get(ctx.earnings_cycle, "?"))
    p.append("流动性周期: " + CYCLES["liquidity"].get(ctx.liquidity_cycle, "?"))
    p.append("风险偏好: " + CYCLES["risk"].get(ctx.risk_preference, "?"))
    p.append("库存周期: " + CYCLES["inventory"].get(ctx.inventory_position, "?"))
    p.append("信用周期: " + CYCLES["credit"].get(ctx.credit_cycle, "?"))
    p.append("政策取向: " + CYCLES["policy"].get(ctx.policy_orientation, "?"))
    p.append("[/宏观背景板]")
    return NL.join(p)

def ddm_injection(ctx, biz_type=""):
    p = ["[DDM三要素分析框架]"]
    p.append("1. 盈利驱动: 当前处于" + CYCLES["earnings"].get(ctx.earnings_cycle, "?"))
    p.append("2. 流动性驱动: 当前处于" + CYCLES["liquidity"].get(ctx.liquidity_cycle, "?"))
    p.append("3. 风险偏好: 当前" + CYCLES["risk"].get(ctx.risk_preference, "?"))
    if biz_type:
        p.append("")
        p.append("商业模式类型: " + biz_type)
    p.append("[/DDM三要素]")
    return NL.join(p)