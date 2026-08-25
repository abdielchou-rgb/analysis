"""V50+ Exporter Adapter — bridges V30 ReportExporter into V50+ T3_delivery.

Provides:
- to_docx: markdown → formatted Word document
- to_pdf: via LibreOffice or reportlab fallback
- export_all: md + docx + pdf in one call

All heavy lifting delegated to V30's proven ReportExporter (671 lines).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from core.models import Deliverable, KnowledgePackage

logger = logging.getLogger("v50.exporter")

_HAS_EXPORTER = False
try:
    from export.exporter import ReportExporter

    _HAS_EXPORTER = True
except ImportError as e:
    logger.warning("V30 exporter not available: %s", e)


class ExportAdapter:
    """Adapter wrapping V30 ReportExporter for V50+ Deliverable."""

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self, deliverable: Deliverable) -> dict[str, str]:
        """Export deliverable to all available formats.

        Returns dict mapping format → file path.
        """
        paths: dict[str, str] = {}

        # .md — always write
        md_path = self.output_dir / f"{deliverable.version.version_id}.md"
        md_path.write_text(deliverable.report_md, encoding="utf-8")
        paths["md"] = str(md_path)
        deliverable.export_paths["md"] = str(md_path)

        # .docx + others — via V30 exporter
        if _HAS_EXPORTER and deliverable.report_md:
            try:
                exporter = ReportExporter(company_name=deliverable.brief.asset if deliverable.brief else "")
                docx_path = str(self.output_dir / f"{deliverable.version.version_id}.docx")
                result = exporter.to_docx(
                    markdown_text=deliverable.report_md,
                    output_path=docx_path,
                )
                if result:
                    paths["docx"] = result
                    deliverable.export_paths["docx"] = result

                # pdf via docx
                pdf_path = str(self.output_dir / f"{deliverable.version.version_id}.pdf")
                pdf_result = exporter.to_pdf(
                    docx_path=docx_path,
                    output_path=pdf_path,
                )
                if pdf_result:
                    paths["pdf"] = pdf_result
                    deliverable.export_paths["pdf"] = pdf_result
            except Exception as e:
                logger.warning("DOCX/PDF export failed: %s", e)

        return paths


# Singleton
adapter = ExportAdapter()
