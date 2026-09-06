"""research_planner LLM 预算熔断测试 (2026-09-07 P0-1, 真实 PROFILE 驱动).

验证 question_tree_v2 的共享时间预算:
- 预算耗尽时未完成维度回落 v1 模板, 不让单维度把整轮拖死
- LLM 失败回落模板
- 无 LLM key / use_llm=False 直接模板
- 顺序确定 (保持 dims 顺序)
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from pipeline.research_planner import question_tree_v2


@pytest.fixture
def fake_llm_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-real")


def _install_slow_llm(monkeypatch, delay_s: float = 10.0):
    """把 _llm_generate_questions 替换成 sleep(delay) 后返回 None 的慢函数。"""
    import pipeline.research_planner as rp

    def _slow(asset, dim, report_type, data_context):
        time.sleep(delay_s)
        return None

    monkeypatch.setattr(rp, "_llm_generate_questions", _slow)


def _install_fast_llm(monkeypatch, result=None):
    import pipeline.research_planner as rp

    def _fast(asset, dim, report_type, data_context):
        return result or [f"{dim}专属问题A", f"{dim}专属问题B"]

    monkeypatch.setattr(rp, "_llm_generate_questions", _fast)


def test_no_key_goes_template(monkeypatch):
    """无 DEEPSEEK_API_KEY → 全模板(不触发 LLM)。"""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    tree = question_tree_v2(["规模", "竞争"], use_llm=True)
    assert all(n.get("source", "template") != "llm" for n in tree)
    assert len(tree) == 2
    assert [n["dim"] for n in tree] == ["规模", "竞争"]  # 顺序确定


def test_use_llm_false_goes_template():
    tree = question_tree_v2(["规模"], use_llm=False)
    assert tree[0]["dim"] == "规模"
    assert any("口径" in q or "来源" in q or "支撑" in q for q in tree[0]["questions"])


def test_budget_elapsed_falls_back_template(fake_llm_key, monkeypatch):
    """慢 LLM(10s) + 预算 0.1s → 全部回落模板且不阻塞。"""
    _install_slow_llm(monkeypatch, delay_s=10.0)
    t0 = time.monotonic()
    tree = question_tree_v2(["规模", "竞争", "估值", "增速"], use_llm=True, llm_budget_s=0.1)
    elapsed = time.monotonic() - t0
    # 关键断言: 不应等待慢 LLM 的 10s; 预算熔断后快速返回
    assert elapsed < 8.0, f"预算熔断未生效, 耗时 {elapsed:.1f}s"
    assert len(tree) == 4
    assert all(n.get("source") != "llm" for n in tree)
    assert [n["dim"] for n in tree] == ["规模", "竞争", "估值", "增速"]


def test_llm_success_kept(fake_llm_key, monkeypatch):
    """LLM 正常返回 → 保留 LLM 问题 + source=llm。"""
    _install_fast_llm(monkeypatch)
    tree = question_tree_v2(["规模"], use_llm=True, llm_budget_s=5.0)
    assert tree[0]["source"] == "llm"
    assert tree[0]["questions"] == ["规模专属问题A", "规模专属问题B"]


def test_llm_failure_falls_back_template(fake_llm_key, monkeypatch):
    """LLM 抛错/返回 None → 回落模板(不崩)。"""
    import pipeline.research_planner as rp

    def _boom(asset, dim, report_type, data_context):
        raise RuntimeError("deepseek down")

    monkeypatch.setattr(rp, "_llm_generate_questions", _boom)
    tree = question_tree_v2(["毛利率"], use_llm=True, llm_budget_s=5.0)
    assert tree[0]["dim"] == "毛利率"
    assert tree[0].get("source") != "llm"


def test_settings_budget_available():
    """settings 提供 research_llm_budget_s, 默认 45s 且 ≥5s。"""
    from core.settings import research_llm_budget_s

    v = research_llm_budget_s()
    assert v >= 5.0
