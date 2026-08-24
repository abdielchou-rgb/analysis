"""
Kelly Formula Module — 赔率计算与仓位建议

凯利公式: f* = (bp - q) / b
  f* = 最优下注比例
  b = 赔率 (潜在涨幅/潜在跌幅)
  p = 胜率
  q = 1-p = 败率

用于估值章节的赔率评估，增强投资判断的量化基础。
"""

from dataclasses import dataclass
from typing import Optional  # noqa: F401  (dead-import debt)


@dataclass
class KellyResult:
    optimal_fraction: float  # 凯利最优仓位比例
    upside: float  # 潜在涨幅 (%)
    downside: float  # 潜在跌幅 (%)
    win_prob: float  # 胜率
    odds_ratio: float  # 赔率
    edge: float  # 期望收益
    half_kelly: float  # 半凯利（保守）
    quarter_kelly: float  # 四分之一凯利（极保守）
    interpretation: str  # 中文解读


def kelly_bet(
    upside_pct: float,
    downside_pct: float,
    win_prob: float,
) -> KellyResult:
    """计算凯利公式

    Args:
        upside_pct: 上涨幅度 (如 50 表示+50%)
        downside_pct: 下跌幅度 (如 30 表示-30%)
        win_prob: 上涨概率 (0.0-1.0)

    Returns:
        KellyResult 包含全部计算结果
    """
    if downside_pct <= 0:
        downside_pct = 1  # 避免除零

    b = upside_pct / downside_pct  # 赔率
    p = win_prob
    q = 1.0 - p

    if b <= 0:
        return KellyResult(
            optimal_fraction=0.0,
            upside=upside_pct,
            downside=downside_pct,
            win_prob=win_prob,
            odds_ratio=0.0,
            edge=0.0,
            half_kelly=0.0,
            quarter_kelly=0.0,
            interpretation="赔率为零或负数，不建议下注",
        )

    edge = b * p - q
    f_star = (b * p - q) / b if b > 0 else 0.0
    f_star = max(0.0, min(f_star, 1.0))  # 限制在 [0, 1]

    # 解读
    if f_star <= 0:
        interp = "期望收益为负，不建议投资"
    elif f_star < 0.1:
        interp = "极低置信度仓位，仅适合极小仓位参与"
    elif f_star < 0.25:
        interp = "低置信度仓位，建议使用四分之一凯利"
    elif f_star < 0.5:
        interp = "中等置信度仓位，建议使用半凯利"
    elif f_star < 0.75:
        interp = "高置信度仓位，可适度配置"
    else:
        interp = "极高置信度仓位，可重仓配置"

    return KellyResult(
        optimal_fraction=f_star,
        upside=upside_pct,
        downside=downside_pct,
        win_prob=win_prob,
        odds_ratio=round(b, 2),
        edge=round(edge, 4),
        half_kelly=round(f_star * 0.5, 4),
        quarter_kelly=round(f_star * 0.25, 4),
        interpretation=interp,
    )


def compute_from_valuation(
    target_price: float,
    current_price: float,
    bear_case: float,
    win_prob: float,
) -> KellyResult:
    """从估值参数计算凯利

    Args:
        target_price: 目标价
        current_price: 当前价
        bear_case: 熊市情景价
        win_prob: 达到目标价的概率 (0.0-1.0)
    """
    if current_price <= 0:
        upside = 0.0
        downside = 0.0
    else:
        upside = (target_price - current_price) / current_price * 100
        downside = (current_price - bear_case) / current_price * 100

    return kelly_bet(upside, downside, win_prob)


def interpret(result: KellyResult) -> str:
    """生成自然语言的赔率分析段落"""
    lines = [
        f"赔率分析：上涨空间{result.upside:.1f}%，下跌风险{result.downside:.1f}%，",
        f"胜率{result.win_prob:.0%}，赔率{result.odds_ratio:.2f}倍。",
        f"凯利最优仓位{result.optimal_fraction:.1%}",
        f"（半凯利{result.half_kelly:.1%}，四分之一凯利{result.quarter_kelly:.1%}）。",
        result.interpretation,
    ]
    return "".join(lines)


if __name__ == "__main__":
    # Test
    r = kelly_bet(upside_pct=50, downside_pct=30, win_prob=0.6)
    print(interpret(r))
    print(f"  f*={r.optimal_fraction:.2%} half={r.half_kelly:.2%}")
