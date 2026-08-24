# -*- coding: utf-8 -*-
"""intent_parser.py — 意图解析层（FP0 落地，2026-08-07）

从"写满 SAC 模板"升级为"回答委托方必答问题"。

核心：委托方问题清单确认 → 必答问题 → 报告结构。
这是 FP0（意图第一公民）的工程落地——每个任务启动先确认：
  谁读（委托方身份） / 决策点（要做什么决定） / 必答问题（必须回答什么）

用法：
  ip = IntentParser()
  plan = ip.parse(asset="柯力传感", report_type="decision_memo",
                  requirement="久通要把油位传感器业务给柯力生产，评估市场规模/投入产出比/战略卡位/衍生价值")
  # plan: {client, decision_point, must_answer_questions, structure, guardrails}

  ip.validate_report(plan, report_text)  # 意图符合性：必答问题是否被回答
"""
from __future__ import annotations
import os, re, json, logging
from pathlib import Path

logger = logging.getLogger("2hao.intent_parser")

_ROOT = Path(__file__).resolve().parent.parent


class IntentParser:
    """委托方意图 → 必答问题 → 报告结构。"""

    # 报告类型 → 默认委托方 + 决策点 + 必答问题模板
    DEFAULT_INTENT = {
        "decision_memo": {
            "client": "委托方（董事长/CEO）",
            "decision_point": "进/不进/条件性进",
            "must_answer": [
                "市场规模多大？空间与节奏？",
                "投入产出比如何？多久回本？",
                "战略卡位是否关键？有无替代路径？",
                "最坏损失多少？能否承受？",
                "衍生价值/期权价值有多大？",
            ],
        },
        "listed_company": {
            "client": "二级市场投资者",
            "decision_point": "买入/持有/卖出",
            "must_answer": [
                "公司核心价值驱动是什么？",
                "当前估值是否合理？",
                "关键风险与催化剂是什么？",
            ],
        },
        "unlisted_company": {
            "client": "投资人/尽调方",
            "decision_point": "投/不投/估值区间",
            "must_answer": [
                "公司价值与成长性如何？",
                "退出路径与概率？",
                "核心风险（股权/经营/市场）？",
            ],
        },
        "industry_deep": {
            "client": "机构投资人/行业研究者",
            "decision_point": "行业景气方向与配置",
            "must_answer": [
                "行业规模与增速？",
                "竞争格局与利润池在哪？",
                "关键变量与传导逻辑？",
                "受益标的与风险？",
            ],
        },
    }

    # 需求关键词 → 追加必答问题（行业/场景定制）
    REQUIREMENT_QUESTIONS = {
        "投入产出": "投入产出比具体测算？盈亏平衡点？",
        "代工": "代工成本/良率爬坡/转移定价？自产vs外包？",
        "并购": "并购协同/整合风险/估值合理性？",
        "卡位": "战略卡位的关键性？不做的机会成本？",
        "衍生": "衍生价值/期权价值/相邻品类机会？",
        "渠道": "渠道真实性与可持续性？",
        "竞争": "竞争格局/壁垒/替代威胁？",
    }

    def parse(self, asset: str, report_type: str = "decision_memo",
              requirement: str = "", client: str = "") -> dict:
        """解析委托方意图 → 报告结构计划。

        requirement: 用户口述需求（自由文本），驱动必答问题定制。
        """
        # 基础意图（按报告类型默认）
        base = self.DEFAULT_INTENT.get(report_type, self.DEFAULT_INTENT["decision_memo"])
        must_answer = list(base.get("must_answer", []))
        if client:
            base["client"] = client

        # 需求定制：追加必答问题
        req_questions = []
        if requirement:
            for kw, q in self.REQUIREMENT_QUESTIONS.items():
                if kw in requirement:
                    req_questions.append(q)

        # 合并必答问题（基础 + 需求定制，去重）
        seen = set(must_answer)
        for q in req_questions:
            if q not in seen:
                must_answer.append(q)
                seen.add(q)

        # 生成报告结构（必答问题 → 章节）
        structure = self._build_structure(must_answer, report_type)

        return {
            "asset": asset,
            "report_type": report_type,
            "client": base["client"],
            "decision_point": base["decision_point"],
            "requirement": requirement,
            "must_answer_questions": must_answer,
            "structure": structure,
            "guardrails": {
                "禁止": self._guardrails(report_type),
                "强制": ["执行摘要必须直接回答必答问题，结论先行"],
            },
        }

    def validate_report(self, plan: dict, report_text: str) -> dict:
        """意图符合性检查：必答问题是否被报告回答。

        用关键词命中近似（报告出现问题关键词的语义变体）。返回每问题命中/未命中。
        """
        results = []
        for q in plan.get("must_answer_questions", []):
            keywords = self._extract_keywords(q)
            hit = any(kw in report_text for kw in keywords if len(kw) >= 2)
            results.append({
                "question": q,
                "keywords": keywords,
                "answered": hit,
            })
        answered = sum(1 for r in results if r["answered"])
        total = len(results)
        return {
            "total": total,
            "answered": answered,
            "coverage": round(answered / total, 2) if total else 0,
            "results": results,
            "passed": (answered / total) >= 0.6 if total else True,  # ≥60% 算通过
        }

    def build_prompt(self, plan: dict) -> str:
        """生成注入写作 prompt 的意图约束块（FP0 强制）。"""
        lines = ["=== 委托方意图（FP0 最高优先级，必须回答）===",
                 f"委托方: {plan['client']}",
                 f"决策点: {plan['decision_point']}",
                 "必答问题（必须全部在报告中回答）:"]
        for i, q in enumerate(plan.get("must_answer_questions", []), 1):
            lines.append(f"  {i}. {q}")
        lines.append("报告结构必须围绕必答问题组织，禁止只填模板不回答问题。")
        lines.append("=== 意图约束结束 ===")
        return "\n".join(lines)

    # ── 内部 ─────────────────────────────────────────

    def _build_structure(self, questions: list, report_type: str) -> list:
        """必答问题 → 章节结构（决策备忘录直接映射）。"""
        sections = [{"title": "执行摘要", "answers": questions[:1]}]
        if report_type == "decision_memo":
            sections.append({"title": "决策建议与依据", "answers": questions})
            sections.append({"title": "行业真相与市场空间", "answers": [q for q in questions if "规模" in q or "空间" in q]})
            sections.append({"title": "投入产出与财务测算", "answers": [q for q in questions if "投入" in q or "产出" in q or "回本" in q]})
            sections.append({"title": "战略卡位与替代路径", "answers": [q for q in questions if "卡位" in q or "战略" in q]})
            sections.append({"title": "最坏损失与风险", "answers": [q for q in questions if "损失" in q or "风险" in q]})
            sections.append({"title": "衍生价值与期权", "answers": [q for q in questions if "衍生" in q or "期权" in q]})
            sections.append({"title": "执行路线图", "answers": []})
        else:
            for q in questions:
                sections.append({"title": q[:20], "answers": [q]})
        return sections

    def _guardrails(self, report_type: str) -> list:
        if report_type == "decision_memo":
            return ["禁止投资评级/目标价/EPS", "禁止二级市场用语",
                    "禁止匿名化委托方", "禁止编造数据（须带来源）"]
        return ["禁止编造数据", "禁止主观评分"]

    @staticmethod
    def _extract_keywords(question: str) -> list:
        """从必答问题提取关键词（用于意图符合性近似匹配）。"""
        # 去除疑问词/标点，取 2-4 字核心词
        _stop = {"什么", "多少", "怎么", "为什么", "如何", "是否", "多大", "多久",
                 "？", "?", "，", ",", "。", "、", "的", "了", "？"}
        words = []
        for ch in re.split(r"[，。？,?!?]", question):
            ch = ch.strip()
            if len(ch) >= 2 and ch not in _stop:
                words.append(ch[:6])
        # 追加高频业务词（行业关键词）
        for kw in ["市场", "规模", "投入", "产出", "卡位", "风险", "损失", "估值",
                   "竞争", "渠道", "代工", "衍生", "期权", "技术", "政策"]:
            if kw in question:
                words.append(kw)
        return words


def parse_requirement_cli(asset: str, requirement: str, report_type: str = "decision_memo",
                          client: str = "") -> dict:
    """CLI 便捷入口。"""
    ip = IntentParser()
    return ip.parse(asset, report_type, requirement, client)
