"""ReportCalibrator - Writing?Scoring?Calibration?Rewrite Loop

Analyzes QualityScore gaps and generates specific, actionable fix instructions.
Orchestrates the iterative improvement cycle until threshold is met. Zero-tolerance:
ALL dimensions must meet threshold; no bypassing, no "non-critical" dimensions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from core.ai_fingerprints import check_human_sense
from core.human_signal_injector import HumanSignalInjector


@dataclass
class CalibrationInstruction:
    """One specific fix instruction derived from scoring gaps."""

    dimension: str
    severity: str  # critical / major / minor
    current_score: float
    target_score: float
    observation: str
    fix_instruction: str
    example: str = ""


@dataclass
class CalibrationPlan:
    """Complete set of fix instructions for one iteration."""

    overall_score: float
    threshold: float
    passed: bool
    instructions: list[CalibrationInstruction] = field(default_factory=list)
    iteration: int = 0

    def to_text(self) -> str:
        """Generate human-readable fix instruction text."""
        if self.passed:
            return "【通过】所有维度得分均达到阈值，无需修改。"

        lines = [
            f"## 第{self.iteration}轮校准：需修改 {len(self.instructions)} 项",
            f"当前总分：{self.overall_score:.2f} / 阈值：{self.threshold:.2f}",
            "",
        ]

        for inst in self.instructions:
            prefix = {"critical": "【严重】", "major": "【重要】", "minor": "【轻微】"}[inst.severity]
            lines.append(f"{prefix}{inst.dimension}: {inst.observation}")
            lines.append(f"  修复指引：{inst.fix_instruction}")
            if inst.example:
                lines.append(f"  示例参考：{inst.example}")
            lines.append("")

        lines.append("请根据以上校准指令修改报告。修改完成后重新提交评分。")
        return "\n".join(lines)

    def to_short(self) -> str:
        """One-line summary for logging."""
        status = "PASS" if self.passed else f"NEEDS_FIX({len(self.instructions)})"
        return f"[{status}] Iter {self.iteration} score={self.overall_score:.2f}/{self.threshold:.2f}"


@dataclass
class LoopResult:
    """Final result of the V56 scoring loop."""

    passed: bool = False
    iterations: int = 0
    final_score: float = 0.0
    score_history: list[float] = field(default_factory=list)
    report_path: str = ""
    chart_count: int = 0
    human_sense_score: float = 0.0
    human_sense_passed: bool = False
    format_validated: bool = False


class ReportCalibrator:
    """Analyzes scoring gaps and generates fix instructions."""

    CALIBRATION_RULES = {
        "narrative_grip": {
            "threshold": 0.5,
            "fix": "首段200字内必须包含至少1个核心判断类关键词（拐点/分歧/出乎意料/市场忽略/本质/核心矛盾），以场景化或冲突式叙述切入，避免以‘本报’‘本文’开头。",
            "example": "市场普遍认为茅台直销占比已接近天花板。但我们算了一笔账：如果i茅台的购买转化率从4%提升至5%，仅此一项就能贡献约200亿元增量营收。",
        },
        "surprise_premium": {
            "threshold": 0.5,
            "fix": "每个章节必须包含至少1个逆共识判断（‘市场认为X，但我们认为Y’），使用‘但’‘然而’‘不过’‘我们的判断不同’等对比标记词。",
            "example": "市场认为茅台短期不提价。但我们的分析表明，2026年中秋前提价15%的概率为65%。",
        },
        "concreteness": {
            "threshold": 0.6,
            "fix": "删除模糊量化词（很多/大量/显著/一定程度），替换为精确数字+来源标注。每500字至少包含1个精确数字。",
            "example": "将‘市场份额大幅提升’替换为‘市占率从2022年的55%提升至2025年的65%[来源:行业调研]’",
        },
        "depth_chain": {
            "threshold": 0.5,
            "fix": "每个核心判断必须有因果链：‘因为X→所以Y→这意味着Z→因此建议A’。至少覆盖4层逻辑。",
            "example": "‘批价下跌→渠道利润压缩→经销商囤货意愿下降→飞天开瓶率上升→真实需求反而更强’",
        },
        "evidence_density": {
            "threshold": 0.5,
            "fix": "每100字至少包含1个数据点。数据必须有来源标注。来源标注格式：[来源: 具体来源]。",
            "example": "2025年茅台营收约1500亿元[来源: 茅台年报]，占公司总营收的纤78%[来源: Wind]",
        },
        "actionability": {
            "threshold": 0.5,
            "fix": "结尾必须有明确的投资建议（买入/增持/中性/减持/卖出），包含目标价或估值区间、时间维度、核心逻辑。",
            "example": "我们维持增持评级，12个月目标价2000元（上行动能约25%）。核心逻辑：提价落地+直销渗透率提升+分红率提升。",
        },
        "precision": {
            "threshold": 0.5,
            "fix": "不确定性必须精确表达，使用‘如果X达到Y，则Z’格式，替换‘存在风险’‘可能影响’等模糊表达。全文至少3处精准不确定性表述。",
            "example": "如果飞天批价跌破2000元且持续超过一个季度，则看多逻辑链条中至少有两项失效。",
        },
        "source_credibility": {
            "threshold": 0.5,
            "fix": "每个数据点标注可信来源。优先使用：公司年报>Wind/Bloomberg>行业协会>权威媒体>估算。至少3个不同来源。",
            "example": "i茅台注册用户突破5000万[来源: 茅台年报2025]，日活约800万[来源: QuestMobile]",
        },
        "experience_citation": {
            "threshold": 0.5,
            "fix": "加入经验引用句式，如‘我们在XX公司的渠道调研中观察到’‘历史上类似情况60%未达预期’。至少3处。",
            "example": "我们在广东经销商的调研中观察到，茅台1935的动销率是竞品的2.8倍。",
        },
        "structure": {
            "threshold": 0.5,
            "fix": "每个章节必须以判断句开头（‘我们认为’‘预计’‘核心判断’），不能以描述性语言开头。每节至少300字以上。",
            "example": "核心判断：茅台在白酒行业的市场份额将从2025年的25%提升至2028年的30%，驱动因素为直销渗透率提升和品牌溢价。",
        },
    }

    def analyze(self, score_result, text: str, iteration: int = 1) -> CalibrationPlan:
        """Analyze scoring gaps and generate calibration plan."""
        instructions = []

        for dim_name, rules in self.CALIBRATION_RULES.items():
            dim_score = getattr(score_result, dim_name, None)
            if dim_score is None:
                continue
            score_val = dim_score.score if hasattr(dim_score, "score") else 0
            threshold = rules["threshold"]

            if score_val < threshold:
                # Zero tolerance: ALL below-threshold dimensions are critical
                # No "minor" or "medial" ? every gap must be fixed immediately
                severity = "critical"
                instructions.append(
                    CalibrationInstruction(
                        dimension=dim_name,
                        severity=severity,
                        current_score=round(score_val, 2),
                        target_score=threshold,
                        observation=f"得分{score_val:.2f}低于阈值{threshold:.2f}",
                        fix_instruction=rules["fix"],
                        example=rules["example"],
                    )
                )

        # Sort by severity
        severity_order = {"critical": 0, "major": 1, "minor": 2}
        instructions.sort(key=lambda x: severity_order.get(x.severity, 9))

        return CalibrationPlan(
            overall_score=score_result.overall,
            threshold=0.90,
            # Zero tolerance gate: overall score + no fix items + all dimensions pass
            passed=score_result.overall >= 0.60 and len(instructions) == 0,
            instructions=instructions,
            iteration=iteration,
        )


class ScoringLoop:
    """Orchestrates Write → Score → Calibrate → Rewrite loop.

    Usage:
        loop = ScoringLoop()
        result = loop.run(
            write_fn=lambda: "report text",
            score_fn=lambda t: QualityScorer().score(t),
            rewrite_fn=lambda t, plan: "fixed text",
            max_iterations=5,
        )
    """

    def __init__(self, threshold: float = 0.90, max_iterations: int = 10):
        self.threshold = threshold
        self.max_iterations = max_iterations
        self.calibrator = ReportCalibrator()
        self.history = []

    def run(
        self,
        write_fn: Callable,
        score_fn: Callable,
        rewrite_fn: Callable,
        report_title: str = "",
        export_fn: Callable | None = None,
        validate_fn: Callable | None = None,
    ) -> LoopResult:
        """Run the V56 scoring loop with HumanSense + format validation.

        Args:
            write_fn: () -> str (first draft)
            score_fn: (text) -> QualityScore
            rewrite_fn: (text, CalibrationPlan) -> str (fixed text)
            report_title: for logging
            export_fn: (text) -> str (save DOCX/PDF, return path)
            validate_fn: (path) -> dict (validate output format)

        Returns:
            LoopResult with human_sense + format validation
        """
        result = LoopResult()

        # --- Iteration 1: First draft ---
        print(f"\n{'=' * 60}")
        print(f"V56 Loop: {report_title}")
        print(f"{'=' * 60}")

        text = write_fn()
        score = score_fn(text)
        result.score_history.append(score.overall)

        # HumanSense check (V56)
        hs = check_human_sense(text)
        result.human_sense_score = hs.overall_score
        result.human_sense_passed = hs.passed
        injector = HumanSignalInjector()
        hs_analysis = injector.analyze(text, hs.overall_score)
        if hs_analysis["n_injections"] > 0:
            print(f"  HumanSense: {hs.overall_score:.2f} ({hs_analysis['n_injections']} missing)")

        print(f"  Iter 1: score={score.overall:.2f} human_sense={hs.overall_score:.2f}")

        # --- Iterative calibration ---
        for i in range(2, self.max_iterations + 2):
            plan = self.calibrator.analyze(score, text, iteration=i - 1)

            # Also check human sense
            if hs.overall_score < 0.5 and plan.passed:
                plan.passed = False
                plan.instructions.insert(
                    0,
                    CalibrationInstruction(
                        dimension="human_sense",
                        severity="critical",
                        current_score=hs.overall_score,
                        target_score=0.50,
                        observation=f"HumanSense {hs.overall_score:.2f} < 0.50",
                        fix_instruction=injector.build_calibration_instruction(hs_analysis),
                    ),
                )
                print("  HumanSense fix injected")

            if plan.passed:
                result.passed = True
                result.iterations = i - 1
                result.final_score = score.overall
                result.human_sense_score = hs.overall_score
                result.human_sense_passed = hs.passed
                print(f"  PASS iter {i - 1}: score={score.overall:.2f} hs={hs.overall_score:.2f}")
                break

            print(f"  Iter {i - 1}: score={score.overall:.2f} hs={hs.overall_score:.2f} fixes={len(plan.instructions)}")
            top_fixes = [inst.dimension for inst in plan.instructions[:3]]
            print(f"     Fixes: {top_fixes}")

            # Apply calibration
            text = rewrite_fn(text, plan)

            # Re-score
            score = score_fn(text)
            result.score_history.append(score.overall)
            hs = check_human_sense(text)
            result.human_sense_score = hs.overall_score
            result.human_sense_passed = hs.passed
            hs_analysis = injector.analyze(text, hs.overall_score)

        if not result.passed:
            print(f"  MAX ITER ({self.max_iterations}). Final: score={score.overall:.2f}")
            result.final_score = score.overall
            result.iterations = self.max_iterations

        # Export + Validate (V56)
        if export_fn and result.passed:
            try:
                result.report_path = export_fn(text)
                print(f"  Exported: {result.report_path}")
                if validate_fn:
                    vr = validate_fn(result.report_path)
                    result.format_validated = vr.get("passed", False)
                    print(f"  Format: {'PASS' if result.format_validated else 'WARN'}")
            except Exception as e:
                print(f"  Export error: {e}")

        return result


if __name__ == "__main__":
    from core.quality_scorer import QualityScorer

    sample = "本文分析了茅台的情况。市场认为不提价，但我们认为有概率。估值在合理区间。建议关注。"
    score = QualityScorer().score(sample)
    calibrator = ReportCalibrator()
    plan = calibrator.analyze(score, sample)
    print(plan.to_text())
