"""Live-forward outcome update script.

Checks expired predictions against live market data and updates outcomes.
Run periodically (e.g., daily) to resolve predictions that have reached
their time horizon.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("2hao.outcome_update")


def load_track_record(path: str = "core/data/forward_picks/track_record.json") -> dict:
    """Load track record from disk."""
    p = Path(path)
    if not p.exists():
        return {"predictions": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_track_record(data: dict, path: str = "core/data/forward_picks/track_record.json"):
    """Save track record to disk."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_horizon(horizon: str) -> int:
    """Parse time horizon string to days.

    '6m' → 180, '12m' → 360, '1y' → 365
    """
    if horizon.endswith("m"):
        return int(horizon[:-1]) * 30
    elif horizon.endswith("y"):
        return int(horizon[:-1]) * 365
    return 180  # default 6m


def check_expired(
    predictions: list[dict],
    as_of_date: str = None,
) -> list[dict]:
    """Find predictions that have expired but are still pending.

    Args:
        predictions: List of prediction dicts
        as_of_date: ISO date to check against (default: today)

    Returns:
        List of expired predictions with computed expiry_date
    """
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    expired = []
    for p in predictions:
        if p.get("outcome") != "pending":
            continue

        made_date = p.get("made_date", "")
        horizon = p.get("time_horizon", "6m")

        if not made_date:
            continue

        try:
            made_dt = datetime.fromisoformat(made_date.replace("Z", "+00:00"))
            days = parse_horizon(horizon)
            expiry_dt = made_dt + __import__("datetime").timedelta(days=days)
            expiry_date = expiry_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue

        if expiry_date <= as_of_date:
            p["expiry_date"] = expiry_date
            expired.append(p)

    return expired


def resolve_outcome(
    prediction: dict,
    get_price_func=None,
) -> dict:
    """Resolve a prediction's outcome based on price data.

    Args:
        prediction: The prediction dict
        get_price_func: Callable(asset, date) → price. If None, returns placeholder.

    Returns:
        Updated prediction with outcome set
    """
    asset = prediction.get("asset", "")
    direction = prediction.get("direction", "")
    made_date = prediction.get("made_date", "")
    expiry_date = prediction.get("expiry_date", "")

    if not get_price_func:
        # Placeholder: mark as needing manual review
        prediction["outcome"] = "pending_review"
        prediction["outcome_reason"] = "no_price_function_available"
        return prediction

    try:
        price_at_make = get_price_func(asset, made_date)
        price_at_expiry = get_price_func(asset, expiry_date)

        if price_at_make is None or price_at_expiry is None:
            prediction["outcome"] = "pending_review"
            prediction["outcome_reason"] = "missing_price_data"
            return prediction

        # Determine if direction was correct
        price_change = (price_at_expiry - price_at_make) / price_at_make

        if direction == "bullish":
            prediction["outcome"] = "correct" if price_change > 0 else "incorrect"
        elif direction == "bearish":
            prediction["outcome"] = "correct" if price_change < 0 else "incorrect"
        else:
            prediction["outcome"] = "pending_review"
            prediction["outcome_reason"] = f"unknown_direction: {direction}"

        prediction["return_pct"] = round(price_change * 100, 2)
        prediction["price_at_make"] = price_at_make
        prediction["price_at_expiry"] = price_at_expiry
        prediction["resolved_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        prediction["outcome"] = "pending_review"
        prediction["outcome_reason"] = f"error: {str(e)[:200]}"

    return prediction


def run_outcome_update(
    track_record_path: str = "core/data/forward_picks/track_record.json",
    get_price_func=None,
    dry_run: bool = False,
) -> dict:
    """Run outcome update on all expired predictions.

    Args:
        track_record_path: Path to track record JSON
        get_price_func: Callable(asset, date) → price
        dry_run: If True, don't write changes

    Returns:
        {updated, pending_review, already_resolved, errors}
    """
    data = load_track_record(track_record_path)
    predictions = data.get("predictions", [])

    expired = check_expired(predictions)
    stats = {
        "total": len(predictions),
        "expired": len(expired),
        "updated": 0,
        "pending_review": 0,
        "already_resolved": 0,
        "errors": 0,
    }

    for p in expired:
        try:
            p = resolve_outcome(p, get_price_func)
            if p.get("outcome") == "correct" or p.get("outcome") == "incorrect":
                stats["updated"] += 1
            elif p.get("outcome") == "pending_review":
                stats["pending_review"] += 1
        except Exception as e:
            stats["errors"] += 1
            logger.error("[OUTCOME] Error resolving %s: %s", p.get("asset", "?"), str(e))

    if not dry_run and (stats["updated"] > 0 or stats["pending_review"] > 0):
        save_track_record(data, track_record_path)
        logger.info("[OUTCOME] Track record updated: %d resolved, %d pending review",
                     stats["updated"], stats["pending_review"])
    else:
        logger.info("[OUTCOME] Dry run: %d would be updated, %d pending review",
                     stats["updated"], stats["pending_review"])

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update prediction outcomes")
    parser.add_argument("--track-record", default="core/data/forward_picks/track_record.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--as-of", default=None, help="ISO date to check against")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    stats = run_outcome_update(
        track_record_path=args.track_record,
        dry_run=args.dry_run,
    )

    print(json.dumps(stats, indent=2))
