"""write_sections 段级 profile (2026-09-07 P0-2) 守护测试.

改动是在 _write_dimension_parallel 组级写入处加 [PROFILE] 耗时日志(纯增量,不改行为)。
运行时真实验证需完整 LLM mock, 本测试守护:
- settings 提供 slow_group_threshold_s (env 可调)
- section_writer 模块可导入且含组级 timing 注入点(源码守卫, 防后续被误删)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path


def test_slow_group_threshold_default():
    from core.settings import slow_group_threshold_s

    v = slow_group_threshold_s()
    assert v == 30.0
    assert v >= 5.0


def test_slow_group_threshold_env_override(monkeypatch):
    monkeypatch.setenv("SLOW_GROUP_THRESHOLD_S", "12")
    from core.settings import slow_group_threshold_s

    assert slow_group_threshold_s() == 12.0


def test_section_writer_group_timing_injected():
    """_write_dimension_parallel 中必须存在组级 [PROFILE] 计时注入点。"""
    src = Path("pipeline/section_writer.py").read_text(encoding="utf-8")
    assert "_grp_t0 = _perf_counter()" in src, "组级总计时起点被移除"
    assert "_group_times[gname] = round(_perf_counter() - _t0, 1)" in src, "单组计时被移除"
    assert "[DIM-PARALLEL][PROFILE] 组级总耗时" in src, "组级汇总日志被移除"
    assert "[DIM-PARALLEL][PROFILE] 组 %s 写完" in src, "单组完成日志被移除"


def test_section_writer_imports_clean():
    """section_writer 可导入(改动不破坏模块加载)。"""
    import pipeline.section_writer  # noqa: F401


def test_merge_timing_injected():
    """_editor_merge 调用处必须含 merge 耗时日志(P0-2b: 串行 merge 是组级之后的唯一慢嫌疑)。"""
    src = Path("pipeline/section_writer.py").read_text(encoding="utf-8")
    assert "_merge_t0 = _perf_counter()" in src, "merge 计时起点被移除"
    assert "[EDITOR][PROFILE] merge 耗时" in src, "merge 耗时日志被移除"
    assert "merge %.1fs ≥15s" in src, "merge 慢段告警被移除"
