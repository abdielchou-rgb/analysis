#!/usr/bin/env python
"""Parallel MinerU conversion with multiple servers."""

import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
GOLDEN_RAW = ROOT / "benchmark" / "golden_raw"
GOLDEN = ROOT / "benchmark" / "golden"
STATE_FILE = ROOT / "benchmark" / "convert_state_parallel.jsonl"
LOG_FILE = ROOT / "benchmark" / "convert_parallel.log"

NUM_SERVERS = 4  # Number of parallel MinerU servers
CHUNK_SIZE = 10  # Files per chunk (smaller for parallel)
PORT_BASE = 54800  # Starting port for servers

log_lock = threading.Lock()


def log(msg):
    with log_lock:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def start_server(port):
    """Start a MinerU server on specified port."""
    cmd = [sys.executable, "-m", "mineru.cli.fast_api", "--host", "127.0.0.1", "--port", str(port)]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    time.sleep(3)  # Wait for server to start
    return proc


def convert_chunk(pdf_files, category_name, port, chunk_id):
    """Convert a chunk of PDFs using a specific server."""
    chunk_dir = ROOT / "benchmark" / f"temp_chunk_{port}"
    chunk_dir.mkdir(exist_ok=True)

    try:
        # Hardlink files to chunk dir
        for pdf in pdf_files:
            link = chunk_dir / pdf.name
            if not link.exists():
                os.link(str(pdf), str(link))

        # Create temp output dir
        temp_out = ROOT / "benchmark" / f"temp_out_{port}"
        temp_out.mkdir(exist_ok=True)

        # Run MinerU client
        cmd = [
            sys.executable,
            "-m",
            "mineru.cli.client",
            "-p",
            str(chunk_dir),
            "-o",
            str(temp_out),
            "--api-url",
            f"http://127.0.0.1:{port}",
            "-b",
            "pipeline",
            "-m",
            "auto",
        ]

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, encoding="utf-8", errors="replace")

        # Restructure output
        md_ok = 0
        md_missing = 0

        for pdf in pdf_files:
            stem = pdf.stem
            src_md = temp_out / "auto" / f"{stem}.md"
            dst_md = GOLDEN / category_name / f"{stem}.md"

            if src_md.exists():
                dst_md.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_md), str(dst_md))
                md_ok += 1
            else:
                md_missing += 1

        return md_ok, md_missing

    except subprocess.TimeoutExpired:
        return 0, len(pdf_files)
    except Exception as e:
        log(f"Error in chunk {chunk_id}: {e}")
        return 0, len(pdf_files)
    finally:
        # Cleanup
        shutil.rmtree(str(chunk_dir), ignore_errors=True)
        shutil.rmtree(str(temp_out), ignore_errors=True)


def main():
    log(f"Starting parallel conversion with {NUM_SERVERS} servers")

    # Start servers
    servers = []
    for i in range(NUM_SERVERS):
        port = PORT_BASE + i
        proc = start_server(port)
        servers.append((proc, port))
        log(f"Started server on port {port} (PID: {proc.pid})")

    # Process categories
    categories = ["industry_deep"]  # Add more categories as needed

    for cat in categories:
        cat_dir = GOLDEN_RAW / cat
        if not cat_dir.exists():
            continue

        pdfs = list(cat_dir.glob("*.pdf"))
        log(f"Processing {cat}: {len(pdfs)} PDFs")

        # Split into chunks
        chunks = [pdfs[i : i + CHUNK_SIZE] for i in range(0, len(pdfs), CHUNK_SIZE)]

        # Process chunks in parallel
        with ThreadPoolExecutor(max_workers=NUM_SERVERS) as executor:
            futures = {}
            for i, chunk in enumerate(chunks):
                server_idx = i % NUM_SERVERS
                port = servers[server_idx][1]
                future = executor.submit(convert_chunk, chunk, cat, port, i)
                futures[future] = (i, port)

            for future in as_completed(futures):
                chunk_id, port = futures[future]
                try:
                    md_ok, md_missing = future.result()
                    log(f"Chunk {chunk_id} (port {port}): +{md_ok} MDs, {md_missing} missing")
                except Exception as e:
                    log(f"Chunk {chunk_id} failed: {e}")

    # Stop servers
    for proc, port in servers:
        proc.terminate()
        log(f"Stopped server on port {port}")

    log("Parallel conversion completed")


if __name__ == "__main__":
    import shutil

    main()
