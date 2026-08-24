"""R55 (2026-08-03) 回归测试 — Layer3 LLM 数据交叉验证（对侧 provider）。

Phase E：IronGate 新增 _check_llm_data_verification——校验 provider 与生成 provider
对侧，防止同源偏见（LLM 自采自校验）。训练模式生成=Marvis→校验=DeepSeek，
性能模式生成=DeepSeek→校验=Marvis/本地。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_verification_registered():
    """_check_llm_data_verification 应注册为类方法。"""
    from pipeline.iron_gate import IronGate

    assert hasattr(IronGate, "_check_llm_data_verification")
    # 应在 LLM 并行检查名单中
    src = (Path(__file__).parent.parent / "pipeline" / "iron_gate.py").read_text(encoding="utf-8")
    assert "_check_llm_data_verification" in src
    assert "llm_data_verification" in src


def test_opposite_provider_logic():
    """校验 provider 应取生成 provider 的对侧。"""
    # R61(2026-08-03) 迁移：LLM 校验逻辑从 iron_gate.py 拆到 pipeline/checks/llm_checks_mixin.py
    mixin = (Path(__file__).parent.parent / "pipeline" / "checks" / "llm_checks_mixin.py").read_text(encoding="utf-8")
    # 训练模式（agent_provider 生成）→ 校验 deepseek
    assert "agent_provider" in mixin and "deepseek-reasoner" in mixin
    # 应读 LLM_PROVIDER 判断生成端
    assert "LLM_PROVIDER" in mixin
    # iron_gate.py 应通过 mixin 继承接入（接线检查）
    ig_src = (Path(__file__).parent.parent / "pipeline" / "iron_gate.py").read_text(encoding="utf-8")
    assert "llm_checks_mixin" in ig_src or "llm_data_verification" in ig_src


def test_verification_skips_short_text():
    """短文本应跳过。"""
    from pipeline.iron_gate import IronGate

    gate = IronGate.from_text("太短了", report_type="industry_deep", style="cicc")
    r = gate._check_llm_data_verification()
    assert r.passed, f"短文本应跳过: {r.details}"


def test_verification_runs_in_sandbox():
    """沙箱环境下校验应运行（不抛异常），返回 GateCheckResult。"""
    from pipeline.iron_gate import IronGate

    text = (
        "本报告对某公司分析。2024年归母净利2.1亿元，2025年预计3.5亿元。"
        "毛利率维持40%以上，PE估值22倍。公司市占率约15%，位居行业前列。"
        "目标价25元，对应PE 22倍。风险提示：下游需求波动。"
        "行业处于成长期，渗透率持续提升，国产替代加速。"
        "产业链覆盖上游材料、中游制造、下游应用，竞争格局集中度提升。"
    ) * 2  # 保证 >500 字
    gate = IronGate.from_text(text, report_type="industry_deep", style="cicc")
    try:
        r = gate._check_llm_data_verification()
        # 不抛异常即可，passed 可能因沙箱 provider 而异
        assert r is not None
        assert hasattr(r, "name")
    except Exception as e:
        # 若沙箱完全无 provider，应优雅降级不抛异常
        assert "降级" in str(e) or "不可用" in str(e), f"应优雅降级: {e}"


def test_three_tier_calibration():
    """三级判定：低分阻断、中分警告通过、高分通过。"""

    # R61 迁移后阈值常量在 pipeline/checks/llm_checks_mixin.py
    src = (Path(__file__).parent.parent / "pipeline" / "checks" / "llm_checks_mixin.py").read_text(encoding="utf-8")
    assert "LLM_VERIFY_MIN_PASS" in src, "应含通过阈值"
    assert "LLM_VERIFY_MIN_BLOCK" in src, "应含阻断阈值"
    assert "_MIN_BLOCK" in src, "应含低分阻断逻辑"
    # 阈值默认值
    assert 'LLM_VERIFY_MIN_PASS", "0.70"' in src, "默认通过阈值应0.70"
    assert 'LLM_VERIFY_MIN_BLOCK", "0.40"' in src, "默认阻断阈值应0.40"


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
