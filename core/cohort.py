"""C4: Live-forward cohort management.

Predictions are frozen at made_date (no look-ahead).
Outcomes are checked at expiry using live data.
Asset pool and benchmark cohort are fixed to prevent survivorship bias.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("2hao.cohort")


class LiveForwardCohort:
    """Manages live-forward prediction cohorts."""

    def __init__(self, track_record_path: str = "core/data/forward_picks/track_record.json"):
        self.track_record_path = Path(track_record_path)

    def load_predictions(self) -> list[dict]:
        if not self.track_record_path.exists():
            return []
        with open(self.track_record_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("predictions", [])

    def get_cohort(
        self,
        made_after: str = None,
        made_before: str = None,
        time_horizon: str = None,
        direction: str = None,
        asset: str = None,
    ) -> list[dict]:
        """Get a specific cohort of predictions.

        Args:
            made_after: ISO date — only predictions made after this date
            made_before: ISO date — only predictions made before this date
            time_horizon: Filter by time_horizon (e.g., "6m", "12m")
            direction: Filter by direction (bullish/bearish)
            asset: Filter by asset name

        Returns:
            List of predictions matching the cohort criteria
        """
        predictions = self.load_predictions()
        cohort = []

        for p in predictions:
            made_date = p.get("made_date", "")

            if made_after and made_date < made_after:
                continue
            if made_before and made_date > made_before:
                continue
            if time_horizon and p.get("time_horizon") != time_horizon:
                continue
            if direction and p.get("direction") != direction:
                continue
            if asset and p.get("asset") != asset:
                continue

            cohort.append(p)

        logger.info("[COHORT] Filtered %d predictions (made_after=%s, made_before=%s, horizon=%s)",
                     len(cohort), made_after, made_before, time_horizon)
        return cohort

    def get_expired_predictions(self, as_of_date: str = None) -> list[dict]:
        """Get predictions that have expired (time_horizon elapsed).

        Args:
            as_of_date: ISO date to check expiry against (default: today)

        Returns:
            List of expired predictions with outcome_date set
        """
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        predictions = self.load_predictions()
        expired = []

        for p in predictions:
            if p.get("outcome") != "pending":
                continue  # Already resolved

            made_date = p.get("made_date", "")
            horizon = p.get("time_horizon", "6m")

            if not made_date:
                continue

            # Parse horizon
            try:
                if horizon.endswith("m"):
                    months = int(horizon[:-1])
                    made_dt = datetime.fromisoformat(made_date.replace("Z", "+00:00"))
                    expiry_dt = made_dt + timedelta(days=months * 30)
                    expiry_date = expiry_dt.strftime("%Y-%m-%d")
                elif horizon.endswith("y"):
                    years = int(horizon[:-1])
                    made_dt = datetime.fromisoformat(made_date.replace("Z", "+00:00"))
                    expiry_dt = made_dt + timedelta(days=years * 365)
                    expiry_date = expiry_dt.strftime("%Y-%m-%d")
                else:
                    continue
            except (ValueError, TypeError):
                continue

            if expiry_date <= as_of_date:
                p["expiry_date"] = expiry_date
                expired.append(p)

        logger.info("[COHORT] %d predictions expired as of %s", len(expired), as_of_date)
        return expired

    def get_pending_predictions(self) -> list[dict]:
        """Get all pending predictions."""
        return [p for p in self.load_predictions() if p.get("outcome") == "pending"]

    def get_resolved_predictions(self) -> list[dict]:
        """Get all resolved predictions (hit/miss)."""
        return [p for p in self.load_predictions() if p.get("outcome") in ("hit", "miss")]

    def cohort_stats(self, cohort: list[dict]) -> dict:
        """Compute statistics for a cohort."""
        if not cohort:
            return {"total": 0, "resolved": 0, "pending": 0, "hit_rate": 0}

        resolved = [p for p in cohort if p.get("outcome") in ("hit", "miss")]
        correct = sum(1 for p in resolved if p["outcome"] == "hit")
        hit_rate = correct / len(resolved) if resolved else 0

        return {
            "total": len(cohort),
            "resolved": len(resolved),
            "pending": len([p for p in cohort if p.get("outcome") == "pending"]),
            "hit": correct,
            "miss": len(resolved) - correct,
            "hit_rate": round(hit_rate, 4),
        }

    def fixed_asset_pool(self) -> list[str]:
        """Return fixed asset pool to prevent survivorship bias.

        The asset pool is frozen at the first prediction date.
        Assets that delisted after the freeze are still included.
        """
        predictions = self.load_predictions()
        if not predictions:
            return []

        # Find earliest made_date
        dates = [p.get("made_date", "") for p in predictions if p.get("made_date")]
        if not dates:
            return []
        freeze_date = min(dates)

        # All assets that had a prediction on or before freeze_date
        pool = set()
        for p in predictions:
            if p.get("made_date", "") <= freeze_date:
                pool.add(p.get("asset", ""))

        return sorted(pool)

    def generate_cohort_report(self, output_dir: str = "output") -> dict:
        """Generate full cohort report with all cohorts."""
        cohorts = {
            "all": self.get_cohort(),
            "bullish_6m": self.get_cohort(direction="bullish", time_horizon="6m"),
            "bullish_12m": self.get_cohort(direction="bullish", time_horizon="12m"),
            "bearish": self.get_cohort(direction="bearish"),
            "expired": self.get_expired_predictions(),
            "pending": self.get_pending_predictions(),
            "resolved": self.get_resolved_predictions(),
        }

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fixed_asset_pool": self.fixed_asset_pool(),
            "cohorts": {name: self.cohort_stats(c) for name, c in cohorts.items()},
        }

        # Save report
        from pathlib import Path as _Path
        out_path = _Path(output_dir) / "cohort_report.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("[COHORT] Report saved: %s", out_path)
        return report
