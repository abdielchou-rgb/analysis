# -*- coding: utf-8 -*-
"""backfill_deepseek_watch.py — 队列自动响应（DeepSeek 后端）

train 模式下写作端经 agent_provider 落盘队列等待 agent 兜底响应；
本脚本以 DeepSeek 为能力后端持续消费新请求，写回 response.json，
供 agent_provider 轮询取回（合规：响应仅为 LLM 调用返回值，仍走完整管线）。
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

QUEUE_DIR = _ROOT / "data" / "agent_llm_queue"

# 读注册表注入 key（独立进程时父进程可能无 key）
try:
    import subprocess as _sp

    _k = _sp.run(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    _key = _k.stdout.strip()
    if _key:
        os.environ["DEEPSEEK_API_KEY"] = _key
except Exception:
    pass

from core.deepseek_client import call_llm


def respond(req_path: Path):
    req_id = req_path.name.replace("_request.json", "")
    resp_path = QUEUE_DIR / f"{req_id}_response.json"
    if resp_path.exists():
        return
    try:
        r = json.loads(req_path.read_text(encoding="utf-8"))
    except Exception:
        return
    sys_p = (r.get("system_prompt") or "").strip()
    usr_p = (r.get("user_prompt") or "").strip()
    msgs = []
    if sys_p:
        msgs.append({"role": "system", "content": sys_p})
    msgs.append({"role": "user", "content": usr_p or "继续"})
    mt = r.get("max_tokens") or 4096
    for temp in (0.35, 0.6):
        try:
            resp = call_llm(msgs, model="deepseek-chat", temperature=temp, max_tokens=mt, provider="deepseek")
            content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
            if len(content.strip()) < 150:
                print(f"[SHORT] {req_id} len={len(content.strip())}, retry temp={temp}")
                continue
            payload = {
                "id": req_id,
                "status": "completed",
                "content": content,
                "responded_at": time.time(),
                "responded_by": "marvis-deepseek",
            }
            resp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[OK] {req_id} {len(content)} chars temp={temp}")
            return
        except Exception as e:
            print(f"[FAIL] {req_id} {str(e)[:150]}")
    # 双温度都失败：写 failed 让 provider 快速失败
    try:
        resp_path.write_text(
            json.dumps(
                {
                    "id": req_id,
                    "status": "failed",
                    "error": "deepseek backfill failed",
                    "responded_at": time.time(),
                    "responded_by": "marvis-deepseek",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def watch():
    seen = set()
    print("[WATCH-DS] 队列自动响应启动（DeepSeek 后端）")
    while True:
        try:
            reqs = sorted(QUEUE_DIR.glob("*_request.json"))
            for f in reqs:
                req_id = f.name.replace("_request.json", "")
                if req_id in seen:
                    continue
                seen.add(req_id)
                threading.Thread(target=respond, args=(f,), daemon=True).start()
        except Exception as e:
            print("[WATCH-ERR]", str(e)[:120])
        time.sleep(3)


if __name__ == "__main__":
    watch()
