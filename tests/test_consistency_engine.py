# -*- coding: utf-8 -*-
"""consistency_engine 测试 — 跨段数值一致性检查

覆盖：正常报告无冲突 / 矛盾报告阻断 / 币种归一化 / 跨年合理差异 /
占比多指标不混簇 / 派生市场规模不误报 / ImportError 显式失败。

独立运行：python tests/test_consistency_engine.py
可被 run_all.py 调用：run() 返回 (n_pass, n_fail)
"""

from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def run(report=None) -> tuple:
    """执行全部测试。report 可选回调 (name, ok, detail)。返回 (n_pass, n_fail)。"""
    n_pass, n_fail = 0, 0

    def t(name, ok, detail=""):
        nonlocal n_pass, n_fail
        if ok:
            n_pass += 1
        else:
            n_fail += 1
            print(f"  FAIL: {name} {detail}")
            if report:
                report(name, ok, detail)

    from pipeline.consistency_engine import check_consistency

    # ── 1. 正常报告：多指标自洽 ─────────────────────────
    good = """
    2025年全球市场规模890亿美元，2026年预计1050亿美元。
    2025年中国市场规模320亿美元。
    单台成本15万元。目标价基于2026E PS 8.0x，对应目标涨幅35%。
    2025年人形机器人出货量约1.2万台。渗透率5.5%。
    """
    r = check_consistency(good)
    t("正常报告无冲突", r["passed"], str(r.get("conflicts")))

    # ── 2. 矛盾报告：目标价涨幅冲突 ────────────────────
    bad = "目标价涨幅35%。目标价对应提升12%。"
    r2 = check_consistency(bad)
    t("矛盾报告被阻断", not r2["passed"], str(r2.get("conflicts")))
    t("矛盾命中目标价涨幅", any("目标价_涨幅" in c for c in r2["conflicts"]))

    # ── 2b. R11: 矛盾报告命中 PS 倍数（保护 R6 阈值不被回退）──
    bad_ps = "目标价基于2026E PS 8.0x。目标价对应2026年PS 9.5倍。"
    r2b = check_consistency(bad_ps)
    t("PS 8.0x vs 9.5x 被阻断", not r2b["passed"], str(r2b.get("conflicts")))
    t("矛盾命中 PS 倍数", any("目标价_PS倍数" in c for c in r2b["conflicts"]))

    # ── 2c. 正常 PS 一致不误报 ─────────────────────────
    ok_ps = "目标价基于2026E PS 8.0x，对应目标涨幅35%。"
    r2c = check_consistency(ok_ps)
    t("PS 一致不误报", r2c["passed"], str(r2c.get("conflicts")))

    # ── 3. 币种归一化：亿美元 vs 亿元 同量级不误报 ─────
    money = "全球市场规模达890亿美元。全球市场规模约6000亿元。"
    r3 = check_consistency(money)
    t("币种归一化后同量级无冲突", r3["passed"], str(r3.get("conflicts")))

    # ── 4. 跨年合理差异不误报 ─────────────────────────
    years = "2025年出货量1.2万台。2027年出货量预计5万台。"
    r4 = check_consistency(years)
    t("跨年出货量差异不误报", r4["passed"], str(r4.get("conflicts")))

    # ── 5. 同口径市场规模真矛盾应阻断 ─────────────────
    same_year = "2025年全球市场规模890亿美元。2025年全球市场规模120亿美元。"
    r5 = check_consistency(same_year)
    t("同口径市场规模矛盾被阻断", not r5["passed"], str(r5.get("conflicts")))

    # ── 6. 占比多指标不混簇 ───────────────────────────
    ratios = "工业机器人占比62%。服务机器人占比28%。人形机器人占比10%。"
    r6 = check_consistency(ratios)
    t("多占比指标不误报", r6["passed"], str(r6.get("conflicts")))

    # ── 7. 派生市场规模（"对应市场规模约X亿"）不误报 ───
    derived = "2025年全球市场规模890亿美元。12.3万台对应市场规模约310亿元。"
    r7 = check_consistency(derived)
    t("派生市场规模不误报", r7["passed"], str(r7.get("conflicts")))

    # ── 7b. R32: 目标价金额矛盾（柯力案：51.60 vs 48）──
    tp_bad = "12个月目标价51.60元。综合DCF+PE，12个月目标价48元。"
    r7b = check_consistency(tp_bad)
    t("目标价金额矛盾被阻断", not r7b["passed"], str(r7b.get("conflicts")))
    t("矛盾命中目标价金额簇", any("目标价金额" in c for c in r7b["conflicts"]))

    # ── 7c. R32: 目标价金额一致不误报 ──────────────────
    tp_ok = "12个月目标价51.60元。投资评级：增持 ｜ 12个月目标价：51.60元。"
    r7c = check_consistency(tp_ok)
    t("目标价金额一致不误报", r7c["passed"], str(r7c.get("conflicts")))

    # ── 7d. R32: 目标价区间不误报（"PE估值对应40-48元"非综合目标价）──
    tp_range = "PE估值合理目标区间40-48元。综合目标价取48元。"
    r7d = check_consistency(tp_range)
    t("目标价区间表述不误报", r7d["passed"], str(r7d.get("conflicts")))

    # ── 7f. R45 P0-1: 双字连接词（约为/达到/预计达）必须命中 ──
    conn1 = "全球机器人市场规模约为 500 亿美元。全球机器人市场规模达到 100 亿美元。"
    r7f = check_consistency(conn1)
    t("R45: '约为/达到'矛盾被阻断", not r7f["passed"], str(r7f.get("conflicts")))
    t("R45: 矛盾命中市场规模簇", any("市场规模" in c for c in r7f["conflicts"]))

    conn2 = "全球机器人市场规模约为 500 亿美元。全球机器人市场规模约为 500 亿美元。"
    r7g = check_consistency(conn2)
    t("R45: 双字连接词一致不误报", r7g["passed"], str(r7g.get("conflicts")))

    conn3 = "全球机器人市场规模预计达 500 亿美元。全球机器人市场规模约为 500 亿美元。"
    r7h = check_consistency(conn3)
    t("R45: 预计达/约为一致不误报", r7h["passed"], str(r7h.get("conflicts")))

    # ── 7e. R32: 敏感性矩阵数值不入簇（防表格误报）──────
    tp_matrix = "12个月目标价51.60元。| 8.5% | 40.9 | 42.4 | 44.0 | 45.8 |"
    r7e = check_consistency(tp_matrix)
    t("敏感性矩阵数值不入簇", r7e["passed"], str(r7e.get("conflicts")))

    # ── 8. 空文本 ─────────────────────────────────────
    r8 = check_consistency("")
    t("空文本无冲突", r8["passed"])

    print(f"[test_consistency_engine] {n_pass} passed, {n_fail} failed")
    return n_pass, n_fail


if __name__ == "__main__":
    np_, nf_ = run()
    sys.exit(1 if nf_ > 0 else 0)
