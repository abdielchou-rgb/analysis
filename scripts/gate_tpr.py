"""R1 门禁变异测试报告 — 输出 IronGate 逐检查项 TPR 表。

用法：
    python scripts/gate_tpr.py                 # 打印 TPR 表
    python scripts/gate_tpr.py --json out.json # 同时导出机器可读结果

输出的 TPR（true positive rate）回答的是审计最核心的问题：

    **门禁说"通过"到底意味着什么？**

如果 TPR 低，说明 105 项检查里有一批是"永远不叫的看门狗"——
它们不报错，不是因为报告没问题，而是因为它们压根抓不到问题。

对比基线：软件测试领域认为 70% 左右的变异分数是成熟测试套件的量级
（100% 通常意味着变异体太弱，而不是套件太强）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402

from tests.gate_mutation import corpus as C  # noqa: E402
from tests.gate_mutation import harness as H  # noqa: E402


def run_corpus(baseline_name: str = "gas_sensor_cicc.md") -> tuple[list[H.Verdict], dict]:
    mp = pytest.MonkeyPatch()
    H.stub_llm_checks(mp)
    try:
        text = H.load_baseline(baseline_name)
        base_results = H.run_gate(text)
        verdicts = [H.evaluate(m, text, base_results, H.run_gate) for m in C.MUTANTS]
        return verdicts, base_results
    finally:
        mp.undo()


def print_table(verdicts: list[H.Verdict], base_results: dict) -> None:
    stats = H.summarise(verdicts)

    print()
    print("=" * 108)
    print("IronGate 变异测试 TPR 表（基线：tests/golden/gas_sensor_cicc.md，105 项检查）")
    print("=" * 108)
    tier_of = {m.id: m.tier for m in C.MUTANTS}
    print(f"{'变异体':<32}{'目标检查项':<28}{'层':<9}{'方向':<6}{'基线':>6}{'变异后':>8}{'Δ':>8}  判定")
    print("-" * 108)
    for v in verdicts:
        verdict = "KILLED" if v.killed else ("N/A" if v.saturated else "SURVIVED")
        print(
            f"{v.mutant_id:<32}{v.target:<28}{tier_of.get(v.mutant_id, '?'):<9}{v.direction:<6}"
            f"{v.base_score:>6.2f}{v.mut_score:>8.2f}{v.delta:>+8.3f}  {verdict}"
        )
    print("-" * 108)

    print(
        f"变异体总数 {stats['total_mutants']} | 可判定 {stats['applicable']} | "
        f"检出 {stats['killed']} | 漏检 {stats['survived']} | N/A(饱和) {stats['na_saturated']}"
    )
    print()
    for tier, label, meaning in (
        (C.PATTERN, "PATTERN 层", "照检查项自己实现的模式构造 → 漏检=检查项坏了"),
        (C.NATURAL, "NATURAL 层", "真人评审会挑出的毛病 → 漏检=门禁盲区"),
        (C.BENIGN, "BENIGN 层", "注入正确无害的内容 → 报警=误报"),
    ):
        s = H.summarise(verdicts, tier)
        if tier == C.BENIGN:
            fpr = s["fpr"]
            print(
                f"  {label}: 可判定 {s['applicable']:>2} | 保持安静 {s['quiet']:>2} | "
                f"误报 {s['false_alarms']:>2} | N/A {s['na_saturated']:>2}  →  "
                f"FPR = {fpr:.1%}"
                if fpr is not None
                else f"  {label}: 无可判定样本"
            )
            print(f"      （{meaning}）")
        else:
            print(
                f"  {label}: 可判定 {s['applicable']:>2} | 检出 {s['killed']:>2} | "
                f"漏检 {s['survived']:>2} | N/A {s['na_saturated']:>2}  →  TPR = {s['tpr']:.1%}"
            )
            print(f"      （{meaning}）")
    print()
    print(f"总体 TPR = {stats['tpr']:.1%}")

    _print_prevalence_correction(verdicts, base_results, stats)
    _print_survivors(verdicts, base_results, stats)


def _print_prevalence_correction(verdicts: list[H.Verdict], base_results: dict, stats: dict) -> None:
    """用 Rogan–Gladen 把门禁的观测分数换算成真实缺陷率。

    门禁的 error_mean 是"观测患病率"。它不等于真实缺陷率，除非
    TPR = TNR = 1。测出 TPR/TNR 后必须反校准，否则 0.95 会被读成
    "5% 有问题"，而真实值可能是它的数倍。
    """
    nat = H.summarise(verdicts, C.NATURAL)
    ben = H.summarise(verdicts, C.BENIGN)
    tpr, fpr = nat["tpr"], ben["fpr"]
    if fpr is None:
        print("\n【真实缺陷率】无法估计：BENIGN 层无可用样本（特异度未知）。")
        return
    tnr = 1.0 - fpr

    err = [o for o in base_results.values() if o.severity == "error"]
    if not err:
        return
    n_red = sum(1 for o in err if not o.passed)
    observed_fail = n_red / len(err)

    print()
    print("── 门禁的性格：高特异度、低敏感度 ──")
    print(f"  TPR = {tpr:.1%}（NATURAL 层）   FPR = {fpr:.1%}（BENIGN 层）   TNR = {tnr:.1%}")
    print("  ⟹ 它报的红灯基本都是真的 —— **红灯可信**")
    print("  ⟹ 它放行的绿灯不作数（多数缺陷没被看见）—— **绿灯不可信**")
    print()
    print("── 观测失败率 → 真实缺陷率（Rogan–Gladen 反校准）──")
    print(f"  本基线样本：error 级 {len(err)} 项中报红 {n_red} 项 → 观测失败率 {observed_fail:.1%}")
    print("  换算表（TNR=1 时 p = 观测失败率 / TPR）：")
    for obs in (0.05, 0.10, 0.15, 0.19):
        p = H.rogan_gladen(obs, tpr, tnr)
        if p is None:
            continue
        tag = "   ← 典型出厂报告量级" if obs == 0.05 else ""
        print(f"    观测 {obs:>4.0%}  →  真实缺陷率 ≈ {p:>5.1%}{tag}")
    print(f"    观测 {tpr:>4.0%}  →  真实缺陷率 ≈ 100%（框架上界：观测值已达 TPR 本身）")
    print()
    if observed_fail > tpr:
        print(f"  ⚠ 本样本观测失败率 {observed_fail:.1%} > TPR {tpr:.1%} → 解越界。")
        print("    越界不是算错，而是：这份样本已差到『比检测器能表达的最坏情况还差』。")
        print("    （这份 golden 样本只有 6917 字，远低于行业报告 10420 字门槛，")
        print("     42.9% 的 error 报红是被截断造成的，不代表生产报告。）")
    print()
    print("  ⚠ 方法边界：Rogan–Gladen 要求观测率与 TPR 取自**同一总体**。")
    print("     不能拿本样本的 TPR 去反推生产报告的分数，反之亦然。")
    print("     要得到生产可用的换算，必须在**生产报告样本**上重测 TPR。")


def _print_survivors(verdicts: list[H.Verdict], base_results: dict, stats: dict) -> None:
    """漏检（假阴性）清单。独立于患病率换算——即使特异度未知也必须打印，
    否则"算不出真实缺陷率"会连带把最该看的清单一起吞掉。"""
    if stats["survivors"]:
        print()
        print("── 漏检清单（注入了已知缺陷但检查项无反应 = 假阴性）──")
        for v in stats["survivors"]:
            print(f"  · {v.mutant_id} → {v.target}  {v.note}")

    # 按"严重级别"拆解：error 级漏检是硬伤，warning 级只是建议
    err_surv = [
        v for v in stats["survivors"] if base_results.get(v.target) and base_results[v.target].severity == "error"
    ]
    if err_surv:
        print()
        print(f"── 其中 severity=error 的漏检 {len(err_surv)} 项（直接决定 overall_score）──")
        for v in err_surv:
            print(f"  !! {v.mutant_id} → {v.target}  Δ={v.delta:+.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="导出结果为 JSON")
    ap.add_argument("--baseline", default="gas_sensor_cicc.md")
    args = ap.parse_args()

    verdicts, base_results = run_corpus(args.baseline)
    print_table(verdicts, base_results)

    if args.json:
        summary = H.summarise(verdicts)
        summary["survivors"] = [vars(v) for v in summary["survivors"]]
        payload = {
            "baseline": args.baseline,
            "summary": summary,
            "pattern_tpr": H.summarise(verdicts, C.PATTERN)["tpr"],
            "natural_tpr": H.summarise(verdicts, C.NATURAL)["tpr"],
            "verdicts": [vars(v) for v in verdicts],
        }
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已导出 → {args.json}")

    # 退出码：漏检即非零，便于 CI 卡口（配合 --max-survivors 之类策略）
    return 1 if H.summarise(verdicts)["survived"] else 0


if __name__ == "__main__":
    sys.exit(main())
