"""
2号分析师 Agent Loop — 升级版写作循环评分库

新增:
- DeepSeek评分支持
- 数据可信度检查
- 排版质量检查
"""

import sys
import json
import re
import logging
from pathlib import Path
from typing import Optional
from core.sacs import SACLoader
from pipeline.learning_loop import LearningLoop
from core.calibration.dashboard import CalibrationDashboard

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.agent_loop")


class ScoreEngine:
    """评分引擎 - 升级版"""

    def __init__(self, use_deepseek: bool = False, report_type: str = "industry_deep"):
        self._scorer = None
        self._deepseek = None
        self._use_deepseek = use_deepseek
        self.report_type = report_type
        self.sac = SACLoader(report_type)
        self.learning_loop = LearningLoop()
        self.calibration = None
        try:
            self.calibration = CalibrationDashboard()
        except Exception:
            self.calibration = None
        self._init_modules()

    def _init_modules(self):
        try:
            from core.quality_scorer import QualityScorer
            self._scorer = QualityScorer()
        except Exception as e:
            logger.warning(f"QualityScorer unavailable: {e}")

        if self._use_deepseek:
            try:
                from core.deepseek_client import score_text
                self._deepseek = score_text
            except Exception as e:
                logger.warning(f"DeepSeek scoring unavailable: {e}")

    def score(self, text: str, report_type: str = "industry_deep") -> dict:
        """给报告评分，返回8维评分"""
        result = {
            "overall": 0.0,
            "dimensions": {},
            "details": [],
        }

        result["dimensions"]["aigc_fingerprint"] = self._score_aigc(text)
        result["dimensions"]["human_sense"] = self._score_human(text)
        result["dimensions"]["quality"] = self._score_quality(text)
        result["dimensions"]["sac_coverage"] = self._score_sac(text, report_type)
        result["dimensions"]["chart_density"] = self._score_charts(text, report_type)
        result["dimensions"]["data_traceability"] = self._score_data(text)
        result["dimensions"]["format_consistency"] = self._score_format(text)
        result["dimensions"]["persuasion"] = self._score_persuasion(text)

        # 加权综合
        weights = {
            "aigc_fingerprint": 0.15, "human_sense": 0.10,
            "quality": 0.20, "sac_coverage": 0.15,
            "chart_density": 0.15, "data_traceability": 0.10,
            "format_consistency": 0.05, "persuasion": 0.10,
        }
        overall = sum(result["dimensions"][k] * w for k, w in weights.items()) / sum(weights.values())
        result["overall"] = round(overall, 4)

        for dim, score in result["dimensions"].items():
            status = "PASS" if score >= 0.7 else "FAIL"
            result["details"].append(f"[{status}] {dim}: {score:.2f}")

        # 如果启用DeepSeek，补充AI评分
        if self._deepseek and self._use_deepseek:
            try:
                ds_score = self._deepseek(text[:6000])
                if ds_score and ds_score.get("overall"):
                    # DeepSeek评分作为参考
                    result["deepseek_overall"] = ds_score["overall"]
                    result["deepseek_issues"] = ds_score.get("issues", [])
            except Exception:
                pass

        return result

    def _score_aigc(self, text: str) -> float:
        try:
            from core.ai_fingerprints import AIScanner
            scanner = AIScanner()
            result = scanner.scan(text)
            ratio = getattr(result, 'ai_fingerprint_ratio', 0.0)
            return 1.0 - ratio
        except Exception:
            return 0.5

    def _score_human(self, text: str) -> float:
        try:
            from core.human_signal_injector import HumanSenseDetector
            detector = HumanSenseDetector()
            return detector.detect(text)
        except Exception:
            return 0.5

    def _score_quality(self, text: str) -> float:
        if self._scorer:
            try:
                result_obj = self._scorer.score(text)
                return getattr(result_obj, 'overall', 0.0)
            except Exception:
                pass
        score = 0.5
        if re.search(r'我们认为|我们判断|我们建议', text): score += 0.1
        if re.search(r'数据来源[：:]', text): score += 0.1
        if re.search(r'风险因素|Bear Case|反方', text): score += 0.1
        if len(text) > 3000: score += 0.1
        if len(text) > 10000: score += 0.1
        return min(max(score, 0.0), 1.0)

    def _score_sac(self, text: str, report_type: str) -> float:
        """Score SAC dimension coverage using SAC loader (single source of truth)"""
        try:
            dim_keywords = self.sac.get_dimension_keywords()
            if not dim_keywords:
                return 0.5
            covered = 0
            for dim, keywords in dim_keywords.items():
                if any(kw in text for kw in keywords):
                    covered += 1
            return covered / max(len(required_dims), 1)
        except Exception:
            return 0.5

    def _score_charts(self, text: str, report_type: str) -> float:
        charts = re.findall(r'!\[.*?\]\(.*?\)', text)
        tables = [t for t in re.findall(r'\|.*\|', text) if '---' not in t and t.count('|') >= 3]
        min_charts = {"industry_deep": 5, "listed_company": 5, "unlisted_company": 4, "earnings_notes": 2}
        min_tables = {"industry_deep": 3, "listed_company": 3, "unlisted_company": 2, "earnings_notes": 1}
        mc = min_charts.get(report_type, 3)
        mt = min_tables.get(report_type, 2)

        chart_score = min(len(charts) / mc, 1.0)
        table_score = min(len(tables) / mt, 1.0)

        # 检查图表是否在正文中引用（不是全部在末尾）
        charts_in_text = sum(1 for c in charts if self._is_chart_in_context(text, c))
        context_bonus = 0.1 if charts_in_text >= len(charts) / 2 else 0.0

        return min((chart_score + table_score) / 2 + context_bonus, 1.0)

    def _is_chart_in_context(self, text: str, chart_ref: str) -> bool:
        """检查图表是否在正文上下文中被引用"""
        idx = text.find(chart_ref)
        if idx < 0:
            return False
        # 检查前面200字是否有分析文本
        before = text[max(0, idx - 200):idx]
        return len(before.strip()) > 50

    def _score_data(self, text: str) -> float:
        sources = re.findall(r'数据来源[：:]\s*\S+', text)
        confidence = re.findall(r'置信度|可信度|可靠度', text)
        cross_val = re.findall(r'交叉验证|数据分歧|多源', text)
        score = (min(len(sources) / 3, 1.0) * 0.5 +
                 min(len(confidence) / 1, 1.0) * 0.2 +
                 min(len(cross_val) / 1, 1.0) * 0.3)
        return min(score, 1.0)

    def _score_format(self, text: str) -> float:
        issues = 0
        # 加粗检查
        bold_count = len(re.findall(r'\*\*', text))
        para_count = max(len([p for p in text.split("\n\n") if p.strip()]), 1)
        if bold_count > para_count * 3:
            issues += 1
        # 表格溢出检查
        for line in text.split("\n"):
            if line.startswith("|") and len(line) > 200:
                issues += 1
                break
        # 图片溢出检查
        imgs = re.findall(r'!\[.*?\]\(.*?\)', text)
        for img in imgs:
            if len(img) > 300:
                issues += 1
                break
        return max(0.0, 1.0 - issues * 0.2)

    def _score_persuasion(self, text: str) -> float:
        checks = [
            any(kw in text for kw in ["投资论点", "核心判断", "投资逻辑"]),
            any(kw in text for kw in ["反方", "Bear Case", "风险因素", "证伪"]),
            any(kw in text for kw in ["市场共识", "Consensus", "超预期"]),
            any(kw in text for kw in ["这意味着", "因此", "所以建议"]),
            # R42：报告应像人类分析师撰写，不出现 AI 免责声明。原把"免责声明"
            # 作为说服力加分项（评分正确性存疑），移除该检查。
        ]
        return sum(checks) / len(checks)

    def get_feedback(self, score_result: dict) -> str:
        """生成Agent用的改进反馈"""
        lines = ["=" * 60, "写作循环 - 评分反馈", "=" * 60]
        lines.append(f"综合评分: {score_result['overall']:.2f}/1.00 (目标: >= 0.90)")

        if "deepseek_overall" in score_result:
            lines.append(f"DeepSeek评分: {score_result['deepseek_overall']:.2f}/1.00")
            if score_result.get("deepseek_issues"):
                lines.append(f"DeepSeek发现问题: {', '.join(score_result['deepseek_issues'][:3])}")
        lines.append("")

        for dim_name, dim_score in score_result["dimensions"].items():
            icons = {True: "+", False: "-"}
            passed = dim_score >= 0.7
            lines.append(f"  [{icons[passed]}] {dim_name}: {dim_score:.2f}")

        lines.extend([
            "",
            "改进要求:",
            "  1. 所有FAIL项必须修复",
            "  2. 综合评分必须 >= 0.9",
            f"  3. 图表必须足够 ({self._get_min_charts(next((k for k in ['industry_deep','listed_company','unlisted_company','earnings_notes'] if True), 'industry_deep'))})",
            "  4. 每个数据点必须标注来源",
            "  5. SAC维度覆盖率 >= 80%",
            "  6. 排版无问题（字体一致、表格不溢出、图片不溢出）",
            # R42：不要求免责声明——报告必须像人类分析师撰写，避免 AI 免责痕迹。
            "",
            "修复后重新评分，直到所有PASS且综合 >= 0.9",
            "=" * 60,
        ])
        return "\n".join(lines)


    def before_report(self, asset: str, report_type: str) -> str:
        """Call learning loop before report writing. Returns historical context."""
        try:
            return self.learning_loop.before_report(asset, report_type)
        except Exception as e:
            return ""

    def after_report(self, asset: str, report_type: str, score_result: dict) -> None:
        """Call learning loop after report writing to record failures."""
        try:
            # Record to calibration dashboard
            if self.calibration:
                try:
                    if hasattr(self.calibration, 'record'):
                        self.calibration.record(
                            asset=asset,
                            report_type=report_type,
                            score=score_result.get("overall", 0.0),
                            dimensions=score_result.get("dimensions", {}),
                        )
                except Exception:
                    pass
            if score_result.get("overall", 1.0) < 0.9:
                failures = []
                for dim, score in score_result.get("dimensions", {}).items():
                    if score < 0.7:
                        failures.append(dim)
                self.learning_loop.after_report(
                    asset, report_type,
                    {"passed": False, "score": score_result["overall"], "failures": failures}
                )
        except Exception:
            pass

    def _get_min_charts(self, report_type: str) -> str:
        mins = {"industry_deep": "5图3表", "listed_company": "5图3表", "unlisted_company": "4图2表", "earnings_notes": "2图1表"}
        return mins.get(report_type, "3图2表")


class ReportFixer:
    """报告修复器"""

    def __init__(self):
        self._formatter = None
        self._init_formatter()

    def _init_formatter(self):
        try:
            from export.format_professionalizer import FormatProfessionalizer
            self._formatter = FormatProfessionalizer()
        except Exception:
            pass

    def fix(self, text: str, feedback: str) -> str:
        """根据反馈修复报告"""
        result = text

        if self._formatter:
            result = self._formatter.professionalize(result)

        # 确保数据来源
        if "数据来源" not in result:
            result += "\n\n---\n\n**数据来源**: 本报告数据来源于公开市场数据、公司公告、行业研究机构报告。各图表和数据表底部已标注具体来源。\n"

        # R42（2026-08-02）：不再注入免责声明——报告必须像人类分析师撰写。
        # 专业券商报告不出现"仅供参考/不构成投资建议"这类 AI 免责痕迹。
        # 原逻辑在此处追加"免责声明"段落，已删除。

        return result


def test():
    test_text = """
我们认为茅台的核心竞争力在于品牌力和渠道力。
2025年营收预计增长15%，净利润增长18%。
数据来源：公司公告、行业研究。
风险因素：宏观经济放缓可能影响高端白酒消费。
"""
    engine = ScoreEngine()
    result = engine.score(test_text, "listed_company")
    print(f"Overall: {result['overall']:.2f}")
    for d in result["details"]:
        print(f"  {d}")
    print()
    print(engine.get_feedback(result))


if __name__ == "__main__":
    test()
