"""R1 变异测试执行器 — 跑 IronGate 并给出逐项差分结果。"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_ROOT = Path(__file__).resolve().parent.parent.parent

# corpus 只依赖标准库，无循环导入风险
from tests.gate_mutation.corpus import HOLD  # noqa: E402

# 三个走 LLM 的校验器。变异测试必须可离线、可重复、可归因——
# LLM 校验器不确定（同输入不同输出），且无网络时降级"放行"，
# 会把"未检出"伪装成"通过"。故一律打桩为满分 error。
LLM_CHECK_METHODS = (
    "_check_ai_tone_by_llm",
    "_check_human_impossible_dimension",
    "_check_llm_data_verification",
)

# 差分阈值：分数变化必须超过它才算"检出"，规避浮点噪声
EPS = 1e-6


@dataclass(frozen=True)
class Outcome:
    name: str
    passed: bool
    score: float
    severity: str
    details: str


@dataclass(frozen=True)
class Verdict:
    mutant_id: str
    target: str
    direction: str
    base_score: float
    mut_score: float
    delta: float
    killed: bool
    saturated: bool  # 基线已封顶/触底，该方向在数学上不可能被检出
    note: str = ""


def stub_llm_checks(monkeypatch):
    """把三个 LLM 校验器替换为确定性满分（供 gate 运行期使用）。"""
    from pipeline.checks.llm_checks_mixin import LlmChecksMixin
    from pipeline.iron_gate import GateCheckResult

    for name in LLM_CHECK_METHODS:
        if not hasattr(LlmChecksMixin, name):
            continue

        def _stub(self, _name=name):
            return GateCheckResult(
                name=_name.replace("_check_", ""),
                passed=True,
                score=1.0,
                details="[MUTATION-HARNESS] LLM 校验器已打桩（离线确定性）",
                severity="error",
            )

        monkeypatch.setattr(LlmChecksMixin, name, _stub, raising=False)


def run_gate(text: str, *, report_type: str = "industry_deep", style: str = "cicc", asset: str = "气体传感器"):
    """跑一次 IronGate，返回 {check_name: Outcome}。

    不用 IronGate.from_text——它以 delete=False 建临时文件且从不清理，
    跑 40 个变异体就漏 40 个临时文件。这里显式管理临时文件生命周期。
    """
    from pipeline.iron_gate import IronGate

    fd, tmp_path = tempfile.mkstemp(suffix=".md", prefix="gate_mut_", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        gate = IronGate(tmp_path, report_type=report_type, style=style, asset=asset)
        gate.report_text = text
        report = gate.run_all()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return {
        c.name: Outcome(name=c.name, passed=bool(c.passed), score=float(c.score), severity=c.severity, details=str(c.details))
        for c in report.checks
    }


def load_baseline(name: str = "gas_sensor_cicc.md") -> str:
    return (_ROOT / "tests" / "golden" / name).read_text(encoding="utf-8")


def evaluate(mutant, baseline_text: str, baseline_results: dict[str, Outcome], run: Callable[[str], dict]) -> Verdict:
    """注入变异体 → 比对目标检查项相对基线的变化。"""
    base = baseline_results.get(mutant.target)
    if base is None:
        return Verdict(
            mutant.id,
            mutant.target,
            mutant.direction,
            float("nan"),
            float("nan"),
            float("nan"),
            False,
            False,
            note="基线中不存在该检查项（检查项名拼写错误或已下线）",
        )

    mutated_text = mutant.apply(baseline_text)
    cur = run(mutated_text).get(mutant.target)
    if cur is None:
        return Verdict(
            mutant.id,
            mutant.target,
            mutant.direction,
            base.score,
            float("nan"),
            float("nan"),
            False,
            False,
            note="变异体中该检查项未产出结果",
        )

    # 双信号判据：分数变化 **或** details 文本变化。
    # 只用分数会被"评分函数饱和"误导——实测 completeness_scan 在基线已有 6 项
    # 问题时分数钉在 0.30，再加缺陷分数不动，但 details 明明从"6 项"变成"7 项"。
    # 只报分数会把这类"检查项其实响应了"误判成"检查项失灵"。
    delta = cur.score - base.score
    details_changed = cur.details != base.details
    from tests.gate_mutation.corpus import HOLD

    if mutant.direction == HOLD:
        # 基线已经红了 → 它本来就在叫，无法据此判断"会不会误报"
        saturated = not base.passed
        # 保持安静 = 仍然通过 + 分数不动 + details 不变
        killed = cur.passed and (not details_changed) and abs(delta) < EPS
    elif mutant.direction == "drop":
        saturated = base.score <= 0.0 + EPS
        killed = (delta < -EPS) or (details_changed and not cur.passed) or (details_changed and not base.passed)
    else:
        saturated = base.score >= 1.0 - EPS
        killed = (delta > EPS) or (details_changed and cur.passed and not base.passed)

    if saturated and not killed:
        if mutant.direction == HOLD:
            note = f"基线已报红（{base.score:.2f}），无法度量误报 → N/A"
        else:
            note = f"基线已{'触底' if mutant.direction == 'drop' else '封顶'}（{base.score:.2f}），该方向不可检出 → N/A"
    elif killed:
        note = "KILLED" + (f"（Δ={delta:+.3f}）" if abs(delta) > EPS else "（details 变化）")
    else:
        note = f"SURVIVED（Δ={delta:+.3f}，details 未变）——检查项对该缺陷无反应"

    return Verdict(
        mutant.id,
        mutant.target,
        mutant.direction,
        base.score,
        cur.score,
        delta,
        killed,
        saturated,
        note=note,
    )


def summarise(verdicts: list[Verdict], tier: str | None = None) -> dict:
    """汇总为 TPR 表所需的统计。tier 传入则只统计该层。"""
    if tier is not None:
        from tests.gate_mutation.corpus import MUTANTS

        wanted = {m.id for m in MUTANTS if m.tier == tier}
        verdicts = [v for v in verdicts if v.mutant_id in wanted]
    applicable = [v for v in verdicts if not v.saturated and v.base_score == v.base_score]
    killed = [v for v in applicable if v.killed]
    survived = [v for v in applicable if not v.killed]

    # HOLD 方向：killed 表示"保持安静"（正确行为），未 killed 即误报
    hold = [v for v in applicable if v.direction == HOLD]
    quiet = [v for v in hold if v.killed]
    false_alarms = [v for v in hold if not v.killed]

    return {
        "total_mutants": len(verdicts),
        "applicable": len(applicable),
        "killed": len(killed),
        "survived": len(survived),
        "na_saturated": len([v for v in verdicts if v.saturated]),
        "na_missing": len([v for v in verdicts if v.base_score != v.base_score]),
        "tpr": (len(killed) / len(applicable)) if applicable else 0.0,
        "survivors": survived,
        "hold_total": len(hold),
        "quiet": len(quiet),
        "false_alarms": len(false_alarms),
        "fpr": (len(false_alarms) / len(hold)) if hold else None,
    }


def rogan_gladen(observed_fail_rate: float, tpr: float, tnr: float) -> float | None:
    """用不完美检测器的敏感度/特异度反推**真实**缺陷率。

    观测失败率 = p·TPR + (1−p)·(1−TNR)   ⟹   p = (观测值 − (1−TNR)) / (TPR + TNR − 1)

    这就是流行病学的 Rogan–Gladen 估计量：用不完美诊断工具的结果反推真实
    患病率。迁移到这里——门禁就是一个不完美的诊断工具，它的 error_mean
    是"观测患病率"，不是真实缺陷率。

    分母 ≤ 0（TPR + TNR ≤ 1，即检测器不如随机猜）或结果越界时返回 None：
    这种情况下真实率**不可估计**，硬算会给出一个看起来精确其实无意义的数。
    """
    denom = tpr + tnr - 1.0
    if denom <= 1e-9:
        return None
    p = (observed_fail_rate - (1.0 - tnr)) / denom
    if p < -1e-9 or p > 1.0 + 1e-9:
        return None
    return min(1.0, max(0.0, p))
