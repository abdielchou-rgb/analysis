#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_llm_responder.py — Agent 作为 LLM 主执行 provider 的响应端

强制 Marvis 主执行（2026-08-01 用户决策）：AgentProvider priority=-1 为最高优先级，
管线 call_llm 默认先落盘队列到 data/agent_llm_queue/（DeepSeek 仅作降级）。
本脚本（由 agent 侧运行）watch 该队列，发现请求后用 agent 自身能力生成回复，
写回 response 文件，管线继续执行。

用法:
    python scripts/agent_llm_responder.py watch        # 持续监听（agent 运行）
    python scripts/agent_llm_responder.py list         # 查看待处理请求
    python scripts/agent_llm_responder.py respond <id> # 手动处理单个请求

合规（FP7d，最高约束）：本脚本产出的文本是 LLM 调用的返回值，进入 section_writer 后
仍走 StyleCompiler → IronGate → export 完整管线。agent 不直接写报告文件，
严禁绕过管线直接产出报告正文/MD/DOCX。
"""

import argparse, json, os, sys, time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = _ROOT / "data" / "agent_llm_queue"


def _pending_requests() -> list:
    if not QUEUE_DIR.exists():
        return []
    return sorted(QUEUE_DIR.glob("*_request.json"))


def cmd_list() -> int:
    reqs = _pending_requests()
    if not reqs:
        print("(空) 无待处理的 agent LLM 兜底请求")
        return 0
    print(f"{'ID':<16} {'模型':<20} {'创建时间':<20} 提示长度")
    print("-" * 70)
    for f in reqs:
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            created = time.strftime("%H:%M:%S", time.localtime(r.get("created_at", 0)))
            print(f"{r.get('id',''):<16} {r.get('model',''):<20} {created:<20} {len(r.get('user_prompt',''))}")
        except Exception:
            print(f"{f.stem:<16} (解析失败)")
    print(f"\n{len(reqs)} 个待处理。处理: python scripts/agent_llm_responder.py respond <id>")
    return 0


def _detect_agent() -> str:
    """自动探测当前兜底 agent 身份。默认 marvis（用户配置）。"""
    env = os.environ.get("AGENT_LLM_BACKFILLER", "").strip()
    if env:
        return env
    return "marvis"


def _respond(req_id: str, content: str = None, agent: str = None) -> int:
    """处理单个请求。content 由 agent 传入；若为空则提示 agent 需要提供内容。"""
    req_path = QUEUE_DIR / f"{req_id}_request.json"
    resp_path = QUEUE_DIR / f"{req_id}_response.json"
    if not req_path.exists():
        print(f"[!!] 请求 {req_id} 不存在")
        return 1

    r = json.loads(req_path.read_text(encoding="utf-8"))
    if content is None:
        # agent 需要亲自生成内容（本脚本只负责通道）
        print("=" * 60)
        print(f"[AGENT-LLM] 请求 {req_id} 需要你兜底写作")
        print(f"  模型: {r.get('model')}")
        print(f"  System: {r.get('system_prompt','')[:200]}")
        print(f"  User: {r.get('user_prompt','')[:500]}")
        print("=" * 60)
        print("\n请用你的分析能力生成正文（作为 LLM 返回值），然后运行：")
        print(f"  python scripts/agent_llm_responder.py respond {req_id} --content \"<你的正文>\" --agent marvis")
        print("  或把正文写入文件后：")
        print(f"  python scripts/agent_llm_responder.py respond {req_id} --file <path> --agent marvis")
        return 2  # 需要 agent 介入

    agent_name = agent or _detect_agent()
    response = {
        "id": req_id,
        "status": "completed",
        "content": content,
        "responded_at": time.time(),
        "responded_by": agent_name,
    }
    resp_path.write_text(json.dumps(response, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"[✓] 请求 {req_id} 已回复 ({len(content)} chars) by {agent_name}")
    return 0


def cmd_respond(req_id: str, content: str = None, file: str = None,
                agent: str = None) -> int:
    if file:
        content = Path(file).read_text(encoding="utf-8")
    return _respond(req_id, content, agent)


def _auto_respond(req_id: str, r: dict, ollama_model: str = "qwen3:14b") -> bool:
    """用本地 Ollama 生成响应并写回（2026-08-01 优化）。

    返回 True 表示已响应；False 表示需人工处理。
    """
    import requests
    try:
        messages = []
        sys_p = (r.get("system_prompt") or "").strip()
        usr_p = (r.get("user_prompt") or "").strip()
        if sys_p:
            messages.append({"role": "system", "content": sys_p})
        if usr_p:
            messages.append({"role": "user", "content": usr_p})
        if not messages:
            messages = r.get("messages") or [{"role": "user", "content": "继续"}]
        resp = requests.post("http://localhost:11434/api/chat",
                             json={"model": ollama_model, "messages": messages,
                                   "stream": False,
                                   "options": {"temperature": 0.3, "num_predict": 3000}},
                             timeout=180)
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            if content:
                _respond(req_id, content, agent=f"ollama:{ollama_model}")
                return True
        print(f"[!] Ollama 响应 {req_id} 失败({resp.status_code})，转人工处理")
    except Exception as e:
        print(f"[!] Ollama 响应 {req_id} 异常: {str(e)[:80]}，转人工处理")
    return False


def cmd_watch(poll: float = 3.0, auto_ollama: bool = False, ollama_model: str = "qwen3:14b",
              max_workers: int = 4) -> int:
    """持续监听队列。

    auto_ollama=True: 用本地 Ollama 并发生成响应（2026-08-01 优化）。
      - 解决 AgentProvider 阻塞轮询在并行 write/critic 下的请求堆积
      - 本地 Ollama 免费，不耗 DeepSeek token
      - 并发处理堆积请求，Marvis 可人工介入高价值请求
    R77（2026-08-05）：每次轮询更新心跳文件（data/agent_llm_queue/.heartbeat），
    供 AgentProvider 判断"是否有活跃 responder 在消费"。无 responder 时
    provider 快速失败回退 DeepSeek，不再空等 MAX_WAIT_SEC。
    """
    import threading
    print(f"[WATCH] 监听 {QUEUE_DIR} (每 {poll}s)... Ctrl+C 退出")
    print(f"  auto_ollama={auto_ollama} model={ollama_model} workers={max_workers}" if auto_ollama
          else "  (人工模式：看到新请求用 respond 命令处理)")
    seen = set()
    lock = threading.Lock()

    try:
        while True:
            # R77：心跳——标记 responder 活跃
            try:
                (QUEUE_DIR / ".heartbeat").write_text(
                    json.dumps({"ts": time.time(), "pid": os.getpid()}), encoding="utf-8")
            except OSError:
                pass
            pending = _pending_requests()
            for f in pending:
                req_id = f.stem.replace("_request", "")
                with lock:
                    if req_id in seen:
                        continue
                    seen.add(req_id)
                if auto_ollama:
                    try:
                        r = json.loads(f.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    # 并发提交 Ollama 生成
                    threading.Thread(target=_auto_respond, args=(req_id, r, ollama_model),
                                     daemon=True).start()
                else:
                    print(f"\n[新请求] {req_id} — 用以下命令处理:")
                    print(f"  python scripts/agent_llm_responder.py respond {req_id}")
            time.sleep(poll)
    except KeyboardInterrupt:
        print("\n[WATCH] 退出")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Agent LLM 兜底响应端")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_watch = sub.add_parser("watch", help="持续监听队列")
    p_watch.add_argument("--agent", default=None, help="兜底 agent 名（默认 marvis）")
    p_watch.add_argument("--poll", type=float, default=3.0, help="轮询间隔（秒）")
    p_watch.add_argument("--auto-ollama", action="store_true",
                         help="用本地 Ollama 并发生成响应（2026-08-01 优化，免费）")
    p_watch.add_argument("--ollama-model", default="qwen3:14b", help="Ollama 模型")
    p_watch.add_argument("--max-workers", type=int, default=4, help="并发上限")
    sub.add_parser("list", help="查看待处理请求")
    p_resp = sub.add_parser("respond", help="处理单个请求")
    p_resp.add_argument("req_id")
    p_resp.add_argument("--content", default=None, help="直接提供正文")
    p_resp.add_argument("--file", default=None, help="从文件读正文")
    p_resp.add_argument("--agent", default=None, help="兜底 agent 名（默认 marvis）")
    args = parser.parse_args()

    if args.cmd == "watch":
        return cmd_watch(poll=args.poll, auto_ollama=args.auto_ollama,
                         ollama_model=args.ollama_model, max_workers=args.max_workers)
    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "respond":
        return cmd_respond(args.req_id, args.content, args.file, args.agent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
