"""prompt_injectors 注册表单元测试。

P3-audit 2026-08-24 Strangler-Fig 重构的守护测试：
1. build_injections 返回全部 30 个变量键（与 section_writer 消费端契约）
2. 静态文本注入器（无需外部模块）产出非空内容
3. 条件注入器按 report_type 正确门控
4. 单个注入器抛异常不拖垮整体（返回空串）
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from pipeline.prompt_injectors import INJECTORS, build_injections


def _ctx(**over):
    base = {"asset": "测试标的", "report_type": "listed_company",
            "data_context": {}, "asset_code": "", "data_dict": {}}
    base.update(over)
    return base


@pytest.mark.unit
def test_registry_returns_all_contract_keys():
    out = build_injections(**_ctx())
    expected = {name for name, _ in INJECTORS}
    assert set(out.keys()) == expected, f"注册表与返回键不一致: {expected ^ set(out.keys())}"
    # 与 section_writer 消费端约定的 30 个变量名
    assert len(expected) == 30


@pytest.mark.unit
def test_static_injectors_produce_content():
    """静态方法论提示（ss/cc/sf/cf/esg/ex-unlisted）不依赖数据即可产出。"""
    out = build_injections(**_ctx(report_type="unlisted_company"))
    for key in ("ss_str", "cc_str", "sf_str", "cf_str", "esg_str", "ex_str"):
        assert out[key], f"{key} 应有静态内容"
    assert "做空者视角" in out["ss_str"]
    assert "退出路径分析" in out["ex_str"]


@pytest.mark.unit
def test_conditional_injectors_gated_by_report_type():
    """ur/di/ex 按 report_type 门控。"""
    listed = build_injections(**_ctx(report_type="listed_company"))
    assert listed["ur_str"] == "", "unlisted 反向定价不应出现在个股报告"
    assert listed["ex_str"] == ""
    assert listed["di_str"] == "", "行业戴维斯双击不应出现在个股报告"
    industry = build_injections(**_ctx(report_type="industry_deep"))
    # di 无估值数据时为空串，但 ex/ur 门控方向正确
    assert industry["ur_str"] == ""


@pytest.mark.unit
def test_broken_data_does_not_crash():
    """畸形 data_context 不应抛异常——全部降级为空串或正常值。"""
    out = build_injections(**_ctx(data_context={"chart_data": None,
                                                "compute_results": "not-a-dict",
                                                "universe_summary": 12345}))
    assert isinstance(out, dict) and len(out) == 30


@pytest.mark.unit
def test_single_injector_failure_isolated(monkeypatch):
    """某个注入器炸了 → 该键空串，其余照常。"""
    import pipeline.prompt_injectors as pi
    def _boom(ctx):
        raise RuntimeError("boom")
    monkeypatch.setitem(pi.__dict__, "_inj_esg_str", _boom)
    # 直接操作注册表内引用（INJECTORS 持函数对象）
    saved = dict(pi.INJECTORS)
    try:
        pi.INJECTORS[:] = [(n, (_boom if n == "esg_str" else f)) for n, f in pi.INJECTORS]
        out = build_injections(**_ctx())
    finally:
        pi.INJECTORS[:] = [(n, f) for n, f in saved.items()]
    assert out["esg_str"] == ""
    assert out["ss_str"], "其他静态注入器不受影响"
