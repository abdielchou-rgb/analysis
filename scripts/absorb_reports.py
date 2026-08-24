#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1hao 资料库全量扫描吸收 — 把顶级机构研报变成 2hao 大脑的基准

扫描 D:\\Claude\\1hao-analyst-v51\\data 下的全部研报（国际投行/国内券商/
战略咨询/四大/管理咨询/财经媒体 + 券商咨询报告汇总），复用 data/report_scanner
的指标提取，输出到 2hao 的 data/ 消费层：

  1. data/absorbed_baseline.json    — 全量写作基线（分机构类别）
  2. data/absorbed_style_dna.json   — 机构风格 DNA（按机构聚合的写作特征）
  3. data/absorbed_methodology.json — 方法论/估值方法提取

消费方：
  - section_writer._build_data_bundle 读 baseline_findings（同类）
  - StyleCompiler 读方法论风格
  - chart_config 读机构风格 DNA

用法:
    python scripts/absorb_reports.py                 # 全量扫描
    python scripts/absorb_reports.py --quick         # 只扫每个类别前 N 份
    python scripts/absorb_reports.py --dry-run       # 只统计，不写
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("absorb")

# 1hao 资料库根：优先环境变量（VM 测试用），否则 Windows 路径（宿主机）
_data1_env = os.environ.get("DATA1_ROOT", "")
DATA1 = Path(_data1_env) if _data1_env else Path(r"D:\Claude\1hao-analyst-v51\data")

# 研报扫描目录
SCAN_DIRS = [
    ("国际投行", DATA1 / "深度研究报告原始文档" / "A_国际投行"),
    ("国内券商", DATA1 / "深度研究报告原始文档" / "B_国内券商"),
    ("战略咨询", DATA1 / "深度研究报告原始文档" / "C_战略咨询"),
    ("四大会计", DATA1 / "深度研究报告原始文档" / "D_四大会计"),
    ("管理咨询", DATA1 / "深度研究报告原始文档" / "E_管理咨询"),
    ("财经媒体", DATA1 / "深度研究报告原始文档" / "F_财经媒体"),
    ("券商报告", DATA1 / "券商与咨询报告汇总" / "券商报告"),
    ("咨询公司", DATA1 / "券商与咨询报告汇总" / "咨询公司报告"),
]

# 输出（2hao 消费层）
OUT_BASELINE = _ROOT / "data" / "absorbed_baseline.json"
OUT_STYLE = _ROOT / "data" / "absorbed_style_dna.json"
OUT_METHOD = _ROOT / "data" / "absorbed_methodology.json"


def extract_text(path: Path) -> str:
    """提取 PDF/DOCX 文本（内联，不导入 data 包避免触发引擎）"""
    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                parts = []
                for i, page in enumerate(pdf.pages):
                    if i >= 15:  # 前15页足够提取风格
                        break
                    t = page.extract_text() or ""
                    parts.append(t)
                return "\n".join(parts)
        except Exception as e:
            logger.debug("PDF 提取失败 %s: %s", path.name, e)
            return ""
    elif path.suffix.lower() == ".docx":
        try:
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs[:400])
        except Exception as e:
            logger.debug("DOCX 提取失败 %s: %s", path.name, e)
            return ""
    return ""


# 风格指标正则（复用 report_scanner 的模式）
_JUDGMENT_WORDS = ["我们认为", "我们判断", "我们预计", "我们预期", "有望", "将",
                   "意味着", "关键在于", "核心在于", "判断", "预计", "预期",
                   "看好", "看空", "超预期", "低于预期", "拐点", "反转"]
_COUNTER_CONSENSUS = ["而非", "不同于市场", "与市场分歧", "与市场共识", "超预期",
                      "低于预期", "颠覆", "拐点", "误读", "认知差", "预期差", "逆共识"]
_PATTERN_EXPERIENCE = re.compile(
    r'(我们在[^，。]{2,20}(调研|观察|走访|访谈|跟踪)[^。]{5,50})'
    r'|((20\d{2}|201[0-9])年.{2,10}(也|同样|类似|曾经)[^。]{10,60})')
_PATTERN_UNCERTAINTY = re.compile(
    r'(不确定性[集中在于在][^。]{10,60})|(风险集中[在于在][^。]{10,60})'
    r'|(关键[在于要看是][^。]{10,50})|(取决于[^。]{10,50})|(如果[^。]{10,80})')
_PATTERN_DATA_QUALITY = re.compile(
    r'(数据[来自源于][^。]{10,50})|(该数据[^。]{5,30}(可能|存在|偏低|偏高|低估|高估)[^。]{5,30})')


def scan_one(path: Path, category: str) -> dict:
    """扫描单份报告，返回指标 dict（内联，无引擎依赖）"""
    text = extract_text(path)
    if len(text) < 200:
        return None
    char_count = len(text)
    word_count = len(re.findall(r'[一-鿿]', text))
    # 判断密度
    kc = char_count / 1000
    jc = len(re.findall("|".join(_JUDGMENT_WORDS), text))
    cc = len(re.findall("|".join(_COUNTER_CONSENSUS), text))
    er = len(_PATTERN_EXPERIENCE.findall(text))
    uc = len(_PATTERN_UNCERTAINTY.findall(text))
    dq = len(_PATTERN_DATA_QUALITY.findall(text))
    return {
        "file": path.name,
        "category": category,
        "chars": char_count,
        "words": word_count,
        "judgment_density": round(jc / kc, 2) if kc > 0 else 0,
        "counter_density": round(cc / kc, 2) if kc > 0 else 0,
        "experience_refs": er,
        "uncertainty": uc,
        "data_quality": dq,
    }


def main():
    parser = argparse.ArgumentParser(description="1hao 资料库全量扫描吸收")
    parser.add_argument("--quick", type=int, default=0, help="每个类别只扫前 N 份（0=全部）")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写文件")
    args = parser.parse_args()

    # 收集所有研报文件
    all_files = []
    for cat, directory in SCAN_DIRS:
        if not directory.exists():
            logger.warning("目录不存在: %s", directory)
            continue
        files = list(directory.rglob("*.pdf")) + list(directory.rglob("*.docx"))
        if args.quick:
            files = files[:args.quick]
        logger.info("[%s] %d 份", cat, len(files))
        for f in sorted(files):
            if f.is_file():
                all_files.append((cat, f))

    logger.info("共 %d 份研报待扫描", len(all_files))
    if args.dry_run:
        print(f"\n扫描计划: {len(all_files)} 份")
        for cat, _ in all_files:
            pass
        return 0

    # 扫描
    results = []
    t0 = time.time()
    for i, (cat, f) in enumerate(all_files, 1):
        r = scan_one(f, cat)
        if r:
            results.append(r)
        if i % 20 == 0 or i == len(all_files):
            logger.info("进度 %d/%d, 有效 %d", i, len(all_files), len(results))
    elapsed = time.time() - t0
    logger.info("扫描完成: %d 份有效 (%d 失败), 用时 %.1fs",
                len(results), len(all_files) - len(results), elapsed)

    if not results:
        logger.error("无有效结果")
        return 1

    # ── 1. 写作基线（分类别 + 全量）──
    baseline = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "total_scanned": len(results)}
    by_cat = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    all_agg = defaultdict(float)
    for cat, items in by_cat.items():
        agg = {
            "count": len(items),
            "avg_chars": sum(i["chars"] for i in items) / len(items),
            "avg_judgment_density": sum(i["judgment_density"] for i in items) / len(items),
            "avg_counter_density": sum(i["counter_density"] for i in items) / len(items),
            "avg_experience_refs": sum(i["experience_refs"] for i in items) / len(items),
            "avg_uncertainty": sum(i["uncertainty"] for i in items) / len(items),
            "avg_data_quality": sum(i["data_quality"] for i in items) / len(items),
        }
        baseline[cat] = agg
        for k, v in agg.items():
            if k != "count":
                all_agg[k] += v
    # 全量平均
    n = len(results)
    baseline["all"] = {k: v / n for k, v in all_agg.items()}
    baseline["all"]["count"] = n
    OUT_BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("写作基线 → %s", OUT_BASELINE)

    # ── 2. 机构风格 DNA（按文件名前缀聚合机构）──
    inst_items = defaultdict(list)
    for r in results:
        # 文件名前缀 → 机构（如 GS-, MS-, JPM-, 高盛, 大摩 等）
        name = r["file"]
        inst = _detect_institution(name)
        if inst:
            inst_items[inst].append(r)
    style_dna = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "institutions": {}}
    for inst, items in inst_items.items():
        n_items = len(items)
        style_dna["institutions"][inst] = {
            "count": n_items,
            "avg_judgment_density": sum(i["judgment_density"] for i in items) / n_items,
            "avg_counter_density": sum(i["counter_density"] for i in items) / n_items,
            "avg_experience_refs": sum(i["experience_refs"] for i in items) / n_items,
            "avg_uncertainty": sum(i["uncertainty"] for i in items) / n_items,
            "avg_data_quality": sum(i["data_quality"] for i in items) / n_items,
        }
    OUT_STYLE.write_text(json.dumps(style_dna, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("机构风格 DNA → %s (%d 机构)", OUT_STYLE, len(inst_items))

    # ── 3. 方法论提取（估值/分析框架关键词）──
    method = _extract_methodology(results)
    OUT_METHOD.write_text(json.dumps(method, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("方法论 → %s", OUT_METHOD)

    print(f"\n=== 吸收完成 ===")
    print(f"  扫描研报: {len(results)} 份")
    print(f"  写作基线: {OUT_BASELINE}")
    print(f"  机构风格: {OUT_STYLE} ({len(inst_items)} 机构)")
    print(f"  方法论: {OUT_METHOD}")
    return 0


_INST_PREFIXES = [
    ("高盛", ["GS-", "高盛", "Goldman"]),
    ("摩根士丹利", ["MS-", "大摩", "Morgan Stanley"]),
    ("摩根大通", ["JPM-", "摩根大通", "JP Morgan"]),
    ("美银", ["BAC-", "美银", "BofA"]),
    ("伯恩斯坦", ["Bernstein", "伯恩斯坦"]),
    ("野村", ["Nomura", "野村"]),
    ("花旗", ["Citi", "花旗"]),
    ("中金", ["CICC", "中金"]),
    ("中信", ["中信", "CITIC"]),
    ("华福", ["华福"]),
    ("光大", ["光大"]),
]


def _detect_institution(fname: str) -> str:
    for inst, markers in _INST_PREFIXES:
        for m in markers:
            if m in fname:
                return inst
    return ""


_METHOD_KEYWORDS = {
    "DCF": ["DCF", "贴现", "折现现金流"],
    "可比公司": ["可比公司", "可比倍数", "peer", "P/E", "P/S", "EV/EBITDA"],
    "SOTP": ["SOTP", "分部估值", "sum-of-the-parts"],
    "目标价": ["目标价", "TP", "price target"],
    "风险收益": ["风险收益", "risk-reward", "下行风险"],
    "催化剂": ["催化剂", "catalyst", "事件驱动"],
    "敏感性": ["敏感性", "sensitivity", "情景分析"],
}


def _extract_methodology(results: list) -> dict:
    """从研报文件名+已提取指标推断方法论/估值方法出现频率"""
    freq = defaultdict(int)
    method_by_file = defaultdict(list)
    for r in results:
        name = r["file"].lower()
        for method, keywords in _METHOD_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in name:
                    freq[method] += 1
                    method_by_file[method].append(r["file"])
                    break
    return {"freq": dict(freq), "note": "方法提取基于文件名关键词（正文级提取待后续）"}


if __name__ == "__main__":
    sys.exit(main())
