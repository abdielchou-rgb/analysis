# -*- coding: utf-8 -*-
"""Intent Parser - 意图解析器

将用户输入解析为结构化的 Intent 对象
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from core.analysis_context import IntentType


class ProblemClass(Enum):
    """问题分类 - 用于方法选择"""

    PROFITABILITY_ANALYSIS = "profitability_analysis"
    GROWTH_ANALYSIS = "growth_analysis"
    VALUATION = "valuation"
    COMPETITIVE_POSITION = "competitive_position"
    RISK_ASSESSMENT = "risk_assessment"
    CASH_FLOW_ANALYSIS = "cash_flow_analysis"
    BALANCE_SHEET_QUALITY = "balance_sheet_quality"
    MARKET_SIZING = "market_sizing"
    COMPETITIVE_DYNAMICS = "competitive_dynamics"
    REGULATORY_RISK = "regulatory_risk"
    TECHNOLOGY_DISRUPTION = "technology_disruption"
    MANAGEMENT_QUALITY = "management_quality"
    CAPITAL_ALLOCATION = "capital_allocation"
    UNSPECIFIED = "unspecified"


@dataclass(frozen=True)
class ParsedIntent:
    """解析后的意图"""

    original_text: str
    asset: str
    report_type: IntentType
    problem_classes: FrozenSet[ProblemClass]
    explicit_questions: Tuple[str, ...]
    implicit_questions: Tuple[str, ...]
    constraints: Dict[str, Any]
    time_horizon: Optional[str] = None
    focus_areas: FrozenSet[str] = field(default_factory=frozenset)
    exclude_areas: FrozenSet[str] = field(default_factory=frozenset)
    confidence: float = 1.0


class IntentParser:
    """意图解析器 - 将自然语言/结构化输入解析为结构化 Intent"""

    # 问题类别关键词映射
    PROBLEM_CLASS_KEYWORDS = {
        ProblemClass.PROFITABILITY_ANALYSIS: [
            "盈利",
            "毛利",
            "净利",
            "利润",
            "ROE",
            "ROA",
            "利润率",
            "盈利能力",
            "profitability",
            "margin",
            "profit",
            "earnings",
        ],
        ProblemClass.GROWTH_ANALYSIS: [
            "增长",
            "增速",
            "增量",
            "扩张",
            "扩产",
            "新产能",
            "新产品",
            "growth",
            "growth_rate",
            "expansion",
        ],
        ProblemClass.VALUATION: [
            "估值",
            "目标价",
            "PE",
            "PB",
            "DCF",
            "估值模型",
            "溢价",
            "折价",
            "valuation",
            "target_price",
            "fair_value",
        ],
        ProblemClass.COMPETITIVE_POSITION: [
            "竞争",
            "市场份额",
            "竞争力",
            "护城河",
            "竞争优势",
            "市场地位",
            "competitive",
            "market_share",
            "moat",
            "positioning",
        ],
        ProblemClass.RISK_ASSESSMENT: [
            "风险",
            "下行",
            "隐患",
            "不确定",
            "威胁",
            "下行风险",
            "risk",
            "downside",
            "threat",
            "uncertainty",
        ],
        ProblemClass.CASH_FLOW_ANALYSIS: [
            "现金流",
            "FCF",
            "自由现金流",
            "经营现金流",
            "现金流量",
            "cash_flow",
            "FCF",
            "operating_cash_flow",
        ],
        ProblemClass.BALANCE_SHEET_QUALITY: [
            "资产负债表",
            "负债",
            "资产质量",
            "商誉",
            "存货",
            "应收账款",
            "balance_sheet",
            "leverage",
            "debt",
            "asset_quality",
        ],
        ProblemClass.MARKET_SIZING: [
            "市场规模",
            "TAM",
            "SAM",
            "SOM",
            "市场空间",
            "渗透率",
            "market_size",
            "TAM",
            "penetration",
        ],
        ProblemClass.COMPETITIVE_DYNAMICS: [
            "竞争格局",
            "竞争对手",
            "新进入者",
            "替代品",
            "供应商",
            "客户",
            "competitive_dynamics",
            "competitors",
            "new_entrants",
        ],
        ProblemClass.REGULATORY_RISK: [
            "政策",
            "监管",
            "合规",
            "牌照",
            "许可",
            "监管风险",
            "regulation",
            "policy",
            "compliance",
            "license",
        ],
        ProblemClass.TECHNOLOGY_DISRUPTION: [
            "技术颠覆",
            "创新",
            "颠覆性",
            "新技术",
            "替代",
            "disruption",
            "innovation",
            "technology",
        ],
        ProblemClass.MANAGEMENT_QUALITY: [
            "管理层",
            "治理",
            "激励",
            "股权结构",
            "大股东",
            "management",
            "governance",
            "incentive",
        ],
        ProblemClass.CAPITAL_ALLOCATION: [
            "资本配置",
            "分红",
            "回购",
            "并购",
            "投资",
            "资本支出",
            "capital_allocation",
            "dividend",
            "buyback",
            "M&A",
            "capex",
        ],
    }

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译正则模式"""
        self._class_patterns = {}
        for cls, keywords in self.PROBLEM_CLASS_KEYWORDS.items():
            pattern = "|".join(re.escape(kw) for kw in keywords)
            self._class_patterns[cls] = re.compile(pattern, re.IGNORECASE)

    def parse(
        self,
        text: str,
        asset: str = "",
        report_type: IntentType = IntentType.INDUSTRY_DEEP,
        explicit_questions: List[str] = None,
        context: Dict = None,
    ) -> "ParsedIntent":
        """
        解析意图

        Args:
            text: 用户输入文本
            asset: 分析标的
            report_type: 报告类型
            explicit_questions: 显式问题清单
            context: 额外上下文

        Returns:
            ParsedIntent: 解析后的意图
        """
        text = text or ""
        explicit_questions = explicit_questions or []
        context = context or {}

        # 1. 识别问题类别
        problem_classes = self._classify_problems(text, context)

        # 2. 提取显式问题
        explicit_qs = self._extract_explicit_questions(text, explicit_questions)

        # 3. 生成隐式问题
        implicit_qs = self._generate_implicit_questions(problem_classes, context)

        # 4. 提取约束条件
        constraints = self._extract_constraints(text, context)

        # 5. 确定时间跨度和关注领域
        time_horizon = self._extract_time_horizon(text, context)
        focus_areas = self._extract_focus_areas(text, context)
        exclude_areas = self._extract_exclude_areas(text, context)

        return ParsedIntent(
            original_text=text,
            asset=asset,
            report_type=report_type,
            problem_classes=frozenset(problem_classes),
            explicit_questions=tuple(explicit_qs),
            implicit_questions=tuple(implicit_qs),
            constraints=constraints,
            time_horizon=time_horizon,
            focus_areas=frozenset(focus_areas),
            exclude_areas=frozenset(exclude_areas),
            confidence=0.8,  # TODO: 基于匹配度计算
        )

    def _classify_problems(self, text: str, context: Dict) -> List[ProblemClass]:
        """识别问题类别"""
        problem_classes = []
        text_lower = text.lower()
        context_text = " ".join(str(v) for v in context.values()).lower()
        full_text = text_lower + " " + context_text

        for cls, pattern in self._class_patterns.items():
            if pattern.search(full_text):
                problem_classes.append(cls)

        if not problem_classes:
            problem_classes = [ProblemClass.UNSPECIFIED]

        return problem_classes

    def _extract_explicit_questions(self, text: str, explicit_questions: List[str]) -> List[str]:
        """提取显式问题"""
        questions = list(explicit_questions)

        # 从文本中提取问句
        question_patterns = [
            r"[？?]",
            r"如何[^。]*",
            r"为什么[^。]*",
            r"是否[^。]*",
            r"能否[^。]*",
        ]

        for pattern in question_patterns:
            matches = re.findall(pattern, text)
            questions.extend(matches)

        # 去重
        seen = set()
        unique = []
        for q in questions:
            q = q.strip()
            if q and q not in seen:
                seen.add(q)
                unique.append(q)

        return unique[:10]  # 最多 10 个显式问题

    def _generate_implicit_questions(self, problem_classes: List[ProblemClass], context: Dict) -> List[str]:
        """基于问题类别生成隐式问题"""
        implicit = []

        for cls in problem_classes:
            if cls == ProblemClass.PROFITABILITY_ANALYSIS:
                implicit.extend(
                    [
                        "毛利率变化的核心驱动因素是什么？",
                        "净利率是否可持续？",
                        "ROE 分解：利润率、周转率、杠杆谁在驱动？",
                    ]
                )
            elif cls == ProblemClass.GROWTH_ANALYSIS:
                implicit.extend(["增长是否可持续？", "增长来自量还是价？", "市场空间还能支撑多久？"])
            elif cls == ProblemClass.VALUATION:
                implicit.extend(["当前估值是否合理？", "多模型估值是否自洽？", "关键假设敏感性如何？"])
            elif cls == ProblemClass.COMPETITIVE_POSITION:
                implicit.extend(["核心竞争优势是什么？", "护城河是加宽还是收窄？", "竞争格局是否发生结构性变化？"])
            elif cls == ProblemClass.RISK_ASSESSMENT:
                implicit.extend(["最大的下行风险是什么？", "压力测试下的极端情况如何？", "关键假设失效的概率多大？"])

        return list(dict.fromkeys(implicit))[:8]  # 去重，最多 8 个

    def _extract_constraints(self, text: str, context: Dict) -> Dict[str, Any]:
        """提取约束条件"""
        constraints = {}

        # 时间约束
        time_matches = re.findall(r"(20\d{2})年?", text)
        if time_matches:
            constraints["time_horizon"] = time_matches

        # 数值约束
        for pattern, key in [
            (r"不低于\s*(\d+(?:\.\d+)?)\s*%", "min_margin"),
            (r"不高于\s*(\d+(?:\.\d+)?)\s*倍", "max_pe"),
            (r"目标价\s*(\d+(?:\.\d+)?)\s*元", "target_price"),
        ]:
            matches = re.findall(pattern, text)
            if matches:
                constraints[key] = matches[0]

        # 排除领域
        exclude_keywords = ["不关注", "排除", "忽略", "不考虑"]
        for kw in exclude_keywords:
            if kw in text:
                constraints.setdefault("exclude", []).append(kw)

        return constraints

    def _extract_time_horizon(self, text: str, context: Dict) -> Optional[str]:
        """提取时间跨度"""
        patterns = [
            r"(未来\s*\d+\s*年?)",
            (r"未来\s*\d+\s*季度?"),
            (r"未来\s*\d+\s*月?"),
            (r"短期|中期|长期"),
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        return None

    def _extract_focus_areas(self, text: str, context: Dict) -> List[str]:
        """提取关注领域"""
        focus_map = {
            "营收": "revenue",
            "利润": "profit",
            "毛利": "gross_margin",
            "净利": "net_profit",
            "现金流": "cash_flow",
            "估值": "valuation",
            "风险": "risk",
            "竞争": "competition",
            "增长": "growth",
            "分红": "dividend",
        }

        focus = []
        for kw, area in focus_map.items():
            if kw in text:
                focus.append(area)
        return list(dict.fromkeys(focus))  # 去重保序

    def _extract_exclude_areas(self, text: str, context: Dict) -> List[str]:
        """提取排除领域"""
        exclude = []
        exclude_keywords = ["不关注", "排除", "忽略", "不考虑"]
        for kw in exclude_keywords:
            if kw in text:
                # 简单提取后面的词
                idx = text.find(kw)
                if idx >= 0:
                    after = text[idx + len(kw) : idx + len(kw) + 20]
                    exclude.append(after.strip().split()[0] if after.strip() else kw)
        return exclude
