# -*- coding: utf-8 -*-
"""R89 回归测试：_build_prompt_v4 必须接受调用方传入的 fp8_plan_str kwarg。

背景（2026-08-25 空芯光纤行业深度运行时发现）：
  section_writer._write_segment 三处调用 _build_prompt_v4(..., fp8_plan_str=...)，
  但函数签名未声明该参数 → 每段写作必抛
  "_build_prompt_v4() got an unexpected keyword argument 'fp8_plan_str'"
  → 全部分组失败 → E2E 空转 MAX_ATTEMPTS 轮后 abort。
本测试静态校验"调用 kwargs ⊆ 签名参数"，防同类接线漂移复发。
"""

import ast
import inspect
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _signature_params():
    from pipeline.section_writer import SectionWriter

    sig = inspect.signature(SectionWriter._build_prompt_v4)
    return set(sig.parameters.keys())


def test_build_prompt_v4_accepts_fp8_plan_str():
    params = _signature_params()
    assert "fp8_plan_str" in params, (
        "_build_prompt_v4 缺少 fp8_plan_str 形参——调用方(section_writer L918/L935/L994)"
        "会以 unexpected keyword argument 崩溃"
    )


def test_all_call_site_kwargs_subset_of_signature():
    """AST 级校验：所有 _build_prompt_v4(...) 调用的关键字实参必须都在签名里。"""
    params = _signature_params()
    src = (_ROOT / "pipeline" / "section_writer.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    checked = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "_build_prompt_v4":
            for kw in node.keywords:
                assert kw.arg in params, f"line {node.lineno}: _build_prompt_v4 收到签名外参数 {kw.arg!r}"
            checked += 1
    assert checked >= 3, f"应至少检查到3处调用点，实际 {checked}"
