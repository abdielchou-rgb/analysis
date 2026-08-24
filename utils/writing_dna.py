"""
V53 Writing DNA — Institutional writing style DNA profiles and executor.

Provides style profiles for different investment banks and consultancies.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("v53.writing_dna")


class WritingDNA:
    def __init__(
        self,
        institution_name: str = "",
        judgment_verbs: dict = None,
        paragraph_start: dict = None,
        uncertainty: dict = None,
        first_person: dict = None,
        p0_tolerance: float = 0.0,
        data_citation: dict = None,
    ):
        self.institution_name = institution_name
        self.judgment_verbs = judgment_verbs or {"primary": "我们认为", "secondary": "我们判断", "frequency": 0.7}
        self.paragraph_start = paragraph_start or {
            "preferred": ["我们认为", "从基本面看", "综合来看"],
            "avoid": ["值得注意的是", "综上所述"],
        }
        self.uncertainty = uncertainty or {"preferred": ["我们预计", "大概率"], "avoid": ["可能", "不排除"]}
        self.first_person = first_person or {"we_frequency": 0.8, "passive_allowed": False}
        self.p0_tolerance = p0_tolerance
        self.data_citation = data_citation or {"style": "inline", "template": "据{source}数据，{value}"}


INSTITUTION_DNA: dict[str, dict] = {
    "cicc": {
        "institution_name": "CICC",
        "judgment_verbs": {"primary": "我们认为", "secondary": "我们判断", "frequency": 0.75},
        "paragraph_start": {"preferred": ["我们认为", "从基本面看"], "avoid": ["值得注意的是", "综上所述", "不可否认"]},
        "uncertainty": {"preferred": ["我们预计", "大概率"], "avoid": ["可能", "不排除"]},
        "first_person": {"we_frequency": 0.85, "passive_allowed": False},
        "p0_tolerance": 0.0,
    },
    "goldman_sachs": {
        "institution_name": "Goldman Sachs",
        "judgment_verbs": {"primary": "我们认为", "secondary": "我们的判断是", "frequency": 0.8},
        "paragraph_start": {"preferred": ["我们的分析表明", "数据显示"], "avoid": ["值得注意的是", "综上所述"]},
        "uncertainty": {"preferred": ["我们预计", "我们的基准情景假设"], "avoid": ["可能"]},
        "first_person": {"we_frequency": 0.9, "passive_allowed": False},
        "p0_tolerance": 0.0,
    },
    "mckinsey": {
        "institution_name": "McKinsey",
        "judgment_verbs": {"primary": "我们的分析表明", "secondary": "数据证实", "frequency": 0.7},
        "paragraph_start": {"preferred": ["我们的分析表明", "数据证实"], "avoid": ["值得注意的是", "综上所述"]},
        "uncertainty": {"preferred": ["我们的基准情景假设", "预计"], "avoid": ["可能"]},
        "first_person": {"we_frequency": 0.9, "passive_allowed": False},
        "p0_tolerance": 0.0,
    },
    "standard": {
        "institution_name": "Standard",
        "judgment_verbs": {"primary": "我们认为", "secondary": "我们判断", "frequency": 0.7},
        "paragraph_start": {"preferred": ["我们认为", "从基本面看"], "avoid": ["值得注意的是", "综上所述"]},
        "uncertainty": {"preferred": ["我们预计"], "avoid": []},
        "first_person": {"we_frequency": 0.8, "passive_allowed": False},
        "p0_tolerance": 0.0,
    },
}


_STYLE_ALIASES = {
    # 管线 style id → INSTITUTION_DNA 键
    "gs": "goldman_sachs",
    "goldman": "goldman_sachs",
    "mck": "mckinsey",
    "bcg": "mckinsey",  # 咨询腔最近似
    "bain": "mckinsey",
    "jpm": "standard",
    "ms": "goldman_sachs",
}


def get_dna(style_id: str) -> WritingDNA:
    """Get institutional writing DNA profile."""
    sid = _STYLE_ALIASES.get(style_id, style_id)
    data = INSTITUTION_DNA.get(sid, INSTITUTION_DNA["standard"])
    return WritingDNA(**data)


def apply_dna(text: str, dna: WritingDNA) -> tuple[str, list[str]]:
    """Apply writing DNA rules to text."""
    applied_rules = []

    # Rule 1: Replace avoided paragraph starts
    for phrase in dna.paragraph_start["avoid"]:
        if phrase in text[:2000]:
            primary = dna.paragraph_start["preferred"][0]
            text = text.replace(phrase, primary, 1)
            applied_rules.append(f"replaced: {phrase} -> {primary}")

    # Rule 2: Replace avoided uncertainty phrases
    for phrase in dna.uncertainty["avoid"]:
        count = text.count(phrase)
        if count > 0:
            preferred = dna.uncertainty["preferred"][0] if dna.uncertainty["preferred"] else "预计"
            text = text.replace(phrase, preferred)
            applied_rules.append(f"replaced uncertainty: {phrase} -> {preferred}")

    return text, applied_rules
