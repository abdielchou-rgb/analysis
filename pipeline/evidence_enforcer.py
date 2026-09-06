"""
Evidence Enforcer — 声明账本（Phase A1，2026-09-06）。

职责：报告全文数值声明 → 与计算引擎产出做容差匹配 → 产出账本：
    [{claim, value, source_module, status: verified|unverifiable|contradicted}]

消费方：
1. iron_gate._check_evidence_coverage（WARN 一个版本拿基线，再收紧 BLOCK）
2. _revision_targets_from_gate（只重写违规段落，enforcer 给出替换值）
3. 导出审计附录（每数字 → 来源模块 → 假设）

设计约束：
- 纯函数，零 LLM，零网络——确定性问题用确定性手段
- 单位归一（万/亿/%/倍/x）+ ±2% 容差匹配
- 中英文数字声明正则
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.evidence_enforcer")

# ── 数值声明提取（中英文） ────────────────────────────────────────────────

# 单位捕获: 百分比/亿/万/元/倍/x
_UNIT_CLASS = r"(?:%|％|亿|万|元|股|倍|x|X)"

_NUM = r"[\-−+]?\d[\d,，]*(?:\.\d+)?"

_PATTERNS = [
    # 中文: 目标价 1500元 / 目标价：1,500
    rf"(?:目标价|公允价值|合理估值|每股价值)[\s:：为是]*({_NUM})\s*(?:{_UNIT_CLASS})?",
    # 增长率: 增长 15.7% / 同比增长15% / 增速为20%
    rf"(?:增长|增速|增长率|下降|下滑|扩张|提升)[\s:：为约]*({_NUM})\s*[%％]",
    # 估值倍数: PE 22倍 / PE为22x / 市盈率25
    rf"(?:PE|PB|PS|P/E|P/B|市盈率|市净率|市销率|EV/EBITDA)[\s:：约为]*({_NUM})\s*(?:倍|{_UNIT_CLASS})?",
    # 利润率: 毛利率91.9% / 净利率50% / ROE 36%
    rf"(?:毛利率|净利率|利润率|ROE|ROIC|ROA|WACC|IRR)[\s:：约为达]*({_NUM})\s*[%％]?",
    # 营收/利润绝对值: 营收1741亿 / 净利润862亿
    rf"(?:营收|收入|营业收入|净利润|归母净利润|利润|FCF|自由现金流)[\s:：为约达]*({_NUM})\s*(亿|万)?",
    # 份额/占比: 市占率35% / 占比达40%
    rf"(?:市占率|市场份额|占比)[\s:：为约达]*({_NUM})\s*[%％]",
    # English: target price of $150 / revenue of 174.1B
    rf"target price (?:of )?({_NUM})",
    rf"(?:revenue|net income|EPS) (?:of )?({_NUM})",
]

_COMPILED = [(p, re.compile(p)) for p in _PATTERNS]


@dataclass
class NumericClaim:
    text: str
    raw_number: str
    value: float
    unit: str = ""
    kind: str = "generic"  # target_price / growth / multiple / margin / absolute / share
    line: int = 0


@dataclass
class ClaimLedger:
    claims: list[NumericClaim] = field(default_factory=list)
    verified: list[NumericClaim] = field(default_factory=list)
    contradicted: list[NumericClaim] = field(default_factory=list)
    unverifiable: list[NumericClaim] = field(default_factory=list)
    replacement_map: dict[int, str] = field(default_factory=dict)  # claim idx -> "原文 → 修正值"

    @property
    def coverage(self) -> float:
        """verified / total（无声明时返回 1.0——没有数字就没有可错数字）"""
        if not self.claims:
            return 1.0
        return len(self.verified) / len(self.claims)

    def summary(self) -> dict:
        return {
            "total_claims": len(self.claims),
            "verified": len(self.verified),
            "contradicted": len(self.contradicted),
            "unverifiable": len(self.unverifiable),
            "coverage": round(self.coverage, 4),
        }


def _to_float(raw: str) -> float:
    try:
        return float(raw.replace(",", "").replace("，", "").replace("−", "-"))
    except (ValueError, TypeError):
        return float("nan")


def _classify(pattern_idx: int) -> str:
    return {
        0: "target_price",
        1: "growth",
        2: "multiple",
        3: "margin",
        4: "absolute",
        5: "share",
    }.get(pattern_idx, "generic")


def extract_claims(text: str) -> list[NumericClaim]:
    """从报告全文提取数值声明。按行号标注便于 fail_segment_locator 定位。"""
    claims: list[NumericClaim] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        # 跳过表格分隔符/代码块噪音
        if line.strip().startswith(("|", "---")):
            continue
        for idx, (_, compiled) in enumerate(_COMPILED):
            for m in compiled.finditer(line):
                raw = m.group(1)
                val = _to_float(raw)
                if val != val:  # NaN
                    continue
                claims.append(
                    NumericClaim(
                        text=m.group(),
                        raw_number=raw,
                        value=val,
                        unit=m.group(2) if m.lastindex and m.lastindex >= 2 else "",
                        kind=_classify(idx),
                        line=line_no,
                    )
                )
    return claims


# ── 计算引擎产出 → 候选值池 ──────────────────────────────────────────────


def build_value_pool(compute_results: dict) -> list[tuple[str, float, str]]:
    """从 compute_results 抽取 (名称, 值, 展示串) 候选池。

    覆盖: engine_ib（16步核）、dcf_valuation、scenario_analysis、
    sotp_valuation、comparable_valuation、revenue_bridge。
    """
    pool: list[tuple[str, float, str]] = []

    def _add(name: str, val, fmt: str | None = None):
        if isinstance(val, (int, float)) and val == val and abs(val) < 1e15:
            pool.append((name, float(val), fmt or f"{val:,.2f}"))

    # engine_ib 优先（审计核）
    ib = compute_results.get("engine_ib") or {}
    if ib.get("status") == "ok":
        r = ib.get("result") or {}
        _add("engine_ib.fair_value", r.get("fair_value"), f"{r.get('fair_value'):,.2f}")
        _add("engine_ib.scenario_weighted", r.get("scenario_weighted_target"))
        _add("engine_ib.mc_median", r.get("mc_median"))
        if r.get("mc_ci95"):
            _add("engine_ib.mc_ci95_low", r["mc_ci95"][0])
            _add("engine_ib.mc_ci95_high", r["mc_ci95"][1])
        exp = r.get("expectations") or {}
        _add("engine_ib.implied_growth_pct", (exp.get("implied_growth") or 0) * 100)
        _add("engine_ib.wacc_pct", (r.get("wacc") or 0) * 100)
        _add("engine_ib.tv_pct", (r.get("tv_pct") or 0) * 100)
        _add("engine_ib.upside_pct", r.get("upside_pct"))
        assump = r.get("assumptions") or {}
        for i, g in enumerate(assump.get("growth_rates") or []):
            _add(f"engine_ib.growth_y{i + 1}_pct", g * 100)

    # 既有模块
    for key, field_name in [
        ("dcf_valuation", "fair_value"),
        ("sotp_valuation", "target_price"),
    ]:
        mod = compute_results.get(key) or {}
        if mod.get("status") == "ok":
            _add(f"{key}.{field_name}", (mod.get("result") or {}).get(field_name))

    scen = compute_results.get("scenario_analysis") or {}
    if scen.get("status") == "ok":
        sr = scen.get("result") or {}
        _add("scenario.bull", sr.get("bull_price"))
        _add("scenario.base", sr.get("base_price"))
        _add("scenario.bear", sr.get("bear_price"))
        _add("scenario.weighted", sr.get("weighted_target"))

    comp = compute_results.get("comparable_valuation") or {}
    if comp.get("status") == "ok":
        _add("comparable.implied_pe_price", (comp.get("result") or {}).get("implied_pe_price"))

    rb = compute_results.get("revenue_bridge") or {}
    if rb.get("status") == "ok":
        _add("revenue_bridge.growth_pct", (rb.get("result") or {}).get("total_revenue_growth_pct"))

    return pool


# ── 匹配 ────────────────────────────────────────────────────────────────

_TOLERANCE = 0.02  # ±2%
# 单位换算: 声明值×乘数 后与池值比对
_UNIT_MULT = {"亿": 1e8, "万": 1e4, "%": 0.01, "％": 0.01, "倍": 1.0}


def _candidates_for(claim: NumericClaim, pool: list[tuple[str, float, str]]) -> list[tuple[str, float, str]]:
    """按声明类型过滤候选值（target_price 声明不匹配增长率池值，反之亦然）。"""
    kind_families = {
        "target_price": {"fair_value", "weighted", "implied_pe", "mc_median", "ci95", "bull", "base", "bear"},
        "multiple": {"pe", "implied_pe", "multiple", "ev"},
        "growth": {"growth", "upside", "cagr"},
        "margin": {"margin", "roe", "wacc", "irr", "tv_pct"},
        "absolute": {"revenue", "fcf", "absolute"},
        "share": {"share", "growth", "upside"},
    }
    family = kind_families.get(claim.kind, set())
    out = []
    for name, val, fmt in pool:
        if not family:
            out.append((name, val, fmt))
            continue
        n = name.lower()
        if any(f in n for f in family):
            out.append((name, val, fmt))
    return out


def verify_claims(claims: list[NumericClaim], pool: list[tuple[str, float, str]]) -> ClaimLedger:
    """容差匹配: 声明值（含单位换算）vs 池值。±2% 内即 verified。"""
    ledger = ClaimLedger(claims=claims)
    for i, claim in enumerate(claims):
        matched = None
        # 尝试两种解读: 原值 / 带单位换算
        interpretations = [claim.value]
        if claim.unit and claim.unit in _UNIT_MULT:
            interpretations.append(claim.value * _UNIT_MULT[claim.unit])
        # 百分比类声明也试 /100 后的形态（"15%" vs 池中 0.15 或 15）
        if claim.kind in ("growth", "margin", "share"):
            interpretations.extend([claim.value / 100, claim.value * 100])

        for name, pval, fmt in _candidates_for(claim, pool):
            for iv in interpretations:
                if pval == 0 and iv == 0:
                    matched = (name, pval, fmt)
                    break
                denom = max(abs(pval), abs(iv), 1e-9)
                if abs(iv - pval) / denom <= _TOLERANCE:
                    matched = (name, pval, fmt)
                    break
            if matched:
                break

        if matched:
            ledger.verified.append(claim)
        elif pool:
            # 有池可查但没对上 → contradicted（池非空时才判，避免全 skip 误伤）
            # 但 percentage/growth 类声明若只是"展望性表述"（无对应池值家族）降为 unverifiable
            cands = _candidates_for(claim, pool)
            if cands:
                ledger.contradicted.append(claim)
                best = cands[0]
                ledger.replacement_map[i] = (
                    f"声明『{claim.text.strip()[:40]}』未通过计算引擎核对（最接近: {best[0]}={best[2]}）"
                )
            else:
                ledger.unverifiable.append(claim)
        else:
            ledger.unverifiable.append(claim)
    return ledger


def run_evidence_check(
    report_text: str,
    compute_results: dict,
) -> ClaimLedger:
    """端到端入口: 文本 → 声明 → 账本。"""
    claims = extract_claims(report_text)
    pool = build_value_pool(compute_results)
    return verify_claims(claims, pool)


def format_gate_feedback(ledger: ClaimLedger) -> str:
    """给修订循环的反馈串：只列违规项 + 修正指引。"""
    if not ledger.contradicted:
        return ""
    lines = ["[证据账本] 以下数值声明与计算引擎输出不符，必须修正："]
    for i, msg in sorted(ledger.replacement_map.items()):
        lines.append(f"- {msg}")
    cov = ledger.summary()
    lines.append(
        f"当前证据覆盖率 {cov['coverage']:.0%}（verified {cov['verified']}/{cov['total_claims']}），"
        f"目标 ≥70%。修正时直接采用计算引擎输出值，不要重新推导。"
    )
    return "\n".join(lines)


def format_audit_appendix(ledger: ClaimLedger, compute_results: dict) -> str:
    """导出审计附录（Markdown，附 DOCX 末尾）。"""
    cov = ledger.summary()
    lines = [
        "## 附录：数值证据账本（自动生成）",
        "",
        f"- 提取数值声明: {cov['total_claims']} 处",
        f"- 通过计算引擎核对: {cov['verified']} 处",
        f"- 与计算结果冲突: {cov['contradicted']} 处",
        f"- 不可核验（展望性/无池值）: {cov['unverifiable']} 处",
        f"- 证据覆盖率: {cov['coverage']:.0%}",
        "",
    ]
    if ledger.contradicted:
        lines.append("### 未通过核对的声明")
        for msg in sorted(ledger.replacement_map.values()):
            lines.append(f"- {msg}")
        lines.append("")
    lines.append("### 计算引擎输出基准（估值数字唯一事实来源）")
    ib = (compute_results.get("engine_ib") or {}).get("result") or {}
    if ib:
        lines.append(f"- DCF 目标价: {ib.get('fair_value'):,.2f} 元/股")
        if ib.get("mc_ci95"):
            lines.append(f"- MC 95% CI: [{ib['mc_ci95'][0]:,.0f}, {ib['mc_ci95'][1]:,.0f}]")
        lines.append(f"- 情景加权: {ib.get('scenario_weighted_target'):,.2f}")
        exp = ib.get("expectations") or {}
        if exp.get("implied_growth") is not None:
            lines.append(f"- 市场隐含增长: {exp['implied_growth']:.2%}（本报告假设 {exp.get('our_growth'):.2%}）")
    lines.append("")
    return "\n".join(lines)
