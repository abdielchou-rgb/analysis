"""
2号分析师 ProbabilisticDeepCheck — 概率性深度检查

职责：
1. 确定性检查：100% 执行 SAC 维度覆盖率检查、图表密度等规则检查
2. 概率性检查：20% 概率触发深度质量分析，随机抽取 1-2 个 SAC 维度
   做推理链条完整性验证（不仅检查关键词出现，还检查"因为->所以->因此"模式）
3. 输出标准化的检查结果，可被 IronGate 和 WriteReviseLoop 消费

防 Game 机制设计：
- IronGate 是确定性门禁（规则固定，可被 Agent 针对性优化）
- ProbabilisticDeepCheck 是概率性抽查（不可预测，无法针对性优化）
- Agent 无法判断本次是否会触发深度检查→倒逼全维度认真写作

集成方式：
    from pipeline.probabilistic_deep_check import ProbabilisticDeepCheck
    deep = ProbabilisticDeepCheck("industry_deep")
    result = deep.check(report_text)
    if result["probabilistic_triggered"]:
        # 深度检查未通过，必须重写
        print(deep.get_feedback(result))
"""

from __future__ import annotations

import logging
import random
import re
from typing import Any

from core.sacs import SACLoader

logger = logging.getLogger("2hao.probabilistic_deep_check")


class ProbabilisticDeepCheck:
    """概率性深度检查器

    Parameters
    ----------
    report_type : str
        报告类型，用于加载对应的 SAC 框架。
    trigger_probability : float
        触发概率性深度检查的概率，默认 0.20（20%）。
    random_seed : Optional[int]
        可选的随机种子，用于可复现测试。生产环境不设置。
    """

    # 推理链关键词模式：用于检测"因为->所以->因此"逻辑连接
    REASONING_PATTERNS = {
        "causal_forward": [r"因为", r"由于", r"源于", r"得益于", r"受(到|益于)", r"基于", r"考虑到"],
        "causal_backward": [r"因此", r"所以", r"从而导致", r"进而", r"推动", r"带动", r"意味着"],
        "conclusion": [r"综上所述", r"综上", r"可见", r"鉴于此", r"这表明", r"这说明", r"由此判断"],
        "conditional": [r"如果", r"假设", r"一旦", r"当.*时", r"在.*条件下"],
        "contrast": [r"然而", r"但(是)?", r"不过", r"相反", r"另一方面", r"与之不同"],
    }

    # 数据来源标注模式
    SOURCE_PATTERNS = [
        r"来源[：:]",
        r"数据来源[：:]",
        r"据[^。]*?(报告|数据|统计|调研)",
        r"(Wind|Bloomberg|中金|申万|中信|东方财富|同花顺|公司年报|公告|招股书)",
        r"(前瞻产业研究院|艾瑞咨询|IDC|Gartner|Frost & Sullivan|Yole|MarketsandMarkets)",
        r"(国家统计局|海关总署|工信部|科技部|发改委|国务院)",
        r"(行业访谈|专家访谈|实地调研|产业链调研|草根调研)",
    ]

    def __init__(
        self,
        report_type: str = "industry_deep",
        trigger_probability: float = 0.20,
        random_seed: int | None = None,
    ):
        self.report_type = report_type
        self.probability = max(0.0, min(1.0, trigger_probability))
        self._seed = random_seed

        # 加载 SAC 框架
        self.sac = SACLoader(report_type)
        if not self.sac.is_loaded():
            logger.warning("SAC YAML 未加载成功，使用内置兜底维度")
            self.dimension_ids = self._fallback_dimension_ids()
        else:
            self.dimension_ids = self.sac.get_dimension_ids()

        self.logic_chain = self.sac.get_logic_chain()
        self.evidence_reqs = self.sac.get_evidence_requirements()

    # ── 外部入口 ──────────────────────────────────────────────────────────

    def check(self, report_text: str) -> dict[str, Any]:
        """执行完整检查，返回结构化检查结果。

        Parameters
        ----------
        report_text : str
            待检查的报告文本。

        Returns
        -------
        dict
            包含 deterministic（确定性检查）和 probabilistic（概率性检查）两部分结果。
        """
        if not report_text or len(report_text.strip()) < 100:
            return {
                "deterministic": {"error": "报告文本为空或过短"},
                "probabilistic": {},
                "probabilistic_triggered": False,
                "overall_passed": False,
            }

        # 1. 确定性检查：100% 执行
        deterministic = self._run_deterministic_checks(report_text)

        # 2. 概率性检查：以 probability 概率触发
        probabilistic = {}
        triggered = self._should_trigger()

        if triggered:
            probabilistic = self._run_probabilistic_checks(report_text)

        # 3. 综合判定
        det_passed = deterministic.get("overall_passed", False)
        prob_passed = not triggered or probabilistic.get("overall_passed", False)

        return {
            "deterministic": deterministic,
            "probabilistic": probabilistic,
            "probabilistic_triggered": triggered,
            "overall_passed": det_passed and prob_passed,
            "report_type": self.report_type,
            "word_count": len(report_text),
        }

    def get_feedback(self, result: dict[str, Any]) -> str:
        """将检查结果转换为人类可读的反馈文本。

        Parameters
        ----------
        result : dict
            check() 方法返回的结果字典。

        Returns
        -------
        str
            格式化的反馈文本，可直接注入 DeepSeek prompt 或日志记录。
        """
        lines = [
            "=" * 64,
            "ProbabilisticDeepCheck — 检查报告",
            "=" * 64,
        ]

        # 确定性检查摘要
        det = result.get("deterministic", {})
        lines.append("\n## 确定性检查")
        lines.append(f"  总体通过: {'是' if det.get('overall_passed', False) else '否'}")
        lines.append(f"  SAC维度覆盖率: {det.get('sac_coverage', {}).get('score', 0):.0%}")

        sac_cov = det.get("sac_coverage", {})
        covered = sac_cov.get("covered", [])
        missing = sac_cov.get("missing", [])
        if covered:
            lines.append(f"  已覆盖维度 ({len(covered)}): {', '.join(covered)}")
        if missing:
            lines.append(f"  缺失维度 ({len(missing)}): {', '.join(missing)}")

        # 图表密度
        charts = det.get("chart_density", {})
        lines.append(f"  图表密度: {charts.get('chart_count', 0)} 张图表, 阈值 {charts.get('min_required', 5)}")

        # 逻辑链完整性
        lc = det.get("logic_chain_completeness", {})
        lines.append(
            f"  逻辑链完整性: {lc.get('coverage', 0):.0%} ({lc.get('covered_steps', 0)}/{lc.get('total_steps', 0)})"
        )

        # 数据可追溯性
        dt = det.get("data_traceability", {})
        lines.append(f"  数据来源标注: {dt.get('source_count', 0)} 处")

        # 概率性检查摘要
        prob = result.get("probabilistic", {})
        triggered = result.get("probabilistic_triggered", False)
        lines.append("\n## 概率性深度检查")
        lines.append(f"  本批次触发: {'是' if triggered else '否（未抽中，跳过）'}")

        if triggered:
            lines.append(f"  总体通过: {'是' if prob.get('overall_passed', False) else '否'}")
            deep_dims = prob.get("deep_checked_dimensions", [])
            lines.append(f"  深度检查维度: {', '.join(deep_dims) if deep_dims else '无'}")

            for dim_id in deep_dims:
                dim_result = prob.get(dim_id, {})
                lines.append(f"\n  [{dim_id}]")
                lines.append(f"    关键词覆盖: {dim_result.get('keyword_score', 0):.0%}")
                lines.append(f"    推理链质量: {dim_result.get('reasoning_score', 0):.0%}")
                lines.append(f"    数据来源: {dim_result.get('source_count', 0)} 处")
                issues = dim_result.get("issues", [])
                if issues:
                    lines.append("    问题:")
                    for issue in issues:
                        lines.append(f"      - {issue}")

            if not prob.get("overall_passed", False):
                lines.append("\n  ⚠ 深度检查未通过，建议重写对应维度。")

        lines.append("\n" + "=" * 64)
        return "\n".join(lines)

    def get_structured_feedback(self, result: dict[str, Any]) -> dict[str, Any]:
        """返回结构化反馈，供 IronGate 或 WriteReviseLoop 消费。

        Returns
        -------
        dict
            包含 passed、failures、suggestions 的 dict，与 IronGate 的 GateReport 兼容。
        """
        failures = []
        suggestions = []

        det = result.get("deterministic", {})
        prob = result.get("probabilistic", {})

        # 确定性失败
        sac_cov = det.get("sac_coverage", {})
        if sac_cov.get("missing"):
            failures.append(f"SAC维度缺失: {', '.join(sac_cov['missing'])}")
            suggestions.append(f"请补充以下维度的分析: {', '.join(sac_cov['missing'])}")

        lc = det.get("logic_chain_completeness", {})
        if lc.get("missing_steps"):
            failures.append(f"逻辑链步骤缺失: {', '.join(lc['missing_steps'])}")
            suggestions.append(f"请按 SAC 因果链补充: {', '.join(lc['missing_steps'])}")

        charts = det.get("chart_density", {})
        if not charts.get("passed", True):
            failures.append(f"图表密度不足: {charts.get('chart_count', 0)} < {charts.get('min_required', 5)}")
            suggestions.append(f"至少需要 {charts.get('min_required', 5)} 张图表")

        # 概率性失败
        triggered = result.get("probabilistic_triggered", False)
        if triggered and not prob.get("overall_passed", False):
            for dim_id in prob.get("deep_checked_dimensions", []):
                dim_result = prob.get(dim_id, {})
                if dim_result.get("issues"):
                    failures.append(f"[深度] {dim_id}: {'; '.join(dim_result['issues'])}")

        return {
            "passed": result.get("overall_passed", False),
            "failures": failures,
            "suggestions": suggestions,
            "probabilistic_triggered": triggered,
        }

    # ── 确定性检查 ────────────────────────────────────────────────────────

    def _run_deterministic_checks(self, text: str) -> dict[str, Any]:
        """执行所有确定性检查（100% 执行）。"""
        results = {}

        # 1. SAC 维度覆盖率检查
        results["sac_coverage"] = self._check_sac_coverage(text)

        # 2. 图表密度检查
        results["chart_density"] = self._check_chart_density(text)

        # 3. 逻辑链完整性检查
        results["logic_chain_completeness"] = self._check_logic_chain(text)

        # 4. 数据可追溯性检查
        results["data_traceability"] = self._check_data_traceability(text)

        # 5. 总体判定
        all_passed = all(r.get("passed", False) if isinstance(r, dict) else False for r in results.values())
        results["overall_passed"] = all_passed

        return results

    def _check_sac_coverage(self, text: str) -> dict[str, Any]:
        """检查 SAC 所有维度的关键词覆盖率。

        每个维度检查其定义中的 keywords 是否在文本中出现。
        部分维度有 required_elements 要求（如"产业链"、"利润"等）。
        """
        covered = []
        missing = []
        dim_scores = {}

        for dim_id in self.dimension_ids:
            dim = self.sac.get_dimension(dim_id)
            if not dim:
                continue

            # 优先检查 required_elements
            required = dim.get("required_elements", [])
            keywords = dim.get("keywords", [])
            question = dim.get("question", "")

            # 构建检查关键词集合
            check_terms = set()
            if required:
                check_terms.update(required)
            if keywords:
                check_terms.update(keywords)
            # 从 question 中提取关键名词
            if question:
                q_words = re.findall(r"[\u4e00-\u9fff]{2,}", question)
                # 只取前 3 个最有信息量的词
                check_terms.update(q_words[:3])

            if not check_terms:
                # 如果没有关键词定义，用 dim_id 本身做粗略检查
                check_terms = {dim_id}

            # 计算覆盖率
            found = [t for t in check_terms if t in text]
            score = len(found) / len(check_terms) if check_terms else 0.0

            dim_scores[dim_id] = {
                "score": score,
                "found": found,
                "total": len(check_terms),
                "passed": score >= 0.5,
            }

            if score >= 0.5:
                covered.append(dim_id)
            else:
                missing.append(dim_id)

        overall_score = sum(d["score"] for d in dim_scores.values()) / len(dim_scores) if dim_scores else 0.0
        passed = overall_score >= 0.6 and len(missing) <= len(self.dimension_ids) * 0.3

        return {
            "covered": covered,
            "missing": missing,
            "scores": dim_scores,
            "overall_score": overall_score,
            "passed": passed,
        }

    def _check_chart_density(self, text: str) -> dict[str, Any]:
        """检查图表密度是否满足 SAC 要求。"""
        try:
            chart_config = self.sac.get_chart_config()
            min_charts = chart_config.get("min_charts", 5)
        except Exception:
            min_charts = {"industry_deep": 5, "listed_company": 5, "unlisted_company": 3, "earnings_notes": 3}.get(
                self.report_type, 5
            )

        # 统计图表引用：![]() 和表格（|---| 模式）
        img_count = len(re.findall(r"!\[.*?\]\(.*?\)", text))
        table_count = len(re.findall(r"^\|.+\|$", text, re.MULTILINE))

        # 检查图表编号规律（如 图1、图2、表1、表2）
        fig_refs = len(re.findall(r"[图圖][：: ]?\d+", text))
        tab_refs = len(re.findall(r"[表][：: ]?\d+", text))

        chart_count = max(img_count, fig_refs)
        table_total = max(table_count, tab_refs)
        total_visuals = chart_count + table_total

        passed = chart_count >= min_charts

        return {
            "chart_count": chart_count,
            "table_count": table_total,
            "total_visuals": total_visuals,
            "min_required": min_charts,
            "passed": passed,
        }

    def _check_logic_chain(self, text: str) -> dict[str, Any]:
        """检查逻辑链完整性：每个 logic_chain step 是否在报告中有对应内容。"""
        if not self.logic_chain:
            return {"coverage": 1.0, "covered_steps": 0, "total_steps": 0, "missing_steps": [], "passed": True}

        covered_steps = []
        missing_steps = []

        for step in self.logic_chain:
            step_name = step.get("step", "")
            description = step.get("description", "")
            maps_to = step.get("maps_to", [])

            # 检查 step 名称是否出现在文本（作为章节标题或行文引用）
            name_in_text = step_name in text

            # 检查 maps_to 维度是否被覆盖
            dims_in_text = any(dim in text for dim in maps_to)

            # 检查 description 中的关键短语
            desc_phrases = re.findall(r"[\u4e00-\u9fff]{4,}", description)
            phrases_in_text = any(phrase in text for phrase in desc_phrases[:3])

            if name_in_text or dims_in_text or phrases_in_text:
                covered_steps.append(step_name)
            else:
                missing_steps.append(step_name)

        total = len(self.logic_chain)
        covered = len(covered_steps)
        coverage = covered / total if total > 0 else 1.0
        passed = coverage >= 0.7

        return {
            "coverage": coverage,
            "covered_steps": covered_steps,
            "total_steps": total,
            "missing_steps": missing_steps,
            "passed": passed,
        }

    def _check_data_traceability(self, text: str) -> dict[str, Any]:
        """检查数据来源标注的密度。"""
        source_count = 0
        for pattern in self.SOURCE_PATTERNS:
            matches = re.findall(pattern, text)
            source_count += len(matches)

        # 去重近似：每千字至少应有 1-2 个来源标注
        word_count = len(text)
        expected_min = max(3, word_count // 1000)
        passed = source_count >= expected_min

        return {
            "source_count": source_count,
            "expected_min": expected_min,
            "passed": passed,
        }

    # ── 概率性检查 ────────────────────────────────────────────────────────

    def _should_trigger(self) -> bool:
        """决定本轮是否触发概率性深度检查。"""
        if self._seed is not None:
            random.seed(self._seed)
        return random.random() < self.probability

    def _run_probabilistic_checks(self, text: str) -> dict[str, Any]:
        """执行概率性深度检查。

        随机抽取 1-2 个 SAC 维度，对每个维度检查：
        1. 关键词覆盖（同确定性检查）
        2. 推理链完整性（"因为->所以->因此"模式检测）
        3. 数据来源标注密度
        4. 生成可操作的问题列表
        """
        if not self.dimension_ids:
            return {"overall_passed": True, "deep_checked_dimensions": []}

        # 随机抽取 1-2 个维度
        num_to_check = min(2, len(self.dimension_ids))
        dims_to_check = random.sample(self.dimension_ids, num_to_check)

        results = {"deep_checked_dimensions": dims_to_check}
        all_passed = True

        for dim_id in dims_to_check:
            dim_result = self._deep_check_dimension(text, dim_id)
            results[dim_id] = dim_result
            if not dim_result.get("passed", False):
                all_passed = False

        results["overall_passed"] = all_passed
        return results

    def _deep_check_dimension(self, text: str, dim_id: str) -> dict[str, Any]:
        """对单一 SAC 维度执行深度分析质量检查。

        不仅检查关键词出现，还检查：
        - 推理链完整性（因果连接词密度）
        - 数据来源标注
        - 论点-论据配对
        """
        dim = self.sac.get_dimension(dim_id) or {}
        issues = []

        # 1. 关键词检查
        required = dim.get("required_elements", [])
        keywords = dim.get("keywords", [])
        question = dim.get("question", "")
        evidence_min = dim.get("evidence_min", 1)

        check_terms = set()
        if required:
            check_terms.update(required)
        if keywords:
            check_terms.update(keywords)
        if question:
            q_words = re.findall(r"[\u4e00-\u9fff]{2,}", question)
            check_terms.update(q_words[:3])

        # 尝试定位该维度的文本段落（找包含关键词的上下文窗口）
        dim_texts = self._locate_dimension_text(text, dim_id, check_terms, required)
        combined = " ".join(dim_texts) if dim_texts else text

        # 2. 推理链完整性检查
        reasoning_result = self._check_reasoning_chain(combined)
        reasoning_score = reasoning_result["score"]

        if reasoning_score < 0.3:
            issues.append(f"推理链条薄弱（{reasoning_score:.0%}），缺乏因果连接词")
        elif reasoning_score < 0.6:
            issues.append(f"推理链条一般（{reasoning_score:.0%}），建议补充因果逻辑")

        # 3. 数据来源检查
        source_count = 0
        for pattern in self.SOURCE_PATTERNS:
            matches = re.findall(pattern, combined)
            source_count += len(matches)

        # 每个 evidence_min 至少对应 1 个数据来源
        min_sources = max(1, evidence_min)
        if source_count < min_sources:
            issues.append(f"数据来源不足（{source_count} < {min_sources}），需要更多数据支撑")

        # 4. 关键词检查（在该维度上下文中）
        found_terms = [t for t in check_terms if t in combined]
        keyword_score = len(found_terms) / len(check_terms) if check_terms else 0.0
        if keyword_score < 0.5:
            issues.append(
                f"关键词覆盖不足（{keyword_score:.0%}），仅找到 {len(found_terms)}/{len(check_terms)} 个关键概念"
            )

        # 5. required_elements 强制检查
        missing_required = [r for r in required if r not in combined]
        if missing_required:
            issues.append(f"缺少强制要素: {', '.join(missing_required)}")

        # 6. 数据来源标注可追溯性
        if source_count > 0:
            traceability = "有"
        else:
            traceability = "无"

        passed = len(issues) == 0
        return {
            "passed": passed,
            "keyword_score": keyword_score,
            "reasoning_score": reasoning_score,
            "reasoning_detail": reasoning_result,
            "source_count": source_count,
            "evidence_min_required": min_sources,
            "traceability": traceability,
            "issues": issues,
            "found_terms": found_terms,
            "missing_required": missing_required,
        }

    # ── 辅助方法 ──────────────────────────────────────────────────────────

    def _locate_dimension_text(self, text: str, dim_id: str, check_terms: set, required: list) -> list[str]:
        """定位文本中属于特定维度的段落。

        策略：找到包含 required_elements 或检查关键词的段落，
        提取其前后各一段作为该维度的分析上下文。
        """
        paragraphs = text.split("\n\n")
        dim_paragraphs = []

        search_terms = set(check_terms)
        if required:
            search_terms.update(required)
        if dim_id:
            search_terms.add(dim_id)

        for i, para in enumerate(paragraphs):
            if any(term in para for term in search_terms):
                # 包含该段落及前后各一段
                start = max(0, i - 1)
                end = min(len(paragraphs), i + 2)
                dim_paragraphs.extend(paragraphs[start:end])

        return dim_paragraphs

    def _check_reasoning_chain(self, text: str) -> dict[str, Any]:
        """检查推理链完整性。

        基于五个维度的因果连接词模式：
        - causal_forward: 因为、由于、源于
        - causal_backward: 因此、所以、从而导致
        - conclusion: 综上所述、可见
        - conditional: 如果、假设
        - contrast: 然而、但是

        完整推理链至少需要 3 类模式出现。
        """
        if not text or len(text.strip()) < 50:
            # 文本太短无法评估推理链
            return {
                "score": 0.0,
                "categories_found": [],
                "categories_total": len(self.REASONING_PATTERNS),
                "total_matches": 0,
            }

        categories_found = []
        total_matches = 0

        for category, patterns in self.REASONING_PATTERNS.items():
            matches = 0
            for pat in patterns:
                matches += len(re.findall(pat, text))
            if matches > 0:
                categories_found.append(category)
                total_matches += matches

        found = len(categories_found)
        total = len(self.REASONING_PATTERNS)

        # 评分：至少覆盖 3 类模式，且有足够的连接词密度
        coverage_score = found / total
        density_score = min(total_matches / 20, 1.0)  # 每 20 个连接词得满分

        score = coverage_score * 0.6 + density_score * 0.4
        score = max(0.0, min(1.0, score))

        return {
            "score": score,
            "categories_found": categories_found,
            "categories_total": total,
            "total_matches": total_matches,
        }

    def _fallback_dimension_ids(self) -> list[str]:
        """SAC 加载失败时的兜底维度列表。"""
        fallback = {
            "industry_deep": [
                "bold_call",
                "core_disagreement",
                "industry_boundary",
                "life_cycle",
                "policy",
                "market_size",
                "supply_demand",
                "profit_pool",
                "competitive",
                "technology",
                "capital_market",
            ],
            "listed_company": [
                "core_disagreement",
                "business_model",
                "financial_analysis",
                "competitive_position",
                "growth_drivers",
                "governance_esg",
                "valuation_assessment",
                "falsification",
                "catalyst",
            ],
            "unlisted_company": [
                "data_declaration",
                "company_profile",
                "funding_history",
                "business_kpi",
                "competitive_moat",
                "valuation_estimate",
                "exit_analysis",
                "due_diligence",
                "falsification",
            ],
            "earnings_notes": [
                "headline",
                "key_surprise",
                "segment_analysis",
                "balance_cashflow",
                "outlook_implication",
            ],
        }
        return fallback.get(self.report_type, fallback["industry_deep"])


# ── CLI 入口 ──────────────────────────────────────────────────────────────


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="2hao-analyst ProbabilisticDeepCheck")
    parser.add_argument("report_path", help="报告文件路径")
    parser.add_argument(
        "--type",
        default="industry_deep",
        choices=[
            "industry_deep",
            "listed_company",
            "unlisted_company",
            "earnings_notes",
        ],
    )
    parser.add_argument("--probability", type=float, default=0.20, help="概率性触发概率 (0.0-1.0)")
    parser.add_argument("--seed", type=int, help="随机种子（可复现测试用）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--force-deep", action="store_true", help="强制触发深度检查（忽略概率）")
    args = parser.parse_args()

    try:
        text = Path(args.report_path).read_text(encoding="utf-8")
    except Exception as e:
        print(f"读取文件失败: {e}")
        return 1

    checker = ProbabilisticDeepCheck(
        report_type=args.type,
        trigger_probability=1.0 if args.force_deep else args.probability,
        random_seed=args.seed,
    )

    result = checker.check(text)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(checker.get_feedback(result))

    # 非零退出码标记未通过
    return 0 if result.get("overall_passed", False) else 1


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.exit(main())
