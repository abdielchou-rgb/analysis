"""V52 Constraint Enforcement Layer.

Three-tier approach:
  1. Schema enforcement (structured output via dataclass validation)
  2. Post-processing checklist (10-item compliance gate)
  3. Section gate (optional: verify per-section before allowing next)

Design principle: "宁可拒真，不可放伪"
"""

from __future__ import annotations

from core.enforcer.schema import EnforcedReport, EnforcedSection, EnforcementResult, EnforcementError
from core.enforcer.checklist import ComplianceChecklist, ComplianceChecklistItem
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EnforcerConfig:
    require_schema: bool = True
    run_checklist: bool = True
    require_all_dimensions: bool = True
    fail_on_first: bool = False  # stop at first failure
    mode: str = "warn"  # "warn" | "block" — block raises EnforcementError


class Enforcer:
    """Main entry point for constraint enforcement."""

    def __init__(self, config: Optional[EnforcerConfig] = None):
        self.config = config or EnforcerConfig()
        self.checklist = ComplianceChecklist()

    def enforce(self, text: str, sac_id: str = "", required_dims: list[str] = None,
                context: dict = None) -> EnforcementResult:
        """Run all enforcement checks and return results."""
        context = context or {}
        result = EnforcementResult()

        # 1. Schema check
        if self.config.require_schema:
            schema_result = self._check_schema(text, required_dims or [])
            result.schema_passed = schema_result["passed"]
            result.schema_issues = schema_result["issues"]
            result.section_count = schema_result.get("section_count", 0)

        # 2. Compliance checklist
        if self.config.run_checklist:
            check_result = self.checklist.run(text, sac_id=sac_id,
                                              required_dims=required_dims)
            result.checklist_passed = check_result["passed"]
            result.checklist_items = check_result["items"]

        result.passed = result.schema_passed and result.checklist_passed
        # Block mode: raise if not passed
        if self.config.mode == "block" and not result.passed:
            from core.enforcer.schema import EnforcementError
            raise EnforcementError(
                f"Enforcer blocked: schema={result.schema_passed}, checklist={result.checklist_passed}",
                result=result,
            )
        return result

    def _check_schema(self, text: str, required_dims: list[str]) -> dict:
        """Verify report structure against EnforcedReport schema."""
        issues = []
        sections = [s for s in text.split('\n## ') if s.strip()]

        if len(sections) < 2:
            return {"passed": False, "issues": ["No ## sections found"], "section_count": 0}

        # Check core disagreement (page 2)
        if len(sections) >= 2:
            sec2 = sections[1][:300]
            has_disagreement = any(m in sec2 for m in ["分歧", "共识", "不同于", "市场认为"])
            if not has_disagreement:
                issues.append(f"第2页(核心分歧): 未检测到争议定位")

        # Check required dimensions are present as ## sections
        if required_dims:
            section_titles = [s.split('\n')[0].strip().lower() for s in sections[1:]]
            for dim in required_dims:
                dim_lower = dim.lower()
                # Fuzzy match: dim keyword appears in any section title
                found = any(dim_lower in t or t in dim_lower for t in section_titles)
                if not found:
                    issues.append(f"缺少 required_dimension: {dim}")

        # Check forbidden patterns
        forbidden = ["AIGC:", "AIGC：", "contentproducer:", "reservedcode"]
        for fp in forbidden:
            if fp.lower() in text.lower():
                # Only flag if in header area (first 500 chars)
                if fp.lower() in text[:500].lower():
                    issues.append(f"AIGC 元数据残留: {fp}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "section_count": len(sections),
        }

    def enforce_section(self, section_text: str, section_id: str,
                        requirements: dict = None) -> dict:
        """Enforce a single section (for section-gating mode)."""
        issues = []
        lines = [l for l in section_text.strip().split('\n') if l.strip()]
        if not lines:
            return {"passed": False, "issues": ["Empty section"]}

        first_line = lines[0]
        has_judgment = any(j in first_line for j in
                           ["我们认为", "预计", "核心", "关键", "估值", "风险"])
        if not has_judgment:
            issues.append("首句不是判断句")

        if requirements:
            evidence_min = requirements.get("evidence_min", 0)
            if evidence_min > 0:
                ev_count = section_text.count("来源") + section_text.count("数据")
                if ev_count < evidence_min:
                    issues.append(f"证据不足: 需要 {evidence_min} 处, 实际 {ev_count} 处")

        return {"passed": len(issues) == 0, "issues": issues}
