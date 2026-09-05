#!/usr/bin/env python
"""
Integration patches for 2hao-analyst pipeline.

Patches:
1. section_writer.py: Exemplar injection into _build_prompt_v4
2. iron_gate.py: IronGate V2 5-layer verification
3. data_collector.py: Context enrichment in collect()
"""

import re
from pathlib import Path

ROOT = Path(r"D:\Claude\projects\2hao-analyst")


# ── Patch 1: Exemplar Injection ───────────────────────────────


def patch_section_writer():
    """Add exemplar injection to section_writer.py."""
    filepath = ROOT / "pipeline" / "section_writer.py"
    content = filepath.read_text(encoding="utf-8")

    # Check if already patched
    if "EXEMPLAR_INJECTION_START" in content:
        print("  section_writer.py already patched")
        return

    # Find the insertion point: after dim_defs, before "## 可用数据"
    old_marker = """            "## 可用数据",
            data_str[:4000],"""

    new_code = """            # EXEMPLAR_INJECTION_START: Diversity-aware exemplar injection
            self._build_exemplar_injection(parts, seg, asset),
            # EXEMPLAR_INJECTION_END

            "## 可用数据",
            data_str[:4000],"""

    if old_marker in content:
        content = content.replace(old_marker, new_code)
        filepath.write_text(content, encoding="utf-8")
        print("  section_writer.py patched: exemplar injection added")
    else:
        print("  section_writer.py: insertion point not found, manual patch needed")

    # Add the _build_exemplar_injection method
    method_code = '''
    def _build_exemplar_injection(self, parts, seg, asset):
        """Inject diversity-aware exemplars from FinRpt bank."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            from exemplar_injector import ExemplarInjector

            injector = ExemplarInjector()

            # Map segment to section names
            section_map = {
                0: "利润表分析",  # Strategy Layer
                1: "竞争格局分析",  # Competition Layer
                2: "趋势分析",  # Forward-Looking Layer
            }
            section = section_map.get(seg.get("idx", 0), "财务综述")

            # Get dimension IDs for this segment
            dim_ids = seg.get("dimension_ids", [])

            # Build exemplar prompt
            exemplar_text = injector._format_exemplars(
                injector.retriever.retrieve(
                    section=section,
                    n=3,
                    exclude_stocks={self._asset_code} if self._asset_code else None,
                )
            )

            if exemplar_text:
                parts.append("## 资深分析师参考示例（风格参考，禁止照搬）")
                parts.append(exemplar_text[:2000])  # Cap at 2000 chars
                parts.append("")

        except ImportError as e:
            import logging
            logging.warning("[EXEMPLAR] Exemplar injection unavailable: %s", e)
            logging.warning("[EXEMPLAR] Running in DEGRADED mode - no exemplars injected")
        except Exception as e:
            import logging
            logging.error("[EXEMPLAR] Exemplar injection failed: %s", e)
'''

    # Insert the method after _build_prompt_v4
    # Find the end of _build_prompt_v4 method
    method_pattern = r"(    def _build_prompt_v4\([^)]+\):.*?)(    def [a-z_]+\(self)"
    match = re.search(method_pattern, content, re.DOTALL)
    if match:
        insert_pos = match.end(2)
        content = content[:insert_pos] + method_code + "\n" + content[insert_pos:]
        filepath.write_text(content, encoding="utf-8")
        print("  section_writer.py: _build_exemplar_injection method added")
    else:
        print("  section_writer.py: could not find _build_prompt_v4 end, manual patch needed")


# ── Patch 2: IronGate V2 Integration ─────────────────────────


def patch_iron_gate():
    """Add IronGate V2 5-layer verification to iron_gate.py."""
    filepath = ROOT / "pipeline" / "iron_gate.py"
    content = filepath.read_text(encoding="utf-8")

    # Check if already patched
    if "IRONGATE_V2_START" in content:
        print("  iron_gate.py already patched")
        return

    # Find the run_all method and add V2 checks after existing checks
    old_marker = """        # ── LLM checks (parallel) ──"""

    new_code = """        # IRONGATE_V2_START: 5-layer verification
        self._run_irongate_v2_checks(report_text, context)
        # IRONGATE_V2_END

        # ── LLM checks (parallel) ──"""

    if old_marker in content:
        content = content.replace(old_marker, new_code)
        filepath.write_text(content, encoding="utf-8")
        print("  iron_gate.py patched: V2 checks added")
    else:
        print("  iron_gate.py: insertion point not found")

    # Add the V2 check method
    v2_method = '''
    def _run_irongate_v2_checks(self, report_text: str, context: dict = None):
        """Run IronGate V2 5-layer verification."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            from irongate_v2 import IronGateV2

            gate_v2 = IronGateV2()
            result = gate_v2.verify(report_text, context, threshold=0.55)

            # Add V2 results as checks
            for layer_result in result.layers:
                self.checks.append(GateCheckResult(
                    name=f"v2_{layer_result.layer}",
                    passed=layer_result.passed,
                    score=layer_result.score,
                    details="; ".join(layer_result.issues[:3]),
                    severity="error" if layer_result.score < 0.5 else "warning",
                ))

        except ImportError as e:
            import logging
            logging.error("[IRON_GATE_V2] V2 verification unavailable: %s", e)
            logging.error("[IRON_GATE_V2] Running in DEGRADED mode - V2 checks skipped")
            self.checks.append(GateCheckResult(
                name="v2_unavailable",
                passed=False,
                score=0.0,
                details=f"V2 import failed: {e}",
                severity="error",
            ))
        except Exception as e:
            import logging
            logging.error("[IRON_GATE_V2] V2 verification failed: %s", e)
            self.checks.append(GateCheckResult(
                name="v2_error",
                passed=False,
                score=0.0,
                details=f"V2 execution failed: {e}",
                severity="error",
            ))
'''

    # Insert before run_all method end
    insert_marker = "    def check_only("
    if insert_marker in content:
        content = content.replace(insert_marker, v2_method + "\n" + insert_marker)
        filepath.write_text(content, encoding="utf-8")
        print("  iron_gate.py: _run_irongate_v2_checks method added")
    else:
        print("  iron_gate.py: could not find check_only, manual patch needed")


# ── Patch 3: Context Enrichment ────────────────────────────────


def patch_data_collector():
    """Add context enrichment to data_collector.py."""
    filepath = ROOT / "pipeline" / "data_collector.py"
    content = filepath.read_text(encoding="utf-8")

    # Check if already patched
    if "CONTEXT_ENRICHMENT_START" in content:
        print("  data_collector.py already patched")
        return

    # Find the collect method and add enrichment after data collection
    old_marker = """        return collected"""

    new_code = """        # CONTEXT_ENRICHMENT_START: Enrich with historical context
        collected = self._enrich_with_context(collected, stock_code)
        # CONTEXT_ENRICHMENT_END

        return collected"""

    if old_marker in content:
        content = content.replace(old_marker, new_code, 1)  # Only first occurrence
        filepath.write_text(content, encoding="utf-8")
        print("  data_collector.py patched: context enrichment added")
    else:
        print("  data_collector.py: insertion point not found")

    # Add the enrichment method
    enrich_method = '''
    def _enrich_with_context(self, collected: dict, stock_code: str) -> dict:
        """Enrich collected data with historical context from exemplar bank."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            from context_enrichment import ContextEnricher

            enricher = ContextEnricher()
            context = enricher.enrich(
                stock_code=stock_code,
                section="财务综述",
                raw_data=collected,
            )

            # Add context to collected data
            collected["_enrichment_context"] = {
                "historical_reports": len(context.get("historical_reports", [])),
                "related_research": len(context.get("related_research", [])),
                "related_news": len(context.get("related_news", [])),
                "formatted_context": enricher.format_context_for_prompt(context)[:3000],
            }

        except ImportError as e:
            import logging
            logging.error("[CONTEXT_ENRICHMENT] Enrichment unavailable: %s", e)
            logging.error("[CONTEXT_ENRICHMENT] Running in DEGRADED mode - no context enrichment")
            collected["_enrichment_context"] = {
                "status": "degraded",
                "error": str(e),
            }
        except Exception as e:
            import logging
            logging.error("[CONTEXT_ENRICHMENT] Enrichment failed: %s", e)
            collected["_enrichment_context"] = {
                "status": "error",
                "error": str(e),
            }

        return collected
'''

    # Insert before the last method or at end of class
    insert_marker = "    def _network_phase("
    if insert_marker in content:
        content = content.replace(insert_marker, enrich_method + "\n" + insert_marker)
        filepath.write_text(content, encoding="utf-8")
        print("  data_collector.py: _enrich_with_context method added")
    else:
        print("  data_collector.py: could not find _network_phase, manual patch needed")


# ── Main ──────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("Integrating new components into pipeline")
    print("=" * 60)

    print("\n1. Patching section_writer.py (exemplar injection)...")
    patch_section_writer()

    print("\n2. Patching iron_gate.py (V2 verification)...")
    patch_iron_gate()

    print("\n3. Patching data_collector.py (context enrichment)...")
    patch_data_collector()

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
