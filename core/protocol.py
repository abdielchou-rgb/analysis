"""V50+ research protocol

MECE + Serenity 9-step for ALL industry reports.

V51.6 方法论文档注入（来自UBS/BOA/高盛/中金培训材料）:
  - to_agent_brief() 输出时自动追加投行方法论框架
  - 不增加规则（规则够多了），增加思考框架
  - 自然地吸收，不机械引用
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from core.methodology_injector import inject_into_protocol


@dataclass
class ResearchTask:
    task_id: str = ""
    dimension_id: str = ""
    question: str = ""
    evidence_min: int = 1
    counter_required: bool = False
    evidence_found: int = 0
    counter_found: int = 0
    completed: bool = False
    findings: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    strongest_evidence: str = ""

    def to_instruction(self) -> str:
        lines = [f"## Task: {self.question}", f"ID: {self.task_id}", f"Min evidence: {self.evidence_min}"]
        if self.counter_required:
            lines.append("Counter evidence: required (>=1)")
        lines.append("Fill: findings=..., gaps=..., strongest_evidence=...")
        return "\n".join(lines)


@dataclass
class ResearchProtocol:
    brief_id: str = ""
    report_type: str = ""
    output_depth: str = "standard"
    sac_id: str = ""
    title: str = ""
    core_question: str = ""
    tasks: list[ResearchTask] = field(default_factory=list)
    all_completed: bool = False
    total_evidence_found: int = 0
    total_gaps: list[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_agent_brief(self) -> str:
        # 先构建原有协议文本
        lines = [
            f"# Protocol: {self.title}",
            f"SAC: {self.sac_id}",
            f"Core: {self.core_question} | Depth: {self.output_depth}",
            f"Tasks: {len(self.tasks)} (complete ALL before writing. Format and structure of the report is YOUR CHOICE as long as all dimensions are covered.)",
            "",
            "---",
            "",
        ]
        for t in self.tasks:
            lines.append(t.to_instruction())
            lines.append("")
        lines.append("---")
        w = []
        if self.output_depth == "brief":
            w = [
                "### BRIEF (5 min)",
                "覆盖全部 MECE + S9 dimensions. 上限 800 字。",
                "核心判断（一句话）+ 核心分歧（一段话）放在第二页。",
                "最强证据（3-4 个维度）。 一个风险/缺口。",
            ]
        elif self.output_depth == "deep":
            w = [
                "### 深度报告",
                "覆盖全部 MECE + S9. Min 12 sources.",
                "核心分歧在第二页。30-60 页。",
                "每章至少有一个锐利判断。 找不到就说明这一章还没准备好。",
            ]
        else:
            w = [
                "### 标准报告",
                "覆盖全部 MECE + S9. Min 8 sources.",
                "核心分歧在第二页。15-25 页。",
                "每章至少有一个锐利判断。",
            ]
        lines += w

        # 全局结构约束（新增：行业深度必须按维度独立成章）
        if self.sac_id == "sac_industry_deep":
            lines += [
                "",
                "### 结构约束（行业深度报告专用）",
                "- 报告必须按以下12个维度独立成章（每个维度至少一个独立章节，不可合并）：",
                "  1. 核心锐判（Bold Call / 分歧定位 / 增量信息，三选一）",
                "  2. 核心分歧与极性（市场共识 vs 我们的分析）",
                "  3. 行业边界定义（L1/L2/L3细分赛道）",
                "  4. 生命周期与产业阶段（导入/成长/成熟/衰退 + 分歧判断）",
                "  5. 政策传导链（政策→行业→利润→股价，4跳完整）",
                "  6. 市场空间（TAM + 渗透率 + 天花板，2种方法交叉验证）",
                "  7. 供需分析（结构/约束/平衡 + 稀缺瓶颈判断）",
                "  8. 利润池（分布/迁移/定价权 —— 这是核心差异章节）",
                "  9. 竞争格局（梯队/CR3/CR5/壁垒 —— 每梯队必须有判断）",
                "  10. 技术路线（当前 vs 下一代 —— 如行业成熟可跳过但需注明）",
                "  11. 资本市场映射（估值锚/催化剂日历/风险收益）",
                "  12. 证伪条件（3+量化触发条件 + 跟踪指标）",
                "- 禁止将多个维度合并到一个章节中（如'供需+竞争'作为一章）",
                "- 每个维度章节标题必须包含维度核心词（如'市场空间''竞争格局'）",
                "- 每章至少包含一个'我们认为/我们判断'的主观判断句",
                "- 最后两章必须是'资本市场映射'和'证伪条件'",
            ]
        elif self.sac_id == "sac_listed_company":
            lines += [
                "",
                "### 结构约束（上市公司深度专用）",
                "- 报告必须按以下9个维度独立成章：",
                "  1. 核心分歧（市场共识 vs 我们的分析，必须第二页）",
                "  2. 商业模式（利润驱动因素 + 护城河判断）",
                "  3. 财务分析（收入/利润/ROE拆解——必须有数据表和判断句）",
                "  4. 竞争格局（份额趋势 + 壁垒量化判断）",
                "  5. 增长驱动（量/价/结构拆解 —— 核心差异章节）",
                "  6. 治理与ESG（ROIC/WACC + 资本配置判断）",
                "  7. 估值分析（三情景目标价 + 敏感性矩阵 + 假设对标）",
                "  8. 证伪条件（4+量化触发条件）",
                "  9. 催化剂日历（3-6-12月事件 + 概率 + 影响幅度）",
                "- 每章至少一个'我们认为/我们判断'的判断句",
            ]
        elif self.sac_id == "sac_unlisted_company":
            lines += [
                "",
                "### 结构约束（非上市企业分析专用）",
                "- 报告必须按以下9个维度独立成章：",
                "  1. 企业概览（业务结构 + 市场定位判断）",
                "  2. 商业模式（收入/利润来源 + 单位经济判断）",
                "  3. 核心指标（用户/ARPU/变现率 + 趋势判断）",
                "  4. 资本结构（融资历史 + 估值变化）",
                "  5. 竞争壁垒（护城河类型 + 可持续性判断）",
                "  6. 估值分析（可比 + SOTP + 单用户估值，含敏感性矩阵）",
                "  7. 退出路径（IPO/M&A + 时间线判断）",
                "  8. 核心分歧（市场定价分歧地图）",
                "  9. 证伪条件（3+量化触发条件）",
                "- 每章至少一个'我们认为/我们判断'的判断句",
            ]

        # 规则部分（保持现有）
        lines += [
            "",
            "### 规则 (违规 = 打回)",
            "- 禁止 AI 披露 (AI generated/assisted/by system). 禁止 AIGC 元数据。",
            "- 禁止 AI 免责声明：不出现 '仅供参考''不构成投资建议''市场有风险''内容由AI生成'",
            "- 禁止内部方法论标签 (SAC/MECE/dimension/paradigm/protocol/Writing Scaffold/研究协议/11维/8阶)",
            "- 禁止自我评价 like '本报告已达到XX标准'",
            "- 禁止第一人称 '我' 或 '本系统'。使用 '我们' 或 '本报告'。",
            "- 数字：自然标注来源；禁止编造来源",
            "- 禁止模糊量化词 (很多/大量/显著—use exact numbers)",
            "- 数据来源统一格式：在数字后用（来源：XX），不在末尾列'参考文献'或'参考资料'",
            "- 核心锐判：方向 + 时间 + 变量 + 分歧点（可以是 Bold Call、分歧定位或增量信息，三选一即可）",
            "- 每章至少一个判断句：每章必须包含至少一句'我们认为/我们判断/核心在于'类主观判断句——不能只有事实陈述没有判断",
            "- 反方：每个核心判断必须有明确反方",
            "- 政策：完整 4 跳传导链",
            "- 数据缺口：标记待补充，不编造",
            "- 重要：写正文前，先简要说明这个行业/公司的基本情况（前三家玩家是谁、业务怎么分、关键变量是什么）。然后再深入分析。",
            "- CRITICAL: Every chapter must contain ONE judgment that would surprise consensus. '行业在增长' 不是判断. '市场认为X稳态/但我们认为Y颠覆在即' 是判断.",
            "- 不确定性的表述要精确：不说'有风险'，说'风险集中在两个变量上：X的产能爬坡速度和新品认证周期（120-150天）'",
            "- 引用历史时带具体案例背景：不说'历史上类似情况'，说'2021年宁德时代也面临过类似的产能瓶颈，当时的解决方案是……'",
            "- 每个数值后面自然跟一句可信度判断，例如'这个数据来自行业协会的季度报告，但样本覆盖约70%的规上企业，有低估可能'",
            "",
            "### 写作风格参考样本",
            "以下段落展示'十年以上分析师'的写作节奏和语感。这不是模板，是语感参考——注意它怎么处理不确定性、怎么引用经验、怎么连接证据与判断：",
            "",
            "『关于市场担心的竞争格局恶化问题，我们的看法有所不同。当前行业的CR5从三年前的72%下降到68%，这个趋势让不少投资者感到不安——但如果拆开来看，份额流失主要集中在低端市场（单价5000元以下），高端市场的集中度反而在这三年里从81%提升到了85%。高端和低端正在变成两个不同的战场。我们在XX公司的渠道调研中观察到，低端客户的价格敏感度在上升、品牌忠诚度在下降——这意味着低端市场份额的变化更多反映的是需求结构的调整，而非竞争格局的恶化。这个判断最大的不确定性在于供应链的转移速度：如果东南亚产能爬坡比预期快两个季度，低端市场可能会比我们基准情形再多跌3-5%的份额。这个风险我们会在估值中给一个额外折价。』",
            "",
            "关键观察点：",
            "1. 不确定性精确化了（'如果……快两个季度'而非'可能更快'）",
            "2. 有具体经验引用（'我们在XX公司的渠道调研中观察到'）",
            "3. 数据说完了不立刻跳结论（'这个趋势'到'但如果拆开'之间的转折是自然的）",
            "4. 风险不是丢到风险章节，是嵌在判断里面一起出来的",
            "5. 每段只有一个核心判断，不塞三四个论据",
            "",
            "### 辩论协议（强制——先写看空立场，再写看多立场）",
            "",
            "**步骤一：独立看空立场**",
            "在写任何正文之前，先以最坚定的空头角色写一个 300 字以上的 bear case。",
            "规则：",
            "  - 假设你极度看空这个标的，写出完整的、自洽的看空逻辑链——要有事实基础，不要稻草人",
            "  - 包括：为什么市场过度乐观、哪个关键变量最可能不及预期、什么事件会触发下跌",
            "  - 给出至少两个可量化的证伪条件（'如果X达到Y，则看多逻辑不成立'）",
            "  - 这个 bear case 不是用来证明你错了——是用来让你知道自己错在哪里",
            "",
            "**步骤二：独立看多立场**",
            "然后以最坚定的多头角色写 300 字以上的 bull case。",
            "规则：",
            "  - 同样必须是完整的、自洽的逻辑链",
            "  - 直接回应 bear case 中的最强论点（'空头认为X会导致Y，我们的分析是X导致Z而非Y，理由如下'）",
            "",
            "**步骤三：合并为报告核心分歧**",
            "将 bear case 和 bull case 中的核心分歧点提取出来，生成：",
            "  - 分歧地图：列出 3-5 个关键分歧变量，标注对方的立场和自己的立场",
            "  - 每个分歧变量给出双方最强的一条证据",
            "  - 不确定性的来源就在分歧点上——不是其他",
            "",
            "这不是可选的。 没有经过 bear/bull 辩论就直接写正面的报告将被退回。",
        ]

        # 注入投行方法论（来自137+84份培训材料）
        injected = inject_into_protocol(
            "\n".join(lines),
            sector=self.title,
            depth=self.output_depth,
        )
        return injected


class ResearchOrchestrator:
    """Orchestrates research protocol generation from SAC entries."""

    def __init__(self):
        self._generator = SACToResearchProtocol()

    def prepare(self, sac, brief_id="", core_question="", output_depth="deep"):
        return self._generator.generate(sac, brief_id=brief_id, core_question=core_question, output_depth=output_depth)


class SACToResearchProtocol:
    SERENITY_9 = [
        ("s01", "Step1/9: demand translation from topic"),
        ("s02", "Step2/9: 8-layer value chain, 3+ levels"),
        ("s03", "Step3/9: validate scarcity layer"),
        ("s04", "Step4/9: 核心锐判 — Bold Call、核心分歧或增量信息，三选一均可"),
        ("s05", "Step5/9: polarity map, 3+ per side"),
        ("s06", "Step6/9: counter-case construction"),
        ("s07", "Step7/9: evidence audit + AI contamination check"),
        ("s08", "Step8/9: falsification, 3+ conditions"),
        ("s09", "Step9/9: catalyst calendar"),
    ]

    IND_DIMS = [
        (
            "sharp_judgment",
            "核心锐判：最有价值的一个判断——可以是 Bold Call（逆共识）、核心分歧定位（市场在吵什么）、或增量信息（市场还没消化的新数据），三选一",
            3,
            True,
        ),
        ("polarity", "核心分歧与极性：支持/反对力量。反方观点明确。", 2, True),
        ("falsify", "Falsification: 3+ quantified triggers.", 2, True),
        ("boundary", "Industry boundary: L1/L2/L3?", 1, False),
        ("lifecycle", "Lifecycle: stage? cycle? consensus vs you?", 1, True),
        ("policy", "Policy: full 4-link chain (policy->industry->profit->stocks).", 3, True),
        ("market", "Market size: 2+ methods. penetration? ceiling?", 2, False),
        ("s_d", "Supply-Demand: structure? constraints? balance?", 2, False),
        ("profit", "Profit pool: distribution. margins. pricing.", 3, True),
        ("compete", "Competitive: tiers. CR3/CR5. moat. barriers.", 2, True),
        ("tech", "Technology: current? next? skip if mature.", 2, False),
        ("capital", "Capital market: valuation. catalyst calendar.", 2, True),
    ]

    LST_DIMS = [
        ("disagree", "Disagreement: consensus vs our view?", 2, True),
        ("model", "Business model: profit drivers? moat?", 2, False),
        ("financial", "Financial: revenue/margin/ROE bridge.", 3, False),
        ("compete", "Competitive: share trend. moat quant.", 2, True),
        ("growth", "Growth: vol/price/mix. sustainability.", 2, False),
        ("gov", "Governance: ROIC/WACC. related-party. ESG.", 1, True),
        ("value", "Valuation: expectations priced in?", 2, True),
        ("falsify", "Falsification: quantified triggers.", 2, True),
        ("catalyst", "Catalysts: 3-6-12m events.", 1, False),
    ]

    UNL_DIMS = [
        ("data", "Data: sources? verified vs estimates?", 1, False),
        ("overview", "Overview: business? position? stage?", 1, False),
        ("equity", "Capital: ownership? funding?", 2, False),
        ("kpi", "KPI tree: unit economics?", 2, False),
        ("moat", "Competitive: advantage type?", 2, True),
        ("value", "Valuation: comparable+transactions+DCF.", 2, True),
        ("exit", "Exit: IPO/M&A/secondary.", 2, False),
        ("dd", "DD: items by materiality.", 1, False),
        ("falsify", "Falsification: 3+ triggers.", 1, True),
        ("disagree", "Core disagreement: consensus vs our view?", 2, True),  # 新增
        ("catalyst", "Catalysts: 3-6-12m events.", 1, False),  # 新增
    ]

    def generate(self, sac, brief_id="", core_question="", output_depth="deep"):
        proto = ResearchProtocol(
            brief_id=brief_id,
            report_type=sac.applies_to[0] if sac.applies_to else "",
            output_depth=output_depth,
            sac_id=sac.sac_id,
            title=sac.name,
            core_question=core_question or self._guess(sac),
        )

        if sac.sac_id == "sac_industry_deep":
            dims = self.IND_DIMS
            for s in self.SERENITY_9:
                proto.tasks.append(ResearchTask(task_id=s[0], dimension_id="serenity", question=s[1], evidence_min=1))
        elif sac.sac_id == "sac_listed_company":
            dims = self.LST_DIMS
        elif sac.sac_id == "sac_unlisted_company":
            dims = self.UNL_DIMS
        else:
            dims = self.LST_DIMS

        for d in dims:
            proto.tasks.append(
                ResearchTask(
                    task_id=f"dim_{d[0]}", dimension_id=d[0], question=d[1], evidence_min=d[2], counter_required=d[3]
                )
            )
        return proto

    @staticmethod
    def _guess(sac):
        if "unlisted" in sac.sac_id:
            return "Value and risk of this unlisted company?"
        if "earnings" in sac.sac_id:
            return "Incremental info from this earnings?"
        return "Most important structural change - where is excess return?"
