"""R57 (2026-08-03) 回归测试 — 顶级机构视角升级。

覆盖：
  - SAC 新增 core_hypothesis/industry_consolidation/esg_materiality 维度
  - MBB 咨询方法论吸收（methodology_consulting_deep.json）
  - 四大审计方法论吸收（methodology_audit_deep.json）
  - Gate 新增并购/假设/ESG 检查
  - 并购估值模块
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── SAC 维度 ─────────────────────────────────────
def test_sac_new_dimensions():
    """三类型 SAC 应含 core_hypothesis + esg_materiality。"""
    from pipeline.section_writer import SectionWriter
    for rt in ['industry_deep', 'listed_company', 'unlisted_company']:
        sw = SectionWriter(rt, 'cicc')
        dims = sw.sac.get_dimension_ids()
        assert 'core_hypothesis' in dims, f"{rt} 应含 core_hypothesis"
        assert 'esg_materiality' in dims, f"{rt} 应含 esg_materiality"


def test_industry_consolidation_dimension():
    """行业+listed 应含 industry_consolidation。"""
    from pipeline.section_writer import SectionWriter
    for rt in ['industry_deep', 'listed_company']:
        sw = SectionWriter(rt, 'cicc')
        dims = sw.sac.get_dimension_ids()
        assert 'industry_consolidation' in dims, f"{rt} 应含 industry_consolidation"


def test_sac_coverage_with_new_dims():
    """新增维度后分组覆盖应完整。"""
    from pipeline.section_writer import SectionWriter
    from pipeline.dimension_grouper import group_dimensions, verify_coverage
    for rt in ['industry_deep', 'listed_company', 'unlisted_company']:
        sw = SectionWriter(rt, 'cicc')
        dims = sw.sac.get_dimension_ids()
        groups = group_dimensions(rt, dims)
        assert verify_coverage(rt, dims, groups), f"{rt} 分组覆盖失败"


# ── 方法论吸收 ──────────────────────────────────
def test_consulting_methodology_exists():
    """MBB 方法论应存在且含可执行规则。"""
    import json
    d = json.loads((_ROOT / "data" / "methodology_consulting_deep.json").read_text(encoding="utf-8"))
    for k in ['hypothesis_driven', 'issue_tree_mece', 'profit_pool', 'rule_of_three']:
        assert k in d, f"应含 {k}"
        rules = d[k].get('checklist') or d[k].get('core_principles') or []
        assert len(rules) >= 3, f"{k} 应≥3规则"


def test_audit_methodology_exists():
    """四大审计方法论应存在且含量化规则。"""
    import json
    d = json.loads((_ROOT / "data" / "methodology_audit_deep.json").read_text(encoding="utf-8"))
    for k in ['fraud_signals', 'revenue_recognition', 'three_statement_bridge']:
        assert k in d, f"应含 {k}"
        rules = d[k].get('checklist') or []
        assert len(rules) >= 3, f"{k} 应≥3规则"


# ── Gate 检查 ───────────────────────────────────
def test_gate_new_checks():
    """IronGate 应注册并购/假设/ESG 检查。"""
    from pipeline.iron_gate import IronGate
    for fn in ['_check_industry_consolidation', '_check_core_hypothesis', '_check_esg_materiality']:
        assert hasattr(IronGate, fn), f"{fn} 缺失"


def test_gate_consolidation_detects():
    """含并购信号的行业报告应通过并购检查。"""
    from pipeline.iron_gate import IronGate
    text = (
        "## 行业概况\n本报告分析气体传感器行业。行业集中度持续提升，CR3从35%升至45%，"
        "行业正在加速整合，头部企业通过并购扩张。龙头企业凭借资本实力成为整合者，"
        "ROIC 15%高于WACC 8%，资本配置效率高。行业终局判断为寡头格局。"
        "我们判断行业处于成长期。我们预计渗透率提升。我们看好龙头。\n"
    ) * 5
    gate = IronGate.from_text(text, report_type="industry_deep", style="cicc")
    r = gate._check_industry_consolidation()
    assert r.passed, f"并购信号应通过: {r.details}"


# ── 并购估值模块 ────────────────────────────────
def test_consolidation_module():
    """并购估值模块应判断整合阶段。"""
    from core.compute.consolidation import consolidation_assessment, consolidator_profile
    a = consolidation_assessment(industry="半导体", cr3=45)
    assert "consolidation_stage" in a, "应返回整合阶段"
    assert "整合" in a["consolidation_stage"], "CR3=45应判整合中"
    p = consolidator_profile(roic=0.15, wacc=0.08, mcap_b=200, net_cash_b=30)
    assert p["profile"]["role"] == "consolidator", "ROIC>WACC+净现金应判整合者"


# ── section_writer 注入 ─────────────────────────
def test_writer_injects_consulting():
    """section_writer 应注入 MBB/审计方法论。"""
    from pipeline.section_writer import SectionWriter
    sw = SectionWriter("industry_deep", "cicc")
    ref1 = sw._build_methodology_reference(1)
    ref2 = sw._build_methodology_reference(2)
    assert "问题树MECE" in ref1 or "利润池" in ref1, "竞争层应含MBB规则"
    assert "财务造假" in ref2 or "收入确认" in ref2, "前瞻层应含审计规则"


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
