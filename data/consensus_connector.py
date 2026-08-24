"""V50+ Consensus Connector — akshare stock_profit_forecast + stock_analyst_rank.

一致预期数据接入：
  - stock_profit_forecast_em: 机构盈利预测（营收/净利润/EPS）
  - stock_analyst_rank_em: 分析师评级分布
  - stock_analyst_detail_em: 分析师详细评级

输出 DataPoint[]，与 pipeline 体系无缝对接。
"""

from __future__ import annotations
import logging
from core.models import DataPoint

logger = logging.getLogger("v51.data.consensus")

_HAS_AKSHARE = False
try:
    import akshare as ak
    _HAS_AKSHARE = True
except ImportError:
    logger.warning("akshare not installed, consensus data unavailable")


def fetch_consensus(asset_code: str) -> list[DataPoint]:
    """Fetch consensus forecast data for a stock code.

    Returns DataPoint[] with:
      - consensus_revenue / consensus_net_profit: 机构一致预期营收/净利润
      - analyst_buy / analyst_hold / analyst_sell: 评级分布
      - analyst_target_avg: 平均目标价
    """
    if not asset_code or not _HAS_AKSHARE:
        return []

    pts: list[DataPoint] = []

    # 1. Profit forecast
    # akshare stock_profit_forecast_em 返回原始单位"元"，
    # revenue/profit 除以 1e8 转换为"亿"；若 akshare 版本升级后单位变化需对应调整
    try:
        forecast = ak.stock_profit_forecast_em(symbol=asset_code)
        if forecast is not None and not forecast.empty:
            latest = forecast.iloc[0]
            for col, name in [
                ("predictRevenue", "consensus_revenue"),
                ("predictNetProfit", "consensus_net_profit"),
                ("predictPER", "consensus_pe"),
            ]:
                val = latest.get(col)
                if val:
                    # akshare 返回单位为"元"，/1e8 转为"亿"；若 API 版本变更需调整
                    pts.append(DataPoint(
                        name=name, value=float(val) / 1e8 if "revenue" in name or "profit" in name else float(val),
                        unit="亿" if "revenue" in name or "profit" in name else "x",
                        source="akshare_consensus", source_level="L2_provider",
                        confidence="medium",
                    ))
    except Exception as e:
        logger.debug("Consensus forecast unavailable for %s: %s", asset_code, e)

    # 2. Analyst ratings
    try:
        rank = ak.stock_analyst_rank_em(symbol=asset_code)
        if rank is not None and not rank.empty:
            buy = int(rank.iloc[0].get("买入", 0) or 0)
            hold = int(rank.iloc[0].get("中性", 0) or 0)
            sell = int(rank.iloc[0].get("卖出", 0) or 0)
            total = buy + hold + sell
            if total > 0:
                pts.append(DataPoint(name="analyst_buy", value=buy, unit="家",
                                     source="akshare_analyst", source_level="L2_provider",
                                     confidence="medium"))
                pts.append(DataPoint(name="analyst_hold", value=hold, unit="家",
                                     source="akshare_analyst", source_level="L2_provider",
                                     confidence="medium"))
                pts.append(DataPoint(name="analyst_sell", value=sell, unit="家",
                                     source="akshare_analyst", source_level="L2_provider",
                                     confidence="medium"))

            # Average target price — 使用 .get() 兜底防止列名缺失 KeyError
            # akshare stock_analyst_rank_em 返回的列名含"目标价"（元）
            target_col = rank.get("目标价")
            if target_col is not None:
                targets = target_col.dropna()
                if len(targets) > 0:
                    avg_target = float(targets.mean())
                    pts.append(DataPoint(name="analyst_target_avg", value=round(avg_target, 2),
                                         unit="元", source="akshare_analyst",
                                         source_level="L2_provider", confidence="medium"))
            else:
                logger.debug("Target price column missing for %s", asset_code)
    except Exception as e:
        logger.debug("Analyst rank unavailable for %s: %s", asset_code, e)

    return pts
