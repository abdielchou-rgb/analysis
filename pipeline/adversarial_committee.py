"""
pipeline/adversarial_committee.py — 多模型对抗委员会

参考 Roundtable 架构：
1. 多模型并行审查（OpenRouter + Zen + DeepSeek）
2. 对抗性验证（一个模型的论点必须经受另一个模型的挑战）
3. 置信度校准（不是简单的多数决）
4. 完整溯源（每个观点链接到具体模型和推理过程）
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

from core.deepseek_client import call_deepseek

logger = logging.getLogger("2hao.adversarial_committee")


@dataclass
class CommitteeMember:
    """委员会成员"""

    name: str
    role: str  # bull/bear/macro/valuation/risk
    provider: str
    model: str = ""
    weight: float = 1.0  # 权重


@dataclass
class MemberOpinion:
    """成员意见"""

    member: CommitteeMember
    content: str
    confidence: float = 0.0
    key_points: list[str] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)  # 对其他成员的挑战
    duration_ms: float = 0.0


@dataclass
class CommitteeResult:
    """委员会结果"""

    consensus: str = ""
    confidence: float = 0.0
    dissents: list[str] = field(default_factory=list)  # 异议
    member_opinions: list[MemberOpinion] = field(default_factory=list)
    total_duration_ms: float = 0.0
    convergence_rounds: int = 0


class AdversarialCommittee:
    """
    多模型对抗委员会

    核心机制：
    1. 多模型并行审查（不同模型担任不同角色）
    2. 对抗性验证（成员之间相互挑战）
    3. 置信度校准（加权平均，不是简单多数决）
    4. 完整溯源（每个观点链接到具体模型和推理过程）
    """

    def __init__(
        self,
        members: Optional[list[CommitteeMember]] = None,
        max_rounds: int = 2,
        convergence_threshold: float = 0.2,
    ):
        """
        Args:
            members: 委员会成员列表
            max_rounds: 最大审查轮次
            convergence_threshold: 收敛阈值
        """
        self.members = members or self._default_members()
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold

    def _default_members(self) -> list[CommitteeMember]:
        """默认委员会成员"""
        return [
            CommitteeMember(name="Bull Analyst", role="bull", provider="deepseek", weight=1.0),
            CommitteeMember(name="Bear Analyst", role="bear", provider="openrouter", weight=1.0),
            CommitteeMember(name="Macro Strategist", role="macro", provider="opencode", weight=1.2),
            CommitteeMember(name="Valuation Expert", role="valuation", provider="deepseek", weight=1.1),
            CommitteeMember(name="Risk Manager", role="risk", provider="openrouter", weight=1.0),
        ]

    def review(
        self,
        asset: str,
        data_str: str,
        report_type: str = "listed_company",
        compute_results: Optional[dict] = None,
    ) -> CommitteeResult:
        """
        执行委员会审查

        Args:
            asset: 标的名称
            data_str: 可用数据字符串
            report_type: 报告类型
            compute_results: 计算结果

        Returns:
            CommitteeResult: 委员会结果
        """
        start_time = time.time()
        result = CommitteeResult()

        base_prompt = f"分析标的:{asset}\n\n可用数据:{data_str[:800]}\n\n"

        # 第一轮：并行收集意见
        logger.info("[COMMITTEE] Round 1: Collecting opinions")
        opinions = self._collect_opinions(base_prompt, report_type)
        result.member_opinions.extend(opinions)

        # 第二轮：对抗性验证
        if self.max_rounds > 1:
            logger.info("[COMMITTEE] Round 2: Adversarial validation")
            challenges = self._adversarial_validation(base_prompt, opinions, report_type)
            result.member_opinions.extend(challenges)

        # 综合裁决
        consensus = self._synthesize_consensus(result.member_opinions)
        result.consensus = consensus.content
        result.confidence = consensus.confidence
        result.dissents = self._extract_dissents(result.member_opinions)
        result.convergence_rounds = self.max_rounds
        result.total_duration_ms = (time.time() - start_time) * 1000

        return result

    def _collect_opinions(self, base_prompt: str, report_type: str) -> list[MemberOpinion]:
        """并行收集意见"""
        opinions = []

        with ThreadPoolExecutor(max_workers=len(self.members)) as executor:
            futures = {}
            for member in self.members:
                prompt = self._build_member_prompt(base_prompt, member, report_type)
                future = executor.submit(self._call_member, member, prompt)
                futures[future] = member

            for future in as_completed(futures):
                member = futures[future]
                try:
                    opinion = future.result()
                    opinions.append(opinion)
                except Exception as e:
                    logger.error("[COMMITTEE] Member %s failed: %s", member.name, e)

        return opinions

    def _adversarial_validation(
        self,
        base_prompt: str,
        opinions: list[MemberOpinion],
        report_type: str,
    ) -> list[MemberOpinion]:
        """对抗性验证"""
        challenges = []

        # 让每个成员挑战其他成员的意见
        with ThreadPoolExecutor(max_workers=len(self.members)) as executor:
            futures = {}
            for member in self.members:
                # 找到其他成员的意见
                other_opinions = [o for o in opinions if o.member.name != member.name]
                if not other_opinions:
                    continue

                prompt = self._build_challenge_prompt(base_prompt, member, other_opinions, report_type)
                future = executor.submit(self._call_member, member, prompt)
                futures[future] = member

            for future in as_completed(futures):
                member = futures[future]
                try:
                    challenge = future.result()
                    challenges.append(challenge)
                except Exception as e:
                    logger.error("[COMMITTEE] Challenge from %s failed: %s", member.name, e)

        return challenges

    def _build_member_prompt(self, base_prompt: str, member: CommitteeMember, report_type: str) -> str:
        """构建成员提示词"""
        role_prompts = {
            "bull": "从看多角度分析，给出核心论点、催化剂和预期回报。",
            "bear": "从看空角度分析，给出核心风险、潜在问题和下行空间。",
            "macro": "从宏观环境分析，给出经济周期、政策影响和市场情绪判断。",
            "valuation": "从估值角度分析，给出合理估值范围和估值方法论。",
            "risk": "从风险管理角度分析，给出关键风险因素和风险缓释措施。",
        }

        role_prompt = role_prompts.get(member.role, "请给出你的专业分析。")

        return f"{base_prompt}\n\n{role_prompt}\n\n请给出结构化分析（300字以内）。"

    def _build_challenge_prompt(
        self,
        base_prompt: str,
        member: CommitteeMember,
        other_opinions: list[MemberOpinion],
        report_type: str,
    ) -> str:
        """构建挑战提示词"""
        challenges_text = "\n".join([f"- {o.member.name} ({o.member.role}): {o.content[:200]}" for o in other_opinions])

        return (
            f"{base_prompt}\n\n"
            f"其他分析师的意见:\n{challenges_text}\n\n"
            f"作为{member.role}分析师，请对上述意见进行挑战和补充。"
            f"指出逻辑漏洞、数据不足或视角缺失。"
            f"请给出你的挑战（200字以内）。"
        )

    def _call_member(self, member: CommitteeMember, prompt: str) -> MemberOpinion:
        """调用成员"""
        start_time = time.time()

        try:
            system_prompt = f"你是{member.name}，专注于{member.role}分析。请基于数据给出专业判断。"
            r = call_deepseek(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.35,
                max_tokens=1500,
                provider=member.provider,
            )
            content = r["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("[COMMITTEE] Member %s call failed: %s", member.name, e)
            content = ""

        duration_ms = (time.time() - start_time) * 1000

        return MemberOpinion(
            member=member,
            content=content,
            confidence=self._extract_confidence(content),
            key_points=self._extract_key_points(content),
            duration_ms=duration_ms,
        )

    def _synthesize_consensus(self, opinions: list[MemberOpinion]) -> MemberOpinion:
        """综合共识"""
        # 加权平均置信度
        total_weight = sum(o.member.weight for o in opinions)
        weighted_confidence = (
            sum(o.confidence * o.member.weight for o in opinions) / total_weight if total_weight > 0 else 0.5
        )

        # 综合内容
        key_points = []
        for opinion in opinions:
            key_points.extend(opinion.key_points)

        # 去重
        unique_points = list(dict.fromkeys(key_points))[:10]

        consensus_content = "综合委员会意见:\n" + "\n".join([f"- {p}" for p in unique_points])

        return MemberOpinion(
            member=CommitteeMember(name="Committee", role="consensus", provider=""),
            content=consensus_content,
            confidence=weighted_confidence,
            key_points=unique_points,
        )

    def _extract_dissents(self, opinions: list[MemberOpinion]) -> list[str]:
        """提取异议"""
        dissents = []

        # 找出置信度明显低于平均的意见
        avg_confidence = sum(o.confidence for o in opinions) / len(opinions) if opinions else 0.5

        for opinion in opinions:
            if opinion.confidence < avg_confidence - 0.2:
                dissents.append(f"{opinion.member.name} ({opinion.member.role}): {opinion.content[:100]}")

        return dissents

    def _extract_confidence(self, text: str) -> float:
        """提取置信度"""
        import re

        patterns = [
            r"置信度[：:]\s*(\d+\.?\d*)\s*%",
            r"信心[：:]\s*(\d+\.?\d*)\s*%",
            r"(\d+\.?\d*)\s*%\s*概率",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return float(m.group(1)) / 100

        # 默认根据论点强度估算
        strong_words = ["强烈", "非常", "明确", "坚定", "无疑"]
        weak_words = ["可能", "或许", "不确定", "存疑", "谨慎"]
        score = 0.5
        for w in strong_words:
            if w in text:
                score += 0.1
        for w in weak_words:
            if w in text:
                score -= 0.1
        return max(0.1, min(0.9, score))

    def _extract_key_points(self, text: str) -> list[str]:
        """提取核心论点"""
        import re

        key_points = []
        # 匹配以数字开头的列表项
        matches = re.findall(r"[1-9][.、].*?(?=[1-9][.、]|\n|$)", text)
        key_points.extend(matches[:5])
        return key_points
