"""
V53 Models Additions
====================
Additional dataclasses needed by V53 integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChartSpec:
    """Specification for a single chart in a report."""

    chart_id: str = ""
    chart_type: str = "bar"
    title: str = ""
    data_sources: list[str] = field(default_factory=list)
    file_name: str = ""
    section_hint: str = ""
    priority: int = 1


@dataclass
class WritingDNA:
    """Institutional writing style DNA."""

    institution_name: str = ""
    judgment_verbs: dict = field(
        default_factory=lambda: {"primary": "我们认为", "secondary": "我们判断", "frequency": 0.7}
    )
    paragraph_start: dict = field(
        default_factory=lambda: {"preferred": ["我们认为", "从基本面看"], "avoid": ["值得注意的是", "综上所"]}
    )
    uncertainty: dict = field(default_factory=lambda: {"preferred": ["我们预计"], "avoid": ["可能"]})
    first_person: dict = field(default_factory=lambda: {"we_frequency": 0.8, "passive_allowed": False})
    p0_tolerance: float = 0.0
    data_citation: dict = field(default_factory=lambda: {"style": "inline", "template": "据{source}数据：{value}"})


@dataclass
class ProvenanceRecord:
    """Record of data provenance for traceability."""

    source: str = ""
    field: str = ""
    value: str = ""
    confidence: float = 1.0


@dataclass
class ReportBlueprint:
    """Blueprint for a report structure."""

    report_type: str = "listed_company"
    sections: list[str] = field(
        default_factory=lambda: [
            "Executive Summary",
            "Industry Overview",
            "Company Analysis",
            "Financial Analysis",
            "Forecast & Valuation",
            "Risk Factors",
            "Appendix",
        ]
    )
    mandatory_sections: list[str] = field(
        default_factory=lambda: ["Executive Summary", "Financial Analysis", "Forecast & Valuation"]
    )
    style_id: str = "cicc"
    language: str = "zh-CN"

    def to_prompt_block(self) -> str:
        lines = ["\n## Report Blueprint"]
        lines.append(f"Type: {self.report_type}")
        lines.append("Required sections (in order):")
        for s in self.mandatory_sections:
            lines.append(f"- **{s}** (mandatory)")
        for s in self.sections:
            if s not in self.mandatory_sections:
                lines.append(f"- {s} (optional)")
        return "\n".join(lines)


def get_blueprint(report_type: str = "listed_company") -> ReportBlueprint:
    """Get report blueprint for a given report type."""
    blueprints = {
        "listed_company": ReportBlueprint(
            report_type="listed_company",
            sections=[
                "Executive Summary",
                "Industry Overview",
                "Company Analysis",
                "Financial Analysis",
                "Forecast & Valuation",
                "Risk Factors",
                "Appendix",
            ],
            mandatory_sections=["Executive Summary", "Financial Analysis", "Forecast & Valuation"],
        ),
        "industry": ReportBlueprint(
            report_type="industry",
            sections=[
                "Executive Summary",
                "Industry Overview",
                "Industry Chain Analysis",
                "Competitive Landscape",
                "Trends & Outlook",
                "Appendix",
            ],
            mandatory_sections=["Executive Summary", "Industry Overview", "Competitive Landscape"],
        ),
        "macro": ReportBlueprint(
            report_type="macro",
            sections=[
                "Executive Summary",
                "Global Outlook",
                "Policy Analysis",
                "Risk Assessment",
                "Investment Implications",
                "Appendix",
            ],
            mandatory_sections=["Executive Summary", "Global Outlook", "Risk Assessment"],
        ),
    }
    return blueprints.get(report_type, blueprints["listed_company"])
