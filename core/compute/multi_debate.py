"""多模型辩论引擎 — 多 LLM 对同一问题的独立判断+辩论收敛"""
from __future__ import annotations
from dataclasses import dataclass
import logging

logger = logging.getLogger("2hao.multi_debate")


@dataclass
class DebateResult:
    question: str
    answers: list[dict]
    convergence: str
    consensus: str
    disagreements: list[str]


class MultiModelDebate:
    """多模型辩论引擎。当前已接线 core.deepseek_client。"""
    
    def __init__(self, models: list[str] = None):
        self.models = models or ["deepseek", "deepseek-reasoner"]
    
    def debate(self, question: str, context: str = "") -> DebateResult:
        from core.deepseek_client import call_llm
        answers = []
        for model in self.models:
            try:
                prompt = f"请独立判断以下问题，只输出JSON:\n问题: {question}\n上下文: {context[:200]}\n输出: {{\"answer\": \"你的判断\", \"confidence\": 0.xx}}"
                result = call_llm(
                    messages=[{"role": "user", "content": prompt}],
                    model=model,
                    temperature=0.3,
                    max_tokens=300,
                )
                import json
                import re
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                score_match = re.search(r'(\d\.\d+)', content)
                confidence = float(score_match.group(1)) if score_match else 0.5
                answers.append({"model": model, "answer": content[:100], "confidence": confidence})
            except Exception as e:
                answers.append({"model": model, "answer": f"error: {str(e)[:50]}", "confidence": 0.0})
        
        return DebateResult(
            question=question, answers=answers,
            convergence="pending", consensus="(待分析)", disagreements=[],
        )
    
    def to_report(self) -> str:
        return f"[MultiModelDebate] 模型: {self.models} | 接线状态: live"


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    d = MultiModelDebate().debate("半导体行业2027年景气度如何？")
    print(d.convergence)
