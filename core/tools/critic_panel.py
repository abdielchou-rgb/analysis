# -*- coding: utf-8 -*-
# Critic Panel - Multi-role review cluster
# Codex generated - 2026-07-30

from __future__ import annotations
import json, logging, re, time, os
from dataclasses import dataclass, field
from pathlib import Path as PPath
from collections import Counter

_ROOT = PPath(__file__).resolve().parent.parent.parent
import sys
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.deepseek_client import call_llm
logger = logging.getLogger("2hao.critic_panel")


@dataclass
class CriticRole:
    role_id: str = ""
    role_name: str = ""
    focus: list = field(default_factory=list)
    system_prompt: str = ""
    weight: float = 1.0


@dataclass
class CriticScore:
    dimension: str = ""
    score: float = 0.0
    passed: bool = False
    comment: str = ""
    severity: str = "info"


@dataclass
class CriticVerdict:
    role_id: str = ""
    role_name: str = ""
    overall_score: float = 0.0
    passed: bool = False
    dimension_scores: list = field(default_factory=list)
    strengths: list = field(default_factory=list)
    weaknesses: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return dict(role_id=self.role_id, role_name=self.role_name,
                    overall_score=self.overall_score, passed=self.passed,
                    strengths=self.strengths[:3], weaknesses=self.weaknesses[:3])


@dataclass
class ConsensusReport:
    final_score: float = 0.0
    passed: bool = False
    verdicts: list = field(default_factory=list)
    consensus_strengths: list = field(default_factory=list)
    consensus_weaknesses: list = field(default_factory=list)
    top_suggestions: list = field(default_factory=list)
    disagreement_areas: list = field(default_factory=list)
    duration_ms: float = 0.0

    def summary(self) -> str:
        out = [f"SCORE: {self.final_score:.2f}  PASSED: {self.passed}"]
        for v in self.verdicts:
            icon = "+" if v.passed else "-"
            out.append(f"  [{icon}] {v.role_name}: {v.overall_score:.2f}")
        for s in self.top_suggestions[:5]:
            out.append(f"  - {s}")
        return chr(10).join(out)

    def to_dict(self) -> dict:
        return dict(final_score=round(self.final_score, 2), passed=self.passed,
                    verdicts=[v.to_dict() for v in self.verdicts],
                    top_suggestions=self.top_suggestions[:8])


def _extract_json(text):
    """Extract JSON from LLM response."""
    import re, json
    m = re.search(r"```(?:json)?\n?(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


# ---- Role Definitions ----

IB_PROMPT = '''You are a senior investment banking research director
with 20 years at Goldman Sachs or Morgan Stanley.
Evaluate the report on: data provenance, valuation framework,
bold call quality, peer benchmarking, risk management.
Be strict. Score each dimension 0.0-1.0.
Return JSON: {overall_score, passed, dimensions: [{dimension, score, passed, comment, severity}], strengths, weaknesses, suggestions}
'''

PE_PROMPT = '''You are a managing partner at a top PE firm
(Sequoia, Hillhouse, KKR) with 15 years experience.
Evaluate: business model, moat, scalability, capital efficiency, management.
Return JSON.'''

MBB_PROMPT = '''You are a McKinsey/BCG/Bain strategy consultant
with 12 years experience. Evaluate: methodology, framework integrity,
logical flow, argument depth, counter-argument quality.
Return JSON.'''

BIG4_PROMPT = '''You are a Big 4 audit partner with 18 years experience.
Evaluate: compliance, audit trail, data fidelity, accounting quality, disclosure.
Return JSON.'''

CS_PROMPT = '''You are a chief strategist at a top Chinese brokerage
(CICC, CITIC) with 15 years experience.
Evaluate: regulation, market context, policy transmission, client fit.
Return JSON.'''


class CriticAgent:
    """Single critic role evaluator."""

    def __init__(self, role):
        self.role = role

    def evaluate(self, report_text, prompts, context=None):
        t0 = time.time()
        if context is None:
            context = {}
        prompt = self.role.system_prompt or prompts.get(self.role.role_id, '')
        user_msg = f"""Evaluate this report as {self.role.role_name}.
Focus on: {', '.join(self.role.focus)}

Report (first 6000 chars):
{report_text[:6000]}

Return strict JSON with overall_score, passed, dimensions, strengths, weaknesses, suggestions.
"""

        try:
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg},
            ]
            # R13（2026-08-01 三算力架构）：critic 分两档 —— 前 3 席高价值走 DeepSeek 保质量，
            # 后 2 席冗余评审可经 CRITIC_LOCAL=1 路由到本地 Ollama 提速（需先验证偏差<5%）。
            # P3-1（2026-08-07）异源圆桌：CRITIC_HETEROSOURCE=1 时走 OpenRouter——
            # 与 DeepSeek 不同源，防同源偏差（Marvis 方案：终局圆桌至少 1 席付费异源模型）。
            import os as _os
            _provider = "deepseek"
            if _os.environ.get("CRITIC_HETEROSOURCE", "0") == "1":
                # 异源终局：全部走 OpenRouter（deepseek 异源路由 + qwen flash）
                try:
                    from core.deepseek_client import _registry
                    if "openrouter" in _registry._providers:
                        _provider = "openrouter"
                except Exception:
                    pass
            elif _os.environ.get("CRITIC_LOCAL", "0") == "1":
                _critic_order = ["IB", "PE", "MBB", "BIG4", "CS"]
                _idx = _critic_order.index(self.role.role_id) if self.role.role_id in _critic_order else 9
                if _idx >= 3:  # 后 2 席
                    _provider = "ollama_local"
            result = call_llm(messages, temperature=0.2, provider=_provider)
            content = result["choices"][0]["message"]["content"]
            parsed = _extract_json(content)
            # 修复（2026-08-01）：LLM 输出 JSON 嵌套字符串时 json.loads 可能返回 str，
            # 导致 parsed.get() 报 "'str' object has no attribute 'get'"。
            # 加类型保护，非 dict 视为解析失败。
            if not isinstance(parsed, dict):
                parsed = None
            if parsed:
                dims = []
                for d in parsed.get("dimensions", []):
                    if not isinstance(d, dict):
                        continue
                    dims.append(CriticScore(
                        dimension=d.get("dimension", "?"),
                        score=float(d.get("score", 0.5)),
                        passed=d.get("passed", False),
                        comment=d.get("comment", ""),
                        severity=d.get("severity", "info"),
                    ))
                return CriticVerdict(
                    role_id=self.role.role_id,
                    role_name=self.role.role_name,
                    overall_score=float(parsed.get("overall_score", 0.5)),
                    passed=parsed.get("passed", False),
                    dimension_scores=dims,
                    strengths=parsed.get("strengths", []),
                    weaknesses=parsed.get("weaknesses", []),
                    suggestions=parsed.get("suggestions", []),
                    duration_ms=(time.time()-t0)*1000,
                )
        except Exception as e:
            logger.warning(f"Critic {self.role.role_id} failed: {e}")
            return CriticVerdict(
                role_id=self.role.role_id,
                role_name=self.role.role_name,
                overall_score=0.5, passed=False,
                suggestions=[f"Critic failed: {str(e)[:100]}"],
                duration_ms=(time.time()-t0)*1000,
            )
        return CriticVerdict(
            role_id=self.role.role_id,
            role_name=self.role.role_name,
            overall_score=0.5, passed=False,
            suggestions=["Critic produced no output"],
            duration_ms=(time.time()-t0)*1000,
        )


class ConsensusOrchestrator:
    """Orchestrate multiple critic evaluations."""

    def __init__(self):
        self.prompts = {
            "IB": IB_PROMPT, "PE": PE_PROMPT,
            "MBB": MBB_PROMPT, "BIG4": BIG4_PROMPT,
            "CS": CS_PROMPT,
        }

    def evaluate(self, report_text, roles=None, context=None):
        t0 = time.time()
        if roles is None:
            # R15（2026-08-01 提速）：默认 3 席核心评委（IB/PE/MBB），
            # 实测 critic 424s 是第二大瓶颈。3 席保留最高价值评审（投行/PE/战略），
            # 砍掉审计(BIG4)/券商(CS)冗余。需要 5 席时设 CRITIC_FULL=1。
            if os.environ.get("CRITIC_FULL", "0") == "1":
                roles = [
                    CriticRole("IB", "Investment Bank Partner",
                        ["data", "valuation", "bold call"], "", 1.0),
                    CriticRole("PE", "Private Equity Partner",
                        ["moat", "scale", "mgmt"], "", 1.0),
                    CriticRole("MBB", "Strategy Consultant",
                        ["methodology", "logic"], "", 1.0),
                    CriticRole("BIG4", "Audit Partner",
                        ["compliance", "data fidelity"], "", 1.0),
                    CriticRole("CS", "Chinese Brokerage Chief",
                        ["regulation", "market context"], "", 1.0),
                ]
            else:
                roles = [
                    CriticRole("IB", "Investment Bank Partner",
                        ["data", "valuation", "bold call"], "", 1.0),
                    CriticRole("PE", "Private Equity Partner",
                        ["moat", "scale", "mgmt"], "", 1.0),
                    CriticRole("MBB", "Strategy Consultant",
                        ["methodology", "logic"], "", 1.0),
                ]
        verdicts = []
        # 2026-08-01 优化：并行跑评委（相互独立），50-66秒 → 10-15秒
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=len(roles)) as pool:
                futures = {pool.submit(CriticAgent(role).evaluate, report_text, self.prompts, context): role
                           for role in roles}
                verdicts_by_role = {}
                for fut in as_completed(futures):
                    role = futures[fut]
                    try:
                        verdicts_by_role[id(role)] = fut.result()
                    except Exception as e:
                        logger.warning("Critic %s failed: %s", role.role_id, str(e)[:80])
                # 保持 roles 顺序
                verdicts = [verdicts_by_role.get(id(r),
                             CriticVerdict(role_id=r.role_id, role_name=r.role_name,
                                           overall_score=0.5, passed=False,
                                           suggestions=["Critic failed"]))
                            for r in roles]
        except Exception:
            # 回退串行（线程池不可用时）
            for role in roles:
                agent = CriticAgent(role)
                v = agent.evaluate(report_text, self.prompts, context)
                verdicts.append(v)
        total_w = sum(r.weight for r in roles)
        # P3-3 圆桌信誉机制（2026-08-07）：记录各角色评审（关键判断进回测），
        # 最终分用信誉加权（信誉高的角色权重高，激励倒挂修正）。
        try:
            from core.reviewer_reputation import ReviewerReputation
            _rr = ReviewerReputation()
            _report_id = str(getattr(self, "_report_id", "") or (context or {}).get("asset", "report"))
            for v, r in zip(verdicts, roles):
                _claims = [getattr(v, "strengths", []) or []] + [getattr(v, "weaknesses", []) or []]
                try:
                    _rr.record_review(r.role_id, _report_id, v.overall_score,
                                      [str(x)[:80] for x in _claims][:4])
                except Exception:
                    pass
            # 信誉加权最终分
            weighted = sum(v.overall_score * r.weight * _rr.get_weight(r.role_id)
                           for v, r in zip(verdicts, roles)) / sum(
                r.weight * _rr.get_weight(r.role_id) for r in roles)
        except Exception:
            weighted = sum(v.overall_score * r.weight for v, r in zip(verdicts, roles)) / total_w
        return ConsensusReport(
            final_score=round(weighted, 2),
            passed=weighted >= 0.6,
            verdicts=verdicts,
            duration_ms=(time.time()-t0)*1000,
        )


def critic_panel_node(node_id, context):
    """E2E pipeline node for critic panel."""
    text = context.get("final_text") or context.get("report_text", "")
    if not text:
        return {"critic_passed": False}
    oc = ConsensusOrchestrator()
    report = oc.evaluate(text)
    context["critic_report"] = report
    context["critic_passed"] = report.passed
    context["critic_score"] = report.final_score
    logger.info(f"Critic: score={report.final_score} passed={report.passed}")
    return {
        "critic_report": report,
        "critic_passed": report.passed,
        "critic_score": report.final_score,
    }


if __name__ == "__main__":
    print("Critic Panel module loaded.")
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=str, help="Report path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.report:
        p = PPath(args.report)
        if p.exists():
            text = p.read_text(encoding="utf-8")
            oc = ConsensusOrchestrator()
            r = oc.evaluate(text)
            if args.json:
                import json as j
                print(j.dumps(r.to_dict(), ensure_ascii=False, indent=2))
            else:
                print(r.summary())