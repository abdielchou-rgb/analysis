#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-fix script for Silent Business Defaults

This script scans the codebase for silent business defaults and provides
guided fixes. It does NOT auto-modify files - instead it generates a
detailed report with suggested fixes that can be reviewed and applied.
"""

from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
import json


class SilentDefaultScanner:
    """Scans codebase for silent business defaults"""
    
    # Patterns that indicate silent business defaults (CRITICAL)
    CRITICAL_PATTERNS = [
        (r'\.get\(["\']capacity[^"\']*["\']\s*,\s*\d+', 'capacity business default'),
        (r'\.get\(["\']unit_price["\']\s*,\s*\d+', 'unit_price business default'),
        (r'\.get\(["\']unit_price["\']\s*,\s*\d+\.?\d*', 'unit_price business default'),
        (r'\.get\(["\']variable_cost["\']\s*,\s*\d+', 'variable_cost business default'),
        (r'\.get\(["\']fixed_capex["\']\s*,\s*\d+', 'fixed_capex business default'),
        (r'\.get\(["\']fixed_opex["\']\s*,\s*\d+', 'fixed_opex business default'),
        (r'\.get\(["\']revenue["\']\s*,\s*\d+', 'revenue business default'),
        (r'\.get\(["\']gross_margin["\']\s*,\s*[\d.]+', 'gross_margin business default'),
        (r'\.get\(["\']net_profit["\']\s*,\s*\d+', 'net_profit business default'),
        (r'\.get\(["\']price["\']\s*,\s*\d+', 'price business default'),
        (r'\.get\(["\']market_cap["\']\s*,\s*\d+', 'market_cap business default'),
        (r'\.get\(["\']shares["\']\s*,\s*\d+', 'shares business default'),
        (r'\.get\(["\']net_debt["\']\s*,\s*\d+', 'net_debt business default'),
        (r'\.get\(["\']free_cash_flow["\']\s*,\s*\d+', 'fcf business default'),
        (r'\.get\(["\']eps["\']\s*,\s*\d+', 'eps business default'),
        (r'\.get\(["\']bvps["\']\s*,\s*\d+', 'bvps business default'),
        (r'\.get\(["\']roe["\']\s*,\s*[\d.]+', 'roe business default'),
        (r'\.get\(["\']gross_margin["\']\s*,\s*[\d.]+', 'gross_margin business default'),
        (r'\.get\(["\']pe["\']\s*,\s*\d+', 'pe business default'),
        (r'\.get\(["\']ps["\']\s*,\s*\d+', 'ps business default'),
        (r'\.get\(["\']pb["\']\s*,\s*\d+', 'pb business default'),
    ]
    
    # Patterns that are likely configuration (LOW priority - review only)
    CONFIG_PATTERNS = [
        'timeout', 'max_tokens', 'limit', 'retry', 'cache', 'batch_size', 
        'port', 'pool', 'worker', 'thread', 'version', 'version_info',
        'min_charts', 'min_tables', 'min_sources', 'threshold', 'ratio',
        'pct', 'percent', 'rate', 'rate_', 'default', 'default_', 
        'fallback', 'fallback_'
    ]
    
    def __init__(self):
        self.findings: List[Dict] = []
    
    def scan_file(self, file_path: Path) -> List[Dict]:
        """Scan a single file for silent business defaults"""
        findings = []
        
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()
                
                # Skip comments, strings, and obvious config
                if line_stripped.startswith('#'):
                    continue
                if 'test' in str(file_path).lower() and 'test' in file_path.name:
                    continue
                    
                # Check for .get() with numeric default using regex with capture groups
                # Pattern: .get("key", 123) or .get('key', 123) or .get("key", 123.45)
                get_matches = re.finditer(r'\.get\((["\'])([^"\']+)\1\s*,\s*(\d+(?:\.\d+)?)', line)
                for match in get_matches:
                    key = match.group(2).strip()
                    default_val = match.group(3)
                    
                    # Check if this is a business default vs config
                    is_critical = False
                    match_type = "LOW"
                    
                    # Check critical patterns
                    for pattern, desc in self.CRITICAL_PATTERNS:
                        if re.search(pattern, line):
                            is_critical = True
                            match_type = "CRITICAL"
                            break
                    
                    if not is_critical:
                        # Check if it's a config pattern
                        for config_kw in self.CONFIG_PATTERNS:
                            if config_kw in line.lower():
                                match_type = "LOW"
                                break
                        else:
                            match_type = "MEDIUM"
                    
                    if match_type != "LOW":
                        self.findings.append({
                            'file': str(file_path.relative_to(Path.cwd())),
                            'line_num': i,
                            'line': line.strip(),
                            'key': key,
                            'default': default_val,
                            'type': match_type,
                            'suggested_fix': self._generate_fix(key, default_val, match_type)
                        })
        
        except Exception as e:
            print(f"Error scanning {file_path}: {e}")
        
        return findings
    
    def _generate_fix(self, key: str, default: str, severity: str) -> str:
        """Generate suggested fix code"""
        if severity == "CRITICAL":
            return f"# REPLACE: .get('{key}', {default}) -> accessor.require('{key}') or accessor.assume('{key}', default={default}, source='manual_estimate')"
        elif severity == "HIGH":
            return f"# REVIEW: .get('{key}', {default}) -> consider accessor.assume('{key}', {default}, source='estimate')"
        else:
            return f"# REVIEW: .get('{key}', {default}) -> verify if config or business default"
    
    def scan(self, root: str, exclude_dirs: List[str] = None) -> List[Dict]:
        """Scan entire project for silent business defaults"""
        exclude_dirs = exclude_dirs or ['.venv', '__pycache__', '.git', '.venv', 'site-packages', '.git', 'node_modules', '.pytest_cache', '.mypy_cache', 'dist', 'build', 'dist', '*.egg-info']
        
        root_path = Path(root)
        all_findings = []
        
        for py_file in root_path.rglob('*.py'):
            # Skip excluded directories
            if any(excl in str(py_file) for excl in ['.venv', '__pycache__', '.git', 'site-packages', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.idea', '.vscode']):
                continue
            
            if py_file.stat().st_size > 500_000:  # Skip huge files
                continue
                
            try:
                findings = self.scan_file(py_file)
                all_findings.extend(findings)
            except Exception as e:
                print(f"Error scanning {py_file}: {e}")
        
        self.findings = all_findings
        return all_findings
    
    def generate_report(self, findings: List[Dict]) -> str:
        """Generate markdown report"""
        critical = [f for f in findings if f['type'] == 'CRITICAL']
        high = [f for f in findings if f['type'] == 'HIGH']
        medium = [f for f in findings if f['type'] == 'MEDIUM']
        low = [f for f in findings if f['type'] == 'LOW']
        
        report = f"""# Silent Business Defaults Scan Report

## Summary
- **CRITICAL**: {len(critical)} findings (must fix - business logic defaults)
- **HIGH**: {len(high)} findings (should fix - likely business defaults)
- **MEDIUM**: {len(medium)} findings (review needed)
- **LOW**: {len(low)} findings (likely config, review only)

## CRITICAL Findings (Must Fix)
"""
        for f in critical:
            report += f"""
### {f['file']}:{f['line_num']}
**Line:** `{f['line']}`
**Key:** `{f['key']}` = `{f['default']}`
**Fix:** {f['suggested_fix']}
"""
        
        report += "\n## HIGH Findings (Should Fix)\n"
        for f in high:
            report += f"""
### {f['file']}:{f['line_num']}
**Line:** `{f['line']}`
**Fix:** {f['suggested_fix']}
"""
        
        report += "\n## MEDIUM Findings (Review)\n"
        for f in medium:
            report += f"""
### {f['file']}:{f['line_num']}
**Line:** `{f['line']}`
**Fix:** {f['suggested_fix']}
"""
        
        return report


def main():
    scanner = SilentDefaultScanner()
    
    print("Scanning for silent business defaults...")
    findings = scanner.scan("D:/Claude/projects/2hao-analyst")
    
    print(f"\nFound {len(findings)} potential silent business defaults")
    
    critical = [f for f in findings if f['type'] == 'CRITICAL']
    high = [f for f in findings if f['type'] == 'HIGH']
    medium = [f for f in findings if f['type'] == 'MEDIUM']
    low = [f for f in findings if f['type'] == 'LOW']
    
    print(f"CRITICAL: {len(critical)}")
    print(f"HIGH: {len(high)}")
    print(f"MEDIUM: {len(medium)}")
    print(f"LOW: {len(low)}")
    
    # Generate detailed report
    report = scanner.generate_report(findings)
    report_path = Path("D:/Claude/projects/2hao-analyst/silent_defaults_report.md")
    report_path.write_text(scanner.generate_report(findings), encoding='utf-8')
    print(f"\nReport saved to: {report_path}")
    
    # Print critical findings
    if critical:
        print("\n=== CRITICAL FINDINGS ===")
        for f in critical[:20]:
            print(f"\n{f['file']}:{f['line_num']}")
            print(f"  Line: {f['line'][:100]}")
            print(f"  Fix: {f['suggested_fix'][:100]}")
    
    # Save findings as JSON for further processing
    json_path = Path("D:/Claude/projects/2hao-analyst/silent_defaults_findings.json")
    json_path.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nFindings saved to: {json_path}")


if __name__ == "__main__":
    main()