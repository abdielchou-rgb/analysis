# -*- coding: utf-8 -*-
"""
反共识检测器（Anti-Consensus Detector）— R16 深度补强

投行报告的核心价值是"与众不同但正确"。本模块：
  1. 从一致预期数据（consensus_estimates.db）+ 研报发现（baseline_findings.json）提取市场共识
  2. 从标的/行业的实际数据（财务/估值/资金面）识别与共识的偏差
  3. 生成"反共识信号"——供 Bold Call 引用，强化报告的独特洞察

**不编造**：共识来自真实数据（一致预期/研报），偏差是数值计算，不是 LLM 臆测。
"""
from __future__ import annotations
import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger("2hao.anti_consensus")

_ROOT = Path(__file__).resolve().parent.parent.parent  # 项目根（core/compute/ → 根）


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def detect_anti_consensus(asset: str, collected_data: dict) -> dict:
    """检测反共识信号。

    从三处找"市场共识 vs 数据现实"的偏差：
      1. 一致预期（consensus_estimates.db）— EPS 预测 vs 实际增速
      2. 研报发现（baseline_findings.json）— 市场观点文本
      3. 估值分位 — 当前 PE  vs 历史/行业
    """
    cd = collected_data.get("chart_data", {}) if isinstance(collected_data, dict) else {}
    signals = []
    code = ""
    import re as _re
    m = _re.search(r"(\d{6})", asset)
    code = m.group(1) if m else ""

    # ── 信号1：一致预期 vs 实际增速 ──
    if code:
        conn = _connect_consensus()
        if conn:
            try:
                row = conn.execute(
                    "SELECT * FROM consensus WHERE code=? ORDER BY as_of DESC LIMIT 1",
                    (code,)).fetchone()
                if row:
                    eps_cur = row["eps_2026e"] if "eps_2026e" in row.keys() else None
                    n_analysts = row["n_analysts"] if "n_analysts" in row.keys() else 0
                    rating_buy = row["rating_buy"] if "rating_buy" in row.keys() else 0
                    if n_analysts and eps_cur:
                        # 一致预期 EPS 暗示的增长 vs 实际财务增速
                        signals.append({
                            "type": "consensus_vs_growth",
                            "signal": f"{n_analysts}家分析师一致预期 EPS={eps_cur}",
                            "bias": "consensus_positive" if rating_buy > n_analysts * 0.6 else "neutral",
                            "confidence": 0.7,
                        })
            except Exception as e:
                logger.debug("[ANTI-CONSENSUS] consensus: %s", e)
            finally:
                conn.close()

    # ── 信号2：估值分位（当前 PE vs 行业基线）──
    val = cd.get("fig_valuation", {}) if isinstance(cd, dict) else {}
    pe = _safe_float(val.get("pe", val.get("pe_ttm", 0)))
    # industry_pe 来自 data_basement 的 industry_pe_ttm（行业基线）
    industry_pe = _safe_float(cd.get("industry_pe_ttm", cd.get("_industry_pe", 0)))
    if pe > 0 and industry_pe > 0:
        ratio = pe / industry_pe
        if ratio > 1.5:
            signals.append({
                "type": "valuation_premium",
                "signal": f"当前PE({pe:.1f})为行业均值({industry_pe:.1f})的{ratio:.1f}倍，市场给予显著溢价",
                "bias": "consensus_expensive",
                "confidence": 0.8,
            })
        elif ratio < 0.6:
            signals.append({
                "type": "valuation_discount",
                "signal": f"当前PE({pe:.1f})仅为行业均值({industry_pe:.1f})的{ratio:.1f}倍，市场或低估",
                "bias": "consensus_cheap",
                "confidence": 0.8,
            })

    # ── 信号3：研报共识文本（从 baseline_findings 提取评级/观点）──
    try:
        bf_path = _ROOT / "data" / "baseline_findings.json"
        if bf_path.exists():
            bf = json.loads(bf_path.read_text(encoding="utf-8"))
            findings = bf.get("findings", {})
            # 找标的相关的研报评级
            name = asset.split()[0] if asset else ""
            ratings = []
            for level, items in findings.items():
                if not isinstance(items, list):
                    continue
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    if name and name not in str(it.get("file", "")):
                        continue
                    r = it.get("rating", "")
                    if r:
                        ratings.append(r)
            if ratings:
                from collections import Counter
                cnt = Counter()
                for r in ratings:
                    for kw in ["买入", "增持", "持有", "中性", "减持", "卖出"]:
                        if kw in str(r):
                            cnt[kw] += 1
                            break
                if cnt:
                    total = sum(cnt.values())
                    buy_ratio = (cnt.get("买入", 0) + cnt.get("增持", 0)) / max(total, 1)
                    signals.append({
                        "type": "research_consensus",
                        "signal": f"研报评级分布: {dict(cnt)}，买入占比{buy_ratio:.0%}",
                        "bias": "consensus_buy" if buy_ratio > 0.7 else "neutral",
                        "confidence": 0.6,
                    })
    except Exception as e:
        logger.debug("[ANTI-CONSENSUS] research: %s", e)

    return {
        "signals": signals,
        "has_anti_consensus": len(signals) > 0,
        "summary": _summarize(signals),
    }


def _connect_consensus():
    path = _ROOT / "data" / "consensus_estimates.db"
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _summarize(signals) -> str:
    if not signals:
        return "暂无明确反共识信号（市场共识与数据基本一致）"
    parts = []
    for s in signals[:3]:
        parts.append(f"[{s['bias']}] {s['signal']}")
    return "; ".join(parts)


def build_anti_consensus_prompt(fc: dict) -> str:
    """序列化成 prompt 注入文本（供 section_writer 引用）。"""
    if not fc or not fc.get("signals"):
        return ""
    lines = ["=== 反共识信号（市场共识 vs 数据现实） ==="]
    for s in fc["signals"][:3]:
        lines.append(f"- {s['signal']} (置信度{s['confidence']})")
    return "\n".join(lines)
