"""
eval/score_predictions.py — 预测兑现打分器（Phase B3，2026-09-06）。

闭环管线最后一环：record_results 写下的预测（目标价/方向/时间窗）→
T+30/90 拉真实行情 → 计算命中率/方向准确率/误差 → eval/calibration.json。

这是校准叙事的起点：报告生成器从不闭环预测兑现，本模块补上。

用法：
    python -m eval.score_predictions [--horizon 30] [--ticker 600519]

依赖：akshare（行情）、track_record 记录文件（core 数据资产）。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.eval.predictions")

CALIBRATION_FILE = _ANALYST_ROOT / "eval" / "calibration.json"


def _find_records() -> list[dict]:
    """定位 track_record 类文件（多路径兼容）。"""
    candidates = [
        _ANALYST_ROOT / "track_record.json",
        _ANALYST_ROOT / "output" / "track_record.json",
        _ANALYST_ROOT / "data" / "track_record.json",
        # Phase B3 集成修复（2026-09-06）：forward_picks 是预测记录真实落盘位置
        _ANALYST_ROOT / "core" / "data" / "forward_picks" / "track_record.json",
        _ANALYST_ROOT / "core" / "data" / "forward_picks" / "track_record_clean.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                # 兼容 {"records": [...]} / {"predictions": [...]} / 裸 list
                if isinstance(data, dict):
                    data = data.get("records") or data.get("predictions") or []
                # 兼容 {"analyst_name", "predictions"} + id 形态
                return [r for r in data if isinstance(r, dict)]
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("record 文件损坏 %s: %s", p, e)
    return []


def _parse_date(s) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)[:19])
    except ValueError:
        # 兼容纯日期 "2026-07-31"
        try:
            return datetime.fromisoformat(str(s)[:10] + "T00:00:00")
        except ValueError:
            return None


def _asset_to_code(name: str) -> str:
    """中文资产名 → A 股 6 位代码（复用统一解析层）。失败返回原名。"""
    try:
        from core.asset_resolver import resolve_asset

        r = resolve_asset(name)
        return r.code if getattr(r, "has_code", False) and r.code else name
    except Exception:
        return name


def _fetch_price_history(ticker: str, start: str, end: str) -> list[tuple[str, float]] | None:
    """akshare 拉日线（A 股 6 位代码）。失败返回 None（离线容错）。"""
    try:
        import akshare as ak

        code = "".join(c for c in ticker if c.isdigit())[:6]
        if len(code) != 6:
            return None
        df = ak.stock_zh_a_hist(
            symbol=code, start_date=start.replace("-", ""), end_date=end.replace("-", ""), period="daily", adjust="qfq"
        )
        if df is None or df.empty:
            return None
        return [
            (str(r.get("日期", "")), float(r.get("收盘", 0))) for _, r in df.iterrows() if r.get("收盘") is not None
        ]
    except Exception as e:
        logger.warning("akshare %s 失败: %s", ticker, str(e)[:80])
        return None


def score_predictions(horizon_days: int = 30) -> dict:
    """主入口：预测记录 → 兑现打分。"""
    records = _find_records()
    if not records:
        return {"status": "no_records", "checked": 0}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    checked, direction_hits, direction_total, errors = [], 0, 0, []

    for rec in records:
        made_at = _parse_date(rec.get("timestamp") or rec.get("date") or rec.get("created_at") or rec.get("made_date"))
        ticker = str(rec.get("ticker") or rec.get("asset") or rec.get("code") or rec.get("stock_code") or "")
        # 兼容 track_record 形态：target_price 可能是空串/含逗号字符串
        _tp = rec.get("target_price") or rec.get("prediction_price")
        try:
            target_price = float(str(_tp).replace(",", "")) if _tp not in (None, "") else None
        except (ValueError, TypeError):
            target_price = None
        # A 股资产名 → 代码解析（track_record 存中文名，akshare 需 6 位代码）
        if ticker and not (ticker.isdigit() and len(ticker) == 6):
            ticker = _asset_to_code(ticker)
        if not (made_at and ticker and isinstance(target_price, (int, float)) and target_price > 0):
            continue
        if now < made_at + timedelta(days=horizon_days):
            continue  # 未到期

        hist = _fetch_price_history(ticker, made_at.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
        if not hist or len(hist) < 2:
            continue
        entry_price = hist[0][1]
        latest_price = hist[-1][1]
        if entry_price <= 0:
            continue

        # 方向判定: 目标价 vs 入场价
        pred_direction = "up" if target_price > entry_price else "down"
        actual_direction = "up" if latest_price > entry_price else "down"
        hit = pred_direction == actual_direction
        direction_total += 1
        direction_hits += int(hit)

        # 误差: |实际变动% - 预测变动%|
        pred_move = (target_price - entry_price) / entry_price * 100
        actual_move = (latest_price - entry_price) / entry_price * 100
        errors.append(abs(pred_move - actual_move))

        checked.append(
            {
                "ticker": ticker,
                "made_at": made_at.isoformat()[:10],
                "entry_price": round(entry_price, 2),
                "latest_price": round(latest_price, 2),
                "target_price": target_price,
                "pred_direction": pred_direction,
                "actual_direction": actual_direction,
                "hit": hit,
                "error_pp": round(abs(pred_move - actual_move), 2),
            }
        )

    summary = {
        "status": "ok",
        "horizon_days": horizon_days,
        "n_scored": len(checked),
        "direction_accuracy": round(direction_hits / direction_total, 4) if direction_total else None,
        "mean_abs_error_pp": round(sum(errors) / len(errors), 2) if errors else None,
        "timestamp": datetime.now(timezone.utc).isoformat()[:19],
        "detail": checked[:20],
    }

    CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=30)
    args = parser.parse_args()
    result = score_predictions(args.horizon)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_cli()
