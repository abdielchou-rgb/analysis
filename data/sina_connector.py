"""Sina Connector — Sina Finance API-backed data source (EastMoney替代方案)

EastMoney API 被墙，Sina 接口可正常使用:
  - stock_financial_abstract(): 季度财务指标（营收/利润/资产/毛利率等 80+ 指标）
  - stock_zh_a_daily(): 日线行情（开高低收+量额，qfq 前复权）

用法:
    from data.sina_connector import SinaConnector
    conn = SinaConnector()
    pts = conn.fetch_financials("688469")       # → list[DataPoint]
    price_df = conn.fetch_price_history("688469")  # → DataFrame
"""

from __future__ import annotations
import logging
from typing import Optional
from core.models import DataPoint

logger = logging.getLogger("v51.data.sina")

_HAS_AKSHARE = False
try:
    import akshare as ak
    _HAS_AKSHARE = True
except ImportError:
    logger.warning("akshare not installed, Sina connector unavailable")


# 财务指标映射：stock_financial_abstract 行名 → DataPoint name
FINANCIAL_INDICATOR_MAP = {
    "归母净利润": "net_profit",
    "营业总收入": "revenue",
    "营业成本": "cost",
    "营业利润": "operating_profit",
    "利润总额": "total_profit",
    "每股收益": "eps",
    "每股净资产": "bps",
    "每股经营现金流": "ocf_per_share",
    "毛利率": "gross_margin",
    "净利率": "net_margin",
    "净资产收益率(ROE)": "roe",
    "总资产收益率(ROA)": "roa",
    "总资产": "total_assets",
    "总负债": "total_liabilities",
    "股东权益合计": "total_equity",
    "资产负债率": "debt_ratio",
    "经营活动现金流": "operating_cf",
    "投资活动现金流": "investing_cf",
    "筹资活动现金流": "financing_cf",
    "研发费用": "rnd_expense",
    "营业收入增长率": "revenue_yoy",
    "归母净利润增长率": "np_yoy",
    "扣非净利润": "deducted_np",
    "基本每股收益": "basic_eps",
    "加权平均净资产收益率": "weighted_roe",
}

# 需要金额单位转换（元→亿）的指标
AMOUNT_INDICATORS = {
    "net_profit", "revenue", "cost", "operating_profit", "total_profit",
    "total_assets", "total_liabilities", "total_equity",
    "operating_cf", "investing_cf", "financing_cf", "rnd_expense",
    "deducted_np",
}


class SinaConnector:
    """Sina Finance 数据连接器 — EastMoney 的替代方案"""

    @staticmethod
    def _normalize_code(asset_code: str) -> str:
        """将 688469 转换为新浪格式 sh688469"""
        code = asset_code.strip().replace(".SH", "").replace(".SZ", "")
        if code.startswith("6"):
            prefix = "sh"
        elif code.startswith(("0", "3")):
            prefix = "sz"
        else:
            prefix = "sh"  # default
        return f"{prefix}{code}"

    def fetch_financials(self, asset_code: str) -> list[DataPoint]:
        """获取季度财务指标（最近4个季度 + TTM对比）

        从 stock_financial_abstract 提取关键指标，生成 DataPoint 列表。
        """
        if not _HAS_AKSHARE:
            logger.warning("akshare not available")
            return []

        try:
            df = ak.stock_financial_abstract(symbol=asset_code)
            if df is None or df.empty:
                logger.warning("stock_financial_abstract returned empty for %s", asset_code)
                return []
        except Exception as e:
            logger.warning("stock_financial_abstract failed for %s: %s", asset_code, e)
            return []

        pts: list[DataPoint] = []

        # 获取季度列名（排除了 '选项'和'指标'列）
        period_cols = [c for c in df.columns if c not in ("选项", "指标")]
        # 取最近几个季度
        recent_cols = period_cols[:4]  # 最近4个季度

        for _, row in df.iterrows():
            indicator = row.get("指标", "")
            dp_name = FINANCIAL_INDICATOR_MAP.get(indicator)
            if not dp_name:
                continue

            is_amount = dp_name in AMOUNT_INDICATORS

            # 为每个有数据的季度创建 DataPoint
            for col in recent_cols:
                val = row.get(col)
                if val is None or val == 0:
                    continue
                try:
                    val_f = float(val)
                except (TypeError, ValueError):
                    continue

                if is_amount:
                    # 元 → 亿
                    val_f = val_f / 1e8
                    unit = "亿"
                elif dp_name in ("eps", "bps", "basic_eps", "ocf_per_share"):
                    unit = "元"
                elif dp_name in ("gross_margin", "net_margin", "roe", "roa",
                                 "debt_ratio", "revenue_yoy", "np_yoy", "weighted_roe"):
                    unit = "%"
                else:
                    unit = ""

                pts.append(DataPoint(
                    name=f"{dp_name}_{col}",
                    value=val_f,
                    unit=unit,
                    source="sina_finance",
                    source_level="L1_filing",
                    confidence="high",
                ))

        # 追加最新季度快照（无后缀，方便图表提取）
        if recent_cols:
            latest_col = recent_cols[0]
            for _, row in df.iterrows():
                indicator = row.get("指标", "")
                dp_name = FINANCIAL_INDICATOR_MAP.get(indicator)
                if not dp_name:
                    continue
                val = row.get(latest_col)
                if val is None:
                    continue
                try:
                    val_f = float(val)
                except (TypeError, ValueError):
                    continue
                is_amount = dp_name in AMOUNT_INDICATORS
                if is_amount:
                    val_f = val_f / 1e8
                    unit = "亿"
                else:
                    unit = "%" if dp_name in ("gross_margin", "net_margin") else ""
                pts.append(DataPoint(
                    name=dp_name,
                    value=val_f,
                    unit=unit,
                    source="sina_finance_latest",
                    source_level="L1_filing",
                    confidence="high",
                ))

        logger.info("Sina: fetched %d financial data points for %s", len(pts), asset_code)
        return pts

    def fetch_price_history(self, asset_code: str, days: int = 250) -> Optional[list[DataPoint]]:
        """获取日线行情数据，生成带时间戳的 DataPoint 列表。

        每个交易日生成 price_close_{date} 形式的 DataPoint，
        可用于图表集成模块构建时间序列。
        """
        if not _HAS_AKSHARE:
            return None

        code = self._normalize_code(asset_code)
        try:
            df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")
            if df is None or df.empty:
                return None

            # 取最近 days 行
            df = df.tail(days)

            pts: list[DataPoint] = []
            for _, row in df.iterrows():
                date_str = str(row["date"])[:10]  # "2026-07-28"
                close = float(row["close"])
                pts.append(DataPoint(
                    name=f"price_close_{date_str}",
                    value=close,
                    unit="元",
                    source="sina_daily",
                    source_level="L2_provider",
                    confidence="high",
                ))

            logger.info("Sina: fetched %d daily price points for %s", len(pts), asset_code)
            return pts
        except Exception as e:
            logger.warning("Sina price history failed for %s: %s", asset_code, e)
            return None

    def fetch_realtime(self, asset_code: str) -> list[DataPoint]:
        """获取实时行情快照（从日线最新一行提取）"""
        pts: list[DataPoint] = []

        code = self._normalize_code(asset_code)
        try:
            df = ak.stock_zh_a_daily(symbol=code, adjust="qfq")
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                pts.append(DataPoint(
                    name="realtime_price",
                    value=float(latest["close"]),
                    unit="元",
                    source="sina_realtime",
                    source_level="L2_provider",
                    confidence="high",
                ))
                # 涨跌幅 (用最近两日)
                if len(df) >= 2:
                    prev_close = float(df.iloc[-2]["close"])
                    chg_pct = (float(latest["close"]) - prev_close) / prev_close * 100
                    pts.append(DataPoint(
                        name="realtime_change_pct",
                        value=round(chg_pct, 2),
                        unit="%",
                        source="sina_realtime",
                        source_level="L2_provider",
                        confidence="high",
                    ))
        except Exception as e:
            logger.debug("Sina realtime failed for %s: %s", asset_code, e)

        return pts


# 全局单例
_sina_connector: Optional[SinaConnector] = None


def get_sina_connector() -> SinaConnector:
    global _sina_connector
    if _sina_connector is None:
        _sina_connector = SinaConnector()
    return _sina_connector
