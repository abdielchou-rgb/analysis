# -*- coding: utf-8 -*-
"""business_logic_gate.py — 业务逻辑检测（2026-08-08 圆桌 Codex 建议）

检测报告中的"业务逻辑断点"——非数字一致性，而是语义级逻辑：
  1. 双价格带冲突：报告出现两个明显不同的价格带但未说明业务关系
     （油位 v2.3 事故：久通300元 vs 测算5000元，未讲清双轨承接）
  2. 跨章节口径冲突：同一指标在不同章节出现不同值（盈亏平衡30% vs 中高端40-50%）
  3. 声称无量化的价值：报告声称"协同/期权/战略价值"但无数值支撑

用法：
  from core.business_logic_gate import check_business_logic
  result = check_business_logic(report_text)
"""
from __future__ import annotations
import re
import logging

logger = logging.getLogger("2hao.business_logic")


def check_business_logic(report_text: str) -> dict:
    """业务逻辑检测入口。返回 {passed, issues, details}。"""
    issues = []
    text = report_text or ""

    # 1. 双价格带冲突检测
    # 匹配：单价约300元/只 / 5,000元/台 / 取中位5,000元 / 价格带3,000-8,000元
    price_pattern = r"(?:单价|价格|售价|中位|约|元/台|元/只)[^0-9]{0,8}?([0-9][0-9,]{1,8})(?:元)"
    prices = []
    for m in re.finditer(price_pattern, text):
        try:
            v = float(m.group(1).replace(",", ""))
            prices.append((v, m.group(0)[:40]))
        except ValueError:
            continue
    # 找"低值 + 高值"并存（价差>3倍）且无"入场券/主战场/双轨/两条业务线"说明
    if len(prices) >= 2:
        low = min(p[0] for p in prices)
        high = max(p[0] for p in prices)
        if high > low * 3:
            has_explanation = any(k in text for k in
                                  ("双轨", "两条业务线", "入场券", "主战场", "业务定位", "代工线", "中高端线"))
            issues.append({
                "type": "dual_price_band",
                "severity": "warning" if has_explanation else "error",
                "low_price": low,
                "high_price": high,
                "ratio": round(high / low, 1),
                "issue": f"报告出现价格带 {low:.0f} 与 {high:.0f}（差{high/low:.1f}倍）"
                         + ("，已说明双轨业务关系" if has_explanation else "，但未说明两条业务线关系——需明确是入场券+主战场"),
            })

    # 2. 跨章节口径冲突（毛利率等）
    margin_vals = []
    for m in re.finditer(r"毛利率\s*([0-9]{1,3})%", text):
        try:
            margin_vals.append(int(m.group(1)))
        except ValueError:
            continue
    if len(set(margin_vals)) >= 2:
        lo, hi = min(margin_vals), max(margin_vals)
        if hi - lo > 15:
            has_explanation = any(k in text for k in ("口径", "盈亏平衡", "中高端", "场景不同"))
            issues.append({
                "type": "cross_section_margin_conflict",
                "severity": "warning" if has_explanation else "error",
                "values": sorted(set(margin_vals)),
                "issue": f"毛利率口径不一致（{sorted(set(margin_vals))}），差异{hi-lo}pct——"
                         + ("已说明场景不同" if has_explanation else "需统一口径（盈亏平衡 vs 中高端）"),
            })

    # 3. 声称无量化的价值检测
    for kw in ["协同", "期权", "战略价值", "衍生价值", "护城河"]:
        if kw in text:
            # 检查该词附近是否有数字
            for m in re.finditer(kw, text):
                window = text[max(0, m.start()-30):m.end()+80]
                has_num = bool(re.search(r"[0-9]{2,}", window))
                if not has_num:
                    issues.append({
                        "type": "claimed_value_no_quant",
                        "severity": "warning",
                        "claim": kw,
                        "issue": f"声称「{kw}」但附近无量化数值——顶级报告会对战略价值做粗略量化",
                    })
                    break

    passed = not any(i["severity"] == "error" for i in issues)
    return {
        "passed": passed,
        "issues": issues,
        "error_count": sum(1 for i in issues if i["severity"] == "error"),
        "warning_count": sum(1 for i in issues if i["severity"] == "warning"),
    }


def business_logic_gate_node(node_id: str, context: dict) -> dict:
    """IronGate 集成节点。"""
    text = context.get("final_text") or context.get("report_text", "")
    if not text:
        return {"business_logic_passed": True}
    try:
        result = check_business_logic(text)
        context["business_logic_result"] = result
        logger.info("[BUSINESS-LOGIC] passed=%s errors=%d warnings=%d",
                    result["passed"], result["error_count"], result["warning_count"])
        return {
            "business_logic_passed": result["passed"],
            "business_logic_errors": result["error_count"],
            "business_logic_warnings": result["warning_count"],
        }
    except Exception as e:
        logger.debug("[BUSINESS-LOGIC] %s", str(e)[:60])
        return {"business_logic_passed": True}
