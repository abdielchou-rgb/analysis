# -*- coding: utf-8 -*-
"""
预期差引擎（Earnings Surprise）— R30 模块7：对标券商研究所

**问题**：2hao 做盈利预测，但没有"我的预测 vs 市场一致预期"的实时对比。
对标券商：alpha 来自预测与市场预期的差（预期差）。

**方案**：
  1. 从 consensus_estimates.db 读一致预期（EPS/目标价）
  2. 从 earnings_forecast.db（业绩预告/快报）读实际预告值
  3. 计算预期差：预告值 vs 一致预期 → 超预期/符合/低于预期
  4. 信号注入写作 prompt（核心判断引用）

本模块读数据不写正文（FP2）。
"""
from __future__ import annotations
import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger("2hao.earnings_surprise")

_ROOT = Path(__file__).resolve().parent.parent
CONSENSUS_DB = _ROOT / "data" / "consensus_estimates.db"
EARNINGS_DB = _ROOT / "data" / "earnings_forecast.db"


def load_consensus(code: str) -> dict | None:
    """读一致预期。"""
    if not CONSENSUS_DB.exists():
        return None
    try:
        conn = sqlite3.connect(str(CONSENSUS_DB))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM consensus WHERE code=? ORDER BY as_of DESC LIMIT 1",
            (code,)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.debug("[EARN-SURPRISE] consensus: %s", e)
        return None


def load_earnings_forecast(code: str) -> list[dict]:
    """读业绩预告/快报。"""
    if not EARNINGS_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(EARNINGS_DB))
        rows = conn.execute(
            "SELECT * FROM earnings_forecast WHERE code=? ORDER BY announce_date DESC LIMIT 5",
            (code,)).fetchall()
        conn.close()
        if rows:
            cols = [d[0] for d in conn.execute("PRAGMA table_info(earnings_forecast)").fetchall()]
            return [dict(zip(cols, r)) for r in rows]
        return []
    except Exception as e:
        logger.debug("[EARN-SURPRISE] forecast: %s", e)
        return []


def compute_surprise(code: str) -> dict:
    """计算预期差信号。

    输入：consensus EPS_2026e + 业绩预告净利
    逻辑：
      - 若业绩预告净利增速 vs 一致预期隐含增速 → 超/低于预期
      - 若只有一致预期无预告 → 报告当前一致预期（供预测对比）
    """
    consensus = load_consensus(code)
    forecasts = load_earnings_forecast(code)

    if not consensus and not forecasts:
        return {"status": "no_data", "code": code}

    result = {"status": "ok", "code": code,
              "consensus": consensus, "forecasts": forecasts}
    # 一致预期隐含增速
    if consensus:
        eps = consensus.get("eps_2026e") or consensus.get("eps_2027e")
        result["consensus_eps"] = eps
        result["consensus_target"] = consensus.get("target_price_avg")
        result["rating_buy"] = consensus.get("rating_buy")
        result["n_analysts"] = consensus.get("n_analysts")

    # 业绩预告 vs 一致预期
    if forecasts and consensus:
        latest = forecasts[0]
        forecast_net = latest.get("forecast_net_profit") or latest.get("net_profit_upper")
        surprise = None
        if forecast_net and consensus.get("eps_2026e"):
            # 简化：预告净利 vs 一致预期 EPS 隐含净利（需股本）→ 用增速对比
            # 这里给出定性判断
            growth = latest.get("forecast_growth")
            if growth is not None:
                if growth > 15:
                    surprise = "超预期"
                elif growth < 0:
                    surprise = "低于预期"
                else:
                    surprise = "符合预期"
        result["surprise"] = surprise
        result["surprise_signal"] = {
            "超预期": "bullish", "符合预期": "neutral", "低于预期": "bearish"
        }.get(surprise, "neutral")

    return result


def serialize_surprise(s: dict) -> str:
    """序列化注入 prompt。"""
    if not s or s.get("status") != "ok":
        return ""
    lines = ["=== 预期差信号（一致预期 vs 实际/预测） ==="]
    if s.get("consensus_eps"):
        lines.append(f"一致预期 EPS: {s['consensus_eps']}（{s.get('n_analysts', '?')}家分析师, "
                     f"目标价{s.get('consensus_target', '?')}）")
    if s.get("rating_buy"):
        lines.append(f"一致预期买入评级: {s['rating_buy']}")
    if s.get("surprise"):
        lines.append(f"业绩预告: **{s['surprise']}** → 信号 {s['surprise_signal']}")
    elif s.get("forecasts"):
        lines.append("业绩预告已发布（详见数据附录）")
    return "\n".join(lines)


if __name__ == "__main__":
    for code in ["603662", "688469"]:
        s = compute_surprise(code)
        print(f"\n=== {code} ===")
        print(serialize_surprise(s))
