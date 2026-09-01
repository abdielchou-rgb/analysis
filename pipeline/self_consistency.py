"""
Self-Consistency — 多次采样取一致结果

基于 SelfCheckGPT (2023) 和 arXiv:2604.13717 (Composo AI, 2026)：
- 多次采样同一prompt，检查输出一致性
- 一致的输出置信度高，不一致的输出置信度低
- 用于验证关键事实和判断的准确性
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.self_consistency")


@dataclass
class ConsistencyResult:
    """一致性评估结果"""

    claim: str
    samples: list[str]
    consistency_score: float  # 0.0 - 1.0
    passed: bool
    details: str
    variations: list[str] = field(default_factory=list)


class SelfConsistency:
    """自一致性检查器"""

    def __init__(self, report_type: str = "unlisted_company"):
        self.report_type = report_type
        self._thresholds = {
            "unlisted_company": {
                "fact_consistency": 0.7,  # 事实一致性阈值
                "judgment_consistency": 0.6,  # 判断一致性阈值
                "min_samples": 3,  # 最少采样次数
            },
            "listed_company": {
                "fact_consistency": 0.75,
                "judgment_consistency": 0.65,
                "min_samples": 3,
            },
            "industry_deep": {
                "fact_consistency": 0.7,
                "judgment_consistency": 0.6,
                "min_samples": 3,
            },
        }
        self._thresholds = self._thresholds.get(report_type, self._thresholds["unlisted_company"])

    def extract_claims(self, text: str) -> list[dict]:
        """提取报告中的关键声明"""
        claims = []

        # 1. 事实性声明（数字+单位）
        fact_patterns = [
            r"(\d+(?:\.\d+)?\s*(?:%|亿元|亿|倍|万股|元|万吨|万台))[^，。]*?[，。]",
            r"(?:营收|利润|毛利率|增速|份额|市占率)[^，。]*?(\d+(?:\.\d+)?(?:%|亿元|亿))[^，。]*?[，。]",
        ]

        for pattern in fact_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # 提取上下文
                idx = text.find(match)
                start = max(0, idx - 100)
                end = min(len(text), idx + len(match) + 100)
                context = text[start:end]
                claims.append(
                    {
                        "type": "fact",
                        "claim": match,
                        "context": context,
                    }
                )

        # 2. 判断性声明
        judgment_patterns = [
            r"我们判断[^，。]*?[，。]",
            r"我们认为[^，。]*?[，。]",
            r"预计[^，。]*?[，。]",
            r"有望[^，。]*?[，。]",
        ]

        for pattern in judgment_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                claims.append(
                    {
                        "type": "judgment",
                        "claim": match,
                        "context": match,
                    }
                )

        return claims

    def check_consistency(self, claim: str, samples: list[str]) -> ConsistencyResult:
        """检查单个声明的一致性"""
        if len(samples) < 2:
            return ConsistencyResult(
                claim=claim,
                samples=samples,
                consistency_score=0.5,
                passed=True,
                details="采样数不足，跳过检查",
            )

        # 提取声明中的关键信息
        key_info = self._extract_key_info(claim)

        # 检查每个样本是否包含相同的关键信息
        consistent_count = 0
        variations = []

        for sample in samples:
            sample_info = self._extract_key_info(sample)
            if self._info_matches(key_info, sample_info):
                consistent_count += 1
            else:
                variations.append(sample[:100])

        # 计算一致性分数
        consistency_score = consistent_count / len(samples)

        # 判断是否通过
        threshold = self._thresholds["fact_consistency"]
        passed = consistency_score >= threshold

        return ConsistencyResult(
            claim=claim,
            samples=samples,
            consistency_score=consistency_score,
            passed=passed,
            details=f"一致性: {consistency_score:.2f} (阈值: {threshold})",
            variations=variations,
        )

    def _extract_key_info(self, text: str) -> dict:
        """提取文本中的关键信息"""
        info = {}

        # 提取数字
        numbers = re.findall(r"\d+(?:\.\d+)?", text)
        info["numbers"] = numbers

        # 提取单位
        units = re.findall(r"(?:%|亿元|亿|倍|万股|元|万吨|万台)", text)
        info["units"] = units

        # 提取关键词
        keywords = re.findall(r"(?:营收|利润|毛利率|增速|份额|市占率|预计|有望|判断)", text)
        info["keywords"] = keywords

        return info

    def _info_matches(self, info1: dict, info2: dict) -> bool:
        """检查两个信息是否匹配"""
        # 检查数字是否一致
        if info1.get("numbers") and info2.get("numbers"):
            # 允许微小差异（<5%）
            for n1 in info1["numbers"]:
                for n2 in info2["numbers"]:
                    try:
                        v1 = float(n1)
                        v2 = float(n2)
                        if abs(v1 - v2) / max(v1, v2) < 0.05:
                            return True
                    except ValueError:
                        pass

        # 检查关键词是否一致
        if info1.get("keywords") and info2.get("keywords"):
            common = set(info1["keywords"]) & set(info2["keywords"])
            if len(common) > 0:
                return True

        return False

    def generate_samples(self, prompt: str, n_samples: int = 3, provider: str = None) -> list[str]:
        """生成多个样本（实际应用中调用LLM）"""
        # 简化版：实际应用中应该调用LLM生成多个样本
        # 这里返回空列表，表示需要外部实现
        logger.warning("[SELF_CONSISTANCE] generate_samples 需要外部LLM实现")
        return []

    def check_report(self, report_text: str, n_samples: int = 3) -> list[ConsistencyResult]:
        """检查整个报告的一致性"""
        claims = self.extract_claims(report_text)
        results = []

        for claim_info in claims[:10]:  # 最多检查10个声明
            claim = claim_info["claim"]

            # 生成多个样本（实际应用中应该调用LLM）
            # 这里简化处理：使用原文作为单个样本
            samples = [claim]  # 实际应该是多个LLM输出

            # 检查一致性
            result = self.check_consistency(claim, samples)
            results.append(result)

        return results

    def should_rewrite(self, results: list[ConsistencyResult]) -> tuple[bool, str]:
        """判断是否需要重写"""
        if not results:
            return False, "无检查结果"

        # 检查失败的声明
        failed = [r for r in results if not r.passed]

        if not failed:
            return False, "所有声明一致性通过"

        # 检查失败比例
        failed_ratio = len(failed) / len(results)

        if failed_ratio > 0.3:
            return True, f"失败声明过多: {failed_ratio:.0%}"

        # 检查关键声明失败
        critical_claims = [r for r in failed if "关键" in r.claim or "核心" in r.claim]
        if critical_claims:
            return True, f"关键声明不一致: {[r.claim[:30] for r in critical_claims]}"

        return False, "非关键声明不一致，可接受"


def self_consistency_prompt(results: list[ConsistencyResult]) -> str:
    """生成自一致性反馈prompt"""
    failed = [r for r in results if not r.passed]

    if not failed:
        return ""

    lines = [
        "## [自一致性检查反馈] 以下声明不一致，请修正：",
        "",
    ]

    for r in failed:
        lines.append(f"### 声明: {r.claim[:50]}...")
        lines.append(f"- 一致性分数: {r.consistency_score:.2f}")
        lines.append(f"- 变体: {r.variations[:2] if r.variations else '无'}")
        lines.append("- 建议: 确保数据准确，来源标注清晰")
        lines.append("")

    return "\n".join(lines)
