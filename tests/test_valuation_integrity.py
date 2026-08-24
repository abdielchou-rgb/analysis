"""R53审计 (2026-08-03) 回归测试 — 估值勾稽硬规则 valuation_integrity。

问题：R35 EPS 桥只匹配"2027E EPS X元"预测期模式，报告用"2025E动态PE对应
      EPS约1.10元"（PE 表述）不命中 → 估值链四方矛盾漏检。
修复：新增 valuation_integrity 检查——净利=EPS×股本 / 市值=股价×股本 /
      目标价/PE=EPS 三环勾稽，偏差>5% 即 FAIL。
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _run_gate(text, asset=""):
    from pipeline.iron_gate import IronGate

    gate = IronGate.from_text(text, report_type="listed_company", style="cicc")
    if asset:
        gate.asset = asset
        gate.sac_id = asset
    # 直接调检查器
    return gate._check_valuation_integrity()


# ── 1. PE 表述的 EPS 漏检修复 ─────────────────────────────────
_BASE = (
    "本报告对某公司估值分析如下。公司为称重传感器龙头，主营业务为应变式称重传感器、"
    "仪表及物联网应用系统的研发、生产与销售，下游覆盖工业衡器、物流自动化、人形机器人、"
    "智慧医疗等多个领域。公司凭借核心弹性体应变片技术积累深厚护城河，市场份额位居国内前列，"
    "客户结构涵盖国内外知名工业设备厂商。近年来公司持续推进物联网应用平台建设，"
    "由单一传感器制造向数据服务延伸，成长逻辑逐步清晰。公司财务结构稳健，"
    "资产负债率处于行业合理水平，经营性现金流表现良好，研发投入持续加码。"
)


def test_pe_expression_eps_detected():
    """报告用 PE 表述（"动态PE X倍对应EPS Y元"）应被估值勾稽拦截。"""
    text = _BASE + (
        "公司总股本4.2亿股，总市值约196亿元，当前价46.7元。"
        "2025E动态PE 42倍对应EPS约1.10元，2025年净利润约5.2亿元。"
        "公司业务稳健增长，市场份额持续提升，物联网业务打开成长空间。"
        "风险提示包括下游需求波动、原材料价格上行以及新业务拓展不及预期等。"
    )
    r = _run_gate(text)
    # 1.10×4.2=4.62亿 ≠ 5.2亿（偏差 12.5% > 5%）→ 应 FAIL
    assert not r.passed, f"应拦截 EPS×股本≠净利, 实际: {r.details}"


def test_consistent_valuation_passes():
    """EPS×股本=净利 一致时应通过。"""
    text = _BASE + (
        "公司总股本4.2亿股，总市值约196亿元，当前价46.7元。"
        "2027E EPS 1.24元，2027年净利润约5.2亿元。"
        "公司业务稳健增长，市场份额持续提升，物联网业务打开成长空间。"
        "风险提示包括下游需求波动、原材料价格上行以及新业务拓展不及预期等。"
    )
    r = _run_gate(text)
    # 1.24×4.2=5.21 ≈ 5.2（偏差 0.2% < 5%）→ PASS
    assert r.passed, f"一致估值不应拦截: {r.details}"


def test_market_cap_price_shares_integrity():
    """市值=股价×股本 勾稽：偏差>5% 应拦截。"""
    text = _BASE + (
        "公司总股本4.2亿股，总市值约250亿元，当前价46.7元。"
        "公司业务稳健增长，市场份额持续提升，物联网业务打开成长空间。"
        "风险提示包括下游需求波动、原材料价格上行以及新业务拓展不及预期等。"
    )
    r = _run_gate(text)
    # 46.7×4.2=196亿 ≠ 250亿（偏差 27%）→ 应 FAIL
    assert not r.passed, f"应拦截市值矛盾: {r.details}"


def test_target_price_pe_eps_integrity():
    """目标价/PE=EPS 勾稽：目标价与 PE 隐含 EPS 不一致应拦截。"""
    text = _BASE + (
        "公司总股本4.2亿股，总市值约196亿元，当前价46.7元。"
        "目标价60元，对应PE 42倍，2025E EPS约1.10元。"
        "公司业务稳健增长，市场份额持续提升，物联网业务打开成长空间。"
        "风险提示包括下游需求波动、原材料价格上行以及新业务拓展不及预期等。"
    )
    r = _run_gate(text)
    # 60/42=1.43 元 vs 报告 EPS 1.10 元（偏差 30%）→ 应 FAIL
    assert not r.passed, f"应拦截目标价/PE vs EPS 矛盾: {r.details}"


# ── 2. data_dict 外部锚 ──────────────────────────────────────
def test_data_dict_external_anchor(tmp_path=None):
    """data_dict 提供真实股本/股价/净利时，作为外部锚校验。"""
    from pipeline.iron_gate import IronGate

    text = _BASE + (
        "公司总股本4.2亿股，总市值约196亿元，当前价46.7元。"
        "2027E EPS 1.50元，2027年净利润约5.2亿元。"
        "公司业务稳健增长，市场份额持续提升，物联网业务打开成长空间。"
        "风险提示包括下游需求波动、原材料价格上行以及新业务拓展不及预期等。"
    )
    gate = IronGate.from_text(text, report_type="listed_company", style="cicc")
    # 写一个 data_dict（外部锚：股本4.2亿股、价46.7元、净利5.2亿）
    asset = "test_asset_val"
    gate.asset = asset
    gate.sac_id = asset
    out_dir = _ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    dd_path = out_dir / f"{asset}_data_dict.json"
    dd = {"shares_total": 4.2, "price_latest": 46.7, "net_profit_latest": 5.2}
    dd_path.write_text(json.dumps(dd, ensure_ascii=False), encoding="utf-8")
    try:
        r = gate._check_valuation_integrity()
        # 1.50×4.2=6.3亿 vs 外部净利5.2亿（偏差 21%）→ 应 FAIL
        assert not r.passed, f"应拦截 data_dict 外部锚矛盾: {r.details}"
    finally:
        try:
            dd_path.unlink(missing_ok=True)
        except OSError:
            pass  # 沙箱只读保护，忽略


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
