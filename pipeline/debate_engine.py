"""
pipeline/debate_engine.py — 多智能体辩论引擎 V3 (Free-MAD 增强)

从 section_writer._debate_bold_call() 提取并增强：
1. 支持多轮迭代辩论（Bull↔Bear 交换论点，Judge 裁决）
2. 支持多模型并行（OpenRouter + Zen + DeepSeek 异源审查）
3. 辩论结果结构化（含置信度、证伪条件、数学信号覆盖）
4. 溯源链（每个观点链接到具体数据和推理过程）
5. Quant Referee 数学信号覆盖（LLM vs 量化冲突时量化优先）
6. 结构化输出（JSON 格式，便于下游消费）
7. Free-MAD 机制：轨迹评估 + 反从众 + 基于分数的决策

参考: Free-MAD (ACL 2026) - 消除共识需求的多智能体辩论框架
"""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.deepseek_client import call_deepseek

logger = logging.getLogger("2hao.debate_engine")


class DebateRole(Enum):
    BULL = "bull"
    BEAR = "bear"
    JUDGE = "judge"
    QUANT_REFEREE = "quant_referee"


@dataclass
class DebateArgument:
    """辩论论点"""

    role: DebateRole
    content: str
    confidence: float = 0.0  # 0-1
    evidence: list[str] = field(default_factory=list)  # 引用的数据源
    falsification: list[str] = field(default_factory=list)  # 证伪条件
    model_used: str = ""  # 使用的模型
    round_num: int = 0  # 辩论轮次
    timestamp: float = field(default_factory=time.time)
    key_points: list[str] = field(default_factory=list)  # 核心论点


@dataclass
class DebateResult:
    """辩论结果"""

    bull_thesis: str = ""
    bear_thesis: str = ""
    judge_conclusion: str = ""
    confidence: float = 0.0  # 最终置信度
    probability: float = 0.0  # 概率评估
    time_window: str = ""  # 时间窗口
    target_price: str = ""  # 目标价
    rating: str = ""  # 评级
    catalysts: list[str] = field(default_factory=list)  # 催化剂
    falsification_conditions: list[str] = field(default_factory=list)
    math_signal_override: bool = False  # 数学信号是否覆盖了 LLM 判断
    rounds: int = 0  # 实际辩论轮次
    total_duration_ms: float = 0.0
    arguments: list[DebateArgument] = field(default_factory=list)
    convergence_history: list[dict] = field(default_factory=list)  # 收敛历史


class DebateEngine:
    """
    多智能体辩论引擎 V2

    核心机制：
    1. Bull/Bear 多轮迭代（最多 N 轮，直到置信度收敛）
    2. Judge 综合裁决（含概率、时间窗口、证伪条件）
    3. Quant Referee 数学信号覆盖（LLM vs 量化冲突时量化优先）
    4. 多模型异源审查（可选）
    5. 结构化输出（JSON 格式，便于下游消费）
    """

    def __init__(
        self,
        max_rounds: int = 3,
        convergence_threshold: float = 0.15,
        use_multi_model: bool = False,
        providers: Optional[list[str]] = None,
    ):
        """
        Args:
            max_rounds: 最大辩论轮次
            convergence_threshold: 收敛阈值（Bull/Bear 置信度差值小于此值时停止）
            use_multi_model: 是否启用多模型异源审查
            providers: 多模型列表（当 use_multi_model=True 时使用）
        """
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.use_multi_model = use_multi_model
        self.providers = providers or ["opencode_go", "openrouter", "opencode_zen"]

    def debate(
        self,
        asset: str,
        data_str: str,
        report_type: str = "listed_company",
        compute_results: Optional[dict] = None,
        provider: str = "opencode_go",
    ) -> DebateResult:
        """
        执行完整辩论流程

        Args:
            asset: 标的名称
            data_str: 可用数据字符串
            report_type: 报告类型
            compute_results: 计算结果（用于数学信号覆盖）
            provider: LLM provider

        Returns:
            DebateResult: 辩论结果
        """
        start_time = time.time()
        result = DebateResult()

        base_prompt = f"分析标的:{asset}\n\n可用数据:{data_str[:800]}\n\n请给出该标的的核心投资判断。"

        bull_argument = None
        bear_argument = None

        for round_num in range(1, self.max_rounds + 1):
            logger.info("[DEBATE] Round %d/%d", round_num, self.max_rounds)

            # 多模型并行辩论（可选）
            if self.use_multi_model and round_num == 1:
                bull_argument, bear_argument = self._multi_model_debate(
                    base_prompt, report_type
                )
            else:
                # Bull 论点
                bull_prompt = self._build_bull_prompt(
                    base_prompt, bear_argument, round_num, report_type
                )
                bull_content = self._call_llm(bull_prompt, provider)
                bull_confidence = self._extract_confidence(bull_content)
                bull_argument = DebateArgument(
                    role=DebateRole.BULL,
                    content=bull_content,
                    confidence=bull_confidence,
                    evidence=self._extract_evidence(bull_content),
                    falsification=self._extract_falsification(bull_content),
                    key_points=self._extract_key_points(bull_content),
                    model_used=provider,
                    round_num=round_num,
                )
                result.arguments.append(bull_argument)

                # Bear 论点
                bear_prompt = self._build_bear_prompt(
                    base_prompt, bull_argument, round_num, report_type
                )
                bear_content = self._call_llm(bear_prompt, provider)
                bear_confidence = self._extract_confidence(bear_content)
                bear_argument = DebateArgument(
                    role=DebateRole.BEAR,
                    content=bear_content,
                    confidence=bear_confidence,
                    evidence=self._extract_evidence(bear_content),
                    falsification=self._extract_falsification(bear_content),
                    key_points=self._extract_key_points(bear_content),
                    model_used=provider,
                    round_num=round_num,
                )
                result.arguments.append(bear_argument)

            # 检查收敛
            confidence_diff = abs(bull_argument.confidence - bear_argument.confidence)
            logger.info(
                "[DEBATE] Round %d: Bull=%.2f Bear=%.2f diff=%.2f",
                round_num,
                bull_argument.confidence,
                bear_argument.confidence,
                confidence_diff,
            )

            # 记录收敛历史
            result.convergence_history.append({
                "round": round_num,
                "bull_confidence": bull_argument.confidence,
                "bear_confidence": bear_argument.confidence,
                "diff": confidence_diff,
            })

            if confidence_diff < self.convergence_threshold and round_num > 1:
                logger.info("[DEBATE] Converged at round %d", round_num)
                break

        # Judge 裁决
        judge_prompt = self._build_judge_prompt(
            base_prompt, bull_argument, bear_argument, report_type
        )
        judge_content = self._call_llm(judge_prompt, provider)
        judge_argument = DebateArgument(
            role=DebateRole.JUDGE,
            content=judge_content,
            confidence=self._extract_confidence(judge_content),
            model_used=provider,
            round_num=round_num,
        )
        result.arguments.append(judge_argument)

        # 数学信号覆盖检查
        if compute_results:
            math_override = self._check_math_signal_override(
                bull_argument, bear_argument, compute_results
            )
            result.math_signal_override = math_override
            if math_override:
                logger.info("[DEBATE] Math signal override activated")

        # 填充结果
        result.bull_thesis = bull_argument.content if bull_argument else ""
        result.bear_thesis = bear_argument.content if bear_argument else ""
        result.judge_conclusion = judge_content
        result.confidence = judge_argument.confidence
        result.probability = self._extract_probability(judge_content)
        result.time_window = self._extract_time_window(judge_content)
        result.target_price = self._extract_target_price(judge_content)
        result.rating = self._extract_rating(judge_content)
        result.catalysts = self._extract_catalysts(judge_content)
        result.falsification_conditions = self._merge_falsification(
            bull_argument, bear_argument
        )
        result.rounds = round_num
        result.total_duration_ms = (time.time() - start_time) * 1000

        return result

    def _multi_model_debate(
        self, base_prompt: str, report_type: str
    ) -> tuple[DebateArgument, DebateArgument]:
        """
        多模型并行辩论

        使用不同模型同时生成 Bull 和 Bear 论点
        """
        bull_prompt = self._build_bull_prompt(base_prompt, None, 1, report_type)
        bear_prompt = self._build_bear_prompt(base_prompt, None, 1, report_type)

        # 并行调用不同模型
        with ThreadPoolExecutor(max_workers=2) as executor:
            bull_future = executor.submit(
                self._call_llm, bull_prompt, self.providers[0]
            )
            bear_future = executor.submit(
                self._call_llm, bear_prompt, self.providers[1 % len(self.providers)]
            )

            bull_content = bull_future.result()
            bear_content = bear_future.result()

        bull_confidence = self._extract_confidence(bull_content)
        bear_confidence = self._extract_confidence(bear_content)

        bull_argument = DebateArgument(
            role=DebateRole.BULL,
            content=bull_content,
            confidence=bull_confidence,
            evidence=self._extract_evidence(bull_content),
            falsification=self._extract_falsification(bull_content),
            key_points=self._extract_key_points(bull_content),
            model_used=self.providers[0],
            round_num=1,
        )

        bear_argument = DebateArgument(
            role=DebateRole.BEAR,
            content=bear_content,
            confidence=bear_confidence,
            evidence=self._extract_evidence(bear_content),
            falsification=self._extract_falsification(bear_content),
            key_points=self._extract_key_points(bear_content),
            model_used=self.providers[1 % len(self.providers)],
            round_num=1,
        )

        return bull_argument, bear_argument

    def _build_bull_prompt(
        self,
        base_prompt: str,
        bear_argument: Optional[DebateArgument],
        round_num: int,
        report_type: str,
    ) -> str:
        """构建 Bull 提示词"""
        parts = [base_prompt]

        if report_type == "decision_memo":
            parts.append("\n\n从看多角度给出核心论点(300字以内),包含催化剂与预期回报。")
        else:
            parts.append("\n\n从看多角度给出核心论点(300字以内),包含目标价和催化剂。")

        if bear_argument and round_num > 1:
            parts.append(
                f"\n\n看空方上一轮论点:\n{bear_argument.content[:400]}\n\n"
                "请针对看空论点进行反驳，并强化你的看多论点。"
            )

        if round_num > 1:
            parts.append(f"\n\n[第{round_num}轮辩论] 请深化论点，引入新的证据或视角。")

        return "".join(parts)

    def _build_bear_prompt(
        self,
        base_prompt: str,
        bull_argument: Optional[DebateArgument],
        round_num: int,
        report_type: str,
    ) -> str:
        """构建 Bear 提示词"""
        parts = [base_prompt]

        if bull_argument:
            parts.append(
                f"\n\n看多方论点:\n{bull_argument.content[:400]}\n\n"
                "从看空角度反驳(300字以内),包含风险因素。"
            )
        else:
            parts.append("\n\n从看空角度给出核心论点(300字以内),包含风险因素。")

        if round_num > 1:
            parts.append(f"\n\n[第{round_num}轮辩论] 请深化反驳，找出对方论证的逻辑漏洞。")

        return "".join(parts)

    def _build_judge_prompt(
        self,
        base_prompt: str,
        bull_argument: Optional[DebateArgument],
        bear_argument: Optional[DebateArgument],
        report_type: str,
    ) -> str:
        """构建 Judge 提示词"""
        parts = [base_prompt]

        if bull_argument:
            parts.append(f"\n\n看多:\n{bull_argument.content[:400]}")
        if bear_argument:
            parts.append(f"\n\n看空:\n{bear_argument.content[:400]}")

        if report_type == "decision_memo":
            parts.append(
                "\n\n作为首席分析师,综合双方观点给出最终Bold Call(300字),"
                "包含概率、时间窗口和证伪条件。"
            )
        else:
            parts.append(
                "\n\n作为首席分析师,综合双方观点给出最终Bold Call(300字),"
                "包含目标价、概率、时间窗口和证伪条件。"
            )

        parts.append(
            "\n\n请按以下格式输出:\n"
            "1. 核心判断: [一句话结论]\n"
            "2. 目标价: [具体价格]\n"
            "3. 概率: [XX%]\n"
            "4. 时间窗口: [X个月]\n"
            "5. 催化剂: [关键事件]\n"
            "6. 证伪条件: [什么情况下判断错误]"
        )

        return "".join(parts)

    def _call_llm(self, prompt: str, provider: str = "opencode_go") -> str:
        """调用 LLM"""
        try:
            system_prompt = (
                "你是专业投资分析师。请基于数据给出结构化判断，"
                "避免空洞表述，每个论点必须有数据支撑。"
            )
            r = call_deepseek(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.35,
                max_tokens=2000,
                provider=provider,
            )
            return r["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("[DEBATE] LLM call failed: %s", e)
            return ""

    def _extract_confidence(self, text: str) -> float:
        """从文本中提取置信度"""
        # 尝试多种格式
        patterns = [
            r"置信度[：:]\s*(\d+\.?\d*)\s*%",
            r"信心[：:]\s*(\d+\.?\d*)\s*%",
            r"confidence[：:]\s*(\d+\.?\d*)\s*%",
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

    def _extract_evidence(self, text: str) -> list[str]:
        """提取证据引用"""
        evidence = []
        # 匹配 (A)/(E)/(F)/(B) 标注的数据
        matches = re.findall(r"[^。]*?[（(][AEFB][）)][^。]*。", text)
        evidence.extend(matches[:5])
        return evidence

    def _extract_falsification(self, text: str) -> list[str]:
        """提取证伪条件"""
        falsification = []
        patterns = [
            r"证伪[条件：:].*?。",
            r"风险[因素：:].*?。",
            r"若.*?则.*?。",
        ]
        for pat in patterns:
            matches = re.findall(pat, text)
            falsification.extend(matches[:3])
        return falsification

    def _extract_key_points(self, text: str) -> list[str]:
        """提取核心论点"""
        key_points = []
        # 匹配以数字开头的列表项
        matches = re.findall(r"[1-9][.、].*?(?=[1-9][.、]|\n|$)", text)
        key_points.extend(matches[:5])
        return key_points

    def _extract_probability(self, text: str) -> float:
        """提取概率"""
        m = re.search(r"(\d+\.?\d*)\s*%", text)
        if m:
            return float(m.group(1)) / 100
        return 0.5

    def _extract_time_window(self, text: str) -> str:
        """提取时间窗口"""
        patterns = [
            r"(\d+)\s*个月",
            r"(\d+)\s*年",
            r"未来\s*(\d+)",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group(0)
        return "12个月"

    def _extract_target_price(self, text: str) -> str:
        """提取目标价"""
        patterns = [
            r"目标价[：:]\s*(\d+\.?\d*)\s*元",
            r"目标价\s*(\d+\.?\d*)\s*元",
            r"(\d+\.?\d*)\s*元\s*目标价",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group(1) + "元"
        return ""

    def _extract_rating(self, text: str) -> str:
        """提取评级"""
        patterns = [
            r"评级[：:]\s*(买入|增持|持有|中性|减持|卖出)",
            r"(买入|增持|持有|中性|减持|卖出)\s*评级",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group(1)
        return ""

    def _extract_catalysts(self, text: str) -> list[str]:
        """提取催化剂"""
        catalysts = []
        patterns = [
            r"催化剂[：:].*?。",
            r"关键事件[：:].*?。",
            r"驱动因素[：:].*?。",
        ]
        for pat in patterns:
            matches = re.findall(pat, text)
            catalysts.extend(matches[:3])
        return catalysts

    def _check_math_signal_override(
        self,
        bull_argument: Optional[DebateArgument],
        bear_argument: Optional[DebateArgument],
        compute_results: dict,
    ) -> bool:
        """
        数学信号覆盖检查

        当 LLM 判断与量化信号冲突时，优先信任量化
        """
        if not compute_results:
            return False

        # 检查 DCF 结果
        dcf_value = compute_results.get("dcf_value")
        if dcf_value and bull_argument:
            # 如果 Bull 看多但 DCF 显示高估，触发覆盖
            price_match = re.search(r"目标价[：:]\s*(\d+\.?\d*)", bull_argument.content)
            if price_match:
                target_price = float(price_match.group(1))
                if target_price > dcf_value * 1.3:  # 目标价比 DCF 高 30%+
                    logger.warning(
                        "[MATH-OVERRIDE] Bull target %.1f >> DCF %.1f",
                        target_price,
                        dcf_value,
                    )
                    return True

        return False

    def _merge_falsification(
        self,
        bull_argument: Optional[DebateArgument],
        bear_argument: Optional[DebateArgument],
    ) -> list[str]:
        """合并证伪条件"""
        conditions = []
        if bull_argument:
            conditions.extend(bull_argument.falsification)
        if bear_argument:
            conditions.extend(bear_argument.falsification)
        # 去重
        return list(dict.fromkeys(conditions))[:5]

    def to_json(self, result: DebateResult) -> str:
        """将辩论结果转换为 JSON 格式"""
        data = {
            "bull_thesis": result.bull_thesis,
            "bear_thesis": result.bear_thesis,
            "judge_conclusion": result.judge_conclusion,
            "confidence": result.confidence,
            "probability": result.probability,
            "time_window": result.time_window,
            "target_price": result.target_price,
            "rating": result.rating,
            "catalysts": result.catalysts,
            "falsification_conditions": result.falsification_conditions,
            "math_signal_override": result.math_signal_override,
            "rounds": result.rounds,
            "total_duration_ms": result.total_duration_ms,
            "convergence_history": result.convergence_history,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    # ═══ Free-MAD 增强机制 (ACL 2026) ═══

    def evaluate_trajectory(self, result: DebateResult) -> float:
        """
        轨迹评估机制 (Free-MAD)

        评估整个辩论轨迹而非仅最后一轮
        基于每个论点的质量、证据强度、推理深度进行评分

        Returns:
            float: 轨迹质量分数 0-1
        """
        if not result.arguments:
            return 0.0

        scores = []
        for arg in result.arguments:
            # 论点质量评分
            arg_score = self._score_argument(arg)
            scores.append(arg_score)

        # 加权平均（后面的轮次权重更高）
        weights = [1.0 + i * 0.2 for i in range(len(scores))]
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

        return min(1.0, weighted_score)

    def _score_argument(self, arg: DebateArgument) -> float:
        """
        评分单个论点

        基于：
        - 证据数量和质量
        - 推理深度
        - 置信度合理性
        - 证伪条件完整性
        """
        score = 0.0

        # 证据评分 (0-0.3)
        evidence_score = min(0.3, len(arg.evidence) * 0.1)
        score += evidence_score

        # 推理深度评分 (0-0.3)
        reasoning_score = min(0.3, len(arg.key_points) * 0.1)
        score += reasoning_score

        # 置信度合理性 (0-0.2)
        # 置信度在 0.3-0.7 之间为合理
        if 0.3 <= arg.confidence <= 0.7:
            confidence_score = 0.2
        elif 0.2 <= arg.confidence <= 0.8:
            confidence_score = 0.1
        else:
            confidence_score = 0.0
        score += confidence_score

        # 证伪条件完整性 (0-0.2)
        falsification_score = min(0.2, len(arg.falsification) * 0.1)
        score += falsification_score

        return score

    def anti_conformity_adjustment(self, result: DebateResult) -> DebateResult:
        """
        反从众机制 (Free-MAD)

        减少多数派过度影响，保护少数派正确观点
        当 Bull 和 Bear 置信度差异过大时，提升少数派权重
        """
        if len(result.arguments) < 2:
            return result

        # 找出 Bull 和 Bear 的论点
        bull_args = [a for a in result.arguments if a.role == DebateRole.BULL]
        bear_args = [a for a in result.arguments if a.role == DebateRole.BEAR]

        if not bull_args or not bear_args:
            return result

        # 计算置信度差异
        bull_confidence = bull_args[-1].confidence
        bear_confidence = bear_args[-1].confidence
        confidence_diff = abs(bull_confidence - bear_confidence)

        # 如果差异过大（>0.3），触发反从众
        if confidence_diff > 0.3:
            logger.info("[FREE-MAD] Anti-conformity triggered: diff=%.2f", confidence_diff)

            # 提升少数派权重
            if bull_confidence > bear_confidence:
                # Bull 是多数派，提升 Bear 权重
                for arg in bear_args:
                    arg.confidence = min(1.0, arg.confidence * 1.2)
            else:
                # Bear 是多数派，提升 Bull 权重
                for arg in bull_args:
                    arg.confidence = min(1.0, arg.confidence * 1.2)

        return result

    def score_based_decision(self, result: DebateResult) -> dict:
        """
        基于分数的决策机制 (Free-MAD)

        评估整个辩论轨迹，而非仅看最后一轮
        返回综合评分和决策建议
        """
        # 轨迹评估
        trajectory_score = self.evaluate_trajectory(result)

        # 反从众调整
        adjusted_result = self.anti_conformity_adjustment(result)

        # 综合评分
        bull_score = 0.0
        bear_score = 0.0

        for arg in adjusted_result.arguments:
            arg_score = self._score_argument(arg)
            if arg.role == DebateRole.BULL:
                bull_score += arg_score
            elif arg.role == DebateRole.BEAR:
                bear_score += arg_score

        # 归一化
        total_score = bull_score + bear_score
        if total_score > 0:
            bull_normalized = bull_score / total_score
            bear_normalized = bear_score / total_score
        else:
            bull_normalized = 0.5
            bear_normalized = 0.5

        # 决策建议
        if bull_normalized > 0.6:
            decision = "看多"
            confidence = bull_normalized
        elif bear_normalized > 0.6:
            decision = "看空"
            confidence = bear_normalized
        else:
            decision = "中性"
            confidence = 0.5

        return {
            "trajectory_score": trajectory_score,
            "bull_score": bull_normalized,
            "bear_score": bear_normalized,
            "decision": decision,
            "confidence": confidence,
            "rounds": adjusted_result.rounds,
        }
