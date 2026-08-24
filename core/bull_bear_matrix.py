# -*- coding: utf-8 -*-
"""
多空逻辑表（Bull/Bear Case Matrix）— R23 王牌方法：一页纸证伪框架

**核心**：顶级买方的标配。把多头逻辑、空头逻辑、各自的关键假设、证伪信号
并排列出——让读者一眼看到"什么情况下我会错"。与反共识检测互补：
反共识找市场分歧点，多空表把分歧结构化。

**来源**：
  - 反共识信号（detect_anti_consensus）→ bull/bear 各一条
  - 反向DCF 预期差 → 估值判断
  - 瓶颈分析（卡位评级）→ 供给端多头逻辑
  - 催化剂日历 → 验证时间点
  - 盈利预测（build_forecast）→ 增长假设

输出结构化 bull_side / bear_side / falsification_conditions，供正文引用。
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger("2hao.bullbear")

_ROOT = Path(__file__).resolve().parent.parent


def _safe(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def build_bull_bear_matrix(data: dict, report_type: str = "listed_company") -> dict:
    """构建多空逻辑表。

    返回 dict：{status, bull_side:[{logic, assumption, evidence}],
               bear_side:[...], falsification:[...], summary}
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    if not isinstance(cd, dict):
        cd = {}
    asset = data.get("asset", "") if isinstance(data, dict) else ""
    asset_name = asset.split()[0] if asset else ""

    bull = []
    bear = []
    falsification = []

    # ── 1. 反共识信号（分歧点）──
    try:
        from core.compute.anti_consensus import detect_anti_consensus
        ac = detect_anti_consensus(asset, data) or {}
        for s in ac.get("signals", []):
            stype = s.get("type", "")
            if s.get("bias") in ("consensus_positive", "bullish", "undervalued"):
                bull.append({"logic": f"市场分歧点：{s.get('signal','')}",
                             "assumption": "市场低估了该信号隐含的利好",
                             "evidence": f"反共识信号({stype})"})
            elif s.get("bias") in ("consensus_negative", "bearish", "overvalued"):
                bear.append({"logic": f"市场分歧点：{s.get('signal','')}",
                             "assumption": "市场高估了该信号隐含的利好",
                             "evidence": f"反共识信号({stype})"})
    except Exception as _e:
        logger.debug("[BULLBEAR] anti_consensus: %s", _e)

    # ── 2. 瓶颈分析（卡位）──
    try:
        from core.bottleneck_engine import build_bottleneck_analysis
        bn = build_bottleneck_analysis(data, report_type) or {}
        cp = bn.get("chokepoint", {})
        if cp and cp.get("rating") in ("强", "中"):
            bull.append({"logic": f"卡位评级 {cp.get('rating')}：卡在供应链瓶颈上",
                         "assumption": "瓶颈环节的议价权能转化为利润",
                         "evidence": f"卡点评分 {cp.get('score')}/{cp.get('max_score')}"})
        elif cp and cp.get("rating") in ("弱", "无"):
            bear.append({"logic": f"卡位评级 {cp.get('rating')}：未卡在瓶颈上",
                         "assumption": "供给可替代，议价权弱",
                         "evidence": f"卡点评分 {cp.get('score')}/{cp.get('max_score')}"})
        pp = bn.get("profit_pool", {})
        if pp.get("status") == "ok" and pp.get("thickest"):
            bull.append({"logic": f"利润池最厚环节 {pp.get('thickest')}",
                         "assumption": "该环节利润份额可持续",
                         "evidence": f"利润池流向：{pp.get('migration')}"})
    except Exception as _e:
        logger.debug("[BULLBEAR] bottleneck: %s", _e)

    # ── 3. 反向DCF 预期差（估值）──
    try:
        from core.compute.patterns import estimate_implied_growth_full
        mcap = cd.get("market_cap")
        fcf = cd.get("fcf", cd.get("free_cash_flow"))
        if mcap and fcf:
            rd = estimate_implied_growth_full(market_cap=_safe(mcap),
                                              current_fcf=_safe(fcf))
            if rd and rd.data:
                gap = rd.data.get("expectation_gap_pct", 0)
                if gap < -5:
                    bull.append({"logic": f"市场隐含增速{rd.data['implied_growth_pct']}%低于我们的{rd.data['our_growth_pct']}%",
                                 "assumption": "我们的增长预测正确，市场过于悲观",
                                 "evidence": f"反向DCF预期差 {gap:+.1f}%"})
                elif gap > 5:
                    bear.append({"logic": f"市场隐含增速{rd.data['implied_growth_pct']}%高于我们的{rd.data['our_growth_pct']}%",
                                 "assumption": "市场过于乐观，增长难兑现",
                                 "evidence": f"反向DCF预期差 {gap:+.1f}%"})
    except Exception as _e:
        logger.debug("[BULLBEAR] reverse_dcf: %s", _e)

    # ── 4. 估值基线对比（行业PE）──
    pe = _safe(cd.get("pe", cd.get("pe_ttm", 0)))
    industry_pe = _safe(cd.get("industry_pe_ttm", 0))
    if pe > 0 and industry_pe > 0:
        ratio = pe / industry_pe
        if ratio > 1.3:
            bear.append({"logic": f"估值溢价：PE={pe:.1f} vs 行业{industry_pe:.1f}（{ratio:.1f}x）",
                         "assumption": "高溢价需高增长兑现支撑",
                         "evidence": "行业估值基线"})
        elif ratio < 0.7:
            bull.append({"logic": f"估值折价：PE={pe:.1f} vs 行业{industry_pe:.1f}（{ratio:.1f}x）",
                         "assumption": "折价将随基本面验证收敛",
                         "evidence": "行业估值基线"})

    # ── 5. 催化剂日历（验证时间点）──
    try:
        from core.catalyst_timeline import build_catalyst_timeline
        ct = build_catalyst_timeline(data, report_type)
        if ct.get("status") == "ok":
            falsification.append(
                {"condition": f"催化剂证伪点：{ct.get('next_catalyst')} — {ct.get('next_catalyst_desc','')[:40]}",
                 "trigger": ct.get("next_earnings", "")})
    except Exception as _e:
        logger.debug("[BULLBEAR] catalyst: %s", _e)

    # ── 默认填充（保证非空）──
    if not bull:
        bull.append({"logic": "行业增长/政策支持",
                     "assumption": "行业需求维持增长，政策持续友好",
                     "evidence": "行业逻辑（需数据验证）"})
    if not bear:
        bear.append({"logic": "竞争加剧/需求不及预期",
                     "assumption": "竞争者进入或需求低于预期",
                     "evidence": "风险因素（需数据验证）"})
    if not falsification:
        falsification.append(
            {"condition": "财报季验证：营收/利润增速是否兑现", "trigger": "下一财报窗口"})

    return {
        "status": "ok",
        "bull_side": bull[:5],
        "bear_side": bear[:5],
        "falsification": falsification[:4],
        "summary": f"多头逻辑 {len(bull)} 条 / 空头逻辑 {len(bear)} 条 / 证伪条件 {len(falsification)} 条",
    }


def serialize_bull_bear(bb: dict, max_chars: int = 1000) -> str:
    """序列化为 prompt 注入文本。"""
    if not bb or bb.get("status") != "ok":
        return ""
    lines = ["=== 多空逻辑表（Bull/Bear Case Matrix）==="]
    lines.append(f"**多头逻辑**（{len(bb.get('bull_side', []))}条）:")
    for b in bb.get("bull_side", []):
        lines.append(f"- {b.get('logic','')[:50]} | 假设: {b.get('assumption','')[:30]}")
    lines.append(f"\n**空头逻辑**（{len(bb.get('bear_side', []))}条）:")
    for b in bb.get("bear_side", []):
        lines.append(f"- {b.get('logic','')[:50]} | 假设: {b.get('assumption','')[:30]}")
    lines.append(f"\n**证伪条件**（什么情况下我会错）:")
    for f in bb.get("falsification", []):
        lines.append(f"- {f.get('condition','')[:55]} | 触发: {f.get('trigger','')}")
    return "\n".join(lines)[:max_chars]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    sample = {"asset": "柯力传感(603662.SH)",
              "chart_data": {"pe": 25, "industry_pe_ttm": 20,
                             "market_cap": 80, "fcf": 6}}
    bb = build_bull_bear_matrix(sample, "listed_company")
    print(serialize_bull_bear(bb))
