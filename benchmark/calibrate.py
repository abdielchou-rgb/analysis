#!/usr/bin/env python3
"""Calibrate IronGate thresholds from report samples

P2-2 (2026-09-01): \u6821\u51c6\u95ed\u73af\u52a0\u56fa\u2014\u2014
1. \u6837\u672c\u6e90\u4ece output/\u81ea\u4ea7\u62a5\u544a + benchmark/reports \u6539\u4e3a benchmark/golden/ \u5206\u7c7b\u5b50\u76ee\u5f55
   \uff08\u771f\u5b9e\u5916\u90e8\u673a\u6784\u62a5\u544a\uff1a\u5238\u5546\u7814\u62a5/\u54a8\u8be2\u62a5\u544a/\u5e74\u62a5\uff09\uff0c\u6253\u7834"\u7528\u81ea\u4ea7\u62a5\u544a\u6821\u51c6\u81ea\u5df1\u95e8\u69db"\u7684\u81ea\u8bc1\u5faa\u73af
2. \u8f93\u51fa P10/P25/P50 \u5206\u4f4d\uff0c\u4f9b\u9608\u503c\u51b3\u7b56\uff08\u4e0d\u53ea P20\uff09
3. \u660e\u786e\u6392\u9664 output/ \u81ea\u4ea7\u5931\u8d25\u4ea7\u7269
"""

import os, sys, json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# P2-2\uff1agolden \u8bed\u6599\u5e93\u5206\u7c7b\u76ee\u5f55\uff08\u5916\u90e8\u771f\u5b9e\u62a5\u544a\uff0c\u975e\u81ea\u4ea7\uff09
GOLDEN_SUBS = [
    "benchmark/golden/industry_deep",
    "benchmark/golden/earnings_notes",
    "benchmark/golden/listed_company",
    "benchmark/golden/decision_memo",
    "benchmark/golden/reports",
]


def collect_samples():
    """\u4ece golden \u5916\u90e8\u8bed\u6599\u6536\u96c6\u6837\u672c\uff08\u6392\u9664 output \u81ea\u4ea7\u62a5\u544a\u2014\u2014P2-2 \u7834\u81ea\u8bc1\u5faa\u73af\uff09\u3002"""
    samples = []
    for sub in GOLDEN_SUBS:
        d = _ROOT / sub
        if d.is_dir():
            for f in sorted(d.glob("*.md"), key=os.path.getmtime, reverse=True)[:20]:
                if os.path.getsize(f) > 1000:
                    samples.append(f)
    # \u515c\u5e95\uff1agolden \u76ee\u5f55\u4e0b\u4efb\u610f md\uff08\u5916\u90e8\u8f6c\u7801\u7814\u62a5\uff09
    if not samples:
        d = _ROOT / "benchmark" / "golden"
        if d.is_dir():
            for f in sorted(d.glob("*/*.md"), key=os.path.getmtime, reverse=True)[:30]:
                if os.path.getsize(f) > 1000:
                    samples.append(f)
    return samples


def _percentile(scores: list, p: float) -> float:
    """p \u5206\u4f4d\uff080-1\uff09\u3002"""
    if not scores:
        return 0.0
    s = sorted(scores)
    idx = min(len(s) - 1, int(len(s) * p))
    return s[idx]


def calibrate():
    from pipeline.iron_gate import IronGate

    samples = collect_samples()
    if not samples:
        print("No golden samples found. Place some in benchmark/golden/")
        return
    print("Calibrating with " + str(len(samples)) + " golden samples (external reports)...")
    all_scores = {}
    for fp in samples:
        try:
            with open(fp, encoding="utf-8") as f:
                text = f.read()
            # P2-2：外部研报常超 50KB，Gate 全量跑超时——校准只需代表性片段，
            # 截断到 12000 字符（覆盖判断密度/数据密度/结构核心区域）
            if len(text) > 12000:
                text = text[:12000]
            rtype = "listed_company"
            if "\u884c\u4e1a" in text[:500]:
                rtype = "industry_deep"
            elif "\u51b3\u7b56" in text[:500]:
                rtype = "decision_memo"
            ig = IronGate.from_text(text, rtype, "cicc")
            result = ig.run_all()
            for chk in result.checks:
                all_scores.setdefault(chk.name, []).append(chk.score)
        except Exception as e:
            print("  Skip " + fp.name + ": " + str(e))
    if not all_scores:
        print("No scores collected.")
        return
    thresholds = {}
    defaults = {"sac_coverage": 0.7, "data_traceability": 0.5, "content_volume": 0.6}
    print(f"\n{'check'.ljust(32)} {'n':>4} {'P10':>6} {'P25':>6} {'P50':>6} {'default':>8}  flag")
    for name in sorted(all_scores.keys()):
        scores = sorted(all_scores[name])
        if len(scores) < 3:
            continue
        p10 = _percentile(scores, 0.10)
        p25 = _percentile(scores, 0.25)
        p50 = _percentile(scores, 0.50)
        # \u9608\u503c\u53d6 P25\uff08\u5916\u90e8\u62a5\u544a 75% \u80fd\u8fc7\uff0c25% \u662f\u4f4e\u5206\u6837\u672c\u7684\u4fdd\u5b88\u7ebf\uff09\u2014\u2014\u6bd4\u65e7 P20 \u7565\u4fdd\u5b88
        thresholds[name] = round(max(0.3, min(p25, 0.95)), 2)
        dflt = defaults.get(name, 0.6)
        flag = " *" if abs(p25 - dflt) > 0.15 else ""
        print(
            f"  {name.ljust(30)} {len(scores):>4} {p10:>6.2f} {p25:>6.2f} {p50:>6.2f} {dflt:>8.2f}{flag}"
        )
    out = _ROOT / "benchmark" / "calibrated_thresholds.json"
    with open(out, "w") as f:
        json.dump(thresholds, f, indent=2, ensure_ascii=False)
    print("\nWritten: benchmark/calibrated_thresholds.json (" + str(len(thresholds)) + " dims)")


if __name__ == "__main__":
    calibrate()
