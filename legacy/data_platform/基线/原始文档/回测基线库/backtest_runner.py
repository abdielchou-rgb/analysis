#!/usr/bin/env python3
# 2haofenxi v2.0 backtest runner - FP1-FP4 compliant

import json, sys, re, os
from pathlib import Path

SCORE_CARD = {
    "A_structure": {
        "weight": 0.18,
        "max": 20,
        "items": {
            "A1_cover": 4,
            "A2_summary": 3,
            "A3_framework": 5,
            "A4_risk": 3,
            "A5_conclusion": 3,
            "A6_appendix": 2,
        },
    },
    "B_data": {
        "weight": 0.23,
        "max": 25,
        "items": {"B1_citation": 8, "B2_freshness": 5, "B3_crossref": 5, "B4_accuracy": 5, "B5_model": 2},
    },
    "C_chart": {
        "weight": 0.23,
        "max": 25,
        "items": {
            "C1_density": 5,
            "C2_numbering": 5,
            "C3_placement": 5,
            "C4_quality": 5,
            "C5_color": 3,
            "C6_labels": 2,
        },
    },
    "D_logic": {
        "weight": 0.13,
        "max": 15,
        "items": {"D1_what_so_what": 5, "D2_causal_chain": 4, "D3_clarity": 3, "D4_counter": 3},
    },
    "E_format": {"weight": 0.09, "max": 10, "items": {"E1_font": 3, "E2_layout": 3, "E3_language": 2, "E4_flow": 2}},
    "F_style": {"weight": 0.05, "max": 5, "items": {"F1_style_match": 5}},
    "G_turing": {
        "weight": 0.09,
        "max": 10,
        "items": {"G1_experience": 3, "G2_uncertainty": 2, "G3_ai_fingerprint": 3, "G4_human_tone": 2},
    },
}
# AI fingerprints (12 P0-level patterns)
AI_FINGERPRINTS_P0 = [
    "值得注意的是",
    "综上所述",
    "从另一个角度看",
    "总的来说",
    "不可忽视的是",
    "莫庸置疑",
    "显而易见",
    "可以预见的是",
    "我们不难发现",
]
# Human signal patterns
HUMAN_SIGNALS = {
    "experience": [
        "我们调研发现",
        "从历史经验看",
        "根据我们调研",
        "我们注意到",
    ],
    "uncertainty": [
        "预测区间",
        "可能在",
        "约为",
        "估计",
        "测算",
        "我们认为",
    ],
    "credibility": [
        "统计口径",
        "调整后",
        "修正为",
        "数据来源",
        "来源",
    ],
}


def check_structure(text):
    """Check report structure completeness (FP1)"""
    first = text[:500]
    has_cover = bool(re.search(r"证券研究报告|深度报告|研究报告|Cover", first))
    has_summary = bool(re.search(r"核心观点|Key Takeaways|摘要|Executive Summary|投资逻辑", text[:2000]))
    has_risk = bool(re.search(r"风险提示|Risks|Risk Factors|风险", text[-3000:]))
    has_conclusion = bool(re.search(r"投资建议|结论|Conclusion|推荐", text[-5000:]))
    has_numbered = bool(re.search(r"1[、.]|2[、.]|3[、.]", text))
    has_appendix = bool(re.search(r"附录|Appendix|数据来源|参考", text[-2000:]))
    return {
        "cover": has_cover,
        "summary": has_summary,
        "risk": has_risk,
        "conclusion": has_conclusion,
        "numbered": has_numbered,
        "appendix": has_appendix,
    }


def check_citations(text):
    """Check data source citation coverage (FP2)"""
    patterns = [
        r"来源[：:]\s*\S+",
        r"Source[：:]\s*\S+",
        r"数据来源[：:]\s*\S+",
        r"根据\S+数据",
        r"资料来源[：:]\s*\S+",
    ]
    count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in patterns)
    data_points = len(re.findall(r"\d+\.?\d*[%亿万]", text))
    coverage = min(1.0, count / max(1, data_points / 3))
    return count, coverage, data_points


def check_figures(text):
    """Check figure density and placement (FP2)"""
    fig_refs = len(re.findall(r"(图|表|Figure|Table|Exhibit)\s*\d+", text))
    body = text.split("风险提示")[0] if "风险提示" in text else text[: len(text) // 2]
    body_figs = len(re.findall(r"(图|表)\s*\d+[：:]", body))
    total_fn = len(re.findall(r"(图|表)\s*\d+[：:]", text))
    end_figs = max(0, total_fn - body_figs)
    ratio = body_figs / max(1, total_fn)
    return fig_refs, body_figs, end_figs, ratio


def check_human_signals(text):
    """Check human-ness signals (FP4)"""
    pos = 0
    neg = 0
    for key, patterns in HUMAN_SIGNALS.items():
        for p in patterns:
            pos += len(re.findall(p, text, re.IGNORECASE))
    for fp in AI_FINGERPRINTS_P0:
        neg += len(re.findall(fp, text))
    md = len(re.findall(r"\*\*", text)) // 2
    neg += md
    net = pos - neg * 2
    return {"positive": pos, "negative": neg, "net": max(-10, min(10, net))}


def check_what_so_what(text):
    """Check What->So What causal chain (FP2)"""
    signals = [r"这意味着", r"Therefore|So What", r"因此|所以|故而", r"建议|推荐|策略"]
    return sum(len(re.findall(p, text, re.IGNORECASE)) for p in signals)


def check_counter_argument(text):
    """Check counter-argument presence (FP2/FP4)"""
    signals = [r"风险[在提示]", r"Risk|risk", r"bear case|Bear Case", r"然而|但|不过|尽管如此"]
    return sum(len(re.findall(p, text, re.IGNORECASE)) for p in signals)


def score_report(text, report_type="industry", target_tier="S"):
    """Score report against FP1-FP4 criteria. Returns dict."""

    # A. Structure (FP1)
    struct = check_structure(text)
    a = (
        (4 if struct["cover"] else 0)
        + (3 if struct["summary"] else 0)
        + (5 if struct["numbered"] else 0)
        + (3 if struct["risk"] else 0)
        + (3 if struct["conclusion"] else 0)
        + (2 if struct["appendix"] else 0)
    )

    # B. Data (FP2)
    cit_count, cit_coverage, total_points = check_citations(text)
    b = min(8, int(cit_coverage * 8)) + 5 + min(5, cit_count // 2) + 5 + 2

    # C. Charts (FP2)
    fig_count, body_figs, end_figs, in_text_ratio = check_figures(text)
    c = min(5, fig_count) + min(5, fig_count // 2) + int(5 * in_text_ratio) + 3 + 2 + 1

    # D. Logic (FP2/FP4)
    sw = check_what_so_what(text)
    cc = check_counter_argument(text)
    d = min(5, sw) + min(4, sw // 2) + (3 if struct["summary"] else 1) + min(3, cc)

    # E. Format (FP4)
    md_stars = len(re.findall(r"\*\*", text))
    e = max(0, 3 - md_stars // 2) + (3 if struct["numbered"] else 1) + 2 + 2

    # F. Style (FP3)
    f = 0
    if "Key Takeaways" in text or "KEY TAKEAWAYS" in text:
        f += 2
    if re.search(r"(Exhibit|Figure)\s*\d+", text):
        f += 1
    if struct["numbered"]:
        f += 1
    if re.search(r"SAC|SFC|编号", text):
        f += 1
    f = min(5, f)

    # G. Turing (FP4)
    sig = check_human_signals(text)
    ai_fp = len(re.findall(r"值得注意的是|综上所述", text))
    g = min(3, sig["positive"] // 3) + min(2, sig["positive"] // 4) + max(0, 3 - ai_fp) + min(2, sig["positive"] // 5)

    total = a + b + c + d + e + f + g

    # Dimension rates
    rates = {"A": a / 20, "B": b / 25, "C": c / 25, "D": d / 15, "E": e / 10, "F": f / 5, "G": g / 10}
    all_70 = all(v >= 0.7 for v in rates.values())
    key_ok = rates["B"] >= 0.7 and rates["C"] >= 0.7 and rates["G"] >= 0.7

    if total >= 85 and all_70:
        verdict = "PASS"
    elif total >= 75 and key_ok:
        verdict = "CONDITIONAL"
    else:
        verdict = "FAIL"

    # Gaps and improvement plan
    gaps = []
    if not struct["cover"]:
        gaps.append("缺少封面元素")
    if not struct["summary"]:
        gaps.append("缺少核心摘要")
    if cit_coverage < 0.6:
        gaps.append(f"数据来源标注不足({cit_coverage:.0%})")
    if fig_count < 3:
        gaps.append(f"图表密度不足({fig_count}个)")
    if in_text_ratio < 0.5:
        gaps.append(f"图表多在文末({in_text_ratio:.0%})")
    if sig["net"] < 0:
        gaps.append(f"人感净分为负({sig['net']})")
    if sig["negative"] > 0:
        gaps.append(f"存在{sig['negative']}处AI指纹")

    imp = []
    for gap_item in gaps:
        if "封面" in gap_item:
            imp.append("添加封面(标题+日期+评级)")
        elif "摘要" in gap_item:
            imp.append("添加核心观点摘要或Key Takeaways")
        elif "来源" in gap_item:
            imp.append("补充数据来源标注")
        elif "密度" in gap_item:
            imp.append("增加图表数量")
        elif "文末" in gap_item:
            imp.append("移动图表到对应正文位置")
        elif "人感" in gap_item or "指纹" in gap_item:
            imp.append("减少AI套话,增加经验引用")

    result = {
        "scores": {
            "A_structure": a,
            "B_data": b,
            "C_chart": c,
            "D_logic": d,
            "E_format": e,
            "F_style": f,
            "G_turing": g,
        },
        "total": total,
        "dimension_rates": {k: round(v, 2) for k, v in rates.items()},
        "verdict": verdict,
        "gaps": gaps,
        "improvement_plan": imp,
        "human_signals": {"positive": sig["positive"], "negative": sig["negative"], "net": sig["net"]},
        "citations": {"count": cit_count, "coverage": round(cit_coverage, 2)},
        "figures": {
            "total": fig_count,
            "in_body": body_figs,
            "at_end": end_figs,
            "in_text_ratio": round(in_text_ratio, 2),
        },
    }
    return result


def main():
    report_path = None
    report_type = "industry"
    target_tier = "S"

    for i, arg in enumerate(sys.argv):
        if arg == "--report":
            report_path = sys.argv[i + 1]
        elif arg == "--type":
            report_type = sys.argv[i + 1]
        elif arg == "--tier":
            target_tier = sys.argv[i + 1]

    if not report_path:
        print('{"error": "请提供 --report 参数"}')
        sys.exit(1)

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(report_path, "r", encoding="gbk") as f:
            text = f.read()

    result = score_report(text, report_type, target_tier)
    result["filename"] = os.path.basename(report_path)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return result


if __name__ == "__main__":
    main()
