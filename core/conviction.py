"""V51 Conviction Matrix — integrates V30 scenario analysis into workflow.

基于摩根士丹利 Risk-Reward 框架。读取 SAC 各维度的论证强度，
自动生成三情景加权目标价 + 置信度评分。

完全确定性代码，零 LLM，零 API。
"""

from __future__ import annotations
from dataclasses import dataclass, field
import logging
from typing import Optional

from core.models import ArgumentScaffold, KnowledgePackage, DataPoint
from core.assumption_benchmark import calibrate_probabilities, detect_growth_assumption_gap

logger = logging.getLogger("v51.conviction")

_HAS_SCENARIO = False
try:
    from core.compute.valuation.scenario import (
        compute_scenario,
        make_base_scenario,
        make_bull_scenario,
        make_bear_scenario,
        ScenarioResult,
    )
    _HAS_SCENARIO = True
except ImportError as e:
    logger.warning("V30 scenario not available: %s", e)


@dataclass
class ConvictionMatrix:
    """置信度矩阵 — 整合三情景 + 论证强度。"""
    asset: str = ""
    stock_code: str = ""
    base_price: float = 0.0

    # 三情景
    base_target: float = 0.0
    bull_target: float = 0.0
    bear_target: float = 0.0
    weighted_target: float = 0.0
    upside_pct: float = 0.0
    downside_pct: float = 0.0
    risk_reward: float = 0.0

    # 置信度评分 (0-100)
    evidence_score: float = 0.0  # 证据充分度
    consensus_gap: float = 0.0   # 与共识的偏离度
    overall_conviction: float = 0.0

    warnings: list[str] = field(default_factory=list)


def compute_conviction(
    scaffold: ArgumentScaffold,
    kp: KnowledgePackage,
    base_price: Optional[float] = None,
) -> ConvictionMatrix:
    """从论证骨架 + 知识包计算 Conviction Matrix。"""
    cm = ConvictionMatrix(
        asset=kp.brief.asset if kp.brief else "",
        stock_code=kp.brief.asset_code if kp.brief else "",
        base_price=base_price or 0.0,
    )

    if not _HAS_SCENARIO:
        cm.warnings.append("V30 scenario mod  le 不可用，跳过情景计算")
        return cm

    # 从 SAC 维度提取参数
    revenue_base = _extract_revenue(kp)
    evi_count = len(kp.evidence_items) if kp.evidence_items else 0
    gap_count = len(kp.data_gaps) if kp.data_gaps else 0

    # 论证强度 → 情景概率调整
    base_conf = 0.55
    bull_conf = 0.20
    bear_conf = 0.25

    if gap_count > 5:
        bear_conf += 0.10
        base_conf -= 0.10
    if evi_count > 10:
        base_conf += 0.05
        bull_conf += 0.05
        bear_conf -= 0.10

    # V53 B1: Calibrate using industry assumption benchmark if available
    industry = ""
    if kp.sac and hasattr(kp.sac, "applies_to") and kp.sac.applies_to:
        industry = kp.sac.applies_to[0]
    if industry:
        try:
            calib = calibrate_probabilities(
                industry=industry,
                revenue_cagr=revenue_base,
                base_prob=(base_conf, bull_conf, bear_conf),
            )
            base_conf = calib["base"]
            bull_conf = calib["bull"]
            bear_conf = calib["bear"]
            cm.calibration_log = calib.get("calibration_log", [])
        except Exception as cal_err:
            logger.debug("Benchmark calibration skipped: %s", cal_err)

    total = base_conf + bull_conf + bear_conf
    base_conf /= total
    bull_conf /= total
    bear_conf /= total

    base = make_base_scenario(probability=base_conf)
    bull = make_bull_scenario(probability=bull_conf)
    bear = make_bear_scenario(probability=bear_conf)

    base_price_c = base_price or 0.0

    result = compute_scenario(
        company=cm.asset,
        stock_code=cm.stock_code,
        base_price=base_price_c or 100.0,
        base_scenario=base,
        bull_scenario=bull,
        bear_scenario=bear,
        base_revenue=revenue_base,
    )

    cm.base_target = result.scenarios.get("base", {}).get("target_price", 0.0)
    cm.bull_target = result.scenarios.get("bull", {}).get("target_price", 0.0)
    cm.bear_target = result.scenarios.get("bear", {}).get("target_price", 0.0)
    cm.weighted_target = result.weighted_target_price
    cm.upside_pct = result.upside or 0.0
    cm.downside_pct = result.downside or 0.0
    cm.risk_reward = result.risk_reward_ratio or 0.0

    # 置信度评分
    cm.evidence_score = min(100, evi_count * 10)
    cm.consensus_gap = min(100, gap_count * 15)
    cm.overall_conviction = round(
        cm.evidence_score * 0.6 + (100 - cm.consensus_gap) * 0.4, 1
    )
    cm.warnings.extend(result.warnings)

    return cm


def _extract_revenue(kp: KnowledgePackage) -> Optional[float]:
    """从知识包提取基准营收。"""
    if not kp.data_points:
        return None
    for dp in kp.data_points:
        if dp.name in ("revenue", "revenue_bn", "营收") and dp.value:
            return float(dp.value)
    return None


def format_conviction(cm: ConvictionMatrix) -> str:
    """格式化为报告可插入的文本块。"""
    lines = []
    lines.append("\n## 置信度矩阵\n")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 概率加权目标价 | {cm.weighted_target:.2f} 元 |")
    if cm.base_price > 0:
        lines.append(f"| 当前价格 | {cm.base_price:.2f} 元 |")
    lines.append(f"| 基准情景 | {cm.base_target:.2f} 元 |")
    lines.append(f"| 乐观情景 | {cm.bull_target:.2f} 元 |")
    lines.append(f"| 悲观情景 | {cm.bear_target:.2f} 元 |")
    if cm.base_price > 0:
        lines.append(f"| 上行空间 | +{cm.upside_pct:.1f}% |")
        lines.append(f"| 下行空间 | {cm.downside_pct:.1f}% |")
    lines.append(f"| 风险收益比 | {cm.risk_reward:.2f}x |")
    lines.append(f"| 置信度评分 | {cm.overall_conviction}/100 |")
    for w in cm.warnings:
        lines.append(f"*{w}*")
    lines.append("")
    return "\n".join(lines)
