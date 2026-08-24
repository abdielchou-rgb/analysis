"""
hypothesis_checker.py - T0.5 hypothesis validation layer.
Before entering the full pipeline, test if an investment thesis is worth pursuing.
"""
import json, logging, re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("2hao.hypothesis")

_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class HypothesisResult:
    """Result of hypothesis checking"""
    asset: str = ""
    hypothesis: str = ""
    passes_gate: bool = False
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    suggested_direction: str = "neutral"
    confidence: float = 0.0


class HypothesisChecker:
    """Check if an investment hypothesis is worth pursuing"""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from core.deepseek_client import DeepSeekClient
                self._client = DeepSeekClient()
            except Exception:
                return None
        return self._client

    def check(self, asset: str, hypothesis: str = "",
              context: str = "", threshold: float = 0.6,
              block_on_fail: bool = False) -> HypothesisResult:
        """Check a hypothesis. block_on_fail=True will add blocking risks if score < threshold"""
        result = self._check_internal(asset, hypothesis, context, threshold)
        if block_on_fail and not result.passes_gate:
            result.risks.append("BLOCKING: Hypothesis failed gate - score={:.1f} < threshold={:.1f}".format(result.score, threshold))
            result.risks.append("建议: 重新审视假说或收集更多数据后再试")
        return result

    def _check_internal(self, asset: str, hypothesis: str,
                        context: str, threshold: float) -> HypothesisResult:
        """Check a hypothesis using DeepSeek + data validation"""
        client = self._get_client()
        if not client:
            return self._check_rule_based(asset, hypothesis, context)

        prompt = f"""你是一位资深投资分析师。请评估以下投资假说的质量。

标的: {asset}
假说: {hypothesis or "无明确假说，全面扫描"}
上下文: {context[:2000]}

请从以下维度评分（0-10分）：
1. 假说是否具体、可证伪
2. 是否有明确的市场共识分歧点
3. 是否有数据/逻辑支撑
4. 是否有明确的风险点
5. 时间窗口是否清晰

输出JSON:
{{
    "score": 0-10,
    "passes_gate": true/false (score >= {threshold*10}为通过),
    "reasons": ["理由1", "理由2"],
    "risks": ["风险1", "风险2"],
    "suggested_direction": "bullish/bearish/neutral",
    "confidence": 0.0-1.0
}}"""

        try:
            response = client.chat(prompt, temperature=0.3)
            if response:
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    return HypothesisResult(
                        asset=asset,
                        hypothesis=hypothesis,
                        passes_gate=data.get("passes_gate", False),
                        score=data.get("score", 0) / 10.0,
                        reasons=data.get("reasons", []),
                        risks=data.get("risks", []),
                        suggested_direction=data.get("suggested_direction", "neutral"),
                        confidence=data.get("confidence", 0.0),
                    )
        except Exception as e:
            logger.debug("DeepSeek hypothesis check failed: %s", e)

        return self._check_rule_based(asset, hypothesis, context)

    def _check_rule_based(self, asset: str, hypothesis: str,
                          context: str) -> HypothesisResult:
        """Rule-based fallback"""
        score = 0.3  # Default low score
        reasons = []
        risks = []

        if hypothesis and len(hypothesis) > 10:
            score += 0.2
            reasons.append("假说明确")

        if context and len(context) > 100:
            score += 0.2
            reasons.append("有上下文支撑")

        # Check for direction keywords
        direction = "neutral"
        if any(w in (hypothesis + context).lower() for w in ["增长", "突破", "机会", "优势"]):
            direction = "bullish"
            score += 0.1
        if any(w in (hypothesis + context).lower() for w in ["风险", "下降", "挑战", "衰退"]):
            direction = "bearish"
            score += 0.1

        if score < 0.4:
            risks.append("假说不够具体")
            risks.append("缺少数据支撑")

        return HypothesisResult(
            asset=asset,
            hypothesis=hypothesis,
            passes_gate=score >= 0.5,
            score=min(score, 1.0),
            reasons=reasons,
            risks=risks,
            suggested_direction=direction,
            confidence=score,
        )

    def suggest_report_type(self, asset: str, context: str = "") -> str:
        """Suggest which report type is most appropriate"""
        client = self._get_client()
        if client:
            prompt = f"""根据以下标的和上下文，推荐最合适的报告类型。

标的: {asset}
上下文: {context[:1500]}

选项：
1. industry_deep - 行业深度研究（适用于行业性机会）
2. listed_company - 上市公司深度（适用于已上市公司）
3. unlisted_company - 非上市公司分析（适用于未上市公司）
4. earnings_notes - 财报点评（适用于财报季）

输出JSON: {{"report_type": "xxx", "reason": "原因"}}"""
            try:
                response = client.chat(prompt, temperature=0.2)
                if response:
                    jm = re.search(r"\{.*\}", response, re.DOTALL)
                    if jm:
                        return json.loads(jm.group()).get("report_type", "industry_deep")
            except Exception:
                pass
        return "industry_deep"


__all__ = ["HypothesisChecker", "HypothesisResult"]
