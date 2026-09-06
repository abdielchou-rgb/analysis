"""Live-forward outcome update script.

Checks expired predictions against live market data and updates outcomes.
Run periodically (e.g., daily) to resolve predictions that have reached
their time horizon.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.outcome_update")


def load_track_record(path: str = "core/data/forward_picks/track_record.json") -> dict:
    """Load track record from disk (read-only; 写入一律走 TrackRecordManager.apply_resolved)."""
    p = Path(path)
    if not p.exists():
        return {"predictions": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def parse_horizon(horizon: str) -> Optional[int]:
    """Parse time horizon string to days, or None when unparseable.

    '6m' → 180, '12m' → 360, '1y' → 365, '5y' → 1825,
    range '6-12m' → 360 (取上界: 未到最长期限不提前结算, fail-closed)。
    'unknown'/空/无法解析 → None (不猜测到期日; 由人工或回填修复)。
    """
    h = (horizon or "").strip().lower()
    if not h or h in {"unknown", "na", "n/a", "null", "none", "-"}:
        return None
    if "-" in h:
        parts = h.split("-")
        if len(parts) == 2 and parts[1]:
            h = parts[1].strip()
        else:
            return None
    if h.endswith("m") and h[:-1].isdigit():
        return int(h[:-1]) * 30
    if h.endswith("y") and h[:-1].isdigit():
        return int(h[:-1]) * 365
    return None


def check_expired(
    predictions: list[dict],
    as_of_date: str = None,
) -> tuple[list[dict], list[str]]:
    """Find predictions that have expired but are still pending.

    Args:
        predictions: List of prediction dicts
        as_of_date: ISO date to check against (default: today)

    Returns:
        (expired_list, warnings). expired_list 带计算出的 expiry_date；
        warnings 是"无法判定到期、被跳过"的记录说明——不静默吞掉，
        避免 unknown/坏 horizon 记录永远不被发现。
    """
    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    expired = []
    warnings = []
    for p in predictions:
        if p.get("outcome") != "pending":
            continue

        made_date = p.get("made_date", "")
        horizon = p.get("time_horizon", "6m")

        if not made_date:
            warnings.append(f"made_date missing, skip id={p.get('id', '?')} asset={p.get('asset', '?')}")
            continue

        try:
            made_dt = datetime.fromisoformat(made_date.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            warnings.append(
                f"made_date unparseable={made_date!r}, skip id={p.get('id', '?')} asset={p.get('asset', '?')}"
            )
            continue

        days = parse_horizon(horizon)
        if days is None:
            warnings.append(
                f"time_horizon unparseable={horizon!r}, skip id={p.get('id', '?')} "
                f"asset={p.get('asset', '?')} — 该记录永不自动到期，需人工修复 horizon"
            )
            continue

        expiry_date = (made_dt + timedelta(days=days)).strftime("%Y-%m-%d")
        if expiry_date <= as_of_date:
            p["expiry_date"] = expiry_date
            expired.append(p)

    return expired, warnings


def resolve_outcome(
    prediction: dict,
    get_price_func=None,
    backend: str = "auto",
    get_benchmark_func=None,
) -> dict:
    """Resolve a prediction's outcome based on price data and alpha judge.

    Args:
        prediction: The prediction dict
        get_price_func: Callable(asset, date) → price. If None, uses price_feeder.
        backend: Price backend ('auto', 'akshare', 'yfinance', 'mock')
        get_benchmark_func: Callable(benchmark_code, date) → price. If None, degraded judge.

    Returns:
        Updated prediction with outcome set.
        If price unavailable → outcome="unverifiable", never fabricates.
    """
    from core.prediction_judge import judge_outcome
    from core.price_feeder import get_price_or_unverifiable

    def _default_price_func(a, d):
        return get_price_or_unverifiable(a, d, backend=backend).get("price")

    asset = prediction.get("asset", "")
    direction = prediction.get("direction", "")
    made_date = prediction.get("made_date", "")
    expiry_date = prediction.get("expiry_date", "")

    if not get_price_func:
        get_price_func = _default_price_func

    try:
        price_at_make = get_price_func(asset, made_date)
        price_at_expiry = get_price_func(asset, expiry_date)

        if price_at_make is None or price_at_expiry is None:
            # P0-1: Never fabricate — mark as unverifiable
            prediction["outcome"] = "unverifiable"
            prediction["outcome_reason"] = f"data_unavailable:{asset}@make={made_date},expiry={expiry_date}"
            prediction["price_at_make"] = price_at_make
            prediction["price_at_expiry"] = price_at_expiry
            return prediction

        # Compute returns
        actual_return = (price_at_expiry - price_at_make) / price_at_make

        # Get benchmark return if available
        bench_return = None
        if get_benchmark_func:
            try:
                bench_make = get_benchmark_func("000300", made_date)  # CSI 300
                bench_expiry = get_benchmark_func("000300", expiry_date)
                if bench_make and bench_expiry:
                    bench_return = (bench_expiry - bench_make) / bench_make
            except Exception:
                pass  # Degraded: no benchmark

        # Get target price if available
        target_price = prediction.get("target_price")
        if target_price:
            try:
                target_price = float(target_price)
            except (ValueError, TypeError):
                target_price = None

        # M1-W2: Use judge_outcome instead of absolute direction
        judge_result = judge_outcome(
            actual_return=actual_return,
            direction=direction,
            bench_return=bench_return,
            target_price=target_price,
            price_at_expiry=price_at_expiry,
        )

        prediction["outcome"] = judge_result["outcome"]
        prediction["outcome_detail"] = judge_result["detail"]
        prediction["judge_ver"] = judge_result["judge_ver"]
        prediction["bench"] = judge_result.get("bench", "none")
        prediction["alpha"] = judge_result.get("alpha")
        prediction["return_pct"] = round(actual_return * 100, 2)
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
    as_of_date: str = None,
) -> dict:
    """Run outcome update on all expired predictions.

    SSOT (2026-09-07 T1): resolve 结果经 TrackRecordManager.apply_resolved 写回
    (唯一写路径 = dataclass 门面)，禁止在此裸 json.dump track_record。

    Args:
        track_record_path: Path to track record JSON
        get_price_func: Callable(asset, date) → price
        dry_run: If True, don't write changes

    Returns:
        {updated, pending_review, already_resolved, errors}
    """
    data = load_track_record(track_record_path)
    predictions = data.get("predictions", [])

    expired, expiry_warnings = check_expired(predictions, as_of_date=as_of_date)
    stats = {
        "total": len(predictions),
        "expired": len(expired),
        "expiry_warnings": len(expiry_warnings),
        "updated": 0,
        "pending_review": 0,
        "already_resolved": 0,
        "errors": 0,
    }

    for w in expiry_warnings:
        logger.warning("[OUTCOME] %s", w)

    resolved_items = []
    for p in expired:
        try:
            p = resolve_outcome(p, get_price_func)
            if p.get("outcome") == "hit" or p.get("outcome") == "miss":
                stats["updated"] += 1
                resolved_items.append(p)
            elif p.get("outcome") == "pending_review":
                stats["pending_review"] += 1
            elif p.get("outcome") == "unverifiable":
                # 无真实价 → 诚实标注不可验证，同样需要持久化
                stats["updated"] += 1
                resolved_items.append(p)
        except Exception as e:
            stats["errors"] += 1
            logger.error("[OUTCOME] Error resolving %s: %s", p.get("asset", "?"), str(e))

    if not dry_run and resolved_items:
        from core.tools.track_record import TrackRecordManager

        mgr = TrackRecordManager(storage_path=track_record_path)
        n = mgr.apply_resolved(resolved_items)
        logger.info("[OUTCOME] Track record updated via SSOT façade: %d resolved", n)
    else:
        logger.info(
            "[OUTCOME] Dry run: %d would be updated, %d pending review", stats["updated"], stats["pending_review"]
        )

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
        as_of_date=args.as_of,
    )

    print(json.dumps(stats, indent=2))
