"""2号分析师 Report Writer"""

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from core.sacs import SACLoader
from pipeline.compute_injector import ComputeInjector
from pipeline.format_sheriff import FormatSheriff
from pipeline.template_enforcer import TemplateEnforcer


class ReportWriter:
    def __init__(self, report_type="industry_deep", style="cicc"):
        self.report_type = report_type
        self.style = style
        self.asset = ""
        self.sac = SACLoader(report_type)

    def prepare_charts(self, data=None):
        from pipeline.chart_planner import ChartPlanner

        planner = ChartPlanner(self.report_type, self.style, "output/charts")
        paths = planner.generate_all(data or {})
        n = len([k for k in paths if not k.startswith("error")])
        print(f"[ChartPlanner] Generated {n} charts")
        return paths

    def export(self, report_text, output_path="output/report", chart_paths=None, data=None, compute_results=None):
        output_base = Path(output_path)
        output_base.parent.mkdir(parents=True, exist_ok=True)

        # ---- Layer 3: FormatSheriff (format enforcement) ----
        try:
            sheriff = FormatSheriff()
            report_text = sheriff.patrol(report_text, self.report_type)
        except Exception as e:
            print(f"FormatSheriff: {e}")

        # ---- ChartAssembler (chart insertion) ----
        if chart_paths:
            try:
                from pipeline.chart_assembler import assemble_report

                report_text = assemble_report(
                    report_text, chart_paths, sac_loader=self.sac, report_type=self.report_type
                )
            except Exception as e:
                print(f"[ChartAssembler] Failed: {e}")

        # ---- Layer 2: ComputeInjector (valuation params injection) ----
        try:
            injector = ComputeInjector(compute_results=compute_results, data=data)
            report_text = injector.inject(report_text)
        except Exception as e:
            print(f"[ComputeInjector] Failed: {e}")

        # ---- Layer 1: TemplateEnforcer (hard constraints) ----
        try:
            enforcer = TemplateEnforcer(sac_loader=self.sac)
            enforce_result = enforcer.enforce(report_text, self.report_type, data=data)
            report_text = enforce_result["report_text"]
            if enforce_result["violations"]:
                print(f"[TemplateEnforcer] {len(enforce_result['violations'])} violations:")
                for v in enforce_result["violations"]:
                    print(f"  {v}")
                if not enforce_result["pass"]:
                    print("[TemplateEnforcer] BLOCKED: cannot export")
                    return {"error": "TemplateEnforcer blocked", "violations": enforce_result["violations"]}
            if enforce_result["fixes"]:
                print(f"[TemplateEnforcer] {len(enforce_result['fixes'])} auto-fixes applied")
        except Exception as e:
            print(f"[TemplateEnforcer] Failed: {e}")

        # ---- Export ----
        md_path = output_base.with_suffix(".md")
        md_path.write_text(report_text, encoding="utf-8")
        print(f"MD: {md_path}")

        docx_path = output_base.with_suffix(".docx")
        try:
            from export.report_gate import GateBlockedError, export_report

            title_m = re.search(r"^#\s+([^\n]+)", report_text)
            title = title_m.group(1).strip() if title_m else "Report"
            export_report(
                report_text,
                str(docx_path),
                report_type=self.report_type,
                style=self.style,
                company_name=self.asset,
                title=title,
            )
            print(f"DOCX: {docx_path} (gates passed)")
        except GateBlockedError as e:
            print(f"GATE BLOCKED: {e}")
            import traceback

            traceback.print_exc()
        except Exception as e:
            print(f"DOCX failed: {e}")
            import traceback

            traceback.print_exc()

        return {"md": str(md_path), "docx": str(docx_path)}


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--output", "-o", default="output/report")
    args = p.parse_args()
    print(ReportWriter().export("", args.output))
