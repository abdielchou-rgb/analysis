"""V50+ DataSourceManager — unified engine lifecycle, retry, circuit breaker.

统一管理所有 data engine 的：
  - 注册与优先级
  - 超时与重试策略（指数退避）
  - 熔断器（连续失败 N 次后暂停该源）  - 健康检查"""

from __future__ import annotations
import time
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger("v51.data.manager")

# 鈹€鈹€ Configuration 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


@dataclass
class EngineConfig:
    """Per-engine configuration."""

    name: str
    priority: int = 0  # lower = higher priority
    timeout: float = 10.0  # seconds
    max_retries: int = 2  # retry count before fallback
    retry_backoff: float = 1.5  # multiplicative backoff
    circuit_threshold: int = 5  # consecutive failures before circuit opens
    cooldown: float = 60.0  # seconds before trying circuit half-open


# 鈹€鈹€ Circuit Breaker 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class CircuitBreaker:
    """Simple circuit breaker: closed → open → half-open → closed."""

    def __init__(self, failure_threshold: int = 5, cooldown: float = 60.0):
        self.threshold = failure_threshold
        self.cooldown = cooldown
        self._failures = 0
        self._opened_at: float = 0.0
        self._state = "closed"  # closed | open | half_open

    @property
    def state(self) -> str:
        return self._state

    def allow(self) -> bool:
        if self._state == "closed":
            return True
        if self._state == "open":
            if time.time() - self._opened_at >= self.cooldown:
                self._state = "half_open"
                logger.info("Circuit half-open, testing...")
                return True
            return False
        # half_open: allow one probe
        return True

    def success(self) -> None:
        if self._state == "half_open":
            self._state = "closed"
            self._failures = 0
            logger.info("Circuit closed (recovered)")
        else:
            self._failures = 0

    def failure(self) -> None:
        self._failures += 1
        if self._failures >= self.threshold:
            self._state = "open"
            self._opened_at = time.time()
            logger.warning("Circuit OPEN after %d consecutive failures (cooldown %.0fs)", self._failures, self.cooldown)


# 鈹€鈹€ Data Source Manager 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class DataSourceManager:
    """Orchestrates multiple data engines with retry, timeout, and circuit breaker.

    Usage:
        mgr = DataSourceManager()
        mgr.register("eastmoney", engine, priority=0, timeout=10.0)
        mgr.register("tencent_kline", engine2, priority=1, timeout=8.0)
        result = mgr.fetch_with_fallback(DataQuery(assets=["600519"]))
    """

    def __init__(self):
        self._engines: dict[str, tuple[EngineConfig, Callable, CircuitBreaker]] = {}

    def register(
        self,
        name: str,
        fetch_fn: Callable,
        *,
        priority: int = 0,
        timeout: float = 10.0,
        max_retries: int = 2,
        circuit_threshold: int = 5,
        cooldown: float = 60.0,
    ):
        """Register an engine with its fetch function and config."""
        config = EngineConfig(
            name=name,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            circuit_threshold=circuit_threshold,
            cooldown=cooldown,
        )
        cb = CircuitBreaker(failure_threshold=circuit_threshold, cooldown=cooldown)
        self._engines[name] = (config, fetch_fn, cb)

    @property
    def registered_engines(self) -> list[str]:
        return sorted(self._engines.keys(), key=lambda n: self._engines[n][0].priority)

    def engine_health(self) -> dict[str, str]:
        """Return health status of all registered engines."""
        return {name: cb.state for name, (_, _, cb) in self._engines.items()}

    def fetch_with_fallback(self, query):
        """Fetch data with retry, timeout, circuit breaker, and fallback.

        Uses ThreadPoolExecutor + Future.result(timeout=...) for proper
        thread lifecycle management — timed-out tasks are cancelled cleanly.

        On first call, lazily registers built-in engines via _init_builtin_engines().
        """
        # Lazy initialization: register built-in engines on first fetch
        _init_builtin_engines()

        last_error: Optional[str] = None
        sorted_engines = sorted(self._engines.items(), key=lambda x: x[1][0].priority)

        for name, (config, fetch_fn, breaker) in sorted_engines:
            if not breaker.allow():
                logger.debug("Circuit open for %s, skipping", name)
                continue

            for attempt in range(config.max_retries + 1):
                try:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(fetch_fn, query)
                        try:
                            data = future.result(timeout=config.timeout)
                        except FutureTimeoutError:
                            future.cancel()
                            logger.warning(
                                "%s timed out after %.1fs (attempt %d/%d)",
                                name,
                                config.timeout,
                                attempt + 1,
                                config.max_retries + 1,
                            )
                            if attempt < config.max_retries:
                                time.sleep(config.retry_backoff**attempt)
                                continue
                            break

                        if data is not None:
                            has_data = False
                            if hasattr(data, "points") and data.points:
                                has_data = True
                            elif isinstance(data, list) and data:
                                has_data = True
                            elif data and not hasattr(data, "points"):
                                has_data = True

                            if has_data:
                                breaker.success()
                                return data

                        # Empty result, try next attempt
                        if attempt < config.max_retries:
                            time.sleep(config.retry_backoff**attempt)
                            continue
                        break

                except Exception as e:
                    last_error = str(e)
                    logger.warning("%s fetch failed (attempt %d/%d): %s", name, attempt + 1, config.max_retries + 1, e)
                    if attempt < config.max_retries:
                        time.sleep(config.retry_backoff**attempt)
                        continue
                    breaker.failure()
                    break
            else:
                breaker.failure()

        # All failed
        from legacy.data_platform.engine import DataResponse

        return DataResponse(error=f"all engines failed (last: {last_error})")

    def reset_circuits(self):
        """Reset all circuit breakers to closed state."""
        for _, (_, _, cb) in self._engines.items():
            cb._state = "closed"
            cb._failures = 0


# 鈹€鈹€ Singleton 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

data_manager = DataSourceManager()
_builtin_initialized = False


def _init_builtin_engines():
    """Lazily register built-in engines on first use.

    Called from data/__init__.py after all imports are resolved,
    avoiding circular import issues from module-level registration.
    """
    global _builtin_initialized
    if _builtin_initialized:
        return
    _builtin_initialized = True

    try:
        from legacy.data_platform.engine import EastMoneyEngine, KLineEngine, CacheEngine

        _em = EastMoneyEngine()
        _kl = KLineEngine()
        _cache = CacheEngine()

        data_manager.register("eastmoney", _em.fetch, priority=0, timeout=10.0)
        data_manager.register("tencent_kline", _kl.fetch, priority=1, timeout=8.0)
        data_manager.register("cache", _cache.fetch, priority=2, timeout=1.0)

        logger.info("V56 core engines: eastmoney, tencent_kline, cache")
    except ImportError:
        logger.warning("Could not auto-register built-in engines; data.engine unavailable")

    # V56: New multi-dimensional data engines
    try:
        from legacy.data_platform.yfinance_engine import YFinanceEngine

        _yf = YFinanceEngine()
        data_manager.register("yfinance", _yf.fetch, priority=1, timeout=15.0)
        logger.info("V56 engine: yfinance (global markets)")
    except ImportError:
        logger.debug("yfinance_engine not available")

    try:
        from legacy.data_platform.macro_engine import ChinaMacroEngine

        _macro = ChinaMacroEngine()
        data_manager.register("china_macro", _macro.fetch, priority=2, timeout=20.0)
        logger.info("V56 engine: china_macro (GDP/CPI/PMI/M2)")
    except ImportError:
        logger.debug("macro_engine not available")

    try:
        from legacy.data_platform.policy_crawler import PolicyCrawlerEngine

        _policy = PolicyCrawlerEngine()
        data_manager.register("policy_crawler", _policy.fetch, priority=3, timeout=30.0)
        logger.info("V56 engine: policy_crawler (policy/regulation)")
    except ImportError:
        logger.debug("policy_crawler not available")

    try:
        from legacy.data_platform.cvc_engine import CVCEngine

        _cvc = CVCEngine()
        data_manager.register("cvc_engine", _cvc.fetch, priority=4, timeout=10.0)
        logger.info("V56 engine: cvc_engine (CVC/primary market)")
    except ImportError:
        logger.debug("cvc_engine not available")

    try:
        from legacy.data_platform.news_engine import NewsEngine

        _news = NewsEngine()
        data_manager.register("news_engine", _news.fetch, priority=4, timeout=15.0)
        logger.info("V56 engine: news_engine (news/sentiment)")
    except ImportError:
        logger.debug("news_engine not available")

    try:
        from legacy.data_platform.satellite_engine import SatelliteEngine

        _sat = SatelliteEngine()
        data_manager.register("satellite_engine", _sat.fetch, priority=5, timeout=30.0)
        logger.info("V56 engine: satellite_engine (satellite/remote sensing framework)")
    except ImportError:
        logger.debug("satellite_engine not available")
