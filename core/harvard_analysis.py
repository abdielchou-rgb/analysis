# -*- coding: utf-8 -*-
"""
哈佛分析框架（Harvard Framework / Palepu-Healy）— R19 财务分析总纲

Palepu, Healy & Peek 四步分析框架，是投行/学术公认的财务分析总纲：
  1. 战略分析（Business Strategy Analysis）：行业分析+竞争战略，定性判断盈利来源
  2. 会计分析（Accounting Analysis）：识别会计政策/操纵空间，评估财务数据可靠性
  3. 财务分析（Financial Analysis）：比率分析+现金流，量化盈利能力/风险
  4. 前景分析（Prospective Analysis）：预测+估值，整合前三步给结论

**本模块**：把四步框架固化为可执行判断规则 + 从 data_dict 提取数据支撑，
注入报告 prompt，让分析按哈佛框架展开而非碎片化罗列。
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("2hao.harvard_analysis")


def build_harvard_analysis(data: dict) -> dict:
    """构建哈佛四步分析（从数据提取支撑 + 规则提示）。"""
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    if not isinstance(cd, dict):
        cd = {}
    val = cd.get("fig_valuation", {}) if isinstance(cd, dict) else {}

    # ── 数据支撑提取 ──
    pe = _sf(val.get("pe", val.get("pe_ttm", 0)))
    roe = _sf(cd.get("fig_roe_trend", {}).get("latest", 0)) if isinstance(cd.get("fig_roe_trend"), dict) else 0
    margin = _sf(cd.get("fig_margin", {}).get("latest", 0)) if isinstance(cd.get("fig_margin"), dict) else 0
    growth = _sf(cd.get("fig_revenue_trend", {}).get("growth", 0)) if isinstance(cd.get("fig_revenue_trend"), dict) else 0

    steps = {
        "1_战略分析": {
            "framework": "行业五力 + 竞争战略（成本领先/差异化/聚焦）",
            "questions": [
                "行业景气处于生命周期哪阶段？供需格局如何？",
                "公司选择成本领先还是差异化？护城河来源？",
                "上游议价、下游需求、新进入者威胁？",
            ],
            "data": {"growth": growth, "industry_pe": _sf(val.get("industry_pe", 0))},
        },
        "2_会计分析": {
            "framework": "识别会计政策与盈余操纵空间",
            "questions": [
                "收入确认政策是否激进（预收/应收异常）？",
                "存货/折旧/减值政策是否调节利润？",
                "关联交易、商誉减值风险？",
            ],
            "data": {},
        },
        "3_财务分析": {
            "framework": "比率分析 + 现金流（杜邦 + 三表勾稽）",
            "questions": [
                "ROE 杜邦三因子（利润率/周转/杠杆）哪个驱动？",
                "毛利率/费用率趋势是否健康？",
                "经营现金流是否匹配净利（利润含金量）？",
            ],
            "data": {"roe": roe, "margin": margin, "pe": pe},
        },
        "4_前景分析": {
            "framework": "预测 + 估值（三表勾稽 + DCF/可比）",
            "questions": [
                "未来 3 年盈利预测的驱动力？",
                "DCF 估值 vs 可比估值，目标区间？",
                "风险情景下估值如何变化？",
            ],
            "data": {},
        },
    }
    return {
        "steps": steps,
        "summary": "按哈佛四步：战略定方向 → 会计验质量 → 财务测盈利 → 前景给估值",
    }


def serialize_harvard_for_prompt(hf: dict, max_chars: int = 1500) -> str:
    """序列化哈佛框架为 prompt 注入文本。"""
    if not hf:
        return ""
    lines = ["=== 哈佛分析框架（Palepu-Healy 四步） ==="]
    for name, step in hf.get("steps", {}).items():
        lines.append(f"\n【{name}】{step.get('framework', '')}")
        for q in step.get("questions", []):
            lines.append(f"- {q}")
        d = step.get("data", {})
        if d:
            ds = ", ".join(f"{k}={v}" for k, v in d.items() if v)
            if ds:
                lines.append(f"  数据: {ds}")
    return "\n".join(lines)[:max_chars]


def _sf(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    hf = build_harvard_analysis({})
    print(serialize_harvard_for_prompt(hf))
