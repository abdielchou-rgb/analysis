"""FP Scorer - FP1-FP4 compliance scoring engine"""
# 7-dimension scoring aligned with 2haofenxi first principles

import re

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


def check_structure(text):
    """FP1: Check report structure completeness"""
    first = text[:500]
    hc = bool(re.search(r"证券研究报告|深度报告|研究报告|Cover", first))
    hs = bool(re.search(r"核心观点|Key Takeaways|摘要|Executive Summary|投资逻辑", text[:2000]))
    hr = bool(re.search(r"风险提示|Risks|Risk Factors|风险", text[-3000:]))
    hco = bool(re.search(r"投资建议|结论|Conclusion|推荐", text[-5000:]))
    hn = bool(re.search(r"1[、.]|2[、.]|3[、.]", text))
    ha = bool(re.search(r"附录|Appendix|数据来源|参考", text[-2000:]))
    return {"cover": hc, "summary": hs, "risk": hr, "conclusion": hco, "numbered": hn, "appendix": ha}


def check_citations(text):
    """FP2: Check data source citation coverage"""
    patterns = [
        r"来源[\uff1a:]\s*\S+",
        r"Source[\uff1a:]\s*\S+",
        r"数据来源[\uff1a:]\s*\S+",
        r"根据\S+数据",
        r"资料来源[\uff1a:]\s*\S+",
    ]
    count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in patterns)
    dp = len(re.findall(r"\d+\.?\d*[%亿万]", text))
    cov = min(1.0, count / max(1, dp / 3))
    return count, cov, dp


def check_figures(text):
    """FP2: Check figure density and placement"""
    fig_refs = len(re.findall(r"(图|表|Figure|Table|Exhibit)\s*\d+", text))
    body = text.split("风险提示")[0] if "风险提示" in text else text[: len(text) // 2]
    body_figs = len(re.findall(r"(图|表)\s*\d+[\uff1a:]", body))
    total_fig = len(re.findall(r"(图|表)\s*\d+[\uff1a:]", text))
    end_figs = max(0, total_fig - body_figs)
    ratio = body_figs / max(1, total_fig)
    return fig_refs, body_figs, end_figs, ratio


def check_human_signals(text):
    """FP4: Check human-ness signals"""
    pos = 0
    for p in [
        "我们调研发现",
        "从历史经验看",
        "根据我们调研",
        "我们注意到",
        "预测区间",
        "可能在",
        "估计",
        "测算",
        "我们认为",
        "统计口径",
        "调整后",
        "数据来源",
    ]:
        pos += len(re.findall(p, text))
    neg = 0
    for fp in AI_FINGERPRINTS_P0:
        neg += len(re.findall(fp, text))
    md_stars = len(re.findall(r"\*\*", text)) // 2
    neg += md_stars
    net = pos - neg * 2
    return {"positive": pos, "negative": neg, "net": max(-10, min(10, net))}


def score_report(text, report_type="industry"):
    """7-dimension FP1-FP4 scoring. Returns dict with scores, gaps, plan."""
    struct = check_structure(text)
    cit_count, cit_cov, tot_pts = check_citations(text)
    fig_cnt, body_f, end_f, ratio = check_figures(text)
    sig = check_human_signals(text)

    # A. Structure (20)
    a = (
        (4 if struct["cover"] else 0)
        + (3 if struct["summary"] else 0)
        + (5 if struct["numbered"] else 0)
        + (3 if struct["risk"] else 0)
        + (3 if struct["conclusion"] else 0)
        + (2 if struct["appendix"] else 0)
    )

    # B. Data (25)
    b = min(8, int(cit_cov * 8)) + 5 + min(5, cit_count // 2) + 5 + 2

    # C. Charts (25)
    c = min(5, fig_cnt) + min(5, fig_cnt // 2) + int(5 * ratio) + 3 + 2 + 1

    # D. Logic (15)
    sw = sum(
        len(re.findall(p, text, re.IGNORECASE))
        for p in ["这意味着", "Therefore|So What", "因此|所以|故而", "建议|推荐|策略"]
    )
    cc = sum(
        len(re.findall(p, text, re.IGNORECASE))
        for p in ["风险[在提示]", "Risk|risk", "bear case|Bear Case", "然而|但|不过|尽管如此"]
    )
    d = min(5, sw) + min(4, sw // 2) + (3 if struct["summary"] else 1) + min(3, cc)

    # E. Format (10)
    e = max(0, 3 - len(re.findall(r"\*\*", text))) + (3 if struct["numbered"] else 1) + 2 + 2

    # F. Style (5)
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

    # G. Turing (10)
    ai_fp = len(re.findall(r"值得注意的是|综上所述", text))
    g = min(3, sig["positive"] // 3) + min(2, sig["positive"] // 4) + max(0, 3 - ai_fp) + min(2, sig["positive"] // 5)

    total = a + b + c + d + e + f + g
    rates = {
        "A": round(a / 20, 2),
        "B": round(b / 25, 2),
        "C": round(c / 25, 2),
        "D": round(d / 15, 2),
        "E": round(e / 10, 2),
        "F": round(f / 5, 2),
        "G": round(g / 10, 2),
    }
    all70 = all(v >= 0.7 for v in rates.values())
    key_ok = rates["B"] >= 0.7 and rates["C"] >= 0.7 and rates["G"] >= 0.7

    if total >= 85 and all70:
        verdict = "PASS"
    elif total >= 75 and key_ok:
        verdict = "CONDITIONAL"
    else:
        verdict = "FAIL"

    gaps = []
    if not struct["cover"]:
        gaps.append("缺少封面元素")
    if not struct["summary"]:
        gaps.append("缺少核心摘要")
    if cit_cov < 0.6:
        gaps.append(f"数据来源标注不足({cit_cov:.0%})")
    if fig_cnt < 3:
        gaps.append(f"图表密度不足({fig_cnt}个)")
    if ratio < 0.5:
        gaps.append(f"图表多在文末({ratio:.0%})")
    if sig["net"] < 0:
        gaps.append(f"人感净分为负({sig['net']})")
    if sig["negative"] > 0:
        gaps.append(f"存在{sig['negative']}处AI指纹")

    return {
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
        "dimension_rates": rates,
        "verdict": verdict,
        "gaps": gaps,
        "human_signals": {"positive": sig["positive"], "negative": sig["negative"], "net": sig["net"]},
        "citations": {"count": cit_count, "coverage": round(cit_cov, 2)},
        "figures": {"total": fig_cnt, "in_body": body_f, "at_end": end_f, "in_text_ratio": round(ratio, 2)},
        "report_type": report_type,
    }
