"""V50+ T1 data connector — akshare-backed financial data with pipeline fallback."""

from __future__ import annotations
import logging
from core.models import DataPoint

from data.engine import pipeline, DataQuery

logger = logging.getLogger("v51.data.akshare")

_HAS_AKSHARE = False
try:
    import akshare as ak
    _HAS_AKSHARE = True
except ImportError:
    logger.warning("akshare not installed, falling back to pipeline")


def fetch_financials(asset_code: str) -> list[DataPoint]:
    """Fetch financial statements for a stock code via akshare, with pipeline fallback."""
    if not asset_code:
        return [DataPoint(name="no_data", value="no asset code provided", source="pipeline", confidence="low")]

    pts: list[DataPoint] = []

    if _HAS_AKSHARE:
        try:
            # Balance sheet (latest annual)
            bs = ak.stock_balance_sheet_by_report_em(symbol=asset_code)
            if bs is not None and not bs.empty:
                latest = bs.iloc[0]
                for col, name in [
                    ("total_assets", "total_assets"),
                    ("total_liabilities", "total_liabilities"),
                    ("total_equity", "total_equity"),
                ]:
                    val = latest.get(col)
                    if val:
                        pts.append(DataPoint(name=name, value=float(val) / 1e8, unit="亿",
                                            source="akshare_balance", source_level="L1_filing",
                                            confidence="high"))

            # Income statement (latest annual)
            inc = ak.stock_profit_sheet_by_report_em(symbol=asset_code)
            if inc is not None and not inc.empty:
                latest = inc.iloc[0]
                for col, name in [
                    ("revenue", "revenue"),
                    ("operating_profit", "operating_profit"),
                    ("net_profit", "net_profit"),
                    ("gross_margin", "gross_margin"),
                ]:
                    val = latest.get(col)
                    if val:
                        pts.append(DataPoint(name=name, value=float(val) / 1e8, unit="亿",
                                            source="akshare_income", source_level="L1_filing",
                                            confidence="high"))

            # Cash flow (latest annual)
            cf = ak.stock_cash_flow_sheet_by_report_em(symbol=asset_code)
            if cf is not None and not cf.empty:
                latest = cf.iloc[0]
                val = latest.get("operating_cf")
                if val:
                    pts.append(DataPoint(name="operating_cf", value=float(val) / 1e8, unit="亿",
                                        source="akshare_cashflow", source_level="L1_filing",
                                        confidence="high"))

        except Exception as e:
            logger.warning("akshare fetch_financials failed for %s: %s", asset_code, e)

    # Pipeline fallback
    if not pts:
        resp = pipeline.fetch(DataQuery(assets=[asset_code], type="market"))
        if resp.points:
            pts.extend(resp.points)

    if not pts:
        return [DataPoint(name="no_data", value=f"no data for {asset_code}", source="pipeline", confidence="low")]

    return pts
