"""claim_citation.py — claim 级数据溯源映射 + 自动附录。

P3-audit 2026-08-24 落地项（对标 STORM claim-level citation）：
此前溯源是报告级的（来源标注率≥30% 的 heuristic），读者无法从单个
数字回溯到数据键。本模块做确定性映射：

  1. build_claim_citation_map —— 扫描正文含数字的句子，与
     collected_data.chart_data 各 fig_* 键的数值做容差匹配（±0.5%），
     命中 → {claim, key, source}
  2. append_citation_appendix —— 把命中表渲染成文末附录
     「附录：关键数据溯源」，无命中则原文返回

纯确定性、零 LLM；env REPORT_CITATION_APPENDIX=0 可关。
"""

from __future__ import annotations

import re

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers_in(sentence: str) -> list[float]:
    out = []
    for m in _NUM_RE.finditer(sentence):
        try:
            v = float(m.group())
            if v != 0:
                out.append(v)
        except ValueError:
            pass
    return out


def _walk_numbers(node, path=""):
    """递归产出 (路径, 数值) 对——dict/list/标量均展开，限深防爆炸。"""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_numbers(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node[:20]):
            yield from _walk_numbers(v, f"{path}[{i}]")
    elif isinstance(node, bool):
        return
    elif isinstance(node, (int, float)):
        yield path, float(node)


def _match_value(num: float, candidates: dict[str, float]) -> str | None:
    """±0.5% 容差匹配；多键同值时取最短路径（更具体的叶节点）。"""
    hits = []
    for path, val in candidates.items():
        if val != 0 and abs(num - val) / abs(val) <= 0.005:
            hits.append(path)
    if not hits:
        return None
    return min(hits, key=len)


def build_claim_citation_map(report_text: str, collected_data: dict) -> list[dict]:
    """正文句子 × chart_data 数值 → 命中映射表。"""
    cd = collected_data or {}
    chart_data = cd.get("chart_data", {}) or {}
    # 预展平全部数值候选：fig_key.leaf_path -> value
    candidates: dict[str, float] = {}
    for fig_key, payload in chart_data.items():
        for leaf, val in _walk_numbers(payload, str(fig_key)):
            candidates[f"{leaf}={val:g}"] = val
    if not candidates:
        return []

    sources_by_key = {}
    items = cd.get("items", []) if isinstance(cd.get("items"), list) else []
    for it in items:
        if isinstance(it, dict) and it.get("key"):
            sources_by_key[it["key"]] = str(it.get("source", ""))[:80]

    claims: list[dict] = []
    seen_sentences: set[str] = set()
    for raw in re.split(r"[。！？\n]", report_text or ""):
        s = raw.strip()
        if len(s) < 8 or s in seen_sentences:
            continue
        nums = [n for n in _numbers_in(s) if n >= 1]  # 排除 0.x 小数噪声
        if not nums:
            continue
        matched_keys = set()
        for n in nums[:6]:  # 每句最多取 6 个数字控制成本
            hit = _match_value(n, candidates)
            if hit:
                fig_key = hit.split(".", 1)[0]
                matched_keys.add((fig_key, sources_by_key.get(fig_key, "")))
        if matched_keys:
            seen_sentences.add(s)
            claims.append(
                {
                    "claim": s[:100],
                    "refs": sorted({k for k, _ in matched_keys}),
                    "sources": sorted({src for _, src in matched_keys if src}),
                }
            )
    return claims


def render_citation_appendix(claims: list[dict], max_rows: int = 30) -> str:
    if not claims:
        return ""
    lines = [
        "",
        "## 附录：关键数据溯源",
        "",
        "| 正文论断 | 数据键 | 来源 |",
        "|---|---|---|",
    ]
    for c in claims[:max_rows]:
        src = "；".join(c["sources"]) or "—"
        lines.append(f"| {c['claim']} | {', '.join(c['refs'])} | {src} |")
    if len(claims) > max_rows:
        lines.append(f"| …（其余 {len(claims) - max_rows} 条略） | | |")
    lines.append("")
    lines.append("*本附录由管线确定性生成：正文数值与数据字典 ±0.5% 容差匹配。*")
    return "\n".join(lines)


def append_citation_appendix(report_text: str, collected_data: dict) -> str:
    """主入口：返回附了溯源附录的报告文本（无命中则原样返回）。"""
    claims = build_claim_citation_map(report_text, collected_data)
    appendix = render_citation_appendix(claims)
    if not appendix:
        return report_text
    return report_text.rstrip() + "\n" + appendix


# ── 内联脚注模式（P3-audit 2026-08-24，env REPORT_CITATION_INLINE 门控）──
# STORM 式 claim-level citation 的正文形态：命中句尾追加 [注N] 标记，
# 附录同步编号。默认关——内联标记改变报告版面，由调用方按交付形态选择。


def render_numbered_appendix(claims: list[dict], max_rows: int = 30) -> str:
    if not claims:
        return ""
    lines = ["", "## 附录：数据溯源注释", ""]
    for i, c in enumerate(claims[:max_rows], 1):
        src = "；".join(c["sources"]) or "—"
        lines.append(f"[注{i}] 数据键 {', '.join(c['refs'])}｜来源：{src}｜论断：{c['claim']}")
    if len(claims) > max_rows:
        lines.append(f"…（其余 {len(claims) - max_rows} 条略）")
    lines.append("")
    lines.append("*本附录由管线确定性生成：正文数值与数据字典 ±0.5% 容差匹配。*")
    return "\n".join(lines)


def annotate_inline(report_text: str, collected_data: dict, max_markers: int = 40) -> tuple[str, list[dict]]:
    """命中句尾追加 [注N] 脚注标记 + 返回编号后的完整文本与 claims。

    与 append_citation_appendix 二选一；无命中时原文返回。
    """
    claims = build_claim_citation_map(report_text, collected_data)
    if not claims:
        return report_text, []
    id_by_claim = {c["claim"]: i + 1 for i, c in enumerate(claims)}
    # 以保留分隔符的方式切分（与 build 的句子边界一致：句末标点+换行）
    parts = re.split(r"([。！？]|\n)", report_text)
    n_marked = 0
    out: list[str] = []
    for seg in parts:
        out.append(seg)
        key = seg.strip()[:100]
        if seg.strip() and len(seg.strip()) >= 8 and key in id_by_claim and n_marked < max_markers:
            # 仅在非分隔符段后加标记
            out.append(f"[注{id_by_claim[key]}]")
            n_marked += 1
    marked_text = "".join(out).rstrip()
    appendix = render_numbered_appendix(claims)
    return marked_text + "\n" + appendix, claims
