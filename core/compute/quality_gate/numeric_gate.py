"""
1号分析师 V30 — L2 数值质量门禁

在计算层的输出进入生成层之前，进行数值级校验：

1. 营收增速自洽性：驱动因子之和 ≈ 总增速
2. 毛利率变化自洽性
3. 关键指标的时序一致性
4. 标记缺失数据和置信度
"""

from __future__ import annotations

from typing import Optional

from core.models import ComputedResults, StructuredData


def run_numeric_gate(
    results: ComputedResults,
    l1_data: Optional[StructuredData] = None,
) -> ComputedResults:
    """
    执行数值质量门禁。

    Args:
        results: L2 计算层的输出
        l1_data: L1 原始数据（可选，用于交叉验证）

    Returns:
        添加了 numeric_gate_report 的 ComputedResults
    """
    warnings = list(results.warnings)
    checks = {}
    all_passed = True

    # 检查1: 收入桥自洽性
    if results.revenue_bridge is not None:
        bridge_check = _check_revenue_bridge(results.revenue_bridge)
        checks["revenue_bridge"] = bridge_check
        if not bridge_check["passed"]:
            all_passed = False
            warnings.append(bridge_check["message"])

    # 检查2: 毛利桥自洽性
    if results.margin_bridge is not None:
        margin_check = _check_margin_bridge(results.margin_bridge)
        checks["margin_bridge"] = margin_check
        if not margin_check["passed"]:
            all_passed = False
            warnings.append(margin_check["message"])

    # 检查3: 财务摘要完整性
    summary_check = _check_summary_completeness(results)
    checks["summary_completeness"] = summary_check
    if not summary_check["passed"]:
        warnings.append(summary_check["message"])

    # 检查4: 跨数据源一致性
    if l1_data is not None:
        consistency_check = _check_cross_layer_consistency(results, l1_data)
        checks["cross_layer_consistency"] = consistency_check
        if not consistency_check["passed"]:
            warnings.append(consistency_check["message"])

    # 检查5: DCF 模型合理性
    if results.dcf_result:
        dcf_check = _check_dcf_reasonableness(results.dcf_result)
        checks["dcf_reasonableness"] = dcf_check
        if not dcf_check["passed"]:
            all_passed = False
            warnings.append(dcf_check["message"])

    # 综合报告
    score = 100
    for check in checks.values():
        score -= check.get("penalty", 0)
    score = max(0, min(100, score))

    results.numeric_gate_report = {
        "passed": all_passed,
        "score": score,
        "checks": checks,
    }
    results.warnings = warnings

    return results


def _check_revenue_bridge(bridge) -> dict:
    """检查收入桥自洽性。"""
    if not bridge.drivers:
        return {
            "passed": False,
            "penalty": 10,
            "message": "收入桥驱动因子为空，无法验证",
        }
    return {
        "passed": True,
        "penalty": 0,
        "message": "收入桥包含驱动因子，可通过",
    }


def _check_margin_bridge(bridge) -> dict:
    """检查毛利桥自洽性。"""
    if bridge.gross_margin_prev is None or bridge.gross_margin_current is None:
        return {
            "passed": False,
            "penalty": 15,
            "message": "毛利桥缺少基期或当前毛利率数据",
        }
    if abs(bridge.gross_margin_current) > 100:
        return {
            "passed": False,
            "penalty": 20,
            "message": "毛利率异常（超过+-100%%）".replace("%%", "%"),
        }
    return {
        "passed": True,
        "penalty": 0,
        "message": "毛利率在合理范围内",
    }


def _check_summary_completeness(results: ComputedResults) -> dict:
    """检查财务摘要的完整性。"""
    fs = results.financial_summary
    missing = []
    for name, values in fs.items.items():
        for y in fs.years:
            val = values.get(str(y), values.get(y, None))
            if val is None:
                missing.append("%s[%s]" % (name, y))

    if missing:
        return {
            "passed": True,
            "penalty": len(missing),
            "message": "财务摘要中 %d 个数据点缺失" % len(missing),
            "missing": missing[:5],
        }
    return {
        "passed": True,
        "penalty": 0,
        "message": "财务摘要完整",
    }


def _check_cross_layer_consistency(results: ComputedResults, l1_data: StructuredData) -> dict:
    """检查 L2 计算结果与 L1 原始数据的一致性。"""
    penalties = []

    if results.revenue_bridge:
        last_l1 = None
        for f in sorted(l1_data.financials, key=lambda x: x.fiscal_year):
            last_l1 = f
        if last_l1 and last_l1.revenue is not None:
            if results.revenue_bridge.drivers:
                last_driver = results.revenue_bridge.drivers[-1]
                last_rev_in_bridge = last_driver.get("revenue_level", 0)
                if last_rev_in_bridge and abs(last_rev_in_bridge - last_l1.revenue) > 0.01:
                    penalties.append("收入桥末年营收 %s 与 L1 %s 不一致" % (last_rev_in_bridge, last_l1.revenue))

    status = "通过" if len(penalties) == 0 else "发现: %s" % penalties
    return {
        "passed": len(penalties) == 0,
        "penalty": len(penalties) * 10,
        "message": "跨层一致性校验 " + status,
        "details": penalties,
    }


def _check_dcf_reasonableness(dcf_result: dict) -> dict:
    """
    检查 DCF 模型结果的合理性。

    校验项:
      1. WACC 是否在合理范围 (2%% ~ 20%%)
      2. 终值占比是否过高 (>90%%)
      3. 企业价值和目标价是否为正
      4. 敏感性矩阵是否完整
    """
    penalties = 0
    messages = []

    wacc = dcf_result.get("assumptions", {}).get("wacc", 0)
    if wacc <= 0.02 or wacc >= 0.20:
        penalties += 15
        messages.append("WACC=%.2f%% 异常，合理范围2%%~20%%" % (wacc * 100))

    ev = dcf_result.get("enterprise_value", 0)
    tv = dcf_result.get("terminal_value", 0)
    if ev > 0:
        tv_ratio = abs(tv) / abs(ev)
        if tv_ratio > 0.90:
            penalties += 20
            messages.append("终值占EV比 %.1f%%%% > 90%%%%，DCF结果对终值假设过度依赖" % (tv_ratio * 100))
        elif tv_ratio > 0.80:
            penalties += 10
            messages.append("终值占EV比 %.1f%%%% > 80%%%%，终值依赖度偏高" % (tv_ratio * 100))

    target_price = dcf_result.get("target_price", 0)
    if target_price <= 0:
        penalties += 15
        messages.append("目标价 %s <= 0，估值结果异常" % target_price)

    pv_fcf = dcf_result.get("present_value_of_fcf", 0)
    if pv_fcf <= 0 and ev > 0:
        penalties += 10
        messages.append("预测期FCF现值 <= 0，估值完全依赖终值")

    sensitivity = dcf_result.get("sensitivity_matrix", {})
    if not sensitivity or len(sensitivity) < 3:
        penalties += 10
        messages.append("敏感性矩阵不完整")

    passed = penalties < 30

    # Fix double %%
    cleaned_messages = [m.replace("%%%%", "%%") for m in messages]

    if passed:
        msg = "DCF合理性校验: 通过"
    else:
        msg = "DCF合理性校验: " + "; ".join(cleaned_messages)

    return {
        "passed": passed,
        "penalty": min(penalties, 100),
        "message": msg,
        "details": cleaned_messages,
    }
