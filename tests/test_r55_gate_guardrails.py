"""R55 (2026-08-03) 回归测试 — IronGate 行业报告质量护栏。

Phase D 新增 4 个检查：
  - stock_pick_chain: 选股传导链存在性
  - unlisted_threat: 非上市威胁判断存在性
  - tam_bottomup: TAM/SAM/SOM 自底向上校验
  - regional_penetration: 区域渗透率错位判断
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 300+ 字完整行业报告（含所有护栏要素）
_CLEAN = (
    "## 行业概况\n"
    "本报告对气体传感器行业深度分析。全球市场规模2025年达45亿美元，"
    "北美/欧洲/亚太分别占30%/25%/35%，中国占全球比例从15%升至20%。"
    "渗透率中国约30%，海外领先国（日本/美国）已达60%，存在约5年错位。"
    "对标日本人均GDP路径，中国渗透率预计2028年达到50%。"
    "TAM全球约60亿美元（渗透率驱动因子×单价×终端数量测算），SAM约45亿美元，"
    "SOM约20亿美元（头部厂商份额收缩）。数据来源：Gartner 2025、灼识咨询。\n\n"
    "## 竞争格局\n"
    "行业集中度CR5约60%，霍尼韦尔、盛思锐占主导。非上市玩家如某国产电化学"
    "传感器厂商产能扩张构成潜在威胁（无权威数据，估算其市占约5%）。\n\n"
    "## 投资建议\n"
    "行业逻辑最受益标的为汉威科技（受益于国产替代），给予增持评级，目标价25元，"
    "弹性最大。四方光电受益于汽车电子渗透。\n\n"
    "风险提示：下游需求波动、原材料上行。\n"
)


def _run(text, check_name):
    from pipeline.iron_gate import IronGate
    gate = IronGate.from_text(text, report_type="industry_deep", style="cicc")
    return getattr(gate, check_name)()


def test_stock_pick_chain_pass():
    """含受益标的+评级+逻辑的行业报告应通过选股传导链。"""
    r = _run(_CLEAN, "_check_stock_pick_chain")
    assert r.passed, f"应通过选股传导链: {r.details}"


def test_stock_pick_chain_fail_without_picks():
    """无选股传导链的行业报告应拦截。"""
    text = _CLEAN.replace("最受益标的为汉威科技", "行业整体处于成长期").replace("给予增持评级，目标价25元", "但需持续跟踪").replace("弹性最大", "")
    r = _run(text, "_check_stock_pick_chain")
    assert not r.passed, f"无选股传导链应拦截: {r.details}"


def test_unlisted_threat_pass():
    """含非上市玩家+威胁度判断应通过。"""
    r = _run(_CLEAN, "_check_unlisted_threat")
    assert r.passed, f"应通过非上市威胁: {r.details}"


def test_unlisted_threat_fail():
    """无非上市玩家分析的行业报告应拦截。"""
    text = _CLEAN.replace("非上市玩家如某国产电化学传感器厂商产能扩张构成潜在威胁（无权威数据，估算其市占约5%）。", "")
    r = _run(text, "_check_unlisted_threat")
    assert not r.passed, f"无非上市威胁应拦截: {r.details}"


def test_tam_bottomup_pass():
    """TAM 含推导依据+来源标注应通过。"""
    r = _run(_CLEAN, "_check_tam_bottomup")
    assert r.passed, f"应通过TAM自底向上: {r.details}"


def test_tam_bottomup_fail_without_derivation():
    """TAM 只有单点数字无推导依据应拦截。"""
    # 独立文本（300+字）：TAM 单点数字（"全球市场规模约60亿美元"），无推导依据/来源
    text = (
        "## 行业概况\n"
        "本报告对气体传感器行业深度分析。全球市场规模2025年约60亿美元，"
        "中国市场规模约15亿美元。行业处于快速成长期，竞争格局集中度持续提升。"
        "产业链覆盖上游敏感材料、中游传感器制造、下游工业安全与消费电子应用。"
        "技术路线包括电化学、MEMS、催化燃烧等，各路线竞争格局不同。"
        "从下游看，工业安全、环保监测、汽车电子、医疗健康是主要应用领域。"
        "近年来行业增速保持两位数，国产替代进程加速推进。"
        "国内企业凭借成本优势和技术突破，市场份额稳步提升。"
        "行业长期成长逻辑清晰，龙头公司有望持续受益于行业扩容。"
        "未来五年行业增速预计保持两位数增长，其中汽车电子与医疗健康是增速最快的细分。"
        "从竞争看，头部企业凭借技术积累和客户资源占据优势，行业集中度有望进一步提升。"
        "综合来看，行业处于景气上行通道，投资价值凸显。\n\n"
        "## 风险提示\n"
        "需关注下游需求波动、原材料价格上行以及国际贸易摩擦带来的不确定性。\n"
    )
    r = _run(text, "_check_tam_bottomup")
    assert not r.passed, f"无推导依据应拦截: {r.details}"


def test_regional_penetration_pass():
    """含区域+渗透率+错位判断应通过。"""
    r = _run(_CLEAN, "_check_regional_penetration")
    assert r.passed, f"应通过区域渗透率: {r.details}"


def test_regional_penetration_fail():
    """无区域渗透率错位判断应拦截。"""
    text = _CLEAN.replace("渗透率中国约30%，海外领先国（日本/美国）已达60%，存在约5年错位。对标日本人均GDP路径，中国渗透率预计2028年达到50%。", "中国渗透率持续提升。")
    r = _run(text, "_check_regional_penetration")
    assert not r.passed, f"无区域错位判断应拦截: {r.details}"


def test_non_industry_skipped():
    """非行业报告（listed）应跳过护栏检查。"""
    from pipeline.iron_gate import IronGate
    gate = IronGate.from_text(_CLEAN, report_type="listed_company", style="cicc")
    r = gate._check_stock_pick_chain()
    assert r.passed, f"非行业报告应跳过: {r.details}"


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
