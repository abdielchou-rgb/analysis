#!/usr/bin/env python3
"""扫描版/无文本层 PDF 检测器 — 定位需要 MinerU 的文档

基线库里绝大多数 PDF 是文本型（pdfplumber 直接提取），只有扫描版/图片型
需要 MinerU（OCR）。本脚本用 pdfplumber 快速扫全库，找出"提取为空"的 PDF，
输出清单供 MinerU 按需解析（避免全量跑云 API 的 71s/份开销）。

用法：
  python scripts/detect_scanned_pdf.py [--dir 目录] [--min-chars 50] [--limit 20]
  # 默认扫 data/基线/原始文档，输出前 20 个疑似扫描版

产出：
  1. 打印疑似扫描版清单
  2. 写 data/scanned_pdf_report.json（全量结果，含每份的字符数与判定）
"""

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pdfplumber

_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = _ROOT / "data" / "基线" / "原始文档"
REPORT = _ROOT / "data" / "scanned_pdf_report.json"

SCAN_PAGES = 2  # 每份扫描前几页判断（前2页通常有封面/目录，纯图=扫描版）
MIN_CHARS = 50  # 前N页有效字符 < 此值 → 判为疑似扫描版


def _scan_one(args) -> tuple:
    """单文件扫描（供并行池调用）。返回 (rel_path, {chars, scanned, error, size})"""
    root, p, min_chars = args
    chars = 0
    error = None
    try:
        with pdfplumber.open(p) as pdf:
            for j in range(min(SCAN_PAGES, len(pdf.pages))):
                chars += len((pdf.pages[j].extract_text() or "").strip())
    except Exception as e:
        error = str(e)[:100]
    try:
        rel = str(p.resolve().relative_to(root.resolve()))
    except ValueError:
        rel = str(p)
    return rel, {
        "chars": chars,
        "scanned": chars < min_chars and error is None,
        "error": error,
        "size": p.stat().st_size,
    }


def detect_scanned(root: Path, min_chars: int = MIN_CHARS, workers: int = 4) -> dict:
    """并行扫描目录下所有非空 PDF，返回 {path: {chars, scanned, error}}"""
    pdfs = [p for p in root.rglob("*.pdf") if p.stat().st_size > 0]
    results = {}
    t0 = time.time()
    tasks = [(root, p, min_chars) for p in pdfs]
    if workers > 1 and len(pdfs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_scan_one, t): t for t in tasks}
            for fut in as_completed(futs):
                try:
                    rel, info = fut.result()
                    results[rel] = info
                except Exception as e:
                    rel = str(futs[fut][1])
                    results[rel] = {"chars": 0, "scanned": True, "error": f"worker: {str(e)[:80]}", "size": 0}
    else:
        for p in pdfs:
            rel, info = _scan_one((root, p, min_chars))
            results[rel] = info
    results["_meta"] = {
        "total": len(pdfs),
        "scan_pages": SCAN_PAGES,
        "min_chars": min_chars,
        "scanned_count": sum(1 for v in results.values() if isinstance(v, dict) and v.get("scanned")),
        "error_count": sum(1 for v in results.values() if isinstance(v, dict) and v.get("error")),
        "elapsed_sec": round(time.time() - t0, 1),
        "scan_dir": str(root),
        "workers": workers,
    }
    return results


def main():
    ap = argparse.ArgumentParser(description="扫描版/无文本层 PDF 检测器")
    ap.add_argument("--dir", default=None, help="扫描目录（默认 data/基线/原始文档）")
    ap.add_argument("--min-chars", type=int, default=MIN_CHARS, help="有效字符阈值（默认50）")
    ap.add_argument("--workers", type=int, default=4, help="并行进程数（默认4，全库扫描提速）")
    ap.add_argument("--limit", type=int, default=20, help="打印前N个疑似扫描版（0=全部）")
    ap.add_argument("--json", action="store_true", help="只输出 JSON 结果文件，不打印清单")
    args = ap.parse_args()

    root = Path(args.dir) if args.dir else DEFAULT_DIR
    if not root.exists():
        print(f"目录不存在: {root}", file=sys.stderr)
        sys.exit(1)

    results = detect_scanned(root, args.min_chars, args.workers)
    meta = results.pop("_meta")

    # 写报告
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"meta": meta, "pdfs": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(f"报告已写: {REPORT}")
        print(
            f"总计 {meta['total']} 份, 疑似扫描版 {meta['scanned_count']} 份, 错误 {meta['error_count']} 份, 耗时 {meta['elapsed_sec']}s"
        )
        return

    print(f"扫描 {meta['total']} 份 PDF, 耗时 {meta['elapsed_sec']}s")
    print(f"疑似扫描版（前2页 < {meta['min_chars']} 字）: {meta['scanned_count']} 份")
    print(f"打开错误: {meta['error_count']} 份")
    print("\n--- 疑似扫描版清单 ---")
    scanned = [(k, v) for k, v in results.items() if v.get("scanned")]
    scanned.sort(key=lambda kv: kv[1]["size"], reverse=True)
    limit = args.limit if args.limit > 0 else len(scanned)
    for k, v in scanned[:limit]:
        print(f"  {v['size'] // 1024:6d}KB | {k}")
    print("\n用 MinerU 解析这些：")
    print(
        '  python -c "from core.mineru_parser import extract_markdown; '
        "print(extract_markdown('<pdf路径>', mode='cloud', page_range='1-20')[:500])\""
    )
    print(f"\n完整报告: {REPORT}")


if __name__ == "__main__":
    main()
