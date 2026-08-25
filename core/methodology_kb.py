# -*- coding: utf-8 -*-
"""methodology_kb.py — K-08：methodology_knowledge_base.json 解析器 + 选择器。

从 2524 条结构化知识条目中按 report_type/industry 关键词选择最相关的
top-N 条目，格式化为写作 prompt 注入块。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("2hao.mkb")

_FILE = Path(__file__).resolve().parent.parent / "data" / "methodology_knowledge_base.json"

# 报告类型 → 最相关的子类优先级
_TYPE_PRIORITY = {
    "listed_company": [
        "valuation_models",
        "research_reports",
        "backtest_gold",
        "industry_research",
        "valuation_methods",
    ],
    "industry_deep": ["industry_research", "backtest_gold", "deep_reports", "research_reports"],
    "unlisted_company": ["valuation_methods", "excel_models", "deep_reports", "backtest_baseline"],
    "earnings_notes": ["research_reports", "backtest_gold", "valuation_models"],
    "decision_memo": ["deep_reports", "valuation_methods", "industry_research"],
}


def _load() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _score_entry(entry: dict, keywords: list[str]) -> float:
    """关键词命中评分：title 权重最高，topic 次之，methods/judgment_signals 再次。"""
    score = 0.0
    title = str(entry.get("title", "")).lower()
    topic = str(entry.get("topic", "")).lower()
    methods = str(entry.get("methods", "")).lower()
    signals = str(entry.get("judgment_signals", "")).lower()

    for kw in keywords:
        kl = kw.lower()
        if kl in title:
            score += 3.0
        if kl in topic:
            score += 2.0
        if kl in methods:
            score += 1.0
        if kl in signals:
            score += 0.5
    return score


def _format_entry(entry: dict, idx: int) -> str:
    lines = [f"[MKB{idx}] {entry.get('title', 'untitled')}"]
    topic = entry.get("topic", "")
    if topic:
        lines.append(f"  主题: {topic}")
    methods = entry.get("methods", "")
    if methods:
        # 截取方法列表的核心部分
        method_lines = [m.strip() for m in str(methods).split("\n") if m.strip()]
        for ml in method_lines[:4]:
            if len(ml) > 5:
                lines.append(f"  方法: {ml[:150]}")
    signals = entry.get("judgment_signals", "")
    if signals:
        sig_lines = [s.strip() for s in str(signals).split("\n") if s.strip()]
        for sl in sig_lines[:3]:
            if len(sl) > 5:
                lines.append(f"  判断信号: {sl[:150]}")
    summary = entry.get("summary", "")
    if summary:
        lines.append(f"  摘要: {str(summary)[:200]}")
    return "\n".join(lines)


def select_entries(
    keywords: list[str],
    report_type: str = "",
    max_items: int = 8,
) -> list[dict]:
    """按关键词相关性选择最相关的知识条目。"""
    kb = _load()
    if not kb:
        return []

    # 按 report_type 确定子类搜索顺序
    priority = _TYPE_PRIORITY.get(report_type, list(kb.keys()))
    scored: list[tuple[float, str, dict]] = []

    for category in priority:
        entries = kb.get(category, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            sc = _score_entry(entry, keywords)
            if sc > 0:
                scored.append((sc, category, entry))

    scored.sort(key=lambda x: -x[0])
    return [e for _, _, e in scored[:max_items]]


def format_block(entries: list[dict]) -> str:
    """将选中条目格式化为 prompt 注入块。"""
    if not entries:
        return ""
    lines = ["## [方法论知识库精选] 以下来自内部券商研报/估值模型知识库（结构化提取），供分析框架与方法论参考："]
    for i, e in enumerate(entries, 1):
        lines.append(_format_entry(e, i))
    return "\n".join(lines)


def build_block(keywords: list[str], report_type: str = "", max_items: int = 8) -> str:
    """主入口：选条目 + 格式化。"""
    entries = select_entries(keywords, report_type, max_items)
    return format_block(entries)
