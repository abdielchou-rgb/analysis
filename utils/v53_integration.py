"""
V53 全面增强 - 集成入口

将 I1/I2/I3 所有模块集成到现有管线中。

用法:
    from utils.v53_integration import V53Pipeline
    pipeline = V53Pipeline()
    kp = pipeline.enhance_knowledge_package(kp)
    blocks = pipeline.build_prompt_extensions(kp)
    report = pipeline.post_process(report, kp)
"""

from __future__ import annotations

import logging

from core.chart_engine import ChartEngine
from core.models import KnowledgePackage, StyleProfile

logger = logging.getLogger("v53.integration")

# Apply professional chart patches on import
try:
    from utils.chart_patch import patch_all

    patch_all()
    logger.info("Chart patches applied (Chinese font + template colors)")
except Exception as e:
    logger.warning(f"Chart patch failed: {e}")

# V53 modules
try:
    from utils.chart_planner import ChartInventory, ChartPlanner  # noqa: F401  (availability probe)

    _HAS_PLANNER = True
except ImportError:
    _HAS_PLANNER = False

try:
    from utils.persuasion_architecture import build_persuasion_prompt

    _HAS_PERSUASION = True
except ImportError:
    _HAS_PERSUASION = False

try:
    from utils.writing_dna import WritingDNA, apply_dna, get_dna  # noqa: F401  (availability probe)

    _HAS_DNA = True
except ImportError:
    _HAS_DNA = False

try:
    from utils.appendix import build_appendix

    _HAS_APPENDIX = True
except ImportError:
    _HAS_APPENDIX = False

try:
    from utils.consensus_dialogue import (  # noqa: F401  (availability probe)
        CONSENSUS_DIALOGUE_PROMPT,
        build_consensus_dialogue,
    )

    _HAS_DIALOGUE = True
except ImportError:
    _HAS_DIALOGUE = False

try:
    from utils.executive_summary import (  # noqa: F401  (availability probe)
        EXECUTIVE_SUMMARY_TEMPLATE,
        format_executive_summary,
    )

    _HAS_EXEC = True
except ImportError:
    _HAS_EXEC = False


class V53Pipeline:
    """V53 enhanced pipeline."""

    def __init__(self, style_id: str = "cicc"):
        self.style_id = style_id
        self.chart_engine = ChartEngine(style_id=style_id)
        self.chart_planner = ChartPlanner(self.chart_engine, style_id) if _HAS_PLANNER else None

    def enhance_knowledge_package(self, kp: KnowledgePackage) -> KnowledgePackage:
        """Attach V53 enhanced data to KnowledgePackage."""
        if self.chart_planner:
            inventory = self.chart_planner.plan(kp)
            kp.chart_inventory = inventory
            logger.info(f"ChartPlanner: {inventory.total_count} charts ({len(inventory.mandatory)} mandatory)")
        if _HAS_DNA:
            kp.style = kp.style or StyleProfile(style_id=self.style_id)
        return kp

    def build_prompt_extensions(self, kp: KnowledgePackage) -> list[str]:
        """Generate all LLM prompt extension blocks."""
        blocks = []
        if hasattr(kp, "chart_inventory") and kp.chart_inventory:
            blocks.append(kp.chart_inventory.to_prompt_block())
        try:
            from utils.v53_models_additions import get_blueprint

            rt = kp.brief.report_type.value if kp.brief and kp.brief.report_type else "listed_company"
            bp = get_blueprint(rt)
            blocks.append(bp.to_prompt_block())
        except Exception:
            pass
        if _HAS_PERSUASION:
            blocks.append(build_persuasion_prompt(kp))
        if _HAS_DIALOGUE:
            blocks.append(build_consensus_dialogue(kp))
        if _HAS_EXEC:
            blocks.append(f"\n## Report Page 1 Format\n{EXECUTIVE_SUMMARY_TEMPLATE}")
        return blocks

    def post_process(self, report_text: str, kp: KnowledgePackage) -> str:
        """Post-process generated report."""
        if _HAS_DNA:
            dna = get_dna(self.style_id)
            report_text, _ = apply_dna(report_text, dna)
        if _HAS_APPENDIX and "## Appendix" not in report_text and "## 附录" not in report_text:
            appendix_data = build_appendix(kp)
            appendix_text = "\n\n## 附录\n"
            for key, content in appendix_data.items():
                if isinstance(content, str) and len(content.strip()) > 50:
                    appendix_text += content + "\n"
            report_text += appendix_text
        return report_text


def enhance_workflow(kp: KnowledgePackage, style_id: str = "cicc") -> KnowledgePackage:
    """Quick entry: enhance KnowledgePackage."""
    return V53Pipeline(style_id).enhance_knowledge_package(kp)
