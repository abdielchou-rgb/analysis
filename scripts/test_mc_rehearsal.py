"""Run MC significance test on resolved data."""

import sys
sys.path.insert(0, ".")

import json
from core.significance import monte_carlo_direction_significance, monte_carlo_alpha_significance


def main():
    with open("core/data/forward_picks/track_record.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    preds = data["predictions"]
    valid = [p for p in preds if p.get("outcome") in ("hit", "miss")]
    print(f"Valid outcomes: {len(valid)}")
    for v in valid:
        print(f"  {v['asset']}: {v['outcome']} ({v.get('outcome_detail', '')})")

    # Run MC
    result = monte_carlo_direction_significance(valid, n_simulations=10000)
    print(f"\nMC Direction Test (N=10000):")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
