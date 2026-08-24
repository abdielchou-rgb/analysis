"""V51 Evidence Chain — structured evidence visibility in reports.

共识一 (P0, 圆桌): 将 ArgumentScaffold 的结构化证据绑定暴露为报告可视化辅栏。
每个判断附带来源+置信度+缺口标注。

Design:
  - 从 ArgumentScaffold.evidence_ids + KnowledgePackage.data_points 直接生成
  - 全是结构化数据，不需要 NLP
  - 支持两种输出格式: MD appendix / DOCX sidebar callout
  - 证据等级用图标化标签：✅ 高置信度 | 📊 中等 | ⚠️ 待补充

Usage in workflow:
    from core.evidence_chain import build_evidence_appendix
    appendix = build_evidence_appendix(scaffold, kp)
    report_md += appendix
"""

from __future__ import annotations

import logging
from typing import Optional

from core.models import (
    ArgumentScaffold, ArgumentSection, KnowledgePackage,
    DataPoint, EvidenceLevel,
)

logger = logging.getLogger("v51.evidence_chain")

# ── Confidence mapping ───────────────────────────────────────

LEVEL_LABELS = {
    "L0_computed": ("✅", "确定性计算", "高"),
    "L1_filing": ("✅", "年报/公告", "高"),
    "L2_media": ("📊", "媒体报道", "中"),
    "L3_estimate": ("📊", "估算值", "中"),
    "L4_analyst": ("🔶", "分析师判断", "中低"),
    "L5_inference": ("🔶", "推理推断", "低"),
    "L9_pending": ("⚠️", "待补充", "—"),
}

DEFAULT_LABEL = ("📊", "数据源", "中")


def _get_level_info(source_level: str) -> tuple[str, str, str]:
    """Get (icon, source_type, confidence) for an evidence level."""
    return LEVEL_LABELS.get(source_level, DEFAULT_LABEL)


def _format_evidence_line(dp: DataPoint, source_level: str) -> str:
    """Format a single evidence item as structured text line."""
    icon, source_type, confidence = _get_level_info(source_level)
    value_str = f"{dp.value}{dp.unit}" if dp.value is not None else "（数据待补充）"
    source_str = f"（{dp.source}）" if dp.source else ""
    return f"  {icon} {dp.name}：{value_str} {source_str} — [{source_type}，置信度: {confidence}]"


# ── Build evidence chain appendix ─────────────────────────────

def build_evidence_appendix(scaffold: ArgumentScaffold,
                            kp: KnowledgePackage) -> str:
    """Generate a structured evidence chain appendix from scaffold + KP.

    Returns markdown string to append to report.

    Format per section:
    ```
    ▸ 核心判断（直销占比可突破50%）
      ├─ ✅ i茅台收入223.74亿元（2023年报）— [年报/公告，置信度: 高]
      ├─ ✅ 直销占比从10%→45.7%（公司年报）— [年报/公告，置信度: 高]
      └─ ⚠ 渠道库存精确数据 — [待补充]
    ```
    """
    if not scaffold or not scaffold.sections:
        return ""

    pool: dict[str, DataPoint] = {}
    if kp and kp.data_points:
        for dp in kp.data_points:
            if dp.name:
                pool[dp.name] = dp

    sections_text = []
    for sec in scaffold.sections:
        lines = []
        thesis = sec.thesis or ""
        # Extract a short thesis (first 40 chars)
        short_thesis = thesis[:60] + ("…" if len(thesis) > 60 else "")
        lines.append(f"▸ **{sec.title}**：{short_thesis}")

        # Evidence items
        for eid in sec.evidence_ids[:6]:
            dp = pool.get(eid)
            if dp:
                lines.append(_format_evidence_line(dp, dp.source_level or dp.confidence))
            else:
                lines.append(f"  📊 {eid}：（数据待补充）")

        # Counter evidence
        for cid in sec.counter_evidence_ids[:3]:
            dp = pool.get(cid)
            if dp:
                lines.append(f"  🔶 [反方] " + _format_evidence_line(dp, dp.source_level or dp.confidence).lstrip("  "))

        # Data gaps
        for gap in sec.data_gaps[:3]:
            lines.append(f"  ⚠️ {gap} — [待补充]")

        if not sec.evidence_ids and not sec.data_gaps:
            lines.append("  （暂无可用数据）")

        sections_text.append("\n".join(lines))

    if not sections_text:
        return ""

    appendix = "\n\n---\n\n### 📋 证据链\n\n" + "\n\n".join(sections_text)
    appendix += "\n\n*证据等级说明：✅ 高置信度（年报/公告/计算）| 📊 中等（媒体/估算）| 🔶 低置信度（推理）| ⚠️ 待补充*"
    return appendix


def build_evidence_table(scaffold: ArgumentScaffold,
                         kp: KnowledgePackage) -> list[dict]:
    """Build structured evidence data for DOCX/HTML export.

    Returns list of dicts per section:
    {
      "section_title": "...",
      "thesis": "...",
      "evidence": [{"name": "...", "value": ..., "unit": "...",
                    "source": "...", "confidence": "high"}],
      "gaps": ["..."],
    }
    """
    pool: dict[str, DataPoint] = {}
    if kp and kp.data_points:
        for dp in kp.data_points:
            if dp.name:
                pool[dp.name] = dp

    table = []
    for sec in scaffold.sections:
        evidence_list = []
        for eid in sec.evidence_ids[:8]:
            dp = pool.get(eid)
            if dp:
                _, source_type, confidence = _get_level_info(dp.source_level or dp.confidence)
                evidence_list.append({
                    "name": dp.name,
                    "value": dp.value,
                    "unit": dp.unit,
                    "source": dp.source or "",
                    "source_type": source_type,
                    "confidence": confidence,
                })
        table.append({
            "section_title": sec.title,
            "thesis": sec.thesis or "",
            "evidence": evidence_list,
            "gaps": sec.data_gaps[:5],
            "counter_evidence_ids": sec.counter_evidence_ids[:3],
        })
    return table


# ── Summary statistics ────────────────────────────────────────

def evidence_stats(scaffold: ArgumentScaffold,
                   kp: KnowledgePackage) -> dict:
    """Compute aggregate evidence statistics for observability."""
    total_evidence = sum(len(s.evidence_ids) for s in scaffold.sections)
    total_gaps = sum(len(s.data_gaps) for s in scaffold.sections)
    high_conf = 0
    med_conf = 0
    low_conf = 0
    pool = {dp.name: dp for dp in (kp.data_points or [])}
    for sec in scaffold.sections:
        for eid in sec.evidence_ids:
            dp = pool.get(eid)
            if dp:
                _, _, conf = _get_level_info(dp.source_level or dp.confidence)
                if conf == "高":
                    high_conf += 1
                elif conf == "中" or conf == "中低":
                    med_conf += 1
                else:
                    low_conf += 1
    return {
        "total_sections": len(scaffold.sections),
        "total_evidence": total_evidence,
        "total_gaps": total_gaps,
        "high_confidence": high_conf,
        "medium_confidence": med_conf,
        "low_confidence": low_conf,
        "coverage_pct": round(
            (total_evidence / (total_evidence + total_gaps)) * 100, 1
        ) if (total_evidence + total_gaps) > 0 else 0,
    }
