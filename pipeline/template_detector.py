"""
pipeline/template_detector.py — 模板重复检测器

消除模板重复问题：
1. 模板重复检测
2. 模板去重
3. 模板替换
4. 模板监控
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.template_detector")

_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class TemplateMatch:
    """模板匹配"""

    template_id: str
    template_text: str
    match_count: int = 0
    match_positions: list[int] = field(default_factory=list)
    severity: str = "warning"  # warning/error


@dataclass
class DetectionReport:
    """检测报告"""

    total_templates: int = 0
    matched_templates: int = 0
    duplicate_rate: float = 0.0
    matches: list[TemplateMatch] = field(default_factory=list)
    overall_score: float = 0.0


class TemplateDetector:
    """
    模板重复检测器

    核心机制：
    1. 模板重复检测
    2. 模板去重
    3. 模板替换
    4. 模板监控
    """

    def __init__(self, templates_path: Optional[str] = None):
        """
        Args:
            templates_path: 模板文件路径
        """
        self.templates_path = templates_path or str(_ROOT / "data" / "template_blacklist.json")
        self._templates = self._load_templates()

    def _load_templates(self) -> list[str]:
        """加载模板"""
        import json

        try:
            path = Path(self.templates_path)
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("templates", [])
        except Exception as e:
            logger.warning("[TEMPLATE-DETECTOR] Failed to load templates: %s", e)

        # 默认模板
        return [
            "值得注意的是",
            "综上所述",
            "不可否认",
            "众所周知",
            "显而易见",
            "毫无疑问",
            "从本质上讲",
            "总的来说",
            "总而言之",
            "简而言之",
        ]

    def detect(self, text: str) -> DetectionReport:
        """
        检测模板重复

        Args:
            text: 报告文本

        Returns:
            DetectionReport: 检测报告
        """
        report = DetectionReport()
        report.total_templates = len(self._templates)

        for template in self._templates:
            match = self._detect_template(text, template)
            if match.match_count > 0:
                report.matches.append(match)
                report.matched_templates += 1

        report.duplicate_rate = report.matched_templates / report.total_templates if report.total_templates > 0 else 0.0

        # 计算整体分数（越低越好）
        if report.matches:
            total_matches = sum(m.match_count for m in report.matches)
            report.overall_score = max(0.0, 1.0 - (total_matches * 0.1))
        else:
            report.overall_score = 1.0

        return report

    def _detect_template(self, text: str, template: str) -> TemplateMatch:
        """检测单个模板"""
        match = TemplateMatch(
            template_id=template[:20],
            template_text=template,
        )

        # 查找所有匹配位置
        start = 0
        while True:
            pos = text.find(template, start)
            if pos == -1:
                break
            match.match_positions.append(pos)
            match.match_count += 1
            start = pos + len(template)

        # 判断严重程度
        if match.match_count >= 3:
            match.severity = "error"
        elif match.match_count >= 2:
            match.severity = "warning"
        else:
            match.severity = "info"

        return match

    def validate(self, report: DetectionReport) -> bool:
        """
        验证检测结果

        Args:
            report: 检测报告

        Returns:
            bool: 是否通过
        """
        # 检查重复率
        if report.duplicate_rate > 0.3:  # 30% 阈值
            logger.warning(
                "[TEMPLATE-DETECTOR] Duplicate rate %.2f > 0.3",
                report.duplicate_rate,
            )
            return False

        # 检查严重匹配
        error_matches = [m for m in report.matches if m.severity == "error"]
        if error_matches:
            logger.warning(
                "[TEMPLATE-DETECTOR] Found %d error-level matches",
                len(error_matches),
            )
            return False

        return True

    def suggest_fixes(self, report: DetectionReport) -> list[str]:
        """
        建议修复

        Args:
            report: 检测报告

        Returns:
            list[str]: 修复建议
        """
        suggestions = []

        for match in report.matches:
            if match.severity in ("error", "warning"):
                suggestions.append(f"模板 '{match.template_text}' 出现 {match.match_count} 次，建议替换或删除")

        return suggestions

    def remove_templates(self, text: str) -> str:
        """
        移除模板

        Args:
            text: 报告文本

        Returns:
            str: 处理后的文本
        """
        result = text

        for template in self._templates:
            # 替换为更自然的表达
            replacements = {
                "值得注意的是": "需要关注的是",
                "综上所述": "综合来看",
                "不可否认": "确实",
                "众所周知": "如我们所知",
                "显而易见": "可以看出",
                "毫无疑问": "确实",
                "从本质上讲": "从根本上说",
                "总的来说": "整体而言",
                "总而言之": "综合来看",
                "简而言之": "简单来说",
            }

            replacement = replacements.get(template, "")
            if replacement:
                result = result.replace(template, replacement)

        return result
