"""LLM 响应缓存（LLM_RESPONSE_CACHE 门控）单元测试。

P3-audit 2026-08-24：llm_cache.py 此前零消费者——现网关级内嵌 call_llm，
同 (messages, model, temperature, max_tokens) 命中免重调。
默认关闭：写作修订循环依赖轮间采样差异，缓存仅用于批量/开发迭代场景。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import uuid

import pytest


def _tok(tag: str) -> str:
    """每次运行唯一 token——磁盘缓存跨 pytest 运行持久化，键必须不可复用。"""
    return f"cache-test-{tag}-{uuid.uuid4().hex[:10]}"


@pytest.fixture()
def fake_provider(monkeypatch):
    """注册假 provider 并拦截 HTTP 层。"""
    import core.deepseek_client as dc
    from core.deepseek_client import ProviderConfig

    dc._registry._providers.clear()
    dc._registry._providers["fake"] = ProviderConfig(
        name="fake", base_url="http://fake.local/v1", api_key="k", models=["m"], priority=0
    )
    counter = {"post": 0}

    class _R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            # 2026-09-14 审计修复：响应体必须 ≥50 字符。
            # 原因：_response_cache_set（core/deepseek_client.py）有防污染门槛——
            # 2026-09-04 加入，因为 zhipu 429 限流期间曾把截断/乱码响应写入缓存，
            # 之后同 prompt 恒命中坏缓存 → 写作修订 3 轮返回同一截断文本 →
            # Gate 恒 0.658。门槛：content 非空且 ≥50 字符才入缓存。
            # 本夹具原先返回 "resp-N"（6 字符），被门槛**正当拒绝** → 缓存永不
            # 命中 → test_cache_hit_saves_second_call 恒失败（本测试写于 08-24，
            # 早于 09-04 的门槛，属典型"测试未跟随实现演进"）。
            # 注意：请勿为迁就测试而放宽该门槛——它保护的是线上报告质量。
            _body = f"resp-{counter['post']}-" + "x" * 60
            return {"choices": [{"message": {"content": _body}}], "usage": {}}

    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: (counter.__setitem__("post", counter["post"] + 1), _R())[1])
    monkeypatch.setattr(requests, "get", lambda *a, **k: _R())
    yield dc, counter
    dc._registry._providers.clear()


@pytest.mark.unit
def test_cache_hit_saves_second_call(fake_provider, monkeypatch):
    dc, counter = fake_provider
    monkeypatch.setenv("LLM_RESPONSE_CACHE", "1")
    _msg = _tok("alpha")  # 同一测试内复用同一 token（键必须相同）
    r1 = dc.call_llm([{"role": "user", "content": _msg}], model="m")
    r2 = dc.call_llm([{"role": "user", "content": _msg}], model="m")
    assert counter["post"] == 1, "第二次同参调用不应触发 HTTP"
    assert r1["choices"][0]["message"]["content"] == r2["choices"][0]["message"]["content"]
    # 清理磁盘缓存中的本测试键，避免污染后续真实调用
    dc._MEM_RESP_CACHE.clear()


@pytest.mark.unit
def test_different_params_miss(fake_provider, monkeypatch):
    dc, counter = fake_provider
    monkeypatch.setenv("LLM_RESPONSE_CACHE", "1")
    dc.call_llm([{"role": "user", "content": _tok("beta")}], model="m", temperature=0.1)
    dc.call_llm([{"role": "user", "content": _tok("beta")}], model="m", temperature=0.9)
    assert counter["post"] == 2, "不同 temperature 应视为不同键"
    dc._MEM_RESP_CACHE.clear()


@pytest.mark.unit
def test_disabled_by_default(fake_provider, monkeypatch):
    dc, counter = fake_provider
    monkeypatch.delenv("LLM_RESPONSE_CACHE", raising=False)
    dc.call_llm([{"role": "user", "content": _tok("gamma")}], model="m")
    dc.call_llm([{"role": "user", "content": _tok("gamma")}], model="m")
    assert counter["post"] == 2, "默认关：不缓存"
