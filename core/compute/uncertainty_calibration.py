# -*- coding: utf-8 -*-
"""uncertainty_calibration.py — 预测不确定性校准（2026-08-08 框架 P2）

顶级打法：预测加置信区间 + 校准（预测区间 vs 实际命中率）。
  1. 预测给区间（非单点）——区间宽度反映不确定性
  2. 校准：历史预测区间 vs 实际命中率 → 校准系数（若90%区间仅70%命中 → 区间过窄需加宽）

用法：
  from core.compute.uncertainty_calibration import forecast_interval, calibrate, build_prompt
  interval = forecast_interval(base, uncertainty_pct)
  cal = calibrate(predictions)  # 历史校准
"""
from __future__ import annotations
import math
import logging

logger = logging.getLogger("2hao.uncertainty")


def forecast_interval(base: float, uncertainty_pct: float = 0.2,
                      confidence: float = 0.9) -> dict:
    """给预测加置信区间。

    Args:
        base: 基准预测
        uncertainty_pct: 不确定性（占基准比例，如 0.2 = ±20%）
        confidence: 置信度（0.9 = 90%区间）

    区间 = base ± z * base * uncertainty，z 按置信度。
    """
    # z 值（近似）：90%→1.645, 80%→1.28, 95%→1.96
    z_map = {0.8: 1.28, 0.9: 1.645, 0.95: 1.96}
    z = z_map.get(confidence, 1.645)
    half = z * base * uncertainty_pct
    return {
        "base": round(base, 2),
        "lower": round(base - half, 2),
        "upper": round(base + half, 2),
        "confidence": confidence,
        "half_width": round(half, 2),
    }


def calibrate(predictions: list) -> dict:
    """校准历史预测区间。

    predictions: [{lower, upper, actual}] 历史预测区间与实际值
    返回：实际命中率 vs 声明置信度 → 校准系数。
    """
    if not predictions:
        return {"status": "no_data", "calibration": 1.0}
    hits = 0
    for p in predictions:
        if p["lower"] <= p["actual"] <= p["upper"]:
            hits += 1
    hit_rate = hits / len(predictions)
    # 校准系数：若声明 90% 但只命中 70% → 系数 <1（区间过窄需加宽）
    declared = predictions[0].get("declared_conf", 0.9)
    calibration = hit_rate / declared if declared else 1.0
    return {
        "status": "ok",
        "n": len(predictions),
        "hit_rate": round(hit_rate, 3),
        "declared_conf": declared,
        "calibration": round(calibration, 3),
        "note": ("校准良好" if 0.9 <= calibration <= 1.1
                 else ("区间过窄，需加宽" if calibration < 0.9
                       else "区间过宽，可收窄")),
    }


def build_prompt(interval: dict, cal: dict) -> str:
    lines = ["=== 预测不确定性校准 ===",
             f"预测区间: {interval['lower']:,.0f} ~ {interval['upper']:,.0f}"
             f"（基准 {interval['base']:,.0f}，{interval['confidence']:.0%} 置信）"]
    if cal.get("status") == "ok":
        lines.append(f"校准: 历史{cal['n']}次预测命中 {cal['hit_rate']:.0%}"
                     f"（声明 {cal['declared_conf']:.0%}）→ 校准系数 {cal['calibration']}（{cal['note']}）")
    lines.append("=== 校准结束 ===")
    return "\n".join(lines)
