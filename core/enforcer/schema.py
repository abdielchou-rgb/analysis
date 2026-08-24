"""Enforced report schema — structured output constraints."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EnforcedSection:
    section_id: str = ""
    headline_judgment: str = ""  # Required: first sentence must be a judgment
    body: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    has_counter_case: bool = False
    so_what: str | None = None
    data_gaps: list[str] = field(default_factory=list)


@dataclass
class EnforcedReport:
    title: str = ""
    core_disagreement: str = ""  # Required: explicit disagreement statement
    sections: list[EnforcedSection] = field(default_factory=list)
    required_artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "core_disagreement": self.core_disagreement,
            "sections": [s.__dict__ for s in self.sections],
            "required_artifacts": self.required_artifacts,
        }


@dataclass
class EnforcementResult:
    passed: bool = False
    schema_passed: bool = True
    schema_issues: list[str] = field(default_factory=list)
    section_count: int = 0
    checklist_passed: bool = True
    checklist_items: list[dict] = field(default_factory=list)


class EnforcementError(Exception):
    """Raised when Enforcer blocks output in block mode."""

    def __init__(self, message: str, result=None):
        self.result = result
        super().__init__(message)
