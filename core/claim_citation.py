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
    # P3-2 (2026-09-01): 兼容非 chart_data 结构（data_dict.json 顶层为数值键，
    # 无 chart_data 容器）——直接展平顶层数值，作为 fig_* 的替代候选源
    if not candidates:
        for leaf, val in _walk_numbers(cd, "data"):
            if isinstance(val, (int, float)) and not isinstance(val, bool):
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
    """主入口：返回附了溯源附录的报告文本（无命中则原样返回）。

    P3-2 (2026-09-01) 幂等加固：若文本已含附录标记则原样返回，
    防止 assemble 节点在 write-revise 循环中被多次调用导致附录重复注入。
    """
    if "附录：关键数据溯源" in (report_text or ""):
        return report_text
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


def _split_sentences(text: str) -> list[str]:
    """统一句子切分——build_claim_citation_map 和 annotate_inline 共用。"""
    return [s.strip() for s in re.split(r"[。！？\n]", text or "") if s.strip()]


def annotate_inline(report_text: str, collected_data: dict, max_markers: int = 40) -> tuple[str, list[dict]]:
    """命中句尾追加 [注N] 脚注标记 + 返回编号后的完整文本与 claims。

    与 append_citation_appendix 二选一；无命中时原文返回。
    幂等：已含 [注1] 或附录标题时原样返回。
    """
    if not report_text:
        return report_text, []
    # 幂等 guard
    if "[注1]" in report_text or "附录：数据溯源注释" in report_text:
        return report_text, []
    claims = build_claim_citation_map(report_text, collected_data)
    if not claims:
        return report_text, []
    id_by_claim = {c["claim"]: i + 1 for i, c in enumerate(claims)}
    # 用统一句子切分，再按原文顺序重组并注入标记
    sentences = _split_sentences(report_text)
    n_marked = 0
    out_parts: list[str] = []
    for sent in sentences:
        out_parts.append(sent)
        key = sent[:100]
        if len(sent) >= 8 and key in id_by_claim and n_marked < max_markers:
            out_parts.append(f"[注{id_by_claim[key]}]")
            n_marked += 1
    # 重组：用句号连接（原始分隔符已丢失，统一用。重建）
    marked_text = "。".join(out_parts)
    if not marked_text.endswith("。"):
        marked_text += "。"
    appendix = render_numbered_appendix(claims)
    return marked_text + "\n" + appendix, claims


def render_jsonld_ledger(claims: list[dict], provenance: dict | None = None) -> str:
    """生成 JSON-LD claim→source ledger，嵌入报告尾部。

    <script type="application/ld+json"> 块，每个 claim 带 source URL。
    符合 FP2a 诚实标注：有来源填 URL，无来源标 "unavailable"。

    Args:
        claims: build_claim_citation_map 的输出
        provenance: data_provenance 字典（可选），用于匹配数据键到原始 URL
    Returns:
        JSON-LD 字符串，无 claims 时返回空字符串
    """
    if not claims:
        return ""

    provenance = provenance or {}
    source_map = {}
    # 从 provenance.sources 提取 {数据键: URL} 映射
    for src in provenance.get("sources", []):
        key = src.get("key", src.get("data_key", ""))
        url = src.get("url", src.get("source_url", ""))
        if key and url:
            source_map[key] = url

    ledger = []
    for claim in claims:
        claim_text = claim.get("claim", "")
        data_key = claim.get("key", "")
        source_url = source_map.get(data_key, "unavailable")

        ledger.append({
            "@type": "Claim",
            "claim": claim_text,
            "source": {
                "url": source_url,
                "data_key": data_key,
                "confidence": claim.get("confidence", "matched"),
            },
        })

    import json
    return f'\n<script type="application/ld+json">\n{json.dumps(ledger, ensure_ascii=False, indent=2)}\n</script>\n'


def build_footnote_url_map(claims: list[dict], provenance: dict | None = None) -> dict[str, str]:
    """构建 [注N] → 来源 URL 映射，供 exporter 超链接使用。

    Returns:
        {"1": "https://...", "2": "https://...", ...}
    """
    if not claims:
        return {}

    provenance = provenance or {}
    source_map = {}
    for src in provenance.get("sources", []):
        key = src.get("key", src.get("data_key", ""))
        url = src.get("url", src.get("source_url", ""))
        if key and url:
            source_map[key] = url

    url_map = {}
    for i, claim in enumerate(claims, 1):
        refs = claim.get("refs", [])
        for ref in refs:
            url = source_map.get(ref, "")
            if url:
                url_map[str(i)] = url
                break
        # 如果没有精确匹配，尝试从 sources 列表取第一个 URL
        if str(i) not in url_map:
            sources = claim.get("sources", [])
            for src in sources:
                if src.startswith("http"):
                    url_map[str(i)] = src
                    break

    return url_map
