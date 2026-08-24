"""V56 YFinanceEngine — 全球市场数据连接器（美股/港股/ETF/外汇/商品）

从 Yahoo Finance 获取全球市场数据，填补现有数据管线的国际覆盖盲区。

使用方式:
    engine = YFinanceEngine()
    result = engine.fetch(DataQuery(assets=["AAPL", "TSLA"]))

依赖: pip install yfinance
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger("v56.data.yfinance")

_HAS_YFINANCE = False
try:
    import yfinance as yf

    _HAS_YFINANCE = True
except ImportError:
    logger.warning("yfinance not installed")

try:
    from core.models import DataPoint
    from legacy.data_platform.engine import DataResponse, DataQuery
except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class DataPoint:
        name: str = ""
        value: Any = None
        unit: str = ""
        source: str = ""
        source_level: str = ""
        confidence: str = "medium"
        is_estimate: bool = False
        fiscal_year: int | None = None
        note: str = ""

    @dataclass
    class DataResponse:
        points: list = field(default_factory=list)
        source: str = ""
        confidence: str = "medium"
        error: str = ""


class YFinanceEngine:
    """Yahoo Finance 全球市场数据引擎

    数据覆盖:
    - 美股/港股/欧股实时行情与基本面
    - 全球 ETF/指数
    - 外汇 & 商品
    - 财务报表 & 估值指标
    - 机构一致预期
    """

    name = "yfinance"

    def fetch(self, query: DataQuery) -> DataResponse:
        if not _HAS_YFINANCE:
            return DataResponse(error="yfinance not installed", source=self.name)

        if not query.assets:
            return DataResponse(error="no assets provided", source=self.name)

        all_points = []
        for asset in query.assets:
            try:
                ticker = yf.Ticker(asset)
                info = ticker.info or {}

                mappings = [
                    ("price", "currentPrice", "currentPrice", "yuan", "high"),
                    ("market_cap", "marketCap", "marketCap", "yuan", "high"),
                    ("pe_ttm", "trailingPE", "trailingPE", "x", "high"),
                    ("pe_forward", "forwardPE", "forwardPE", "x", "medium"),
                    ("pb", "priceToBook", "priceToBook", "x", "high"),
                    ("eps_ttm", "trailingEps", "trailingEps", "yuan", "high"),
                    ("dividend_yield", "dividendYield", "dividendYield", "%", "high"),
                    ("beta", "beta", "beta", "", "medium"),
                    ("revenue", "totalRevenue", "totalRevenue", "yuan", "high"),
                    ("net_income", "netIncomeToCommon", "netIncomeToCommon", "yuan", "high"),
                    ("free_cash_flow", "freeCashflow", "freeCashflow", "yuan", "medium"),
                    ("ebitda", "ebitda", "ebitda", "yuan", "medium"),
                    ("debt_to_equity", "debtToEquity", "debtToEquity", "%", "medium"),
                    ("profit_margin", "profitMargins", "profitMargins", "%", "high"),
                    ("revenue_growth", "revenueGrowth", "revenueGrowth", "%", "medium"),
                    ("target_price", "targetMeanPrice", "targetMeanPrice", "yuan", "medium"),
                    ("recommendation", "recommendationKey", "recommendationKey", "", "medium"),
                    ("sector", "sector", "sector", "", "high"),
                    ("industry", "industry", "industry", "", "high"),
                    ("country", "country", "country", "", "high"),
                ]

                for name_key, info_key, out_name, unit, conf in mappings:
                    val = info.get(info_key)
                    if val is not None:
                        try:
                            val = float(val)
                        except (ValueError, TypeError):
                            pass
                        all_points.append(
                            DataPoint(
                                name=out_name,
                                value=val,
                                unit=unit,
                                source=f"{self.name}/{asset}",
                                source_level="L1_filing" if conf == "high" else "L3_estimate",
                                confidence=conf,
                            )
                        )

                # 历史股价数据
                hist = ticker.history(period="1y")
                if hist is not None and not hist.empty:
                    close = hist["Close"]
                    all_points.append(
                        DataPoint(
                            name="ytd_chg_pct",
                            value=round((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100, 2),
                            unit="%",
                            source=f"{self.name}/{asset}",
                            source_level="L1_filing",
                            confidence="high",
                        )
                    )
                    all_points.append(
                        DataPoint(
                            name="high_52w",
                            value=float(close.max()),
                            unit="yuan",
                            source=f"{self.name}/{asset}",
                            source_level="L1_filing",
                            confidence="high",
                        )
                    )
                    all_points.append(
                        DataPoint(
                            name="low_52w",
                            value=float(close.min()),
                            unit="yuan",
                            source=f"{self.name}/{asset}",
                            source_level="L1_filing",
                            confidence="high",
                        )
                    )

                # 财务报表
                try:
                    fin = ticker.financials
                    if fin is not None and not fin.empty:
                        for col in fin.columns[:3]:
                            year = col.year if hasattr(col, "year") else str(col)[:4]
                            for row_name in ["Total Revenue", "Operating Income", "Net Income"]:
                                if row_name in fin.index:
                                    val = fin.loc[row_name, col]
                                    if val and not (isinstance(val, float) and (val != val)):
                                        all_points.append(
                                            DataPoint(
                                                name=f"{row_name.lower().replace(' ', '_')}_{year}",
                                                value=float(val),
                                                unit="yuan",
                                                source=f"{self.name}/{asset}",
                                                source_level="L1_filing",
                                                confidence="high",
                                            )
                                        )
                except Exception:
                    pass

            except Exception as e:
                logger.warning("YFinanceEngine fetch failed for %s: %s", asset, e)
                continue

        if not all_points:
            return DataResponse(error="all assets failed", source=self.name)

        return DataResponse(
            points=all_points, source=self.name, confidence="high" if len(all_points) > 10 else "medium"
        )

    def fetch_global_market_overview(self) -> DataResponse:
        """获取全球市场概况（主要指数）"""
        indices = {
            "^GSPC": "SP500",
            "^DJI": "DowJones",
            "^IXIC": "NASDAQ",
            "^HSI": "HSI",
            "^N225": "Nikkei225",
            "^FTSE": "FTSE100",
            "000300.SS": "CSI300",
            "^STOXX50E": "EuroStoxx50",
            "GC=F": "Gold",
            "CL=F": "CrudeOil",
        }
        return self.fetch(DataQuery(assets=list(indices.keys())))
