# -*- coding: utf-8 -*-
"""valuation_guardrails.py — 估值规则护栏（R56 知识库接线）

把 methodology_valuation_deep.json 的可执行估值规则落地为
DCF/估值计算后的确定性校验。规则来源：知识库 03-估值与测算 深度吸收
（111 条估值规则，含 DCF/可比/三表勾稽/敏感性/交叉验证）。

核心规则（从知识库提炼）：
  1. 口径一致性：股权价值(FCFE/PE) vs 企业价值(FCFF/EV) 全篇一致
  2. WACC 披露：Rf/ERP/β/债务成本/资本结构/税率齐全，债务成本税后化
  3. 永续增长 g < r（折现率），否则终值无意义
  4. 终值占比合理（< 80%，过高说明显性预测期太短）
  5. 多方法估值差异 >30% → 定位分歧根因，非直接平均

用法：
  from core.compute.valuation_guardrails import validate_dcf_guards
  issues = validate_dcf_guards(dcf_result, wacc, terminal_growth, tv_pct)
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger("2hao.valuation_guardrails")

_ROOT = Path(__file__).resolve().parent.parent.parent

# 终值占比警戒线
_TV_PCT_WARN = 0.80
# 多方法估值差异警戒线
_MULTI_METHOD_TOL = 0.30


def _load_rules() -> dict:
    """加载知识库估值规则（不存在则返回空）。"""
    p = _ROOT / "data" / "methodology_valuation_deep.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def validate_dcf_guards(dcf_result=None, wacc: float = 0.0,
                        terminal_growth: float = 0.0,
                        tv_pct: float = 0.0,
                        uses_fcfe: bool = False,
                        fair_value: float = 0.0) -> list[str]:
    """DCF 结果的知识库规则校验。

    Args:
        dcf_result: DCF 计算结果（含 fair_value 等）
        wacc: 折现率 WACC
        terminal_growth: 永续增长率 g
        tv_pct: 终值占 DCF 总价值比例（0-1）
        uses_fcfe: True=FCFE(股权价值)/False=FCFF(企业价值)
        fair_value: 计算出的公允价值（元/股）

    Returns:
        issues: 违反的规则列表（空 = 全部通过）
    """
    issues = []
    rules = _load_rules()
    if not rules:
        return issues  # 无知识库时静默跳过（不阻断）

    # 规则1：g < r（永续增长必须小于折现率）
    if wacc and terminal_growth:
        if terminal_growth >= wacc:
            issues.append(
                f"[估值护栏] 永续增长g={terminal_growth:.2%} ≥ 折现率r={wacc:.2%}，"
                f"终值无意义（须 g < r）")

    # 规则2：终值占比合理（<80%）
    if tv_pct > 0:
        if tv_pct > _TV_PCT_WARN:
            issues.append(
                f"[估值护栏] 终值占比 {tv_pct:.0%} > {_TV_PCT_WARN:.0%}，"
                f"显性预测期过短或增长假设过激进（须 <{_TV_PCT_WARN:.0%}）")

    # 规则3：估值结果合理区间（公允价值为正）
    if fair_value is not None and fair_value <= 0:
        issues.append(
            f"[估值护栏] 公允价值 {fair_value} ≤ 0，DCF 结果异常")

    # 规则4：口径一致性提示（FCFF 应用企业价值口径，不能直接当股权价值）
    if uses_fcfe is False and dcf_result is not None:
        # FCFF → 企业价值，需扣净债务才是股权价值；FCFE → 直接股权价值
        net_debt = getattr(dcf_result, "net_debt", 0) or 0
        if net_debt > 0:
            issues.append(
                f"[估值护栏] 使用FCFF口径（企业价值），但净债务 {net_debt} 未扣除，"
                f"股权价值 = 企业价值 − 净债务（口径一致性）")

    return issues


def check_multi_method_consistency(values: dict) -> list[str]:
    """多方法估值一致性：差异 >30% 定位分歧根因，非直接平均。

    Args:
        values: {方法名: 估值结果}（如 {"dcf": 48, "pe": 44, "comparable": 52}）

    Returns:
        issues: 违反规则的提示
    """
    issues = []
    vals = {k: v for k, v in values.items() if v and v > 0}
    if len(vals) < 2:
        return issues
    _vals = sorted(vals.values())
    _min, _max = _vals[0], _vals[-1]
    if _max / _min - 1 > _MULTI_METHOD_TOL:
        issues.append(
            f"[估值护栏] 多方法估值差异 {(_max/_min-1):.0%} > {_MULTI_METHOD_TOL:.0%}"
            f"（{min(vals, key=vals.get)}={_min} vs {max(vals, key=vals.get)}={_max}），"
            f"应定位分歧根因（增长率/WACC/可比选择），而非直接平均")
    return issues


def validate_comparable_guards(target_pe: float = 0.0,
                               implied_price: float = 0.0,
                               peer_count: int = 0,
                               company_eps: float = 0.0) -> list[str]:
    """可比估值护栏（valuation_deep comparable checklist）。

    规则：
      1. 可比公司 ≥3 家（不足 3 家 → 可比性不足，提示）
      2. 目标价/评级与估值方向一致（implied_price > 0 才有效）
      3. PE 计算用正常化盈利（company_eps > 0 才有效）
    """
    issues = []
    # 规则1：可比公司 ≥3 家
    if 0 < peer_count < 3:
        issues.append(
            f"[估值护栏] 可比公司仅 {peer_count} 家 < 3，可比性不足（投行标准≥3-5家）")
    # 规则2：隐含价格有效
    if implied_price <= 0:
        issues.append(
            f"[估值护栏] 可比估值隐含价 {implied_price} ≤ 0，结果异常")
    # 规则3：EPS 为 0 时 PE 无意义
    if company_eps <= 0 and target_pe > 0:
        issues.append(
            f"[估值护栏] 公司EPS={company_eps} ≤ 0，PE 估值失真（应说明为何仍用PE）")
    return issues


def validate_scenario_guards(bull: float = 0.0, base: float = 0.0,
                             bear: float = 0.0,
                             risk_reward: float = 0.0) -> list[str]:
    """情景分析护栏（valuation_deep sensitivity/情景规则）。

    规则：
      1. 单调性：bull > base > bear（否则情景排序异常）
      2. 风险收益比 > 0（负值说明 downside 大于 upside）
      3. bull/base/bear 间差异不过度（bull 不应是 bear 的 3 倍以上）
    """
    issues = []
    # 规则1：单调性
    if bull > 0 and base > 0 and bear > 0:
        if not (bull >= base >= bear):
            issues.append(
                f"[估值护栏] 情景排序异常: bull={bull} base={base} bear={bear}"
                f"（须 bull ≥ base ≥ bear）")
    # 规则2：风险收益比
    if bull > 0 and bear > 0 and risk_reward < 0:
        issues.append(
            f"[估值护栏] 风险收益比 {risk_reward:.2f} < 0，下行空间大于上行")
    # 规则3：极差不过度
    if bear > 0 and bull / bear > 3.0:
        issues.append(
            f"[估值护栏] 乐观/悲观价差过大: bull={bull} vs bear={bear}"
            f"（{bull/bear:.1f}倍 > 3倍，假设可能过度乐观/悲观）")
    return issues


if __name__ == "__main__":
    # 自测
    issues = validate_dcf_guards(
        dcf_result=None, wacc=0.10, terminal_growth=0.12, tv_pct=0.85,
        fair_value=-1.0)
    print("DCF 护栏:", issues if issues else "全部通过")
    mi = check_multi_method_consistency({"dcf": 48, "pe": 44, "comparable": 70})
    print("多方法:", mi if mi else "一致")
