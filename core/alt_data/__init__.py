"""Alternative Data Connectors — 非传统数据源接口.

支持:
- 卫星/夜间灯光/港口吞吐
- 信用卡消费面板
- App Store/应用商店下载量
- 供应链/海关/船运单数据

所有连接器统一输出 DataPoint 格式，带完整溯源。
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.models import DataPoint

logger = logging.getLogger("2hao.alt_data")


@dataclass
class AltDataConfig:
    """Alternative data source configuration."""

    name: str
    api_key_env: str
    base_url: str
    rate_limit: int = 60  # requests per minute
    enabled: bool = True


class AltDataConnector(ABC):
    """Base class for alternative data connectors."""

    def __init__(self, config: AltDataConfig):
        self.config = config
        self.api_key = os.environ.get(config.api_key_env, "")
        self.cache_dir = Path("data/alt_data") / config.name
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def get_signals(self, asset: str, signal_types: list[str]) -> list[DataPoint]:
        """Get alternative data signals for an asset."""
        pass

    def is_available(self) -> bool:
        return self.config.enabled and bool(self.api_key)

    def _create_datapoint(
        self,
        asset: str,
        name: str,
        value: Any,
        source: str,
        unit: str = "",
        scope: str = "company",
        confidence: float = 0.6,
        year: int | None = None,
        note: str = "",
    ) -> DataPoint:
        """Helper to create DataPoint with full provenance."""
        excerpt = f"{name}: {value}"
        return DataPoint(
            name=f"{asset}_{name}",
            value=value,
            source=source,
            access_ts=datetime.now(timezone.utc).isoformat(),
            excerpt_sha256=__import__("hashlib").sha256(excerpt.encode()).hexdigest(),
            confidence=confidence,
            scope=scope,
            unit=unit,
            year=year,
            note=note,
        )


class SatelliteConnector(AltDataConnector):
    """卫星/夜间灯光/港口吞吐数据连接器.

    数据源示例:
    - NASA VIIRS 夜间灯光
    - Planet/Satellogic 高分辨率影像
    - Orbital Insight 港口/停车场/油罐监测
    - SpaceKnow 基建/工厂活跃度
    """

    def __init__(self):
        config = AltDataConfig(
            name="satellite",
            api_key_env="SATELLITE_API_KEY",
            base_url="https://api.orbitalinsight.com/v1",
            rate_limit=30,
        )
        super().__init__(config)

    def get_signals(self, asset: str, signal_types: list[str]) -> list[DataPoint]:
        """Get satellite-derived signals."""
        if not self.is_available():
            return self._get_mock_signals(asset, signal_types)

        # Real implementation would call API
        logger.warning(f"SatelliteConnector.get_signals({asset}) - using mock data")
        return self._get_mock_signals(asset, signal_types)

    def _get_mock_signals(self, asset: str, signal_types: list[str]) -> list[DataPoint]:
        """Mock satellite signals for development."""
        dps = []
        current_year = datetime.now().year

        for signal in signal_types:
            if signal == "night_lights":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "night_lights_index",
                        1.15,
                        source="NASA VIIRS (mock)",
                        unit="指数",
                        confidence=0.7,
                        year=current_year,
                        note="夜间灯光指数同比+15%，暗示经济活跃度提升",
                    )
                )
            elif signal == "port_throughput":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "port_throughput_teu",
                        2450000,
                        source="Orbital Insight (mock)",
                        unit="TEU",
                        confidence=0.75,
                        year=current_year,
                        note="主要港口吞吐量环比+8%",
                    )
                )
            elif signal == "factory_activity":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "factory_activity_index",
                        1.08,
                        source="SpaceKnow (mock)",
                        unit="指数",
                        confidence=0.7,
                        year=current_year,
                        note="工厂区域车辆/灯光活跃度指数",
                    )
                )
            elif signal == "oil_storage":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "oil_storage_utilization",
                        0.72,
                        source="Satellite imagery (mock)",
                        unit="%",
                        confidence=0.8,
                        year=current_year,
                        note="油罐阴影分析显示库存利用率72%",
                    )
                )
            elif signal == "parking_lots":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "parking_lot_occupancy",
                        0.85,
                        source="Satellite imagery (mock)",
                        unit="%",
                        confidence=0.7,
                        year=current_year,
                        note="商场/工厂停车场占用率85%，暗示客流/产能高",
                    )
                )

        return dps


class CreditCardConnector(AltDataConnector):
    """信用卡消费面板数据连接器.

    数据源示例:
    - Second Measure / Earnest Research (美股)
    - 中国银联/网联/各大行消费大数据 (A股)
    - 百度/阿里/腾讯消费地图
    """

    def __init__(self):
        config = AltDataConfig(
            name="credit_card",
            api_key_env="CREDIT_CARD_API_KEY",
            base_url="https://api.secondmeasure.com/v1",
            rate_limit=20,
        )
        super().__init__(config)

    def get_signals(self, asset: str, signal_types: list[str]) -> list[DataPoint]:
        if not self.is_available():
            return self._get_mock_signals(asset, signal_types)

        logger.warning(f"CreditCardConnector.get_signals({asset}) - using mock data")
        return self._get_mock_signals(asset, signal_types)

    def _get_mock_signals(self, asset: str, signal_types: list[str]) -> list[DataPoint]:
        dps = []
        current_year = datetime.now().year

        for signal in signal_types:
            if signal == "consumer_spending":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "consumer_spending_yoy",
                        0.12,
                        source="Credit card panel (mock)",
                        unit="%",
                        confidence=0.75,
                        year=current_year,
                        note="信用卡消费同比+12%，高于行业平均",
                    )
                )
            elif signal == "transaction_volume":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "transaction_volume",
                        3.2e9,
                        source="Credit card panel (mock)",
                        unit="元",
                        confidence=0.7,
                        year=current_year,
                        note="交易金额环比增长",
                    )
                )
            elif signal == "customer_retention":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "customer_retention_rate",
                        0.78,
                        source="Credit card panel (mock)",
                        unit="%",
                        confidence=0.7,
                        year=current_year,
                        note="用户留存率78%，行业领先",
                    )
                )
            elif signal == "average_ticket":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "average_ticket_size",
                        245,
                        source="Credit card panel (mock)",
                        unit="元",
                        confidence=0.7,
                        year=current_year,
                        note="客单价同比+5%",
                    )
                )

        return dps


class AppStoreConnector(AltDataConnector):
    """App Store/应用商店下载量连接器.

    数据源示例:
    - Sensor Tower / data.ai (原App Annie)
    - AppMagic / Qimai (七麦数据)
    - 点点数据 / 蝉大师 (国内)
    """

    def __init__(self):
        config = AltDataConfig(
            name="app_store",
            api_key_env="APP_STORE_API_KEY",
            base_url="https://api.sensortower.com/v1",
            rate_limit=30,
        )
        super().__init__(config)

    def get_signals(self, asset: str, signal_types: list[str]) -> list[DataPoint]:
        if not self.is_available():
            return self._get_mock_signals(asset, signal_types)

        logger.warning(f"AppStoreConnector.get_signals({asset}) - using mock data")
        return self._get_mock_signals(asset, signal_types)

    def _get_mock_signals(self, asset: str, signal_types: list[str]) -> list[DataPoint]:
        dps = []
        current_year = datetime.now().year

        for signal in signal_types:
            if signal == "app_downloads":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "app_downloads_monthly",
                        2500000,
                        source="Sensor Tower (mock)",
                        unit="次",
                        confidence=0.8,
                        year=current_year,
                        note="月度下载量250万，环比+15%",
                    )
                )
            elif signal == "mau":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "mau",
                        8500000,
                        source="Sensor Tower (mock)",
                        unit="用户",
                        confidence=0.75,
                        year=current_year,
                        note="月活用户850万，同比+22%",
                    )
                )
            elif signal == "revenue":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "app_revenue_monthly",
                        12000000,
                        source="Sensor Tower (mock)",
                        unit="元",
                        confidence=0.7,
                        year=current_year,
                        note="月度流水1200万，环比+8%",
                    )
                )
            elif signal == "ranking":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "app_store_ranking",
                        15,
                        source="Qimai (mock)",
                        unit="名",
                        confidence=0.8,
                        year=current_year,
                        note="分类榜单第15名，较上月上升10位",
                    )
                )

        return dps


class SupplyChainConnector(AltDataConnector):
    """供应链/海关/船运单数据连接器.

    数据源示例:
    - Panjiva / ImportGenius (海关数据)
    - 项目44 / FourKites (实时物流追踪)
    - 中国海关总署公开数据
    - Flexport / Freightos 波罗的海指数
    """

    def __init__(self):
        config = AltDataConfig(
            name="supply_chain",
            api_key_env="SUPPLY_CHAIN_API_KEY",
            base_url="https://api.panjiva.com/v1",
            rate_limit=20,
        )
        super().__init__(config)

    def get_signals(self, asset: str, signal_types: list[str]) -> list[DataPoint]:
        if not self.is_available():
            return self._get_mock_signals(asset, signal_types)

        logger.warning(f"SupplyChainConnector.get_signals({asset}) - using mock data")
        return self._get_mock_signals(asset, signal_types)

    def _get_mock_signals(self, asset: str, signal_types: list[str]) -> list[DataPoint]:
        dps = []
        current_year = datetime.now().year

        for signal in signal_types:
            if signal == "import_volume":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "import_volume_teu",
                        15000,
                        source="Panjiva (mock)",
                        unit="TEU",
                        confidence=0.75,
                        year=current_year,
                        note="进口集装箱量同比+18%",
                    )
                )
            elif signal == "export_volume":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "export_volume_teu",
                        22000,
                        source="Panjiva (mock)",
                        unit="TEU",
                        confidence=0.75,
                        year=current_year,
                        note="出口集装箱量环比+12%",
                    )
                )
            elif signal == "shipping_cost":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "shipping_cost_per_teu",
                        2800,
                        source="Freightos Baltic Index (mock)",
                        unit="美元/TEU",
                        confidence=0.8,
                        year=current_year,
                        note="波罗的海指数回落至2800/TEU",
                    )
                )
            elif signal == "supplier_diversity":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "supplier_count",
                        47,
                        source="Customs data (mock)",
                        unit="家",
                        confidence=0.7,
                        year=current_year,
                        note="一级供应商47家，HHI指数0.15(分散)",
                    )
                )
            elif signal == "inventory_turnover":
                dps.append(
                    self._create_datapoint(
                        asset,
                        "inventory_turnover_days",
                        42,
                        source="Supply chain analytics (mock)",
                        unit="天",
                        confidence=0.7,
                        year=current_year,
                        note="库存周转天数42天，优于行业均值55天",
                    )
                )

        return dps


# Registry
_CONNECTORS = {
    "satellite": SatelliteConnector,
    "credit_card": CreditCardConnector,
    "app_store": AppStoreConnector,
    "supply_chain": SupplyChainConnector,
}


def get_connector(name: str) -> Optional[AltDataConnector]:
    """Get connector by name."""
    if name in _CONNECTORS:
        return _CONNECTORS[name]()
    return None


def get_all_available_connectors() -> list[AltDataConnector]:
    """Get all available connectors."""
    connectors = []
    for name, cls in _CONNECTORS.items():
        conn = cls()
        if conn.is_available():
            connectors.append(conn)
    return connectors


def fetch_alt_data(asset: str, signal_types: dict[str, list[str]]) -> list[DataPoint]:
    """Fetch alternative data from multiple connectors.

    Args:
        asset: Asset name
        signal_types: Dict of connector_name -> list of signal_types

    Returns:
        List of DataPoints with provenance
    """
    all_dps = []
    for connector_name, signals in signal_types.items():
        connector = get_connector(connector_name)
        if connector:
            try:
                dps = connector.get_signals(asset, signals)
                all_dps.extend(dps)
                logger.info(f"AltData [{connector_name}]: fetched {len(dps)} signals for {asset}")
            except Exception as e:
                logger.warning(f"AltData [{connector_name}] failed for {asset}: {e}")
    return all_dps
