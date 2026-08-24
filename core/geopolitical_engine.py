# -*- coding: utf-8 -*-
"""中美竞争/地缘政治分析引擎 — R78 全量优化。

对标顶级机构（高盛政策时间线 / 大摩双轨情景 / 中金国产替代映射）：
  1. 政策时间线：管制/关税/补贴事件 + 受影响环节（data/geo_events.json）
  2. 双轨情景：脱钩加速 vs 缓和，各给概率 + 影响方向
  3. 国产替代传导：卡脖子环节 → 受益环节（复用 bottleneck 思路）
  4. 量化指标：对美暴露度 / 自主可控度

用法：
    from core.geopolitical_engine import GeopoliticalEngine
    eng = GeopoliticalEngine()
    result = eng.analyze(industry_hint="半导体")
    geo_str = eng.build_injection(result)
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger("2hao.geopolitical")

_ROOT = Path(__file__).resolve().parent.parent
_GEO_EVENTS_PATH = _ROOT / "data" / "geo_events.json"


class GeopoliticalEngine:
    """中美竞争分析引擎。"""

    def __init__(self):
        self.events = self._load_events()

    def _load_events(self) -> list:
        """加载政策时间线事件。"""
        if not _GEO_EVENTS_PATH.exists():
            logger.warning("[GEO] geo_events.json 不存在（需采集）")
            return []
        try:
            data = json.loads(_GEO_EVENTS_PATH.read_text(encoding="utf-8"))
            return data.get("events", [])
        except Exception as e:
            logger.warning("[GEO] 事件加载失败: %s", str(e)[:80])
            return []

    def filter_by_industry(self, industry_hint: str) -> list:
        """按行业筛选事件（行业名匹配或 'all' 通用）。"""
        if not industry_hint:
            return self.events
        matched = []
        for ev in self.events:
            tags = [t.lower() for t in ev.get("tags", [])]
            ind = industry_hint.lower()
            if "all" in tags or any(ind in t for t in tags) or any(t in ind for t in tags):
                matched.append(ev)
        return matched

    def build_timeline(self, industry_hint: str = "") -> list[dict]:
        """政策时间线：按日期排序的事件列表。"""
        events = self.filter_by_industry(industry_hint)
        return sorted(events, key=lambda x: x.get("date", ""), reverse=True)

    def scenario_analysis(self, industry_hint: str = "") -> dict:
        """双轨情景：脱钩加速 vs 缓和。基于事件密度/方向推断概率。"""
        events = self.filter_by_industry(industry_hint)
        if not events:
            return {
                "tracks": [
                    {"name": "脱钩加速", "probability": 0.5, "impact": "negative", "note": "数据不足，默认中性"},
                    {"name": "缓和/再挂钩", "probability": 0.5, "impact": "positive", "note": "数据不足，默认中性"},
                ]
            }
        # 方向计数：restrict=压制（加剧脱钩），relax=缓和，subsidy=补贴（对冲）
        restrict = sum(1 for e in events if e.get("direction") == "restrict")
        relax = sum(1 for e in events if e.get("direction") == "relax")
        total = len(events)
        if total == 0:
            prob_deco = 0.5
        else:
            # 基础 0.5 + 压制事件净占比影响
            prob_deco = min(0.85, max(0.15, 0.5 + (restrict - relax) / max(total, 1) * 0.4))
        return {
            "tracks": [
                {"name": "脱钩加速", "probability": round(prob_deco, 2),
                 "impact": "negative", "note": f"{restrict} 项压制事件"},
                {"name": "缓和/再挂钩", "probability": round(1 - prob_deco, 2),
                 "impact": "positive", "note": f"{relax} 项缓和事件"},
            ]
        }

    def substitution_mapping(self, industry_hint: str = "") -> list[dict]:
        """国产替代传导：从事件 tags 推导受影响环节 → 受益环节。"""
        events = self.filter_by_industry(industry_hint)
        # 从事件中提取"受影响环节"标签
        affected = set()
        for ev in events:
            for t in ev.get("tags", []):
                if t != "all" and t != industry_hint.lower():
                    affected.add(t)
        # 通用替代逻辑（行业可覆盖）
        mapping = []
        for a in sorted(affected)[:5]:
            mapping.append({
                "affected_segment": a,
                "substitution_direction": "国产替代加速",
                "beneficiary_note": f"{a} 环节受管制 → 国产厂商承接替代需求",
            })
        return mapping

    def exposure_metrics(self, industry_hint: str = "") -> dict:
        """量化指标：对美暴露度 / 自主可控度（0-10 分制，数据驱动估算）。"""
        events = self.filter_by_industry(industry_hint)
        # 基于事件密度和方向估算
        n_events = len(events)
        restrict = sum(1 for e in events if e.get("direction") == "restrict")
        # 对美暴露度：事件越多/压制越强 → 暴露度越高（上限 8）
        exposure = min(8.0, 3.0 + n_events * 0.5 + restrict * 0.3)
        # 自主可控度：补贴/缓和事件 → 提高；压制高 → 倒逼自研（中性偏正）
        subsidy = sum(1 for e in events if e.get("direction") == "subsidy")
        controllability = min(8.0, 3.0 + subsidy * 0.8 + (1 if restrict >= 3 else 0))
        return {
            "us_exposure": round(exposure, 1),
            "self_controllability": round(controllability, 1),
            "event_count": n_events,
            "scale": "0-10, 越高越强",
            "basis": f"{n_events} 条事件, {restrict} 条压制, {subsidy} 条补贴",
        }

    def analyze(self, industry_hint: str = "") -> dict:
        """综合分析入口。"""
        return {
            "industry": industry_hint,
            "timeline": self.build_timeline(industry_hint),
            "scenarios": self.scenario_analysis(industry_hint),
            "substitution": self.substitution_mapping(industry_hint),
            "exposure": self.exposure_metrics(industry_hint),
            "event_count": len(self.filter_by_industry(industry_hint)),
        }

    def build_injection(self, result: dict) -> str:
        """生成 section_writer 注入块（geo_str）。"""
        if not result or result.get("event_count", 0) == 0:
            return ""
        lines = ["## 中美竞争与地缘政治分析（Geopolitical Engine）"]
        # 时间线
        tl = result.get("timeline", [])[:6]
        if tl:
            lines.append("### 政策时间线（近6条）")
            for ev in tl:
                lines.append(f"- {ev.get('date', '?')} | {ev.get('title', ev.get('event', ''))} | 影响: {ev.get('impact', ev.get('affected_segment', '行业'))}")
        # 双轨情景
        sc = result.get("scenarios", {})
        tracks = sc.get("tracks", [])
        if tracks:
            lines.append("### 双轨情景")
            for t in tracks:
                lines.append(f"- {t['name']}: 概率 {t['probability']:.0%}，影响 {t['impact']}（{t.get('note', '')}）")
        # 替代传导
        sub = result.get("substitution", [])
        if sub:
            lines.append("### 国产替代传导")
            for m in sub:
                lines.append(f"- {m['affected_segment']}: {m['substitution_direction']} → {m['beneficiary_note']}")
        # 量化指标
        exp = result.get("exposure", {})
        if exp:
            lines.append(f"### 量化指标: 对美暴露度 {exp.get('us_exposure', 'N/A')}/10，"
                         f"自主可控度 {exp.get('self_controllability', 'N/A')}/10（{exp.get('basis', '')}）")
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "半导体"
    eng = GeopoliticalEngine()
    r = eng.analyze(target)
    print(f"行业: {target}, 事件数: {r['event_count']}")
    print(eng.build_injection(r))
