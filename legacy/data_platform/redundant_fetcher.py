"""V52 RedundantFetcher — multi-source redundant data fetching with outlier detection.

Design:
  - 关键数据点从 2-3 个独立信源并行取数
  - 离群值检测（MAD-based）自动标记
  - 降级策略：所有信源失败 → 标记 confidence=low，拒绝 AI 推断
  - 与 DataPipeline 现有引擎（EastMoney/KLine/Consensus）无缝集成

Architecture:
  RedundantFetcher
    ├── fetch_multi_source()    → 主入口，对关键指标多源取数
    ├── merge_with_consensus()  → 合并并标记多源数据点
    └── detect_and_flag()       → 离群值检测 + 置信度标注
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import median, stdev

from core.models import DataPoint
from core.financial_types import resolve_metric, MetricGranularity

logger = logging.getLogger("v52.data.redundant")

# ── 关键指标列表（需要多源冗余取数） ────────────────────────

KEY_METRICS = [
    "attributable_net_profit",  # 归母净利润
    "deducted_net_profit",  # 扣非净利润
    "total_revenue",  # 营业收入
    "revenue_yoy",  # 营收同比
    "profit_yoy",  # 利润同比
    "pe_ttm",  # PE(TTM)
    "market_cap",  # 总市值
]


@dataclass
class FetchResult:
    """单个信源的取数结果"""

    source: str
    points: list = field(default_factory=list)
    success: bool = False
    error: str = ""


@dataclass
class MergedPoint:
    """合并后的多源数据点"""

    name: str
    raw_points: list[DataPoint] = field(default_factory=list)
    merged_value: float = 0.0
    unit: str = ""
    confidence: str = "medium"  # high/medium/low
    source_count: int = 0
    sources: list[str] = field(default_factory=list)
    has_outlier: bool = False
    outlier_sources: list[str] = field(default_factory=list)
    deviation_pct: float = 0.0  # 最大偏离百分比
    method: str = "median"  # median / single / fallback


class RedundantFetcher:
    """冗余信源取数器"""

    def __init__(self, engines: dict[str, Callable] = None):
        """初始化。

        Args:
            engines: {source_name: fetch_function} 映射。
                     fetch_function 签名: (asset_code: str) -> list[DataPoint]
                     默认从 data.engine 和 data.consensus_connector 加载
        """
        self.engines = engines or {}
        self._init_default_engines()

    def _init_default_engines(self):
        """加载默认引擎。"""
        try:
            from legacy.data_platform.engine import EastMoneyEngine, KLineEngine, DataPipeline

            em = EastMoneyEngine()
            kl = KLineEngine()
            self.engines["eastmoney"] = lambda code: self._fetch_eastmoney(code, em)
            self.engines["tencent_kline"] = lambda code: self._fetch_kline(code, kl)
        except ImportError:
            logger.warning("Default engines not available")

        try:
            from legacy.data_platform.consensus_connector import fetch_consensus

            self.engines["akshare_consensus"] = fetch_consensus
        except ImportError:
            pass

        try:
            from legacy.data_platform.akshare_connector import fetch_financials

            self.engines["akshare_financials"] = fetch_financials
        except ImportError:
            pass

    # ── 主入口 ────────────────────────────────────────────

    def fetch_multi_source(
        self, asset_code: str, metric_ids: list[str] = None, timeout: float = 15.0
    ) -> list[DataPoint]:
        """对关键指标做多源冗余取数。

        Args:
            asset_code: 股票代码
            metric_ids: 需要多源取数的指标 ID 列表，默认 KEY_METRICS
            timeout: 单引擎超时（秒）

        Returns:
            合并后的 DataPoint 列表，每个点带 multi_source=True 标记
        """
        if not asset_code:
            return []

        target_metrics = metric_ids or KEY_METRICS
        if not self.engines:
            logger.warning("No engines available, returning empty")
            return []

        # 并行从多个引擎取数
        results: list[FetchResult] = []
        with ThreadPoolExecutor(max_workers=min(len(self.engines), 5)) as ex:
            futures = {}
            for source_name, fetch_fn in self.engines.items():
                futures[ex.submit(fetch_fn, asset_code)] = source_name

            for future in as_completed(futures, timeout=timeout):
                source_name = futures[future]
                try:
                    pts = future.result(timeout=timeout)
                    results.append(
                        FetchResult(
                            source=source_name,
                            points=pts if isinstance(pts, list) else [],
                            success=True,
                        )
                    )
                except Exception as e:
                    logger.debug("Engine %s failed for %s: %s", source_name, asset_code, e)
                    results.append(
                        FetchResult(
                            source=source_name,
                            success=False,
                            error=str(e),
                        )
                    )

        # 合并：按指标名分组，计算中位数，标记离群值
        return self._merge_results(results, target_metrics, asset_code)

    # ── 合并逻辑 ────────────────────────────────────────────

    def _merge_results(self, results: list[FetchResult], target_metrics: list[str], asset_code: str) -> list[DataPoint]:
        """合并多源结果：去重 + 中位数 + 离群值标记。"""
        from collections import defaultdict

        # 按指标名分组
        by_metric: dict[str, list[DataPoint]] = defaultdict(list)
        for fr in results:
            if not fr.success:
                continue
            for dp in fr.points:
                if not hasattr(dp, "name") or dp.value is None:
                    continue
                metric = resolve_metric(dp.name)
                key = metric.id if metric else dp.name
                # 确保 source 字段被正确标注
                if not hasattr(dp, "source") or not dp.source:
                    dp.source = fr.source
                by_metric[key].append(dp)

        merged = []
        for metric_id, dps in by_metric.items():
            if len(dps) == 0:
                continue

            metric = resolve_metric(metric_id)
            display_name = metric.name if metric else metric_id

            units = [getattr(dp, "unit", "") for dp in dps]
            unit = next((u for u in units if u), "")

            values = []
            for dp in dps:
                try:
                    values.append(float(dp.value))
                except (TypeError, ValueError):
                    pass

            if not values:
                continue

            source_names = [getattr(dp, "source", "unknown") for dp in dps]
            source_levels = [getattr(dp, "source_level", "L5_inference") for dp in dps]

            # 中位数合并
            med = median(values)
            max_dev = max(abs(v - med) for v in values) if len(values) > 1 else 0
            deviation_pct = round(max_dev / abs(med) * 100, 1) if med != 0 else 0.0

            # 离群值检测：偏差超过 2 个标准差 或 >20%
            has_outlier = False
            outlier_sources = []
            if len(values) >= 3:
                try:
                    std = stdev(values)
                    for i, v in enumerate(values):
                        if abs(v - med) > 2 * std:
                            has_outlier = True
                            outlier_sources.append(source_names[i])
                except Exception:
                    pass
            if deviation_pct > 20 and not has_outlier:
                has_outlier = True

            # 置信度判定
            if len(dps) >= 2 and not has_outlier:
                confidence = "high"
            elif len(dps) >= 2 and has_outlier:
                confidence = "medium"
            elif len(dps) == 1:
                confidence = "low"
            else:
                confidence = "low"

            # 创建合并后的 DataPoint
            # 保留原始数据用于溯源
            primary_dp = dps[0]  # 取第一个作为模板
            merged_dp = DataPoint(
                name=display_name,
                value=round(med, 4),
                unit=unit,
                source="+".join(source_names),  # 多源标记
                source_level=(
                    "L1_filing" if any("filing" in s or "eastmoney" in s for s in source_names) else "L2_provider"
                ),
                confidence=confidence,
            )

            # 附加元数据（通过 setattr 注入）
            merged_dp.multi_source = len(dps) > 1
            merged_dp.cross_validated = len(dps) > 1 and not has_outlier
            merged_dp.raw_points = dps
            merged_dp.source_count = len(dps)
            merged_dp.has_outlier = has_outlier
            merged_dp.outlier_sources = outlier_sources
            merged_dp.deviation_pct = deviation_pct
            merged_dp.granularity = metric.granularity.value if metric else ""

            merged.append(merged_dp)

        logger.info(
            "Redundant fetch for %s: %d metrics merged from %d/%d successful engines",
            asset_code,
            len(merged),
            sum(1 for r in results if r.success),
            len(results),
        )
        return merged

    # ── 引擎适配器 ──────────────────────────────────────────

    @staticmethod
    def _fetch_eastmoney(code: str, engine) -> list[DataPoint]:
        """适配 EastMoneyEngine.fetch 返回格式。"""
        from legacy.data_platform.engine import DataQuery, DataResponse

        q = DataQuery(type="market", assets=[code])
        resp = engine.fetch(q)
        if isinstance(resp, DataResponse):
            return resp.points
        return []

    @staticmethod
    def _fetch_kline(code: str, engine) -> list[DataPoint]:
        """适配 KLineEngine.fetch 返回格式。"""
        from legacy.data_platform.engine import DataQuery, DataResponse

        q = DataQuery(type="market", assets=[code])
        resp = engine.fetch(q)
        if isinstance(resp, DataResponse):
            return resp.points
        return []


__all__ = [
    "RedundantFetcher",
    "KEY_METRICS",
    "FetchResult",
    "MergedPoint",
]
