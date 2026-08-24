# -*- coding: utf-8 -*-
"""agent_provider.py — Agent 作为 LLM 主执行 provider（2026-08-01 用户决策：强制 Marvis 主执行）

原为 FP7d 兜底设计（DeepSeek 失败/熔断时 fallback），现按用户决策提升为
最高优先级（priority=-1），LLM 调用默认先落盘队列交给 agent（Marvis）执行。

工作机制（能力沙箱：agent 不直接写报告，只响应 LLM 请求）：
  1. call_llm 首先调用 agent_provider（priority=-1 < deepseek 的 0）
  2. agent_provider 把 LLM 请求落盘到 data/agent_llm_queue/<id>_request.json
  3. agent 侧运行 scripts/agent_llm_responder.py watch，看到请求后用自身能力生成回复
  4. agent 写回 <id>_response.json
  5. agent_provider 轮询到响应，返回 OpenAI 兼容格式给 call_llm
  6. 若 agent 超时/失败，call_llm 继续尝试下一个 provider（deepseek）作为降级

合规（FP7d，最高约束）：agent 只能作为 LLM provider 响应队列请求，
产出是"LLM 调用的返回值"，进入 section_writer 后仍走
StyleCompiler → IronGate → export 完整管线。
**严禁 agent 绕过管线直接写报告正文/MD/DOCX —— 出口指纹校验会拒绝无指纹产物。**
"""

from __future__ import annotations
import os, re, json, time, logging, uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = _ROOT / "data" / "agent_llm_queue"

# 兜底轮询参数（2026-08-07 调优：对齐三通道超时设计，原 300s 空等→120s）
POLL_INTERVAL = 2.0          # 轮询间隔（秒）
MAX_WAIT_SEC = 120           # 最长等待 agent 回复（120s，原 300s）
REQUEST_TTL = 300            # 请求文件过期时间（300s，原 600s）

logger = logging.getLogger("2hao.agent_provider")


class AgentProvider:
    """Agent LLM provider — 实现 OpenAI 兼容的 chat/completions 接口"""

    def __init__(self, name: str = "agent_provider", priority: int = 10):
        self.name = name
        self.priority = priority  # 2026-08-07 修复：-1 → 10（原 R81 注释意图"兜底"但
        # ProviderRegistry/call_llm 按升序取最小 priority → -1 实际是最高优先级，语义反转）。
        # agent_provider 仅作 P2 免费预取兜底——DeepSeek(0)/OpenRouter(1) 可用时不应抢主链。
        self.models = ["agent-writing"]
        self.api_key = ""  # 无需 key
        self.base_url = ""  # 不使用 HTTP
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Provider 接口（被 call_llm 调用）────────────────────
    def __call__(self, messages: list, model: str = "agent-writing",
                 temperature: float = 0.35, max_tokens: int = 4096,
                 stream: bool = False, timeout: int = None) -> dict:
        """处理一次 LLM 请求：落盘 → 等待 agent 响应 → 返回 OpenAI 格式"""
        # R77（2026-08-05）：心跳检测快速失败——沙箱/无 responder 环境会空等
        # MAX_WAIT_SEC=300s（test_audit_report / test_r61 触发 IronGate 挂死 5 分钟）。
        # 两层快速失败：
        #   a) 无活跃 responder：.heartbeat 文件 30s 内未更新 = responder 不在跑 →
        #      立即抛错，由 call_llm 回退到 DeepSeek/Ollama。
        #   b) 队列积压过期请求（REQUEST_TTL=600s 无响应）= responder 已停摆 →
        #      拒绝排入新请求，同样回退。
        _now = time.time()
        try:
            _hb = QUEUE_DIR / ".heartbeat"
            _hb_alive = False
            if _hb.exists():
                try:
                    _hb_ts = float(json.loads(_hb.read_text(encoding="utf-8")).get("ts", 0))
                    if _now - _hb_ts <= 30:
                        _hb_alive = True
                except (ValueError, KeyError, TypeError):
                    pass  # 心跳文件损坏视为无 responder
            # 无活跃 responder（无心跳/心跳过期）→ 快速失败，回退 DeepSeek。
            # 注意：不依赖"队列积压"判断——即使队列为空，无 responder 也是空等。
            if not _hb_alive:
                raise RuntimeError(
                    "Agent responder 不在线（无心跳/心跳过期 30s），回退其他 provider")
        except OSError:
            pass  # 队列目录不可读时继续（不阻塞主路径）
        req_id = uuid.uuid4().hex[:12]
        sys_prompt = ""
        user_prompt = ""
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "system":
                sys_prompt += content + "\n"
            elif role == "user":
                user_prompt += content + "\n"

        request = {
            "id": req_id,
            "type": "llm_request",
            "created_at": time.time(),
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "system_prompt": sys_prompt.strip(),
            "user_prompt": user_prompt.strip(),
            "messages": messages,
            # R67（2026-08-04）：质量要求字段——给 agent 兜底明确的输出规格，
            # 缓解"agent 响应质量随机"（柯力事故：attempt3 兜底写泛化稿）。
            "quality_requirements": {
                "min_chars": 150,
                "no_placeholder": True,   # 禁止返回"请求超时/失败/稍后重试"占位
                "no_refusal": True,       # 禁止拒绝生成（"我无法完成"类）
                "must_match_request": True,
            },
        }
        req_path = QUEUE_DIR / f"{req_id}_request.json"
        req_path.write_text(json.dumps(request, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        logger.info("[AGENT-LLM] 请求 %s 已落盘，等待 agent 兜底回复...", req_id)

        # 轮询等待 agent 响应
        resp_path = QUEUE_DIR / f"{req_id}_response.json"
        deadline = time.time() + (timeout or MAX_WAIT_SEC)
        try:
            while time.time() < deadline:
                if resp_path.exists():
                    try:
                        resp = json.loads(resp_path.read_text(encoding="utf-8"))
                        if resp.get("status") == "completed":
                            content = resp.get("content", "")
                            # R67 质量护栏：agent 兜底响应质量校验
                            # （柯力事故根因：无质量校验，200字/4000字/占位符都接受）
                            _q_issue = _check_agent_response_quality(content)
                            if _q_issue:
                                logger.warning("[AGENT-LLM] 请求 %s 响应质量不达标(%s)，忽略重等...",
                                               req_id, _q_issue)
                                # 删除坏响应，等待 agent 重写（重试窗口内）
                                try:
                                    resp_path.unlink()
                                except OSError:
                                    pass
                                time.sleep(POLL_INTERVAL)
                                continue
                            self._cleanup(req_id)
                            logger.info("[AGENT-LLM] 请求 %s 收到 agent 回复 (%d chars)",
                                        req_id, len(content))
                            return {
                                "choices": [{"message": {"role": "assistant",
                                                         "content": content}}],
                                "id": req_id,
                                "object": "chat.completion",
                                "model": model,
                            }
                        elif resp.get("status") == "failed":
                            self._cleanup(req_id)
                            raise RuntimeError(
                                f"Agent 兜底失败: {resp.get('error', 'unknown')}")
                    except json.JSONDecodeError:
                        pass  # agent 还在写，重试
                time.sleep(POLL_INTERVAL)
            # 超时：清理并抛出，触发 L3
            self._cleanup(req_id)
            raise RuntimeError(
                f"Agent 兜底超时（{int(MAX_WAIT_SEC)}s 无响应）。"
                f"请运行: python scripts/agent_llm_responder.py watch")
        except KeyboardInterrupt:
            self._cleanup(req_id)
            raise

    def _cleanup(self, req_id: str):
        """清理请求/响应文件"""
        try:
            for f in [QUEUE_DIR / f"{req_id}_request.json",
                      QUEUE_DIR / f"{req_id}_response.json"]:
                if f.exists():
                    f.unlink()
        except Exception:
            pass


def _check_agent_response_quality(content: str) -> str | None:
    """R67 质量护栏：校验 agent 兜底响应质量，返回问题描述或 None。

    柯力事故教训：agent 兜底响应质量随机（attempt3 写出泛化行业稿），
    无任何校验即被接受。这里拦截明显不合格的响应：
      1. 空/过短（<150 字）：无法构成有效分析段
      2. 占位符（"请求超时/失败/稍后重试"）：agent 未真正生成
      3. 拒绝生成（"我无法完成/不能提供"）：非有效分析
      4. 与请求明显不符（无正文结构）——由调用方 segment 长度约束兜底
    """
    if not content or not isinstance(content, str):
        return "空响应"
    stripped = content.strip()
    if len(stripped) < 150:
        return f"过短({len(stripped)}字<150)"
    lower = stripped.lower()
    placeholders = ["请求超时", "请求失败", "稍后重试", "请稍等", "timeout", "failed to",
                    "重试失败", "服务暂不可用", "queue empty", "无待处理请求"]
    for ph in placeholders:
        if ph in lower:
            return f"占位/错误响应(含'{ph}')"
    refusals = ["我无法完成", "无法生成", "不能提供", "抱歉，我", "对不起，我",
                "i cannot", "i'm unable", "i am unable"]
    for rf in refusals:
        if rf in lower:
            return f"拒绝生成(含'{rf}')"
    return None


# 注册进全局 ProviderRegistry（P2 免费预取，priority=10，排在 DeepSeek 之后）
def register_agent_provider(registry=None) -> AgentProvider:
    """把 AgentProvider 注册进 ProviderRegistry（P2 兜底，非主路径）。"""
    from core.deepseek_client import _registry as default_registry
    reg = registry or default_registry
    provider = AgentProvider()
    # 若已注册则跳过
    if reg._providers.get("agent_provider"):
        return reg._providers["agent_provider"]
    # 直接注入 _providers（AgentProvider 不是 ProviderConfig 但实现了 __call__）
    reg._providers["agent_provider"] = provider
    logger.info("AgentProvider registered as P2 fallback LLM provider (priority=%d)", provider.priority)
    return provider


# 自动注册（幂等）
try:
    register_agent_provider()
except Exception as e:
    logger.warning("AgentProvider 注册跳过: %s", e)
