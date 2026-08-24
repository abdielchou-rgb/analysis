
"""
deepseek_client.py — Multi-Model Provider Layer (V2)
支持 DeepSeek + 开闭原则：添加新provider只需注册，不改调用代码

新增：
- ProviderRegistry：多provider自动切换
- CircuitBreaker：API故障自动降级（P2-8 指数退避+冷却时间）
- RetryWithFallback：失败时自动尝试下一个provider
"""

import os, json, time, logging
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field

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
    CIRCUIT_BREAK_COOLDOWN_BASE = 30    # 基础冷却秒数
    CIRCUIT_BREAK_COOLDOWN_MAX = 600    # 最大冷却秒数 (10 分钟)
    CIRCUIT_BREAK_THRESHOLD = 5         # 连续失败阈值（触发熔断）

    def __init__(self):
        self._providers: dict[str, ProviderConfig] = {}
        self._failures: dict[str, float] = {}  # provider_name → last_failure_time
        self._consecutive_failures: dict[str, int] = {}
        self._circuit_broken_until: dict[str, float] = {}  # provider_name → cooldown_end_time

    def register(self, name: str, config: ProviderConfig):
        self._providers[name] = config
        logger.info("Provider registered: %s (%d models, priority=%d)",
                    name, len(config.models), config.priority)

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

    def get_best(self) -> Optional[ProviderConfig]:
        """返回最高优先级且未熔断（不在冷却期）的provider"""
        available = []
        for name, config in sorted(self._providers.items(),
                                    key=lambda x: x[1].priority):
            consecutive = self._consecutive_failures.get(name, 0)
            if consecutive >= self.CIRCUIT_BREAK_THRESHOLD and self._in_cooldown(name):
                continue
            if consecutive >= self.CIRCUIT_BREAK_THRESHOLD:
                logger.warning("Provider %s circuit-broken (%d consecutive failures, "
                               "cooldown expired, allowing retry)", name, consecutive)
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
            logger.warning("Provider %s circuit-broken for %.0fs (consecutive=%d)",
                           name, cooldown, consecutive)

    def record_success(self, name: str):
        # 单次成功：清零连续失败计数和冷却时间
        self._consecutive_failures[name] = 0
        self._circuit_broken_until[name] = 0

    def all_available(self) -> list[str]:
        return [n for n in self._providers
                if self._consecutive_failures.get(n, 0) < self.CIRCUIT_BREAK_THRESHOLD
                or not self._in_cooldown(n)]


# ── API配置 ─────────────────────────────────────────────────

DEFAULT_MODEL = "deepseek-chat"
REASONER_MODEL = "deepseek-reasoner"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# Provider 优先级常量（2026-08-07 统一语义：数字越小优先级越高，防 R81 语义反转复发）
PROVIDER_PRIORITY = {
    "deepseek": 0,        # P0 主力：付费关键链（写作/组装/修订/终审）
    "openrouter": 1,      # P1 兜底+圆桌：付费降级/异源评审
    "ollama_local": 0,    # 本地（与 deepseek 同级，可用即用）
    "agent_provider": 10, # P2 免费预取：仅兜底，绝不抢主链
}

# ── 初始化provider注册表 ───────────────────────────────────

_registry = ProviderRegistry()


def _register_default_providers(registry: ProviderRegistry):
    """注册默认 Provider（Nit: 从模块级移至函数，支持运行时切换）

    P2-8 Nit (audit 2026-08-01): 将环境变量路由检测从模块级
    （仅在 import 时执行一次）移至 ProviderRegistry 实例化时，
    支持运行时通过修改环境变量切换 provider 路由。
    """
    _deepseek_key = os.environ.get("DEEPSEEK_API_KEY") or ""
    _or_key = os.environ.get("OPENROUTER_API_KEY") or ""

    # P0 主力：DeepSeek（若 DEEPSEEK_API_KEY 存在）
    # 兼容旧逻辑：若 DEEPSEEK_API_KEY 本身是 OpenRouter key（sk-or-v1- 开头）则当 OpenRouter 用
    _is_or_key = _deepseek_key.startswith("sk-or-v1-")
    if _is_or_key:
        _deepseek_base = os.environ.get("DEEPSEEK_BASE_URL", "https://openrouter.ai/api/v1")
        _deepseek_models = ["deepseek/deepseek-chat", "deepseek/deepseek-reasoner"]
        logger.info("DEEPSEEK_API_KEY detected as OpenRouter key, routing via OpenRouter")
    else:
        _deepseek_base = os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL)
        _deepseek_models = [DEFAULT_MODEL, REASONER_MODEL]
    if _deepseek_key and not _is_or_key:
        registry.register("deepseek", ProviderConfig(
            name="deepseek",
            api_key=_deepseek_key,
            base_url=_deepseek_base,
            models=_deepseek_models,
            priority=PROVIDER_PRIORITY.get("deepseek", 0),
        ))
        logger.info("DeepSeek provider registered (key length=%d, base=%s)", len(_deepseek_key), _deepseek_base)

    # P1 兜底+圆桌：OpenRouter（若 OPENROUTER_API_KEY 存在）
    if _or_key:
        registry.register("openrouter", ProviderConfig(
            name="openrouter",
            api_key=_or_key,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            models=os.environ.get("OPENROUTER_MODELS", "deepseek/deepseek-chat,deepseek/deepseek-reasoner,qwen/qwen3-turbo").split(","),
            priority=PROVIDER_PRIORITY.get("openrouter", 1),
        ))
        logger.info("OpenRouter provider registered (key length=%d, models=%s)",
                    len(_or_key), os.environ.get("OPENROUTER_MODELS", "deepseek/deepseek-chat,..."))
    elif _is_or_key:
        # 兼容：DEEPSEEK_API_KEY 是 OpenRouter key 时注册为 openrouter
        registry.register("openrouter", ProviderConfig(
            name="openrouter",
            api_key=_deepseek_key,
            base_url=_deepseek_base,
            models=_deepseek_models,
            priority=PROVIDER_PRIORITY.get("openrouter", 1),
        ))
        logger.info("OpenRouter provider registered from DEEPSEEK_API_KEY (legacy)")

        # 注册本地Ollama(如果宿主机上运行了Ollama)
        _ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        try:
            import requests as _req
            _r = _req.get(_ollama_url.replace('/v1', '/api/tags'), timeout=3)
            if _r.status_code == 200:
                _models = [m['name'] for m in _r.json().get('models', [])]
                if _models:
                    registry.register("ollama_local", ProviderConfig(
                        name="ollama_local",
                        api_key="",
                        base_url=_ollama_url,
                        models=_models,
                        priority=0,
                    ))
                    logger.info("Ollama registered: %s", _models)
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


def _t2_latency() -> int:
    """简单耗时计算：模块级起始时间到现在的毫秒（精度够成本审计用）。"""
    return int((time.time() - _LLM_CALL_T0) * 1000)


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
                        tail = tail[len(_drop):].strip()
                msg["content"] = tail[:500]
                logger.info("[LLM] 推理模型响应 content=None，已从 reasoning 提取尾部答案（%d字）",
                            len(msg.get("content") or ""))
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
    provider: str = "deepseek",
) -> dict:
    """统一LLM调用接口（多provider自动切换）

    用法与 call_deepseek 一致，但会自动处理provider故障切换。
    R13（2026-08-01 三算力架构）：新增 provider 参数强制指定提供方——
      "deepseek" = 云端（默认）
      "ollama_local" = 本地 Ollama（机械任务：评分/格式检查）
      "agent_provider" = Marvis 队列（起草/修订，多实例并行）
    provider 指定的资源不可用时，回退到可用 provider（容错）。
    """
    import requests

    # R13: 强制指定 provider（若存在且未熔断）；否则按优先级取全部可用
    _active = lambda: sorted(
        (p for p in _registry._providers.values()
         if _registry._consecutive_failures.get(p.name, 0) < 5),
        key=lambda x: x.priority,
    )
    if provider and provider != "auto":
        target = _registry._providers.get(provider)
        if target and _registry._consecutive_failures.get(provider, 0) < 5:
            providers = [target]
        else:
            logger.warning("[LLM] 指定 provider=%s 不可用，回退按优先级", provider)
            providers = _active()
    else:
        providers = _active()
    if not providers:
        raise RuntimeError("No available LLM provider (all circuit-broken)")

    last_error = None
    # R77（2026-08-05）：强制指定的 provider 失败后应回退到其他可用 provider，
    # 而不是单元素列表失败即 raise。记录失败 → 若全部 provider 用尽则按优先级全量回退一轮。
    for provider in providers:
        # 可调用 provider（如 AgentProvider）——不走 HTTP，直接调用
        if hasattr(provider, "__call__") and not hasattr(provider, "base_url") or (
                hasattr(provider, "name") and provider.name == "agent_provider"):
            try:
                logger.info("[LLM] fallback 到可调用 provider: %s", provider.name)
                return provider(
                    messages, model=model, temperature=temperature,
                    max_tokens=max_tokens, stream=stream,
                )
            except Exception as e:
                last_error = e
                # R77（2026-08-05）：agent_provider 失败也要记录熔断，否则回退逻辑
                # 永远走不到（providers=[agent_provider] 单元素，失败即 raise）。
                # 记录失败后，下次 call_llm 会因 _consecutive_failures>=5 走全量回退。
                _registry.record_failure(provider.name)
                logger.warning("Agent provider failed: %s", e)
                continue

        # model 必须落在 provider 支持的模型列表内，否则使用 provider 首选模型
        m = model
        if provider.models and m not in provider.models:
            logger.info("Model %s not in provider %s models %s, using %s",
                        m, provider.name, provider.models, provider.models[0])
            m = provider.models[0]

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": m,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        # R53（2026-08-03 P1-4 修复）：provider 健康预检——发起完整请求前
        # 用短超时（5s）探测连通性。只有连接层失败（超时/DNS/拒绝连接）才跳过
        # provider；401/404 说明服务可达（只是端点路径不同），不跳过，继续完整请求。
        # 解决"6 组并行各等满 300s、一轮空耗 10 分钟"。
        if hasattr(provider, "base_url"):
            try:
                _probe_url = provider.base_url.replace("/v1", "").rstrip("/") + "/models"
                _probe_resp = requests.get(
                    _probe_url,
                    headers={"Authorization": headers["Authorization"]},
                    timeout=5,
                )
                # 5xx/连接异常视为服务不可用；4xx 视为可达（端点差异，继续完整请求）
                if _probe_resp.status_code >= 500:
                    raise ConnectionError(f"probe HTTP {_probe_resp.status_code}")
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectTimeout) as _pe:
                logger.warning("[LLM-PROBE] provider=%s 健康预检失败（跳过，避免300s空耗）: %s",
                              provider.name, str(_pe)[:80])
                _registry.record_failure(provider.name)
                continue
            except Exception:
                # 其他异常（401/404/解析等）——provider 可达，不跳过
                pass

        provider_ok = False
        for attempt in range(2):
            try:
                resp = requests.post(
                    f"{provider.base_url}/chat/completions",
                    headers=headers, json=payload,
                    timeout=int(os.environ.get("LLM_HTTP_TIMEOUT", "90")),  # 2026-08-07：300→90
                )
                resp.raise_for_status()
                _registry.record_success(provider.name)
                _resp = _normalize_llm_response(resp.json())
                # P3-2 成本日志（2026-08-07）：记录每次调用 token/通道/耗时，可观测性
                try:
                    from core.metrics import ObservabilityDB
                    _usage = _resp.get("usage", {})
                    ObservabilityDB().log_llm_call_simple(
                        module="call_llm", section_id=m,
                        prompt_tokens=_usage.get("prompt_tokens", 0),
                        completion_tokens=_usage.get("completion_tokens", 0),
                        latency_ms=int(_t2_latency()),
                        status="success",
                        provider=getattr(provider, "name", "unknown"),
                    )
                except Exception as _le:
                    logger.debug("[COST-LOG] %s", str(_le)[:50])
                return _resp
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning("LLM call attempt %d/2 failed (provider=%s model=%s): %s",
                              attempt+1, provider.name, m, e)
                if attempt < 1:
                    time.sleep(1)
        if not provider_ok:
            _registry.record_failure(provider.name)

    # R77（2026-08-05）：强制指定的 provider 失败 → 按优先级全量回退一轮
    # （此前单元素 providers 失败即 raise；agent_provider 队列积压/DeepSeek 网络抖动
    #  都会让原本可用的 provider 得不到机会）
    if provider and provider != "auto":
        _fallback = [p.name for p in _active() if p.name != provider]
        if _fallback:
            logger.warning("[LLM] 指定 provider=%s 全部失败，全量回退 %s",
                           provider, _fallback)
            try:
                return call_llm(messages, model=model, temperature=temperature,
                                max_tokens=max_tokens, stream=stream,
                                provider="auto")
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
    provider: str = "deepseek",
) -> dict:
    """兼容旧接口（provider 默认 deepseek；三算力架构传其他值路由）"""
    return call_llm(messages, model=model, temperature=temperature,
                    max_tokens=max_tokens, stream=stream, provider=provider)


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

    def complete(self, messages: list, temperature: float = 0.3,
                 max_tokens: int = 2048) -> str:
        """多消息对话，返回文本内容。"""
        r = call_deepseek(messages, model=self.model, temperature=temperature,
                          max_tokens=max_tokens)
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
        import re; json_match = re.search(r"\{.*\}", content, re.DOTALL)
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
