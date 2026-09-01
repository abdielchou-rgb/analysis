#!/usr/bin/env python
"""
Resumable chunked PDF->MD conversion via mineru CLI (directory mode).

Design:
  - Each category is processed in chunks of N PDFs (hardlinked into a temp chunk dir).
  - One mineru CLI invocation per chunk (server starts once per chunk, pages batched in windows).
  - After each chunk: restructure temp_out/{stem}/auto/{stem}.md -> golden/{cat}/{stem}.md, then delete temp.
  - Fully resumable: skips PDFs whose target MD already exists.
  - State log: benchmark/golden/convert_state.jsonl (one line per chunk) + convert.log

Usage:
  python scripts/batch_convert_resumable.py                # all categories
  python scripts/batch_convert_resumable.py --only unlisted_company --chunk 10
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

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

CHUNK = 30
CHUNK_TIMEOUT = 7200  # 2h per chunk


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def hardlink_chunk(src_files: list[Path], chunk_dir: Path) -> int:
    """Hardlink PDFs into chunk dir; fall back to copy. Returns count."""
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
    """Move generated MDs to flat golden structure. Returns (done_stems, missing_stems)."""
    done, missing = [], []
    found = {}
    # Map: any *.md under temp_out where parent structure is {stem}/{method}/{stem}.md
    for md in temp_out.rglob("*.md"):
        stem = md.name[: -len(".md")]
        # prefer the file whose parent dir structure matches {stem}/{method}/
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


def convert_chunk(pdf_files: list[Path], category_name: str, chunk_size: int) -> None:
    cat_dir = GOLDEN / category_name
    cat_dir.mkdir(parents=True, exist_ok=True)

    remaining = [f for f in pdf_files if not (cat_dir / f"{f.stem}.md").exists()]
    if not remaining:
        return

    for i in range(0, len(remaining), chunk_size):
        chunk = remaining[i : i + chunk_size]
        chunk_dir = GOLDEN / f"_chunk_{category_name}"
        temp_out = GOLDEN / f"_tmpout_{category_name}"
        shutil.rmtree(chunk_dir, ignore_errors=True)
        shutil.rmtree(temp_out, ignore_errors=True)

        hardlink_chunk(chunk, chunk_dir)
        t0 = time.time()
        log(f"{category_name}: chunk {i // chunk_size + 1}/{(len(remaining) + chunk_size - 1) // chunk_size} ({len(chunk)} files)")

        cmd = [
            sys.executable, "-m", "mineru.cli.client",
            "-p", str(chunk_dir),
            "-o", str(temp_out),
            "-b", "pipeline", "-m", "auto", "-l", "ch",
            "-f", "True", "-t", "True",
        ]
        rc, err_tail = 0, ""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=CHUNK_TIMEOUT, encoding="utf-8", errors="replace")
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
        log(f"{category_name}: chunk done in {dt:.0f}s rc={rc} md_ok={len(done)} md_missing={len(missing)}")
        if missing:
            log(f"{category_name}: missing stems sample: {missing[:3]}")
        if rc != 0 and err_tail:
            log(f"{category_name}: stderr tail: {err_tail}")

        with open(STATE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "cat": category_name, "chunk": i // chunk_size + 1,
                "ok": len(done), "missing": len(missing), "rc": rc, "secs": round(dt),
            }, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=CATEGORIES)
    ap.add_argument("--chunk", type=int, default=CHUNK)
    args = ap.parse_args()

    cats = [args.only] if args.only else CATEGORIES
    for cat in cats:
        pdfs = sorted((RAW / cat).glob("*.pdf"))
        total_md = len(list((GOLDEN / cat).glob("*.md"))) if (GOLDEN / cat).exists() else 0
        log(f"=== {cat}: {len(pdfs)} PDFs, {total_md} MD already present ===")
        convert_chunk(pdfs, cat, args.chunk)
        final = len(list((GOLDEN / cat).glob("*.md")))
        log(f"=== {cat}: final {final}/{len(pdfs)} ===")
    log("ALL CATEGORIES COMPLETE")


if __name__ == "__main__":
    main()
