"""
data_provenance.py V2 - Data lineage tracking system.
Every data point in a report is traceable back to its source.
"""
from __future__ import annotations
import json, logging, os, re, time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger("2hao.data_provenance")

_ROOT = Path(__file__).resolve().parent.parent

# Source hierarchy (matching industry standards)
SOURCE_LEVELS = {
    "L1_official": {"weight": 1.0, "label": "官方/一手", "examples": ["公司公告", "年报", "招股书", "官方数据"]},
    "L2_professional": {"weight": 0.9, "label": "专业数据", "examples": ["Wind", "Bloomberg", "Reuters", "公司官网"]},
    "L3_academic": {"weight": 0.8, "label": "学术/研究", "examples": ["学术论文", "行业白皮书"]},
    "L4_media": {"weight": 0.6, "label": "媒体报道", "examples": ["主流财经媒体", "行业媒体"]},
    "L5_inferred": {"weight": 0.3, "label": "推断/估算", "examples": ["基于多源推演", "行业专家推测"]},
    "L6_unknown": {"weight": 0.1, "label": "未知来源", "examples": ["无法追溯"]},
}


@dataclass
class DataSource:
    """Single data point source record"""
    metric: str                      # 指标名称: "2024年营收"
    value: str                       # 数值: "150亿元"
    source_level: str                # L1-L6
    source_name: str                 # 具体来源: "Wind/公司公告"
    source_url: str = ""             # URL (if available)
    fetch_time: str = ""             # 采集时间
    confidence: float = 0.0          # 0.0-1.0
    cross_validated: bool = False    # 是否交叉验证
    note: str = ""                   # 备注


class DataLineageTracker:
    """Track data lineage throughout the pipeline"""

    def __init__(self):
        self._sources: List[DataSource] = []
        self._start_time = datetime.now()

    def record(self, metric: str, value: str, source_name: str,
               source_level: str = "L4_media", source_url: str = "",
               confidence: Optional[float] = None, cross_validated: bool = False,
               note: str = "", is_inferred: bool = False) -> DataSource:
        """Record a data source (is_inferred=True marks LLM-inferred sources)."""
        if source_level not in SOURCE_LEVELS:
            source_level = "L4_media"
        if confidence is None:
            confidence = SOURCE_LEVELS[source_level]["weight"]
        if is_inferred:
            note = (note + " | [AI推测来源——非确凿来源，需人工核实]" if note
                    else "[AI推测来源——非确凿来源，需人工核实]")
        ds = DataSource(
            metric=metric, value=str(value),
            source_level=source_level,
            source_name=source_name, source_url=source_url,
            fetch_time=datetime.now().isoformat(),
            confidence=confidence,
            cross_validated=cross_validated,
            note=note,
        )
        self._sources.append(ds)
        return ds

    def get_all(self) -> List[DataSource]:
        return self._sources.copy()

    def get_by_metric(self, metric_keyword: str) -> List[DataSource]:
        return [s for s in self._sources if metric_keyword.lower() in s.metric.lower()]

    def summary(self) -> Dict:
        """Get summary statistics"""
        by_level = {}
        by_source = {}
        for s in self._sources:
            by_level[s.source_level] = by_level.get(s.source_level, 0) + 1
            by_source[s.source_name] = by_source.get(s.source_name, 0) + 1
        return {
            "total_points": len(self._sources),
            "by_level": by_level,
            "by_source": by_source,
            "pct_L1_L2": sum(v for k, v in by_level.items() if k in ("L1_official", "L2_professional")) / max(len(self._sources), 1) * 100,
            "cross_validated": sum(1 for s in self._sources if s.cross_validated),
            "avg_confidence": sum(s.confidence for s in self._sources) / max(len(self._sources), 1),
        }

    def render_report_section(self) -> str:
        """Render provenance section for inclusion in report"""
        if not self._sources:
            return ""
        lines = []
        lines.append("\n\n### 数据溯源与可信度")
        lines.append(f"> 共追踪 {len(self._sources)} 个数据点 | 采集时间: {self._start_time.strftime('%Y-%m-%d %H:%M')}\n")
        lines.append("| 指标 | 数值 | 来源等级 | 来源 | 置信度 | 交叉验证 |")
        lines.append("|------|------|---------|------|:------:|:--------:|")

        for s in self._sources:
            level_label = SOURCE_LEVELS.get(s.source_level, {}).get("label", s.source_level)
            cv = "是" if s.cross_validated else "否"
            inferred = "⚠ AI推测" if "AI推测来源" in (s.note or "") else ""
            lines.append(f"| {s.metric} | {s.value} | {level_label}{inferred} | {s.source_name} | {s.confidence:.0%} | {cv} |")

        summary = self.summary()
        lines.append(f"\n**来源质量**: L1-L2占比 {summary['pct_L1_L2']:.0f}% | "
                     f"平均置信度 {summary['avg_confidence']:.0%} | "
                     f"交叉验证 {summary['cross_validated']}处")
        return "\n".join(lines)


class DataProvenance:
    """V2: Full data provenance tracking with real collection"""

    def __init__(self):
        self.tracker = DataLineageTracker()

    def collect_from_tavily(self, asset: str) -> List[DataSource]:
        """Extract provenance from Tavily search results"""
        results = []
        try:
            from tavily import TavilyClient
            key = os.environ.get("TAVILY_API_KEY", "")
            if not key:
                logger.debug("Tavily key not available")
                return results
            client = TavilyClient(api_key=key)
            for query in [f"{asset} 2024 营收", f"{asset} 市场份额", f"{asset} 净利润"]:
                try:
                    r = client.search(query=query, search_depth="basic", max_results=3)
                    sources = r.get("results", [])
                    for s in sources[:2]:
                        title = s.get("title", "")
                        url = s.get("url", "")
                        results.append(DataSource(
                            metric=query, value=title[:80],
                            source_level="L4_media",
                            source_name=url[:60] if url else "Tavily",
                            source_url=url,
                            fetch_time=datetime.now().isoformat(),
                            confidence=0.6,
                        ))
                except Exception:
                    continue
        except Exception:
            pass
        return results

    def collect_from_deepseek(self, asset: str, context: str = "") -> List[DataSource]:
        """Ask DeepSeek to extract data sources from context"""
        results = []
        try:
            from core.deepseek_client import DeepSeekClient
            client = DeepSeekClient()
            prompt = f"""从以下文本中提取所有带数据的陈述，列出每个数据的来源。

文本: {context[:2000]}

输出格式（每行一个）:
指标名 | 数值 | 来源 | 来源可信度(L1-L6)

只输出有明确来源的数据，不要编造。"""
            response = client.chat(prompt, temperature=0.1)
            if response:
                for line in response.split("\n"):
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 3:
                            level = parts[3] if len(parts) >= 4 else "L4_media"
                            if level not in SOURCE_LEVELS:
                                level = "L4_media"
                            results.append(DataSource(
                                metric=parts[0][:60],
                                value=parts[1][:60],
                                source_level=level,
                                source_name=parts[2][:60],
                                fetch_time=datetime.now().isoformat(),
                                confidence=SOURCE_LEVELS[level]["weight"],
                                is_inferred=True,
                            ))
        except Exception as e:
            logger.debug("DeepSeek provenance extraction failed: %s", e)
        return results

    def collect(self, data_points: list = None, asset: str = "",
                report_sections: dict = None, context: str = "") -> dict:
        """Collect provenance data from multiple sources"""
        # Clear previous
        self.tracker = DataLineageTracker()

        # 1. From Tavily
        tavily_sources = self.collect_from_tavily(asset)
        for s in tavily_sources:
            self.tracker.record(s.metric, s.value, s.source_name,
                               source_level=s.source_level, source_url=s.source_url,
                               confidence=s.confidence)

        # 2. From context via DeepSeek
        if context:
            ds_sources = self.collect_from_deepseek(asset, context)
            for s in ds_sources:
                self.tracker.record(s.metric, s.value, s.source_name,
                                   source_level=s.source_level,
                                   confidence=s.confidence)

        # 3. From explicit data_points
        if data_points:
            for dp in data_points:
                if isinstance(dp, dict):
                    self.tracker.record(
                        dp.get("metric", "unknown"),
                        dp.get("value", ""),
                        dp.get("source", "unknown"),
                        source_level=dp.get("source_level", "L4_media"),
                        confidence=dp.get("confidence"),
                    )

        return self.tracker.summary()

    def render_report_section(self) -> str:
        return self.tracker.render_report_section()

    def inject_into_report(self, report_text: str, provenance: dict = None) -> str:
        """Inject provenance section into report"""
        section = self.render_report_section()
        if not section:
            return report_text
        if "数据溯源" in report_text:
            return report_text
        return report_text.rstrip() + "\n" + section


__all__ = ["DataProvenance", "DataLineageTracker", "DataSource", "ProvenanceEntry", "ProvenanceReport"]
