"""settings.py — 运行时配置单一事实源。

P3-audit 2026-08-24：此前 15+ 个环境变量散落在 pipeline/core 各处读取，
无集中清单、无文档、默认值漂移难查。本模块收口：

约定：
1. 全部 knob 在此登记（名称/默认值/语义/消费方）
2. getter 为函数而非常量——测试用 monkeypatch.setenv 即时生效
3. 业务代码一律 `from core import settings` 后调 getter，禁止再直接
   os.environ.get 新增散点（新增 knob 必须先在此登记）

env 三段式命名沿用既有习惯，保持向后兼容。
"""

from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return default


def _bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# ── 管线编排 ──────────────────────────────────────────────────


def max_attempts() -> int:
    """写改循环迭代上限。消费方: e2e_orchestrator.run()"""
    return max(1, _int("MAX_ATTEMPTS", 3))


def report_token_budget() -> int:
    """单份报告 token 总预算（观测/熔断参考）。消费方: e2e_orchestrator"""
    return _int("REPORT_TOKEN_BUDGET", 1_000_000)


def repair_circuit_break() -> int:
    """同一失败项连续 N 轮触发全量重写熔断。消费方: e2e_orchestrator"""
    return max(1, _int("REPAIR_CIRCUIT_BREAK", 3))


def early_stop_similarity() -> float:
    """修订轮 difflib 相似度超过该值即早停。消费方: e2e_orchestrator"""
    return min(0.999, max(0.5, _float("EARLY_STOP_SIMILARITY", 0.90)))


def skeleton_mode() -> bool:
    """骨架模式（快速冒烟，跳过重注入）。消费方: e2e_orchestrator/section_writer"""
    return _bool("SKELETON_MODE")


# ── 写作 ──────────────────────────────────────────────────────


def seg_max_tokens() -> int:
    """组级写作 max_tokens。消费方: section_writer._call_llm"""
    return _int("SEG_MAX_TOKENS", 10_000)


def marvis_prefetch() -> bool:
    """P2 免费预取通道开关。消费方: section_writer._write_dimension_parallel"""
    return _bool("MARVIS_PREFETCH")


def draft_provider() -> str:
    """起草 provider 覆盖（空=按路由策略）。消费方: section_writer"""
    return os.environ.get("DRAFT_PROVIDER", "")


def dim_parallel() -> bool:
    """维度分组并行开关。消费方: section_writer"""
    return _bool("DIM_PARALLEL", True)


# ── LLM 网关 ─────────────────────────────────────────────────


def llm_http_timeout() -> int:
    """单次 HTTP 调用超时秒数。消费方: deepseek_client.call_llm"""
    return max(10, _int("LLM_HTTP_TIMEOUT", 90))


def llm_response_cache() -> bool:
    """响应缓存开关（默认关——修订循环依赖轮间采样差异）。deepseek_client"""
    return _bool("LLM_RESPONSE_CACHE")


def llm_cache_ttl() -> int:
    """响应缓存 TTL 秒数。deepseek_client"""
    return max(60, _int("LLM_CACHE_TTL", 86_400))


# ── 图表 ──────────────────────────────────────────────────────


def chart_parallel() -> bool:
    """图表进程池并行渲染开关。消费方: chart_pipeline.generate_all"""
    return _bool("CHART_PARALLEL", True)


def chart_parallel_workers() -> int:
    """图表渲染进程池大小。chart_pipeline"""
    return max(1, min(8, _int("CHART_PARALLEL_WORKERS", 4)))


# ── 数据与锚点 ────────────────────────────────────────────────


def enrich_anchor_file() -> str:
    """显式权威口径锚点 enrich 文件路径（信任通道）。analysis_mixin"""
    return os.environ.get("ENRICH_ANCHOR_FILE", "")


def min_data_density() -> float:
    """数据充足度下限。消费方: preflight/data_collector"""
    return _float("MIN_DATA_DENSITY", 0.30)
