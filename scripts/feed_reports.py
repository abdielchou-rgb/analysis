#!/usr/bin/env python3
"""2hao-analyst 研报投喂 CLI — 将研报PDF增量提取入知识库

用法:
    python scripts/feed_reports.py "path/to/report.pdf" [more.pdf ...]
    python scripts/feed_reports.py --dir path/to/reports_dir    # 批量喂一个目录
    python scripts/feed_reports.py --batch N                    # 从回测基线库2阶段增量消化N份

流程:
    1. 解析每份PDF文本（pdfplumber）
    2. 检测机构/评级/目标价/核心判断/行业规模
    3. 写入 data/baseline_findings.json（增量合并，去重）
    4. 汇总打印

依赖: pdfplumber（requirements 已含）
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.baseline_pdf_extractor import (
    extract_text,
    extract_findings,
    detect_institution,
)

OUTPUT = _ROOT / "data" / "baseline_findings.json"
FEED_LOG = _ROOT / "data" / "feed_history.json"


# ──────────────────────────────────────────────────────────────────────
# 增量入库
# ──────────────────────────────────────────────────────────────────────

def load_knowledge() -> dict:
    """读取现有知识库，兼容新旧格式。"""
    if not OUTPUT.exists():
        return {"_meta": {"stats": {"total": 0, "parsed": 0}, "generated": None}, "findings": {}}
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    # 兼容旧格式 {inst: [items]}
    if "findings" not in data:
        data = {"_meta": {"stats": {"total": 0, "parsed": 0}, "generated": None}, "findings": data}
    return data


def load_fed_files() -> set:
    """已投喂过的文件名（去重用）。"""
    if not FEED_LOG.exists():
        return set()
    try:
        return set(json.loads(FEED_LOG.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_fed_files(files: set) -> None:
    FEED_LOG.write_text(json.dumps(sorted(files), ensure_ascii=False, indent=2), encoding="utf-8")


def ingest_pdf(pdf_path: Path, knowledge: dict, fed: set) -> dict:
    """提取单份PDF并入库，返回结果统计。"""
    if pdf_path.name in fed:
        return {"status": "skipped_duplicate", "file": pdf_path.name}
    text = extract_text(str(pdf_path))
    if text.startswith("ERROR") or len(text) < 200:
        return {"status": "scanned_or_empty", "file": pdf_path.name}
    data = extract_findings(text)
    if not data:
        return {"status": "no_findings", "file": pdf_path.name}
    inst = detect_institution(str(pdf_path))
    data["file"] = pdf_path.name
    data["level"] = _classify_level(pdf_path)
    data["institution"] = inst
    data["fed_at"] = datetime.now().isoformat()
    knowledge["findings"].setdefault(inst, []).append(data)
    fed.add(pdf_path.name)
    return {"status": "ok", "file": pdf_path.name, "institution": inst}


def _classify_level(pdf_path: Path) -> str:
    parts = pdf_path.parts
    if "A级" in parts: return "A级"
    if "S级" in parts: return "S级"
    if "金牌" in parts: return "gold"
    if "academic" in parts: return "academic"
    return "unknown"


def save_knowledge(knowledge: dict) -> None:
    s = knowledge["_meta"]["stats"]
    knowledge["_meta"] = {
        "stats": s,
        "generated": datetime.now().isoformat(),
    }
    OUTPUT.write_text(json.dumps(knowledge, ensure_ascii=False, indent=2), encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="2hao-analyst 研报投喂 CLI")
    parser.add_argument("pdfs", nargs="*", help="要投喂的PDF文件路径")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dir", help="批量投喂目录下的所有PDF")
    group.add_argument("--batch", type=int, metavar="N",
                       help="从回测基线库2阶段/金牌增量消化N份")
    group.add_argument("--status", action="store_true", help="查看知识库统计")
    parser.add_argument("--force", action="store_true", help="忽略去重，强制重新提取")
    args = parser.parse_args()

    if not any([args.pdfs, args.dir, args.batch, args.status]):
        parser.print_help()
        return 1

    if args.status:
        knowledge = load_knowledge()
        stats = knowledge["_meta"]["stats"]
        print(f"知识库: {OUTPUT}")
        print(f"  总提取: {stats.get('parsed', 0)} 份 / {stats.get('total', 0)} 扫描")
        findings = knowledge.get("findings", {})
        print(f"  机构数: {len(findings)}")
        for inst, items in sorted(findings.items(), key=lambda x: -len(x[1]))[:15]:
            print(f"    {inst}: {len(items)}份")
        fed = load_fed_files()
        print(f"  已投喂去重库: {len(fed)} 文件")
        return 0

    knowledge = load_knowledge()
    fed = load_fed_files()
    if args.force:
        fed = set()

    # 收集要处理的PDF
    targets: list[Path] = []
    if args.pdfs:
        for f in args.pdfs:
            p = Path(f)
            if not p.exists():
                print(f"  [跳过] 不存在: {f}")
                continue
            targets.append(p)
    elif args.dir:
        d = Path(args.dir)
        if not d.exists():
            print(f"  [错误] 目录不存在: {d}")
            return 1
        targets = [p for p in d.rglob("*.pdf")]
    elif args.batch:
        gold_dir = _ROOT / "data" / "基线" / "回测基线库" / "2阶段" / "金牌"
        if not gold_dir.exists():
            print(f"  [错误] 金牌目录不存在: {gold_dir}")
            return 1
        all_pdfs = sorted(gold_dir.glob("*.pdf"))
        remaining = [p for p in all_pdfs if p.name not in fed or args.force]
        targets = remaining[: args.batch]
        print(f"  金牌库共{len(all_pdfs)}份，本次消化{len(targets)}份（剩余{len(remaining)-len(targets)}份待消化）")

    if not targets:
        print("  没有待处理的PDF（可能都已投喂，用 --force 强制重跑）")
        return 0

    print(f"开始投喂 {len(targets)} 份研报...")
    stats = {"ok": 0, "skipped_duplicate": 0, "scanned_or_empty": 0, "no_findings": 0, "errors": 0}
    for i, p in enumerate(targets, 1):
        try:
            r = ingest_pdf(p, knowledge, fed)
            stats[r["status"]] = stats.get(r["status"], 0) + 1
        except Exception as e:
            stats["errors"] += 1
            if stats["errors"] <= 3:
                print(f"  [错误] {p.name}: {e}")
        if i % 50 == 0:
            print(f"  ... {i}/{len(targets)} (ok={stats['ok']})")
            save_knowledge(knowledge)  # 中途落盘防丢

    # 更新统计并落盘
    prev = knowledge["_meta"]["stats"].get("parsed", 0)
    knowledge["_meta"]["stats"] = {
        "total": prev + stats["ok"],
        "parsed": prev + stats["ok"],
        "ok": stats["ok"],
        "skipped": stats["scanned_or_empty"] + stats["no_findings"],
    }
    save_knowledge(knowledge)
    save_fed_files(fed)

    print("\n[完成]")
    print(f"  成功入库: {stats['ok']}")
    print(f"  扫描版/空: {stats['scanned_or_empty']}")
    print(f"  无有效字段: {stats['no_findings']}")
    print(f"  重复跳过: {stats['skipped_duplicate']}")
    print(f"  错误: {stats['errors']}")
    print(f"  知识库当前: {knowledge['_meta']['stats']['parsed']} 份 / {len(knowledge['findings'])} 机构")
    return 0


if __name__ == "__main__":
    sys.exit(main())
