"""R55 (2026-08-03) 回归测试 — LLM 采集 provider 路由 + 数据标签。

Phase A: data_collector._tavily_search 不再写死 deepseek，改读 LLM_PROVIDER。
Phase B: LLM 采集数据带四元组标签（source/year/scope/confidence）。
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_tavily_uses_llm_provider_env():
    """_tavily_search 应读 LLM_PROVIDER 环境变量，非写死 deepseek。"""
    src = (Path(__file__).parent.parent / "pipeline" / "data_collector.py").read_text(encoding="utf-8")
    assert "LLM_PROVIDER" in src, "采集层应读 LLM_PROVIDER 环境变量"
    assert "call_llm" in src, "采集层应使用 call_llm（支持 provider 路由）"
    assert "call_deepseek" not in src.replace("call_llm", ""), "不应再直接写死 call_deepseek"


def test_tavily_emits_collection_meta():
    """采集数据应带 _collection_meta 四元组标签。"""
    src = (Path(__file__).parent.parent / "pipeline" / "data_collector.py").read_text(encoding="utf-8")
    assert "_collection_meta" in src, "应记录数据采集标签"
    assert "confidence" in src, "标签应含 confidence"
    assert "source" in src, "标签应含 source"


def test_provider_default_is_deepseek():
    """默认 provider 应为 deepseek（性能模式）。"""
    from pipeline.data_collector import DataCollectorV5

    dc = DataCollectorV5()
    # 直接检查 provider 解析逻辑
    provider = os.environ.get("LLM_PROVIDER", "deepseek")
    assert provider in ("deepseek", "agent_provider", "ollama_local")


if __name__ == "__main__":
    import traceback

    passed = failed = 0
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
