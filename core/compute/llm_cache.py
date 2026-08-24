"""llm_cache.py — LLM 响应缓存 + 容错（2026-08-08 Python 库接入）

用 diskcache 缓存 LLM 响应（同 prompt 命中免重调，省 token）
用 tenacity 重试（LLM 调用容错，防瞬时故障）

用法：
  from core.compute.llm_cache import cached_llm, retry_llm
  content = cached_llm(prompt, key="segment3")  # 缓存命中免调
  content = retry_llm(prompt)  # 重试3次
"""

from __future__ import annotations

import logging

logger = logging.getLogger("2hao.llm_cache")


def get_cache():
    """diskcache 实例（磁盘持久化，跨进程）。优先项目 data 目录，回退 /tmp。"""
    try:
        from pathlib import Path

        import diskcache

        cache_dir = Path(__file__).resolve().parent.parent.parent / "data" / "llm_cache"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            c = diskcache.Cache(str(cache_dir))
            c.set("_init", 1)  # 验证可写
            return c
        except Exception:
            return diskcache.Cache("/tmp/2hao_llm_cache")
    except ImportError:
        return None


def cached_llm(prompt: str, cache_key: str = "", ttl: int = 86400) -> str:
    """带缓存的 LLM 调用。

    cache_key 为空时用 prompt hash。命中缓存直接返回（0 token）。
    """
    cache = get_cache()
    key = cache_key or f"prompt_{hash(prompt) % (10**8)}"
    if cache is not None:
        hit = cache.get(key)
        if hit:
            logger.info("[LLM-CACHE] 命中 %s（省一次调用）", key[:30])
            return hit
    # 实际调用
    from core.deepseek_client import call_llm

    r = call_llm([{"role": "user", "content": prompt}], temperature=0.1)
    content = r["choices"][0]["message"]["content"]
    if cache is not None:
        cache.set(key, content, expire=ttl)
    return content


def retry_llm(prompt: str, max_retries: int = 3, delay: float = 1.0) -> str:
    """带重试的 LLM 调用（tenacity）。"""
    try:
        import requests
        from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_fixed(delay),
            retry=retry_if_exception_type((requests.exceptions.RequestException, RuntimeError)),
        )
        def _call():
            from core.deepseek_client import call_llm

            r = call_llm([{"role": "user", "content": prompt}], temperature=0.1)
            return r["choices"][0]["message"]["content"]

        return _call()
    except ImportError:
        # 无 tenacity 回退简单重试
        from core.deepseek_client import call_llm

        for _ in range(max_retries):
            try:
                r = call_llm([{"role": "user", "content": prompt}], temperature=0.1)
                return r["choices"][0]["message"]["content"]
            except Exception:
                import time

                time.sleep(delay)
        raise
