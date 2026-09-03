"""
prediction_validator.py - Scheduled task that validates expired predictions against real data.
Runs as a daily/scripted task: python -m core.prediction_validator
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("2hao.prediction_validator")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


class PredictionValidator:
    """Validate expired predictions against real market data"""

    def __init__(self, storage_path: str | None = None, industry: str = ""):
        if storage_path is None:
            storage_path = str(_ROOT / "data" / "forward_picks" / "track_record.json")
        self.storage_path = storage_path
        self.industry = industry  # for industry-calibrated thresholds
        self._load()

    def _get_threshold(self) -> float:
        """Get industry-calibrated threshold.
        High-volatility industries (semiconductor/biotech) need wider thresholds.
        """
        high_vol = {"semiconductor", "biotech", "pharma", "tech"}
        low_vol = {"utility", "consumer_staples", "telecom", "bank"}
        if self.industry and self.industry in high_vol:
            return 0.15
        if self.industry and self.industry in low_vol:
            return 0.03
        return 0.05  # default

    def _load(self):
        """Load current predictions"""
        from core.tools.track_record import TrackRecordManager

        self.tm = TrackRecordManager(self.storage_path)

    def validate_all(self) -> dict:
        """Validate all expired predictions"""
        results = {"total": 0, "validated": 0, "failed": 0, "details": []}
        now = datetime.now()

        for pred in self.tm.record.predictions:
            if pred.outcome != "pending":
                continue

            # Check if prediction has expired
            if not pred.made_date:
                continue

            try:
                made = datetime.strptime(pred.made_date, "%Y-%m-%d")
            except Exception:
                continue

            # Determine expiration based on time_horizon
            horizon_days = {"3m": 90, "6m": 180, "12m": 365, "unknown": 180}
            days = horizon_days.get(pred.time_horizon, 180)

            if (now - made).days < days:
                continue  # Not expired yet

            results["total"] += 1

            # Try to validate against real data
            outcome = self._validate_prediction(pred)
            if outcome["validated"]:
                self.tm.update_outcome(pred.id, outcome["outcome"], outcome["detail"])
                results["validated"] += 1
            else:
                # Mark as requires_human_review
                self.tm.update_outcome(
                    pred.id, "requires_human_review", "需要人工验证: " + outcome.get("reason", "数据不可用")
                )
                results["failed"] += 1
            results["details"].append(outcome)

        if results["total"] > 0:
            self.tm._save()
            logger.info("Validated %d of %d expired predictions", results["validated"], results["total"])

        return results

    def _get_prediction_type(self, bold_call: str, direction: str) -> str:
        """Classify prediction type: price/financial/qualitative."""
        price_keywords = ["目标价", "股价", "估值", "上涨", "下跌", "price", "target"]
        financial_keywords = ["营收", "净利", "收", "增长", "增", "利润率", "ROE", "EPS", "毛利率", "capex", "投资回报"]
        if any(kw in bold_call for kw in price_keywords):
            return "price"
        if any(kw in bold_call for kw in financial_keywords):
            return "financial"
        return "qualitative"

    def _validate_prediction(self, pred) -> dict:
        """Validate a single prediction against market data."""
        result = {
            "prediction_id": pred.id,
            "asset": pred.asset,
            "bold_call": pred.bold_call[:80],
            "validated": False,
            "outcome": "pending",
            "detail": "",
            "reason": "",
        }

        # Classify prediction type
        pred_type = self._get_prediction_type(pred.bold_call, pred.direction)
        result["prediction_type"] = pred_type

        # Only price-type predictions can be auto-validated
        if pred_type != "price":
            result["validated"] = False
            result["outcome"] = "requires_human_review"
            result["reason"] = f"非价格型预测({pred_type})，需人工验证"
            result["detail"] = f"预测类型: {pred_type} | {pred.bold_call[:100]}"
            return result

        # Price validation logic (existing)
        try:
            # Try akshare for A-share stocks
            price_before = self._get_price(pred.asset, pred.made_date)
            if not price_before:
                # Try yfinance as fallback
                price_before = self._get_price_yfinance(pred.asset, pred.made_date)

            if not price_before:
                result["reason"] = "无法获取历史价格数据"
                return result

            # Get price at maturity
            horizon_days = {"3m": 90, "6m": 180, "12m": 365, "unknown": 180}
            days = horizon_days.get(pred.time_horizon, 180)
            maturity_date = (datetime.strptime(pred.made_date, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")

            price_after = self._get_price(pred.asset, maturity_date)
            if not price_after:
                price_after = self._get_price_yfinance(pred.asset, maturity_date)

            if not price_after:
                result["reason"] = "无法获取到期日价格数据"
                return result

            # Compare, using industry-calibrated threshold
            change = (price_after - price_before) / price_before
            threshold = self._get_threshold()

            if pred.direction == "bullish":
                correct = change > threshold
            elif pred.direction == "bearish":
                correct = change < -threshold
            else:
                correct = abs(change) < threshold

            result["validated"] = True
            result["outcome"] = "hit" if correct else "miss"
            result["detail"] = (
                f"入场价: {price_before:.2f}, "
                f"到期价: {price_after:.2f}, "
                f"变动: {change * 100:.1f}%, "
                f"判断: {pred.direction}, "
                f"阈值: {threshold:.0%}, "
                f"预测类型: {pred_type}"
            )

        except Exception as e:
            result["reason"] = str(e)[:100]

        return result

    def _get_price(self, asset: str, date_str: str) -> float | None:
        """Get price from akshare"""
        try:
            import akshare as ak

            code = self._asset_to_code(asset)
            if not code:
                return None
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=date_str, end_date=date_str, adjust="qfq")
            if df is not None and len(df) > 0:
                return float(df.iloc[0]["收盘"])
        except Exception:
            pass
        return None

    def _get_price_yfinance(self, asset: str, date_str: str) -> float | None:
        """Get price from yfinance"""
        try:
            import yfinance as yf

            ticker = yf.Ticker(asset)
            hist = ticker.history(start=date_str, end=date_str)
            if hist is not None and len(hist) > 0:
                return float(hist["Close"].iloc[0])
        except Exception:
            pass
        return None

    def _asset_to_code(self, asset: str) -> str:
        """Convert asset name to akshare code"""
        if "." in asset:
            return asset.split(".")[0]
        return asset

    def get_stats(self) -> dict:
        """Get validation statistics"""
        self._load()
        total = len(self.tm.record.predictions)
        resolved = sum(1 for p in self.tm.record.predictions if p.outcome in ("hit", "miss"))
        correct = sum(1 for p in self.tm.record.predictions if p.outcome == "hit")
        return {
            "total": total,
            "resolved": resolved,
            "hit": correct,
            "miss": resolved - correct,
            "pending": sum(1 for p in self.tm.record.predictions if p.outcome == "pending"),
            "requires_review": sum(1 for p in self.tm.record.predictions if p.outcome == "requires_human_review"),
            "accuracy": correct / resolved if resolved > 0 else 0,
        }

    def format_report(self) -> str:
        """Generate validation report"""
        s = self.get_stats()
        lines = []
        lines.append("=" * 50)
        lines.append("Prediction Validation Report")
        lines.append("=" * 50)
        lines.append(f"Total predictions: {s['total']}")
        lines.append(f"Resolved: {s['resolved']}")
        lines.append(f"  Correct: {s['correct']}")
        lines.append(f"  Incorrect: {s['incorrect']}")
        lines.append(f"  Pending: {s['pending']}")
        lines.append(f"  Requires review: {s['requires_review']}")
        lines.append(f"Accuracy: {s['accuracy']:.1%}")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# R30 模块1：forward_picks.csv 离线验证（打通双轨）
# ForwardPicksDB(csv) 的预测此前从不被 PredictionValidator(json) 验证
# ════════════════════════════════════════════════════════════════
def validate_forward_picks_csv(horizon_days: int = 365) -> dict:
    """验证 forward_picks.csv 中已到期的预测（离线，本地 qlib 价格）。

    规则：
      - 到期判定：created_at + horizon_days <= 今天 → 到期
      - 验证：到期价格 vs 记录时的 current_price → 涨跌幅
      - 结果：direction=bull 且涨>0 → hit；direction=bear 且涨<0 → hit；否则 miss
      - 更新 csv 的 verification_status / actual_price / actual_return

    返回 {total, expired, validated, hit, miss, pending_after}
    """
    import datetime as _dt

    from core.forward_picks import ForwardPicksDB

    db = ForwardPicksDB()
    picks = db.load_all()
    if not picks:
        return {"total": 0, "expired": 0, "validated": 0, "hit": 0, "miss": 0, "pending_after": 0}

    today = _dt.date.today()
    now = today.strftime("%Y-%m-%d")
    expired = [
        p
        for p in picks
        if p.verification_status == "pending"
        and p.created_at
        and (today - _dt.datetime.strptime(p.created_at[:10], "%Y-%m-%d").date()).days >= horizon_days
    ]
    validated = 0
    hit = 0
    miss = 0
    skipped = 0
    for p in expired:
        # 用本地 qlib 价格（离线）
        code = p.asset_code or ""
        if not code:
            skipped += 1
            continue
        from core.data_backends import _query_local_qlib_price

        q = _query_local_qlib_price(code)
        if not q or len(q["prices"]) < 2:
            skipped += 1
            continue
        # 收益率指数口径：qlib close 是"投入1元到该日"的净值，收益=比值-1。
        # 修复（2026-08-04 预测闭环审计）：旧逻辑把 close 当绝对股价与
        # current_price(元) 相减（或 fallback 到首月）→ 长历史个股收益率虚高/
        # 错位。统一用净值比值：as_of 月净值 → 最新月净值。
        _t = (p.created_at or "9999-99")[:7]
        # R64（2026-08-04 审计修复）：优先用入库时记录的 anchor_nav（净值锚点），
        # 避免重复取价与入库不一致；无 anchor_nav 时回退到 as_of 月净值查询。
        as_of_nav = p.anchor_nav if p.anchor_nav and p.anchor_nav > 0 else None
        if not as_of_nav:
            as_of_nav = q["prices"][0]
            for _d, _p in zip(q["dates"], q["prices"]):
                if _d <= _t:
                    as_of_nav = _p
        latest_nav = q["prices"][-1]
        ret = (latest_nav - as_of_nav) / as_of_nav if as_of_nav else 0
        # 判定
        if p.direction == "bull":
            ok = ret > 0
        elif p.direction == "bear":
            ok = ret < 0
        else:
            ok = None
        status = "hit" if ok else ("miss" if ok is not None else "pending")
        if ok is not None:
            p.actual_price = latest_nav
            p.actual_return = ret
            p.verification_status = status
            p.verified_at = now
            validated += 1
            if status == "hit":
                hit += 1
            else:
                miss += 1
    # 写回
    if validated:
        db._rewrite_all(picks)
    return {
        "total": len(picks),
        "expired": len(expired),
        "validated": validated,
        "hit": hit,
        "miss": miss,
        "skipped": skipped,
        "pending_after": sum(1 for p in picks if p.verification_status == "pending"),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    validator = PredictionValidator()
    results = validator.validate_all()
    print(validator.format_report())
    print(f"\nValidated {results['validated']} predictions")
