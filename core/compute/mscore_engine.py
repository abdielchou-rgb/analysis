# -*- coding: utf-8 -*-
"""mscore_engine.py — Beneish M-Score 盈余操纵检测（2026-08-08 框架优化 P0）

顶级打法：四大会所用 Beneish M-Score（8 变量）量化盈余操纵风险。
M-Score > -1.78 → 疑似操纵。

8 变量：
  DSRI  应收账款指数
  GMI   毛利率指数
  AQI   资产质量指数
  SGI   营收增长指数
  DEPI  折旧指数
  SGAI  销售管理费用指数
  LVGI  杠杆指数
  TATA  总应计占总资产

M = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI
      + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI

用法：
  from core.compute.mscore_engine import calculate_mscore
  result = calculate_mscore({...})  # 输入各变量或原始财务数据
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.mscore")


@dataclass
class MScoreResult:
    mscore: float = 0.0
    flagged: bool = False        # M > -1.78 疑似操纵
    risk_level: str = "正常"     # 正常/关注/高风险
    variables: dict = field(default_factory=dict)  # 各指数
    reasons: list = field(default_factory=list)


def calculate_mscore(vars: dict) -> MScoreResult:
    """Beneish M-Score 计算。

    vars 可直接给各指数（DSRI/GMI/AQI/SGI/DEPI/SGAI/LVGI/TATA），
    或给原始财务数据由引擎推算（简化版）。
    """
    r = MScoreResult()

    # 指数：优先直接给，缺省 1.0（中性）
    dsri = float(vars.get("DSRI", 1.0))
    gmi = float(vars.get("GMI", 1.0))
    aqi = float(vars.get("AQI", 1.0))
    sgi = float(vars.get("SGI", 1.0))
    depi = float(vars.get("DEPI", 1.0))
    sgai = float(vars.get("SGAI", 1.0))
    lvgi = float(vars.get("LVGI", 1.0))
    tata = float(vars.get("TATA", 0.0))

    r.variables = {
        "DSRI": round(dsri, 3), "GMI": round(gmi, 3), "AQI": round(aqi, 3),
        "SGI": round(sgi, 3), "DEPI": round(depi, 3), "SGAI": round(sgai, 3),
        "LVGI": round(lvgi, 3), "TATA": round(tata, 3),
    }

    # M-Score 公式
    m = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
         + 0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)
    r.mscore = round(m, 3)

    # 判定
    if m > -1.78:
        r.flagged = True
        r.risk_level = "高风险" if m > -1.0 else "关注"
        r.reasons.append(f"M-Score {m:.2f} > -1.78，疑似盈余操纵")
    else:
        r.risk_level = "正常"
        r.reasons.append(f"M-Score {m:.2f} < -1.78，盈余质量正常")

    # 单变量异常提示
    if dsri > 1.2:
        r.reasons.append(f"DSRI {dsri:.2f} 偏高（应收增速快于营收，激进确认风险）")
    if gmi > 1.2:
        r.reasons.append(f"GMI {gmi:.2f} 偏高（毛利率恶化但操纵迹象）")
    if tata > 0.1:
        r.reasons.append(f"TATA {tata:.2f} 偏高（应计利润占比大）")
    if sgi > 1.3:
        r.reasons.append(f"SGI {sgi:.2f} 偏高（营收高增长，需防激进确认）")

    return r


def build_prompt(r: MScoreResult) -> str:
    """生成注入财务章节的 M-Score 说明。"""
    lines = [
        "=== 盈余质量检测（Beneish M-Score）===",
        f"M-Score: {r.mscore}（阈值 -1.78，{'疑似操纵' if r.flagged else '正常'}）",
        f"风险等级: {r.risk_level}",
        "变量: " + ", ".join(f"{k}={v}" for k, v in r.variables.items()),
    ]
    for x in r.reasons:
        lines.append(f"- {x}")
    lines.append("=== M-Score 结束 ===")
    return "\n".join(lines)
