"""FP v3.2 (2026-08-03) 回归测试 — 来源标注多维化（P2-1）。

圆桌 P1-2：enrich 17 个点全标"置信度0.7"无区分度。
修复：置信度按 {来源类型, 权威度, 交叉验证} 多维加权；
IronGate 数据溯源检查补充四元组覆盖校验。
"""

import os  # noqa: F401  (dead-import debt)
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_weighted_confidence_distinguishes():
    """不同来源应得到不同置信度（不再全 0.7）。"""
    from pipeline.data_enrichment import AgentEnricher

    official = AgentEnricher._weighted_confidence({"source": "公司公告 2026-03"})
    web = AgentEnricher._weighted_confidence({"source": "WebSearch: 关键词"})
    est = AgentEnricher._weighted_confidence({"source": "估算"})
    assert official > web, f"官方应高于搜索: {official} vs {web}"
    assert official > est, f"官方应高于估算: {official} vs {est}"
    assert web >= 0.4, f"搜索不应过低: {web}"


def test_weighted_confidence_respects_explicit():
    """显式 confidence 应优先。"""
    from pipeline.data_enrichment import AgentEnricher

    conf = AgentEnricher._weighted_confidence({"source": "WebSearch", "confidence": 0.9})
    assert abs(conf - 0.9) < 1e-9, f"应尊重显式confidence: {conf}"


def test_weighted_confidence_cross_validation_bonus():
    """交叉验证应加分。"""
    from pipeline.data_enrichment import AgentEnricher

    base = AgentEnricher._weighted_confidence({"source": "公司公告"})
    cv = AgentEnricher._weighted_confidence({"source": "公司公告", "cross_validated": True})
    assert cv >= base, f"交叉验证应≥基础: {cv} vs {base}"


def test_traceability_tetra_tuple():
    """数据溯源检查应含四元组覆盖信息。"""
    from pipeline.iron_gate import IronGate

    text = (
        "本报告分析某行业。市场规模约45亿元（数据来源：公司公告2026）。增速12%（数据来源：Wind 2025）。"
        "龙头市占率30%（数据来源：估算）。国产替代加速。我们判断行业成长期。"
        "我们预计渗透率提升。我们看好龙头。风险提示：需求波动。"
    ) * 8
    gate = IronGate.from_text(text, report_type="industry_deep", style="cicc")
    r = gate._check_data_traceability()
    assert "四元组" in r.details, f"应含四元组信息: {r.details}"


def test_no_source_fails_traceability():
    """无来源标注报告应拦截（coverage < 30%）。"""
    from pipeline.iron_gate import IronGate

    text = (
        "我们判断行业前景良好，预计保持增长。我们认为龙头优势明显，看好其发展。"
        "我们建议关注，给予积极评价。我们预计趋势延续。我们判断拐点临近。"
        "我们看好行业格局。我们建议增持。风险可控。"
    ) * 8
    gate = IronGate.from_text(text, report_type="industry_deep", style="cicc")
    r = gate._check_data_traceability()
    assert not r.passed, f"无来源应拦截: {r.details}"


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
