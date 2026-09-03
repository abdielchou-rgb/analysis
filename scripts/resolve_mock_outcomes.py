"""Resolve mock predictions with mock prices for P0-6 rehearsal.

Since akshare is rate-limited, use realistic mock prices to prove the pipeline.
"""

import sys
sys.path.insert(0, ".")

import json
from pathlib import Path

TRACK_RECORD = "core/data/forward_picks/track_record.json"

# Realistic mock prices (based on actual market data ranges)
MOCK_PRICES = {
    "300750": {"make": 220.0, "expiry": 265.0},   # 宁德时代: +20% → bullish correct
    "600519": {"make": 1650.0, "expiry": 1580.0},  # 贵州茅台: -4% → bullish incorrect
    "002594": {"make": 280.0, "expiry": 310.0},    # 比亚迪: +11% → bullish correct
    "688981": {"make": 85.0, "expiry": 72.0},      # 中芯国际: -15% → bearish correct
    "603259": {"make": 105.0, "expiry": 125.0},    # 药明康德: +19% → bullish correct
}


def main():
    with open(TRACK_RECORD, "r", encoding="utf-8") as f:
        data = json.load(f)

    preds = data["predictions"]
    resolved = 0

    for p in preds:
        if p["id"].startswith("mock_") and p["outcome"] in ("pending", "unverifiable"):
            asset = p["asset"]
            direction = p["direction"]

            if asset not in MOCK_PRICES:
                p["outcome"] = "unverifiable"
                p["outcome_detail"] = "no_mock_price"
                resolved += 1
                continue

            prices = MOCK_PRICES[asset]
            p_make = prices["make"]
            p_exp = prices["expiry"]
            change = (p_exp - p_make) / p_make

            if direction == "bullish":
                p["outcome"] = "correct" if change > 0 else "incorrect"
            elif direction == "bearish":
                p["outcome"] = "correct" if change < 0 else "incorrect"
            else:
                p["outcome"] = "unverifiable"

            p["outcome_detail"] = f"mock:make={p_make:.2f},expiry={p_exp:.2f},change={change:.2%}"
            p["price_at_make"] = p_make
            p["price_at_expiry"] = p_exp
            resolved += 1
            print(f"{asset}: {p['outcome']} (make={p_make:.2f}, exp={p_exp:.2f}, change={change:.2%})")

    with open(TRACK_RECORD, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nResolved {resolved} mock predictions")

    # Summary
    outcomes = {}
    for p in preds:
        o = p.get("outcome", "none")
        outcomes[o] = outcomes.get(o, 0) + 1
    print("Outcome distribution:", outcomes)


if __name__ == "__main__":
    main()
