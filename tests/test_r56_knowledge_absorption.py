"""R56 (2026-08-03) 回归测试 — 知识库深度吸收 + 接入管线。

覆盖：知识库全量索引 + 4 个深度吸收产物 + section_writer 注入。
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_knowledge_base_index_exists():
    """全量索引应存在且含主要主题。"""
    import json
    p = _ROOT / "data" / "methodology_knowledge_base.json"
    assert p.exists(), "methodology_knowledge_base.json 缺失"
    d = json.loads(p.read_text(encoding="utf-8"))
    topics = {k: v for k, v in d.items() if k != "_meta"}
    assert len(topics) >= 6, f"应≥6主题: {list(topics.keys())}"
    assert "valuation_models" in topics, "应含估值模型主题"


def test_deep_absorptions_exist():
    """4 个深度吸收产物应存在。"""
    files = [
        "methodology_valuation_deep.json",
        "methodology_industry_deep.json",
        "methodology_reports_deep.json",
        "methodology_backtest_deep.json",
    ]
    for f in files:
        p = _ROOT / "data" / f
        assert p.exists(), f"{f} 缺失"


def test_industry_deep_has_rules():
    """行业深度吸收应含可执行规则。"""
    import json
    d = json.loads((_ROOT / "data" / "methodology_industry_deep.json").read_text(encoding="utf-8"))
    assert "industry_structure" in d
    assert "competitive" in d
    assert "global_regional" in d
    # 竞争格局应有 checklist 或 quant_methods
    comp = d.get("competitive", {})
    rules = comp.get("checklist") or comp.get("quant_methods") or []
    assert len(rules) >= 3, f"竞争格局应≥3规则: {len(rules)}"


def test_valuation_deep_has_dcf_rules():
    """估值深度吸收应含 DCF 规则。"""
    import json
    d = json.loads((_ROOT / "data" / "methodology_valuation_deep.json").read_text(encoding="utf-8"))
    assert "dcf" in d
    dcf = d["dcf"]
    rules = dcf.get("checklist") or dcf.get("core_principles") or []
    assert len(rules) >= 3, f"DCF应≥3规则: {len(rules)}"


def test_section_writer_injects_deep_kb():
    """section_writer 应注入深度知识库（segment 2 含估值规则）。"""
    from pipeline.section_writer import SectionWriter
    sw = SectionWriter("industry_deep", "cicc")
    ref = sw._build_methodology_reference(2)
    assert "深度知识库" in ref, "应注入深度知识库"
    assert "DCF" in ref or "可比估值" in ref, "前瞻层应含估值规则"


def test_section_writer_injects_industry_kb():
    """行业报告应注入行业框架（segment 0 含行业结构）。"""
    from pipeline.section_writer import SectionWriter
    sw = SectionWriter("industry_deep", "cicc")
    ref = sw._build_methodology_reference(0)
    assert "行业结构" in ref or "行业框架" in ref, "战略层应含行业结构规则"


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
