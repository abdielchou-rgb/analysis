"""Observability Module — Prometheus metrics for 2hao-analyst pipeline."""

import time
from functools import wraps
from typing import Any, Callable

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

# Custom registry for this module
REGISTRY = CollectorRegistry()

# Pipeline-level metrics
PIPELINE_RUNS = Counter(
    "pipeline_runs_total", "Total pipeline runs", ["report_type", "style", "result"], registry=REGISTRY
)

PIPELINE_DURATION = Histogram(
    "pipeline_duration_seconds",
    "Pipeline execution duration",
    ["report_type", "style"],
    buckets=[30, 60, 120, 180, 300, 600, 1200],
    registry=REGISTRY,
)

# Gate-level metrics
GATE_RUNS = Counter("gate_runs_total", "IronGate runs", ["report_type", "result"], registry=REGISTRY)

GATE_SCORE = Histogram(
    "gate_score",
    "IronGate overall score",
    ["report_type"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=REGISTRY,
)

GATE_CHECK_LATENCY = Histogram(
    "gate_check_duration_seconds",
    "Per-check latency",
    ["check_name"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
    registry=REGISTRY,
)

GATE_CHECK_RESULT = Counter(
    "gate_check_result_total", "Gate check results", ["check_name", "result"], registry=REGISTRY
)

# LLM cost tracking
LLM_COST_USD = Counter(
    "llm_cost_usd_total", "LLM API cost in USD", ["provider", "model", "operation"], registry=REGISTRY
)

LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens consumed", ["provider", "model", "direction"], registry=REGISTRY)

LLM_LATENCY = Histogram(
    "llm_request_duration_seconds",
    "LLM request latency",
    ["provider", "model", "operation"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
    registry=REGISTRY,
)

# Degradation tracking
DEGRADATION_LEVEL = Gauge(
    "pipeline_degradation_level",
    "Current pipeline degradation level (0=none, 1=visual, 2=data, 3=llm)",
    registry=REGISTRY,
)

# Data quality metrics
DATA_POINTS_COLLECTED = Counter(
    "data_points_collected_total", "Data points collected", ["source", "scope"], registry=REGISTRY
)

DATA_POINT_PROVENANCE_COMPLETE = Gauge(
    "data_point_provenance_complete",
    "Whether all data points have complete provenance (1=yes, 0=no)",
    registry=REGISTRY,
)

# Golden regression metrics
GOLDEN_REGRESSION_RUNS = Counter(
    "golden_regression_runs_total", "Golden regression test runs", ["report_type", "style", "result"], registry=REGISTRY
)

GOLDEN_GATE_SCORE = Histogram(
    "golden_gate_score",
    "Gate score for golden samples",
    ["report_type", "style"],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0],
    registry=REGISTRY,
)

# Track record metrics
BOLD_CALLS_REGISTERED = Counter(
    "bold_calls_registered_total",
    "Bold calls registered in track record",
    ["asset", "report_type", "direction"],
    registry=REGISTRY,
)

BOLD_CALL_ACCURACY = Gauge(
    "bold_call_accuracy", "Directional accuracy of bold calls", ["asset", "report_type"], registry=REGISTRY
)


# Export metrics endpoint
def get_metrics() -> bytes:
    """Get Prometheus metrics in text format."""
    return generate_latest(REGISTRY)


# Decorators for automatic instrumentation
def track_pipeline(report_type: str, style: str):
    """Decorator to track pipeline execution."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.time()
            result = None
            status = "error"
            try:
                result = func(*args, **kwargs)
                status = "ok" if (isinstance(result, dict) and result.get("status") == "ok") else "error"
                return result
            finally:
                duration = time.time() - start
                PIPELINE_RUNS.labels(report_type=report_type, style=style, result=status).inc()
                PIPELINE_DURATION.labels(report_type=report_type, style=style).observe(duration)

        return wrapper

    return decorator


def track_gate_check(check_name: str):
    """Decorator to track gate check execution."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.time()
            result = None
            passed = False
            try:
                result = func(*args, **kwargs)
                passed = getattr(result, "passed", False) if result else False
                return result
            finally:
                duration = time.time() - start
                GATE_CHECK_LATENCY.labels(check_name=check_name).observe(duration)
                GATE_CHECK_RESULT.labels(check_name=check_name, result="pass" if passed else "fail").inc()

        return wrapper

    return decorator


def track_llm_call(provider: str, model: str, operation: str):
    """Decorator to track LLM API calls."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.time()
            result = None
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                LLM_LATENCY.labels(provider=provider, model=model, operation=operation).observe(duration)

        return wrapper

    return decorator


# Context manager for LLM cost tracking
class LLMCostTracker:
    """Context manager to track LLM costs."""

    def __init__(self, provider: str, model: str, operation: str):
        self.provider = provider
        self.model = model
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        LLM_LATENCY.labels(provider=self.provider, model=self.model, operation=self.operation).observe(duration)

    def record_cost(self, cost_usd: float, input_tokens: int = 0, output_tokens: int = 0):
        """Record cost and token usage."""
        LLM_COST_USD.labels(provider=self.provider, model=self.model, operation=self.operation).inc(cost_usd)
        if input_tokens:
            LLM_TOKENS.labels(provider=self.provider, model=self.model, direction="input").inc(input_tokens)
        if output_tokens:
            LLM_TOKENS.labels(provider=self.provider, model=self.model, direction="output").inc(output_tokens)


# FastAPI metrics endpoint
def create_metrics_endpoint(app):
    """Add /metrics endpoint to FastAPI app."""
    from fastapi import Response

    @app.get("/metrics")
    async def metrics():
        return Response(content=get_metrics(), media_type="text/plain")

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "2hao-analyst"}

    return app
