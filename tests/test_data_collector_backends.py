"""DataCollectorV5 网络阶段 缓存+熔断 收敛测试。

P3-audit 2026-08-24：data_backends 的 SQLite 缓存与 CircuitBreaker 此前
零复用——现四个网络阶段（tavily/yfinance/akshare/stocksdk）统一走
_network_phase 包装。本地阶段(Phase 0)不受影响。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.data_backends import _CIRCUIT


@pytest.fixture()
def collector():
    import uuid

    from pipeline.data_collector import DataCollectorV5

    c = DataCollectorV5()
    c._tavily = None  # 网络不可用环境确定性：禁掉 tavily 客户端
    # 磁盘缓存跨 pytest 运行持久化 → 每次运行唯一 asset 防键复用
    c._cache_asset = f"ut-{uuid.uuid4().hex[:8]}"
    return c


@pytest.mark.unit
def test_cache_hit_skips_second_call(collector, monkeypatch):
    """同一 (source, asset, anchor) 第二次调用应命中磁盘缓存，不再触网。"""
    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        return {"fig_price": 12.3}

    monkeypatch.setattr(collector, "_yfinance_search", None, raising=False)
    out1 = collector._network_phase("yfinance_test_a", fake_fetch)
    out2 = collector._network_phase("yfinance_test_a", fake_fetch)
    assert out1 == {"fig_price": 12.3}
    assert out2 == {"fig_price": 12.3}
    assert calls["n"] == 1, "第二次应命中缓存"


@pytest.mark.unit
def test_breaker_opens_after_failures(collector, monkeypatch):
    """连续失败达阈值 → 熔断跳过，不再调用底层 fn。"""
    src = "akshare_breaker_test"
    _CIRCUIT._failures.pop(src, None)

    def always_fail():
        raise ConnectionError("boom")

    for _ in range(_CIRCUIT.threshold):
        assert collector._network_phase(src, always_fail) is None
    # 达阈值后 allow() 应拒绝 → fn 不再执行
    executed = {"n": 0}

    def must_not_run():
        executed["n"] += 1
        return {}

    assert collector._network_phase(src, must_not_run) is None
    assert executed["n"] == 0
    _CIRCUIT._failures.pop(src, None)


@pytest.mark.unit
def test_empty_result_not_cached_but_success_counts(collector):
    """空结果不写缓存（下轮可重试），但成功计数重置熔断。"""
    src = "stocksdk_empty_test"
    _CIRCUIT._failures[src] = 2  # 差一次熔断
    out = collector._network_phase(src, lambda: {})
    assert out is None or out == {}
    assert _CIRCUIT._failures.get(src, 0) == 0, "成功应重置失败计数"
    _CIRCUIT._failures.pop(src, None)


@pytest.mark.unit
def test_collect_local_phase_unaffected(collector, monkeypatch):
    """本地阶段不经过网络包装——无 key 时 collect 仍能走完返回结构。"""
    # 桩掉全部网络 fetcher（离线确定性；Phase 1.5 内联 akshare 因标的无 6 位代码而跳过）
    monkeypatch.setattr(collector, "_yfinance_search", lambda *a, **k: None)
    monkeypatch.setattr(collector, "_akshare_search", lambda *a, **k: None)
    result = collector.collect("非存在标的XYZ", report_type="listed_company")
    assert result["asset"] == "非存在标的XYZ"
    assert "status" in result
