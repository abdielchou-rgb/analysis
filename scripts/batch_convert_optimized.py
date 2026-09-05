#!/usr/bin/env python
"""
Optimized batch conversion using persistent mineru-api server.
- Uses API server to avoid per-chunk startup overhead
- Larger chunk size (default 60) for better throughput
- Parallel chunk processing (up to 3 concurrent, matching API concurrency limit)
- Resumable with state tracking
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Force UTF-8 stdout/stderr
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
RAW = ROOT / "benchmark" / "golden_raw"
GOLDEN = ROOT / "benchmark" / "golden"
STATE = GOLDEN / "convert_state.jsonl"
LOG = GOLDEN / "convert.log"

CATEGORIES = [
    "unlisted_company",
    "decision_memo",
    "earnings_notes",
    "listed_company",
    "industry_deep",
]

# Optimized settings
CHUNK = 60  # Increased from 30
CHUNK_TIMEOUT = 5400  # 1.5h per chunk (larger chunks take longer)
MAX_CONCURRENT = 3  # Match API server concurrency limit
API_URL = "http://127.0.0.1:8000"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        safe = line.encode("ascii", errors="replace").decode("ascii")
        print(safe, flush=True)
    with open(LOG, "a", encoding="utf-8", errors="replace") as f:
        f.write(line + "\n")


def hardlink_chunk(src_files: list[Path], chunk_dir: Path) -> int:
    chunk_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in src_files:
        target = chunk_dir / f.name
        if target.exists():
            target.unlink()
        try:
            os.link(f, target)
        except OSError:
            shutil.copy2(f, target)
        n += 1
    return n


def restructure(temp_out: Path, category: Path, chunk_files: list[Path]) -> tuple[list[str], list[str]]:
    done, missing = [], []
    found = {}
    for md in temp_out.rglob("*.md"):
        stem = md.name[: -len(".md")]
        found[stem] = md
    for f in chunk_files:
        stem = f.stem
        target = category / f"{stem}.md"
        if target.exists():
            done.append(stem)
            continue
        md = found.get(stem)
        if md is None:
            missing.append(stem)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md, target)
        done.append(stem)
    return done, missing


def convert_chunk(pdf_files: list[Path], category_name: str, chunk_size: int, chunk_idx: int) -> dict:
    cat_dir = GOLDEN / category_name
    cat_dir.mkdir(parents=True, exist_ok=True)

    remaining = [f for f in pdf_files if not (cat_dir / f"{f.stem}.md").exists()]
    if not remaining:
        return {"ok": 0, "missing": 0, "rc": 0}

    chunk = remaining
    chunk_dir = GOLDEN / f"_chunk_{category_name}_{chunk_idx}"
    temp_out = GOLDEN / f"_tmpout_{category_name}_{chunk_idx}"
    shutil.rmtree(chunk_dir, ignore_errors=True)
    shutil.rmtree(temp_out, ignore_errors=True)

    hardlink_chunk(chunk, chunk_dir)
    t0 = time.time()
    log(f"{category_name}: chunk {chunk_idx} ({len(chunk)} files)")

    cmd = [
        sys.executable,
        "-m",
        "mineru.cli.client",
        "-p",
        str(chunk_dir),
        "-o",
        str(temp_out),
        "--api-url",
        API_URL,
        "-b",
        "pipeline",
        "-m",
        "auto",
        "-l",
        "ch",
        "-f",
        "True",
        "-t",
        "True",
    ]
    rc, err_tail = 0, ""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=CHUNK_TIMEOUT, encoding="utf-8", errors="replace"
        )
        rc = r.returncode
        err_tail = (r.stderr or "")[-800:]
    except subprocess.TimeoutExpired:
        rc, err_tail = -1, "chunk timeout"
    except Exception as e:
        rc, err_tail = -2, repr(e)

    done, missing = restructure(temp_out, cat_dir, chunk)
    shutil.rmtree(temp_out, ignore_errors=True)
    shutil.rmtree(chunk_dir, ignore_errors=True)

    dt = time.time() - t0
    log(f"{category_name}: chunk {chunk_idx} done in {dt:.0f}s rc={rc} md_ok={len(done)} md_missing={len(missing)}")
    if missing:
        log(f"{category_name}: missing stems sample: {missing[:3]}")
    if rc != 0 and err_tail:
        log(f"{category_name}: stderr tail: {err_tail}")

    return {
        "cat": category_name,
        "chunk": chunk_idx,
        "ok": len(done),
        "missing": len(missing),
        "rc": rc,
        "secs": round(dt),
    }


def process_category(category_name: str, chunk_size: int, max_concurrent: int) -> None:
    pdfs = sorted((RAW / category_name).glob("*.pdf"))
    total_md = len(list((GOLDEN / category_name).glob("*.md"))) if (GOLDEN / category_name).exists() else 0
    log(f"=== {category_name}: {len(pdfs)} PDFs, {total_md} MD already present ===")

    # Filter already converted
    remaining = [f for f in pdfs if not (GOLDEN / category_name / f"{f.stem}.md").exists()]
    if not remaining:
        log(f"{category_name}: all already converted")
        return

    # Split into chunks
    chunks = [remaining[i : i + chunk_size] for i in range(0, len(remaining), chunk_size)]
    log(f"{category_name}: {len(chunks)} chunks of up to {chunk_size} files each")

    # Process chunks with parallelism
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {
            executor.submit(convert_chunk, chunk, category_name, chunk_size, i + 1): i + 1
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                with open(STATE, "a", encoding="utf-8", errors="replace") as f:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
            except Exception as e:
                log(f"{category_name}: chunk {idx} failed with exception: {e}")
                with open(STATE, "a", encoding="utf-8", errors="replace") as f:
                    f.write(
                        json.dumps(
                            {"cat": category_name, "chunk": idx, "ok": 0, "missing": 0, "rc": -3, "secs": 0},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

    final = len(list((GOLDEN / category_name).glob("*.md")))
    log(f"=== {category_name}: final {final}/{len(pdfs)} ===")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=CATEGORIES)
    ap.add_argument("--chunk", type=int, default=60)
    ap.add_argument("--concurrent", type=int, default=3)
    args = ap.parse_args()

    cats = [args.only] if args.only else CATEGORIES
    for cat in cats:
        process_category(cat, args.chunk, args.concurrent)
    log("ALL CATEGORIES COMPLETE")


if __name__ == "__main__":
    main()
