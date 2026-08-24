#!/usr/bin/env python3
# Roundtable Improvement Loop - v2.0
# Orchestrates: score -> analyze -> improve -> re-score -> gate

import json, sys, os, subprocess
from pathlib import Path

BASE = Path("D:/2hao-analyst/data/基线/回测基线库")
RUNNER = BASE / "backtest_runner.py"
LOG = BASE / "loop_score_log.json"
MAX = 3
PASS = 85
DIM = 0.70
CRIT = ["B_data", "C_chart", "G_turing"]


def load_log():
    if LOG.exists():
        try:
            return json.loads(LOG.read_text("utf-8"))
        except Exception:
            pass  # Layer 5: bare except replaced with Exception
    return {"rounds": [], "current": 0, "status": "init"}


def save_log(log):
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), "utf-8")


def score_file(path, rtype="industry", tier="S"):
    r = subprocess.run(
        [sys.executable, str(RUNNER), "--report", str(path), "--type", rtype, "--tier", tier],
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"error": r.stderr or r.stdout, "verdict": "ERROR"}


def check_gate(res):
    if res.get("verdict") == "ERROR":
        return False, "Scoring error"
    total = res.get("total", 0)
    dims = res.get("dimension_rates", {})
    ok70 = all(v >= DIM for v in dims.values())
    crit_ok = all(dims.get(d, 0) >= DIM for d in CRIT)
    if total >= PASS and ok70:
        return True, f"PASS total={total}"
    elif total >= 75 and crit_ok:
        return False, f"CONDITIONAL total={total}, crit={crit_ok}"
    else:
        return False, f"FAIL total={total}, crit={crit_ok}"


def main():
    print("=" * 60)
    print("2hao - Roundtable Improvement Loop")
    print("=" * 60)
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True)
    p.add_argument("--type", default="industry")
    p.add_argument("--tier", default="S")
    p.add_argument("--max-rounds", type=int, default=MAX)
    args = p.parse_args()
    target = Path(args.target)
    if not target.exists():
        print(f"Error: {target} not found")
        sys.exit(1)
    log = load_log()
    for r in range(log["current"] + 1, log["current"] + args.max_rounds + 1):
        print(f"\n=== Round {r} ===")
        res = score_file(str(target), args.type, args.tier)
        if "error" in res:
            print(f"ERROR: {res.get('error')}")
            log["rounds"].append({"round": r, "error": str(res.get("error"))})
            break
        print(f"Score: {res.get('total', '?')} | {res.get('verdict', '?')}")
        print(f"Dims: {res.get('dimension_rates', {})}")
        print(f"Gaps: {res.get('gaps', [])}")
        passed, msg = check_gate(res)
        log["rounds"].append(
            {
                "round": r,
                "total": res.get("total"),
                "verdict": res.get("verdict"),
                "dims": res.get("dimension_rates"),
                "gaps": res.get("gaps"),
                "plan": res.get("improvement_plan"),
                "gate": msg,
                "passed": passed,
            }
        )
        log["current"] = r
        log["status"] = "PASSED" if passed else "IN_PROGRESS"
        save_log(log)
        if passed:
            print(f"\nPASSED! Final score: {res.get('total')}")
            return
        if res.get("improvement_plan"):
            print("\nImprovements needed:")
            for i, imp in enumerate(res["improvement_plan"], 1):
                print(f"  {i}. {imp}")
        else:
            g = res.get("gaps", [])
            if g:
                print("\nGaps to fix:")
            for i, x in enumerate(g, 1):
                print(f"  {i}. {x}")
        if r < log["current"] + args.max_rounds:
            print("\nNext round will re-score after fixes.")
    log["status"] = "MAX_REACHED"
    save_log(log)
    print(f"\nDone. Final: {res.get('verdict', '?')}")


if __name__ == "__main__":
    main()
