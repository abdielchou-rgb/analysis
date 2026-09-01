#!/usr/bin/env python
"""
Batch PDF to Markdown conversion using MinerU CLI.
Processes PDFs in small batches and flattens output to benchmark/golden/{category}/{pdf_stem}.md
"""

import subprocess
import sys
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


def process_batch(pdf_files, category, output_root, batch_size=10):
    """Process a batch of PDFs using mineru CLI."""
    if not pdf_files:
        return 0, 0
    
    success = 0
    failed = 0
    
    # Process in smaller sub-batches
    for i in range(0, len(pdf_files), batch_size):
        batch = pdf_files[i:i+batch_size]
        print(f"  Processing batch {i//batch_size + 1}/{(len(pdf_files)-1)//batch_size + 1}: {len(batch)} files")
        
        # Create temp output directory for this batch
        temp_out = output_root / "temp_cli_out"
        temp_out.mkdir(parents=True, exist_ok=True)
        
        # Run mineru CLI on the batch
        pdf_paths = [str(f) for f in batch]
        cmd = [
            sys.executable, '-m', 'mineru.cli.client',
            '-p', str(batch[0].parent),  # Process directory containing these files
            '-o', str(temp_out),
            '-b', 'pipeline',
            '-m', 'auto',
            '-l', 'ch',
            '-f', 'True',
            '-t', 'True'
        ]
        
        # Actually, we need to process individual files or a directory
        # Let's process the whole source directory once and then copy results
        # But that would process all files at once. Let me do per-file instead.
        pass
    
    return success, failed


def process_single_pdf(pdf_path, category, output_root):
    """Process a single PDF using mineru CLI and copy MD to expected location."""
    pdf_name = pdf_path.stem
    expected_md = output_root / category / f"{pdf_name}.md"
    
    # Skip if already exists
    if expected_md.exists():
        return True, "skipped"
    
    # Create temp output directory
    temp_out = output_root / "temp_cli_out" / category / pdf_name
    temp_out.mkdir(parents=True, exist_ok=True)
    
    try:
        cmd = [
            sys.executable, '-m', 'mineru.cli.client',
            '-p', str(pdf_path),
            '-o', str(temp_out),
            '-b', 'pipeline',
            '-m', 'auto',
            '-l', 'ch',
            '-f', 'True',
            '-t', 'True'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            return False, f"CLI failed: {result.stderr[-500:]}"
        
        # Find the generated MD file
        md_files = list(temp_out.glob(f"**/{pdf_name}.md"))
        if not md_files:
            return False, "No MD file generated"
        
        # Copy to expected location
        expected_md.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md_files[0], expected_md)
        
        # Cleanup temp
        shutil.rmtree(temp_out, ignore_errors=True)
        
        return True, "success"
        
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def main():
    golden_raw = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden_raw")
    golden = Path(r"D:\Claude\projects\2hao-analyst\benchmark\golden")
    
    golden.mkdir(parents=True, exist_ok=True)
    
    categories = ["listed_company", "industry_deep", "unlisted_company", "earnings_notes", "decision_memo"]
    
    # Collect all PDFs
    all_tasks = []
    for cat in categories:
        cat_dir = golden_raw / cat
        if cat_dir.exists():
            pdf_files = list(cat_dir.glob("*.pdf"))
            for pdf in pdf_files:
                all_tasks.append((pdf, cat))
    
    print(f"Total PDFs to process: {len(all_tasks)}")
    
    # Process sequentially to avoid overwhelming the GPU
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    for i, (pdf_path, category) in enumerate(all_tasks, 1):
        print(f"[{i}/{len(all_tasks)}] {category}/{pdf_path.name}")
        ok, msg = process_single_pdf(pdf_path, category, golden)
        if ok:
            if msg == "skipped":
                skipped_count += 1
                print(f"  Skipped (already exists)")
            else:
                success_count += 1
                print(f"  OK")
        else:
            failed_count += 1
            print(f"  FAILED: {msg}")
        
        # Small delay between files
        time.sleep(1)
    
    print(f"\n=== Complete ===")
    print(f"Success: {success_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")


if __name__ == "__main__":
    main()