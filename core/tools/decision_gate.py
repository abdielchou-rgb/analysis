from enum import Enum

"""决策门结构 — 从线性分析升级为树形决策

核心理念（来自MBB）:
  传统SAC: Step1→Step2→Step3→...→Step7（线性, 必须走完）
  决策门SAC: Step1【决策门】→ 判断是否深入 → Step2【决策门】→ ...

每个决策门是二元判断:
  - GO: 继续深入（置信度足够, 存在alpha机会）
  - NO-GO: 跳过（行业/公司不值得深入, 或分歧不够大）

来源: 圆桌会议 MBB建议 + 实战sell-side分析师方法论
"""

from dataclasses import dataclass, field


class Decision(Enum):
    GO = "go"  # 继续深入
    NO_GO = "no_go"  # 跳过
    CONDITIONAL = "conditional"  # 有条件继续


@dataclass
class DecisionGate:
    """单个决策门"""

    step_name: str
    gate_question: str  # 决策问题
    go_criteria: list[str]  # 什么条件下GO
    no_go_criteria: list[str]  # 什么条件下NO-GO
    decision: Decision = Decision.GO
    confidence: float = 0.0  # 0.0-1.0
    reasoning: str = ""  # 决策理由
    time_cost_estimate: str = ""  # 如果GO, 预计还需要多少分析时间

    def to_dict(self) -> dict:
        return {
            "step": self.step_name,
            "gate": self.gate_question,
            "decision": self.decision.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "time_estimate": self.time_cost_estimate,
        }


@dataclass
class DecisionTree:
    """完整的决策树 — 替代线性SAC"""

    asset: str = ""
    report_type: str = ""
    gates: list[DecisionGate] = field(default_factory=list)
    overall_verdict: str = ""  # 最终是否值得深入
    alpha_confidence: float = 0.0  # 存在超额收益机会的置信度

    @property
    def go_gates(self) -> list[DecisionGate]:
        return [g for g in self.gates if g.decision == Decision.GO]

    @property
    def no_go_gates(self) -> list[DecisionGate]:
        return [g for g in self.gates if g.decision == Decision.NO_GO]

    @property
    def is_worth_deep_dive(self) -> bool:
        return len(self.go_gates) >= len(self.no_go_gates)

    def summary(self) -> str:
        lines = [f"## 决策门分析: {self.asset}"]
        lines.append(
            f"最终判断: {'值得深入' if self.is_worth_deep_dive else '不值得深入'} (置信度: {self.alpha_confidence:.0%})"
        )
        lines.append("")
        for g in self.gates:
            icon = "GO" if g.decision == Decision.GO else "NO-GO" if g.decision == Decision.NO_GO else "COND"
            lines.append(f"[{icon}] {g.step_name}: {g.gate_question}")
            lines.append(f"      理由: {g.reasoning}")
            lines.append(f"      置信度: {g.confidence:.0%}")
        return "\n".join(lines)


class DecisionGateBuilder:
    """决策门构建器 — 为行业/上市/非上市分别构建决策树"""

    # 行业分析决策门
    INDUSTRY_GATES = [
        DecisionGate(
            step_name="稀缺层定位",
            gate_question="行业是否存在真正的稀缺层/瓶颈？",
            go_criteria=["存在一个明确的、不可快速复制的瓶颈", "瓶颈层利润率远超上下游"],
            no_go_criteria=["行业无垂直分工差异", "所有环节利润率趋同", "资源供给充足"],
        ),
        DecisionGate(
            step_name="利润迁移判断",
            gate_question="利润正在迁移还是锁定？",
            go_criteria=["利润在3年内有明显迁移迹象", "技术变化正在重构价值链分配"],
            no_go_criteria=["利润分配5年未变化", "行业格局固化"],
        ),
        DecisionGate(
            step_name="投资机会判断",
            gate_question="是否存在明确的投资机会（Bold Call）？",
            go_criteria=["能找到方向+时间窗口+核心变量的清晰判断", "判断与市场共识有显著差异"],
            no_go_criteria=["判断与市场共识一致", "方向不明确或时间窗口无法确定"],
        ),
    ]

    # 上市公司分析决策门
    LISTED_GATES = [
        DecisionGate(
            step_name="核心分歧锁定",
            gate_question="市场共识与我们的判断是否存在显著分歧？",
            go_criteria=["分歧变量可量化", "分歧幅度>20%", "分歧方向可证伪"],
            no_go_criteria=["与市场共识一致", "分歧变量不可量化", "分歧<10%"],
        ),
        DecisionGate(
            step_name="商业模式验证",
            gate_question="分歧是否存在商业模式层面的支撑？",
            go_criteria=['护城河至少1项为"强"', "ROE>15%且可持续", "经营杠杆正向"],
            no_go_criteria=['护城河全部为"弱"', "ROE<8%", "商业模式不清晰"],
        ),
        DecisionGate(
            step_name="估值吸引力",
            gate_question="当前估值是否有吸引力？（基于我们的分歧判断）",
            go_criteria=["PE/PB处于历史30%分位以下", "我们的目标价有>30%上行空间"],
            no_go_criteria=["PE/PB处于历史70%分位以上", "上行空间<15%"],
        ),
    ]

    # 非上市公司分析决策门
    UNLISTED_GATES = [
        DecisionGate(
            step_name="数据充分性",
            gate_question="非上市数据是否足够支撑投资判断？",
            go_criteria=["有融资估值数据", "有可比公司", "行业TAM估算可行"],
            no_go_criteria=["没有任何财务数据", "行业无可比公司", "无法做任何估值估算"],
        ),
        DecisionGate(
            step_name="投资价值",
            gate_question="公司是否具备投资价值？",
            go_criteria=["退出路径清晰（IPO/并购）", "壁垒可持续", "估值有安全边际"],
            no_go_criteria=["退出路径不明确", "壁垒脆弱", "估值过高"],
        ),
    ]

    GATE_MAP = {
        "industry": INDUSTRY_GATES,
        "listed_company": LISTED_GATES,
        "unlisted_company": UNLISTED_GATES,
    }

    def __init__(self):
        pass

    def build_tree(self, asset: str, report_type: str) -> DecisionTree:
        """构建决策树"""
        gates = self.GATE_MAP.get(report_type, self.INDUSTRY_GATES)
        return DecisionTree(
            asset=asset,
            report_type=report_type,
            gates=[DecisionGate(**g.__dict__) for g in gates],
            overall_verdict="待判断",
            alpha_confidence=0.5,
        )

    def get_gate_text_for_prompt(self, report_type: str) -> str:
        """生成用于注入writing prompt的决策门文本"""
        gates = self.GATE_MAP.get(report_type, self.INDUSTRY_GATES)
        lines = ["\n## 决策门结构（必须执行）"]
        lines.append("在开始正式分析前, 先对每个决策门做出判断:")
        for i, g in enumerate(gates, 1):
            lines.append(f"\n### 决策门{i}: {g.step_name}")
            lines.append(f"核心问题: {g.gate_question}")
            lines.append(f"GO条件: {'; '.join(g.go_criteria)}")
            lines.append(f"NO-GO条件: {'; '.join(g.no_go_criteria)}")
        lines.append("\n### 最终决策")
        lines.append("如果3个决策门中有2个以上GO → 值得深入分析")
        lines.append("如果2个以上NO-GO → 建议跳过, 不需要写完整报告")
        return "\n".join(lines)
