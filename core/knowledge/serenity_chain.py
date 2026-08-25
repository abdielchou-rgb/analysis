# Serenity Reasoning Chain - from V30 Heritage (muxuu ecosystem)
# 9-step structured reasoning: from problem definition to investment conclusion

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SerenityStep:
    step_id: int
    name: str
    content: str
    passed: Optional[bool] = None


@dataclass
class SerenityResult:
    steps: List[SerenityStep]
    all_passed: bool
    failed_steps: List[str]


SERENITY_STEPS = [
    (1, "问题定义", "明确分析的核心问题:是什么在变?为什么在变?"),
    (2, "范围界定", "界定分析的时间和空间边界:什么包括/什么不包括"),
    (3, "假设生成", "提出可检验的分析假设(至少3个)"),
    (4, "数据采集", "确定需要哪些数据来检验每个假设"),
    (5, "证据评估", "对采集到的证据进行可信度评估(L1-L7阶梯)"),
    (6, "推理合成", "将分散的证据合成为连贯的判断链"),
    (7, "反方检验", "主动寻找能够推翻判断的反面证据"),
    (8, "结论收敛", "从多个可能结论中收敛到最合理的判断"),
    (9, "可证伪表达", "确保最终判断具备可证伪性:什么情况下会错"),
]


def run_serenity(text: str) -> SerenityResult:
    """Check if a report follows the Serenity reasoning chain"""
    import re

    steps = []
    failed = []

    checks = [
        (1, "问题定义", r"问题|核心|为什么|是什么"),
        (2, "范围界定", r"范围|边界|包括|时间段|空间"),
        (3, "假设生成", r"假设|如果|若|前提|条件"),
        (4, "数据采集", r"数据|来源|采集|证据"),
        (5, "证据评估", r"可信度|置信度|来源等级|L[1-7]"),
        (6, "推理合成", r"因此|所以|综合|整合|合成|判断链"),
        (7, "反方检验", r"反方|另一|反面|其他可能|异议|反驳"),
        (8, "结论收敛", r"结论|收敛|综合判断|核心判断"),
        (9, "可证伪表达", r"证伪|如果.*错|如果.*不"),
    ]

    for sid, sname, pattern in checks:
        found = bool(re.search(pattern, text, re.IGNORECASE))
        steps.append(SerenityStep(step_id=sid, name=sname, content=f"检查模式:{pattern}", passed=found))
        if not found:
            failed.append(f"Step{sid}:{sname}")

    return SerenityResult(steps=steps, all_passed=len(failed) == 0, failed_steps=failed)


def generate_missing_steps(result: SerenityResult) -> str:
    if not result.failed_steps:
        return ""
    lines = ["[Serenity Chain] 以下推理步骤缺失:"]
    for f in result.failed_steps:
        lines.append(f"  - {f}")
    lines.append("建议补充后再输出最终判断")
    return chr(10).join(lines)
