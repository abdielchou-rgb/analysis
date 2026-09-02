"""
Confidence Gating — 低置信度输出拦截器

基于 arXiv:2604.13717 (Composo AI, 2026) 的四大技术：
1. Ensemble Scoring: 多次独立评分取均值
2. Task-Specific Criteria: 针对每个维度定制评分标准
3. Calibration Context: 注入参考样例锚定评分尺度
4. Adaptive Model Escalation: 简单用小模型，复杂用大模型

本模块实现 Confidence Gating：
- 对LLM输出进行置信度评估
- 低置信度输出拦截，要求重写
- 高置信度输出放行
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.confidence_gating")


@dataclass
class ConfidenceResult:
    """置信度评估结果"""

    dimension: str
    confidence: float  # 0.0 - 1.0
    passed: bool
    details: str
    issues: list[str] = field(default_factory=list)


class ConfidenceGating:
    """置信度门禁系统"""

    def __init__(self, report_type: str = "unlisted_company"):
        self.report_type = report_type
        self._thresholds = self._load_thresholds()
        self._calibration_examples = self._load_calibration_examples()

    def _load_thresholds(self) -> dict:
        """加载置信度阈值"""
        default_thresholds = {
            "unlisted_company": {
                "overall": 0.7,  # 整体置信度阈值
                "dimension_min": 0.5,  # 单维度最低置信度
                "critical_dimensions": [  # 关键维度（必须高置信度）
                    "decision_gate",
                    "falsification",
                    "core_hypothesis",
                    "valuation_estimate",
                ],
                "critical_threshold": 0.8,  # 关键维度置信度阈值
            },
            "listed_company": {
                "overall": 0.75,
                "dimension_min": 0.55,
                "critical_dimensions": [
                    "bold_call",
                    "falsification",
                    "core_disagreement",
                    "valuation_assessment",
                ],
                "critical_threshold": 0.85,
            },
            "industry_deep": {
                "overall": 0.7,
                "dimension_min": 0.5,
                "critical_dimensions": [
                    "bold_call",
                    "falsification",
                    "core_disagreement",
                ],
                "critical_threshold": 0.8,
            },
        }
        return default_thresholds.get(self.report_type, default_thresholds["unlisted_company"])

    def _load_calibration_examples(self) -> dict:
        """加载校准样例（高/低分示例）"""
        # 简化版：实际应用中可以从文件加载
        return {
            "high_score_example": {
                "text": "我们判断浙江觉纤在华为和宁德量产爬坡的驱动下，2027年有望实现8-12%的市场份额(A，据C114通信网2025-2026年度分析)。核心依据：1)华为联合%研发费用(A，据宁波海曙区产业政策文件)；2)华为年度采购量30%基础份额(F，据华为2026承诺)。",
                "confidence": 0.9,
            },
            "low_score_example": {
                "text": "市场规模为46亿美元。公司是行业龙头。竞争激烈。",
                "confidence": 0.3,
            },
        }

    def evaluate_dimension(self, dimension: str, text: str, data_dict: dict = None) -> ConfidenceResult:
        """评估单个维度的置信度"""
        issues = []
        confidence_scores = []

        # 1. 关键词覆盖检查
        keyword_score = self._check_keyword_coverage(dimension, text)
        confidence_scores.append(keyword_score)

        # 2. 数据支撑检查
        data_score = self._check_data_support(text, data_dict)
        confidence_scores.append(data_score)

        # 3. 判断密度检查
        judgment_score = self._check_judgment_density(text)
        confidence_scores.append(judgment_score)

        # 4. 来源标注检查
        source_score = self._check_source_annotations(text)
        confidence_scores.append(source_score)

        # 5. So What链检查
        so_what_score = self._check_so_what_chain(text)
        confidence_scores.append(so_what_score)

        # 计算综合置信度
        overall_confidence = sum(confidence_scores) / len(confidence_scores)

        # 检查是否通过
        threshold = self._thresholds["dimension_min"]
        if dimension in self._thresholds["critical_dimensions"]:
            threshold = self._thresholds["critical_threshold"]

        passed = overall_confidence >= threshold

        return ConfidenceResult(
            dimension=dimension,
            confidence=overall_confidence,
            passed=passed,
            details=f"置信度: {overall_confidence:.2f} (阈值: {threshold})",
            issues=issues,
        )

    def _check_keyword_coverage(self, dimension: str, text: str) -> float:
        """检查关键词覆盖"""
        # 简化版：实际应用中可以从SAC YAML加载关键词
        dimension_keywords = {
            "company_profile": ["公司", "注册", "成立", "主营"],
            "business_kpi": ["营收", "利润", "毛利率", "KPI"],
            "funding_history": ["融资", "轮次", "估值", "投资"],
            "competitive_moat": ["竞争", "壁垒", "护城河", "优势"],
            "valuation_estimate": ["估值", "目标价", "PE", "PS"],
            "exit_analysis": ["退出", "IPO", "并购", "转让"],
            "due_diligence": ["尽调", "核实", "确认", "验证"],
            "falsification": ["证伪", "风险", "红线", "推翻"],
            "decision_gate": ["决策", "GO", "NO-GO", "判断"],
            "core_hypothesis": ["核心", "假设", "判断", "观点"],
        }

        keywords = dimension_keywords.get(dimension, [])
        if not keywords:
            return 0.7  # 默认置信度

        covered = sum(1 for kw in keywords if kw in text)
        return min(1.0, covered / max(len(keywords), 1))

    def _check_data_support(self, text: str, data_dict: dict = None) -> float:
        """检查数据支撑"""
        # 统计数据点数量
        data_patterns = re.findall(r"\d+(?:\.\d+)?\s*(?:%|亿元|亿|倍|万股|元|万吨|万台)", text)
        data_count = len(data_patterns)

        # 统计来源标注数量
        source_patterns = re.findall(r"据[^，。]+", text)
        source_count = len(source_patterns)

        # 计算数据支撑分数
        if data_count == 0:
            return 0.3
        elif source_count == 0:
            return 0.5
        else:
            return min(1.0, (data_count + source_count) / 10)

    def _check_judgment_density(self, text: str) -> float:
        """检查判断密度"""
        judgment_words = [
            "我们认为",
            "我们判断",
            "我们预计",
            "预计",
            "有望",
            "超预期",
            "低于预期",
            "判断",
            "评级",
            "建议",
            "看好",
            "看空",
            "风险",
            "催化剂",
            "拐点",
            "推荐",
        ]

        judgment_count = sum(text.count(word) for word in judgment_words)
        kchars = len(text) / 1000.0

        if kchars == 0:
            return 0.3

        density = judgment_count / kchars

        # 目标密度：5.0/千字
        if density >= 5.0:
            return 1.0
        elif density >= 3.0:
            return 0.8
        elif density >= 1.2:
            return 0.6
        else:
            return 0.3

    def _check_source_annotations(self, text: str) -> float:
        """检查来源标注"""
        # 统计来源标注数量
        source_patterns = re.findall(r"据[^，。]+", text)
        source_count = len(source_patterns)

        # 统计数据点数量
        data_patterns = re.findall(r"\d+(?:\.\d+)?\s*(?:%|亿元|亿|倍|万股|元|万吨|万台)", text)
        data_count = len(data_patterns)

        if data_count == 0:
            return 0.7  # 无数据点，跳过检查

        # 来源覆盖率
        coverage = source_count / max(data_count, 1)

        if coverage >= 0.3:
            return 1.0
        elif coverage >= 0.2:
            return 0.8
        elif coverage >= 0.1:
            return 0.6
        else:
            return 0.3

    def _check_so_what_chain(self, text: str) -> float:
        """检查So What链"""
        so_what_words = [
            "因此",
            "这意味着",
            "我们判断",
            "导致",
            "从而",
            "影响",
            "意味着",
            "综合判断",
            "本质上",
            "核心驱动",
            "基于此",
            "综合看",
            "So What",
            "关键结论",
            "究其根本",
        ]

        # 统计段落数量
        paragraphs = text.split("\n\n")
        paragraph_count = len(paragraphs)

        if paragraph_count == 0:
            return 0.3

        # 统计包含So What词的段落数量
        so_what_count = sum(1 for p in paragraphs if any(word in p for word in so_what_words))

        # 计算覆盖率
        coverage = so_what_count / max(paragraph_count, 1)

        if coverage >= 0.6:
            return 1.0
        elif coverage >= 0.4:
            return 0.8
        elif coverage >= 0.2:
            return 0.6
        else:
            return 0.3

    def evaluate_report(self, report_text: str, data_dict: dict = None) -> list[ConfidenceResult]:
        """评估整个报告的置信度"""
        results = []

        # 分割报告为维度段落
        dimension_patterns = {
            "company_profile": r"公司.*?简介|公司.*?概况|公司.*?定位",
            "business_kpi": r"业务.*?指标|KPI|营收|利润",
            "funding_history": r"融资.*?历史|融资.*?历程|股权.*?结构",
            "competitive_moat": r"竞争.*?壁垒|护城河|竞争优势",
            "valuation_estimate": r"估值.*?分析|目标价|估值.*?三角",
            "exit_analysis": r"退出.*?路径|IPO|并购|转让",
            "due_diligence": r"尽职.*?调查|尽调|待核实",
            "falsification": r"证伪.*?条件|风险.*?红线|推翻.*?判断",
            "decision_gate": r"决策.*?门|GO.*?NO-GO|投资.*?判断",
            "core_hypothesis": r"核心.*?假设|核心.*?判断|关键.*?观点",
        }

        for dimension, pattern in dimension_patterns.items():
            # 查找维度段落
            matches = re.findall(pattern, report_text)
            if matches:
                # 提取段落内容（简化版：取匹配位置前后各200字）
                for match in matches:
                    idx = report_text.find(match)
                    start = max(0, idx - 200)
                    end = min(len(report_text), idx + len(match) + 200)
                    paragraph = report_text[start:end]

                    # 评估置信度
                    result = self.evaluate_dimension(dimension, paragraph, data_dict)
                    results.append(result)
            else:
                # 维度未找到，给低置信度
                results.append(
                    ConfidenceResult(
                        dimension=dimension,
                        confidence=0.2,
                        passed=False,
                        details=f"维度 {dimension} 未在报告中找到",
                        issues=[f"维度 {dimension} 缺失"],
                    )
                )

        return results

    def should_block(self, results: list[ConfidenceResult]) -> tuple[bool, str]:
        """判断是否应该拦截输出"""
        # 检查整体置信度
        if not results:
            return True, "无评估结果"

        overall_confidence = sum(r.confidence for r in results) / len(results)

        # 检查是否有关键维度失败
        critical_failures = [
            r for r in results if not r.passed and r.dimension in self._thresholds["critical_dimensions"]
        ]

        # 检查失败维度数量
        failed_count = sum(1 for r in results if not r.passed)
        failed_ratio = failed_count / len(results)

        # 判断是否拦截
        if overall_confidence < self._thresholds["overall"]:
            return True, f"整体置信度 {overall_confidence:.2f} < {self._thresholds['overall']}"

        if critical_failures:
            return True, f"关键维度失败: {[r.dimension for r in critical_failures]}"

        if failed_ratio > 0.3:
            return True, f"失败维度过多: {failed_ratio:.0%}"

        return False, "置信度通过"


def confidence_gating_prompt(results: list[ConfidenceResult]) -> str:
    """生成置信度门禁反馈prompt"""
    failed_dims = [r for r in results if not r.passed]

    if not failed_dims:
        return ""

    lines = [
        "## [置信度门禁反馈] 以下维度置信度不足，请重写：",
        "",
    ]

    for r in failed_dims:
        lines.append(f"### {r.dimension}")
        lines.append(f"- 置信度: {r.confidence:.2f} (阈值: {self._thresholds.get('dimension_min', 0.5)})")
        lines.append(f"- 问题: {'; '.join(r.issues) if r.issues else '置信度不足'}")
        lines.append("- 建议: 增加数据支撑、来源标注、判断密度")
        lines.append("")

    return "\n".join(lines)
