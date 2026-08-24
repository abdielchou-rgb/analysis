"""akshare_deep.py — akshare 深度集成模块

当前只用了akshare约30个接口。akshare有3000+。
本模块释放高价值未用接口：

高价值列表:
  - stock_board_industry_hist_em: 行业板块历史行情
  - stock_board_industry_cons_em: 行业板块成分股
  - stock_zt_pool_em: 涨停板池
  - stock_hsgt_hist_em: 沪深港通资金
  - stock_margin_detail_szse: 融资融券
  - stock_individual_fund_flow: 个股资金流
  - stock_profit_forecast_em: 盈利预测（已用）
  - stock_comment_detail_em: 个股研报
  - industry_compare: 行业对比

用法:
    from data.akshare_deep import AkshareDeep
    ad = AkshareDeep()
    ad.get_industry_board("光伏")  # 行业板块行情
    ad.get_capital_flow("600519")  # 资金流
    ad.get_northbound_flow()        # 北向资金
    ad.get_margin("600519")         # 融资融券
"""

from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger("v57.data.akshare_deep")

_HAS_AKSHARE = False
try:
    import akshare as ak
    import pandas as pd
    _HAS_AKSHARE = True
except ImportError:
    logger.warning("akshare not installed, AkshareDeep unavailable")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass, field
    @dataclass
    class DataPoint:
        name: str = ""; value: Any = None; unit: str = ""
        source: str = ""; source_level: str = ""; confidence: str = "medium"
        is_estimate: bool = False; fiscal_year: int | None = None; note: str = ""


class AkshareDeep:
    """akshare 深度集成 — 高价值未用接口"""

    name = "akshare_deep"

    def get_industry_board(self, industry: str) -> list[DataPoint]:
        """行业板块行情
        
        类似: stock_board_industry_hist_em
        """
        if not _HAS_AKSHARE:
            return []
        try:
            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                return []
            
            points = []
            for _, row in df.iterrows():
                name = str(row.get("板块名称", ""))
                if industry in name or name in industry:
                    points.append(DataPoint(
                        name="industry_board_name", value=name, unit="",
                        source="akshare/board_industry", source_level="L2_provider",
                        confidence="high",
                    ))
                    for col, unit in [("涨跌幅", "%"), ("总市值", "亿元"),
                                      ("换手率", "%"), ("上涨家数", "家"),
                                      ("市盈率", "x")]:
                        val = row.get(col)
                        if val is not None and val != "":
                            try:
                                points.append(DataPoint(
                                    name=f"board_{col}", value=float(val),
                                    unit=unit, source="akshare/board_industry",
                                    source_level="L2_provider", confidence="high",
                                ))
                            except (ValueError, TypeError):
                                pass
                    break
            return points
        except Exception as e:
            logger.debug("Industry board failed: %s", e)
            return []

    def get_capital_flow(self, asset_code: str) -> list[DataPoint]:
        """个股资金流
        
        类似: stock_individual_fund_flow
        """
        if not _HAS_AKSHARE:
            return []
        try:
            df = ak.stock_individual_fund_flow(stock=asset_code, market="sh")
            if df is None or df.empty:
                df = ak.stock_individual_fund_flow(stock=asset_code, market="sz")
            if df is None or df.empty:
                return []
            
            latest = df.iloc[0]
            points = []
            for col, unit in [("主力净流入-净额", "元"), ("小单净流入-净额", "元"),
                              ("主力净流入-净占比", "%"), ("小单净流入-净占比", "%")]:
                val = latest.get(col)
                if val is not None and val != "":
                    try:
                        v = float(val)
                        if "净额" in col:
                            v = round(v / 1e8, 2)  # 转亿
                            u = "亿元"
                        else:
                            u = "%"
                        points.append(DataPoint(
                            name=f"capital_flow_{col}",
                            value=v, unit=u,
                            source="akshare/fund_flow",
                            source_level="L2_provider", confidence="high",
                        ))
                    except (ValueError, TypeError):
                        pass
            return points
        except Exception as e:
            logger.debug("Capital flow failed: %s", e)
            return []

    def get_northbound_flow(self, days: int = 5) -> list[DataPoint]:
        """北向资金（沪深港通）
        
        类似: stock_hsgt_hist_em
        """
        if not _HAS_AKSHARE:
            return []
        try:
            df = ak.stock_hsgt_hist_em(symbol="北上")
            if df is None or df.empty:
                return []
            
            points = []
            for _, row in df.head(days).iterrows():
                date = str(row.get("日期", ""))
                for col, unit in [("当日成交净买入额", "亿元"), ("买入成交额", "亿元"),
                                  ("卖出成交额", "亿元"), ("领涨股", "")]:
                    val = row.get(col)
                    if val is not None and val != "":
                        try:
                            points.append(DataPoint(
                                name=f"northbound_{col}",
                                value=float(val), unit=unit,
                                source="akshare/hsgt",
                                source_level="L2_provider", confidence="high",
                                note=f"日期:{date}",
                            ))
                        except (ValueError, TypeError):
                            pass
            return points
        except Exception as e:
            logger.debug("Northbound flow failed: %s", e)
            return []

    def get_margin(self, asset_code: str) -> list[DataPoint]:
        """融资融券
        
        类似: stock_margin_detail_szse
        """
        if not _HAS_AKSHARE:
            return []
        try:
            df = ak.stock_margin_detail_szse(date="20260726")
            if df is None or df.empty:
                return []
            
            for _, row in df.iterrows():
                if str(row.get("证券代码", "")).strip().zfill(6) == asset_code:
                    points = []
                    for col, unit in [("融资余额", "万元"), ("融券余额", "万元"),
                                      ("融资余额占流通市值比", "%")]:
                        val = row.get(col)
                        if val is not None and val != "":
                            try:
                                v = float(val)
                                if "余额" in col and "占比" not in col:
                                    v = round(v / 1e4, 2)
                                    u = "亿元"
                                else:
                                    u = "%"
                                points.append(DataPoint(
                                    name=f"margin_{col}", value=v, unit=u,
                                    source="akshare/margin",
                                    source_level="L2_provider", confidence="high",
                                ))
                            except (ValueError, TypeError):
                                pass
                    return points
            return []
        except Exception as e:
            logger.debug("Margin data failed: %s", e)
            return []

    def get_limit_up_pool(self) -> list[DataPoint]:
        """涨停板池
        
        类似: stock_zt_pool_em
        """
        if not _HAS_AKSHARE:
            return []
        try:
            df = ak.stock_zt_pool_em(date="20260726")
            if df is None or df.empty:
                return []
            
            points = []
            for _, row in df.head(10).iterrows():
                name = str(row.get("名称", ""))
                points.append(DataPoint(
                    name="limit_up_stock",
                    value=name,
                    unit="",
                    source="akshare/zt_pool",
                    source_level="L2_provider", confidence="high",
                    note=f"涨停{row.get('涨跌幅','')}%",
                ))
            return points
        except Exception as e:
            logger.debug("Limit up pool failed: %s", e)
            return []

    def get_stock_comments(self, asset_code: str) -> list[DataPoint]:
        """个股研报摘要
        
        类似: stock_comment_detail_em
        """
        if not _HAS_AKSHARE:
            return []
        try:
            df = ak.stock_comment_detail_em(symbol=asset_code)
            if df is None or df.empty:
                return []
            
            points = []
            for _, row in df.head(5).iterrows():
                title = str(row.get("研究报告标题", ""))
                org = str(row.get("机构名称", ""))
                rating = str(row.get("评级", ""))
                points.append(DataPoint(
                    name="analyst_report",
                    value=title,
                    unit="",
                    source=f"akshare/comment/{org}",
                    source_level="L2_provider", confidence="medium",
                    note=f"机构:{org}|评级:{rating}",
                ))
            return points
        except Exception as e:
            logger.debug("Stock comments failed: %s", e)
            return []

    def get_industry_compare(self, industry: str) -> list[DataPoint]:
        """行业对比数据
        
        类似: industry_compare
        """
        if not _HAS_AKSHARE:
            return []
        try:
            from akshare import industry_compare
            df = industry_compare(symbol=industry)
            if df is None or df.empty:
                return []
            
            points = []
            for _, row in df.head(10).iterrows():
                name = str(row.get("股票名称", row.get("名称", "")))
                for col, unit in [("市盈率", "x"), ("市净率", "x"),
                                  ("ROE", "%"), ("毛利率", "%"),
                                  ("营收增长率", "%"), ("净利润增长率", "%")]:
                    val = row.get(col)
                    if val is not None and val != "":
                        try:
                            points.append(DataPoint(
                                name=f"compare_{col}_{name}",
                                value=float(val), unit=unit,
                                source="akshare/industry_compare",
                                source_level="L2_provider", confidence="high",
                            ))
                        except (ValueError, TypeError):
                            pass
            return points
        except Exception as e:
            logger.debug("Industry compare failed: %s", e)
            return []


akshare_deep = AkshareDeep()
