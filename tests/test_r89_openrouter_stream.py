# -*- coding: utf-8 -*-
"""R89 回归测试：OpenRouter SSE 流式聚合器。

背景（2026-08-25 空芯光纤行业深度运行时发现）：
  本机网络路径下 OpenRouter 非流式响应体在 ~7.8KB 处被确定性截断
  （resp.json() 反复报 "Expecting value: line 1427-1429 column 1"），
  长写作调用 100% 失败。解法：对 openrouter provider 强制 SSE 流式并聚合。
本测试用合成 SSE 行验证聚合器纯函数，不触网。
"""

from core.deepseek_client import _accumulate_openrouter_stream


def test_accumulates_content_deltas():
    lines = [
        ": OPENROUTER PROCESSING",  # 注释行必须忽略
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        'data: {"choices":[{"delta":{"content":"反谐振"}}]}',
        'data: {"choices":[{"delta":{"content":"空芯光纤"}}]}',
        "data: [DONE]",
    ]
    acc = _accumulate_openrouter_stream(lines)
    assert acc["content"] == "反谐振空芯光纤"


def test_accumulates_reasoning_and_usage():
    lines = [
        'data: {"choices":[{"delta":{"reasoning":"思考中"}}]}',
        'data: {"choices":[{"delta":{"reasoning":"，结论是A"}}]}',
        'data: {"id":"x","choices":[],"usage":{"total_tokens":99,"completion_tokens":10}}',
        "data: [DONE]",
    ]
    acc = _accumulate_openrouter_stream(lines)
    assert acc["reasoning"] == "思考中，结论是A"
    assert acc["content"] == ""
    assert acc["usage"].get("total_tokens") == 99


def test_tolerates_garbage_lines():
    lines = [
        "data: not-json{{{",
        "",
        'data: {"choices":[{"delta":{"content":"OK"}}]}',
        "data: [DONE]",
        'data: {"late":"after-done"}',  # DONE 后的行也安全
    ]
    acc = _accumulate_openrouter_stream(lines)
    assert acc["content"] == "OK"


def test_reasoning_fallback_when_content_empty():
    """推理模型只吐 reasoning 不吐 content 时，聚合结果 content 为空串（由
    _normalize_llm_response 负责从 reasoning 提取尾部答案）。"""
    lines = [
        'data: {"choices":[{"delta":{"reasoning":"只有推理"}}]}',
        "data: [DONE]",
    ]
    acc = _accumulate_openrouter_stream(lines)
    assert acc["content"] == ""
    assert "只有推理" in acc["reasoning"]
