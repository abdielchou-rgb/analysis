"""宏观方法论PDF正文提取器

解析 data/基线/【15】宏观分析框架和策略方法论/ 下的PDF,
提取每份的方法论核心(测算模型/分析步骤/关键指标/框架结构),
存为 data/methodology_frameworks_detailed.json

2026-08-10 v2: MinerU 增强——文本提取优先走 MinerU（core/mineru_parser，扫描版/
              复杂版面），回退 pdfplumber。目录失效时回退 ifind研报。
              支持 --dir / --mineru 开关。Markdown 语法剥离后喂现有正则。
"""

import argparse
import json
import re
from pathlib import Path

import pdfplumber

_ROOT = Path(__file__).resolve().parent.parent
METHODOLOGY_DIR = _ROOT / "data" / "基线" / "【15】宏观分析框架和策略方法论"
DEFAULT_FALLBACK_DIR = _ROOT / "data" / "基线" / "原始文档" / "ifind研报"
OUTPUT = _ROOT / "data" / "methodology_frameworks_detailed.json"

# 剥离 Markdown 语法符号（与 baseline_pdf_extractor 同款），供正则命中
_MARKDOWN_SYMBOLS = re.compile(r"[#>*`~\[\]()|!\-]", re.IGNORECASE)


def _strip_markdown(md: str) -> str:
    return _MARKDOWN_SYMBOLS.sub(" ", md)


def extract_pdf_text(pdf_path: str, max_pages: int = 8, use_mineru: bool = True) -> str:
    """提取PDF前N页文本。MinerU 优先（扫描版/复杂版面），回退 pdfplumber。

    注意：MinerU 云单份约 70s，适合单份高价值文档；批量用 use_mineru=False。
    """
    if use_mineru:
        try:
            from core.mineru_parser import extract_markdown

            page_range = f"1-{min(max_pages, 20)}"
            md = extract_markdown(str(pdf_path), mode="auto", page_range=page_range)
            return _strip_markdown(md)
        except Exception as e:
            print(f"  [mineru] {Path(pdf_path).name}: {e} → 回退 pdfplumber")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for i in range(min(max_pages, len(pdf.pages))):
                page_text = pdf.pages[i].extract_text() or ""
                text += page_text + "\n"
            return text
    except Exception as e:
        return f"ERROR: {e}"


def detect_topic(name: str) -> str:
    """从文件名检测方法论主题"""
    if (
        "宏观" in name
        or "GDP" in name
        or "CPI" in name
        or "PPI" in name
        or "PMI" in name
        or "投资" in name
        or "货币" in name
    ):
        return "macro"
    elif "产业生命周期" in name:
        return "industry_lifecycle"
    elif "商业模式" in name or "勇者" in name or "能者" in name or "谋者" in name or "智者" in name:
        return "business_model"
    elif "授人以渔" in name or "策略" in name:
        return "strategy"
    elif "信号" in name or "噪声" in name:
        return "signal_noise"
    return "other"


def extract_methodology(text: str) -> dict:
    """从PDF文本提取方法论核心"""
    result = {}

    # 摘要
    summary_match = re.search(r"摘要[：:]\s*(.*?)(?=\n目录|\n目\s*录|\n[一二三四五六七八九十]、|\Z)", text, re.DOTALL)
    if summary_match:
        result["summary"] = summary_match.group(1).strip()[:600]

    # 核心方法关键词
    methods = []
    for kw in [
        "构建.*指数",
        "三因素框架",
        "测算模型",
        "高频指标",
        "预测模型",
        "分析框架",
        "领先指标",
        "同步指标",
        "滞后指标",
    ]:
        if re.search(kw, text):
            methods.append(kw)
    if methods:
        result["methods"] = methods

    # 关键指标
    indicators = []
    for ind in [
        "工业增加值",
        "工业企业利润",
        "固定资产投资",
        "社会消费品零售",
        "出口",
        "CPI",
        "PPI",
        "PMI",
        "M1",
        "M2",
        "社融",
        "信贷",
        "GDP",
        "失业率",
        "库存",
        "产能利用率",
    ]:
        if ind in text:
            indicators.append(ind)
    if indicators:
        result["indicators"] = indicators

    return result


def process_all(search_dir: str = None, use_mineru: bool = False) -> dict:
    """处理全部方法论PDF。

    search_dir: 覆盖扫描目录。默认 METHODOLOGY_DIR，不存在则回退 DEFAULT_FALLBACK_DIR。
    use_mineru: 是否优先走 MinerU（默认 False——批量用 pdfplumber 秒级）。
    """
    base = Path(search_dir) if search_dir else METHODOLOGY_DIR
    if not base.exists():
        if search_dir:
            return {"error": f"{base} not found"}
        base = DEFAULT_FALLBACK_DIR
        if not base.exists():
            return {"error": f"{METHODOLOGY_DIR} 与 {DEFAULT_FALLBACK_DIR} 均不存在"}
    pdfs = list(base.rglob("*.pdf"))
    frameworks = {}
    stats = {"total": len(pdfs), "parsed": 0, "skipped_error": 0, "skipped_empty": 0, "search_dir": str(base)}

    for pdf in pdfs:
        topic = detect_topic(pdf.stem)
        text = extract_pdf_text(str(pdf), use_mineru=use_mineru)
        if text.startswith("ERROR"):
            stats["skipped_error"] += 1
            continue

        meth = extract_methodology(text)
        if not meth:
            stats["skipped_empty"] += 1
            continue

        entry = {
            "file": pdf.name,
            "topic": topic,
            "title": pdf.stem[:60],
        }
        entry.update(meth)

        if topic not in frameworks:
            frameworks[topic] = []
        frameworks[topic].append(entry)
        stats["parsed"] += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(frameworks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] parsed {stats['parsed']}/{stats['total']} PDFs -> {len(frameworks)} topics")
    return frameworks


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="宏观方法论PDF提取器（MinerU 增强）")
    ap.add_argument("--dir", default=None, help="扫描目录（默认方法论目录，缺失则回退 ifind研报）")
    ap.add_argument(
        "--mineru",
        action="store_true",
        help="启用 MinerU 提取（默认 pdfplumber；MinerU 云单份~70s，仅少量高价值文档用）",
    )
    args = ap.parse_args()
    frameworks = process_all(search_dir=args.dir, use_mineru=args.mineru)
    if isinstance(frameworks, dict) and "error" in frameworks:
        print(frameworks["error"])
        raise SystemExit(1)
    print(f"方法论框架: {len(frameworks)} 类")
    for topic, items in frameworks.items():
        print(f"  {topic}: {len(items)} 份")
        for item in items[:2]:
            print(f"    方法: {item.get('methods', [])[:3]}")
            print(f"    指标: {item.get('indicators', [])[:5]}")
