"""研报提取器 — 从券商研报PDF提取行业基线+一致预期

从 assets/reports/券商报告/ 提取:
  1. 行业规模/增速 → data/industry_baselines.json
  2. 目标价/评级 → data/consensus_prices.json
  3. 关键判断/催化剂 → data/industry_drivers.json

供数据驱动注入使用。
"""

import pdfplumber, json, re, os
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = _ROOT / "assets" / "reports" / "券商报告"
BASELINES_OUT = _ROOT / "data" / "industry_baselines.json"
CONSENSUS_OUT = _ROOT / "data" / "consensus_prices.json"
DRIVERS_OUT = _ROOT / "data" / "industry_drivers.json"

# 行业关键词 → 行业名
INDUSTRY_KEYWORDS = {
    "半导体": ["半导体", "晶圆", "芯片", "制程", "存储", "MLCC", "CPU", "GPU"],
    "AI/算力": ["AI", "人工智能", "算力", "服务器", "数据中心", "AIDC", "大模型"],
    "新能源": ["新能源", "锂电", "电池", "光伏", "储能", "风电"],
    "汽车": ["汽车", "新能源车", "智驾", "具身智能", "机器人"],
    "消费": ["消费", "零售", "食品", "白酒", "啤酒", "免税"],
    "医药": ["医药", "CRO", "CDMO", "创新药", "医疗"],
    "金融": ["银行", "券商", "保险", "基金", "支付"],
    "科技": ["科技", "互联网", "软件", "通信", "电子", "光模块"],
    "工业": ["工业", "制造", "机械", "电力", "化工", "有色"],
}

# 评级关键词 → 标准评级
RATING_KEYWORDS = {
    "买入": "买入",
    "增持": "增持",
    "推荐": "增持",
    "优于大市": "增持",
    "强烈推荐": "买入",
    "跑赢行业": "增持",
    "中性": "中性",
    "持有": "中性",
    "减持": "减持",
    "卖出": "卖出",
}


def detect_industry(filename: str, text: str = "") -> str:
    """从文件名+文本检测行业"""
    combined = filename + " " + text[:500]
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(k in combined for k in keywords):
            return industry
    return "其他"


def extract_text(pdf_path: str, max_pages: int = 10) -> str:
    """提取PDF文本(最多前N页)"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for i in range(min(max_pages, len(pdf.pages))):
                page_text = pdf.pages[i].extract_text() or ""
                text += page_text + "\n"
            return text[:8000]
    except Exception as e:
        return f"ERROR: {e}"


def extract_market_size(text: str) -> Optional[dict]:
    """提取行业市场规模/增速"""
    result = {}
    # 模式: XX市场规模达到X亿元/万亿美元, 同比增长X%
    patterns = [
        (r'市场规模[^。]*?(\d+\.?\d*)\s*[亿元万亿万美元]', 'market_size'),
        (r'行业规模[^。]*?(\d+\.?\d*)\s*[亿元万亿万美元]', 'market_size'),
        (r'市场空间[^。]*?(\d+\.?\d*)\s*[亿元万亿万美元]', 'market_size'),
        (r'(?:同比|年增|增速)[^。]*?(\d+\.?\d*)\s*%', 'growth'),
        (r'(\d+\.?\d*)\s*%\s*的[^。]*?(?:年|复合)[^。]*?增速', 'cagr'),
    ]
    for pat, key in patterns:
        m = re.search(pat, text)
        if m and key not in result:
            try:
                result[key] = float(m.group(1))
            except Exception:
                pass
    return result if result else None


def extract_rating_target(text: str) -> Optional[dict]:
    """提取目标价/评级"""
    result = {}
    # 目标价
    target_match = re.search(r'目标价[：: ]*(\d+\.?\d*)', text)
    if target_match:
        result['target_price'] = float(target_match.group(1))
    # 评级
    for kw, rating in RATING_KEYWORDS.items():
        if kw in text:
            result['rating'] = rating
            break
    return result if result else None


def extract_key_drivers(text: str) -> list:
    """提取关键驱动/催化剂"""
    drivers = []
    # 模式: 行业关键词+判断
    sentences = re.split(r'[。\n]', text)
    for s in sentences:
        if any(kw in s for kw in ['受益', '驱动', '催化', '增长', '爆发', '渗透', '需求']):
            if len(s) > 20 and len(s) < 120:
                drivers.append(s.strip()[:100])
    return drivers[:5]


def process_report(pdf_path: str) -> dict:
    """处理单个研报"""
    filename = Path(pdf_path).name
    text = extract_text(pdf_path)
    if text.startswith("ERROR"):
        return {"file": filename, "error": text[:50]}
    
    result = {
        "file": filename,
        "industry": detect_industry(filename, text),
    }
    
    mkt = extract_market_size(text)
    if mkt:
        result["market"] = mkt
    
    rt = extract_rating_target(text)
    if rt:
        result["consensus"] = rt
    
    drivers = extract_key_drivers(text)
    if drivers:
        result["drivers"] = drivers
    
    return result


def process_all() -> dict:
    """处理全部研报"""
    if not REPORT_DIR.exists():
        return {"error": f"{REPORT_DIR} not found"}
    
    pdfs = list(REPORT_DIR.glob("*.pdf"))
    baselines = {}   # industry → {market_size, growth, drivers}
    consensus = {}   # company/file → {target_price, rating}
    drivers = {}     # industry → [drivers]
    
    for idx, pdf in enumerate(pdfs):
        r = process_report(str(pdf))
        if "error" in r:
            continue
        
        # 每5份增量保存一次(避免超时丢失)
        if idx % 5 == 0:
            for data, path in [
                (baselines, BASELINES_OUT),
                (consensus, CONSENSUS_OUT),
                (drivers, DRIVERS_OUT),
            ]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        industry = r.get("industry", "其他")
        
        # 行业基线
        if "market" in r:
            if industry not in baselines:
                baselines[industry] = {}
            baselines[industry].update(r["market"])
        
        # 一致预期
        if "consensus" in r:
            consensus[r["file"]] = r["consensus"]
        
        # 行业驱动
        if "drivers" in r:
            if industry not in drivers:
                drivers[industry] = []
            drivers[industry].extend(r["drivers"])
    
    # 保存
    for data, path in [
        (baselines, BASELINES_OUT),
        (consensus, CONSENSUS_OUT),
        (drivers, DRIVERS_OUT),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "reports_processed": len(pdfs),
        "industries": len(baselines),
        "consensus_count": len(consensus),
    }


if __name__ == "__main__":
    result = process_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 显示样例
    if BASELINES_OUT.exists():
        data = json.loads(BASELINES_OUT.read_text(encoding="utf-8"))
        for industry, mkt in list(data.items())[:8]:
            print(f"  {industry}: {mkt}")
