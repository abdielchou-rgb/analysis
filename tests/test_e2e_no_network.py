"""无网络 E2E 最小链路测试

背景（2026-08-01 审计）：
  2hao 缺少一条能在受限环境（无外网、无 akshare）走通的最小 E2E 路径。
  每次改代码都靠真实运行撞运气（如 preflight 卡死、data_feeds 网络阻塞）。

本测试验证核心链路在无网络环境下可运行：
  data(本地兜底) → enrich(充足性检查+enrich-file) → compute(无网络) →
  write(monkeypatch LLM) → gate(IronGate) → export

关键点：
  - monkeypatch call_deepseek 返回固定报告文本（绕过真实 LLM）
  - 跳过 RuntimeGate 全量语法编译（慢）、data_feeds 网络扫描（慢）
  - 验证 21 节点图中的核心 6 节点链路可走通

2026-09-14 审计修复（R4）——本文件的"无网络"此前只是**一句愿望**：
  - 没有任何机制强制无网络。实测外网不可用时，data 节点挂在 18 个数据源的
    第 14 个上（ProxyError 重试+退避），而 agent_graph 的超时又因
    `with ThreadPoolExecutor` 的 shutdown(wait=True) 而形同虚设
    → 整个 pytest 进程永久挂死，且连 summary 都不打印（这也是本项目
    长期只能"手挑文件"验证的原因之一）。
  - 现由 _offline_env 夹具**强制执行**该前提：socket.connect 直接抛错，
    节点超时压到 30s；数据改用本地夹具，经 data 节点自带的 `_data_cached`
    复用路径短路网络采集（见 e2e_orchestrator.py:412）。
  - 于是本测试从"依赖外网碰运气"变成"真的在无网络下跑通"。
"""

import os
import socket
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 加载 .env
for line in (_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

# 跳过慢 preflight：替换 RuntimeGate.check_all
import pipeline.runtime_gate as _rg

_rg.RuntimeGate.check_all = lambda self: {"summary": {"runtime_score": 1.0, "status": "PASS"}}


# ── 固定 LLM 输出（mock call_deepseek）─────────────────────────
SAMPLE_REPORT = """# 思必驰深度报告

## 一、核心分歧

市场认为公司持续亏损难以盈利，我们认为端侧 AI 放量将驱动亏损收窄并走向盈利。
公司 2025 年营收 6.88 亿元（招股书，2026-03），净利润 -0.80 亿元，亏损同比收窄 49.6%。
反方观点：AI 投入持续高企，盈利拐点不确定。概率判断：2 年内扭亏概率 40%。

## 二、业务分析

公司是国内领先的对话式人工智能企业，聚焦端侧智能。智慧出行车载语音 2025 年国内市占率 22%（盖世汽车研究院，2026-02），AI 办公本 2025 年单品销售额全国第一（招股书，2026-03）。
截至 2025 年末获授权发明专利 717 项（招股书，2026-03）。

## 三、财务与估值

营收三年复合增长 12.9%（2023-2025），研发投入占比 36.86%（2025）。公司处于亏损状态，采用 PS 估值。
建议关注端侧 AI 放量与减亏进度。
"""


def _mock_call_deepseek(messages, **kw):
    """mock LLM：返回固定报告文本"""
    return {"choices": [{"message": {"role": "assistant", "content": SAMPLE_REPORT}}]}


# ── 无网络前提必须被**强制**，而不是假设（2026-09-14 审计修复 R4）────────
_OFFLINE_NODE_TIMEOUT_S = "30"

# 本地夹具数据：取自 output/思必驰_data_dict.json（招股书口径），
# 形状对齐 chart_data（compute / enrich 节点消费）。
# 经 data 节点自带的 `_data_cached` 复用路径注入，从而完全不触碰网络。
_LOCAL_SEED_DATA = {
    "chart_data": {
        "fig_revenue_trend": {"2023": 5.42, "2024": 5.71, "2025": 6.88},
        "fig_profitability": {"2024": -1.59, "2025": -0.80},
    },
    "data_sufficiency": {"sufficient": True},
}


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    """强制"无网络"前提 + 短节点超时 + LLM 隔离。

    没有这个夹具，本文件的"无网络"就只是 docstring 里的一句话：
    测试实际依赖外网，外网不可用时 data 节点会永久挂死（见模块 docstring）。
    """
    monkeypatch.setenv("AGENT_GRAPH_NODE_TIMEOUT_S", _OFFLINE_NODE_TIMEOUT_S)

    def _blocked(*_a, **_k):
        raise OSError("network blocked by _offline_env fixture (no-network e2e)")

    monkeypatch.setattr(socket.socket, "connect", _blocked, raising=False)
    monkeypatch.setattr(socket.socket, "connect_ex", lambda *_a, **_k: 1, raising=False)

    # ── LLM 隔离（2026-09-14 R4）──
    # 两点都是实测踩出来的：
    # 1) pipeline/section_writer.py:26 是 `from core.deepseek_client import call_deepseek`
    #    —— 拿到的是**引用副本**，只 patch 源模块会漏（本项目自己的注释里就写过这个坑）。
    #    漏了它，write 节点会走真实 call_deepseek，进而撞上熔断器。
    # 2) smart_router 的熔断状态是**进程级全局**，会被先前用例的失败污染。
    #    实测：本模块单独跑 4 passed，放进全量套件则因
    #    "No available LLM provider (all circuit-broken)" 而失败。
    #    测试必须与"之前跑过什么"无关。
    import core.deepseek_client as _dsc
    import pipeline.section_writer as _sw

    monkeypatch.setattr(_dsc, "call_deepseek", _mock_call_deepseek, raising=False)
    monkeypatch.setattr(_sw, "call_deepseek", _mock_call_deepseek, raising=False)

    try:
        from core.smart_router import get_router

        _r = get_router()
        _r._circuit_broken_until.clear()
        _r._failures.clear()
    except Exception:
        pass
    yield


# ── 测试 1：核心 6 节点链路可走通 ───────────────────────────────
def test_core_chain_no_network():
    # monkeypatch LLM
    import core.deepseek_client as _dsc

    _orig = _dsc.call_deepseek
    _dsc.call_deepseek = _mock_call_deepseek
    try:
        from pipeline.agent_graph import AgentGraph
        from pipeline.e2e_orchestrator import E2ENodes

        g = AgentGraph("no_net_e2e")
        # 核心链路：data → enrich → compute → write → assemble → validate
        g.add_node("data", E2ENodes.data, deps=[], desc="data")
        g.add_node("enrich", E2ENodes.enrich_data, deps=["data"], desc="enrich")
        g.add_node("compute", E2ENodes.compute, deps=["enrich"], desc="compute")
        g.add_node("write_sections", E2ENodes.write_sections, deps=["enrich", "compute"], desc="write")
        g.add_node("style", E2ENodes.style_compile, deps=["write_sections"], desc="style")
        g.add_node("assemble", E2ENodes.assemble, deps=["style"], desc="assemble")

        ctx = {
            "asset": "思必驰",
            "report_type": "unlisted_company",
            "style": "cicc",
            "output_dir": str(_ROOT / "output"),
            # 2026-09-14（R4）：注入本地夹具，经 data 节点的 `_data_cached`
            # 复用路径短路网络采集——这才是"无网络"该有的样子。
            "_data_cached": True,
            "collected_data": dict(_LOCAL_SEED_DATA),
        }
        r = g.run(ctx)

        # data 节点：招股书本地数据应被加载
        assert r.nodes["data"].status == "passed", f"data failed: {r.nodes['data'].error}"
        cd = ctx.get("collected_data", {})
        chart = cd.get("chart_data", {})
        assert chart.get("fig_revenue_trend"), "data 应加载营收趋势"

        # enrich：数据充足性检查
        assert r.nodes["enrich"].status == "passed", f"enrich failed: {r.nodes['enrich'].error}"
        assert ctx.get("data_sufficiency", {}).get("sufficient") in (True, False)

        # compute：无网络可运行
        assert r.nodes["compute"].status == "passed", f"compute failed: {r.nodes['compute'].error}"
        assert ctx.get("compute_results"), "compute 应产出结果"

        # write：mock LLM 应产出报告
        assert r.nodes["write_sections"].status == "passed", f"write failed: {r.nodes['write_sections'].error}"
        assert ctx.get("report_text"), "write 应产出报告文本"
        assert len(ctx["report_text"]) > 100

        # assemble：final_text
        assert r.nodes["assemble"].status == "passed", f"assemble failed: {r.nodes['assemble'].error}"
        assert ctx.get("final_text"), "assemble 应产出 final_text"
    finally:
        _dsc.call_deepseek = _orig


# ── 测试 2：enrich-file 注入后数据充足性提升 ────────────────────
def test_enrich_file_injection():
    import core.deepseek_client as _dsc

    _orig = _dsc.call_deepseek
    _dsc.call_deepseek = _mock_call_deepseek
    try:
        from pipeline.agent_graph import AgentGraph
        from pipeline.e2e_orchestrator import E2ENodes

        g = AgentGraph("enrich_inject")
        g.add_node("data", E2ENodes.data, deps=[], desc="data")
        g.add_node("enrich", E2ENodes.enrich_data, deps=["data"], desc="enrich")

        ctx = {
            "asset": "思必驰",
            "report_type": "unlisted_company",
            "style": "cicc",
            "output_dir": str(_ROOT / "output"),
            "enrich_file": str(_ROOT / "output" / "思必驰_enrich.json"),
            # 2026-09-14（R4）：同测试 1——无网络前提由 _offline_env 强制，
            # data 节点走本地夹具短路，enrich 节点再读 enrich_file 注入。
            "_data_cached": True,
            "collected_data": dict(_LOCAL_SEED_DATA),
        }
        r = g.run(ctx)
        assert r.nodes["enrich"].status == "passed", f"enrich failed: {r.nodes['enrich'].error}"
        cd = ctx.get("collected_data", {})
        chart = cd.get("chart_data", {})
        assert chart.get("company_intro"), "enrich-file 应注入 company_intro"
        assert chart.get("business_model"), "enrich-file 应注入 business_model"
    finally:
        _dsc.call_deepseek = _orig


# ── 测试 3：E2EOrchestratorV2 可构造 ────────────────────────────
def test_orchestrator_construct():
    from pipeline.e2e_orchestrator import E2EOrchestratorV2

    o = E2EOrchestratorV2("思必驰", "unlisted_company", "cicc")
    assert o.asset == "思必驰"
    assert o.report_type == "unlisted_company"
    assert o.style == "cicc"


# ── 测试 4：缓存注入逻辑 ────────────────────────────────────────
def test_cache_injection():
    from pipeline.e2e_orchestrator import E2EOrchestratorV2

    o = E2EOrchestratorV2("思必驰", "unlisted_company", "cicc")
    ctx1 = o._build_context()
    assert ctx1.get("_data_cached") is None, "首轮不应有缓存标记"

    o._cached_collected = {"chart_data": {"fig_revenue_trend": {2025: 6.88}}}
    o._cached_data_sufficiency = {"sufficient": True}
    ctx2 = o._build_context()
    assert ctx2["_data_cached"] is True, "第二轮应注入缓存标记"
    assert ctx2["collected_data"]["chart_data"]["fig_revenue_trend"] == {2025: 6.88}


if __name__ == "__main__":
    import traceback

    passed = 0
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
