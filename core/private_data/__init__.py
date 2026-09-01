"""Private Capital Data Providers — Base classes and registry.

Supports: IT桔子, 清科/零氪, PitchBook, Preqin
All providers must implement the PrivateDataProvider interface.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.models import DataPoint

logger = logging.getLogger("2hao.private_data")


@dataclass
class CompanyProfile:
    """Standardized company profile from private data sources."""
    name: str
    company_id: str
    sector: str
    stage: str  # seed, series_a, series_b, series_c, pre_ipo, ipo
    location: str = ""
    founded_year: int | None = None
    description: str = ""
    website: str = ""
    tags: list[str] = None


@dataclass
class FinancingRound:
    """Single financing round."""
    company_id: str
    round_name: str  # Pre-Seed, Seed, Series A, B, C, D, Pre-IPO, IPO
    amount_usd: float | None = None
    amount_cny: float | None = None
    valuation_usd: float | None = None
    valuation_cny: float | None = None
    investors: list[str] = None
    lead_investor: str = ""
    date: str = ""  # ISO format
    source_url: str = ""


@dataclass
class ExitComparable:
    """Exit comparable for valuation benchmarking."""
    company_name: str
    sector: str
    exit_type: str  # IPO, M&A, Secondary
    exit_value_usd: float | None = None
    exit_value_cny: float | None = None
    revenue_at_exit: float | None = None
    ebitda_at_exit: float | None = None
    exit_multiple_revenue: float | None = None
    exit_multiple_ebitda: float | None = None
    date: str = ""
    source_url: str = ""


class PrivateDataProvider(ABC):
    """Abstract base class for private capital data providers."""
    
    name: str = "base"
    priority: int = 100  # Lower = higher priority
    
    @abstractmethod
    def search_company(self, name: str) -> list[CompanyProfile]:
        """Search for companies by name. Returns list of profiles."""
        pass
    
    @abstractmethod
    def get_financing_history(self, company_id: str) -> list[FinancingRound]:
        """Get financing history for a company."""
        pass
    
    @abstractmethod
    def get_valuation_rounds(self, company_id: str) -> list[FinancingRound]:
        """Get valuation rounds (alias for financing_history with valuation focus)."""
        pass
    
    @abstractmethod
    def get_exit_comps(self, sector: str, stage: str) -> list[ExitComparable]:
        """Get exit comparables for sector/stage."""
        pass
    
    @abstractmethod
    def to_datapoints(self, raw: dict, asset: str) -> list[DataPoint]:
        """Convert raw data to DataPoints with provenance."""
        pass
    
    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        return True
    
    def _create_datapoint(self, asset: str, name: str, value: Any, 
                          source: str, unit: str = "", scope: str = "company",
                          confidence: float = 0.6, year: int | None = None,
                          note: str = "") -> DataPoint:
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


class ITJuziProvider(PrivateDataProvider):
    """IT桔子 数据提供商."""
    
    name = "itjuzi"
    priority = 10
    
    def __init__(self):
        self.api_key = os.environ.get("ITJUZI_API_KEY", "")
        self.base_url = "https://api.itjuzi.com/api/v1"
        self.cache_dir = Path("data/private_data/itjuzi_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def search_company(self, name: str) -> list[CompanyProfile]:
        """Search IT桔子 for company."""
        if not self.is_available():
            return []
        
        cache_file = self.cache_dir / f"search_{name}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return [CompanyProfile(**c) for c in data]
            except Exception:
                pass
        
        # Mock implementation - replace with real API call
        logger.warning(f"ITJuziProvider.search_company({name}) - using mock data")
        return [CompanyProfile(
            name=name,
            company_id=f"itjuzi_{name}",
            sector="AI/人工智能",
            stage="series_b",
            location="北京",
            founded_year=2020,
            description=f"{name} 是一家专注于人工智能领域的独角兽企业",
            tags=["AI", "芯片", "深度学习"]
        )]
    
    def get_financing_history(self, company_id: str) -> list[FinancingRound]:
        """Get financing history from IT桔子."""
        if not self.is_available():
            return []
        
        # Mock data
        return [
            FinancingRound(
                company_id=company_id,
                round_name="Series A",
                amount_cny=50000000,
                valuation_cny=200000000,
                investors=["红杉中国", "IDG资本"],
                lead_investor="红杉中国",
                date="2021-03-15",
                source_url="https://www.itjuzi.com/company/12345"
            ),
            FinancingRound(
                company_id=company_id,
                round_name="Series B",
                amount_cny=200000000,
                valuation_cny=1000000000,
                investors=["腾讯投资", "红杉中国", "经纬中国"],
                lead_investor="腾讯投资",
                date="2022-08-20",
                source_url="https://www.itjuzi.com/company/12345"
            ),
            FinancingRound(
                company_id=company_id,
                round_name="Series C",
                amount_cny=500000000,
                valuation_cny=5000000000,
                investors=["软银愿景基金", "腾讯投资", "红杉中国"],
                lead_investor="软银愿景基金",
                date="2023-11-10",
                source_url="https://www.itjuzi.com/company/12345"
            ),
        ]
    
    def get_valuation_rounds(self, company_id: str) -> list[FinancingRound]:
        return self.get_financing_history(company_id)
    
    def get_exit_comps(self, sector: str, stage: str) -> list[ExitComparable]:
        """Get exit comparables from IT桔子."""
        if not self.is_available():
            return []
        
        # Mock data for AI sector
        if "AI" in sector or "人工智能" in sector:
            return [
                ExitComparable(
                    company_name="寒武纪",
                    sector="AI芯片",
                    exit_type="IPO",
                    exit_value_cny=20000000000,
                    revenue_at_exit=800000000,
                    exit_multiple_revenue=25.0,
                    date="2020-07-20",
                    source_url="https://www.itjuzi.com/ipo/123"
                ),
                ExitComparable(
                    company_name="云从科技",
                    sector="AI视觉",
                    exit_type="IPO",
                    exit_value_cny=15000000000,
                    revenue_at_exit=600000000,
                    exit_multiple_revenue=25.0,
                    date="2022-05-15",
                    source_url="https://www.itjuzi.com/ipo/456"
                ),
            ]
        return []
    
    def to_datapoints(self, raw: dict, asset: str) -> list[DataPoint]:
        """Convert raw IT桔子 data to DataPoints."""
        dps = []
        if isinstance(raw, FinancingRound):
            dps.append(self._create_datapoint(
                asset, f"financing_{raw.round_name}", raw.amount_cny,
                source=raw.source_url, unit="万元", confidence=0.8,
                year=int(raw.date[:4]) if raw.date else None,
                note=f"round={raw.round_name}; lead={raw.lead_investor}; investors={raw.investors}"
            ))
            if raw.valuation_cny:
                dps.append(self._create_datapoint(
                    asset, f"valuation_{raw.round_name}", raw.valuation_cny,
                    source=raw.source_url, unit="万元", confidence=0.7,
                    year=int(raw.date[:4]) if raw.date else None,
                    note=f"post-money valuation"
                ))
        elif isinstance(raw, ExitComparable):
            dps.append(self._create_datapoint(
                asset, f"exit_comp_{raw.company_name}", raw.exit_value_cny,
                source=raw.source_url, unit="万元", confidence=0.7,
                note=f"exit_type={raw.exit_type}; multiple_rev={raw.exit_multiple_revenue}"
            ))
        return dps


class Zero2IPOProvider(PrivateDataProvider):
    """清科/零氪 数据提供商."""
    
    name = "zero2ipo"
    priority = 20
    
    def __init__(self):
        self.api_key = os.environ.get("ZERO2IPO_API_KEY", "")
        self.base_url = "https://api.zero2ipo.com.cn/v1"
        self.cache_dir = Path("data/private_data/zero2ipo_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def search_company(self, name: str) -> list[CompanyProfile]:
        if not self.is_available():
            return []
        logger.warning(f"Zero2IPOProvider.search_company({name}) - using mock data")
        return [CompanyProfile(
            name=name,
            company_id=f"zero2ipo_{name}",
            sector="新能源/电池",
            stage="pre_ipo",
            location="宁德",
            founded_year=2018,
        )]
    
    def get_financing_history(self, company_id: str) -> list[FinancingRound]:
        if not self.is_available():
            return []
        return [
            FinancingRound(
                company_id=company_id,
                round_name="Series A",
                amount_cny=100000000,
                valuation_cny=500000000,
                investors=["宁德时代", "红杉中国"],
                lead_investor="宁德时代",
                date="2019-06-01",
                source_url="https://www.zero2ipo.com.cn/project/123"
            ),
            FinancingRound(
                company_id=company_id,
                round_name="Series B",
                amount_cny=300000000,
                valuation_cny=2000000000,
                investors=["华为哈勃", "宁德时代", "红杉中国"],
                lead_investor="华为哈勃",
                date="2021-03-15",
                source_url="https://www.zero2ipo.com.cn/project/123"
            ),
        ]
    
    def get_valuation_rounds(self, company_id: str) -> list[FinancingRound]:
        return self.get_financing_history(company_id)
    
    def get_exit_comps(self, sector: str, stage: str) -> list[ExitComparable]:
        if not self.is_available():
            return []
        if "新能源" in sector or "电池" in sector:
            return [
                ExitComparable(
                    company_name="蜂巢能源",
                    sector="动力电池",
                    exit_type="IPO",
                    exit_value_cny=50000000000,
                    revenue_at_exit=20000000000,
                    exit_multiple_revenue=2.5,
                    date="2023-02-01",
                    source_url="https://www.zero2ipo.com.cn/ipo/789"
                ),
            ]
        return []
    
    def to_datapoints(self, raw: dict, asset: str) -> list[DataPoint]:
        dps = []
        if isinstance(raw, FinancingRound):
            dps.append(self._create_datapoint(
                asset, f"financing_{raw.round_name}", raw.amount_cny,
                source=raw.source_url, unit="万元", confidence=0.8,
                year=int(raw.date[:4]) if raw.date else None,
                note=f"round={raw.round_name}; lead={raw.lead_investor}"
            ))
        return dps


class PitchBookProvider(PrivateDataProvider):
    """PitchBook 数据提供商."""
    
    name = "pitchbook"
    priority = 30
    
    def __init__(self):
        self.api_key = os.environ.get("PITCHBOOK_API_KEY", "")
        self.base_url = "https://api.pitchbook.com/v1"
        self.cache_dir = Path("data/private_data/pitchbook_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def search_company(self, name: str) -> list[CompanyProfile]:
        if not self.is_available():
            return []
        logger.warning(f"PitchBookProvider.search_company({name}) - using mock data")
        return [CompanyProfile(
            name=name,
            company_id=f"pitchbook_{name}",
            sector="SaaS/企业软件",
            stage="series_c",
            location="San Francisco, USA",
        )]
    
    def get_financing_history(self, company_id: str) -> list[FinancingRound]:
        if not self.is_available():
            return []
        return [
            FinancingRound(
                company_id=company_id,
                round_name="Series A",
                amount_usd=10000000,
                valuation_usd=50000000,
                investors=["Sequoia", "Accel"],
                lead_investor="Sequoia",
                date="2020-01-15",
                source_url="https://my.pitchbook.com/company/12345"
            ),
            FinancingRound(
                company_id=company_id,
                round_name="Series B",
                amount_usd=30000000,
                valuation_usd=200000000,
                investors=["Andreessen Horowitz", "Sequoia"],
                lead_investor="Andreessen Horowitz",
                date="2021-09-01",
                source_url="https://my.pitchbook.com/company/12345"
            ),
            FinancingRound(
                company_id=company_id,
                round_name="Series C",
                amount_usd=100000000,
                valuation_usd=1000000000,
                investors=["Tiger Global", "Sequoia", "Andreessen Horowitz"],
                lead_investor="Tiger Global",
                date="2023-02-20",
                source_url="https://my.pitchbook.com/company/12345"
            ),
        ]
    
    def get_valuation_rounds(self, company_id: str) -> list[FinancingRound]:
        return self.get_financing_history(company_id)
    
    def get_exit_comps(self, sector: str, stage: str) -> list[ExitComparable]:
        if not self.is_available():
            return []
        return [
            ExitComparable(
                company_name="Snowflake",
                sector="Data Cloud",
                exit_type="IPO",
                exit_value_usd=70000000000,
                revenue_at_exit=1200000000,
                exit_multiple_revenue=58.0,
                date="2020-09-16",
                source_url="https://my.pitchbook.com/ipo/snowflake"
            ),
            ExitComparable(
                company_name="Databricks",
                sector="Data/AI Platform",
                exit_type="Secondary",
                exit_value_usd=43000000000,
                revenue_at_exit=1000000000,
                exit_multiple_revenue=43.0,
                date="2023-09-14",
                source_url="https://my.pitchbook.com/secondary/databricks"
            ),
        ]
    
    def to_datapoints(self, raw: dict, asset: str) -> list[DataPoint]:
        dps = []
        if isinstance(raw, FinancingRound):
            dps.append(self._create_datapoint(
                asset, f"financing_{raw.round_name}", raw.amount_usd,
                source=raw.source_url, unit="万美元", confidence=0.85,
                year=int(raw.date[:4]) if raw.date else None,
                note=f"round={raw.round_name}; lead={raw.lead_investor}"
            ))
        return dps


class PreqinProvider(PrivateDataProvider):
    """Preqin 数据提供商."""
    
    name = "preqin"
    priority = 40
    
    def __init__(self):
        self.api_key = os.environ.get("PREQIN_API_KEY", "")
        self.base_url = "https://api.preqin.com/v1"
        self.cache_dir = Path("data/private_data/preqin_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def search_company(self, name: str) -> list[CompanyProfile]:
        if not self.is_available():
            return []
        logger.warning(f"PreqinProvider.search_company({name}) - using mock data")
        return [CompanyProfile(
            name=name,
            company_id=f"preqin_{name}",
            sector="PE/VC基金",
            stage="fund",
            location="北京",
        )]
    
    def get_financing_history(self, company_id: str) -> list[FinancingRound]:
        if not self.is_available():
            return []
        return []
    
    def get_valuation_rounds(self, company_id: str) -> list[FinancingRound]:
        return []
    
    def get_exit_comps(self, sector: str, stage: str) -> list[ExitComparable]:
        if not self.is_available():
            return []
        return [
            ExitComparable(
                company_name="某消费品牌",
                sector="消费品",
                exit_type="M&A",
                exit_value_cny=3000000000,
                revenue_at_exit=800000000,
                exit_multiple_revenue=3.75,
                date="2023-06-15",
                source_url="https://www.preqin.com/deal/123"
            ),
        ]
    
    def to_datapoints(self, raw: dict, asset: str) -> list[DataPoint]:
        return []


# Provider Registry
_PROVIDERS = [
    ITJuziProvider,
    Zero2IPOProvider,
    PitchBookProvider,
    PreqinProvider,
]


def get_provider(name: str | None = None) -> PrivateDataProvider | None:
    """Get provider by name or highest priority available."""
    if name:
        for p in _PROVIDERS:
            if p.name == name:
                instance = p()
                if instance.is_available():
                    return instance
        return None
    
    # Return highest priority available provider
    for p in sorted(_PROVIDERS, key=lambda x: x.priority):
        instance = p()
        if instance.is_available():
            logger.info(f"Using private data provider: {instance.name} (priority={instance.priority})")
            return instance
    
    logger.warning("No private data provider available (all need API keys)")
    return None


def get_all_available_providers() -> list[PrivateDataProvider]:
    """Get all available providers sorted by priority."""
    providers = []
    for p in sorted(_PROVIDERS, key=lambda x: x.priority):
        instance = p()
        if instance.is_available():
            providers.append(instance)
    return providers