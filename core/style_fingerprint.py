# -*- coding: utf-8 -*-
"""style_fingerprint.py — 可解释风格指纹 v1（S1）。

8 维形式特征向量 + 距离度量。只比形式、不比内容词（防抄袭化）。
冷启动：scripts/style_fingerprint_build.py 对 md 语料批量提取。
"""

from __future__ import annotations

import re
import statistics
from pathlib import Path

_JUDGE_VERBS = ("我们判断", "我们预计", "我们认为", "我们看好", "判断", "预计", "有望", "或将", "大概率")
_CONNECTIVES = ["因此", "然而", "但", "此外", "综上", "同时", "一方面", "反之", "这意味着", "核心在于", "值得注意的是"]
_NUM_UNIT = re.compile(r"\d+(?:\.\d+)?\s*(?:亿|万|%|倍|元|吨|GW|Wh)")
_SENT_SPLIT = re.compile(r"[。！？；]")


def _clean(text: str) -> str:
    text = re.sub(r"```.*?```", "", text or "", flags=re.S)
    return text


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(_clean(text)) if len(s.strip()) >= 4]


def extract(text: str) -> dict:
    body = _clean(text)
    sents = _sentences(body)
    chars = max(len(re.sub(r"\s", "", body)), 1)
    lens = sorted(len(re.sub(r"\s", "", s)) for s in sents) or [0]

    def p(q):
        return round(lens[min(len(lens) - 1, int(len(lens) * q))], 1)

    judge = sum(body.count(v) for v in _JUDGE_VERBS)
    nums = len(_NUM_UNIT.findall(body))
    conn = {c: body.count(c) for c in _CONNECTIVES}
    conn_total = sum(conn.values()) or 1
    spectrum = {k: round(v / conn_total, 3) for k, v in sorted(conn.items(), key=lambda x: -x[1])[:10]}
    heads = {"h1": 0, "h2": 0, "h3": 0}
    for m in re.finditer(r"^(#{1,3})\s", body, re.M):
        heads[f"h{len(m.group(1))}"] += 1
    tables = len(re.findall(r"^\|.+\|\s*\n\|[-: |]+\|", body, re.M))
    first_sent = sents[0] if sents else ""
    pattern = (
        "data_first"
        if _NUM_UNIT.search(first_sent[:30])
        else "claim_first"
        if any(v in first_sent[:20] for v in _JUDGE_VERBS)
        else "other"
    )

    return {
        "sent_len_p50": p(0.5),
        "sent_len_p90": p(0.9),
        "judgment_density": round(judge / chars * 1000, 2),
        "number_density": round(nums / chars * 1000, 2),
        "connective_spectrum": spectrum,
        "heading_depth_hist": heads,
        "table_per_kchar": round(tables / (chars / 1000), 2) if chars > 500 else 0.0,
        "first_sentence_pattern": pattern,
    }


def distance(a: dict, b: dict, weights: dict | None = None) -> float:
    """加权距离：数值维=相对分位偏差，类目维=杰卡德/不一致。返回 0~∞（越小越像）。"""
    w = weights or {
        "sent_len_p50": 1.0,
        "sent_len_p90": 1.0,
        "judgment_density": 1.5,
        "number_density": 1.0,
        "table_per_kchar": 0.8,
    }
    num_dev = 0.0
    wsum = 0.0
    for k, wk in w.items():
        va, vb = a.get(k, 0), b.get(k, 0)
        denom = max(abs(vb), 1e-6)
        num_dev += wk * min(abs(va - vb) / denom, 2.0)  # 截断防单维爆炸
        wsum += wk
    # 连接词谱：top 集合杰卡德
    ca = set((a.get("connective_spectrum") or {}).keys())
    cb = set((b.get("connective_spectrum") or {}).keys())
    jac = (len(ca & cb) / len(ca | cb)) if (ca or cb) else 1.0
    # 标题分布偏差
    ha, hb = a.get("heading_depth_hist", {}), b.get("heading_depth_hist", {})
    tot_a = sum(ha.values()) or 1
    tot_b = sum(hb.values()) or 1
    hdev = sum(abs(ha.get(f"h{i}", 0) / tot_a - hb.get(f"h{i}", 0) / tot_b) for i in (1, 2, 3)) / 3
    pat = 0.0 if a.get("first_sentence_pattern") == b.get("first_sentence_pattern") else 1.0

    base = num_dev / wsum
    return round(base + (1 - jac) * 0.5 + hdev * 0.8 + pat * 0.4, 3)


def build_from_files(paths: list[Path]) -> dict:
    """多篇样本 → 中位指纹（逐特征取中位数；谱取并集频次归一）。"""
    vecs = [extract(Path(p).read_text(encoding="utf-8")) for p in paths]
    out: dict = {}
    for k in ("sent_len_p50", "sent_len_p90", "judgment_density", "number_density", "table_per_kchar"):
        vals = [v[k] for v in vecs]
        out[k] = round(statistics.median(vals), 2)
    spec: dict[str, int] = {}
    for v in vecs:
        for c, f in (v.get("connective_spectrum") or {}).items():
            spec[c] = spec.get(c, 0) + round(f * 100)
    total = sum(spec.values()) or 1
    out["connective_spectrum"] = {k: round(v / total, 3) for k, v in sorted(spec.items(), key=lambda x: -x[1])[:10]}
    hist = {"h1": 0, "h2": 0, "h3": 0}
    for v in vecs:
        for hk, hv in (v.get("heading_depth_hist") or {}).items():
            hist[hk] = hist.get(hk, 0) + hv
    out["heading_depth_hist"] = hist
    from collections import Counter

    out["first_sentence_pattern"] = Counter(v.get("first_sentence_pattern") for v in vecs).most_common(1)[0][0]
    return out


def load_target(style_id: str) -> dict | None:
    fp = Path(__file__).resolve().parent.parent / "data" / "fingerprints" / f"{style_id}.json"
    try:
        return json_load(fp)
    except Exception:
        return None


def json_load(p: Path) -> dict:
    import json

    return json.loads(p.read_text(encoding="utf-8"))
