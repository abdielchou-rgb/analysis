"""M1-W1: Prediction Judge — alpha-based outcome determination.

Replaces absolute direction judge with alpha-based judge:
- With benchmark: hit = alpha > +2%, miss = alpha < -2%, partial otherwise
- Without benchmark: direction-based (degraded, bench=none)
- With target_price: target-touching judge (strictest)

judge_ver tracks which version of the judge was used.
"""

import logging
from typing import Optional

logger = logging.getLogger("2hao.prediction_judge")

# Judge version
JUDGE_VER = 2  # v1=absolute direction, v2=alpha-based

# Alpha thresholds
ALPHA_HIT_THRESHOLD = 0.02   # +2% alpha → hit
ALPHA_MISS_THRESHOLD = -0.02  # -2% alpha → miss


def judge_outcome(
    actual_return: float,
    direction: str,
    bench_return: Optional[float] = None,
    target_price: Optional[float] = None,
    price_at_expiry: Optional[float] = None,
) -> dict:
    """Judge prediction outcome based on alpha or direction.

    Args:
        actual_return: Actual return of the asset (e.g., 0.10 for +10%)
        direction: Prediction direction (bullish/bearish/neutral)
        bench_return: Benchmark return (e.g., market return). If None, degraded to direction judge.
        target_price: Target price (if available). Used for strictest judge.
        price_at_expiry: Actual price at expiry (if target_price provided).

    Returns:
        {outcome, judge_ver, detail, bench, alpha}
    """
    result = {
        "judge_ver": JUDGE_VER,
        "bench": "none" if bench_return is None else "provided",
    }

    # Determine alpha
    if bench_return is not None:
        alpha = actual_return - bench_return
        result["alpha"] = round(alpha, 4)
    else:
        alpha = None
        result["alpha"] = None

    # Determine outcome
    if direction == "neutral":
        result["outcome"] = "partial"
        result["detail"] = f"neutral_direction: return={actual_return:.2%}"
        return result

    # Target price judge (strictest)
    if target_price is not None and price_at_expiry is not None:
        target_hit = False
        if direction == "bullish" and price_at_expiry >= target_price:
            target_hit = True
        elif direction == "bearish" and price_at_expiry <= target_price:
            target_hit = True

        if target_hit:
            result["outcome"] = "hit"
            result["detail"] = f"target_hit: target={target_price}, actual={price_at_expiry:.2f}"
            return result

    # Alpha-based judge (when benchmark available)
    if alpha is not None:
        # For bearish predictions, invert alpha interpretation:
        # Bearish + negative alpha = we predicted drop, market dropped more = good
        effective_alpha = alpha if direction == "bullish" else -alpha

        if effective_alpha > ALPHA_HIT_THRESHOLD:
            result["outcome"] = "hit"
            result["detail"] = f"alpha={alpha:.2%} (dir={direction}), effective={effective_alpha:.2%} > {ALPHA_HIT_THRESHOLD:.0%}"
        elif effective_alpha < ALPHA_MISS_THRESHOLD:
            result["outcome"] = "miss"
            result["detail"] = f"alpha={alpha:.2%} (dir={direction}), effective={effective_alpha:.2%} < {ALPHA_MISS_THRESHOLD:.0%}"
        else:
            result["outcome"] = "partial"
            result["detail"] = f"alpha={alpha:.2%} (dir={direction}), effective={effective_alpha:.2%} in [{ALPHA_MISS_THRESHOLD:.0%}, {ALPHA_HIT_THRESHOLD:.0%}]"
        return result

    # Direction-based judge (degraded, no benchmark)
    # M1-W1: degraded judge must be explicitly marked
    if direction == "bullish":
        if actual_return > 0:
            result["outcome"] = "hit"
            result["detail"] = f"direction_hit(degraded): bullish + return={actual_return:.2%}, bench=none"
        else:
            result["outcome"] = "miss"
            result["detail"] = f"direction_miss(degraded): bullish + return={actual_return:.2%}, bench=none"
    elif direction == "bearish":
        if actual_return < 0:
            result["outcome"] = "hit"
            result["detail"] = f"direction_hit(degraded): bearish + return={actual_return:.2%}, bench=none"
        else:
            result["outcome"] = "miss"
            result["detail"] = f"direction_miss(degraded): bearish + return={actual_return:.2%}, bench=none"
    else:
        result["outcome"] = "partial"
        result["detail"] = f"unknown_direction: {direction}, return={actual_return:.2%}"

    return result
