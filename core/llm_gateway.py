# -*- coding: utf-8 -*-
"""LLM Gateway - 统一 LLM 调用网关

核心功能：
- 统一 LLM 调用接口
- 分层缓存：内存 + 磁盘 + 语义缓存
- 概率预算：基于 token 概率的预算控制
- Provider 自动故障转移
- 请求去重与批处理
"""

from __future__ import annotations

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Tuple, Set
from dataclasses import dataclass, field
import asyncio
import hashlib
import json
import time
import pickle
import os
from pathlib import Path
from collections import defaultdict, OrderedDict
import asyncio

from core.analysis_engine import ExecutionMode
from core.principles.types import Value, DataState


class ProviderType(Enum):
    DEEPSEEK = "deepseek"
    ZHIPU = "zhipu"
    OPENROUTER = "openrouter"
    OPENDOVE = "opencove"
    OLLAMA = "ollama"
    OPENDOE = "opendeepseek"
    AGENT_PROVIDER = "agent_provider"


class CacheLevel(Enum):
    MEMORY = "memory"
    DISK = "disk"
    SEMANTIC = "semantic"  # 语义缓存：基于 embedding 相似度


@dataclass(frozen=True)
class LLMConfig:
    """LLM 调用配置"""
    provider: ProviderType = ProviderType.DEEPSEEK
    model: str = "deepseek-chat"
    temperature: float = 0.35
    max_tokens: int = 10000
    top_p: float = 0.95
    timeout: float = 60.0
    max_retries: int = 2
    response_format: Optional[str] = None  # "json", "text", etc.
    system_prompt: str = ""
    enable_cache: bool = True
    cache_ttl: int = 3600  # 秒


@dataclass(frozen=True)
class LLMRequest:
    """LLM 请求"""
    prompt: str
    config: LLMConfig = field(default_factory=LLMConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:16])
    timestamp: datetime = field(default_factory=datetime.now)
    
    def cache_key(self) -> str:
        """生成缓存键"""
        content = f"{self.config.provider.value}:{self.config.model}:{self.config.temperature}:{self.prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class LLMResponse:
    """LLM 响应"""
    request_id: str
    content: str
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    provider: ProviderType = ProviderType.DEEPSEEK
    model: str = ""
    cached: bool = False
    cache_level: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    response: LLMResponse
    created_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    ttl: int = 3600
    
    def is_expired(self) -> bool:
        return datetime.now() - self.created_at > timedelta(seconds=self.ttl)
    
    def touch(self):
        self.access_count += 1
        self.last_accessed = datetime.now()


class SemanticCache:
    """语义缓存 - 基于 embedding 相似度的缓存"""
    
    def __init__(self, similarity_threshold: float = 0.95, max_size: int = 1000):
        self.similarity_threshold = similarity_threshold
        self.max_size = max_size
        self._entries: List[Tuple[str, List[float], LLMResponse]] = []  # (prompt, embedding, response)
        self._embedding_fn: Optional[Callable] = None
    
    def set_embedding_fn(self, fn: Callable[[str], List[float]]):
        self._embedding_fn = fn
    
    def _get_embedding(self, text: str) -> List[float]:
        if self._embedding_fn:
            return self._embedding_fn(text)
        # 简单的词袋 embedding 作为 fallback
        words = set(text.lower().split())
        return [float(w in words) for w in sorted(list(words))[:100]]
    
    def get(self, prompt: str) -> Optional[LLMResponse]:
        if not self._embedding_fn:
            return None
        
        embedding = self._get_embedding(text)
        best_match = None
        best_score = 0.0
        
        for stored_prompt, stored_embedding, response in self._entries:
            score = self._cosine_similarity(embedding, stored_embedding)
            if score > self.similarity_threshold and score > best_score:
                best_score = score
                best_match = response
        
        return best_match
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
    
    def put(self, prompt: str, response: LLMResponse):
        if not self._embedding_fn:
            return
        embedding = self._get_embedding(response.request_id)  # 使用 request_id 作为标识
        self._entries.append((response.request_id, embedding, response))
        if len(self._entries) > self.max_size:
            self._entries.pop(0)  # FIFO 淘汰


class ProbabilisticBudget:
    """概率预算管理器 - 基于 token 概率分布的预算控制"""
    
    def __init__(
        self,
        total_budget: float = 100000,  # token 预算
        p50_budget: float = 50000,     # P50 预算
        p95_budget: float = 90000,     # P95 预算
    ):
        self.total_budget = total_budget
        self.p50_budget = p50_budget
        self.p95_budget = p95_budget
        self.consumed = 0.0
        self._consumption_history: List[float] = []
    
    def allocate(self, estimated_tokens: int, confidence: float = 0.95) -> Tuple[bool, float]:
        """分配预算，返回 (是否通过, 剩余预算)"""
        # 使用分位数估算
        estimated_p95 = estimated_tokens * (1 + (1 - confidence) * 2)
        
        if self.consumed + estimated_p95 > self.p95_budget:
            return False, self.p95_budget - self.consumed
        
        return True, self.p95_budget - self.consumed - estimated_p95
    
    def consume(self, actual_tokens: int):
        self.consumed += actual_tokens
        self._consumption_history.append(actual_tokens)
    
    def get_remaining(self) -> float:
        return self.p95_budget - self.consumed
    
    def get_stats(self) -> Dict[str, float]:
        if not self._consumption_history:
            return {"mean": 0, "p50": 0, "p95": 0, "total": self.consumed}
        
        sorted_history = sorted(self._consumption_history)
        n = len(sorted_history)
        return {
            "mean": sum(sorted_history) / n,
            "p50": sorted_history[n // 2],
            "p95": sorted_history[int(n * 0.95)],
            "total": self.consumed,
        }


class LLMCache:
    """多层 LLM 缓存"""
    
    def __init__(self, memory_size: int = 1000, disk_dir: str = "cache/llm", ttl: int = 3600):
        self.memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.max_memory_size = memory_size
        self.disk_dir = Path(disk_dir)
        self.disk_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.semantic_cache = SemanticCache()
    
    def _get_memory(self, key: str) -> Optional[LLMResponse]:
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if not entry.is_expired():
                entry.touch()
                # 移到末尾 (LRU)
                self.memory_cache.move_to_end(key)
                return entry.response
            else:
                del self.memory_cache[key]
        return None
    
    def _get_disk(self, key: str) -> Optional[LLMResponse]:
        path = self.disk_dir / f"{key}.pkl"
        if path.exists():
            try:
                with open(path, "rb") as f:
                    entry = pickle.load(f)
                if not entry.is_expired():
                    entry.touch()
                    # 回写到内存
                    self.memory_cache[key] = entry
                    return entry.response
                else:
                    path.unlink()
            except Exception:
                pass
        return None
    
    def _save_to_disk(self, key: str, entry: CacheEntry):
        path = self.disk_dir / f"{key}.pkl"
        try:
            with open(path, "wb") as f:
                pickle.dump(entry, f)
        except Exception:
            pass
    
    def get(self, key: str) -> Optional[LLMResponse]:
        # 1. 内存缓存
        resp = self._get_memory(key)
        if resp:
            return resp
        
        # 2. 磁盘缓存
        resp = self._get_disk(key)
        if resp:
            return resp
        
        # 3. 语义缓存
        # 注意：语义缓存需要 prompt 文本，这里只能通过 key 反查，较难实现
        return None
    
    def put(self, key: str, response: LLMResponse, ttl: Optional[int] = None):
        entry = CacheEntry(
            key=key,
            response=response,
            ttl=ttl or 3600
        )
        # 内存缓存 (LRU)
        self.memory_cache[key] = entry
        if len(self.memory_cache) > self.max_memory_size:
            self.memory_cache.popitem(last=False)
        
        # 磁盘缓存
        self._save_to_disk(key, entry)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "memory_size": len(self.memory_cache),
            "disk_files": len(list(self.disk_dir.glob("*.pkl"))),
            "semantic_size": 0,  # TODO
        }
    
    def clear_expired(self):
        # 清理过期内存缓存
        expired = [k for k, v in self.memory_cache.items() if v.is_expired()]
        for k in expired:
            del self.memory_cache[k]


class ProviderRouter:
    """Provider 路由器 - 自动故障转移"""
    
    def __init__(self):
        self.providers: List[ProviderType] = [
            ProviderType.DEEPSEEK,
            ProviderType.ZHIPU,
            ProviderType.OPENROUTER,
            ProviderType.OPENDOVE,
            ProviderType.OLLAMA,
            ProviderType.AGENT_PROVIDER,
        ]
        self._failures: Dict[ProviderType, int] = defaultdict(int)
        self._last_failure: Dict[ProviderType, datetime] = {}
        self._circuit_open: Dict[ProviderType, bool] = {}
        self._circuit_threshold = 3
        self._circuit_timeout = 300  # 5分钟
    
    def get_available(self) -> List[ProviderType]:
        """获取可用的 provider 列表"""
        available = []
        for p in self.providers:
            if self._is_available(p):
                available.append(p)
        return available
    
    def _is_available(self, provider: ProviderType) -> bool:
        if self._circuit_open.get(provider, False):
            # 检查是否超时恢复
            last_fail = self._last_failure.get(provider)
            if last_fail and datetime.now() - last_fail > timedelta(seconds=self._circuit_timeout):
                self._circuit_open[provider] = False
                self._failures[provider] = 0
                return True
            return False
        return True
    
    def record_success(self, provider: ProviderType):
        self._failures[provider] = 0
        self._circuit_open[provider] = False
    
    def record_failure(self, provider: ProviderType):
        self._failures[provider] += 1
        self._last_failure[provider] = datetime.now()
        if self._failures[provider] >= self._circuit_threshold:
            self._circuit_open[provider] = True
            logger.warning(f"Provider {provider.value} circuit opened after {self._circuit_threshold} failures")


class ProbabilisticBudget:
    """概率预算管理器"""
    
    def __init__(
        self,
        total_budget: float = 100000,
        p50_budget: float = 50000,
        p95_budget: float = 90000,
    ):
        self.total_budget = total_budget
        self.p50_budget = p50_budget
        self.p95_budget = p95_budget
        self.consumed = 0.0
        self._history: List[float] = []
    
    def allocate(self, estimated_tokens: int, confidence: float = 0.95) -> Tuple[bool, float]:
        """分配预算，返回 (是否通过, 剩余预算)"""
        # P95 估算 = estimated * (1 + (1-confidence) * 2)
        estimated_p95 = estimated_tokens * (1 + (1 - confidence) * 2)
        
        if self.consumed + estimated_p95 > self.p95_budget:
            return False, self.p95_budget - self.consumed
        
        return True, self.p95_budget - self.consumed - estimated_p95
    
    def consume(self, actual_tokens: int):
        self.consumed += actual_tokens
        self._history.append(actual_tokens)
    
    def get_remaining(self) -> float:
        return self.p95_budget - self.consumed
    
    def get_stats(self) -> Dict[str, float]:
        if not self._history:
            return {"mean": 0, "p50": 0, "p95": 0, "total": self.consumed}
        
        sorted_hist = sorted(self._history)
        n = len(sorted_hist)
        return {
            "mean": sum(sorted_hist) / n,
            "p50": sorted_hist[n // 2],
            "p95": sorted_hist[int(n * 0.95)],
            "total": self.consumed,
        }


class LLMGateway:
    """LLM 统一网关"""
    
    def __init__(
        self,
        default_config: Optional[LLMConfig] = None,
        cache: Optional[LLMCache] = None,
        router: Optional[ProviderRouter] = None,
        budget: Optional[ProbabilisticBudget] = None,
    ):
        self.default_config = default_config or LLMConfig()
        self.cache = cache or LLMCache()
        self.router = router or ProviderRouter()
        self.budget = budget or ProbabilisticBudget()
        self._call_count = 0
        self._total_tokens = 0
        self._total_latency = 0.0
        self._errors = 0
    
    async def call(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
        use_cache: bool = True,
    ) -> LLMResponse:
        """统一 LLM 调用入口"""
        config = config or self.default_config
        self._call_count += 1
        
        # 1. 检查预算
        if config.max_tokens:
            ok, remaining = self._budget.allocate(config.max_tokens)
            if not ok:
                return LLMResponse(
                    request_id="",
                    content="",
                    error=f"Budget exceeded: remaining {remaining:.0f} tokens",
                    error_code="BUDGET_EXCEEDED"
                )
        
        # 2. 生成缓存键
        cache_key = None
        if use_cache and config.enable_cache:
            req = LLMRequest(prompt=prompt, config=config)
            cache_key = req.cache_key()
            
            # 尝试缓存
            cached = self._cache.get(cache_key)
            if cached:
                cached.cached = True
                cached.cache_level = "memory"
                return cached
        
        # 3. 选择 Provider
        provider = self._select_provider(config)
        
        # 3. 执行调用
        start = time.time()
        response = await self._call_provider(provider, prompt, config)
        latency = int((time.time() - start) * 1000)
        
        # 4. 更新统计
        self._call_count += 1
        self._total_tokens += response.tokens_used
        self._total_latency += latency
        if response.error:
            self._errors += 1
        
        # 5. 记录消费
        self._budget.consume(response.tokens_used)
        
        # 6. 缓存结果
        if use_cache and config.enable_cache and not response.error:
            self._cache.put(cache_key, response)
        
        response.latency_ms = latency
        return response
    
    async def _call_provider(
        self,
        provider: ProviderType,
        prompt: str,
        config: LLMConfig
    ) -> LLMResponse:
        """实际调用 Provider"""
        # 这里应该根据 provider 调用不同的 API
        # 简化实现：统一走 deepseek 兼容接口
        from core.deepseek_client import call_deepseek
        
        try:
            result = call_deepseek(
                messages=[{"role": "user", "content": prompt}],
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                provider=provider.value if provider != ProviderType.DEEPSEEK else "deepseek",
                timeout=config.timeout,
            )
            
            content = result["choices"][0]["message"]["content"]
            tokens = result.get("usage", {}).get("total_tokens", 0)
            
            return LLMResponse(
                request_id=hashlib.sha256(prompt.encode()).hexdigest()[:16],
                content=content,
                tokens_used=tokens,
                provider=provider,
                model=config.model,
            )
        except Exception as e:
            return LLMResponse(
                request_id="",
                content="",
                error=str(e),
                provider=provider,
            )
    
    def _select_provider(self, config: LLMConfig) -> ProviderType:
        """选择 Provider"""
        if config.provider != ProviderType.DEEPSEEK:
            # 显式指定的 provider
            if self._router._is_available(config.provider):
                return config.provider
        
        # 自动选择
        available = self.router.get_available()
        if available:
            return available[0]
        return ProviderType.DEEPSEEK
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_calls": self._call_count,
            "total_tokens": self._total_tokens,
            "avg_latency_ms": self._total_latency / max(1, self._call_count),
            "error_rate": self._errors / max(1, self._call_count),
            "cache_stats": self._cache.get_stats(),
            "budget_stats": self.budget.get_stats(),
            "router_failures": dict(self.router._failures),
        }
    
    def reset_stats(self):
        self._call_count = 0
        self._total_tokens = 0
        self._total_latency = 0.0
        self._errors = 0


# 全局实例
_global_gateway = None

def get_llm_gateway() -> LLMGateway:
    global _global_gateway
    if _global_gateway is None:
        _global_gateway = LLMGateway()
    return _global_gateway


# 便捷函数
async def call_llm(
    prompt: str,
    config: Optional[LLMConfig] = None,
    use_cache: bool = True,
) -> LLMResponse:
    """便捷函数：调用 LLM"""
    gateway = get_llm_gateway()
    return await gateway.call(prompt, config, use_cache)