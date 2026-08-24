"""Unified Acquisition Framework

Layered architecture:
  - DataSource: base class for all data sources
  - AcquisitionOrchestrator: manages sources, fallback chains, circuit breaker
  - SourceRegistry: global registry of available sources

Usage:
    from data.acquisition import AcquisitionOrchestrator
    ao = AcquisitionOrchestrator()
    result = ao.fetch("realtime_600519", fallback_chain=["eastmoney", "sina", "mock"])
"""
from data.acquisition.framework import (
    DataSource, DataSourceResult, SourceHealth,
    CircuitBreaker, AcquisitionOrchestrator, SourceRegistry,
    orchestrator, registry,
)
