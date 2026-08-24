"""R53审计 (2026-08-03) 回归测试 — 语义重复检测 semantic_repeat。

问题：_check_template_repeat 是 10 句硬编码黑名单，只查字面精确重复，
      新套话不在名单即漏。
修复：跨章节字符 n-gram 相似度检测（零依赖），相似度≥0.90 判为语义重复，
      输出"章节A/章节B 相似度0.91"。
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 基础正文（正常报告，无重复）
_CLEAN = (
    "## 一、行业概况\n"
    "气体传感器行业正处于快速成长期，全球市场规模持续扩大。工业安全、环保监测、"
    "汽车电子等下游应用领域需求旺盛，推动行业增长。头部厂商凭借技术积累占据优势。\n\n"
    "## 二、竞争格局\n"
    "行业集中度逐步提升，头部企业市场份额持续扩大。霍尼韦尔、盛思锐等国际厂商"
    "在高端市场占据主导地位，国内企业加速追赶。竞争壁垒主要体现为技术积累与客户资源。\n\n"
    "## 三、产业链分析\n"
    "上游原材料包括弹性体、应变片、半导体器件等，中游为传感器制造环节。"
    "下游覆盖工业、汽车、医疗等多个终端市场，需求结构多元化。\n\n"
    "## 四、风险提示\n"
    "需关注下游需求波动、原材料价格上行以及国际贸易摩擦带来的不确定性。"
    "行业竞争加剧可能压缩利润空间，新进入者可能打破现有格局。\n\n"
)


def _run_semantic(text):
    from pipeline.iron_gate import IronGate
    gate = IronGate.from_text(text, report_type="industry_deep", style="cicc")
    return gate._check_semantic_repeat()


def test_clean_text_passes():
    """正常报告（章节内容各异）不应判为语义重复。"""
    r = _run_semantic(_CLEAN)
    assert r.passed, f"正常报告不应判重复: {r.details}"


def test_cross_section_duplicate_detected():
    """跨章节高度重复的句子应被检测。"""
    dup = (
        "## 五、投资建议\n"
        "这一趋势若延续，盈利中枢存在系统性上移的可能，我们看好龙头公司的长期成长空间。"
        "公司凭借技术优势和客户资源，市场份额有望持续提升。"
        "当前估值处于历史中位区间，具备一定安全边际。"
        "建议重点关注公司在物联网领域的布局进展以及产能释放节奏。\n\n"
    )
    text = _CLEAN + dup + (
        "## 六、估值分析\n"
        "这一趋势若延续，盈利中枢存在系统性上移的可能，我们看好龙头公司的长期成长空间。"
        "公司在产能扩张与产品升级双轮驱动下，收入利润有望保持较快增长。"
        "从相对估值看，当前股价对应明年市盈率处于合理区间。"
        "综合DCF与可比公司估值，我们给予增持评级。\n\n"
    )
    r = _run_semantic(text)
    assert not r.passed, f"跨章节重复应检测: {r.details}"
    assert "相似度" in r.details, f"应输出章节对相似度: {r.details}"


def test_similar_but_not_identical_passes():
    """相似但不同内容的句子（正常分析）不应误报。"""
    text = _CLEAN + (
        "## 五、成长驱动\n"
        "物联网应用平台建设持续推进，由单一传感器制造向数据服务延伸。"
        "机器人、智慧医疗等新兴领域打开第二增长曲线，成长逻辑逐步清晰。\n\n"
    )
    r = _run_semantic(text)
    assert r.passed, f"正常内容不应误报: {r.details}"


def test_template_repeat_still_works():
    """原有硬编码模板句检测不受影响。"""
    from pipeline.iron_gate import IronGate
    text = _CLEAN + (
        "这一趋势若持续，盈利中枢存在系统性上移的可能。"
        "这一趋势若持续，盈利中枢存在系统性上移的可能。"
    )
    gate = IronGate.from_text(text, report_type="industry_deep", style="cicc")
    r = gate._check_template_repeat()
    assert not r.passed, f"模板句重复应检出: {r.details}"


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
