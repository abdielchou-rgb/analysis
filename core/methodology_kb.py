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

# MKB 默认噪声标题词：backtest_gold 74% 是宏观/固收/资金面报告，对"个股/行业"
# 分析是无效弹药。行业标签缺失做通用兜底召回时必须过滤，否则"债券估值/基金持仓"
# 会混入写作者 prompt（2026-09-07 真实探针证实）。
_NOISE_TITLE_TERMS = (
    "债券",
    "固收",
    "利率",
    "央行",
    "缩表",
    "货币",
    "基金持仓",
    "公募基金",
    "流动性观察",
    "物价解读",
    "工业企业利润",
    "经济数据解读",
    "财政数据",
    "宏观前瞻",
    "宏观预测",
)

# 报告类型 → 行业标签缺失时的通用方法论兜底词（title/topic/methods 打分用）。
# 目标是把"公司估值/财务/风险"类方法论条目召回，而不是把 backtest_gold 的
# 宏观报告扫进来。
_TYPE_FALLBACK_TERMS = {
    "listed_company": ["估值", "盈利预测", "财务分析", "公司", "风险", "增长"],
    "unlisted_company": ["估值", "商业模式", "私募", "尽调", "退出", "风险"],
    "industry_deep": ["行业", "供需", "景气", "产业链", "竞争", "渗透率"],
    "earnings_notes": ["业绩", "盈利", "点评", "财务", "预测", "估值"],
    "decision_memo": ["估值", "尽调", "商业模式", "风险", "决策", "财务"],
}

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

# 报告类型 → 全库类别惩罚（行业标签缺失、走通用兜底时，抑制大而杂类别的淹没）
_TYPE_CATEGORY_PENALTY = {
    "listed_company": {"backtest_gold": 0.25, "industry_research": 0.75},
    "industry_deep": {"backtest_gold": 0.25},
    "unlisted_company": {"backtest_gold": 0.2, "research_reports": 0.5},
    "earnings_notes": {"backtest_gold": 0.5},
    "decision_memo": {"backtest_gold": 0.2},
}


def _load() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _has_substantive_content(entry: dict) -> bool:
    """过滤掉只有标题没有实质内容的条目。"""
    methods = str(entry.get("methods", ""))
    signals = str(entry.get("judgment_signals", ""))
    summary = str(entry.get("summary", ""))
    # 至少有一个字段包含 >80 字的实质内容
    return len(methods) > 80 or len(signals) > 60 or len(summary) > 100


def _score_entry(entry: dict, keywords: list[str], category: str = "", filter_noise: bool = False) -> float:
    """关键词命中评分：title 权重最高，topic 次之，methods/judgment_signals 再次。

    filter_noise=True 时，title/topic 命中宏观/固收噪声词（如"债券估值/基金持仓"）
    的条目直接得 0，确保通用兜底召回不把噪声弹药喂给写作者。
    """
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
    if filter_noise:
        _t = title + str(entry.get("topic", "")).lower()
        if any(term.lower() in _t for term in _NOISE_TITLE_TERMS):
            # 噪声条目即使命中关键词也整体排除（对固收/宏观类报告不适用——
            # 本系统的 report_type 面向公司/行业/私募，非债券宏观）。
            score = 0.0
    _ = category  # category-level penalty handled by caller（select_entries）
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
    filter_noise: bool = False,
) -> list[dict]:
    """按关键词相关性选择最相关的知识条目。

    filter_noise=True：对 title/topic 命中宏观/固收噪声词的条目降权
    （行业标签缺失的通用兜底召回应开启）。
    """
    kb = _load()
    if not kb:
        return []

    # 按 report_type 确定子类搜索顺序
    priority = _TYPE_PRIORITY.get(report_type, list(kb.keys()))
    scored: list[tuple[float, str, dict]] = []
    penalty = _TYPE_CATEGORY_PENALTY.get(report_type, {})

    for category in priority:
        entries = kb.get(category, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if not _has_substantive_content(entry):
                continue
            sc = _score_entry(entry, keywords, category=category, filter_noise=filter_noise)
            sc *= penalty.get(category, 1.0)
            if sc > 0:
                scored.append((sc, category, entry))

    scored.sort(key=lambda x: -x[0])
    return [e for _, _, e in scored[:max_items]]


def format_block(entries: list[dict], max_chars: int | None = None) -> str:
    """将选中条目格式化为 prompt 注入块。

    max_chars: 块级预算（与写作侧 mkb_str[:2000] 截断对齐）。条目按传入顺序
    整条纳入，放不下的尾部条目整体丢弃——绝不半截截断，避免"检索到了但
    内容被切掉"。
    """
    if not entries:
        return ""
    header = "## [方法论知识库精选] 以下来自内部券商研报/估值模型知识库（结构化提取），供分析框架与方法论参考："
    parts: list[str] = [header]
    used = len(header)
    for i, e in enumerate(entries, 1):
        blk = _format_entry(e, i)
        cost = len(blk) + 1  # 行尾换行
        if max_chars is not None and used + cost > max_chars:
            break
        parts.append(blk)
        used += cost
    return "\n".join(parts)


def build_block(
    keywords: list[str],
    report_type: str = "",
    max_items: int = 8,
    max_chars: int | None = None,
    filter_noise: bool = False,
) -> str:
    """主入口：选条目 + 格式化。max_chars 交给 format_block 做整块预算。"""
    entries = select_entries(keywords, report_type, max_items, filter_noise=filter_noise)
    return format_block(entries, max_chars=max_chars)
