# -*- coding: utf-8 -*-
"""marvis_prefetch.py — Marvis P2 免费预取通道（2026-08-07）

核心设计（对齐三资源配置方案）：
  - DeepSeek 主链跑的时候，Marvis 免费通道在后台异步产候选草稿
  - channel=marvis 显式标记，落 10_draft/candidates/（不阻塞主链）
  - 失败即弃：候选不可用/过期/质量不过 → 主链照常，零影响
  - 绝不进终稿合并层：候选过 verifier 才可被选用（free/paid 来源标记）

用法：
  pm = MarvisPrefetch()
  pm.submit(asset, seg_name, prompt)      # 后台预取（线程池）
  cand = pm.poll(seg_name)                 # 取可用候选（无则 None）
  pm.cleanup()                              # 清理过期候选

只读环境变量：
  MARVIS_PREFETCH=1       # 开关（默认关，responder 在线才建议开）
  MARVIS_PREFETCH_TTL=600 # 候选过期秒数
"""
from __future__ import annotations
import os, json, time, threading, logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.marvis_prefetch")

_ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_DIR = _ROOT / "output" / "marvis_candidates"
TTL = int(os.environ.get("MARVIS_PREFETCH_TTL", "600"))


class MarvisPrefetch:
    """Marvis 免费预取通道（线程池后台生产候选草稿）。"""

    def __init__(self, candidate_dir: Optional[Path] = None):
        self.candidate_dir = Path(candidate_dir or CANDIDATE_DIR)
        self.candidate_dir.mkdir(parents=True, exist_ok=True)
        self._pool = []
        self._lock = threading.Lock()
        self._alive = self._check_responder()

    @staticmethod
    def _check_responder() -> bool:
        """检查 Marvis responder 是否在线（心跳 30s 内）。"""
        if not os.environ.get("MARVIS_PREFETCH", "0") == "1":
            return False
        try:
            hb = _ROOT / "data" / "agent_llm_queue" / ".heartbeat"
            if hb.exists():
                ts = float(json.loads(hb.read_text(encoding="utf-8")).get("ts", 0))
                return (time.time() - ts) <= 30
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return False

    def enabled(self) -> bool:
        return self._alive

    def submit(self, asset: str, seg_name: str, prompt: str):
        """后台提交一个预取请求（不阻塞）。"""
        if not self._alive:
            return
        t = threading.Thread(target=self._worker, args=(asset, seg_name, prompt),
                             daemon=True)
        with self._lock:
            self._pool.append(t)
        t.start()
        logger.info("[MARVIS-PREFETCH] 后台预取 %s/%s 启动", asset, seg_name)

    def poll(self, asset: str, seg_name: str) -> Optional[str]:
        """取可用候选草稿（无则 None）。候选必须：存在 + 未过期 + 非占位。"""
        try:
            _safe = seg_name.replace("/", "_").replace("\\", "_")[:50]
            p = self.candidate_dir / f"{_safe}.json"
            if not p.exists():
                return None
            data = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - data.get("ts", 0) > TTL:
                try:
                    p.unlink()
                except OSError:
                    pass
                return None
            content = data.get("content", "")
            if len(content) < 150:
                return None
            return content
        except (OSError, json.JSONDecodeError):
            return None

    def cleanup(self):
        """清理过期候选。"""
        try:
            for p in self.candidate_dir.glob("*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if time.time() - data.get("ts", 0) > TTL:
                        p.unlink()
                except (json.JSONDecodeError, OSError):
                    p.unlink()
        except OSError:
            pass

    # ── 内部 ─────────────────────────────────────────────

    def _worker(self, asset: str, seg_name: str, prompt: str):
        """实际预取：走 agent_provider（Marvis 队列），失败静默。"""
        try:
            from core.agent_provider import AgentProvider
            provider = AgentProvider()
            # 短超时：预取失败不影响主链
            resp = provider([{"role": "user", "content": prompt}],
                            max_tokens=2048, timeout=60)
            content = resp["choices"][0]["message"]["content"]
            if content and len(content.strip()) >= 150:
                _safe = seg_name.replace("/", "_").replace("\\", "_")[:50]
                out = {
                    "asset": asset,
                    "seg_name": seg_name,
                    "channel": "marvis",   # 免费来源标记
                    "ts": time.time(),
                    "content": content,
                }
                (self.candidate_dir / f"{_safe}.json").write_text(
                    json.dumps(out, ensure_ascii=False), encoding="utf-8")
                logger.info("[MARVIS-PREFETCH] %s/%s 候选就绪 (%d字)", asset, seg_name, len(content))
            else:
                logger.info("[MARVIS-PREFETCH] %s/%s 候选过短，丢弃", asset, seg_name)
        except Exception as e:
            logger.debug("[MARVIS-PREFETCH] %s/%s 失败（静默，不影响主链）: %s",
                         asset, seg_name, str(e)[:60])
