"""
deepseek_client.py — Multi-Model Provider Layer (V2)
支持 DeepSeek + 开闭原则：添加新provider只需注册，不改调用代码

新增：
- ProviderRegistry：多provider自动切换
- CircuitBreaker：API故障自动降级（P2-8 指数退避+冷却时间）
- RetryWithFallback：失败时自动尝试下一个provider
"""

import json
import logging
import os
import socket
import threading
import time
from dataclasses import dataclass, field

from core import settings as _settings  # P3-audit: 配置单一事实源

# 2026-08-29: 强制 IPv4 — 本机 Python socket.getaddrinfo 返回 IPv6 导致连接挂起
_orig_getaddrinfo = socket.getaddrinfo


def _force_ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _force_ipv4_getaddrinfo

logger = logging.getLogger("2hao.deepseek")

# ── Provider配置 ─────────────────────────────────────────────


@dataclass
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    models: list = field(default_factory=lambda: ["deepseek-chat", "deepseek-v4-pro"])
    priority: int = 0  # 越小优先级越高
    rate_limit_rpm: int = 60


# ── Provider注册表 ──────────────────────────────────────────


class ProviderRegistry:
    """多Provider注册与切换

    用法：
        registry = ProviderRegistry()
        registry.register("deepseek", ProviderConfig(
            name="deepseek",
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com/v1",
        ))
        provider = registry.get_best()  # 返回第一个可用provider

    P2-8 (audit 2026-08-01): 指数退避 + 冷却时间机制
    - 连续失败 n 次后冷却 = min(base_cooldown * 2^n, max_cooldown)
    - 冷却期内直接走降级路由
    - 单次成功即清零连续失败计数并重置冷却
    """

    # 指数退避参数
    CIRCUIT_BREAK_COOLDOWN_BASE = 30  # 基础冷却秒数
    CIRCUIT_BREAK_COOLDOWN_MAX = 600  # 最大冷却秒数 (10 分钟)
    CIRCUIT_BREAK_THRESHOLD = 5  # 连续失败阈值（触发熔断）

    def __init__(self):
        self._providers: dict[str, ProviderConfig] = {}
        self._failures: dict[str, float] = {}  # provider_name → last_failure_time
        self._consecutive_failures: dict[str, int] = {}
        self._circuit_broken_until: dict[str, float] = {}  # provider_name → cooldown_end_time

    def register(self, name: str, config: ProviderConfig):
        self._providers[name] = config
        logger.info("Provider registered: %s (%d models, priority=%d)", name, len(config.models), config.priority)

    def _in_cooldown(self, name: str) -> bool:
        """检查 provider 是否在冷却期内"""
        until = self._circuit_broken_until.get(name, 0)
        if until and time.time() < until:
            remaining = int(until - time.time())
            logger.warning("Provider %s in cooldown (%ds remaining)", name, remaining)
            return True
        # 冷却期已过，允许重试但保持熔断状态以渐进恢复
        if until and time.time() >= until:
            # 冷却期结束，允许试探性恢复（不清零失败计数，等一次成功后再清零）
            self._circuit_broken_until[name] = 0
            logger.info("Provider %s cooldown ended, allowing retry", name)
        return False

    def get_best(self) -> ProviderConfig | None:
        """返回最高优先级且未熔断（不在冷却期）的provider"""
        available = []
        for name, config in sorted(self._providers.items(), key=lambda x: x[1].priority):
            consecutive = self._consecutive_failures.get(name, 0)
            if consecutive >= self.CIRCUIT_BREAK_THRESHOLD and self._in_cooldown(name):
                continue
            if consecutive >= self.CIRCUIT_BREAK_THRESHOLD:
                logger.warning(
                    "Provider %s circuit-broken (%d consecutive failures, cooldown expired, allowing retry)",
                    name,
                    consecutive,
                )
            available.append(config)
        return available[0] if available else None

    def record_failure(self, name: str):
        self._failures[name] = time.time()
        consecutive = self._consecutive_failures.get(name, 0) + 1
        self._consecutive_failures[name] = consecutive
        logger.warning("Provider %s failure #%d", name, consecutive)
        # 指数退避：连续失败 n 次 → 冷却 = base * 2^n，上限 cap
        if consecutive >= self.CIRCUIT_BREAK_THRESHOLD:
            cooldown = min(
                self.CIRCUIT_BREAK_COOLDOWN_BASE * (2 ** (consecutive - self.CIRCUIT_BREAK_THRESHOLD)),
                self.CIRCUIT_BREAK_COOLDOWN_MAX,
            )
            self._circuit_broken_until[name] = time.time() + cooldown
            logger.warning("Provider %s circuit-broken for %.0fs (consecutive=%d)", name, cooldown, consecutive)

    def record_timeout(self, name: str):
        """超时计为半次失败——并行请求容易同时超时，避免误触熔断。"""
        self._failures[name] = time.time()
        prev = self._consecutive_failures.get(name, 0)
        # 超时只加 0.5（向下取整），10 次连续超时才触发熔断
        self._consecutive_failures[name] = prev + 0.5
        logger.warning("Provider %s timeout (consecutive=%.1f)", name, self._consecutive_failures[name])
        if self._consecutive_failures[name] >= self.CIRCUIT_BREAK_THRESHOLD:
            cooldown = min(
                self.CIRCUIT_BREAK_COOLDOWN_BASE
                * (2 ** (int(self._consecutive_failures[name]) - self.CIRCUIT_BREAK_THRESHOLD)),
                self.CIRCUIT_BREAK_COOLDOWN_MAX,
            )
            self._circuit_broken_until[name] = time.time() + cooldown
            logger.warning(
                "Provider %s circuit-broken for %.0fs (consecutive=%.1f)",
                name,
                cooldown,
                self._consecutive_failures[name],
            )

    def record_success(self, name: str):
        # 单次成功：清零连续失败计数和冷却时间
        self._consecutive_failures[name] = 0
        self._circuit_broken_until[name] = 0

    def all_available(self) -> list[str]:
        return [
            n
            for n in self._providers
            if self._consecutive_failures.get(n, 0) < self.CIRCUIT_BREAK_THRESHOLD or not self._in_cooldown(n)
        ]


# ── API配置 ─────────────────────────────────────────────────

DEFAULT_MODEL = os.environ.get("E2E_MODEL", "deepseek-chat")  # 可通过 env 切换
REASONER_MODEL = "deepseek-reasoner"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# Provider 优先级常量（2026-08-07 统一语义：数字越小优先级越高，防 R81 语义反转复发）
PROVIDER_PRIORITY = {
    "deepseek": 0,  # P0 主力：付费关键链（写作/组装/修订/终审）
    "openrouter": 1,  # P1 兜底+圆桌：付费降级/异源评审
    "ollama_local": 0,  # 本地（与 deepseek 同级，可用即用）
    "agent_provider": 10,  # P2 免费预取：仅兜底，绝不抢主链
}

# ── 初始化provider注册表 ───────────────────────────────────

_registry = ProviderRegistry()


def _register_default_providers(registry: ProviderRegistry):
    """注册默认 Provider（集成智能路由器）

    优先级：
    1. OpenCode Go 免费模型（$10/月套餐）
    2. OpenRouter 免费模型（$10 信用）
    3. OpenCode Zen 付费模型（$10/月套餐）
    4. DeepSeek（付费兜底）
    """
    # 使用智能路由器获取配置
    from core.smart_router import get_router

    router = get_router()

    # 注册 OpenCode Go（优先级 1，免费）
    go_config = router.get_config("opencode_go")
    go_key = os.environ.get(go_config.api_key_env, "") if go_config else ""
    if go_key and go_config:
        registry.register(
            "opencode_go",
            ProviderConfig(
                name="opencode_go",
                api_key=go_key,
                base_url=go_config.base_url,
                models=go_config.models,
                priority=go_config.priority,
            ),
        )
        logger.info("OpenCode Go provider registered (priority=1, free)")

    # 注册 OpenRouter（优先级 2）
    or_config = router.get_config("openrouter")
    or_key = os.environ.get(or_config.api_key_env, "") if or_config else ""
    if or_key and or_config:
        registry.register(
            "openrouter",
            ProviderConfig(
                name="openrouter",
                api_key=or_key,
                base_url=or_config.base_url,
                models=or_config.models,
                priority=or_config.priority,
            ),
        )
        logger.info("OpenRouter provider registered (priority=2, free)")

    # 注册 OpenCode Zen（优先级 3）
    zen_config = router.get_config("opencode_zen")
    zen_key = os.environ.get(zen_config.api_key_env, "") if zen_config else ""
    if zen_key and zen_config:
        registry.register(
            "opencode_zen",
            ProviderConfig(
                name="opencode_zen",
                api_key=zen_key,
                base_url=zen_config.base_url,
                models=zen_config.models,
                priority=zen_config.priority,
            ),
        )
        logger.info("OpenCode Zen provider registered (priority=3, paid)")

    # 注册 Zhipu（优先级 1，付费主力）
    zhipu_config = router.get_config("zhipu")
    zhipu_key = os.environ.get(zhipu_config.api_key_env, "") if zhipu_config else ""
    if zhipu_key and zhipu_config:
        registry.register(
            "zhipu",
            ProviderConfig(
                name="zhipu",
                api_key=zhipu_key,
                base_url=zhipu_config.base_url,
                models=zhipu_config.models,
                priority=zhipu_config.priority,
            ),
        )
        logger.info("Zhipu provider registered (priority=1, paid)")

    # 注册 DeepSeek（优先级 4，兜底）
    ds_config = router.get_config("deepseek")
    ds_key = os.environ.get(ds_config.api_key_env, "") if ds_config else ""
    if ds_key and ds_config:
        registry.register(
            "deepseek",
            ProviderConfig(
                name="deepseek",
                api_key=ds_key,
                base_url=ds_config.base_url,
                models=ds_config.models,
                priority=ds_config.priority,
            ),
        )
        logger.info("DeepSeek provider registered (priority=4, fallback)")

    # 注册本地 Ollama（如果可用）
    _ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    try:
        import requests as _req

        _r = _req.get(_ollama_url.replace("/v1", "/api/tags"), timeout=3)
        if _r.status_code == 200:
            _models = [m["name"] for m in _r.json().get("models", [])]
            if _models:
                registry.register(
                    "ollama_local",
                    ProviderConfig(
                        name="ollama_local",
                        api_key="",
                        base_url=_ollama_url,
                        models=_models,
                        # 2026-09-04：priority 0→9。原 0（最高）会让 fallback 链
                        # 在云端限流时先打本地 7B（质量低于 deepseek/openrouter）。
                        # 现在 2hao-analyst-v2(10K SFT) 已可用但仍是 7B——
                        # 定位为"云端全挂时的最后兜底"（在 agent_provider 之前）。
                        priority=9,
                    ),
                )
                logger.info("Ollama registered: %s (priority=9, last-resort fallback)", _models)
    except Exception:
        logger.info("No local Ollama detected")


_register_default_providers(_registry)

# ── 单 Provider 策略（2026-07-31 用户决策）────────────────
# 只保留 DeepSeek 作为 LLM 提供方。
# 故障兜底交给 L3 agent（见 e2e_orchestrator 的 llm_degradation_level 机制），
# 而不是依赖多 provider 自动切换。
# 原 multi-provider 注册逻辑已在 .env.bak / git 历史可回滚。
#
# 注：_register_cloud_providers 被删除。若未来要恢复多 provider，
# 从 .env.bak 恢复 key 并在 ProviderRegistry 重新注册即可。

# ── API调用 ─────────────────────────────────────────────────


_LLM_CALL_T0 = time.time()


# ── 响应缓存（P3-audit 2026-08-24 接线：llm_cache.py 此前零消费者）──
# 门控开关 LLM_RESPONSE_CACHE（默认关——写作修订循环依赖同 prompt 不同轮
# 的采样差异，全局开启会破坏 repair/STALL 语义；适用于批量/开发迭代场景）。
_MEM_RESP_CACHE: dict = {}


def _cache_key(messages: list, model: str, temperature: float, max_tokens: int) -> str:
    import hashlib

    raw = json.dumps(
        {"m": messages, "model": model, "t": temperature, "mt": max_tokens}, ensure_ascii=False, sort_keys=True
    )
    return "llmresp_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _response_cache_get(key: str):
    try:
        from core.compute.llm_cache import get_cache

        c = get_cache()
        if c is not None:
            return c.get(key)
    except Exception:
        pass
    return _MEM_RESP_CACHE.get(key)


def _response_cache_set(key: str, value):
    # 防污染（2026-09-04）：zhipu 429 限流期间曾把截断/乱码响应写入缓存，
    # 后续同 prompt 命中坏缓存 → 写作修订 3 次返回同一截断文本 → Gate 恒 0.658。
    # 门槛：内容必须非空且 ≥50 字符才入缓存（截断响应通常 <50 或为空）。
    try:
        _content = ""
        if isinstance(value, dict):
            _choices = value.get("choices") or []
            if _choices:
                _content = str((_choices[0] or {}).get("message", {}).get("content", ""))
        if len(_content.strip()) < 50:
            logger.info("[LLM-CACHE] 拒绝缓存短/空响应（%d 字符）", len(_content.strip()))
            return
    except Exception:
        pass
    ttl = _settings.llm_cache_ttl()
    try:
        from core.compute.llm_cache import get_cache

        c = get_cache()
        if c is not None:
            c.set(key, value, expire=ttl)
            return
    except Exception:
        pass
    if len(_MEM_RESP_CACHE) > 256:  # 内存兜底：简单容量上限
        _MEM_RESP_CACHE.clear()
    _MEM_RESP_CACHE[key] = value


def _t2_latency() -> int:
    """[DEPRECATED 2026-08-24] 返回模块加载至今的累计毫秒——语义错误，
    成本日志已改用 requests.post 前后的 perf_counter 差值。仅为兼容保留。"""
    return int((time.time() - _LLM_CALL_T0) * 1000)


def _accumulate_openrouter_stream(lines) -> dict:
    """R89（2026-08-25）：聚合 OpenRouter SSE 流式响应为 {content, reasoning, usage}。

    背景：本机网络路径下非流式响应体在 ~7.8KB 处被中间设备确定性截断
    （resp.json() 报 Expecting value），长写作调用 100% 失败；SSE 分块持续
    有数据流动，可穿透该类静默超时。

    协议要点：
      - 注释行以 ":" 开头（如 ": OPENROUTER PROCESSING"）→ 忽略
      - "data: [DONE]" → 结束
      - "data: {...}" → choices[0].delta.content / .reasoning / .reasoning_content 累加
      - usage 出现在任一 chunk（通常最后带 usage 的 chunk）→ 记录
      - 垃圾行/半行 JSON → 容错跳过，不抛异常
    """
    content_parts: list = []
    reasoning_parts: list = []
    usage: dict = {}
    done = False
    try:
        for raw in lines:
            if done:
                break
            if raw is None:
                continue
            line = raw.strip() if isinstance(raw, str) else raw.decode("utf-8", "ignore").strip()
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data:"):
                continue
            payload_str = line[len("data:") :].strip()
            if payload_str == "[DONE]":
                done = True
                continue
            try:
                chunk = json.loads(payload_str)
            except (ValueError, TypeError):
                continue
            if not isinstance(chunk, dict):
                continue
            if isinstance(chunk.get("usage"), dict) and chunk["usage"]:
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = (choices[0] or {}).get("delta") or {}
            c = delta.get("content")
            if isinstance(c, str) and c:
                content_parts.append(c)
            r = delta.get("reasoning") or delta.get("reasoning_content")
            if isinstance(r, str) and r:
                reasoning_parts.append(r)
    except Exception as e:  # 迭代器网络中断：返回已聚合部分（调用方按内容判空）
        logger.warning(
            "[LLM-STREAM] 聚合中断（已收 content=%d chars）: %s", sum(len(p) for p in content_parts), str(e)[:80]
        )
    return {
        "content": "".join(content_parts),
        "reasoning": "".join(reasoning_parts),
        "usage": usage,
    }


# ── 限流（P2-audit 2026-08-24：rate_limit_rpm 字段此前定义后零引用）──
_rate_lock = threading.Lock()
_rate_windows: dict = {}  # provider_name -> list[float] 最近请求时间戳


def _rate_limit_acquire(provider_name: str, rpm: int) -> None:
    """滑动窗口限流：每 provider 每分钟最多 rpm 次请求（rpm<=0 不限）。

    超限时阻塞等待窗口腾出（而非拒绝），与管线"尽量完成"的容错哲学一致。
    """
    if not rpm or rpm <= 0:
        return
    while True:
        with _rate_lock:
            now = time.time()
            win = [t for t in _rate_windows.get(provider_name, []) if now - t < 60.0]
            if len(win) < rpm:
                win.append(now)
                _rate_windows[provider_name] = win
                return
            wait_s = min(60.0 - (now - win[0]) + 0.05, 5.0)
        time.sleep(wait_s)


def _normalize_llm_response(data: dict) -> dict:
    """规范化 LLM 响应（2026-08-07 新增，兼容推理模型）。

    部分推理模型（如 qwen/qwen3.6-flash）返回 content=None，推理过程在
    message.reasoning 字段，最终答案在 reasoning 尾部。统一提取：
      1. content 非空 → 直接用
      2. content 为 None 但 reasoning 有内容 → 从 reasoning 提取最终答案
         （取最后一个推理块/末尾实质内容）
    保证 call_llm 调用方永远拿到 content。
    """
    try:
        msg = data["choices"][0]["message"]
        content = msg.get("content")
        if content and content.strip():
            return data
        reasoning = msg.get("reasoning") or msg.get("reasoning_content") or ""
        if reasoning and reasoning.strip():
            # 推理模型：取 reasoning 最后一段实质内容作为"最终答案"
            _text = reasoning.strip()
            # 找最后的答案块（常见格式：**答案** / 最终答案 / 总结在尾部）
            blocks = [b for b in _text.split("\n") if b.strip()]
            if blocks:
                # 取最后 1-2 块（通常是最终答案/结论）
                tail = blocks[-1]
                # 去掉思考痕迹前缀
                for _drop in ("Therefore", "最终答案", "答案:", "综上", "结论:"):
                    if tail.startswith(_drop):
                        tail = tail[len(_drop) :].strip()
                msg["content"] = tail[:500]
                logger.info(
                    "[LLM] 推理模型响应 content=None，已从 reasoning 提取尾部答案（%d字）",
                    len(msg.get("content") or ""),
                )
                return data
        # 都拿不到 → 返回原样（调用方按空处理）
        return data
    except (KeyError, IndexError, TypeError):
        return data


def call_llm(
    messages: list,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    stream: bool = False,
    provider: str = "auto",
) -> dict:
    """统一LLM调用接口（多provider自动切换）

    用法与 call_deepseek 一致，但会自动处理provider故障切换。
    R13（2026-08-01 三算力架构）：新增 provider 参数强制指定提供方——
      "opencode_go" = OpenCode Go（免费）
    provider 默认 auto（2026-09-04 修复）：此前默认 opencode_go——本机未注册
    该 provider（无 OPENCODE_API_KEY），漏传参数的调用点全部走"指定不可用
    →回退链"，加剧 zhipu 429。auto 走 smart_router 按健康度选可用 provider。
      "openrouter" = OpenRouter（免费）
      "opencode_zen" = OpenCode Zen（免费）
      "agent_provider" = Marvis 队列（起草/修订，多实例并行）
    provider 指定的资源不可用时，回退到可用 provider（容错）。
    """
    import requests

    # P3-audit 2026-08-24：响应缓存（LLM_RESPONSE_CACHE=1 启用）。
    # 命中返回与成功响应同构的 dict，0 token；stream 模式不缓存。
    if _settings.llm_response_cache() and not stream:
        _ck = _cache_key(messages, model, temperature, max_tokens)
        _hit = _response_cache_get(_ck)
        if _hit is not None:
            logger.info("[LLM-CACHE] 命中 %s（省一次调用）", _ck[:28])
            return _hit
    else:
        _ck = None

    # 使用智能路由器选择最优 provider
    from core.smart_router import get_router, record_failure, record_usage

    router = get_router()

    # 确定任务类型
    task_type = "general"
    if model and ("reasoner" in model.lower() or "think" in model.lower()):
        task_type = "reasoning"
    elif any(kw in str(messages[:2]).lower() for kw in ["写", "撰写", "报告", "分析"]):
        task_type = "writing"

    # 使用智能路由器选择 provider
    if provider and provider != "auto":
        # 强制指定 provider
        target = _registry._providers.get(provider)
        if target and _registry._consecutive_failures.get(provider, 0) < 5:
            providers = [target]
        else:
            logger.warning("[LLM 指定 provider=%s 不可用，使用全量回退链", provider)

            # 修复（2026-09-04）：此前这里用 router.select_provider() 只取单选
            # （恒为 priority 最高的 zhipu），zhipu 429 后整链死亡——
            # openrouter/deepseek 在注册表里却永远轮不到。改为全量回退链
            # （按 priority 排序、剔除熔断），指定 provider 失败后逐个尝试。
            def _active():
                return sorted(
                    (p for p in _registry._providers.values() if _registry._consecutive_failures.get(p.name, 0) < 5),
                    key=lambda x: x.priority,
                )

            providers = _active()
    else:
        # 使用智能路由器选择
        result = router.select_provider(task_type=task_type, prefer_free=True)
        if result:
            config, model_name = result
            _picked = _registry._providers.get(config.name)
            if _picked:
                # 修复（2026-09-04）：此前 providers=[单选]，smart_router 首选
                # （zhipu）429 后整链 raise，openrouter/deepseek 永远轮不到。
                # 现在首选排最前，其余可用 provider 追加为回退。
                def _active():
                    return sorted(
                        (
                            p
                            for p in _registry._providers.values()
                            if _registry._consecutive_failures.get(p.name, 0) < 5
                        ),
                        key=lambda x: x.priority,
                    )

                _rest = [p for p in _active() if p.name != config.name]
                providers = [_picked] + _rest
                model = model_name
                logger.info(
                    "[LLM] Smart router selected: %s (model=%s, fallback chain: %s)",
                    config.name,
                    model,
                    [p.name for p in providers],
                )
            else:
                providers = []
        else:
            providers = []

    if not providers:
        # 回退到原有逻辑
        def _active():
            return sorted(
                (p for p in _registry._providers.values() if _registry._consecutive_failures.get(p.name, 0) < 5),
                key=lambda x: x.priority,
            )

        providers = _active()
    else:
        # 当通过智能路由器或其他方式选择了 providers 时，仍定义 _active 供后续全量回退使用
        def _active():
            return sorted(
                (p for p in _registry._providers.values() if _registry._consecutive_failures.get(p.name, 0) < 5),
                key=lambda x: x.priority,
            )

    if not providers:
        raise RuntimeError("No available LLM provider (all circuit-broken)")

    last_error = None
    # P2-audit 2026-08-24：循环变量 `provider` 遮蔽同名函数参数（str），
    # 导致函数尾部 `if provider != "auto"` 永真 → auto 全败时重复递归全量回退。
    # 现循环变量改名 pv，参数语义用 _requested_provider 保留。
    _requested_provider = provider
    for pv in providers:
        # 可调用 provider（如 AgentProvider）——不走 HTTP，直接调用
        if (
            hasattr(pv, "__call__")
            and not hasattr(pv, "base_url")
            or (hasattr(pv, "name") and pv.name == "agent_provider")
        ):
            try:
                logger.info("[LLM] fallback 到可调用 provider: %s", pv.name)
                return pv(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                )
            except Exception as e:
                last_error = e
                # R77（2026-08-05）：agent_provider 失败也要记录熔断，否则回退逻辑
                # 永远走不到（providers=[agent_provider] 单元素，失败即 raise）。
                # 记录失败后，下次 call_llm 会因 _consecutive_failures>=5 走全量回退。
                _registry.record_failure(pv.name)
                logger.warning("Agent provider failed: %s", e)
                continue

        # model 必须落在 provider 支持的模型列表内，否则使用 provider 首选模型
        m = model
        if pv.models and m not in pv.models:
            logger.info("Model %s not in provider %s models %s, using %s", m, pv.name, pv.models, pv.models[0])
            m = pv.models[0]

        headers = {
            "Authorization": f"Bearer {pv.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": m,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        # P2-audit 2026-08-24：限流落地（rate_limit_rpm 字段此前零引用）。
        # 并发组写作 6-8 线程同时打 API 无节流 → 429 连锁失败。
        try:
            _rate_limit_acquire(pv.name, getattr(pv, "rate_limit_rpm", 0) or 0)
        except Exception:
            pass

        # R53（2026-08-03 P1-4 修复）：provider 健康预检——发起完整请求前
        # 用短超时（5s）探测连通性。只有连接层失败（超时/DNS/拒绝连接）才跳过
        # provider；401/404 说明服务可达（只是端点路径不同），不跳过，继续完整请求。
        # 解决"6 组并行各等满 300s、一轮空耗 10 分钟"。
        if hasattr(pv, "base_url"):
            try:
                _probe_url = pv.base_url.replace("/v1", "").rstrip("/") + "/models"
                _probe_resp = requests.get(
                    _probe_url,
                    headers={"Authorization": headers["Authorization"]},
                    timeout=5,
                )
                # 5xx/连接异常视为服务不可用；4xx 视为可达（端点差异，继续完整请求）
                if _probe_resp.status_code >= 500:
                    raise ConnectionError(f"probe HTTP {_probe_resp.status_code}")
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectTimeout,
            ) as _pe:
                logger.warning("[LLM-PROBE] provider=%s 健康预检失败（跳过，避免300s空耗）: %s", pv.name, str(_pe)[:80])
                _registry.record_failure(pv.name)
                continue
            except Exception:
                # 其他异常（401/404/解析等）——provider 可达，不跳过
                pass

        for attempt in range(2):
            try:
                _t0 = time.perf_counter()  # P2-audit 2026-08-24: 单次调用真延迟
                # R99: 调试 400 错误 —— 记录请求摘要
                _msg_count = len(messages)
                _total_chars = sum(len(str(m.get("content", ""))) for m in messages)
                logger.debug(
                    "[LLM] %s request: model=%s, msgs=%d, total_chars=%d", pv.name, m, _msg_count, _total_chars
                )
                # R89（2026-08-25）：openrouter 走 SSE 流式——本机网络对非流式
                # 长响应体在 ~7.8KB 处确定性截断，流式分块可穿透（OPENROUTER_STREAM=0 关闭）。
                if pv.name == "openrouter" and os.environ.get("OPENROUTER_STREAM", "1") != "0":
                    _stream_payload = dict(payload)
                    _stream_payload["stream"] = True
                    with requests.post(
                        f"{pv.base_url}/chat/completions",
                        headers=headers,
                        json=_stream_payload,
                        timeout=max(_settings.llm_http_timeout(), 300),
                        stream=True,
                    ) as _sresp:
                        _sresp.raise_for_status()
                        _acc = _accumulate_openrouter_stream(_sresp.iter_lines(decode_unicode=True))
                    _latency_ms = int((time.perf_counter() - _t0) * 1000)
                    _registry.record_success(pv.name)
                    _resp = _normalize_llm_response(
                        {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": _acc["content"],
                                        "reasoning": _acc["reasoning"],
                                    }
                                }
                            ],
                            "id": f"stream-{int(_t0)}",
                            "object": "chat.completion",
                            "model": m,
                            "usage": _acc.get("usage") or {},
                        }
                    )
                    try:
                        from core.metrics import ObservabilityDB

                        _usage = _resp.get("usage", {})
                        ObservabilityDB().log_llm_call_simple(
                            module="call_llm_stream",
                            section_id=m,
                            prompt_tokens=_usage.get("prompt_tokens", 0),
                            completion_tokens=_usage.get("completion_tokens", 0),
                            latency_ms=_latency_ms,
                            status="success",
                            provider=getattr(pv, "name", "unknown"),
                        )
                    except Exception as _le:
                        logger.debug("[COST-LOG] %s", str(_le)[:50])
                    if _ck is not None:
                        try:
                            _response_cache_set(_ck, _resp)
                        except Exception:
                            pass
                    return _resp
                resp = requests.post(
                    f"{pv.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=_settings.llm_http_timeout(),
                )
                # R99: 捕获响应体用于调试 400 错误
                if resp.status_code >= 400:
                    _body = resp.text[:500] if resp.text else "(empty)"
                    _payload_summary = {
                        "model": payload.get("model"),
                        "msg_count": len(payload.get("messages", [])),
                        "total_chars": sum(len(str(m.get("content", ""))) for m in payload.get("messages", [])),
                        "max_tokens": payload.get("max_tokens"),
                    }
                    logger.error(
                        "[LLM] %s HTTP %d: payload=%s body=%s", pv.name, resp.status_code, _payload_summary, _body
                    )
                resp.raise_for_status()
                _latency_ms = int((time.perf_counter() - _t0) * 1000)
                _registry.record_success(pv.name)
                _resp = _normalize_llm_response(resp.json())
                # 记录使用量到智能路由器
                try:
                    _usage = _resp.get("usage", {})
                    record_usage(
                        pv.name,
                        _usage.get("prompt_tokens", 0),
                        _usage.get("completion_tokens", 0),
                    )
                except Exception as _ue:
                    logger.debug("[SMART-ROUTER] usage record failed: %s", str(_ue)[:50])
                # P3-2 成本日志（2026-08-07）：记录每次调用 token/通道/耗时，可观测性
                try:
                    from core.metrics import ObservabilityDB

                    _usage = _resp.get("usage", {})
                    ObservabilityDB().log_llm_call_simple(
                        module="call_llm",
                        section_id=m,
                        prompt_tokens=_usage.get("prompt_tokens", 0),
                        completion_tokens=_usage.get("completion_tokens", 0),
                        latency_ms=_latency_ms,
                        status="success",
                        provider=getattr(pv, "name", "unknown"),
                    )
                except Exception as _le:
                    logger.debug("[COST-LOG] %s", str(_le)[:50])
                if _ck is not None:
                    try:
                        _response_cache_set(_ck, _resp)
                    except Exception:
                        pass
                return _resp
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout,
            ) as e:
                # 超时：快速失败到下一个 provider（不重试同一 provider）
                logger.warning("[LLM] provider=%s timeout on attempt %d/2 (fail-fast to next)", pv.name, attempt + 1)
                _registry.record_timeout(pv.name)
                break  # 跳出 attempt 循环，外层 provider 循环继续下一个
            except requests.exceptions.RequestException as e:
                # 其他网络错误（连接拒绝等）——记录失败，继续重试
                last_error = e
                logger.warning(
                    "[LLM] provider=%s network error on attempt %d/2: %s", pv.name, attempt + 1, str(e)[:100]
                )
                if attempt < 1:
                    time.sleep(1)
        _registry.record_failure(pv.name)
        # 记录失败到智能路由器
        try:
            record_failure(pv.name)
        except Exception as _fe:
            logger.debug("[SMART-ROUTER] failure record failed: %s", str(_fe)[:50])

    # R77（2026-08-05）：强制指定的 provider 失败 → 按优先级全量回退一轮
    # （此前单元素 providers 失败即 raise；agent_provider 队列积压/DeepSeek 网络抖动
    #  都会让原本可用的 provider 得不到机会）
    if _requested_provider and _requested_provider != "auto":
        _fallback = [p.name for p in _active()]
        if _fallback:
            logger.warning("[LLM] 指定 provider=%s 全部失败，全量回退 %s", _requested_provider, _fallback)
            try:
                return call_llm(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    provider="auto",
                )
            except Exception as _e2:
                last_error = _e2
    raise RuntimeError(f"LLM call failed after all providers: {last_error}")


# ── 兼容旧调用 ─────────────────────────────────────────────

# Provider 优先级常量已在模块顶部定义（PROVIDER_PRIORITY）

# 修复（2026-08-01 审计）：恢复宪法层1 LLM 兜底通道。
# agent_provider.py 定义了 AgentProvider 并自带自动注册（module-level
# register_agent_provider()），但此前从未被本模块导入 → 注册表里只有 deepseek，
# DeepSeek 挂掉时 call_llm 直接 RuntimeError，L3 agent 兜底形同虚设。
# 现在 import 即触发自动注册（priority=10，P2 兜底），DeepSeek/OpenRouter
# 失败后 call_llm 才会 fallback 到 AgentProvider，请求落盘队列 → agent 响应 → 回流管线。
try:
    import core.agent_provider  # noqa: F401  (自动注册 agent_provider)
except Exception as _ap_err:
    logger.warning("AgentProvider 导入失败，LLM 兜底不可用: %s", _ap_err)


def call_deepseek(
    messages: list,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 8192,
    api_key: str = "",
    stream: bool = False,
    provider: str = "auto",
) -> dict:
    """兼容旧接口。

    provider 默认 auto（2026-09-04 修复）：此前默认 opencode_go——该 provider
    在本机未注册（无 OPENCODE_API_KEY），所有漏传 provider 的调用点全部
    打到"指定不可用→回退链"，加剧 zhipu 429。auto 走 smart_router 按
    健康度选可用 provider。
    """
    return call_llm(
        messages, model=model, temperature=temperature, max_tokens=max_tokens, stream=stream, provider=provider
    )


class DeepSeekClient:
    """兼容类：包装 call_deepseek，提供 chat() 接口。

    修复（2026-08-01）：core/bold_call_extractor.py、core/hypothesis_checker.py、
    core/data_provenance.py 均 `from core.deepseek_client import DeepSeekClient`，
    但此前模块只有函数式 call_deepseek，无此类 → 消费者全部降级到正则 fallback，
    日志反复出现 "DeepSeek client unavailable: cannot import name 'DeepSeekClient'"。
    本类提供兼容的 chat(prompt, temperature) 接口，让消费者真正走 LLM。
    """

    def __init__(self, model: str = DEFAULT_MODEL, **kw):
        self.model = model

    def chat(self, prompt: str, temperature: float = 0.3, max_tokens: int = 2048) -> str:
        """单轮对话，返回文本内容（旧接口约定）。失败抛异常由调用方处理。"""
        r = call_deepseek(
            [{"role": "user", "content": prompt}],
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return r["choices"][0]["message"]["content"]

    def complete(self, messages: list, temperature: float = 0.3, max_tokens: int = 2048) -> str:
        """多消息对话，返回文本内容。"""
        r = call_deepseek(messages, model=self.model, temperature=temperature, max_tokens=max_tokens)
        return r["choices"][0]["message"]["content"]


# ── 评分/推理/章节生成（原函数保留） ─────────────────────


def score_text(text: str, criteria: str = "quality") -> dict:
    """文本评分"""
    system_prompt = f"""你是严格的报告质量评审专家。请对以下分析师报告进行评分。

评分维度:
1. aigc_fingerprint (0-1): AI痕迹分数，越低越好（人类写作应<0.15）
2. human_sense (0-1): 人感分数，越高越好（分析师语气、经验引用）
3. argument_depth (0-1): 论证深度（因果链完整性、反方论证质量）
4. data_quality (0-1): 数据质量（来源标注、交叉验证、时效性）
5. chart_density (0-1): 图表密度（数量、相关性、标注质量）
6. persuasion (0-1): 说服力（叙事弧线、共鸣对话、So What链）
7. formatting (0-1): 排版质量（字体一致、表格规范、图表位置）

评分标准: {criteria}

返回JSON格式: {{"dimensions": {{"aigc_fingerprint": 0.xx, ...}}, "overall": 0.xx, "issues": ["问题1"], "suggestions": ["建议1"]}}
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text[:8000]},
    ]
    try:
        result = call_llm(messages, temperature=0.1)
        content = result["choices"][0]["message"]["content"]
        import re

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"overall": 0.5, "dimensions": {}, "issues": ["Parse failed"], "suggestions": []}
    except Exception as e:
        logger.error("scoring failed: %s", e)
        return {"overall": 0.5, "dimensions": {}, "issues": [str(e)], "suggestions": []}


def reason(question: str, context: str = "") -> str:
    """深度推理"""
    messages = [
        {"role": "system", "content": "你是顶尖分析师，擅长深度推理和矛盾识别。请分步骤推理，给出有证据支持的结论。"},
        {"role": "user", "content": f"背景: {context}\n\n问题: {question}"},
    ]
    try:
        result = call_llm(messages, model=REASONER_MODEL, temperature=0.2, max_tokens=8192)
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("reasoning failed: %s", e)
        return ""


def generate_report_section(
    section_name: str,
    sac_requirements: dict,
    data: dict,
    style: str = "cicc",
) -> str:
    """生成报告章节"""
    prompt = f"""请撰写研究报告的《{section_name}》章节。

分析框架要求:
{sac_requirements}

可用数据:
{json.dumps(data, ensure_ascii=False, indent=2)[:3000]}

写作风格: {style}

要求:
1. 语言自然，无AI痕迹
2. 每个判断都有数据支撑
3. 标注数据来源
4. 引用历史经验
5. 有So What链（这意味着...因此...建议...）
"""
    messages = [
        {"role": "system", "content": "你是资深分析师，撰写一级券商质量的研究报告。"},
        {"role": "user", "content": prompt},
    ]
    try:
        result = call_llm(messages, temperature=0.4, max_tokens=4096)
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("section generation failed: %s", e)
        return ""
