"""
报告规划器（Report Planner）— R28 全量修复方向C：先规划后写

**问题**：管线"先写后检"——写作阶段不知道要写什么，Gate 校验阶段才知道缺什么，
导致 enrich 补丁循环、Gate 打地鼠、指标导向写作（为过 Gate 而补）。

**方案**：write_sections 前生成"写作规划"：
  1. 必答问题清单（按报告类型 + SAC 维度生成）
  2. 数据支撑清单（每个必答问题需要哪些数据，缺的提前标缺口）
  3. 结论自洽约束（评级-目标价空间-估值锚联动，写作时即遵守，不靠 Gate 事后拦）

规划注入写作 prompt 后，LLM 一次写对，减少往返。

本模块只做规划组织，不产生正文（FP2）。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("2hao.report_planner")

_ROOT = Path(__file__).resolve().parent.parent

# ── 各报告类型必答问题（核心判断链）──
PLAN_BY_TYPE = {
    "listed_company": [
        {"q": "公司是干什么的？主业/商业模式/行业归属", "data": ["company_intro", "business_model"], "critical": True},
        {
            "q": "公司卡在供应链什么位置？竞争格局如何？",
            "data": ["industry_chain", "competitive", "bottleneck"],
            "critical": True,
        },
        {
            "q": "财务质量如何？收入确认/毛利/现金流/商誉风险",
            "data": ["fig_revenue_trend", "fig_margin", "financials"],
            "critical": True,
        },
        {"q": "合理估值是多少？PE/DCF/可比三法一致吗？", "data": ["valuation", "dcf", "peer"], "critical": True},
        {
            "q": "给出明确评级+目标价。目标价隐含空间与评级匹配吗？",
            "data": [],
            "critical": True,
            "self_consistent": "rating_space",
        },
        {"q": "未来催化是什么？什么时间点验证/证伪判断？", "data": ["catalyst", "falsification"], "critical": True},
        {"q": "最大风险是什么？分层评估", "data": ["risk_layering"], "critical": False},
    ],
    "industry_deep": [
        {
            "q": "行业空间多大？增速几何？生命周期阶段？",
            "data": ["market_size", "life_cycle", "penetration"],
            "critical": True,
        },
        {
            "q": "产业链结构？哪个环节是瓶颈/利润最厚？",
            "data": ["industry_chain", "profit_pool", "bottleneck"],
            "critical": True,
        },
        {"q": "竞争格局？集中度？龙头壁垒？", "data": ["competitive", "global_competition"], "critical": True},
        {"q": "供需关系？政策催化？", "data": ["supply_demand", "policy"], "critical": True},
        {"q": "核心结论：最值得投资的环节/公司？", "data": [], "critical": True},
        {"q": "未来验证点：什么事件/时间验证行业判断？", "data": ["catalyst"], "critical": False},
    ],
    "unlisted_company": [
        {
            "q": "公司是干什么的？产品/技术/团队",
            "data": ["company_intro", "founder_team", "product_tech"],
            "critical": True,
        },
        {"q": "商业化进展？营收/客户/里程碑？", "data": ["business_kpi", "market_traction"], "critical": True},
        {"q": "稀缺性/护城河？卡位多强？", "data": ["competitive_moat", "scarcity"], "critical": True},
        {
            "q": "当前估值支撑多少营收/里程碑？（反向定价）",
            "data": ["valuation_estimate", "reverse_valuation"],
            "critical": True,
        },
        {"q": "退出路径？IPO/并购/下一轮融资？", "data": ["exit_analysis", "milestone"], "critical": True},
        {"q": "最大风险？创始团队/资金链/竞品？", "data": ["founder_risk", "risk"], "critical": False},
    ],
    # R83（2026-08-07）：决策备忘录——写给委托方（董事长/高管）的决策情报，非投资评级
    # 区分：禁评级/目标价（面向二级市场），强制执行摘要/决策建议/最坏损失/路线图
    # 全部标记 client=True → 进入 client_questions，被 Gate _check_client_questions_coverage 校验
    "decision_memo": [
        {"q": "执行摘要：一句话结论——进/不进/怎么进？", "data": [], "critical": True, "client": True},
        {
            "q": "行业真相：委托方不知道的增量信息是什么？市场规模/竞争/卡脖子/政策节奏",
            "data": ["market_size", "competitive", "industry_chain", "policy"],
            "critical": True,
            "client": True,
        },
        {
            "q": "我方禀赋匹配度：现有能力能否承接？（技术栈/生产主体/渠道真伪）",
            "data": ["company_intro", "capability_gap", "production_subject"],
            "critical": True,
            "client": True,
        },
        {
            "q": "怎么进：生产主体三选（自制/外协/子公司承接）？转移定价合规？",
            "data": ["production_subject", "transfer_pricing"],
            "critical": True,
            "client": True,
        },
        {
            "q": "财务测算：收入三浪/投入/敏感性？",
            "data": ["financial_projection", "sensitivity"],
            "critical": True,
            "client": True,
        },
        {
            "q": "最坏损失上限：投入沉没后的最大损失多少？",
            "data": ["worst_case_loss"],
            "critical": True,
            "client": True,
        },
        {"q": "执行路线图：分季度里程碑与验收标准？", "data": ["roadmap"], "critical": True, "client": True},
        {
            "q": "延伸产业：能否进入相邻品类/上游卡位？",
            "data": ["adjacent_expansion", "bottleneck"],
            "critical": False,
            "client": True,
        },
    ],
}

# R83（2026-08-07）：委托方问题清单注入——决策类报告必答问题
# 油位 v0.89 事故：管线产出"二级市场投资评级报告"，委托方要"董事长决策备忘录"。
# 根因：SAC 维度全行业分析向，缺"报告读者要做什么决策"维度。
# 修复：调度时注入"读者 + 决策点 + 必答问题"，作为 section_writer 顶层约束。
# decision_memo 报告类型走此清单；其他类型可选用 --client-questions 注入。

# ── 结论自洽约束 ──
SELF_CONSISTENT_RULES = {
    "rating_space": (
        "评级必须与目标价隐含空间匹配：增持/买入要求目标价较现价≥10%上行空间；"
        "若<10%应给中性/持有。正文必须让评级、目标价、现价三者自洽。"
    ),
    "valuation_anchor": (
        "多估值锚（PE法/DCF法/可比法）必须一致：若差异>20%，必须明确交代最终取值的"
        "加权逻辑（如'PE法40-48元，DCF法52元，取48元因...'）。禁止并列矛盾值不解释。"
    ),
    "unit_caliber": (
        "所有数值必须带单位/时期：毛利率用百分比、营收用亿元、北向资金用万元。"
        "单季值必须标注'Q1单季'，不得与全年值直接混淆。"
    ),
}

# R75（2026-08-05 Phase 3）：InfoDesk 层——读者画像 + 行动问题
# 油位v6审计发现报告"不知道读者想干什么"，全是教科书式行业罗列。
# 对标高盛GS-SUSTAIN：每份报告开场说明"这篇报告回答读者的3个关键问题"。
READER_PROFILES = {
    "industry_deep": {
        "profile": "机构投资者（基金经理/研究员），已有行业基础，需要判断：买不买、买谁、什么时候买、仓位多少？",
        "action_questions": [
            "如果你看好这个赛道，现在应该建仓还是等回调？",
            "这个行业中，买A还是买B？为什么不是C？（具体标的替代关系）",
            "最大风险是什么？什么条件下必须止损？（非'行业下行'的笼统说法）",
        ],
    },
    "listed_company": {
        "profile": "持仓或拟持仓该股的基金经理/研究员，需要决定加仓/减仓/清仓",
        "action_questions": [
            "当前股价是否已充分反映预期？预期差在哪？",
            "12个月目标价隐含上行空间x%——这个空间对组合的边际贡献是否值得交易？",
            "什么事件/数据会让我改变评级？（具体到可观察指标+时间窗口）",
        ],
    },
    "unlisted_company": {
        "profile": "VC/PE投资经理，需要决定是否参与本轮融资、估值是否合理、退出路径是否清晰",
        "action_questions": [
            "这个估值是否合理？三个独立口径是否指向同一区间？",
            "退出路径：IPO/并购/下一轮——哪个最可行？时间窗口？",
            "尽调中最重要的3个待核实事项是什么？（按重要性排列）",
        ],
    },
    "decision_memo": {
        "profile": "委托方决策者（董事长/CEO/事业部负责人），对本公司基本面已熟知，需要的是增量决策信息",
        "action_questions": [
            "这个方向值不值得进？（明确的进/不进/条件性进建议）",
            "进去了能不能快速放量？放量的驱动和验证点是什么？",
            "最坏情况下损失多少？（用金额锚定，而非模糊定性）",
            "第一步做什么？什么时间做什么？（可执行的路线图）",
        ],
    },
}


def build_report_plan(report_type: str = "listed_company", client_questions: list | None = None) -> dict:
    """生成写作规划。R75: 新增 reader_profile + action_questions。
    R83: 新增 client_questions 注入（委托方必答问题，decision_memo 核心）。"""
    questions = PLAN_BY_TYPE.get(report_type, PLAN_BY_TYPE["listed_company"])
    profile = READER_PROFILES.get(report_type, READER_PROFILES["listed_company"])
    # R83：委托方问题注入——合并进 questions 顶层（critical=True），
    # 强制 section_writer 逐条回答，Gate 用同一清单校验覆盖率
    # R84：must_contain（必须出现的实体）+ forbidden_swap（禁止替换成的场景）
    client_questions = client_questions or []
    merged = list(questions)
    global_must_contain = []
    global_forbidden = []
    for i, cq in enumerate(client_questions):
        if isinstance(cq, str):
            cq = {"q": cq}
        if not isinstance(cq, dict) or not cq.get("q"):
            continue
        merged.append(
            {
                "q": f"【委托方必答】{cq['q']}",
                "data": cq.get("data", []),
                "critical": True,
                "client": True,
                "must_contain": cq.get("must_contain", []),
                "forbidden_swap": cq.get("forbidden_swap", []),
            }
        )
        global_must_contain.extend(cq.get("must_contain", []))
        global_forbidden.extend(cq.get("forbidden_swap", []))
    # 去重
    global_must_contain = list(dict.fromkeys(global_must_contain))
    global_forbidden = list(dict.fromkeys(global_forbidden))
    return {
        "report_type": report_type,
        "questions": merged,
        "must_answer": [q["q"] for q in merged if q.get("critical")],
        "client_questions": [q["q"] for q in merged if q.get("client")],
        # R84：委托方实体锚定——must_contain 必须出现在正文，forbidden_swap 禁止出现
        "must_contain": global_must_contain,
        "forbidden_swap": global_forbidden,
        "self_consistent": list(SELF_CONSISTENT_RULES.values()),
        "total_critical": sum(1 for q in merged if q.get("critical")),
        # R75 InfoDesk
        "reader_profile": profile["profile"],
        "action_questions": profile["action_questions"],
    }


def serialize_plan(plan: dict, max_chars: int = 1500) -> str:
    """序列化写作规划，注入 prompt。R75: 新增读者画像 + 行动问题。"""
    if not plan:
        return ""
    lines = [
        "=== 写作规划（本部分必须回答的问题 + 结论自洽约束）===",
        "以下问题必须在本报告正文中明确回答（数据不足时标'数据缺口'，不得跳过）：",
    ]
    for i, q in enumerate(plan.get("questions", [])):
        crit = "【必答】" if q.get("critical") else "【可选】"
        lines.append(f"{i + 1}. {crit} {q['q']}")
    lines.append("")
    lines.append("结论自洽约束（必须同时满足，否则报告不合格）：")
    for r in plan.get("self_consistent", []):
        lines.append(f"  - {r}")
    # R75 InfoDesk
    rp = plan.get("reader_profile", "")
    if rp:
        lines.append(f"\n读者画像: {rp}")
    aq = plan.get("action_questions", [])
    if aq:
        lines.append("读者关心的关键行动问题（必须在报告中给出明确回答）：")
        for i, q in enumerate(aq):
            lines.append(f"  {i + 1}. {q}")
    # R83：委托方必答问题高亮（decision_memo 顶层约束）
    cq = plan.get("client_questions", [])
    if cq:
        lines.append("\n【委托方必答问题——本报告的核心，必须逐条给出明确结论，禁止回避】")
        for i, q in enumerate(cq):
            lines.append(f"  [{i + 1}] {q}")
    # R84：委托方实体锚定——防止匿名委托方/换行业/换场景
    mc = plan.get("must_contain", [])
    if mc:
        lines.append("\n【必须出现的实体/场景（委托方身份锚定，正文必须包含这些）】")
        lines.append(f"  {', '.join(mc)}")
    fb = plan.get("forbidden_swap", [])
    if fb:
        lines.append("【禁止替换成的场景/叙事（若正文大量出现这些，说明写错了行业）】")
        lines.append(f"  {', '.join(fb)}")
    return "\n".join(lines)[:max_chars]


if __name__ == "__main__":
    for rt in ["listed_company", "industry_deep", "unlisted_company"]:
        print(f"\n=== {rt} ===")
        print(serialize_plan(build_report_plan(rt), max_chars=600))
