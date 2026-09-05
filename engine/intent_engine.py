"""
Intent Engine — 决策意图编译器。
将模糊的投资问题分解为结构化的 MECE Issue Tree + Expectations Investing 框架。

组件:
1. MECEIssueTree: 递归分解投资论题为可检验假设
2. ExpectationsInvesting: 价格 → 隐含假设 → 差距分析
3. ResearchPlanGenerator: IssueTree → 数据需求 → 计算步骤
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IssueNodeType(str, Enum):
    THESIS = "thesis"
    HYPOTHESIS = "hypothesis"
    DATA_NEED = "data_need"
    FALSIFIER = "falsifier"


class DecisionPersona(str, Enum):
    """决策主体画像"""

    EQUITY_RESEARCH = "equity_research"
    PE_FUND = "pe_fund"
    CORPORATE_MA = "corporate_ma"
    DISTRESSED_DEBT = "distressed_debt"
    LONG_ONLY = "long_only"


@dataclass
class IssueNode:
    """Issue Tree 节点"""

    id: str
    label: str
    node_type: IssueNodeType
    children: list[IssueNode] = field(default_factory=list)
    data_source: str | None = None
    status: str = "pending"  # pending / confirmed / refuted / partial
    priority: int = 0  # 0=high, 1=medium, 2=low

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.node_type.value,
            "status": self.status,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class ResearchPlan:
    """结构化研究计划"""

    thesis: str
    persona: DecisionPersona
    hypotheses: list[dict] = field(default_factory=list)
    data_needs: list[dict] = field(default_factory=list)
    falsifiers: list[dict] = field(default_factory=list)
    computation_steps: list[str] = field(default_factory=list)
    estimated_complexity: str = "medium"  # low / medium / high


class MECEIssueTree:
    """MECE Issue Tree 构建器 — 将投资论题递归分解"""

    # 预定义模板: 按商业模式分类
    TEMPLATES = {
        "revenue_growth": {
            "label": "营收增长可持续性",
            "children": [
                {"label": "量: 用户/销量增长", "type": "hypothesis"},
                {"label": "价: 提价能力/ASP", "type": "hypothesis"},
                {"label": "结构: 产品mix变化", "type": "hypothesis"},
            ],
        },
        "margin_expansion": {
            "label": "利润率扩张空间",
            "children": [
                {"label": "规模效应: 固定成本摊薄", "type": "hypothesis"},
                {"label": "运营杠杆: 人效提升", "type": "hypothesis"},
                {"label": "产品mix: 高毛利占比提升", "type": "hypothesis"},
            ],
        },
        "multiple_rerating": {
            "label": "估值重估可能性",
            "children": [
                {"label": "风险溢价下降: 政策/治理改善", "type": "hypothesis"},
                {"label": "增长溢价: 新曲线/出海", "type": "hypothesis"},
                {"label": "同业对标: 隐含折价收窄", "type": "hypothesis"},
            ],
        },
        "capital_allocation": {
            "label": "资本配置效率",
            "children": [
                {"label": "ROIC > WACC 持续性", "type": "hypothesis"},
                {"label": "分红/回购力度", "type": "hypothesis"},
                {"label": "并购整合风险", "type": "hypothesis"},
            ],
        },
    }

    def __init__(self, thesis: str, company_context: dict | None = None):
        self.thesis = thesis
        self.context = company_context or {}
        self.root = IssueNode(
            id="root",
            label=thesis,
            node_type=IssueNodeType.THESIS,
        )

    def decompose(self, max_depth: int = 3) -> IssueNode:
        """递归分解论题为可检验假设"""
        # 根据公司类型选择模板
        biz_model = self.context.get("biz_model", "revenue_growth")

        # 添加一级假设
        template = self.TEMPLATES.get(biz_model, self.TEMPLATES["revenue_growth"])
        for i, child in enumerate(template["children"]):
            node = IssueNode(
                id=f"h{i + 1}",
                label=child["label"],
                node_type=IssueNodeType(child["type"]),
            )
            # 添加数据需求
            node.children.append(
                IssueNode(
                    id=f"d{i + 1}_1",
                    label=f"获取 {child['label']} 相关数据",
                    node_type=IssueNodeType.DATA_NEED,
                    data_source=self._suggest_source(child["label"]),
                )
            )
            # 添加证伪条件
            node.children.append(
                IssueNode(
                    id=f"f{i + 1}_1",
                    label=f"{child['label']} 的反面证据",
                    node_type=IssueNodeType.FALSIFIER,
                )
            )
            self.root.children.append(node)

        return self.root

    def to_research_plan(self, persona: DecisionPersona = DecisionPersona.EQUITY_RESEARCH) -> ResearchPlan:
        """转换为结构化研究计划"""
        plan = ResearchPlan(
            thesis=self.thesis,
            persona=persona,
        )

        for child in self.root.children:
            if child.node_type == IssueNodeType.HYPOTHESIS:
                plan.hypotheses.append(child.to_dict())
                for sub in child.children:
                    if sub.node_type == IssueNodeType.DATA_NEED:
                        plan.data_needs.append(sub.to_dict())
                    elif sub.node_type == IssueNodeType.FALSIFIER:
                        plan.falsifiers.append(sub.to_dict())

        # 根据 persona 生成计算步骤
        plan.computation_steps = self._compute_steps_for_persona(persona)
        plan.estimated_complexity = self._estimate_complexity()

        return plan

    def _suggest_source(self, label: str) -> str:
        """根据假设类型建议数据来源"""
        source_map = {
            "量": "年报销量数据 + 行业统计",
            "价": "定价公告 + 行业价格指数",
            "规模": "固定成本明细 + 产能利用率",
            "ROIC": "ROIC 历史趋势 + 同业对比",
            "风险": "政策文件 + 治理评级",
            "分红": "分红历史 + 股东回报政策",
        }
        for keyword, source in source_map.items():
            if keyword in label:
                return source
        return "财报 + 行业报告"

    def _compute_steps_for_persona(self, persona: DecisionPersona) -> list[str]:
        """根据决策主体画像生成计算步骤"""
        steps_map = {
            DecisionPersona.EQUITY_RESEARCH: [
                "三表联动推演",
                "DCF 估值 + 敏感性矩阵",
                "可比公司估值",
                "情景分析 (Bull/Base/Bear)",
                "Monte Carlo 模拟",
            ],
            DecisionPersona.PE_FUND: [
                "LBO 模型",
                "IRR/MOIC 敏感性",
                "现金流偿债能力分析",
                "Exit Multiple 敏感性",
                "PIK toggle 场景",
            ],
            DecisionPersona.CORPORATE_MA: [
                "EPS 增厚/摊薄分析",
                "协同效应 NPV",
                "整合风险调整",
                "商誉减值测试",
                "Synergy realization timeline",
            ],
            DecisionPersona.DISTRESSED_DEBT: [
                "流动性压力测试",
                "债务到期分布",
                "破产清算价值",
                "重组方案比较",
                "DSCR/ICR 临界点",
            ],
            DecisionPersona.LONG_ONLY: [
                "DCF 公允价值",
                "股息折现模型",
                "同业估值对比",
                "安全边际计算",
                "长期回报率测算",
            ],
        }
        return steps_map.get(persona, steps_map[DecisionPersona.EQUITY_RESEARCH])

    def _estimate_complexity(self) -> str:
        """估算研究复杂度"""
        n_children = len(self.root.children)
        if n_children >= 4:
            return "high"
        elif n_children >= 2:
            return "medium"
        return "low"


class ExpectationsInvesting:
    """期望投资法 — 价格 → 隐含假设 → 差距分析"""

    def analyze(
        self,
        current_price: float,
        reverse_dcf_result: dict,
        our_assumptions: dict,
    ) -> dict:
        """三步分析:
        1. 市场当前 Price-in 了什么? (reverse DCF)
        2. 我们的假设是什么? (our model)
        3. 差距在哪里? 什么催化剂会改变?
        """
        implied_growth = reverse_dcf_result.get("implied_growth_rate", 0)
        our_growth = our_assumptions.get("revenue_growth", 0)

        gap_pp = (our_growth - implied_growth) * 100

        # 判断立场
        if gap_pp > 5:
            stance = "BULLISH: 我们假设高于市场隐含"
        elif gap_pp < -5:
            stance = "BEARISH: 我们假设低于市场隐含"
        else:
            stance = "NEUTRAL: 假设基本一致"

        return {
            "current_price": current_price,
            "market_implied_growth": f"{implied_growth:.1%}",
            "our_growth_assumption": f"{our_growth:.1%}",
            "expectation_gap_pp": round(gap_pp, 1),
            "stance": stance,
            "key_question": self._key_question(gap_pp, implied_growth),
            "catalysts_to_watch": self._catalyst_list(our_assumptions),
        }

    def _key_question(self, gap_pp: float, implied_growth: float) -> str:
        if gap_pp > 10:
            return f"市场仅隐含 {implied_growth:.1%} 增长，我们为何如此乐观? 核心催化剂是什么?"
        elif gap_pp < -10:
            return f"市场隐含 {implied_growth:.1%} 增长，我们为何如此悲观? 下行风险是什么?"
        return "当前定价合理，需要关注什么信号来改变判断?"

    def _catalyst_list(self, assumptions: dict) -> list[str]:
        catalysts = []
        if assumptions.get("new_product"):
            catalysts.append("新产品上市放量")
        if assumptions.get("overseas_expansion"):
            catalysts.append("海外市场拓展")
        if assumptions.get("policy_change"):
            catalysts.append("政策变化")
        catalysts.append("季度财报超/低于预期")
        catalysts.append("行业竞争格局变化")
        return catalysts
