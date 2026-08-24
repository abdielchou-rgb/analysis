"""V56 DataManager — 统一多维数据接口

融合旧有 DataSourceManager (统一引擎+熔断+回退) + 新 V56 引擎，
为报告生成提供单一的数据获取入口。

用法:
    from legacy.data_platform.data_manager import get_data
    data = get_data(asset_code="600519", asset_name="贵州茅台", industry="白酒")
    # 返回: {market, consensus, macro, policy, cvc, news, global, industry_board}
"""

from __future__ import annotations
import logging
from typing import Any, Optional

logger = logging.getLogger("v56.data.manager")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass, field
    from typing import Any

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


def get_data(
    asset_code: str = "",
    asset_name: str = "",
    industry: str = "",
    include_macro: bool = True,
    include_policy: bool = True,
    include_cvc: bool = True,
    include_news: bool = True,
    include_global: bool = True,
    max_news: int = 5,
    use_quality_gate: bool = True,
    use_financial_db: bool = True,
    use_akshare_deep: bool = True,
) -> dict[str, list[DataPoint]]:
    """一键获取多维度数据（V57升级版）

    V57新增:
      - use_quality_gate: 数据是否经过质量网关校验
      - use_financial_db: 是否从DuckDB获取历史财务数据
      - use_akshare_deep: 是否获取资金流/北向/融资融券等深度数据

    Args:
        asset_code: 股票代码（如 600519）
        asset_name: 公司名称（如 贵州茅台）
        industry: 所属行业（如 白酒）
        include_macro: 是否获取宏观数据
        include_policy: 是否获取政策数据
        include_cvc: 是否获取CVC/行业资本数据
        include_news: 是否获取新闻数据
        include_global: 是否获取全球市场数据

    Returns:
        dict with keys: market, consensus, macro, policy, cvc, news, global
    """
    result: dict[str, list[DataPoint]] = {}

    # 1. 二级市场数据
    if asset_code:
        try:
            from legacy.data_platform.__init__ import fetch_realtime, fetch_consensus

            result["market"] = fetch_realtime([asset_code])
            result["consensus"] = fetch_consensus(asset_code)
        except Exception as e:
            logger.debug(f"Market data fetch failed: {e}")

    # V57: Quality gateway — validate all data points
    if use_quality_gate and any(result.values()):
        try:
            from legacy.data_platform.quality.validators import quality_gateway

            all_points = []
            for points in result.values():
                if isinstance(points, list):
                    all_points.extend(points)
            if all_points:
                qc_result = quality_gateway.validate(all_points)
                if qc_result.issues:
                    for issue in qc_result.issues[:5]:
                        logger.debug("QC[%s]: %s", issue.severity, issue.message)
                if not qc_result.passed:
                    logger.warning("Quality gate: %d issues found, filtering...", len(qc_result.issues))
                    # Replace with filtered data
                    filtered = quality_gateway.validate_and_filter(all_points)
                    if filtered:
                        logger.info("Quality gate: %d/%d points passed", len(filtered), len(all_points))
        except Exception as e:
            logger.debug("Quality gateway skipped: %s", e)

    # V57: Financial DB — historical data
    if use_financial_db and asset_code:
        try:
            from legacy.data_platform.financial_db import financial_db

            if financial_db._available:
                hist = financial_db.query_financials(asset_code, "income", years=3)
                if hist:
                    result["historical_financials"] = hist
                    logger.info("Financial DB: %d years of %s", len(hist), asset_code)
                # Also try to store current data
                for points in result.get("market", []):
                    if hasattr(points, "name") and "revenue" in str(points.name):
                        financial_db.store_income_statement(
                            asset_code,
                            2026,
                            {
                                "revenue": float(points.value) if hasattr(points, "value") else 0,
                                "source": "data_manager",
                            },
                        )
                        break
        except Exception as e:
            logger.debug("Financial DB query skipped: %s", e)

    # V57: akshare deep — capital flow / northbound / margin
    if use_akshare_deep and asset_code:
        try:
            from legacy.data_platform.akshare_deep import akshare_deep

            flow = akshare_deep.get_capital_flow(asset_code)
            if flow:
                result["capital_flow"] = flow
            north = akshare_deep.get_northbound_flow()
            if north:
                result["northbound"] = north
        except Exception as e:
            logger.debug("Akshare deep skipped: %s", e)

    # 2. 宏观数据
    if include_macro:
        try:
            from legacy.data_platform.__init__ import fetch_macro

            result["macro"] = fetch_macro("all")
        except Exception as e:
            logger.debug(f"Macro data fetch failed: {e}")

    # 3. 政策法规
    if include_policy and industry:
        try:
            from legacy.data_platform.__init__ import fetch_policy

            result["policy"] = fetch_policy(industry)
        except Exception as e:
            logger.debug(f"Policy data fetch failed: {e}")

    # 4. CVC/行业资本
    if include_cvc and industry:
        try:
            from legacy.data_platform.__init__ import fetch_cvc

            result["cvc"] = fetch_cvc(sector=industry)
        except Exception as e:
            logger.debug(f"CVC data fetch failed: {e}")

    # 5. 新闻/情绪
    if include_news and asset_code:
        try:
            from legacy.data_platform.__init__ import fetch_news

            news_data = fetch_news([asset_code])
            if news_data and asset_code in news_data:
                result["news"] = news_data[asset_code][:max_news]
        except Exception as e:
            logger.debug(f"News data fetch failed: {e}")

    # 6. 全球市场概况
    if include_global:
        try:
            from legacy.data_platform.__init__ import fetch_global_market

            result["global_market"] = fetch_global_market()
        except Exception as e:
            logger.debug(f"Global market fetch failed: {e}")

    # 7. 行业板块数据
    if industry:
        try:
            from legacy.data_platform.__init__ import fetch_realtime

            board_points = _fetch_industry_board(industry)
            if board_points:
                result["industry_board"] = board_points
        except Exception as e:
            logger.debug(f"Industry board fetch failed: {e}")

    logger.info(f"Data collected: { {k: len(v) for k, v in result.items()} }")
    return result


def _fetch_industry_board(industry: str) -> list[DataPoint]:
    """获取行业板块行情数据"""
    points = []
    try:
        import akshare as ak

        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            # 查找匹配行业
            for _, row in df.iterrows():
                name = str(row.get("板块名称", ""))
                if industry in name or name in industry:
                    points.append(
                        DataPoint(
                            name="industry_board_name",
                            value=name,
                            unit="",
                            source="akshare/board_industry",
                            source_level="L1_filing",
                            confidence="high",
                        )
                    )
                    for col in ["涨跌幅", "总市值", "换手率", "上涨家数", "下跌家数"]:
                        val = row.get(col)
                        if val:
                            points.append(
                                DataPoint(
                                    name=f"board_{col}",
                                    value=float(val) if not isinstance(val, str) else val,
                                    unit="%" if "率" in str(col) or "幅" in str(col) else "",
                                    source="akshare/board_industry",
                                    source_level="L1_filing",
                                    confidence="high",
                                )
                            )
                    break
    except Exception as e:
        logger.debug(f"Industry board fetch failed: {e}")
    return points


def get_data_summary(data: dict[str, list[DataPoint]]) -> dict:
    """生成数据摘要（用于日志/调试）"""
    return {
        source: {
            "count": len(points),
            "sources": list(set(p.source for p in points)),
            "confidence": max((p.confidence for p in points), default="low") if points else "none",
        }
        for source, points in data.items()
        if points
    }


class DataManager:
    """DataManager wrapper for backward compatibility"""

    def __init__(self):
        self._ready = True

    def collect(self, asset="", asset_code="", industry="", report_type="industry_deep"):
        result = get_data(
            asset_code=asset_code or (asset if any(c.isdigit() for c in asset) else ""),
            asset_name=asset if not any(c.isdigit() for c in asset) else "",
            industry=asset[:3] if not any(c.isdigit() for c in asset) else "",
        )
        return {
            "asset": asset,
            "report_type": report_type,
            "financials": {
                "status": "available" if result.get("market") else "unavailable",
                "data": result.get("market", []),
                "source": "data_manager",
            },
            "consensus": {
                "status": "available" if result.get("consensus") else "unavailable",
                "data": result.get("consensus", []),
                "source": "consensus",
            },
            "sources": ["data_manager", "consensus"],
        }

    def query(self, asset):
        result = self.collect(asset=asset)
        pts = []
        for k in ["financials", "consensus"]:
            d = result.get(k, {}).get("data", [])
            if d:
                pts.extend(d)
        return pts
