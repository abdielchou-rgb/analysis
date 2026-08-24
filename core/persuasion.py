"""Persuasion Architecture - V54
Narrative arc: Hook -> Context -> Analysis -> Counter -> Conclusion -> CTA
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HookResult:
    hook_type: str = ""
    opening_line: str = ""
    full_hook: str = ""
    confidence: float = 0.0


@dataclass
class CTAResult:
    action_type: str = ""
    recommendation: str = ""
    time_horizon: str = ""
    conviction_level: str = "medium"


@dataclass
class PersuasionCheck:
    passed: bool = False
    has_hook: bool = False
    has_core_disagreement: bool = False
    has_counter_arguments: bool = False
    has_cta: bool = False
    issues: list[str] = field(default_factory=list)


class PersuasionArchitecture:
    """Builds narrative arc for reports."""

    def generate_hook(self, topic: str, core_disagreement: dict = None,
                       key_data_point: str = "", hook_type: str = "") -> HookResult:
        if not hook_type and core_disagreement:
            hook_type = "consensus_challenge"
        elif not hook_type:
            hook_type = "data_shock"

        result = HookResult(hook_type=hook_type)

        if core_disagreement:
            consensus = core_disagreement.get("market_consensus", "市场一致预期")
            our_view = core_disagreement.get("our_view", "我们的不同判断")
            key_var = core_disagreement.get("key_variable", "")

            result.opening_line = f"市场共识：{consensus}；我们判断：{our_view}"
            result.full_hook = (
                f"市场共识认为「{consensus}」。"
                f"我们认为这个判断忽略了关键变量「{key_var}」——"
                f"我们的分析表明「{our_view}」。"
            )
            result.confidence = 0.85
        else:
            result.opening_line = f"{topic}正在经历结构性变化"
            result.full_hook = (
                f"{topic}正在经历一次结构性变化——"
                f"我们的分析表明，这趟变化中的赢家与市场预期不同。"
            )

        return result

    def generate_cta(self, investment_thesis: str = "",
                     rating: str = "增持",
                     time_horizon: str = "12个月",
                     conviction_level: str = "medium") -> CTAResult:
        result = CTAResult(
            action_type="buy" if rating in ["增持","买入","超配"] else "watch",
            recommendation=(
                f"我们建议{rating}，{time_horizon}内核心关注。"
                f"核心逻辑：{investment_thesis}"
            ) if investment_thesis else "",
            time_horizon=time_horizon,
            conviction_level=conviction_level,
        )
        return result

    def check_persuasion(self, text: str) -> PersuasionCheck:
        check = PersuasionCheck()
        text_lower = text.lower()

        generic_starts = ["本报告", "本文", "以下是", "这是", "本文档"]
        check.has_hook = not any(text[:5].startswith(g) for g in generic_starts)

        first_20 = text[:int(len(text)*0.2)]
        check.has_core_disagreement = any(
            kw in first_20 for kw in ["市场共识", "我们认为", "核心分歧", "我们判断"]
        )

        check.has_counter_arguments = any(
            kw in text for kw in ["反对者认为", "看空", "空头", "风险在于", "另一种可能"]
        )

        last_30 = text[int(len(text)*0.7):]
        check.has_cta = any(
            kw in last_30 for kw in ["建议", "推荐", "关注", "买入", "增持", "减持", "观望"]
        )

        check.passed = all([
            check.has_hook, check.has_core_disagreement,
            check.has_counter_arguments, check.has_cta
        ])

        if not check.has_hook:
            check.issues.append("开篇缺乏Hook——避免用'本报告'开头")
        if not check.has_core_disagreement:
            check.issues.append("前20%内容未出现核心分歧")
        if not check.has_counter_arguments:
            check.issues.append("缺少反方论证")
        if not check.has_cta:
            check.issues.append("末尾缺少明确的投资建议")

        return check


if __name__ == "__main__":
    pa = PersuasionArchitecture()
    hook = pa.generate_hook("AI算力芯片", {
        "market_consensus": "GPU短期不可替代",
        "our_view": "ASIC在推理场景将快速渗透",
        "key_variable": "推理算力需求占比",
    })
    print(f"Hook: {hook.full_hook}")
    print(f"Confidence: {hook.confidence}")

    cta = pa.generate_cta("ASIC渗透率超预期，建议关注定制化芯片公司")
    print(f"CTA: {cta.recommendation}")

    # Test check
    report = "市场共识认为GPU不可替代。我们认为ASIC在崛起。看空者担心生态壁垒。建议增持。"
    check = pa.check_persuasion(report)
    print(f"Check passed: {check.passed}")
    print(f"Issues: {check.issues}")
