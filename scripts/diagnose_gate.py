# -*- coding: utf-8 -*-
"""诊断脚本：对当前报告跑 IronGate 全部检查，输出每项得分明细。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from pipeline.iron_gate import IronGate


def main():
    report_path = _ROOT / "test_output" / "_gate_check.md"
    gate = IronGate(
        report_path=str(report_path),
        report_type="earnings_notes",
        style="cicc",
        asset="宁德时代",
        chart_ids={"fig_financial_trends", "fig_segment_analysis", "fig_cash_flow", "fig_profit_margin"},
    )
    report = gate.run_all()

    print("=" * 70)
    print(f"总分: {report.overall_score:.3f} | passed: {report.passed}")
    print("=" * 70)

    # 按 severity 分组
    errors, warns, infos = [], [], []
    for c in report.checks:
        sev = getattr(c, "severity", "info")
        if sev == "error":
            errors.append(c)
        elif sev == "warning":
            warns.append(c)
        else:
            infos.append(c)

    print(f"\n### ERROR 级 ({len(errors)} 项) — 每项满分 1.0")
    for c in sorted(errors, key=lambda x: getattr(x, "score", 1)):
        score = getattr(c, "score", None)
        if score is not None and score < 1.0:
            print(f"  [FAIL] {c.name}: score={score:.2f}")
            d = getattr(c, "details", "") or ""
            if d:
                print(f"         {str(d)[:180]}")

    print(f"\n### WARNING 级 ({len(warns)} 项) — 拉低 warn_mean")
    for c in sorted(warns, key=lambda x: getattr(x, "score", 1)):
        score = getattr(c, "score", None)
        if score is not None and score < 1.0:
            print(f"  [LOW] {c.name}: score={score:.2f}")
            d = getattr(c, "details", "") or ""
            if d:
                print(f"         {str(d)[:150]}")

    n_err = len(errors)
    err_sum = sum(getattr(c, "score", 0) for c in errors)
    n_warn = len(warns)
    warn_sum = sum(getattr(c, "score", 0) for c in warns)
    if n_err:
        print(f"\nerror_mean = {err_sum}/{n_err} = {err_sum / n_err:.3f}")
    if n_warn:
        print(f"warn_mean  = {warn_sum}/{n_warn} = {warn_sum / n_warn:.3f}")

    # 提升模拟：如果每个 <1.0 的 error 检查都修到 1.0，error_mean 变多少
    if n_err:
        err_fixed = n_err  # 全部 1.0
        loss = n_err - err_sum
        print(f"\n若 ERROR 全修满: error_mean = {(err_sum + loss) / n_err:.3f} (+{loss / n_err:.3f})")


if __name__ == "__main__":
    main()
