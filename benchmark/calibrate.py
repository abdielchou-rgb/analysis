#!/usr/bin/env python3
"""Calibrate IronGate thresholds from report samples"""
import os, sys, json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

def collect_samples():
    samples = []
    for sub in ["benchmark/reports", "output", "outputs"]:
        d = _ROOT / sub
        if d.is_dir():
            for f in sorted(d.glob("*.md"), key=os.path.getmtime, reverse=True)[:10]:
                if os.path.getsize(f) > 1000:
                    samples.append(f)
    return samples

def calibrate():
    from pipeline.iron_gate import IronGate
    samples = collect_samples()
    if not samples:
        print("No .md samples found. Place some in benchmark/reports/")
        return
    print("Calibrating with " + str(len(samples)) + " samples...")
    all_scores = {}
    for fp in samples:
        try:
            with open(fp, encoding='utf-8') as f:
                text = f.read()
            rtype = "listed_company"
            if "\u884c\u4e1a" in text[:500]:
                rtype = "industry_deep"
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
    for name in sorted(all_scores.keys()):
        scores = sorted(all_scores[name])
        p20 = scores[len(scores)//5] if len(scores)>=5 else scores[0]
        thresholds[name] = round(max(0.3, min(p20, 0.95)), 2)
        dflt = defaults.get(name, 0.6)
        flag = " *" if abs(p20-dflt) > 0.15 else ""
        print("  " + name.ljust(30) + " " + str(len(scores)).rjust(4) + " samples  P20=" + "{:.2f}".format(p20) + "  default=" + "{:.2f}".format(dflt) + flag)
    out = _ROOT / "benchmark" / "calibrated_thresholds.json"
    with open(out, 'w') as f:
        json.dump(thresholds, f, indent=2, ensure_ascii=False)
    print("\nWritten: benchmark/calibrated_thresholds.json (" + str(len(thresholds)) + " dims)")

if __name__ == "__main__":
    calibrate()
