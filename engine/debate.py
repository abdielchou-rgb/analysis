"""
Devil's Advocate Agent + 多 Agent 辩论架构。
参考 AlphaAnalyst: 强制使用不同模型族做反方辩论。
参考 FinRobot: lead orchestrator + modeler + debater + writer。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentRole(str, Enum):
    LEAD = "lead"  # 总协调
    MODELER = "modeler"  # 建模
    BULL = "bull"  # 看多方
    BEAR = "bear"  # 看空方 (Devil's Advocate)
    WRITER = "writer"  # 写作
    EDITOR = "editor"  # 编辑/审查


@dataclass
class AgentArgument:
    """Agent 论点"""

    agent_id: str
    role: AgentRole
    model_family: str  # 不同 agent 必须使用不同模型族
    position: str  # bull / bear / neutral
    thesis: str
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    risks: List[str] = field(default_factory=list)


@dataclass
class DebateRound:
    """辩论轮次"""

    round_number: int
    arguments: List[AgentArgument] = field(default_factory=list)
    consensus: Optional[str] = None


@dataclass
class DebateResult:
    """辩论结果"""

    rounds: List[DebateRound] = field(default_factory=list)
    bull_argument: Optional[AgentArgument] = None
    bear_argument: Optional[AgentArgument] = None
    final_consensus: str = ""
    risks_identified: List[str] = field(default_factory=list)
    confidence_adjustment: float = 0.0  # 调整后的置信度


class DevilAdvocateAgent:
    """Devil's Advocate Agent — 强制反方论证"""

    def __init__(self, agent_id: str = "devil_advocate", model_family: str = "different"):
        self.agent_id = agent_id
        self.model_family = model_family

    def challenge(self, bull_thesis: str, evidence: List[str], financials: Dict[str, Any]) -> AgentArgument:
        """对看多论点提出挑战"""
        risks = []
        counter_evidence = []

        # 检查常见风险
        if financials.get("debt_ratio", 0) > 0.6:
            risks.append("高杠杆风险: 负债率超过 60%")
        if financials.get("revenue_growth", 0) > 0.20:
            risks.append("增长可持续性风险: 增速超过 20% 难以维持")
        if financials.get("margin", 0) > 0.30:
            risks.append("利润率风险: 高利润率可能面临竞争压力")
        if financials.get("pe_ratio", 0) > 30:
            risks.append("估值风险: PE 超过 30 倍，预期已高")
        if financials.get("fcf_negative", False):
            risks.append("现金流风险: 自由现金流为负")
        if financials.get("related_party_transactions", False):
            risks.append("关联交易风险: 存在重大关联交易")

        # 生成反方论点
        counter_evidence.append("竞争格局可能恶化")
        counter_evidence.append("宏观经济下行风险")
        counter_evidence.append("政策监管变化风险")

        return AgentArgument(
            agent_id=self.agent_id,
            role=AgentRole.BEAR,
            model_family=self.model_family,
            position="bear",
            thesis=f"对看多论点的挑战: {bull_thesis[:100]}...",
            evidence=counter_evidence,
            confidence=0.4,
            risks=risks,
        )


class DebateOrchestrator:
    """辩论协调器 — 多 Agent 辩论流程"""

    def __init__(self, max_rounds: int = 2):
        self.max_rounds = max_rounds
        self.agents: Dict[AgentRole, Any] = {}

    def register_agent(self, role: AgentRole, agent: Any) -> None:
        self.agents[role] = agent

    def run_debate(
        self,
        bull_thesis: str,
        bull_evidence: List[str],
        financials: Dict[str, Any],
    ) -> DebateResult:
        """运行多轮辩论"""
        result = DebateResult()

        # Round 1: Bull presents
        bull_arg = AgentArgument(
            agent_id="bull_agent",
            role=AgentRole.BULL,
            model_family="model_a",
            position="bull",
            thesis=bull_thesis,
            evidence=bull_evidence,
            confidence=0.6,
        )
        result.bull_argument = bull_arg

        # Round 1: Bear challenges
        if AgentRole.BEAR in self.agents:
            bear_agent = self.agents[AgentRole.BEAR]
            bear_arg = bear_agent.challenge(bull_thesis, bull_evidence, financials)
            result.bear_argument = bear_arg
            result.risks_identified = bear_arg.risks

        # 生成共识
        result.final_consensus = self._generate_consensus(bull_arg, result.bear_argument)
        result.confidence_adjustment = self._compute_confidence_adjustment(bull_arg, result.bear_argument)

        return result

    def _generate_consensus(self, bull: AgentArgument, bear: Optional[AgentArgument]) -> str:
        if bear is None:
            return bull.thesis

        # 简化共识生成
        consensus_parts = [
            f"看多论点: {bull.thesis[:80]}...",
            f"看空挑战: {bear.thesis[:80]}...",
            f"识别风险: {', '.join(bear.risks[:3])}",
        ]
        return " | ".join(consensus_parts)

    def _compute_confidence_adjustment(self, bull: AgentArgument, bear: Optional[AgentArgument]) -> float:
        if bear is None:
            return 0.0
        # 如果 bear 信心很高，降低整体信心
        return -bear.confidence * 0.2
