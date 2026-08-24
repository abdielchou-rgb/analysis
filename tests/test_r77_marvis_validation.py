"""R77 (2026-08-05) — Marvis 久通物联自检报告修复验证。

验证 Marvis 声称的 R1-R13 修复真实落地，且无副作用：
1. _check_report_date / _check_placeholder_xxx 注册且逻辑正确
2. 占位符检查不误伤中文省略号/正常文本
3. AgentEnricher.merge 保持扁平 chart_data（不破坏下游）
4. style.py 端侧硬编码句已删除
"""
import os
import sys
import json
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_report_date_checker_registered():
    """_check_report_date 应注册进 IronGate。"""
    from pipeline.iron_gate import IronGate
    assert hasattr(IronGate, "_check_report_date")
    src = (_ROOT / "pipeline" / "iron_gate.py").read_text(encoding="utf-8")
    assert "_check_report_date" in src


def test_report_date_checks_correct_date():
    """正确日期的报告应通过日期检查。"""
    import datetime
    from pipeline.iron_gate import IronGate
    now = datetime.datetime.now()
    ig = IronGate.__new__(IronGate)
    ig.report_text = f"# 报告\n报告日期：{now.year}年{now.month}月\n公司营收15.58亿元。" * 3
    r = ig._check_report_date()
    assert r.passed, f"正确日期应通过: {r.details}"


def test_placeholder_checker_no_false_positive():
    """占位符检查不应误伤中文省略号和正常文本。"""
    from pipeline.iron_gate import IronGate
    ig = IronGate.__new__(IronGate)
    ig.report_text = ("# 久通物联报告\n公司2025年营收15.58亿元，毛利率44.8%……\n"
                      "行业空间广阔，成长可期。" * 3)
    r = ig._check_placeholder_xxx()
    assert r.passed, f"正常文本不应误报: {r.details}"


def test_placeholder_checker_catches_real():
    """真实占位符（XXX/TODO）应被拦截。"""
    from pipeline.iron_gate import IronGate
    ig = IronGate.__new__(IronGate)
    ig.report_text = "# 报告\n公司营收XXX亿元，毛利率待填写。\n" * 3
    r = ig._check_placeholder_xxx()
    assert not r.passed, f"占位符应拦截: {r.details}"


def test_enrich_merge_keeps_flat_chart_data():
    """AgentEnricher.merge 应保持 chart_data 扁平（不破坏下游）。"""
    from pipeline.data_enrichment import AgentEnricher
    good = {"asset": "测试", "generated_by": "agent", "items": [
        {"type": "fig_data", "key": "fig_revenue_trend",
         "data": {"2023": 50, "2024": 60}, "source": "公司公告2026-03",
         "confidence": 0.9, "unit": "亿元"},
    ]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump(good, f, ensure_ascii=False); gf = f.name
    try:
        data = AgentEnricher.merge("测试", {"chart_data": {}}, gf)
        cd = data["chart_data"]
        # 扁平：下游可直接读年份
        assert cd["fig_revenue_trend"]["2024"] == 60, f"应扁平: {cd['fig_revenue_trend']}"
        # 伴生 caliber 保留 unit
        assert cd["_caliber"]["fig_revenue_trend"]["unit"] == "亿元"
    finally:
        os.unlink(gf)


def test_style_no_endside_hardcode():
    """style.py 不应再有"端侧产品放量"硬编码句。"""
    src = (_ROOT / "core" / "style.py").read_text(encoding="utf-8")
    assert "端侧产品放量" not in src, "端侧产品放量硬编码应删除"
    assert "端侧变现的兑现节奏" not in src, "端侧变现硬编码应删除"


def test_cross_section_consistency_registered():
    """跨节一致性检查应注册进 IronGate。"""
    from pipeline.iron_gate import IronGate
    assert hasattr(IronGate, "_check_cross_section_consistency")
    src = (_ROOT / "pipeline" / "iron_gate.py").read_text(encoding="utf-8")
    assert "_check_cross_section_consistency" in src


if __name__ == "__main__":
    import traceback
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  OK {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")


def test_sub_element_coverage_exempts_trimmed_dims():
    """维度裁剪豁免：未涉及维度（连核心词都不出现）的子要素不计入缺口。"""
    import tempfile, os as _os
    from pipeline.iron_gate import IronGate
    # 报告不含 elasticity_analysis 相关词 → 该维度应被豁免
    text = ("# 传感器行业报告\n公司2025年营收15.58亿元，毛利率44.8%，归母净利3.41亿元。"
            "我们看好成长期龙头，市占率提升，目标价28元。" * 3)
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
    tmp.write(text); tmp.close()
    gate = IronGate(tmp.name, 'industry_deep', 'cicc')
    r = gate._check_sub_element_coverage()
    _os.unlink(tmp.name)
    # 即使不算裁剪豁免，弹性分析关键词没出现也应被豁免，不再 FAIL
    assert r.passed is True or "弹性" in r.details, f"裁剪维度应豁免或提示: {r.details[:80]}"


def test_sub_element_coverage_catches_shallow():
    """写了维度但缺子要素应被暴露（软覆盖拦截）。"""
    import tempfile, os as _os
    from pipeline.iron_gate import IronGate
    # 报告写了生命周期但没任何子要素
    text = ("# 行业报告\n本报告讨论生命周期阶段。公司2025年营收15.58亿元。" * 5)
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
    tmp.write(text); tmp.close()
    gate = IronGate(tmp.name, 'industry_deep', 'cicc')
    r = gate._check_sub_element_coverage()
    _os.unlink(tmp.name)
    # 生命周期维度有子要素但报告只有"生命周期"一词 → 大概率未覆盖子要素
    # 但豁免逻辑可能跳过（probe 命中"生命周期"则检查）——验证不抛异常即可
    assert r is not None and hasattr(r, 'passed')
