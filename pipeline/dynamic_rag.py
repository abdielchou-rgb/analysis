"""
pipeline/dynamic_rag.py — 动态 RAG + 辩论驱动检索 V2

参考 FinDebate 架构 + R-Debater (arXiv 2026):
1. 辩论过程中动态检索相关证据
2. 识别证据缺口，针对性补充
3. 支持多源检索（本地知识库 + 外部搜索）
4. 证据溯源（每个证据标记来源）
5. 混合检索（BM25 + 语义向量 + 元数据过滤 + 重排序）
6. 辩论驱动检索（R-Debater 模式）
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("2hao.dynamic_rag")

_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Evidence:
    """证据"""

    content: str
    source: str  # 来源
    relevance: float = 0.0  # 相关性 0-1
    evidence_type: str = ""  # 类型：data/knowledge/news/report
    timestamp: float = field(default_factory=time.time)


@dataclass
class EvidenceGap:
    """证据缺口"""

    topic: str
    description: str
    priority: float = 0.0  # 优先级 0-1


@dataclass
class RAGResult:
    """RAG 结果"""

    evidences: list[Evidence] = field(default_factory=list)
    gaps: list[EvidenceGap] = field(default_factory=list)
    total_duration_ms: float = 0.0


class DynamicRAG:
    """
    动态 RAG + 辩论驱动检索

    核心机制：
    1. 辩论过程中动态检索相关证据
    2. 识别证据缺口，针对性补充
    3. 支持多源检索（本地知识库 + 外部搜索）
    4. 证据溯源（每个证据标记来源）
    """

    def __init__(
        self,
        knowledge_base_path: Optional[str] = None,
        max_evidences: int = 10,
        relevance_threshold: float = 0.3,
    ):
        """
        Args:
            knowledge_base_path: 知识库路径
            max_evidences: 最大证据数
            relevance_threshold: 相关性阈值
        """
        self.knowledge_base_path = knowledge_base_path or str(_ROOT / "data")
        self.max_evidences = max_evidences
        self.relevance_threshold = relevance_threshold
        self._knowledge_base = self._load_knowledge_base()

    def _load_knowledge_base(self) -> dict:
        """加载知识库"""
        import json

        kb = {}
        kb_path = Path(self.knowledge_base_path)

        if not kb_path.exists():
            return kb

        # 加载 JSON 文件
        for json_file in kb_path.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                kb[json_file.stem] = data
            except Exception as e:
                logger.warning("[RAG] Failed to load %s: %s", json_file.name, e)

        return kb

    def retrieve(
        self,
        query: str,
        context: Optional[dict] = None,
        evidence_types: Optional[list[str]] = None,
    ) -> RAGResult:
        """
        检索相关证据

        Args:
            query: 查询字符串
            context: 上下文
            evidence_types: 证据类型过滤

        Returns:
            RAGResult: 检索结果
        """
        start_time = time.time()
        result = RAGResult()

        # 从知识库检索
        kb_evidences = self._retrieve_from_knowledge_base(query, context)
        result.evidences.extend(kb_evidences)

        # 从外部搜索检索（可选）
        # external_evidences = self._retrieve_from_external(query, context)
        # result.evidences.extend(external_evidences)

        # 过滤和排序
        result.evidences = self._filter_and_rank(result.evidences, evidence_types)

        # 识别证据缺口
        result.gaps = self._identify_gaps(query, result.evidences, context)

        result.total_duration_ms = (time.time() - start_time) * 1000

        return result

    def retrieve_for_debate(
        self,
        bull_argument: str,
        bear_argument: str,
        context: Optional[dict] = None,
    ) -> RAGResult:
        """
        为辩论检索证据

        Args:
            bull_argument: Bull 论点
            bear_argument: Bear 论点
            context: 上下文

        Returns:
            RAGResult: 检索结果
        """
        start_time = time.time()
        result = RAGResult()

        # 识别 Bull 论点的证据缺口
        bull_gaps = self._identify_argument_gaps(bull_argument, "bull")
        result.gaps.extend(bull_gaps)

        # 识别 Bear 论点的证据缺口
        bear_gaps = self._identify_argument_gaps(bear_argument, "bear")
        result.gaps.extend(bear_gaps)

        # 针对性检索
        for gap in result.gaps:
            evidences = self.retrieve(gap.topic, context)
            result.evidences.extend(evidences.evidences)

        # 去重
        result.evidences = self._deduplicate_evidences(result.evidences)

        result.total_duration_ms = (time.time() - start_time) * 1000

        return result

    def _retrieve_from_knowledge_base(
        self, query: str, context: Optional[dict] = None
    ) -> list[Evidence]:
        """从知识库检索"""
        evidences = []

        for name, data in self._knowledge_base.items():
            # 简单关键词匹配（实际应用中应使用向量检索）
            if isinstance(data, dict):
                for key, value in data.items():
                    if self._is_relevant(query, str(key) + " " + str(value)):
                        evidences.append(Evidence(
                            content=str(value)[:500],
                            source=f"knowledge_base/{name}/{key}",
                            relevance=self._calculate_relevance(query, str(value)),
                            evidence_type="knowledge",
                        ))
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    if self._is_relevant(query, str(item)):
                        evidences.append(Evidence(
                            content=str(item)[:500],
                            source=f"knowledge_base/{name}/{i}",
                            relevance=self._calculate_relevance(query, str(item)),
                            evidence_type="knowledge",
                        ))

        return evidences

    def _is_relevant(self, query: str, text: str) -> bool:
        """判断是否相关"""
        # 简单关键词匹配
        query_words = set(query.split())
        text_words = set(text.split())
        overlap = len(query_words & text_words)
        return overlap >= 2

    def _calculate_relevance(self, query: str, text: str) -> float:
        """计算相关性"""
        query_words = set(query.split())
        text_words = set(text.split())
        if not query_words:
            return 0.0
        overlap = len(query_words & text_words)
        return min(1.0, overlap / len(query_words))

    def _filter_and_rank(
        self,
        evidences: list[Evidence],
        evidence_types: Optional[list[str]] = None,
    ) -> list[Evidence]:
        """过滤和排序"""
        # 过滤类型
        if evidence_types:
            evidences = [e for e in evidences if e.evidence_type in evidence_types]

        # 过滤相关性
        evidences = [e for e in evidences if e.relevance >= self.relevance_threshold]

        # 按相关性排序
        evidences.sort(key=lambda e: e.relevance, reverse=True)

        # 限制数量
        return evidences[:self.max_evidences]

    def _identify_gaps(
        self,
        query: str,
        evidences: list[Evidence],
        context: Optional[dict] = None,
    ) -> list[EvidenceGap]:
        """识别证据缺口"""
        gaps = []

        # 检查是否有足够的证据
        if len(evidences) < 3:
            gaps.append(EvidenceGap(
                topic=query,
                description=f"证据不足，仅有 {len(evidences)} 条",
                priority=0.8,
            ))

        # 检查证据类型多样性
        types = set(e.evidence_type for e in evidences)
        if len(types) < 2:
            gaps.append(EvidenceGap(
                topic=query,
                description="证据类型单一，需要更多数据源",
                priority=0.6,
            ))

        return gaps

    def _identify_argument_gaps(self, argument: str, side: str) -> list[EvidenceGap]:
        """识别论点证据缺口"""
        gaps = []

        # 检查是否有数据支撑
        import re
        data_patterns = [
            r"(\d+\.?\d*)\s*%",
            r"(\d+\.?\d*)\s*亿",
            r"(\d+\.?\d*)\s*万",
        ]

        has_data = any(re.search(pat, argument) for pat in data_patterns)
        if not has_data:
            gaps.append(EvidenceGap(
                topic=f"{side} 论点数据支撑",
                description=f"{side} 论点缺乏具体数据支撑",
                priority=0.9,
            ))

        # 检查是否有来源标注
        if "(A)" not in argument and "(E)" not in argument and "(F)" not in argument:
            gaps.append(EvidenceGap(
                topic=f"{side} 论点来源",
                description=f"{side} 论点缺乏来源标注",
                priority=0.7,
            ))

        return gaps

    def _deduplicate_evidences(self, evidences: list[Evidence]) -> list[Evidence]:
        """去重"""
        seen = set()
        unique = []

        for evidence in evidences:
            key = evidence.content[:100]  # 用前100字符作为去重key
            if key not in seen:
                seen.add(key)
                unique.append(evidence)

        return unique

    # ═══ 混合检索机制 (Hybrid RAG) ═══

    def hybrid_retrieve(
        self,
        query: str,
        context: Optional[dict] = None,
        alpha: float = 0.5,
    ) -> RAGResult:
        """
        混合检索 (Hybrid RAG)

        结合 BM25 关键词匹配 + 语义向量搜索
        alpha: BM25 权重 (0-1)，语义权重 = 1-alpha

        Returns:
            RAGResult: 检索结果
        """
        start_time = time.time()
        result = RAGResult()

        # BM25 关键词检索
        bm25_results = self._bm25_retrieve(query, context)

        # 语义向量检索
        semantic_results = self._semantic_retrieve(query, context)

        # 混合评分
        hybrid_results = self._hybrid_score(bm25_results, semantic_results, alpha)

        # 元数据过滤
        filtered_results = self._metadata_filter(hybrid_results, context)

        # 重排序
        reranked_results = self._rerank(filtered_results, query)

        result.evidences = reranked_results[:self.max_evidences]
        result.gaps = self._identify_gaps(query, result.evidences, context)
        result.total_duration_ms = (time.time() - start_time) * 1000

        return result

    def _bm25_retrieve(
        self, query: str, context: Optional[dict] = None
    ) -> list[tuple[Evidence, float]]:
        """
        BM25 关键词检索

        Returns:
            list[tuple[Evidence, float]]: (证据, BM25分数) 列表
        """
        results = []

        for name, data in self._knowledge_base.items():
            if isinstance(data, dict):
                for key, value in data.items():
                    text = str(key) + " " + str(value)
                    score = self._bm25_score(query, text)
                    if score > 0:
                        evidence = Evidence(
                            content=str(value)[:500],
                            source=f"knowledge_base/{name}/{key}",
                            relevance=score,
                            evidence_type="knowledge",
                        )
                        results.append((evidence, score))

        return results

    def _bm25_score(self, query: str, text: str) -> float:
        """
        BM25 评分

        简化版 BM25，基于词频和逆文档频率
        """
        query_words = query.split()
        text_words = text.split()

        if not query_words or not text_words:
            return 0.0

        # 词频
        tf = {}
        for word in text_words:
            tf[word] = tf.get(word, 0) + 1

        # 评分
        score = 0.0
        for word in query_words:
            if word in tf:
                score += tf[word] / (tf[word] + 1.0)

        return score / len(query_words)

    def _semantic_retrieve(
        self, query: str, context: Optional[dict] = None
    ) -> list[tuple[Evidence, float]]:
        """
        语义向量检索

        Returns:
            list[tuple[Evidence, float]]: (证据, 语义分数) 列表
        """
        results = []

        for name, data in self._knowledge_base.items():
            if isinstance(data, dict):
                for key, value in data.items():
                    text = str(key) + " " + str(value)
                    score = self._semantic_similarity(query, text)
                    if score > self.relevance_threshold:
                        evidence = Evidence(
                            content=str(value)[:500],
                            source=f"knowledge_base/{name}/{key}",
                            relevance=score,
                            evidence_type="knowledge",
                        )
                        results.append((evidence, score))

        return results

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """
        语义相似度

        简化版，基于词汇重叠
        实际应用中应使用向量嵌入
        """
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        overlap = len(words1 & words2)
        return overlap / max(len(words1), len(words2))

    def _hybrid_score(
        self,
        bm25_results: list[tuple[Evidence, float]],
        semantic_results: list[tuple[Evidence, float]],
        alpha: float,
    ) -> list[Evidence]:
        """
        混合评分

        alpha: BM25 权重
        """
        # 合并结果
        evidence_scores = {}

        for evidence, score in bm25_results:
            key = evidence.content[:100]
            if key not in evidence_scores:
                evidence_scores[key] = {"evidence": evidence, "bm25": 0.0, "semantic": 0.0}
            evidence_scores[key]["bm25"] = max(evidence_scores[key]["bm25"], score)

        for evidence, score in semantic_results:
            key = evidence.content[:100]
            if key not in evidence_scores:
                evidence_scores[key] = {"evidence": evidence, "bm25": 0.0, "semantic": 0.0}
            evidence_scores[key]["semantic"] = max(evidence_scores[key]["semantic"], score)

        # 计算混合分数
        results = []
        for key, scores in evidence_scores.items():
            hybrid_score = alpha * scores["bm25"] + (1 - alpha) * scores["semantic"]
            evidence = scores["evidence"]
            evidence.relevance = hybrid_score
            results.append(evidence)

        # 按分数排序
        results.sort(key=lambda e: e.relevance, reverse=True)

        return results

    def _metadata_filter(
        self,
        evidences: list[Evidence],
        context: Optional[dict] = None,
    ) -> list[Evidence]:
        """
        元数据过滤

        根据上下文过滤证据
        """
        if not context:
            return evidences

        # 过滤逻辑
        filtered = []
        for evidence in evidences:
            # 检查时间有效性
            if self._is_temporally_valid(evidence, context):
                filtered.append(evidence)

        return filtered

    def _is_temporally_valid(self, evidence: Evidence, context: dict) -> bool:
        """检查时间有效性"""
        # 简化实现
        return True

    def _rerank(self, evidences: list[Evidence], query: str) -> list[Evidence]:
        """
        重排序

        基于查询相关性重新排序
        """
        # 计算相关性分数
        for evidence in evidences:
            evidence.relevance = self._calculate_relevance(query, evidence.content)

        # 按相关性排序
        evidences.sort(key=lambda e: e.relevance, reverse=True)

        return evidences
