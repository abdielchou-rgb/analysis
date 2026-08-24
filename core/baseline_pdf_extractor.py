"""回测基线PDF提取器 — 从机构报告PDF提取核心判断/评级/目标价/行业规模

解析 data/基线/回测基线库/ 下的PDF（1阶段机构目录 + 2阶段金牌散装），
按目录或文件名识别机构，提取核心判断/评级/估值逻辑/行业规模，
存为 data/baseline_findings.json

2026-07-31 v2: 修复机构识别（目录优先+文件名解析），覆盖 2阶段金牌散装库
2026-08-10 v3: MinerU 增强——文本提取优先走 MinerU（core/mineru_parser，支持扫描版/
              复杂版面），不可用时回退 pdfplumber。支持 --dir 覆盖扫描目录。
              Markdown 语法符号剥离后喂给现有正则，输出 schema 不变。
"""

import pdfplumber, json, re, argparse
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = _ROOT / "data" / "基线" / "回测基线库"
DEFAULT_FALLBACK_DIR = _ROOT / "data" / "基线" / "原始文档" / "ifind研报"
OUTPUT = _ROOT / "data" / "baseline_findings.json"

# 目录名 → 机构ID（1阶段机构目录）
_DIR_INSTITUTIONS = {
    "bcg": "bcg",
    "cicc": "cicc",
    "citic": "citic",
    "goldman_sachs": "goldman_sachs",
    "gs": "goldman_sachs",
    "mckinsey": "mckinsey",
    "morgan_stanley": "morgan_stanley",
    "ms": "morgan_stanley",
    "academic": "academic",
    "A级": "A级",
    "S级": "S级",
    "金牌": "gold",
    "中金": "cicc",
    "中信": "citic",
}

# 文件名关键词 → 机构ID（2阶段散装研报，文件名形如 "20240117-联储证券-14页.pdf"）
_FILE_INSTITUTIONS = [
    ("中金", "cicc"), ("中信", "citic"), ("华泰", "huatai"), ("国泰君安", "gtja"),
    ("申万宏源", "swhy"), ("海通", "haitong"), ("招商", "cms"), ("广发", "gf"),
    ("兴业", "xy"), ("东方", "orient"), ("长江", "cj"), ("天风", "tf"),
    ("浙商", "zs"), ("华西", "hx"), ("华鑫", "hx2"), ("联储", "ls"),
    ("国信", "gx"), ("民生", "ms2"), ("光大", "ebscn"), ("平安", "pa"),
    ("国盛", "gs2"), ("德邦", "db"), ("东吴", "dw"), ("东北", "db2"),
    ("东莞", "dg"), ("信达", "xd"), ("开源", "ky"), ("中泰", "zt"),
    ("中银", "boc"), ("银河", "yh"), ("国海", "gh"), ("中邮", "zy"),
    ("华创", "hc"), ("国投", "gt"), ("国联", "gl"), ("华福", "hf"),
    ("万联", "wl"), ("西部", "xb"), ("长城", "cc"), ("财通", "ct"),
    ("西南", "xn"), ("方正", "fz"), ("太平洋", "tpy"), ("首创", "sc"),
    ("中原", "zy2"), ("红塔", "ht"), ("山西", "sx"), ("东莞", "dg2"),
    ("第一创业", "dyc"), ("东亚前海", "dyqh"), ("上海证券", "shzq"),
    ("联储", "ls"), ("国新", "gxzq"), ("大和", "dwzq"), ("高盛", "goldman_sachs"),
    ("摩根", "morgan_stanley"), ("美林", "ml"), ("沙利文", "f&s"),
    ("鸟语花香", "pawpaw"), ("野村", "nomura"), ("瑞银", "ubs"),
    ("伯恩斯坦", "bernstein"), ("杰富瑞", "jefferies"), ("巴克莱", "barclays"),
]


_MARKDOWN_SYMBOLS = re.compile(r"[#>*`~\[\]()|!\-]", re.IGNORECASE)


def _strip_markdown(md: str) -> str:
    """MinerU 输出是 Markdown，剥离语法符号使现有正则（目标价/评级等）能命中。"""
    return _MARKDOWN_SYMBOLS.sub(" ", md)


def extract_text(pdf_path: str, max_pages: int = 5, use_mineru: bool = True) -> str:
    """提取PDF前N页文本。MinerU 优先（扫描版/复杂版面），回退 pdfplumber。

    注意：MinerU 云 API 单份约 70s（上传+排队），适合单份高价值文档；
    全量批量（如 2651 份基线库）应 use_mineru=False 走 pdfplumber（本地秒级）。
    """
    # 1) MinerU 优先（可选，默认开）
    if use_mineru:
        try:
            from core.mineru_parser import extract_markdown
            # 云 flash 限 20 页；max_pages<=20 直接传，否则截前 20 页
            page_range = f"1-{min(max_pages, 20)}"
            md = extract_markdown(str(pdf_path), mode="auto", page_range=page_range)
            return _strip_markdown(md)
        except Exception as e:
            # 不静默——记录后回退 pdfplumber
            print(f"  [mineru] {Path(pdf_path).name}: {e} → 回退 pdfplumber")
    # 2) 回退 pdfplumber（纯文本层）
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for i in range(min(max_pages, len(pdf.pages))):
                page_text = pdf.pages[i].extract_text() or ""
                text += page_text + "\n"
            return text
    except Exception as e:
        return f"ERROR: {e}"


def detect_institution(path: str) -> str:
    """优先从目录名识别（1阶段机构目录），再从文件名识别（2阶段散装）。"""
    p = Path(path)
    parts = p.parts
    # 1. 目录识别：路径中任一父目录匹配
    for part in parts:
        if part in _DIR_INSTITUTIONS:
            return _DIR_INSTITUTIONS[part]
    # 2. 文件名识别：匹配关键词
    fname = p.name
    for kw, inst in _FILE_INSTITUTIONS:
        if kw in fname:
            return inst
    return "unknown"


def extract_findings(text: str) -> dict:
    """提取核心判断/评级/目标价/行业规模"""
    result = {}
    # 行业评级
    rating = re.search(r"(?:行业评级|投资评级|评级)[：:]\s*([^\n]+)", text)
    if rating:
        result["rating"] = rating.group(1).strip()[:30]
    # 买入/卖出评级
    buy_sell = re.search(r"(?:买入|增持|强烈推荐|推荐|中性|减持|卖出|持有)\s*[-—]\s*[^。\n]{0,30}", text)
    if buy_sell and "rating" not in result:
        result["rating"] = buy_sell.group(0).strip()[:30]
    # 目标价
    tp = re.search(r"目标价[^。\n]{0,30}?(\d+\.?\d*)\s*元", text)
    if tp:
        result["target_price"] = tp.group(1)
    tp2 = re.search(r"目标价[：:]\s*(\d+\.?\d*)", text)
    if tp2:
        result["target_price"] = tp2.group(1)
    # 分析师
    analysts = re.findall(r"分析师\s+(\S+)", text)
    if analysts:
        result["analysts"] = analysts[:3]
    # 核心判断(摘要部分)
    summary = re.search(r"摘要[:：]\s*(.*?)(?=\n\s*\n|\Z)", text, re.DOTALL)
    if summary:
        result["summary"] = summary.group(1).strip()[:600]
    # 行业规模
    size = re.search(r"市场规模[^。]*?(\d+\.?\d*)\s*[亿元万亿]美元", text)
    if size:
        result["market_size"] = size.group(0)[:50]
    size2 = re.search(r"市场规模[^。]*?(\d+\.?\d*)\s*亿元", text)
    if size2:
        result["market_size"] = size2.group(0)[:50]
    # 预计/预测
    forecast = re.findall(r"(?:预计|预期|我们预计)[^。]{0,60}", text)
    if forecast:
        result["forecasts"] = [f.strip()[:80] for f in forecast[:3]]
    # 股票代码
    code = re.search(r"(\d{6})", text)
    if code:
        result["ticker"] = code.group(1)
    return result


def _classify_level(pdf_path: Path) -> str:
    """从目录判断等级：A级/S级/金牌/academic"""
    parts = pdf_path.parts
    if "A级" in parts:
        return "A级"
    if "S级" in parts:
        return "S级"
    if "金牌" in parts:
        return "gold"
    if "academic" in parts:
        return "academic"
    return "unknown"


def process_all(search_dir: str = None, use_mineru: bool = False) -> dict:
    """遍历 1阶段 机构目录 + 2阶段 金牌散装库，提取并入库。

    search_dir: 覆盖扫描目录。默认 BASELINE_DIR，不存在则回退 DEFAULT_FALLBACK_DIR。
    use_mineru: 是否优先走 MinerU 提取（默认 False——批量用 pdfplumber 秒级；
                单份高价值文档可单独用 extract_text(use_mineru=True)）。
    """
    base = Path(search_dir) if search_dir else BASELINE_DIR
    if not base.exists():
        if search_dir:
            return {"error": f"{base} not found"}
        base = DEFAULT_FALLBACK_DIR  # 基线目录重排后的真实研报库
        if not base.exists():
            return {"error": f"{BASELINE_DIR} 与 {DEFAULT_FALLBACK_DIR} 均不存在"}
    pdfs = sorted(base.rglob("*.pdf"))
    findings = {}
    stats = {"total": len(pdfs), "parsed": 0, "skipped_error": 0, "skipped_empty": 0,
             "mineru_fallback": 0, "search_dir": str(base)}
    for pdf in pdfs:
        inst = detect_institution(str(pdf))
        text = extract_text(str(pdf), use_mineru=use_mineru)
        if text.startswith("ERROR"):
            stats["skipped_error"] += 1
            continue
        data = extract_findings(text)
        if not data:
            stats["skipped_empty"] += 1
            continue
        data["file"] = pdf.name
        data["level"] = _classify_level(pdf)
        data["institution"] = inst
        findings.setdefault(inst, []).append(data)
        stats["parsed"] += 1
        # 日志（调试用，生产可关）
        if stats["parsed"] % 200 == 0:
            print(f"  ... parsed {stats['parsed']}/{len(pdfs)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # 附加统计信息
    out = {"_meta": {"stats": stats, "generated": __import__("datetime").datetime.now().isoformat()},
           "findings": findings}
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] parsed {stats['parsed']}/{stats['total']} PDFs -> {len(findings)} institutions")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="回测基线PDF提取器（MinerU 增强）")
    ap.add_argument("--dir", default=None, help="扫描目录（默认回测基线库，缺失则回退 ifind研报）")
    ap.add_argument("--mineru", action="store_true", help="启用 MinerU 提取（默认 pdfplumber；MinerU 云单份~70s，仅少量高价值文档用）")
    args = ap.parse_args()
    result = process_all(search_dir=args.dir, use_mineru=args.mineru)
    stats = result.get("_meta", {}).get("stats", {})
    print(f"机构/等级: {len(result.get('findings', {}))} 类")
    for inst, items in result.get("findings", {}).items():
        print(f"  {inst}: {len(items)}份")
        for item in items[:1]:
            if item.get("rating"):
                print(f"    评级: {item['rating']}")
            if item.get("summary"):
                print(f"    核心: {item['summary'][:80]}...")
