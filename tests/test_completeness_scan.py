"""R53审计 (2026-08-03) 回归测试 — 正文完整性扫描 completeness_scan。

问题：气体传感器圆桌审计坐实正文 3 处截断——决策门"双的分析"(L12)、
      表E-2"2025-202"(L318)、DCF碎片(L320)，Gate 全绿出厂——无完整性扫描。
修复：新增 completeness_scan 确定性扫描（未闭合代码块/表格半cell/年份截断/
      已知碎片/句末连字符/段落截半）。
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 300+ 字完整文本（不应触发完整性扫描）
_CLEAN = (
    "本报告对气体传感器行业深度分析。行业正处于快速成长期，全球市场规模持续扩大。"
    "工业安全、环保监测、汽车电子、医疗健康等下游应用领域需求旺盛，推动行业增长。"
    "头部厂商凭借技术积累和客户资源占据优势地位，行业集中度逐步提升。"
    "从产业链看，上游原材料包括弹性体、应变片、半导体器件等，中游为传感器制造环节，"
    "下游覆盖工业、汽车、医疗等多个终端市场。未来五年行业增速预计保持两位数增长，"
    "其中汽车电子与医疗健康是增速最快的细分领域。风险方面，需关注下游需求波动、"
    "原材料价格上行以及国际贸易摩擦带来的不确定性。综合来看，行业长期成长逻辑清晰，"
    "龙头公司有望持续受益于行业扩容与集中度提升。我们给予行业增持评级，"
    "重点推荐技术壁垒高、客户结构优的头部企业。\n"
)


def _run_scan(text):
    from pipeline.iron_gate import IronGate
    gate = IronGate.from_text(text, report_type="industry_deep", style="cicc")
    return gate._check_completeness_scan()


def test_clean_text_passes():
    """完整文本不应触发完整性扫描。"""
    r = _run_scan(_CLEAN)
    assert r.passed, f"完整文本不应拦截: {r.details}"


def test_unclosed_code_fence_detected():
    """奇数个 ``` 应拦截。"""
    text = _CLEAN + "\n```python\nx = 1\n"
    r = _run_scan(text)
    assert not r.passed, f"未闭合代码块应拦截: {r.details}"
    assert "代码块" in r.details


def test_year_truncation_detected():
    """'2025-202' 后无完整年份应拦截。"""
    text = _CLEAN + "\n表E-2 市场规模预测（2025-202）：\n"
    r = _run_scan(text)
    assert not r.passed, f"年份截断应拦截: {r.details}"
    assert "年份截断" in r.details


def test_fragment_detected():
    """'双的分析' 类截断碎片应拦截。"""
    text = _CLEAN + "\n决策门双的分析\n"
    r = _run_scan(text)
    assert not r.passed, f"截断碎片应拦截: {r.details}"


def test_trailing_hyphen_detected():
    """句末连字符（截半词）应拦截。"""
    text = _CLEAN + "\n该公司的竞争优势主要体现在其核心- \n"
    r = _run_scan(text)
    assert not r.passed, f"句末连字符应拦截: {r.details}"


def test_table_half_cell_detected():
    """表格半 cell（行管道符不一致）应拦截。"""
    text = _CLEAN + """
| 年份 | 市场规模 |
|------|---------|
| 2024 | 45亿 |
| 2025 | 52亿 | 53亿
"""
    r = _run_scan(text)
    # 若表格结构明显异常应拦截
    assert not r.passed, f"表格半cell应拦截: {r.details}"


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
