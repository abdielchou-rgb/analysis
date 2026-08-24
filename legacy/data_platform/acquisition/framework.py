"""acquisition/framework.py — Unified Acquisition Framework

分层采集架构：
  1. DataSource — 基类，所有数据源继承
  2. CircuitBreaker — 熔断器，连续失败N次后自动暂停
  3. AcquisitionOrchestrator — 编排器，管理fallback链
  4. SourceRegistry — 全局源注册中心

用法:
    from legacy.data_platform.acquisition.framework import orchestrator
    # 定义fallback链：东财→新浪→mock
    result = orchestrator.fetch("600519_price",
        fallback_chain=["eastmoney", "sina", "mock"],
        params={"code": "600519"})
"""

from __future__ import annotations
import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

logger = logging.getLogger("v57.data.acquisition")


@dataclass
class DataSourceResult:
    """统一数据源返回格式"""

    success: bool = False
    data: Any = None
    source: str = ""
    confidence: str = "low"  # high / medium / low
    latency_ms: float = 0.0
    error: str = ""
    cached: bool = False
    timestamp: str = ""


@dataclass
class SourceHealth:
    """数据源健康状态"""

    source_name: str = ""
    status: str = "unknown"  # healthy / degraded / down
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    total_calls: int = 0
    success_rate_1h: float = 1.0
    avg_latency_ms: float = 0.0


class CircuitBreaker:
    """熔断器 — 连续失败N次后暂停M秒"""

    STATE_CLOSED = "closed"  # 正常
    STATE_OPEN = "open"  # 熔断
    STATE_HALF_OPEN = "half_open"  # 半开（试恢复）

    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout_s: int = 300):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    def record_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = self.STATE_CLOSED

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = self.STATE_OPEN
                logger.warning("CircuitBreaker %s OPEN after %d failures", self.name, self.failure_count)

    def allow_request(self) -> bool:
        with self._lock:
            if self.state == self.STATE_CLOSED:
                return True
            if self.state == self.STATE_OPEN:
                # 检查是否超过恢复时间
                if self.last_failure_time and time.time() - self.last_failure_time > self.recovery_timeout_s:
                    self.state = self.STATE_HALF_OPEN
                    logger.info("CircuitBreaker %s HALF_OPEN, testing recovery", self.name)
                    return True
                return False
            # HALF_OPEN — 允许一个试探请求
            return True


class DataSource:
    """数据源基类"""

    name: str = "base_source"
    priority: int = 10  # 越小优先
    health: SourceHealth = None

    def __init__(self):
        self.name = getattr(self.__class__, "name", self.__class__.__name__)
        self.health = SourceHealth(source_name=self.name)
        self.circuit_breaker = CircuitBreaker(self.name)
        self._lock = threading.Lock()

    def fetch(self, params: dict = None) -> DataSourceResult:
        """统一fetch入口，带熔断+健康记录"""
        if not self.circuit_breaker.allow_request():
            return DataSourceResult(success=False, source=self.name, error=f"CircuitBreaker OPEN ({self.name})")

        start = time.time()
        try:
            result = self._do_fetch(params or {})
            elapsed = (time.time() - start) * 1000
            result.latency_ms = elapsed
            self._record_success(elapsed)
            return result
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._record_failure()
            return DataSourceResult(
                success=False,
                source=self.name,
                error=str(e),
                latency_ms=elapsed,
            )

    def _do_fetch(self, params: dict) -> DataSourceResult:
        """子类实现此方法"""
        raise NotImplementedError

    def _record_success(self, latency_ms: float):
        with self._lock:
            self.circuit_breaker.record_success()
            self.health.last_success = datetime.now()
            self.health.consecutive_failures = 0
            self.health.total_calls += 1
            self.health.avg_latency_ms = self.health.avg_latency_ms * 0.9 + latency_ms * 0.1
            self.health.status = "healthy"

    def _record_failure(self):
        with self._lock:
            self.circuit_breaker.record_failure()
            self.health.last_failure = datetime.now()
            self.health.consecutive_failures += 1
            self.health.total_calls += 1
            if self.health.consecutive_failures >= 3:
                self.health.status = "degraded"
            if self.health.consecutive_failures >= 10:
                self.health.status = "down"

    def health_report(self) -> dict:
        return {
            "source": self.name,
            "status": self.health.status,
            "consecutive_failures": self.health.consecutive_failures,
            "total_calls": self.health.total_calls,
            "avg_latency_ms": round(self.health.avg_latency_ms, 1),
            "circuit_breaker": self.circuit_breaker.state,
        }


class SourceRegistry:
    """全局数据源注册中心"""

    def __init__(self):
        self._sources: dict[str, DataSource] = {}
        self._lock = threading.Lock()

    def register(self, source: DataSource):
        with self._lock:
            self._sources[source.name] = source
            logger.info("Source registered: %s", source.name)

    def get(self, name: str) -> Optional[DataSource]:
        return self._sources.get(name)

    def list_sources(self) -> list[str]:
        return list(self._sources.keys())

    def health_all(self) -> dict[str, dict]:
        return {name: src.health_report() for name, src in self._sources.items()}


class AcquisitionOrchestrator:
    """采集编排器 — 管理fallback链"""

    def __init__(self, registry: SourceRegistry = None):
        self.registry = registry or SourceRegistry()

    def fetch(self, key: str, fallback_chain: list[str], params: dict = None) -> DataSourceResult:
        """按fallback链依次尝试

        Args:
            key: 缓存键（用于去重）
            fallback_chain: 按优先级的源名称列表
            params: 传给数据源的参数

        Returns:
            第一个成功的结果，或最后失败的
        """
        params = params or {}
        last_error = ""

        for source_name in fallback_chain:
            source = self.registry.get(source_name)
            if source is None:
                logger.debug("Source not registered: %s", source_name)
                continue

            result = source.fetch(params)
            if result.success:
                result.source = source_name
                return result
            last_error = result.error
            logger.debug("Fallback from %s: %s", source_name, result.error)

        return DataSourceResult(
            success=False,
            source=fallback_chain[-1] if fallback_chain else "none",
            error=f"All sources failed: {last_error}",
        )

    def health_report(self) -> dict:
        return self.registry.health_all()


# 全局单例
registry = SourceRegistry()
orchestrator = AcquisitionOrchestrator(registry)
