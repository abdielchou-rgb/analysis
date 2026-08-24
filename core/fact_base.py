# -*- coding: utf-8 -*-
"""fact_base.py — 行业事实库（P2-2，2026-08-07）

把"行业事实点"结构化沉淀为可检索的事实库（工作台文档的缺口）：
  - 从"方法论洞察"升级为"可检索事实点"
  - 数据分级（R87）：verified / corrected / unverified
  - 每条带 source + intent 归属（回答哪个必答问题）
  - 持续累积：用户纠偏 → corrected 条目 → 下次不再犯

用法：
  fb = FactBase()
  fb.add("油位市场规模", "全球46亿美元(2024)", level="verified", source="行业研报", intent="市场规模")
  results = fb.search("油位 市场")
  fb.correct("油位市场规模", "全球46亿→65亿美元(2030)")  # 纠偏 → corrected
"""
from __future__ import annotations
import os, json, time, logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("2hao.fact_base")

_ROOT = Path(__file__).resolve().parent.parent
FACT_BASE_FILE = _ROOT / "data" / "fact_base.json"

# 数据分级（R87 对齐）
LEVELS = {"verified", "corrected", "unverified"}


class FactBase:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or FACT_BASE_FILE)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {"version": 1, "facts": {}}

    def _save(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1),
                             encoding="utf-8")

    def add(self, fact_id: str, value: str, level: str = "verified",
            source: str = "", intent: str = "", tags: Optional[list] = None) -> None:
        """新增/更新事实点。level: verified/corrected/unverified。"""
        level = level if level in LEVELS else "unverified"
        self.data["facts"][fact_id] = {
            "value": value,
            "level": level,
            "source": source,
            "intent": intent,
            "tags": tags or [],
            "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "history": self.data["facts"].get(fact_id, {}).get("history", []),
        }
        self._save()
        logger.info("[FACT-BASE] %s=%s (%s)", fact_id, value[:40], level)

    def correct(self, fact_id: str, value: str, source: str = "用户纠偏") -> None:
        """纠偏：旧值入 history，新值标 corrected。"""
        prev = self.data["facts"].get(fact_id, {})
        history = prev.get("history", [])
        if prev.get("value"):
            history.append({"old": prev["value"], "old_level": prev.get("level"),
                            "corrected_to": value, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
        self.data["facts"][fact_id] = {
            "value": value,
            "level": "corrected",
            "source": source,
            "intent": prev.get("intent", ""),
            "tags": prev.get("tags", []),
            "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "history": history,
        }
        self._save()
        logger.info("[FACT-BASE] 纠偏 %s: %s → %s", fact_id, prev.get("value", "?"), value[:40])

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """简易字符相似度（近似 embedding：ngram 重叠率）。"""
        a, b = a.lower(), b.lower()
        if not a or not b:
            return 0.0
        # 字符 3-gram 集合
        ga = {a[i:i+3] for i in range(len(a)-2)} if len(a) >= 3 else {a}
        gb = {b[i:i+3] for i in range(len(b)-2)} if len(b) >= 3 else {b}
        inter = len(ga & gb)
        union = len(ga | gb) or 1
        return inter / union

    def search(self, query: str, intent: str = "") -> list:
        """检索事实点（关键词/意图匹配），verified/corrected 优先。"""
        q = query.lower()
        results = []
        for fid, f in self.data.get("facts", {}).items():
            hay = f"{fid} {f.get('value','')} {' '.join(f.get('tags',[]))}".lower()
            if q in hay or any(t.lower() in q for t in f.get("tags", [])):
                if intent and intent.lower() not in f"{fid} {f.get('intent','')}".lower():
                    continue
                results.append({"id": fid, **f})
        # 相似度排序（embedding 近似）
        for r in results:
            r["_sim"] = self._similarity(query, f"{r.get('id','')} {r.get('value','')}")
        # 分级排序 + 相似度
        rank = {"corrected": 0, "verified": 1, "unverified": 2}
        results.sort(key=lambda x: (rank.get(x.get("level", "unverified"), 3), -x.get("_sim", 0)))
        return results

    def get(self, fact_id: str) -> Optional[dict]:
        return self.data.get("facts", {}).get(fact_id)

    def stats(self) -> dict:
        facts = self.data.get("facts", {})
        from collections import Counter
        levels = Counter(f.get("level", "unverified") for f in facts.values())
        return {"total": len(facts), "levels": dict(levels)}

    def build_prompt(self, query: str = "", intent: str = "", limit: int = 10) -> str:
        """生成注入写作 prompt 的事实库块（分级标注）。"""
        results = self.search(query, intent)[:limit]
        if not results:
            return ""
        lines = ["=== 行业事实库（分级：verified可直接引用 / corrected已修正 / unverified须标E）==="]
        for r in results:
            mark = {"verified": "✓", "corrected": "✎修正", "unverified": "△"} \
                .get(r.get("level", "unverified"), "?")
            lines.append(f"- [{mark}] {r['id']}: {r.get('value','')}"
                         + (f"（来源:{r.get('source','')}）" if r.get("source") else ""))
        lines.append("=== 事实库结束 ===")
        return "\n".join(lines)
