"""S3-3: 信号背离标注

检测舆情情绪 vs 基本面趋势的背离：
- 情绪强负面 但 营收正增长 → 背离
- 情绪正面 但 资金流出 → 背离
返回背离列表，注入报告"风险"段。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("signal_divergence")


def detect_divergence(
    fig_sentiment: dict | None = None,
    fig_revenue: dict | None = None,
    fig_valuation: dict | None = None,
    fig_capital_flow: dict | None = None,
) -> list[dict]:
    """检测信号背离。

    Args:
        fig_sentiment: 舆情情绪数据 {score: float, trend: str, headlines: list}
        fig_revenue: 营收数据 {yoy_growth: float, trend: str}
        fig_valuation: 估值数据 {pe: float, pb: float, vs_history: str}
        fig_capital_flow: 资金流向 {net_inflow: float, trend: str}

    Returns:
        [{"signal_a": str, "signal_b": str, "type": str, "severity": str, "note": str}]
    """
    divergences = []

    if fig_sentiment and fig_revenue:
        s_score = fig_sentiment.get("score", 0)
        r_growth = fig_revenue.get("yoy_growth", 0)

        # 情绪负面但营收正增长
        if s_score < -0.3 and r_growth > 0.05:
            divergences.append({
                "signal_a": f"舆情情绪 {s_score:.2f}（负面）",
                "signal_b": f"营收同比 +{r_growth:.1%}",
                "type": "sentiment_fundamental",
                "severity": "medium",
                "note": "市场情绪悲观但基本面仍在增长，可能存在超跌机会或市场提前反映下行风险",
            })

        # 情绪正面但营收负增长
        if s_score > 0.3 and r_growth < -0.05:
            divergences.append({
                "signal_a": f"舆情情绪 {s_score:.2f}（正面）",
                "signal_b": f"营收同比 {r_growth:.1%}",
                "type": "sentiment_fundamental",
                "severity": "high",
                "note": "市场情绪乐观但基本面恶化，需警惕预期差风险",
            })

    if fig_sentiment and fig_capital_flow:
        s_score = fig_sentiment.get("score", 0)
        net_inflow = fig_capital_flow.get("net_inflow", 0)

        # 情绪正面但资金流出
        if s_score > 0.3 and net_inflow < 0:
            divergences.append({
                "signal_a": f"舆情情绪 {s_score:.2f}（正面）",
                "signal_b": f"资金净流出 {net_inflow:.0f}",
                "type": "sentiment_flow",
                "severity": "medium",
                "note": "情绪乐观但资金在撤离，可能是聪明钱在出货",
            })

        # 情绪负面但资金流入
        if s_score < -0.3 and net_inflow > 0:
            divergences.append({
                "signal_a": f"舆情情绪 {s_score:.2f}（负面）",
                "signal_b": f"资金净流入 +{net_inflow:.0f}",
                "type": "sentiment_flow",
                "severity": "low",
                "note": "情绪悲观但资金在流入，可能存在分歧",
            })

    if fig_revenue and fig_valuation:
        r_growth = fig_revenue.get("yoy_growth", 0)
        vs_hist = fig_valuation.get("vs_history", "")

        # 营收增长但估值历史低位
        if r_growth > 0.1 and "低位" in vs_hist:
            divergences.append({
                "signal_a": f"营收同比 +{r_growth:.1%}",
                "signal_b": f"估值处于{vs_hist}",
                "type": "fundamental_valuation",
                "severity": "low",
                "note": "增长良好但估值被压制，需检查是否有结构性折价因素",
            })

    return divergences


def format_divergence_section(divergences: list[dict]) -> str:
    """格式化为报告段落。"""
    if not divergences:
        return ""

    lines = ["### 信号背离提示", ""]
    for d in divergences:
        severity_mark = {"high": "⚠️", "medium": "⚡", "low": "ℹ️"}.get(d["severity"], "")
        lines.append(f"- {severity_mark} **{d['type']}**: {d['signal_a']} vs {d['signal_b']}")
        lines.append(f"  {d['note']}")
    lines.append("")

    return "\n".join(lines)


def main():
    """测试用例。"""
    divs = detect_divergence(
        fig_sentiment={"score": -0.5, "trend": "negative", "headlines": ["业绩下滑"]},
        fig_revenue={"yoy_growth": 0.12, "trend": "up"},
        fig_capital_flow={"net_inflow": -5000, "trend": "outflow"},
    )
    print(format_divergence_section(divs))


if __name__ == "__main__":
    main()
