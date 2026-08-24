"""
audit_engine.py - Standardized audit engine
Unified detection rules so all auditors share the same standards.
"""

import json
import logging
import os
import re

logger = logging.getLogger("2hao.audit_engine")

# Unified audit checks - ALL auditors use the same rules
AUDIT_CHECKS = {
    "bare_except": {
        "pattern": re.compile(r"^\s*except\s*:"),
        "severity": "P0",
        "description": "Bare except silences all exceptions",
        "message": "Use except Exception: instead of bare except:",
    },
    "hardcoded_api_key": {
        "pattern": re.compile(r'"(sk-[a-zA-Z0-9]{20,}|tvly-[a-zA-Z0-9]{20,})"'),
        "severity": "P0",
        "description": "Hardcoded API key",
        "message": "API keys should be read from environment variables",
    },
    "hardcoded_path": {
        "pattern": re.compile(r'["\'][A-Z]:\\[a-zA-Z0-9]'),
        "severity": "P1",
        "description": "Hardcoded absolute path",
        "message": "Use Path(__file__).resolve().parent.parent instead",
    },
    "root_path_bug": {
        "pattern": re.compile(r'str\("_ROOT"\)|Path\(r?"str\(_ROOT\)"\)'),
        "severity": "P0",
        "description": "_ROOT path literal string bug",
        "message": "Use Path(__file__).resolve().parent.parent instead of str(_ROOT)",
    },
    "fake_data_fallback": {
        "pattern": re.compile(
            r"(np\.random|random\.uniform|\[10\]\*len|random\.randint|random\.sample|random\.random|numpy\.random|numpy\.random\.rand)"
        ),
        "severity": "P1",
        "description": "Fake/random data fallback pattern",
        "message": "Never use random data as real data - degrade gracefully",
    },
    "placeholder_chart": {
        "pattern": re.compile(r"(placeholder|figure_\d+|chart_\d+|dummy_chart)"),
        "severity": "P1",
        "description": "Placeholder chart/image",
        "message": "Never use placeholder charts - all charts must have real data",
    },
    "hardcoded_threshold": {
        "pattern": re.compile(r"change\s*[><]\s*0\.0[0-9]\s*#"),
        "severity": "P1",
        "description": "Hardcoded validation threshold (should use industry-calibrated threshold)",
        "message": "Use self._get_threshold() or parameterized threshold instead of hardcoded value",
    },
}


def scan_file(filepath: str) -> list[dict]:
    """Run all audit checks on a single file"""
    findings = []
    if not filepath.endswith(".py") or "__pycache__" in filepath:
        return findings
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        if stripped.startswith("//"):
            continue
        for check_name, check_def in AUDIT_CHECKS.items():
            if check_def["pattern"].search(stripped):
                findings.append(
                    {
                        "check": check_name,
                        "file": filepath,
                        "line": i,
                        "severity": check_def["severity"],
                        "description": check_def["description"],
                        "message": check_def["message"],
                        "code": stripped[:100],
                    }
                )
    return findings


def scan_project(project_root: str) -> dict:
    """Scan entire project and return audit report"""
    all_findings = []
    file_count = 0
    skip_dirs = {"__pycache__", ".git", "node_modules", ".venv"}
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if not f.endswith(".py"):
                continue
            filepath = os.path.join(root, f)
            file_count += 1
            all_findings.extend(scan_file(filepath))

    by_severity = {"P0": [], "P1": [], "P2": []}
    for f in all_findings:
        sev = f.get("severity", "P2")
        if sev in by_severity:
            by_severity[sev].append(f)

    return {
        "project_root": project_root,
        "files_scanned": file_count,
        "total_findings": len(all_findings),
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "findings": all_findings,
        "summary": {
            "P0_count": len(by_severity["P0"]),
            "P1_count": len(by_severity["P1"]),
            "P2_count": len(by_severity["P2"]),
        },
    }


def format_report(report: dict) -> str:
    """Format audit report as readable text"""
    lines = []
    lines.append("=" * 60)
    lines.append("Audit Engine Report")
    lines.append(f"Project: {report['project_root']}")
    lines.append(f"Files scanned: {report['files_scanned']}")
    lines.append(f"Total findings: {report['total_findings']}")
    lines.append(f"  P0: {report['summary']['P0_count']}")
    lines.append(f"  P1: {report['summary']['P1_count']}")
    lines.append(f"  P2: {report['summary']['P2_count']}")
    lines.append("=" * 60)

    for sev in ["P0", "P1", "P2"]:
        items = [f for f in report["findings"] if f["severity"] == sev]
        if not items:
            continue
        lines.append(f"\n[{sev}] {len(items)} issues:")
        for f in items:
            short_path = f["file"][len(report["project_root"]) :]
            lines.append(f"  {short_path}:{f['line']}")
            lines.append(f"    {f['description']}: {f['message']}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def run_audit_and_save(project_root: str, output_path: str | None = None) -> dict:
    """Run audit and optionally save results"""
    report = scan_project(project_root)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        text_path = output_path.replace(".json", ".txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(format_report(report))
    return report


if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else r"D:\2hao-analyst"
    report = run_audit_and_save(root, os.path.join(root, "output", "_audit_report.json"))
    print(format_report(report))
