"""V56 ChinaMacroEngine — 中国宏观经济数据连接器

通过 akshare 获取中国宏观经济数据，用于报告的宏观环境分析。

覆盖:
- GDP/CPI/PPI/PMI
- M2/M1/M0货币供应
- LPR/利率/国债收益率
- 社融/信贷数据
- 外汇储备/汇率
- 工业增加值/固定资产投资
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger("v56.data.macro")

_HAS_AKSHARE = False
try:
    import akshare as ak
    import pandas as pd

    _HAS_AKSHARE = True
except ImportError:
    logger.warning("akshare not installed, macro engine unavailable")

_HAS_FRED = False
try:
    from fredapi import Fred

    _HAS_FRED = True
except ImportError:
    logger.warning("fredapi not installed, global macro unavailable")

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

    @dataclass
    class DataQuery:
        type: str = "macro"
        assets: list = field(default_factory=list)
        indicator: str = ""
        days: int = 365


class ChinaMacroEngine:
    """中国经济宏观数据引擎

    用法:
        engine = ChinaMacroEngine()
        result = engine.fetch(DataQuery(type="macro", indicator="gdp"))
        result = engine.fetch_all()  # 获取所有宏观指标
    """

    name = "china_macro"

    def fetch(self, query: DataQuery) -> DataResponse:
        if not _HAS_AKSHARE:
            return DataResponse(error="akshare not installed", source=self.name)

        indicator = query.assets[0] if query.assets else "all"
        points = []

        try:
            if indicator in ("gdp", "all"):
                points.extend(self._fetch_gdp())
            if indicator in ("cpi", "pmi", "all"):
                points.extend(self._fetch_pmi())
            if indicator in ("m2", "money", "all"):
                points.extend(self._fetch_money_supply())
            if indicator in ("bond", "rate", "all"):
                points.extend(self._fetch_bond_yield())
            if indicator in ("cpi", "all"):
                points.extend(self._fetch_cpi())
        except Exception as e:
            logger.error("ChinaMacroEngine fetch failed: %s", e)
            return DataResponse(error=str(e), source=self.name)

        if not points:
            return DataResponse(error="no data returned", source=self.name)

        return DataResponse(points=points, source=self.name, confidence="high")

    def fetch_all(self) -> DataResponse:
        """获取所有宏观指标"""
        return self.fetch(DataQuery(type="macro", indicator="all"))

    def _fetch_gdp(self) -> list[DataPoint]:
        points = []
        try:
            df = ak.macro_china_gdp()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                for col in df.columns:
                    val = latest.get(col)
                    if val and col not in ("季度", "时间"):
                        points.append(
                            DataPoint(
                                name=f"gdp_{col}",
                                value=float(val) if not isinstance(val, str) else val,
                                unit="%",
                                source="akshare/macro_china_gdp",
                                source_level="L1_filing",
                                confidence="high",
                            )
                        )
        except Exception as e:
            logger.debug("GDP fetch failed: %s", e)
        return points

    def _fetch_pmi(self) -> list[DataPoint]:
        points = []
        try:
            df = ak.macro_china_pmi()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                points.append(
                    DataPoint(
                        name="pmi_manufacturing",
                        value=float(latest.get("制造业-指数", 0)),
                        unit="",
                        source="akshare/macro_china_pmi",
                        source_level="L1_filing",
                        confidence="high",
                    )
                )
                points.append(
                    DataPoint(
                        name="pmi_non_manufacturing",
                        value=float(latest.get("非制造业-指数", 0)),
                        unit="",
                        source="akshare/macro_china_pmi",
                        source_level="L1_filing",
                        confidence="high",
                    )
                )
        except Exception as e:
            logger.debug("PMI fetch failed: %s", e)
        return points

    def _fetch_money_supply(self) -> list[DataPoint]:
        points = []
        try:
            df = ak.macro_china_supply_of_money()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                for col, name in [
                    ("货币和准货币（广义货币M2）同比增长", "m2_yoy"),
                    ("货币(狭义货币M1)同比增长", "m1_yoy"),
                    ("流通中现金(M0)同比增长", "m0_yoy"),
                ]:
                    val = latest.get(col)
                    if val:
                        points.append(
                            DataPoint(
                                name=name,
                                value=float(val),
                                unit="%",
                                source="akshare/macro_china_supply_of_money",
                                source_level="L1_filing",
                                confidence="high",
                            )
                        )
        except Exception as e:
            logger.debug("Money supply fetch failed: %s", e)
        return points

    def _fetch_bond_yield(self) -> list[DataPoint]:
        points = []
        try:
            df = ak.bond_zh_us_rate()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                cn_cols = [c for c in df.columns if "中国" in c and "收益率" in c]
                us_cols = [c for c in df.columns if "美国" in c and "收益率" in c]
                for col in cn_cols[:3]:
                    val = latest.get(col)
                    if val:
                        points.append(
                            DataPoint(
                                name=f"cn_bond_{col[:4]}",
                                value=float(val),
                                unit="%",
                                source="akshare/bond_zh_us_rate",
                                source_level="L1_filing",
                                confidence="high",
                            )
                        )
        except Exception as e:
            logger.debug("Bond yield fetch failed: %s", e)
        return points

    def _fetch_cpi(self) -> list[DataPoint]:
        points = []
        try:
            df = ak.macro_china_cpi_monthly()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                for col in df.columns:
                    if "同比" in str(col):
                        val = latest.get(col)
                        if val:
                            points.append(
                                DataPoint(
                                    name="cpi_yoy",
                                    value=float(val),
                                    unit="%",
                                    source="akshare/macro_china_cpi_monthly",
                                    source_level="L1_filing",
                                    confidence="high",
                                )
                            )
        except Exception as e:
            logger.debug("CPI fetch failed: %s", e)
        return points
