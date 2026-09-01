#!/usr/bin/env python
"""
Efficient batch conversion: Process each category directory with single CLI call,
then restructure output to flat benchmark/golden/{category}/{pdf_stem}.md
"""

import subprocess
import sys
import shutil
from pathlib import Path


def process_category(category, golden_raw, golden):
    """Process all PDFs in a category using single mineru CLI call."""
    src_dir = golden_raw / category
    if not src_dir.exists():
        print(f"  Source dir not found: {src_dir}")
        return 0, 0
    
    pdf_files = list(src_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"  No PDFs in {category}")
        return 0, 0
    
    # Count already converted
    existing = list((golden / category).glob("*.md")) if (golden / category).exists() else []
    remaining = [p for p in pdf_files if not (golden / category / f"{p.stem}.md").exists()]
    
    print(f"  {category}: {len(pdf_files)} total, {len(existing)} done, {len(remaining)} remaining")
    
    if not remaining:
        return len(existing), 0
    
    # Temp output for this category
    temp_out = golden / f"temp_{category}"
    if temp_out.exists():
        shutil.rmtree(temp_out)
    temp_out.mkdir(parents=True)
    
    # Run mineru CLI on the whole source directory
    cmd = [
        sys.executable, '-m', 'mineru.cli.client',
        '-p', str(src_dir),
        '-o', str(temp_out),
        '-b', 'pipeline',
        '-m', 'auto',
        '-l', 'ch',
        '-f', 'True',
        '-t', 'True'
    ]
    
    print(f"  Running CLI on {len(pdf_files)} files...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)  # 2 hour timeout
        if result.returncode != 0:
            print(f"  CLI failed: {result.stderr[-1000:]}")
            return len(existing), len(remaining)
    except subprocess.TimeoutExpired:
        print(f"  CLI timeout after 2 hours")
        return len(existing), len(remaining)
    except Exception as e:
        print(f"  CLI error: {e}")
        return len(existing), len(remaining)
    
    # Restructure: find all .md files and copy to flat structure
    md_files = list(temp_out.glob(f"**/*.md"))
    copied = 0
    for md in md_files:
        # Expected: temp_category/{pdf_stem}/auto/{pdf_stem}.md
        pdf_stem = md.parent.parent.name  # go up two levels: auto -> pdf_stem
        target = golden / category / f"{pdf_stem}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md, target)
        copied += 1
    
    # Cleanup
    shutil.rmtree(temp_out, ignore_errors=True)
    
    print(f"  Copied {copied} MD files to {golden/category}")
    return len(existing) + copied, len(remaining) - copied


def main():
    golden_raw = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_raw")
    golden = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden")
    
    golden.mkdir(parents=True, exist_ok=True)
    
    categories = ["listed_company", "industry_deep", "unlisted_company", "earnings_notes", "decision_memo"]
    
    total_done = 0
    total_failed = 0
    
    for cat in categories:
        print(f"\n=== Processing {cat} ===")
        done, failed = process_category(cat, golden_raw, golden)
        total_done += done
        total_failed += failed
    
    print(f"\n=== Complete ===")
    print(f"Total successful: {total_done}")
    print(f"Total failed: {total_failed}")


if __name__ == "__main__":
    main()