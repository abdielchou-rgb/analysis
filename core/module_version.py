# -*- coding: utf-8 -*-
"""module_version.py — 模块版本管理（P0-2 地基，2026-08-07）

目标：把"整篇迭代"降为"单模块迭代"（R79-R87 八轮全量重写不收敛的根治方向）。

核心概念：
  - 模块（module）= 可独立评审/修复的最小单元（SAC 维度/章节/论点单元）
  - 每个模块保留版本历史（v1/v2/v3...），可回滚、可对比
  - frozen_facts = 模块锚定的不可变事实（数字/口径/引用），影响传播的依据

用法：
  mv = ModuleVersion(asset="柯力传感")
  v1 = mv.checkout("founder_ri")          # 取最新版（无则 None）
  mv.commit("founder_ri", "正文...", {"frozen_facts": {...}})  # 新版本 v2
  mv.rollback("founder_ri")               # 回滚到上一版
  mv.dependents("founder_ri")             # 依赖该模块的模块列表（影响传播）
  mv.mark_dirty("biz_model")              # 标记下游待重校验
"""
from __future__ import annotations
import os, json, time, hashlib, logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.module_version")

_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VERSION_DIR = _ROOT / "data" / "module_versions"
MAX_VERSIONS = 10  # 每模块最多保留版本数，防磁盘膨胀


class ModuleVersion:
    """模块版本管理器（每报告独立命名空间，工作区隔离）"""

    def __init__(self, asset: str, version_dir: Optional[Path] = None):
        self.asset = asset
        self.version_dir = Path(version_dir or DEFAULT_VERSION_DIR)
        # 工作区隔离：每报告独立目录，防跨任务污染
        self.asset_dir = self.version_dir / _safe(asset)
        self.asset_dir.mkdir(parents=True, exist_ok=True)

    # ── 版本生命周期 ─────────────────────────────────────

    def commit(self, module_id: str, content: str,
               metadata: Optional[dict] = None) -> dict:
        """提交一个新版本（自动递增版本号）。metadata 可带 frozen_facts/source 等。"""
        module_id = _safe(module_id)
        meta = dict(metadata or {})
        prev = self.latest(module_id)
        ver = (prev.get("version", 0) + 1) if prev else 1
        entry = {
            "module_id": module_id,
            "version": ver,
            "content": content,
            "hash": hashlib.md5((content or "").encode("utf-8")).hexdigest()[:12],
            "frozen_facts": meta.get("frozen_facts", {}),
            "source": meta.get("source", ""),
            "parent_version": (prev.get("version") if prev else None),
            "timestamp": time.time(),
            "status": meta.get("status", "active"),
        }
        # 保留额外 metadata（dirty_reason 等），不丢用户传入信息
        for _k in ("dirty_reason",):
            if _k in meta:
                entry[_k] = meta[_k]
        path = self._ver_path(module_id, ver)
        path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        self._prune(module_id)
        logger.info("[MODVER] %s/%s v%d committed (%d chars)",
                    self.asset, module_id, ver, len(content or ""))
        return entry

    def latest(self, module_id: str) -> Optional[dict]:
        """取最新版本（无则 None）。"""
        versions = self._versions(module_id)
        if not versions:
            return None
        return versions[-1]

    def get(self, module_id: str, version: int) -> Optional[dict]:
        """取指定版本。"""
        p = self._ver_path(module_id, version)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def rollback(self, module_id: str) -> Optional[dict]:
        """回滚到上一版：删除最新版，返回上一版。无历史则返回 None。"""
        module_id = _safe(module_id)
        versions = self._versions(module_id)
        if len(versions) < 2:
            logger.warning("[MODVER] %s/%s 无历史可回滚", self.asset, module_id)
            return None
        last = versions[-1]
        try:
            (self._ver_path(module_id, last["version"])).unlink()
        except (OSError, KeyError) as e:
            logger.warning("[MODVER] 删除失败: %s", e)
            return None
        prev = versions[-2]
        logger.info("[MODVER] %s/%s rollback → v%d", self.asset, module_id, prev.get("version"))
        return prev

    def mark_dirty(self, module_id: str, reason: str = ""):
        """标记模块为 dirty（待重校验），影响传播的入口。"""
        latest = self.latest(module_id)
        if not latest:
            return
        self.commit(
            module_id, latest["content"],
            metadata={
                "frozen_facts": latest.get("frozen_facts", {}),
                "status": "dirty",
                "dirty_reason": reason,
                "source": latest.get("source", ""),
            },
        )
        logger.info("[MODVER] %s/%s marked dirty (%s)", self.asset, module_id, reason[:60])

    def dependents(self, module_id: str, dependency_map: dict) -> list[str]:
        """返回依赖本模块的模块列表（影响范围传播）。

        dependency_map: {module_id: [依赖的 module_id, ...]}（input_contract 反向）
        """
        return [k for k, deps in dependency_map.items() if module_id in deps]

    # ── 内部工具 ─────────────────────────────────────────

    def _versions(self, module_id: str) -> list:
        mod_dir = self.asset_dir / module_id
        if not mod_dir.exists():
            return []
        files = sorted(
            mod_dir.glob("v*.json"),
            key=lambda p: int(p.stem[1:]),
        )
        out = []
        for p in files:
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return out

    def _ver_path(self, module_id: str, version: int) -> Path:
        mod_dir = self.asset_dir / module_id
        mod_dir.mkdir(parents=True, exist_ok=True)
        return mod_dir / f"v{version}.json"

    def _prune(self, module_id: str):
        versions = self._versions(module_id)
        if len(versions) <= MAX_VERSIONS:
            return
        for entry in versions[:-MAX_VERSIONS]:
            try:
                (self._ver_path(module_id, entry["version"])).unlink()
            except (OSError, KeyError):
                pass


def _safe(name: str) -> str:
    """文件名安全化：去路径/空格/中文转拼音风险→用 hash 兜底。"""
    import re as _re
    cleaned = _re.sub(r"[^\w\-.]+", "_", str(name).strip())
    if not cleaned or len(cleaned) > 80:
        cleaned = cleaned[:40] + "_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    return cleaned
