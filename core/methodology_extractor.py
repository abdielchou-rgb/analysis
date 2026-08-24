"""方法论提取器 — 从基线库提取机构方法论

从 data/基线/ 提取:
  1. 回测基线库机构报告(BCG/CICC/GS/MS) → 机构风格指纹
  2. 宏观方法论PDF → 分析方法论
  3. 估值模型 → DCF参数(扩充valuation_params)

输出:
  data/methodology_styles.json  — 机构风格指纹
  data/methodology_frameworks.json — 分析方法论
"""

import json, re, os, glob
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = _ROOT / "data" / "基线"
STYLES_OUT = _ROOT / "data" / "methodology_styles.json"
FRAMEWORKS_OUT = _ROOT / "data" / "methodology_frameworks.json"


def extract_style_from_md(md_path: str) -> dict:
    """从机构报告md提取风格指纹"""
    try:
        content = Path(md_path).read_text(encoding='utf-8')
    except Exception:
        return {}
    
    # 识别机构
    inst = "unknown"
    lower = md_path.lower()
    if 'bcg' in lower: inst = 'bcg'
    elif 'cicc' in lower: inst = 'cicc'
    elif 'goldman' in lower or 'gs_' in lower: inst = 'goldman_sachs'
    elif 'morgan' in lower or 'ms_' in lower: inst = 'morgan_stanley'
    
    # 提取KEY POSITIONING / FRAMEWORK / VALUATION / SCENARIOS / SECTOR / FINDINGS
    sections = {}
    # BCG用KEY FINDINGS/INVESTMENT TRENDS, GS/MS用KEY POSITIONING/FRAMEWORK, CICC用核心观点
    patterns = {
        'key_findings': r'(?:KEY FINDINGS|核心观点|要点)[:：]?\s*\n?(.*?)(?=\n(?:##|## |[A-Z]{2,}:)|\Z)',
        'key_positioning': r'(?:KEY POSITIONING|投资定位)[:：]?\s*\n?(.*?)(?=\n(?:##|## |[A-Z]{2,}:)|\Z)',
        'framework': r'(?:KEY FRAMEWORK|分析框架|投资框架)[:：]?\s*\n?(.*?)(?=\n(?:##|## |[A-Z]{2,}:)|\Z)',
        'valuation': r'(?:VALUATION|估值)[:：]?\s*\n?(.*?)(?=\n(?:##|## |[A-Z]{2,}:)|\Z)',
        'scenarios': r'(?:SCENARIOS|情景)[:：]?\s*\n?(.*?)(?=\n(?:##|## |[A-Z]{2,}:)|\Z)',
        'sector_preference': r'(?:SECTOR PREFERENCE|行业配置)[:：]?\s*\n?(.*?)(?=\n(?:##|## |[A-Z]{2,}:)|\Z)',
        'core_thesis': r'(?:CORE THESIS|核心判断|核心逻辑)[:：]?\s*\n?(.*?)(?=\n(?:##|## |[A-Z]{2,}:)|\Z)',
        'investment_trends': r'(?:INVESTMENT TRENDS|投资趋势)[:：]?\s*\n?(.*?)(?=\n(?:##|## |[A-Z]{2,}:)|\Z)',
    }
    for key, pat in patterns.items():
        m = re.search(pat, content, re.DOTALL | re.IGNORECASE)
        if m:
            sections[key] = m.group(1).strip()[:500]
    
    return {
        "institution": inst,
        "file": Path(md_path).name,
        "sections": sections,
    }


def extract_styles() -> dict:
    """提取所有机构风格指纹"""
    styles = {}
    md_files = list(BASELINE_DIR.rglob('*.md')) if BASELINE_DIR.exists() else []
    for md in md_files:
        if '回测基线' not in str(md):
            continue
        style = extract_style_from_md(str(md))
        if style.get('sections'):
            inst = style['institution']
            if inst not in styles:
                styles[inst] = []
            styles[inst].append(style)
    return styles


def extract_frameworks() -> dict:
    """从宏观方法论PDF文件名提取方法论框架"""
    frameworks = {}
    if not BASELINE_DIR.exists():
        return {}
    
    macro_dir = BASELINE_DIR / "【15】宏观分析框架和策略方法论"
    if not macro_dir.exists():
        return {}
    
    for pdf in macro_dir.rglob('*.pdf'):
        name = pdf.stem
        # 识别主题
        if '宏观' in name:
            topic = 'macro'
        elif '产业生命周期' in name:
            topic = 'industry_lifecycle'
        elif '授人以渔' in name or '策略' in name:
            topic = 'strategy'
        elif '商业模式' in name or '勇者' in name or '能者' in name or '谋者' in name or '智者' in name:
            topic = 'business_model'
        elif '信号' in name or '噪声' in name:
            topic = 'signal_noise'
        else:
            topic = 'other'
        
        if topic not in frameworks:
            frameworks[topic] = []
        frameworks[topic].append({
            "file": pdf.name,
            "title": name[:80],
        })
    
    return frameworks


def save():
    styles = extract_styles()
    frameworks = extract_frameworks()
    
    STYLES_OUT.parent.mkdir(parents=True, exist_ok=True)
    STYLES_OUT.write_text(json.dumps(styles, ensure_ascii=False, indent=2), encoding='utf-8')
    FRAMEWORKS_OUT.write_text(json.dumps(frameworks, ensure_ascii=False, indent=2), encoding='utf-8')
    
    return styles, frameworks


if __name__ == "__main__":
    styles, frameworks = save()
    print(f"机构风格: {len(styles)} 家机构")
    for inst, files in styles.items():
        print(f"  {inst}: {len(files)} 份报告")
    print(f"\n方法论框架: {len(frameworks)} 类")
    for topic, files in frameworks.items():
        print(f"  {topic}: {len(files)} 份")
