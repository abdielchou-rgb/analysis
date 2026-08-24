# -*- coding: utf-8 -*-
"""context_compiler.py — 上下文模板程序化（P3，轻量 DSPy 式，2026-08-07）

把"上下文工程模板"从手写升级为参数化程序化生成（DSPy 思想的轻量落地，零重依赖）。

核心：意图/数据/约束/示例 四段分离 → 按报告类型/必答问题程序化组装 → 输出上下文。
与 workbench_executor 的 step3 互补：workbench 用模板，这里把模板参数化可复用。

用法：
  from core.context_compiler import compile_context
  ctx = compile_context(asset="柯力传感", report_type="decision_memo",
                        requirement="评估市场规模/投入产出比",
                        data={...}, compute_summaries=[...])
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("2hao.context_compiler")

# 2026-08-08：框架适配清单（防"该用未用" + 防"框架错配"）
# 按行业驱动类型注入适用框架——政策/内需驱动行业不注入宏观DDM（估值框架错配）
# industry_hint 关键词 → (适用框架, 不适用的框架说明)
FRAMEWORK_FIT = {
    # 政策/合规驱动（油位/环保/安监类）
    "policy_driven": {
        "must": ["产业生命周期", "利润池/卡位", "商业模式分类", "政策传导", "竞争格局",
                 "国产替代传导", "技术路线"],
        "misfit_note": "宏观 DDM 三要素（盈利/流动性/风险偏好）为股票估值框架，"
                       "对政策/内需驱动行业适配度低——除非报告明确涉及估值，否则不注入",
    },
    # 周期/流动性驱动（宏观敏感类）
    "macro_driven": {
        "must": ["宏观传导", "产业生命周期", "竞争格局", "信号链", "供需平衡"],
        "misfit_note": "",
    },
    # 技术驱动（半导体/创新类）
    "tech_driven": {
        "must": ["中美竞争", "技术路线", "国产替代", "卡点评分", "产业生命周期", "信号链"],
        "misfit_note": "",
    },
}

# 行业关键词 → 驱动类型
_DRIVER_HINTS = {
    "油位": "policy_driven", "液位": "policy_driven", "传感器": "policy_driven",
    "环保": "policy_driven", "安监": "policy_driven", "危化品": "policy_driven",
    "加油站": "policy_driven", "半导体": "tech_driven", "芯片": "tech_driven",
    "ai": "tech_driven", "人工智能": "tech_driven", "新能源": "macro_driven",
    "地产": "macro_driven", "基建": "macro_driven", "消费": "macro_driven",
}


def framework_fit_prompt(industry_hint: str = "") -> str:
    """生成框架适配检查清单（注入上下文，指导写手覆盖适用框架）。

    返回空串若无匹配。
    """
    if not industry_hint:
        return ""
    driver = None
    for kw, d in _DRIVER_HINTS.items():
        if kw in industry_hint.lower():
            driver = d
            break
    if not driver:
        return ""
    fit = FRAMEWORK_FIT.get(driver, {})
    must = fit.get("must", [])
    misfit = fit.get("misfit_note", "")
    lines = ["=== 行业分析框架适配清单（必须覆盖）===",
             f"行业驱动类型: {driver}"]
    for fw in must:
        lines.append(f"- 必须覆盖: {fw}")
    if misfit:
        lines.append(f"- 不适用（勿硬塞）: {misfit}")
    lines.append("=== 框架清单结束 ===")
    return "\n".join(lines)


# 报告类型 → 段配置（长度/重点/禁忌）
SEGMENT_CONFIG = {
    "decision_memo": {
        "title_note": "决策备忘录",
        "focus_blocks": ["intent", "data", "compute", "guardrail"],
        "guardrails": ["禁止投资评级/目标价/EPS", "结论先行", "必答问题必须逐条回答"],
        "example_hint": "执行摘要样例：建议进入（条件性），卡位评分X.X/5，三年投入1.5-2亿，最坏损失≈2亿（0.6倍归母净利）",
    },
    "listed_company": {
        "title_note": "深度研究报告",
        "focus_blocks": ["intent", "data", "compute", "guardrail"],
        "guardrails": ["禁止编造数据", "每个判断带反方论证"],
        "example_hint": "执行摘要样例：评级增持，目标价51.6元（+18%），核心逻辑是...",
    },
    "unlisted_company": {
        "title_note": "非上市尽调",
        "focus_blocks": ["intent", "data", "compute", "guardrail"],
        "guardrails": ["估值用区间不用点位", "退出路径必须明确"],
        "example_hint": "投资价值区间样例：1.5-4亿，三口径交叉验证，退出以并购为主",
    },
    "industry_deep": {
        "title_note": "行业深度报告",
        "focus_blocks": ["intent", "data", "guardrail"],
        "guardrails": ["行业增速预测要明确区间", "受益标的需要点名"],
        "example_hint": "行业判断样例：未来3年CAGR 12-15%，超配，受益标的为...",
    },
}


@dataclass
class ContextTemplate:
    """参数化上下文模板。"""
    asset: str = ""
    report_type: str = "decision_memo"
    requirement: str = ""
    client: str = ""
    decision_point: str = ""
    must_answer_questions: list = field(default_factory=list)
    data: dict = field(default_factory=dict)
    compute_summaries: list = field(default_factory=list)
    facts_prompt: str = ""
    guardrails: list = field(default_factory=list)
    example_hint: str = ""
    industry_hint: str = ""  # 2026-08-08：行业关键词（框架适配检查用）

    def compile(self) -> str:
        """程序化组装上下文。"""
        cfg = SEGMENT_CONFIG.get(self.report_type, SEGMENT_CONFIG["decision_memo"])
        blocks = []

        # ① 意图块
        blocks.append(f"# 写作任务：{self.asset} {cfg['title_note']}")
        if self.client:
            blocks.append(f"委托方: {self.client}")
        if self.decision_point:
            blocks.append(f"决策点: {self.decision_point}")
        if self.must_answer_questions:
            blocks.append("\n## 必答问题（必须全部回答，报告围绕它们组织）")
            for i, q in enumerate(self.must_answer_questions, 1):
                blocks.append(f"{i}. {q}")

        # ② 数据块（分级）
        if self.data:
            blocks.append("\n## 可用数据（verified可直接引用 / corrected已修正 / unverified须标(E)）")
            blocks.append(json.dumps(self.data, ensure_ascii=False, indent=1)[:3000])

        # 事实库块
        if self.facts_prompt:
            blocks.append(f"\n{self.facts_prompt}")

        # ③ 计算块
        if self.compute_summaries:
            blocks.append("\n## 计算模块产出（代码已算好，直接引用，禁止重算）")
            blocks.append("\n".join(self.compute_summaries))

        # ④ 约束块
        g = self.guardrails or cfg["guardrails"]
        blocks.append("\n## 写作约束")
        for x in g:
            blocks.append(f"· {x}")
        blocks.append("· 每个数字带来源和标注 (A)/(E)/(F)/(B)")
        blocks.append("· 数据不足写'待尽调核实'，禁止编造")

        # 示例块
        if self.example_hint or cfg.get("example_hint"):
            blocks.append(f"\n## 写法参考\n{self.example_hint or cfg['example_hint']}")

        blocks.append("\n## 要求\n直接写正文（Markdown），先执行摘要，再分章节回答每个必答问题。")

        # 2026-08-08：作者姿态硬约束（元评论语言根治）——
        # 报告作者陈述事实，不教读者怎么做、不解释工作过程、不自我指涉
        blocks.append(
            "\n## 作者姿态（最高优先级）\n"
            "你是报告作者，不是写作助手。正文必须：\n"
            "· 只陈述事实、数据、分析、结论——不出现'建议验证/待核实/升级为实际值/值得关注/需要说明'等指导语\n"
            "· 不教读者'如何验证/如何尽调'——验证方法信息放附录，不进正文\n"
            "· 不解释'本报告如何得出'——直接给结果与依据\n"
            "· 不自指'见某节/本报告'——用内容自然衔接\n"
            "· 不出现'可考虑/需评估/建议对'等助手式措辞——直接给判断"
        )

        # 2026-08-08：框架适配检查（防"该用未用" + 防"框架错配"）
        if self.industry_hint:
            _fit = framework_fit_prompt(self.industry_hint)
            if _fit:
                blocks.append(f"\n{_fit}")
        return "\n".join(blocks)


def compile_context(asset: str, report_type: str = "decision_memo",
                    requirement: str = "", data: Optional[dict] = None,
                    compute_summaries: Optional[list] = None,
                    facts_prompt: str = "", industry_hint: str = "") -> str:
    """便捷入口：参数化生成上下文 prompt。

    自动从 requirement 派生意图（intent_parser）+ 组装模板。
    industry_hint 触发框架适配检查（按行业注入适用框架，防错配）。
    """
    from core.intent_parser import IntentParser
    plan = IntentParser().parse(asset, report_type, requirement)
    tpl = ContextTemplate(
        asset=asset, report_type=report_type, requirement=requirement,
        client=plan["client"], decision_point=plan["decision_point"],
        must_answer_questions=plan["must_answer_questions"],
        data=data or {}, compute_summaries=compute_summaries or [],
        facts_prompt=facts_prompt, industry_hint=industry_hint,
    )
    return tpl.compile()
