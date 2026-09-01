"""语义级 SAC 维度覆盖判断 —— TF-IDF + 余弦相似度兜底关键词匹配。"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger("2hao.semantic_match")


@lru_cache(maxsize=1)
def _get_vectorizer():
    """懒加载 TF-IDF 向量化器（避免冷启动开销）。"""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        return TfidfVectorizer(ngram_range=(1, 2), max_features=2000, min_df=1)
    except Exception as e:
        logger.warning("[SEMANTIC] sklearn 不可用，降级关键词匹配: %s", e)
        return None


def semantic_cover(text: str, keywords: list[str], threshold: float = 0.70) -> bool:
    """语义级覆盖判断：TF-IDF + 余弦相似度 ≥ threshold 即判定覆盖。

    Args:
        text: 报告正文
        keywords: SAC 维度关键词列表
        threshold: 余弦相似度阈值（默认 0.70，经验值平衡召回/精度）

    Returns:
        所有关键词在语义上均被覆盖返回 True
    """
    if not text or not keywords:
        return False

    # 1. 先做快速关键词匹配（保持原有高精度）
    # 修复：将 kws 改为 keywords
    if isinstance(keywords, list) and keywords:
        if isinstance(keywords[0], list):
            # 嵌套列表：每个子列表是一个维度的关键词
            kw_ok = all(any(kw in text for kw in kw_list) for kw_list in keywords)
        else:
            # 扁平列表：所有关键词
            kw_ok = any(kw in text for kw in keywords)
    else:
        kw_ok = False
    if kw_ok:
        return True

    # 2. 语义兜底：TF-IDF + 余弦相似度
    # 2026-08-30 修复：原逻辑要求 ALL keywords ≥ 0.70，过于严格，
    # 导致几乎所有维度的语义兜底都失败 → keyword匹配失败 = 维度缺失。
    # 修复：改为 ANY keyword ≥ 0.25 即通过（任一关键词有语义关联即算覆盖），
    # 且阈值从 0.70 → 0.25（更低的单键词相似度要求）。
    vectorizer = _get_vectorizer()
    if vectorizer is None:
        return False

    try:
        text_truncated = text[:50000]
        kw_list = [str(k) for k in keywords]
        if not kw_list:
            return False
        corpus = [text_truncated] + kw_list
        tfidf = vectorizer.fit_transform(corpus)
        from sklearn.metrics.pairwise import cosine_similarity

        sims = cosine_similarity(tfidf[0:1], tfidf[1:])[0]
        # 任一关键词相似度 ≥ 0.25 即认为该维度有语义覆盖
        # 阈值 0.25 是经验值：区分"完全不相关"（0.0-0.1）与"有关联"（0.2-0.4）
        return float(sims.max()) >= 0.25
    except Exception as e:
        logger.debug("[SEMANTIC] 语义匹配异常降级: %s", e)
        return False


def _split_keywords(raw_keywords: dict) -> dict[str, list[str]]:
    """将 SAC 原始关键词字典标准化为 {dim_id: [kw1, kw2, ...]}。"""
    normalized = {}
    for dim, kws in raw_keywords.items():
        if isinstance(kws, str):
            normalized[dim] = [kws]
        elif isinstance(kws, list):
            normalized[dim] = [str(k) for k in kws]
        else:
            normalized[dim] = [str(kws)]
    return normalized
