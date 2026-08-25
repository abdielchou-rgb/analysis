#!/usr/bin/env python3
"""2hao-analyst 招股书提取器 — 从招股说明书 PDF 提取非上市公司核心数据

从 D:\\Claude\\1hao-analyst-v51\\data\\深度研究报告原始文档\\招股说明书 提取：
  公司简介 / 行业 / 营收净利趋势 / 毛利率 / 股权结构
存为 data/prospectus_findings.json，供非上市公司报告使用。

用法:
    python scripts/extract_prospectus.py                # 全量提取
    python scripts/extract_prospectus.py "宇树科技"      # 单份
    python scripts/extract_prospectus.py --status        # 查看已提取
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import pdfplumber

_ROOT = Path(__file__).resolve().parent.parent
# 招股书源目录（用户挂载的 1hao 项目）
PROSPECTUS_DIR = Path(r"D:\Claude\1hao-analyst-v51\data\深度研究报告原始文档\招股说明书")
# 输出到 2hao 数据层
OUTPUT = _ROOT / "data" / "prospectus_findings.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("prospectus")


def extract_text(pdf_path: Path, max_pages: int = 60) -> str:
    """提取招股书前 N 页文本（核心数据在概览/摘要部分）"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for i in range(min(max_pages, len(pdf.pages))):
                page_text = pdf.pages[i].extract_text() or ""
                text += page_text + "\n"
            return text
    except Exception as e:
        logger.warning("提取失败 %s: %s", pdf_path.name, e)
        return ""


def extract_company_profile(text: str) -> dict:
    """提取公司核心信息"""
    result = {}
    # 公司简介（通常"是一家...公司，专注于..."）
    intro = re.search(r"(?:本公司|发行人|公司)(?:是一家|主要从事|专注于)[^。]{20,200}", text)
    if intro:
        result["intro"] = intro.group(0)[:300]
    # 行业
    industry = re.search(r"(?:所属行业|行业分类)[：:]\s*([^\n]+)", text)
    if industry:
        result["industry"] = industry.group(1).strip()[:50]
    # 主营
    main_biz = re.search(r"(?:主营业务|主营)[：:]\s*([^\n]+)", text)
    if main_biz:
        result["main_business"] = main_biz.group(1).strip()[:100]
    return result


def extract_financials(text: str) -> dict:
    """提取营收/净利趋势（多页扫描，年份→金额）"""
    result = {}
    # 营收趋势：年份 + 营业收入 + 金额
    rev_by_year = {}
    for m in re.finditer(
        r"(20\d{2})[年]?[^0-9]{0,25}(?:营业收入|营收)[^0-9]{0,20}(\d[\d,]*\.?\d*)\s*(亿元|万元|元)", text
    ):
        year, val, unit = m.group(1), m.group(2), m.group(3)
        rev_by_year.setdefault(year, []).append({"value": float(val.replace(",", "")), "unit": unit})
    # 也匹配 "营业收入 xx万元" 不带年份（取最近几年）
    if not rev_by_year:
        revs = re.findall(r"营业收入[^0-9]{0,10}(\d[\d,]*\.?\d*)\s*(亿元|万元|元)", text[:30000])
        if revs:
            result["revenues"] = [{"value": float(r[0].replace(",", "")), "unit": r[1]} for r in revs[:5]]
    else:
        result["revenues_by_year"] = {y: v[0] for y, v in sorted(rev_by_year.items())}

    # 净利趋势
    prof_by_year = {}
    for m in re.finditer(
        r"(20\d{2})[年]?[^0-9]{0,25}(?:净利润|归母净利润)[^0-9]{0,20}([-\d][\d,]*\.?\d*)\s*(亿元|万元|元)", text
    ):
        year, val, unit = m.group(1), m.group(2), m.group(3)
        prof_by_year.setdefault(year, []).append({"value": float(val.replace(",", "")), "unit": unit})
    if not prof_by_year:
        profits = re.findall(r"净利润[^0-9]{0,10}([-\d][\d,]*\.?\d*)\s*(亿元|万元|元)", text[:30000])
        if profits:
            result["profits"] = [{"value": float(p[0].replace(",", "")), "unit": p[1]} for p in profits[:5]]
    else:
        result["profits_by_year"] = {y: v[0] for y, v in sorted(prof_by_year.items())}
    return result


def extract_structure(text: str) -> dict:
    """提取股权/控股信息"""
    result = {}
    # 控股股东
    holder = re.search(r"(?:控股股东|实际控制人)[：:]?\s*([^\n]{2,30})", text)
    if holder:
        result["controlling_holder"] = holder.group(1).strip()[:30]
    # 持股比例
    pct = re.search(r"(?:实际控制人|控股股东)[^%]{0,50}?(\d+\.?\d*)%", text)
    if pct:
        result["holder_pct"] = pct.group(1) + "%"
    return result


def process_pdf(pdf_path: Path) -> dict:
    """处理单份招股书"""
    text = extract_text(pdf_path)
    if not text:
        return {"file": pdf_path.name, "status": "error"}

    data = {}
    data.update(extract_company_profile(text))
    data.update(extract_financials(text))
    data.update(extract_structure(text))
    data["file"] = pdf_path.name
    data["source_dir"] = pdf_path.parent.name
    data["status"] = "ok"
    return data


def process_all() -> dict:
    """处理所有招股书"""
    if not PROSPECTUS_DIR.exists():
        return {"error": f"{PROSPECTUS_DIR} 不存在"}
    pdfs = sorted(PROSPECTUS_DIR.rglob("*.pdf"))
    results = {}
    for pdf in pdfs:
        logger.info("处理 %s", pdf.name)
        data = process_pdf(pdf)
        if data.get("status") == "ok":
            key = pdf.stem.split("_")[0]  # 用文件名主名作 key
            results[key] = data
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("提取完成: %d/%d 份", len(results), len(pdfs))
    return results


def main():
    parser = argparse.ArgumentParser(description="招股书提取器")
    parser.add_argument("asset", nargs="?", help="公司名，如 宇树科技")
    parser.add_argument("--status", action="store_true", help="查看已提取")
    args = parser.parse_args()

    if args.status:
        if OUTPUT.exists():
            data = json.loads(OUTPUT.read_text(encoding="utf-8"))
            print(f"已提取 {len(data)} 份招股书")
            for k, v in data.items():
                print(f"  {k}: {v.get('industry', '?')} | {v.get('intro', '')[:40]}")
        else:
            print("尚未提取")
        return 0

    if args.asset:
        # 单份
        candidates = [p for p in PROSPECTUS_DIR.rglob("*.pdf") if args.asset in p.stem]
        if not candidates:
            print(f"未找到 {args.asset} 的招股书")
            return 1
        data = process_pdf(candidates[0])
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    process_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
