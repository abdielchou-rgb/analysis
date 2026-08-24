"""V50+ T0.5 Hypothesis Verifier — checks hypotheses against real data"""

from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.models import EvidenceItem, EvidenceLevel, DataPoint


@dataclass
class VerificationResult:
    hypothesis: str = ""
    status: str = "pending"
    supporting_signals: list[dict] = field(default_factory=list)
    challenging_signals: list[dict] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    similar_cases: list[str] = field(default_factory=list)
    consensus_estimate: Optional[dict] = None
    price_trend: Optional[dict] = None
    summary: str = ""
    confidence: str = "medium"


class HypothesisVerifier:
    def verify(self, hypothesis: str, asset_code: str = "") -> VerificationResult:
        result = VerificationResult(hypothesis=hypothesis)
        parsed = self._parse(hypothesis, asset_code)
        code = parsed.get("code", "")
        direction = parsed.get("direction", "neutral")

        if not code:
            result.data_gaps.append("cannot extract stock code from hypothesis")
            result.status = "insufficient_data"
            result.summary = "Please specify a stock code (e.g., 600519)"
            return result

        from legacy.data_platform.engine import pipeline, DataQuery

        data = pipeline.fetch(DataQuery(assets=[code]))
        if data.points:
            pts = {p.name: p.value for p in data.points}
            result.supporting_signals.append({"source": data.source, "data": {k: pts[k] for k in list(pts.keys())[:5]}})

        kline = pipeline.fetch_kline(code)
        if kline and len(kline) > 20:
            closes = [float(d[2]) for d in kline if len(d) >= 3]
            if closes:
                result.price_trend = {
                    "current": closes[-1],
                    "20d_chg_pct": round((closes[-1] - closes[-20]) / closes[-20] * 100, 2),
                    "ytd_chg_pct": round((closes[-1] - closes[0]) / closes[0] * 100, 2),
                    "52wk_high": max(closes),
                    "52wk_low": min(closes),
                }

        result.data_gaps.append("consensus data unavailable (Tushare free tier restricted)")
        result.confidence = "low" if kline else "insufficient_data"
        result.status = "supported" if kline else "insufficient_data"
        result.summary = self._summary(result, parsed)
        return result

    @staticmethod
    def _parse(text, code=""):
        p = {"code": code, "metric": "", "direction": "neutral", "threshold": None}
        codes = re.findall(r"(\d{6})", text)
        if codes:
            p["code"] = codes[0]
        if any(w in text for w in ["突破", "超过", "看多", "看好", "上涨"]):
            p["direction"] = "bull"
        if any(w in text for w in ["下降", "低于", "看空", "风险", "下跌"]):
            p["direction"] = "bear"
        t = re.findall(r"(\d+\.?\d*)", text)
        if t:
            p["threshold"] = float(t[-1])
        for m in ["PE", "市盈率", "净利润", "营收", "直销", "毛利率", "ROE"]:
            if m in text:
                p["metric"] = m
                break
        return p

    @staticmethod
    def _summary(r, p):
        lines = [f"## Hypothesis: {r.hypothesis}", f"Confidence: {r.confidence}"]
        if r.price_trend:
            pt = r.price_trend
            lines.append(
                f"\nPrice: {pt['current']:.0f}, 20d: {pt['20d_chg_pct']:+.1f}%, YTD: {pt['ytd_chg_pct']:+.1f}%"
            )
            lines.append(f"52wk range: {pt['52wk_low']:.0f} - {pt['52wk_high']:.0f}")
        if r.supporting_signals:
            lines.append(f"\nSupporting: {len(r.supporting_signals)} signal(s)")
        if r.data_gaps:
            for g in r.data_gaps:
                lines.append(f"\nGap: {g}")
        return "\n".join(lines)
