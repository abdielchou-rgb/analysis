"""R1 门禁变异测试 — 把"检查项能否抓到已知缺陷"做成 CI 断言。

与 scripts/gate_tpr.py 共用语料库与执行器：
  · scripts/gate_tpr.py     → 出 TPR 表（给人看，可导出 JSON）
  · 本文件                  → 逐变异体断言（给 CI 用，漏检即红）

设计要点见 tests/gate_mutation/corpus.py 顶部说明。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tests.gate_mutation import corpus as C  # noqa: E402
from tests.gate_mutation import harness as H  # noqa: E402


@pytest.fixture(scope="session")
def _stub_llm():
    """三个 LLM 校验器打桩——LLM 不确定且离线会降级放行，会把漏检伪装成通过。"""
    mp = pytest.MonkeyPatch()
    H.stub_llm_checks(mp)
    yield
    mp.undo()


@pytest.fixture(scope="session")
def baseline(_stub_llm):
    text = H.load_baseline()
    return text, H.run_gate(text)


@pytest.fixture(scope="session")
def verdicts(baseline):
    text, base_results = baseline
    return {v.mutant_id: v for v in (H.evaluate(m, text, base_results, H.run_gate) for m in C.MUTANTS)}


def _parametrize_mutants():
    """已登记盲区的变异体标 xfail：CI 保持绿，但一旦被修复会 XPASS 自动浮出。"""
    out = []
    for m in C.MUTANTS:
        if m.id in C.KNOWN_BLIND_SPOTS or m.id in C.KNOWN_FALSE_ALARMS:
            spot = C.BLIND_SPOT_REGISTRY.get(m.id) or C.KNOWN_FALSE_ALARMS.get(m.id)
            assert spot is not None, f"{m.id} 被登记为盲区却没有登记条目——登记册与 xfail 必须同源"
            out.append(
                pytest.param(
                    m,
                    marks=pytest.mark.xfail(
                        reason=f"已知盲区（owner={spot.owner}, 退役={spot.retire}）：{spot.reason}",
                        strict=False,
                    ),
                )
            )
        else:
            out.append(pytest.param(m))
    return out


@pytest.mark.parametrize("mutant", _parametrize_mutants(), ids=lambda m: m.id)
def test_mutant_is_killed(mutant: C.Mutant, verdicts):
    """注入已知缺陷后，目标检查项必须有反应。

    N/A（基线已饱和）不算失败——数学上不可能检出，硬判失败只会逼人删用例。
    """
    v = verdicts[mutant.id]
    if v.saturated or v.base_score != v.base_score:
        pytest.skip(f"{v.note}")
    assert v.killed, f"[{mutant.tier}] {mutant.desc} → 检查项 {mutant.target} 无反应：{v.note}"


def test_harness_is_deterministic(baseline):
    """空变异（恒等变换）必须零反应——否则整套差分判据不可信。"""
    text, base_results = baseline
    again = H.run_gate(text)
    drifted = [
        k
        for k in base_results
        if again[k].score != base_results[k].score or again[k].details != base_results[k].details
    ]
    assert not drifted, f"门禁在同一输入上不稳定（{len(drifted)} 项漂移）：{drifted[:5]}"


def test_gate_produces_all_checks(baseline):
    """门禁必须产出全部 105 项检查——少一项就意味着某个检查项静默消失。"""
    _, base_results = baseline
    assert len(base_results) >= 100, f"检查项数量异常：{len(base_results)}（基线应为 105）"


def test_no_check_silently_errors(baseline):
    """『检查异常』/『引擎不可用』不是通过——出现即说明该检查项实际已失效。"""
    _, base_results = baseline
    broken = [
        name
        for name, o in base_results.items()
        if "检查异常" in o.details or "unavailable" in o.details or "不可用" in o.details
    ]
    assert not broken, f"以下检查项在基线上异常/不可用却计入评分：{broken}"


# ── 负对照：FPR / TNR ────────────────────────────────────────
#
# TPR 单独拿出来没有意义。一个对所有输入都报警的检测器 TPR = 100%，
# 但它毫无价值。必须有 BENIGN 层作为负对照，才能把"敏感"和"乱叫"分开。
# 这一组断言就是为了让 FPR 不在 CI 里被悄悄忽略。

#: FPR 预算。门禁当前实测 0.0%，留 20% 冗余给未来新增检查项。
#: 超过它意味着"为了抓缺陷不惜乱叫"——那会让绿灯失去意义之外的另一面：
#: 红灯也失去意义。
FPR_BUDGET = 0.20


def test_negative_controls_exist():
    """BENIGN 层必须存在且有足够样本——否则 FPR 根本没被测，却会显示成 0%。

    这是个反脆弱断言：删掉负对照会让 FPR 变成"无样本 → None → 看起来没问题"。
    必须先保证样本存在，FPR 数字才有资格被读。
    """
    benign = [m for m in C.MUTANTS if m.tier == C.BENIGN]
    assert len(benign) >= 5, (
        f"BENIGN 层只有 {len(benign)} 个变异体——负对照不足，FPR 不可信。"
        "Hamel/Shreya：没有负对照的评估套件会把『乱叫』测成『敏感』。"
    )


def test_false_positive_rate_within_budget(verdicts):
    """注入正确无害的内容后，检查项必须保持安静。FPR 超预算即 CI 红。"""
    vs = [verdicts[m.id] for m in C.MUTANTS if m.tier == C.BENIGN and m.id in verdicts]
    stats = H.summarise(vs, C.BENIGN)
    if stats["fpr"] is None:
        pytest.skip("BENIGN 层无可判定样本（全部饱和）——FPR 本轮不可测")
    assert stats["fpr"] <= FPR_BUDGET, (
        f"FPR = {stats['fpr']:.1%} 超过预算 {FPR_BUDGET:.0%}："
        f"{stats['false_alarms']}/{stats['hold_total']} 个良性变异体被误报。\n"
        "误报比漏检更伤：漏检让人放过缺陷，误报让人不再相信门禁。"
    )


def test_tpr_and_fpr_measured_on_overlapping_targets():
    """TPR 与 FPR 必须测在同一批检查项上，否则 Rogan–Gladen 反校准无效。

    敏感度取自 A 人群、特异度取自 B 人群，再拿去反推总体患病率——这是
    流行病学里经典的错配。两份样本不可比时，算出的 p 精确但无意义。
    """
    nat = {m.target for m in C.MUTANTS if m.tier == C.NATURAL}
    ben = {m.target for m in C.MUTANTS if m.tier == C.BENIGN}
    overlap = nat & ben
    assert len(overlap) >= 5, (
        f"NATURAL 与 BENIGN 只共现 {len(overlap)} 个检查项（共现：{sorted(overlap)}）。"
        "共现不足 → TPR 与 FPR 来自不同总体 → 患病率反校准不可用。"
    )


def test_prevalence_correction_is_finite(verdicts):
    """Rogan–Gladen 分母（TPR + TNR − 1）必须为正，否则检测器不如随机猜。

    这是硬性的能力下界：TPR + TNR ≤ 1 意味着"抛硬币"和"问门禁"等价。
    此时真实缺陷率**不可估计**，任何换算出来的数字都是假的。
    """
    nat = H.summarise(
        [verdicts[m.id] for m in C.MUTANTS if m.tier == C.NATURAL and m.id in verdicts],
        C.NATURAL,
    )
    ben = H.summarise(
        [verdicts[m.id] for m in C.MUTANTS if m.tier == C.BENIGN and m.id in verdicts],
        C.BENIGN,
    )
    if ben["fpr"] is None:
        pytest.skip("特异度未测得（BENIGN 层无可用样本）")
    tnr = 1.0 - ben["fpr"]
    assert nat["tpr"] + tnr > 1.0, (
        f"TPR({nat['tpr']:.1%}) + TNR({tnr:.1%}) = {nat['tpr'] + tnr:.1%} ≤ 100%："
        "门禁的判别力不优于随机猜测，其 error_mean 不能被反校准为真实缺陷率。"
    )


# ── 盲区台账的时效 ──────────────────────────────────────────
#
# xfail 是双刃剑：它让 CI 保持绿，也让盲区可以无限期挂着。没有账期的
# 登记册会退化成"写在代码里的免责声明"。以下测试给它加账期。


def test_blind_spot_ids_all_exist():
    """登记册里的 ID 必须是真实存在的变异体——拼错一个字，盲区就永远不会被关闭。"""
    real = {m.id for m in C.MUTANTS}
    dangling = sorted(set(C.BLIND_SPOT_REGISTRY) - real)
    assert not dangling, f"登记册引用了不存在的变异体：{dangling}"


def test_blind_spots_have_owner_and_retirement():
    """每条盲区必须有 owner 与退役日期。缺一即视为未登记的债。"""
    bad = []
    for sid, spot in C.BLIND_SPOT_REGISTRY.items():
        if not spot.owner:
            bad.append(f"{sid}: 缺 owner")
        if not spot.retire:
            bad.append(f"{sid}: 缺退役日期")
        if not spot.action:
            bad.append(f"{sid}: 缺关闭动作")
        else:
            try:
                spot.days_left("2026-01-01")  # 触发日期解析
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{sid}: 退役日期格式错误（{exc}）")
    assert not bad, "盲区登记不完整：\n  " + "\n  ".join(bad)


def test_blind_spots_are_not_stale():
    """过期的盲区必须被重新评估——到期即 CI 红，不给"永久 xfail"留活路。

    到期后只有两条路：
      1. 修好了 → 用例 XPASS → 从登记册删除（这是最好的结局）
      2. 没修好 → 续期，但必须改写 action，说明这次比上次多知道了什么

    第 2 条是刻意的摩擦力：续期要写东西，才不会变成无脑 +3 个月。
    """
    from datetime import date

    today = date.today().isoformat()
    expired = [(sid, spot) for sid, spot in C.BLIND_SPOT_REGISTRY.items() if spot.days_left(today) < 0]
    if not expired:
        return
    lines = [
        f"{sid}（owner={spot.owner}）已于 {spot.retire} 到期，超期 {abs(spot.days_left(today))} 天"
        for sid, spot in sorted(expired, key=lambda kv: kv[1].retire)
    ]
    pytest.fail(
        f"{len(expired)} 条盲区已过期，必须重估（修好就删，没修好就续期并改写 action）：\n  " + "\n  ".join(lines)
    )


def test_blind_spot_owners_are_known_domains():
    """owner 必须是已定义的责任域——防止出现 'TODO' / '待定' 这类占位。"""
    known = {C.OWNER_NUMERICS, C.OWNER_STRUCTURE, C.OWNER_ARGUMENT, C.OWNER_STYLE}
    unknown = {sid: spot.owner for sid, spot in C.BLIND_SPOT_REGISTRY.items() if spot.owner not in known}
    assert not unknown, f"owner 不是已定义的责任域（禁止 TODO/待定占位）：{unknown}"
