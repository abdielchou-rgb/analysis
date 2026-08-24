"""V51 Edit History Connector — bridges EditCase DB to T2a generation.

共识二 (P0, 圆桌): 修改学习闭环打通。
  EditCase DB (SQLite) → EditHistory.get_injections() → T2a ArgumentEngine

Flow:
  1. T2a.design() 前调用 EditHistory.get_injections(brief, style)
  2. 返回分析师历史偏好注入（措辞调整、证据强项、常见修改类型）
  3. T2a 将注入内容应用到 ArgumentSection.thesis 和 style_rules
  4. 分析师每修改一次 → EditCase 写入 SQLite → 下次生成自动参考

Integration point: workflow.py V51Orchestrator.run()
    from core.edit_history import inject_preferences
    scaffold = inject_preferences(scaffold, brief)
"""

from __future__ import annotations

import logging
from typing import Optional

from core.models import (
    ArgumentScaffold, ArgumentSection, WritingBrief,
    EditingType,
)
from core.edit_learn import EditDatabase

logger = logging.getLogger("v51.edit_history")

# ── Intensity adjustment mapping (from actual edit patterns) ──

INTENSITY_MAP = {
    "必将": "有望",
    "无疑": "大概率",
    "毫无疑问": "有较强证据表明",
    "必然": "概率较大",
    "始终": "在多数情况下",
    "所有": "多数",
    "毫无": "有限",
    "彻底": "实质性",
    "全面": "较大范围",
    "根本": "重要",
    "确定": "有较高概率",
}

# ── Injector ─────────────────────────────────────────────────

def inject_preferences(scaffold: ArgumentScaffold,
                       brief: WritingBrief,
                       db: Optional[EditDatabase] = None) -> ArgumentScaffold:
    """Inject edit history preferences into scaffold design.

    1. Query DB for analyst's most common correction type
    2. Apply intensity adjustments from biased_judgment history
    3. Flag weak_evidence sections for extra data sourcing
    4. Inject style-specific preferences

    Returns the modified scaffold (in-place + return for chaining).
    """
    if db is None:
        db = EditDatabase()

    total = db.count_cases()
    if total < 5:
        return scaffold  # not enough data to learn from

    stats = db.get_stats_by_type()
    total_cases = sum(stats.values()) if stats else 0
    if total_cases == 0:
        return scaffold

    # Determine dominant correction type
    dominant_type = _get_dominant_type(stats, total_cases)

    # Apply per-section adjustments
    for section in scaffold.sections:
        _adjust_thesis(section, dominant_type, db, brief)

    # Add style_rules based on learned preferences
    suggested = db.suggest_adjustment(EditingType.BIASED_JUDGMENT, brief.style_profile)
    if suggested:
        scaffold.sections.append(
            ArgumentSection(
                section_id="_edit_history_note",
                title="修改学习提示",
                thesis=f"系统提示：基于历史修改记录，建议关注措辞强度调整（{suggested}）。",
                style_rules=["注意判断措辞强度，避免过度确定性的表述"],
                section_type=None,
            )
        )

    return scaffold


def _get_dominant_type(stats: dict, total: int) -> Optional[str]:
    """Find the most common correction type (if > 20% of total)."""
    for ctype, count in sorted(stats.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        if pct >= 20:
            return ctype
    return None


def _adjust_thesis(section: ArgumentSection,
                   dominant_type: Optional[str],
                   db: EditDatabase,
                   brief: WritingBrief):
    """Apply learned adjustments to a single section's thesis."""
    if not section.thesis:
        return

    # 1. Intensity adjustment (if biased_judgment is common)
    if dominant_type == "biased_judgment":
        adjusted = section.thesis
        for strong, mild in INTENSITY_MAP.items():
            adjusted = adjusted.replace(strong, mild)
        if adjusted != section.thesis:
            section.thesis = adjusted
            section.style_rules.append("措辞强度已根据历史修改自动调整")
            logger.debug(f"Adjusted thesis intensity in {section.section_id}")

    # 2. Evidence flag (if weak_evidence is common)
    if dominant_type == "weak_evidence":
        if len(section.evidence_ids) < section.required_citations:
            section.style_rules.append(
                f"基于历史修改记录：本节证据数({len(section.evidence_ids)})低于要求({section.required_citations})，建议补充"
            )

    # 3. Style-specific rules
    if brief.style_profile == "cicc":
        # CICC: 政策的敏感性，风险提示完整性
        if "风险" not in section.thesis and "政策" not in section.thesis:
            if section.section_id == "valuation_assessment":
                section.style_rules.append("中金风格：补充风险提示段落")


def summarize_learning(db: EditDatabase) -> dict:
    """Generate human-readable learning status."""
    total = db.count_cases()
    if total == 0:
        return {"total": 0, "status": "cold_start", "message": "尚无修改记录，系统处于冷启动阶段。"}

    stats = db.get_stats_by_type() or {}
    by_type = []
    total_cases = sum(stats.values()) or 1
    for ctype, count in sorted(stats.items(), key=lambda x: -x[1]):
        by_type.append({
            "type": ctype,
            "count": count,
            "pct": round(count / total_cases * 100, 1),
        })

    status = "learning" if total >= 10 else "initial"
    message = (
        f"已积累 {total} 条修改记录。系统在同类型报告生成时会自动参考历史偏好。"
        if total >= 10 else
        f"仅 {total} 条记录，继续积累至 10+ 条后生效。"
    )

    return {
        "total": total,
        "status": status,
        "by_type": by_type,
        "message": message,
    }
