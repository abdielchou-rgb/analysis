"""V51.6 研报批量扫描管线

从投行估值数据集中批量提取并分析真实研报，
生成反AI指纹命中率、人感评分、风格基线的统计基线。

输入: data/投行估值数据加模板加分析方法！ 100家上市/估值/行业研究报告/
      data/投行估值数据加模板加分析方法！ 100家上市/估值/研究报告/
输出: benchmark/report_baseline.csv + benchmark/report_baseline_stats.json

FP4 关键: 这是"用真实数据校准系统"的闭环步骤。
  「人感评分 0.50 → 真实研报的人感评分是否也是 0.50？」
  「P0 级反AI指纹 0 处 → 真实研报有多少处？」
  回答这些问题的唯一方式是跑在真实研报上。
"""

from __future__ import annotations
import csv
import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("v51.scan.reports")

# ═══════════════════════════════════════════════════════════════
# 文本提取
# ═══════════════════════════════════════════════════════════════

try:
    import pdfplumber

    _HAS_PDF = True
except ImportError:
    _HAS_PDF = False

try:
    from docx import Document

    _HAS_DOCX = True
except ImportError:
    _HAS_DOCX = False


def extract_text_from_pdf(path: Path) -> str:
    """从 PDF 提取文本。"""
    if not _HAS_PDF:
        return ""
    try:
        text_parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                text_parts.append(t)
                if len("".join(text_parts)) > 50000:  # 防止过大的文件
                    break
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning(f"PDF extract failed: {path.name}: {e}")
        return ""


def extract_text_from_docx(path: Path) -> str:
    """从 docx 提取文本。"""
    if not _HAS_DOCX:
        return ""
    try:
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.warning(f"DOCX extract failed: {path.name}: {e}")
        return ""


def extract_text(path: Path) -> str:
    """从文件提取文本。"""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext == ".docx":
        return extract_text_from_docx(path)
    return ""


# ═══════════════════════════════════════════════════════════════
# 扫描引擎
# ═══════════════════════════════════════════════════════════════

# 反 AI 指纹 P0 级正则
P0_PATTERNS = {
    "P0-01 值得注意的是": r"值得注意的是[，。,．]?",
    "P0-03 综上所述": r"综上所述[，。]?",
    "P0-04 不可否认": r"不可否认的是[，。]?",
    "P0-05 在当前": r"在[当今当前近年来][，。\s]",
    "P0-07 众所周知": r"众所周知[，。]?",
    "P0-09 重要意义": r"具有重要意义[，。深远影响]",
    "P0-11 总体而言": r"总体而言[整体来看][，。]?",
    "P0-12 需要指出": r"需要指出的是[，。]?",
}

# 人感信号正则（复用 ai_fingerprints.py 的模式）
PATTERN_EXPERIENCE = re.compile(
    r"(我们在[^，。]{2,20}(调研|观察|走访|访谈|跟踪)[^。]{5,50})"
    r"|((20\d{2}|201[0-9])年.{2,10}(也|同样|类似|曾经)[^。]{10,60})"
    r"|(历史[上地][^。]{10,60})"
)

PATTERN_UNCERTAINTY = re.compile(
    r"(不确定性[集中在于在][^。]{10,60})"
    r"|(风险集中[在于在][^。]{10,60})"
    r"|(关键[在于要看是][^。]{10,50})"
    r"|(取决于[^。]{10,50})"
    r"|(如果[^。]{10,80})"
)

PATTERN_DATA_QUALITY = re.compile(
    r"(数据[来自源于][^。]{10,50})"
    r"|(该数据[^。]{5,30}(可能|存在|偏低|偏高|低估|高估)[^。]{5,30})"
    r"|(样本[覆盖大小]?[^。]{5,30})"
)

# 判断词库
JUDGMENT_WORDS = [
    "我们认为",
    "我们判断",
    "我们预计",
    "我们预期",
    "有望",
    "将",
    "意味着",
    "关键在于",
    "核心在于",
    "判断",
    "预计",
    "预期",
    "看好",
    "看空",
    "超预期",
    "低于预期",
    "拐点",
    "反转",
]

# 反共识词库
COUNTER_CONSENSUS = [
    "而非",
    "不同于市场",
    "与市场分歧",
    "与市场共识",
    "超预期",
    "低于预期",
    "颠覆",
    "拐点",
    "误读",
    "认知差",
    "预期差",
    "逆共识",
]


@dataclass
class ReportScan:
    """单份报告的分析结果。"""

    file_name: str = ""
    category: str = ""
    char_count: int = 0
    word_count: int = 0  # 中文按字数

    # 反 AI 指纹
    p0_hits: dict = field(default_factory=dict)
    total_p0: int = 0

    # 人感信号
    experience_refs: int = 0
    uncertainty_hits: int = 0
    data_quality_hits: int = 0

    # 判断密度
    judgment_count: int = 0
    judgment_density: float = 0.0  # /千字

    # 反共识密度
    counter_consensus_count: int = 0
    counter_density: float = 0.0  # /千字

    # 风格特征
    avg_sentence_chars: float = 0.0
    paragraph_count: int = 0
    short_para_ratio: float = 0.0  # <60字的段落占比


def scan_report(text: str, file_name: str = "", category: str = "") -> ReportScan:
    """扫描一份报告的所有指标。"""
    result = ReportScan(file_name=file_name, category=category)
    if not text or len(text) < 100:
        return result

    result.char_count = len(text)
    result.word_count = len(re.findall(r"[一-鿿]", text))

    # 反 AI 指纹
    for pattern_name, pattern in P0_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            result.p0_hits[pattern_name] = len(matches)
            result.total_p0 += len(matches)

    # 人感信号
    result.experience_refs = len(PATTERN_EXPERIENCE.findall(text))
    result.uncertainty_hits = len(PATTERN_UNCERTAINTY.findall(text))
    result.data_quality_hits = len(PATTERN_DATA_QUALITY.findall(text))

    # 判断密度
    kw = "|".join(JUDGMENT_WORDS)
    result.judgment_count = len(re.findall(kw, text))
    kc = result.char_count / 1000
    result.judgment_density = round(result.judgment_count / kc, 2) if kc > 0 else 0

    # 反共识密度
    ckw = "|".join(COUNTER_CONSENSUS)
    result.counter_consensus_count = len(re.findall(ckw, text))
    result.counter_density = round(result.counter_consensus_count / kc, 2) if kc > 0 else 0

    # 段落统计
    paragraphs = [p for p in text.split("\n\n") if len(p.strip()) > 10]
    result.paragraph_count = len(paragraphs)
    if paragraphs:
        short = sum(1 for p in paragraphs if len(p) < 60)
        result.short_para_ratio = round(short / len(paragraphs), 2)

        # 句长（粗略：按句号分割）
        all_sentences = []
        for p in paragraphs:
            sents = re.split(r"[。！？]", p)
            all_sentences.extend(s for s in sents if len(s) > 5)
        if all_sentences:
            result.avg_sentence_chars = round(sum(len(s) for s in all_sentences) / len(all_sentences), 1)

    return result


# ═══════════════════════════════════════════════════════════════
# 批量扫描
# ═══════════════════════════════════════════════════════════════


class BatchScanner:
    """批量扫描研报目录，生成统计基线。"""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(__file__), "..", "data", "投行估值数据加模板加分析方法！ 100家上市")
        self.base = Path(base_dir)

    def scan_all(self) -> list[ReportScan]:
        """扫描所有研报类文件。"""
        results = []

        scan_dirs = [
            ("行业研究", self.base / "估值" / "行业研究报告"),
            ("研究报告", self.base / "估值" / "研究报告"),
        ]

        for category, directory in scan_dirs:
            if not directory.exists():
                logger.warning(f"目录不存在: {directory}")
                continue
            for f in sorted(directory.rglob("*")):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in (".pdf", ".docx"):
                    continue
                text = extract_text(f)
                if len(text) < 200:
                    continue
                scan = scan_report(text, file_name=f.name, category=category)
                results.append(scan)
                if len(results) % 20 == 0:
                    logger.info(f"Scanned {len(results)} reports...")

        return results

    def compute_stats(self, results: list[ReportScan]) -> dict:
        """计算全量统计。"""
        stats = {}
        categories = set(r.category for r in results)

        for cat in sorted(categories):
            cat_results = [r for r in results if r.category == cat and r.char_count > 200]
            if not cat_results:
                continue

            stats[cat] = {
                "count": len(cat_results),
                "avg_chars": round(sum(r.char_count for r in cat_results) / len(cat_results), 0),
                "avg_p0": round(sum(r.total_p0 for r in cat_results) / len(cat_results), 2),
                "avg_judgment_density": round(sum(r.judgment_density for r in cat_results) / len(cat_results), 2),
                "avg_counter_density": round(sum(r.counter_density for r in cat_results) / len(cat_results), 2),
                "avg_experience_refs": round(sum(r.experience_refs for r in cat_results) / len(cat_results), 2),
                "avg_uncertainty": round(sum(r.uncertainty_hits for r in cat_results) / len(cat_results), 2),
                "avg_data_quality": round(sum(r.data_quality_hits for r in cat_results) / len(cat_results), 2),
                "avg_sentence_chars": round(
                    sum(r.avg_sentence_chars for r in cat_results if r.avg_sentence_chars > 0)
                    / max(1, sum(1 for r in cat_results if r.avg_sentence_chars > 0)),
                    1,
                ),
                "p0_zero_ratio": round(sum(1 for r in cat_results if r.total_p0 == 0) / len(cat_results), 2),
                "counter_consensus_gt2_ratio": round(
                    sum(1 for r in cat_results if r.counter_consensus_count >= 2) / len(cat_results), 2
                ),
            }

        # 全量
        all_valid = [r for r in results if r.char_count > 200]
        if all_valid:
            stats["all"] = {
                "count": len(all_valid),
                "avg_chars": round(sum(r.char_count for r in all_valid) / len(all_valid), 0),
                "avg_p0": round(sum(r.total_p0 for r in all_valid) / len(all_valid), 2),
                "p0_zero_ratio": round(sum(1 for r in all_valid if r.total_p0 == 0) / len(all_valid), 2),
                "avg_judgment_density": round(sum(r.judgment_density for r in all_valid) / len(all_valid), 2),
                "avg_counter_density": round(sum(r.counter_density for r in all_valid) / len(all_valid), 2),
                "avg_experience_refs": round(sum(r.experience_refs for r in all_valid) / len(all_valid), 2),
                "avg_uncertainty": round(sum(r.uncertainty_hits for r in all_valid) / len(all_valid), 2),
                "avg_data_quality": round(sum(r.data_quality_hits for r in all_valid) / len(all_valid), 2),
                "avg_sentence_chars": round(
                    sum(r.avg_sentence_chars for r in all_valid if r.avg_sentence_chars > 0)
                    / max(1, sum(1 for r in all_valid if r.avg_sentence_chars > 0)),
                    1,
                ),
                "short_para_ratio": round(sum(r.short_para_ratio for r in all_valid) / len(all_valid), 2),
            }

        return stats

    def export_csv(self, results: list[ReportScan], path: str):
        """导出为 CSV。"""
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "file",
                    "category",
                    "chars",
                    "p0_hits",
                    "judgment_density",
                    "counter_density",
                    "experience_refs",
                    "uncertainty_hits",
                    "data_quality_hits",
                    "avg_sentence_chars",
                    "short_para_ratio",
                ]
            )
            for r in results:
                if r.char_count < 200:
                    continue
                writer.writerow(
                    [
                        r.file_name,
                        r.category,
                        r.char_count,
                        r.total_p0,
                        r.judgment_density,
                        r.counter_density,
                        r.experience_refs,
                        r.uncertainty_hits,
                        r.data_quality_hits,
                        r.avg_sentence_chars,
                        r.short_para_ratio,
                    ]
                )

    def export_stats(self, stats: dict, path: str):
        """导出统计 baseline JSON。"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════


def run_scan(output_dir: str = "benchmark") -> dict:
    """运行全量扫描管线。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    scanner = BatchScanner()
    results = scanner.scan_all()

    csv_path = out / "report_baseline.csv"
    scanner.export_csv(results, str(csv_path))
    logger.info(f"CSV exported: {csv_path}")

    stats = scanner.compute_stats(results)
    json_path = out / "report_baseline_stats.json"
    scanner.export_stats(stats, str(json_path))
    logger.info(f"Stats exported: {json_path}")

    return stats
