"""
智能 LLM 路由器 — 成本感知 + 信用追踪 + 自动降级

优先级：
1. OpenRouter 免费模型（$10 信用）
2. OpenCode Zen 免费模型（$20 信用）
3. DeepSeek（付费兜底）

特性：
- 信用余额追踪（本地持久化）
- 按任务类型选择最优模型
- 熔断器 + 指数退避
- 成本日志 + 可观测性
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.smart_router")

# ── 信用配置 ─────────────────────────────────────────────────


@dataclass
class CreditBalance:
    """Provider 信用余额"""

    provider: str
    total_cents: int  # 总额度（美分）
    used_cents: int = 0  # 已用额度
    last_updated: float = 0.0  # 最后更新时间戳

    @property
    def remaining_cents(self) -> int:
        return self.total_cents - self.used_cents

    @property
    def remaining_usd(self) -> float:
        return self.remaining_cents / 100.0

    @property
    def usage_pct(self) -> float:
        return (self.used_cents / self.total_cents * 100) if self.total_cents > 0 else 0

    def is_exhausted(self, threshold_pct: float = 95.0) -> bool:
        """检查信用是否已耗尽（默认 95% 阈值）"""
        return self.usage_pct >= threshold_pct


# ── 模型配置 ─────────────────────────────────────────────────


@dataclass
class ModelConfig:
    """模型配置"""

    name: str
    provider: str
    base_url: str
    api_key_env: str
    models: list[str] = field(default_factory=list)
    priority: int = 0  # 越小优先级越高
    is_free: bool = False  # 是否免费模型
    cost_per_1k_tokens: float = 0.0  # 每 1k token 成本（美分）
    rate_limit_rpm: int = 60  # 每分钟请求数限制
    supports_streaming: bool = True  # 是否支持流式


# ── 智能路由器 ───────────────────────────────────────────────


class SmartRouter:
    """智能 LLM 路由器

    功能：
    1. 按优先级 + 信用余额选择最优 provider
    2. 追踪每个 provider 的信用使用情况
    3. 熔断器：连续失败后自动降级
    4. 成本日志：记录每次调用的成本
    """

    # 默认配置
    DEFAULT_CONFIGS = {
        "zhipu": ModelConfig(
            name="zhipu",
            provider="zhipu",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key_env="ZHIPU_API_KEY",
            models=[
                "glm-4.7",
                "glm-4.6v",
                "glm-4.5-air",
                "glm-4-flash",
                "glm-4-air",
                "glm-4v-plus",
                "glm-4v-flash",
            ],
            priority=1,
            is_free=False,
            cost_per_1k_tokens=0.5,  # 0.5元/万token
            rate_limit_rpm=60,
        ),
        "opencode_go": ModelConfig(
            name="opencode_go",
            provider="opencode_go",
            base_url="https://opencode.ai/zen/go/v1",
            api_key_env="OPENCODE_API_KEY",
            models=[
                "deepseek-v4-flash",
                "qwen3.7-plus",
                "minimax-m3",
                "glm-5.3",
                "glm-5.2",
                "glm-5.1",
                "kimi-k2.7-code",
                "kimi-k2.6",
                "qwen3.6-plus",
                "qwen3.5-plus",
            ],
            priority=99,  # 临时禁用：opencode_go 连续超时 23 次，拖垮全链路
            is_free=True,
            cost_per_1k_tokens=0.0,
            rate_limit_rpm=30,
        ),
        "openrouter": ModelConfig(
            name="openrouter",
            provider="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key_env="OPENROUTER_API_KEY",
            models=[
                "deepseek/deepseek-chat",
                "deepseek/deepseek-reasoner",
                "qwen/qwen3-turbo",
                "meta-llama/llama-3.1-8b-instruct:free",
                "google/gemma-2-9b-it:free",
            ],
            priority=2,
            is_free=True,
            cost_per_1k_tokens=0.0,
            rate_limit_rpm=20,
        ),
        "opencode_zen": ModelConfig(
            name="opencode_zen",
            provider="opencode_zen",
            base_url="https://opencode.ai/zen/v1",
            api_key_env="OPENCODE_API_KEY",
            models=[
                # 免费模型
                "big-pickle",
                "mimo-v2.5-free",
                "hy3-free",
                "nemotron-3-ultra-free",
                "nemotron-3.5-lightning-free",
                "muse-spark-1.2-contributor-free",
                # 付费模型（备用）
                "deepseek-v4-pro",
                "deepseek-v4-flash",
                "gpt-5.6-luna",
                "gpt-5.4-mini",
                "gpt-5.4-nano",
                "claude-haiku-4.5",
                "gemini-3.5-flash-lite",
            ],
            priority=3,
            is_free=True,  # 优先使用免费模型
            cost_per_1k_tokens=0.0,
            rate_limit_rpm=30,
        ),
        "deepseek": ModelConfig(
            name="deepseek",
            provider="deepseek",
            base_url="https://api.deepseek.com/v1",
            api_key_env="DEEPSEEK_API_KEY",
            models=["deepseek-chat", "deepseek-reasoner"],
            priority=4,
            is_free=False,
            cost_per_1k_tokens=0.27,
            rate_limit_rpm=60,
        ),
    }

    # 信用文件路径
    CREDIT_FILE = Path("output/.credit_balance.json")

    # 熔断器参数
    CIRCUIT_BREAK_THRESHOLD = 5  # 连续失败阈值（2026-08-29: 3→5，免费 provider 网络不稳）
    CIRCUIT_BREAK_COOLDOWN_BASE = 30  # 基础冷却秒数
    CIRCUIT_BREAK_COOLDOWN_MAX = 300  # 最大冷却秒数

    def __init__(self):
        self._configs: dict[str, ModelConfig] = dict(self.DEFAULT_CONFIGS)
        self._credits: dict[str, CreditBalance] = {}
        self._failures: dict[str, int] = {}  # provider → 连续失败次数
        self._circuit_broken_until: dict[str, float] = {}  # provider → 冷却结束时间
        self._last_selected: dict[str, str] = {}  # task_type → last selected provider

        # 加载信用余额
        self._load_credits()

        # 从环境变量覆盖配置
        self._apply_env_overrides()

        logger.info(
            "SmartRouter initialized: providers=%s, credits=%s",
            list(self._configs.keys()),
            {k: f"${v.remaining_usd:.2f}" for k, v in self._credits.items()},
        )

    def _load_credits(self):
        """加载信用余额"""
        try:
            if self.CREDIT_FILE.exists():
                with open(self.CREDIT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for provider, info in data.items():
                    self._credits[provider] = CreditBalance(
                        provider=provider,
                        total_cents=info.get("total_cents", 0),
                        used_cents=info.get("used_cents", 0),
                        last_updated=info.get("last_updated", 0),
                    )
        except Exception as e:
            logger.warning("Failed to load credits: %s", e)

        # 初始化默认信用（如果没有加载到）
        if "openrouter" not in self._credits:
            self._credits["openrouter"] = CreditBalance(
                provider="openrouter",
                total_cents=1000,  # $10
            )
        if "opencode_zen" not in self._credits:
            self._credits["opencode_zen"] = CreditBalance(
                provider="opencode_zen",
                total_cents=2000,  # $20
            )
        if "zhipu" not in self._credits:
            self._credits["zhipu"] = CreditBalance(
                provider="zhipu",
                total_cents=2400000,  # ~2400万 token (glm-4.7:500万 + glm-4.6v:600万 + glm-4.5-air:1200万)
            )

    def _save_credits(self):
        """保存信用余额"""
        try:
            self.CREDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for provider, credit in self._credits.items():
                data[provider] = {
                    "total_cents": credit.total_cents,
                    "used_cents": credit.used_cents,
                    "last_updated": time.time(),
                }
            with open(self.CREDIT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Failed to save credits: %s", e)

    def _apply_env_overrides(self):
        """从环境变量覆盖配置（key 统一由 .env 提供）"""
        # OpenRouter
        if os.environ.get("OPENROUTER_API_KEY"):
            self._configs["openrouter"].api_key_env = "OPENROUTER_API_KEY"

        # OpenCode Zen
        if os.environ.get("OPENCODE_API_KEY"):
            self._configs["opencode_zen"].api_key_env = "OPENCODE_API_KEY"

        # Zhipu
        if os.environ.get("ZHIPU_API_KEY"):
            self._configs["zhipu"].api_key_env = "ZHIPU_API_KEY"

    def get_config(self, provider: str) -> Optional[ModelConfig]:
        """获取 provider 配置"""
        return self._configs.get(provider)

    def get_credit(self, provider: str) -> Optional[CreditBalance]:
        """获取 provider 信用余额"""
        return self._credits.get(provider)

    def _in_cooldown(self, provider: str) -> bool:
        """检查 provider 是否在冷却期"""
        until = self._circuit_broken_until.get(provider, 0)
        if until and time.time() < until:
            return False  # 还在冷却期
        return True  # 不在冷却期

    def _record_failure(self, provider: str):
        """记录失败"""
        self._failures[provider] = self._failures.get(provider, 0) + 1
        if self._failures[provider] >= self.CIRCUIT_BREAK_THRESHOLD:
            cooldown = min(
                self.CIRCUIT_BREAK_COOLDOWN_BASE * (2 ** (self._failures[provider] - self.CIRCUIT_BREAK_THRESHOLD)),
                self.CIRCUIT_BREAK_COOLDOWN_MAX,
            )
            self._circuit_broken_until[provider] = time.time() + cooldown
            logger.warning(
                "Provider %s circuit-broken for %.0fs (consecutive=%d)",
                provider,
                cooldown,
                self._failures[provider],
            )

    def _record_timeout(self, provider: str):
        """超时计为半次失败——并行请求容易同时超时，避免误触熔断。"""
        prev = self._failures.get(provider, 0)
        self._failures[provider] = prev + 0.5
        if self._failures[provider] >= self.CIRCUIT_BREAK_THRESHOLD:
            cooldown = min(
                self.CIRCUIT_BREAK_COOLDOWN_BASE * (2 ** (int(self._failures[provider]) - self.CIRCUIT_BREAK_THRESHOLD)),
                self.CIRCUIT_BREAK_COOLDOWN_MAX,
            )
            self._circuit_broken_until[provider] = time.time() + cooldown
            logger.warning(
                "Provider %s circuit-broken for %.0fs (consecutive=%.1f)",
                provider,
                cooldown,
                self._failures[provider],
            )

    def _record_success(self, provider: str):
        """记录成功"""
        self._failures[provider] = 0
        self._circuit_broken_until[provider] = 0

    def _record_usage(self, provider: str, prompt_tokens: int, completion_tokens: int):
        """记录使用量"""
        if provider not in self._credits:
            return

        credit = self._credits[provider]
        config = self._configs.get(provider)
        if not config:
            return

        # 计算成本（美分）- 使用浮点数避免整数截断
        total_tokens = prompt_tokens + completion_tokens
        cost_cents_float = total_tokens * config.cost_per_1k_tokens / 1000

        # 转换为整数美分（向上取整，确保至少记录 1 美分如果有成本）
        import math

        cost_cents = math.ceil(cost_cents_float) if cost_cents_float > 0 else 0

        credit.used_cents += cost_cents
        credit.last_updated = time.time()

        # 保存到文件
        self._save_credits()

        logger.info(
            "Provider %s usage: %d tokens, cost=%.4f USD ($%d cents), remaining=$%.2f",
            provider,
            total_tokens,
            cost_cents / 100,
            cost_cents,
            credit.remaining_usd,
        )

    def select_provider(
        self,
        task_type: str = "general",
        prefer_free: bool = True,
        min_credit_usd: float = 0.1,
    ) -> Optional[tuple[ModelConfig, str]]:
        """选择最优 provider

        Args:
            task_type: 任务类型 (general/reasoning/writing)
            prefer_free: 是否优先使用免费模型
            min_credit_usd: 最低信用余额要求（美元）

        Returns:
            (ModelConfig, model_name) 或 None
        """
        candidates = []

        for name, config in sorted(self._configs.items(), key=lambda x: x[1].priority):
            # 检查 API key
            api_key = os.environ.get(config.api_key_env, "")
            if not api_key:
                continue

            # 检查熔断器
            if self._failures.get(name, 0) >= self.CIRCUIT_BREAK_THRESHOLD:
                if not self._in_cooldown(name):
                    continue

            # 检查信用余额（免费 provider 跳过信用检查）
            credit = self._credits.get(name)
            if not config.is_free and credit and credit.remaining_usd < min_credit_usd:
                logger.info("Provider %s credit exhausted ($%.2f remaining)", name, credit.remaining_usd)
                continue

            # 优先级 1 的 provider（如 Zhipu）始终优先，不受 prefer_free 影响
            if config.priority == 1:
                candidates.append((config, credit))
            elif prefer_free and not config.is_free:
                continue
            else:
                candidates.append((config, credit))

        if not candidates:
            # 如果没有免费 provider，尝试所有可用的（优先级 1 永远优先）
            for name, config in sorted(self._configs.items(), key=lambda x: x[1].priority):
                api_key = os.environ.get(config.api_key_env, "")
                if not api_key:
                    continue
                if self._failures.get(name, 0) >= self.CIRCUIT_BREAK_THRESHOLD:
                    if not self._in_cooldown(name):
                        continue
                credit = self._credits.get(name)
                if not config.is_free and credit and credit.remaining_usd < min_credit_usd:
                    continue
                # 优先级 1 永远加入，不受 free 限制
                if config.priority == 1:
                    candidates.append((config, credit))
                elif prefer_free and not config.is_free:
                    continue
                else:
                    candidates.append((config, credit))

        if not candidates:
            return None

        # 按优先级选择（已排序）
        best_config, best_credit = candidates[0]

        # 选择模型
        model = self._select_model(best_config, task_type)

        logger.info(
            "Selected provider=%s, model=%s, credit=$%.2f, task=%s",
            best_config.name,
            model,
            best_credit.remaining_usd if best_credit else 0,
            task_type,
        )

        return best_config, model

    def _select_model(self, config: ModelConfig, task_type: str) -> str:
        """根据任务类型选择模型"""
        if not config.models:
            return "default"

        # 推理任务优先使用推理模型
        if task_type == "reasoning":
            for model in config.models:
                if "reasoner" in model.lower() or "think" in model.lower():
                    return model

        # 写作任务优先使用高质量模型（glm-4.7 > glm-4.6v > glm-4.5-air > glm-4-flash）
        if task_type == "writing":
            priority_order = ["glm-4.7", "glm-4.6v", "glm-4.5-air", "glm-4-flash", "glm-4-air"]
            for preferred in priority_order:
                for model in config.models:
                    if preferred in model:
                        return model

        # 默认使用第一个模型
        return config.models[0]

    def get_all_providers(self) -> list[dict]:
        """获取所有 provider 状态"""
        result = []
        for name, config in sorted(self._configs.items(), key=lambda x: x[1].priority):
            credit = self._credits.get(name)
            api_key = os.environ.get(config.api_key_env, "")
            result.append(
                {
                    "name": name,
                    "priority": config.priority,
                    "is_free": config.is_free,
                    "has_api_key": bool(api_key),
                    "credit_usd": credit.remaining_usd if credit else 0,
                    "credit_pct": credit.usage_pct if credit else 0,
                    "failures": self._failures.get(name, 0),
                    "circuit_broken": self._failures.get(name, 0) >= self.CIRCUIT_BREAK_THRESHOLD,
                    "models": config.models,
                }
            )
        return result

    def reset_circuit_breaker(self, provider: str):
        """重置熔断器"""
        self._failures[provider] = 0
        self._circuit_broken_until[provider] = 0
        logger.info("Provider %s circuit breaker reset", provider)

    def update_credit(self, provider: str, total_cents: int):
        """更新信用额度"""
        if provider not in self._credits:
            self._credits[provider] = CreditBalance(provider=provider, total_cents=total_cents)
        else:
            self._credits[provider].total_cents = total_cents
        self._save_credits()
        logger.info("Provider %s credit updated: $%.2f", provider, total_cents / 100)


# ── 全局实例 ─────────────────────────────────────────────────

_router: Optional[SmartRouter] = None


def get_router() -> SmartRouter:
    """获取全局路由器实例"""
    global _router
    if _router is None:
        _router = SmartRouter()
    return _router


def select_provider(task_type: str = "general", prefer_free: bool = True) -> Optional[tuple[ModelConfig, str]]:
    """便捷函数：选择 provider"""
    return get_router().select_provider(task_type=task_type, prefer_free=prefer_free)


def record_usage(provider: str, prompt_tokens: int, completion_tokens: int):
    """便捷函数：记录使用量"""
    get_router()._record_usage(provider, prompt_tokens, completion_tokens)


def record_success(provider: str):
    """便捷函数：记录成功"""
    get_router()._record_success(provider)


def record_failure(provider: str):
    """便捷函数：记录失败"""
    get_router()._record_failure(provider)


def record_timeout(provider: str):
    """便捷函数：记录超时（计为半次失败）"""
    get_router()._record_timeout(provider)


def get_provider_status() -> list[dict]:
    """便捷函数：获取所有 provider 状态"""
    return get_router().get_all_providers()
