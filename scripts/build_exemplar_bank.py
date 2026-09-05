#!/usr/bin/env python
"""
Build exemplar bank from FinRpt data AND Golden corpus (converted PDF reports).

Maps FinRpt 9-task outputs + Golden corpus sections to SAC dimensions and creates a
diversity-aware retrieval index for section_writer prompts.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"D:\Claude\projects\2hao-analyst")
FINRPT = ROOT / "benchmark" / "external_datasets" / "FinRpt" / "FinRpt.jsonl"
GOLDEN = ROOT / "benchmark" / "golden"
OUT = ROOT / "benchmark" / "exemplar_bank"
OUT.mkdir(parents=True, exist_ok=True)

# ── SAC Dimension Mapping ─────────────────────────────────────
# FinRpt task → SAC dimension + section_writer target
TASK_MAP = {
    "income": {
        "sac_dim": "财务验证",
        "section": "利润表分析",
        "description": "基于三表数据的财务健康度判断",
    },
    "balance": {
        "sac_dim": "财务验证",
        "section": "资产负债表分析",
        "description": "资产结构、负债水平、偿债能力",
    },
    "cash": {
        "sac_dim": "财务验证",
        "section": "现金流量表分析",
        "description": "经营/投资/筹资现金流质量",
    },
    "finance_write": {
        "sac_dim": "财务验证",
        "section": "财务综述",
        "description": "三表综合判断，投资含义",
    },
    "report_write": {
        "sac_dim": "投资建议",
        "section": "投资建议报告",
        "description": "个股推荐、目标价、评级",
    },
    "trend_write": {
        "sac_dim": "催化剂/证伪",
        "section": "趋势分析",
        "description": "股价趋势、市场预期、催化剂",
    },
    "risk": {
        "sac_dim": "风险",
        "section": "风险提示",
        "description": "核心风险因素识别",
    },
    "news_write": {
        "sac_dim": "核心分歧",
        "section": "新闻综述",
        "description": "近期重要新闻及影响",
    },
    "news_anlyzer": {
        "sac_dim": "核心分歧",
        "section": "新闻分析",
        "description": "新闻事件对公司的潜在影响",
    },
}

# ── Golden Corpus Section → SAC Section Mapping ────────────────
# Loaded from JSON file to avoid encoding issues with Chinese in source
_GOLDEN_MAP_PATH = ROOT / "benchmark" / "golden_section_map.json"
GOLDEN_SECTION_MAP = {}
if _GOLDEN_MAP_PATH.exists():
    GOLDEN_SECTION_MAP = json.loads(_GOLDEN_MAP_PATH.read_text(encoding="utf-8"))

# ── Section Name Normalization ────────────────────────────────
# Maps SAC section name to canonical key for section_dir
SECTION_CANONICAL = {
    "利润表分析": "利润表分析",
    "资产负债表分析": "资产负债表分析",
    "现金流量表分析": "现金流量表分析",
    "财务综述": "财务综述",
    "投资建议报告": "投资建议报告",
    "趋势分析": "趋势分析",
    "风险提示": "风险提示",
    "新闻综述": "新闻综述",
    "新闻分析": "新闻分析",
}


# ── Sector Classification ─────────────────────────────────────
def classify_sector(stock_code: str) -> str:
    """Simple sector classification by stock code range."""
    code = stock_code.split(".")[0]
    return "unknown"


# ── Quality Scoring for FinRpt (Original) ──────────────────────
def compute_quality_score(record: dict) -> float:
    """Compute quality score for an exemplar based on:
    - Output length (longer = more detailed = better, up to a point)
    - Output structure (JSON with clear fields = better)
    - Input data completeness
    """
    score = 0.0

    for task in ["income", "balance", "cash", "finance_write", "report_write", "trend_write"]:
        out = record.get(f"{task}_response", "")
        inp = record.get(f"{task}_prompt", "")

        # Length score (sweet spot: 150-350 chars)
        out_len = len(out)
        if 150 <= out_len <= 350:
            score += 1.0
        elif 100 <= out_len < 150 or 350 < out_len <= 500:
            score += 0.5
        elif out_len > 50:
            score += 0.2

        # Structure score (JSON output = better)
        if out.strip().startswith("{"):
            try:
                json.loads(out)
                score += 0.5
            except json.JSONDecodeError:
                pass

        # Input completeness
        if len(inp) > 1000:
            score += 0.3

    # Risk task (short is fine)
    risk = record.get("risk_response", "")
    if risk.strip().startswith("{"):
        try:
            parsed = json.loads(risk)
            if isinstance(parsed, dict) and "risks" in parsed:
                risks = parsed["risks"]
                if 3 <= len(risks) <= 5:
                    score += 1.0
                elif len(risks) > 0:
                    score += 0.5
        except json.JSONDecodeError:
            pass

    return round(score, 2)


def build_exemplar(record: dict) -> dict:
    """Convert a FinRpt record into an exemplar entry."""
    stock = record["stock_code"]
    date = record["date"]
    quality = compute_quality_score(record)

    exemplar = {
        "id": f"{stock}_{date}",
        "stock_code": stock,
        "date": date,
        "sector": classify_sector(stock),
        "quality_score": quality,
        "sections": {},
    }

    for task_key, meta in TASK_MAP.items():
        out = record.get(f"{task_key}_response", "")
        inp = record.get(f"{task_key}_prompt", "")
        if not out.strip():
            continue

        # Parse output
        parsed_output = None
        try:
            parsed_output = json.loads(out)
        except (json.JSONDecodeError, ValueError):
            pass

        # Extract structured data from input
        input_data = extract_input_data(inp, task_key)

        exemplar["sections"][task_key] = {
            "sac_dim": meta["sac_dim"],
            "section_name": meta["section"],
            "description": meta["description"],
            "input_data": input_data,
            "output_raw": out,
            "output_parsed": parsed_output,
            "output_length": len(out),
        }

    return exemplar


def extract_input_data(prompt: str, task: str) -> str:
    """Extract the core data from a FinRpt prompt, removing boilerplate."""
    # Find data after common prefixes
    patterns = [
        r"(报告日期|日期)[:：]\s*\d{4}",
        r"(公司概况|公司名称)[:：]",
        r"(财务数据|三表数据)[:：]",
    ]
    for pat in patterns:
        m = re.search(pat, prompt)
        if m:
            return prompt[m.start() :]

    # Fallback: return last 60% of prompt (skip boilerplate)
    start = int(len(prompt) * 0.4)
    return prompt[start:]


# ── Quality Scoring for Golden Reports ────────────────────────
def compute_golden_quality(sections: dict, meta: dict) -> float:
    """Compute quality score for a golden report exemplar based on section completeness."""
    score = 0.0
    total_sections = len(sections)

    # Base score for having sections
    score += min(total_sections * 0.5, 4.0)

    # Length and structure bonus per section
    for section_name, content in sections.items():
        length = len(content)
        if 200 <= length <= 2000:
            score += 0.5
        elif 100 <= length < 200 or 2000 < length <= 5000:
            score += 0.3
        elif length > 100:
            score += 0.1

        # Structure: has clear paragraphs, numbers, tables
        if re.search(r"\d+\.?\d*\s*[%亿万]", content):
            score += 0.3  # Has concrete numbers
        if re.search(r"[（\(]\d{4}[）\)]", content):
            score += 0.2  # Has year references
        if re.search(r"[A-Z]{2,}\d+", content):
            score += 0.1  # Has stock codes

    # Diversity bonus: more distinct SAC dims covered
    return round(min(score, 10.0), 2)


# ── Golden Report Parsing ──────────────────────────────────────
def parse_golden_report(md_path: Path) -> list[dict]:
    """Parse a golden MD file into section dicts: {section_name: content}."""
    text = md_path.read_text(encoding="utf-8", errors="replace")

    # Split by markdown headings (##, ###)
    # Pattern: ^#{1,3}\s+(.+)$
    sections = {}
    current_section = None
    current_content = []

    lines = text.split("\n")
    for line in lines:
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            # Save previous section
            if current_section is not None:
                content = "\n".join(current_content).strip()
                if content:
                    # Normalize section name
                    norm_name = normalize_section_name(current_section)
                    if norm_name:
                        sections[norm_name] = content
            # Start new section
            current_section = heading_match.group(2).strip()
            current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_section is not None:
        content = "\n".join(current_content).strip()
        if content:
            norm_name = normalize_section_name(current_section)
            if norm_name:
                sections[norm_name] = content

    return sections


def normalize_section_name(raw_name: str) -> str:
    """Normalize section name to canonical SAC section name."""
    raw = raw_name.strip()
    # Remove common prefixes/suffixes
    raw = re.sub(r"^\d+[\.\s]*", "", raw)  # Remove leading numbers
    raw = re.sub(r"[（\(].*?[）\)]", "", raw)  # Remove parenthetical
    raw = raw.strip()

    # Direct match
    if raw in GOLDEN_SECTION_MAP:
        return GOLDEN_SECTION_MAP[raw]

    # Fuzzy match: check if any key is contained in raw or vice versa
    for key, val in GOLDEN_SECTION_MAP.items():
        if key in raw or raw in key:
            return val

    # Fuzzy: check partial word matches
    raw_words = set(re.findall(r"[\u4e00-\u9fff]+", raw))
    for key, val in GOLDEN_SECTION_MAP.items():
        key_words = set(re.findall(r"[\u4e00-\u9fff]+", key))
        if raw_words & key_words:
            return val

    return None


def parse_golden_report_with_meta(md_path: Path) -> dict:
    """Parse golden report and extract metadata + sections."""
    text = md_path.read_text(encoding="utf-8", errors="replace")

    # Extract metadata from first few lines
    meta = {
        "source_file": md_path.name,
        "asset": md_path.stem,
    }

    # Try to extract stock code / company name from filename
    stem = md_path.stem
    # Pattern: Name_code_date or similar
    code_match = re.search(r"(\d{6}\.[SHZ]?|[A-Z]{1,5}\.?[A-Z]?)", stem)
    if code_match:
        meta["stock_code"] = code_match.group(1)
    else:
        meta["stock_code"] = "UNKNOWN"

    # Parse date from filename
    date_match = re.search(r"(\d{8})", stem)
    if date_match:
        meta["date"] = date_match.group(1)
    else:
        meta["date"] = "20240101"

    sections = parse_golden_report(md_path)

    return {
        "meta": meta,
        "sections": sections,
    }


# ── Build Exemplar from Golden Report ─────────────────────────
def build_golden_exemplar(parsed: dict, source_category: str) -> dict:
    """Convert a parsed golden report into an exemplar entry."""
    meta = parsed["meta"]
    sections = parsed["sections"]

    # Map sections to SAC sections
    sac_sections = defaultdict(str)
    for sec_name, content in sections.items():
        canon = normalize_section_name(sec_name)
        if canon and canon in SECTION_CANONICAL:
            canon_name = SECTION_CANONICAL[canon]
            sac_sections[canon_name] += "\n\n" + content

    quality = compute_golden_quality(sac_sections, {})

    stock = meta.get("stock_code", "UNKNOWN")
    date = meta.get("date", "20240101")
    asset_name = parsed.get("meta", {}).get("asset", "UNKNOWN")

    exemplar = {
        "id": f"golden_{source_category}_{stock}_{date}",
        "stock_code": stock,
        "date": date,
        "sector": classify_sector(stock),
        "quality_score": quality,
        "sections": {},
        "source": "golden",
        "source_category": source_category,
        "asset_name": asset_name,
    }

    # Map each SAC section to task_key format
    section_to_task = {
        "利润表分析": "income",
        "资产负债表分析": "balance",
        "现金流量表分析": "cash",
        "财务综述": "finance_write",
        "投资建议报告": "report_write",
        "趋势分析": "trend_write",
        "风险提示": "risk",
        "新闻综述": "news_write",
        "新闻分析": "news_anlyzer",
    }

    for sac_section, content in sac_sections.items():
        if not content.strip():
            continue
        task_key = section_to_task.get(sac_section)
        if not task_key:
            continue

        meta_info = TASK_MAP[task_key]

        # Create a pseudo-input from the content itself (summary)
        input_data = content[:500]  # First 500 chars as context

        exemplar["sections"][task_key] = {
            "sac_dim": meta_info["sac_dim"],
            "section_name": meta_info["section"],
            "description": meta_info["description"],
            "input_data": input_data,
            "output_raw": content,
            "output_parsed": None,
            "output_length": len(content),
        }

    return exemplar


# ── Updated Main ──────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--include-golden", action="store_true", help="Include golden corpus reports")
    parser.add_argument("--only-golden", action="store_true", help="Only process golden corpus")
    args = parser.parse_args()

    all_exemplars = []

    # 1. Load FinRpt exemplars (original logic)
    if not args.only_golden:
        print("Building exemplar bank from FinRpt...")
        records = []
        with open(FINRPT, encoding="utf-8") as f:
            for line in f:
                records.append(json.loads(line))
        print(f"  Loaded {len(records)} FinRpt records")

        for rec in records:
            ex = build_exemplar(rec)
            all_exemplars.append(ex)
        print(f"  Built {len(all_exemplars)} FinRpt exemplars")

    # 2. Load Golden corpus exemplars
    if args.include_golden or args.only_golden:
        print("Building exemplar bank from Golden corpus...")
        golden_count = 0
        for cat in ["listed_company", "industry_deep", "unlisted_company", "earnings_notes", "decision_memo"]:
            cat_dir = GOLDEN / cat
            if not cat_dir.exists():
                continue
            md_files = list(cat_dir.glob("*.md"))
            if not md_files:
                continue
            print(f"  Processing {cat}: {len(md_files)} files...")
            cat_count = 0
            for md_file in md_files:
                try:
                    parsed = parse_golden_report_with_meta(md_file)
                    ex = build_golden_exemplar(parsed, cat)
                    if ex["sections"]:  # Only add if has valid sections
                        all_exemplars.append(ex)
                        golden_count += 1
                except Exception as e:
                    print(f"  Warning: Failed to parse {md_file.name}: {e}")
            print(f"  Added {golden_count} golden exemplars from {cat}")
        print(f"  Total golden exemplars: {golden_count}")

    print(f"\nTotal exemplars: {len(all_exemplars)}")

    # Sort by quality score
    all_exemplars.sort(key=lambda x: x["quality_score"], reverse=True)

    # Save full index
    index_path = OUT / "exemplar_index.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        for ex in all_exemplars:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"  Saved {len(all_exemplars)} exemplars to {index_path}")

    # Create sector-grouped files for retrieval
    by_sector = defaultdict(list)
    for ex in all_exemplars:
        by_sector[ex["sector"]].append(ex)

    # Create section-specific exemplar files
    # Combine FinRpt task_keys and golden canonical sections
    all_section_keys = set(TASK_MAP.keys()) | set(SECTION_CANONICAL.values())

    for task_key in all_section_keys:
        # Determine section metadata
        if task_key in TASK_MAP:
            meta = TASK_MAP[task_key]
            section_name = meta["section"]
        else:
            # Golden-only section
            meta = {
                "sac_dim": "财务验证",  # default
                "section": task_key,
                "description": "Golden corpus derived section",
            }
            section_name = task_key

        section_dir = OUT / "sections" / section_name
        section_dir.mkdir(parents=True, exist_ok=True)

        # Get top exemplars for this section
        section_exemplars = [ex for ex in all_exemplars if task_key in ex.get("sections", {})]
        section_exemplars.sort(key=lambda x: x["sections"].get(task_key, {}).get("output_length", 0), reverse=True)

        # Save top 100 per section
        section_file = section_dir / "exemplars.jsonl"
        with open(section_file, "w", encoding="utf-8") as f:
            for ex in section_exemplars[:100]:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        print(f"  {section_name}: {len(section_exemplars)} exemplars, top 100 saved")

    # Create metadata summary
    summary = {
        "total_exemplars": len(all_exemplars),
        "sectors": {s: len(exs) for s, exs in by_sector.items()},
        "sections": {
            TASK_MAP.get(k, {}).get("section", k): sum(1 for ex in all_exemplars if k in ex.get("sections", {}))
            for k in all_section_keys
        },
        "quality_stats": {
            "mean": sum(ex["quality_score"] for ex in all_exemplars) / max(len(all_exemplars), 1),
            "max": max(ex["quality_score"] for ex in all_exemplars) if all_exemplars else 0,
            "min": min(ex["quality_score"] for ex in all_exemplars) if all_exemplars else 0,
        },
        "golden_exemplars": sum(1 for ex in all_exemplars if ex.get("source") == "golden"),
        "finrpt_exemplars": sum(1 for ex in all_exemplars if ex.get("source") != "golden"),
    }

    with open(OUT / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n  Summary:")
    print(f"    Total exemplars: {summary['total_exemplars']}")
    print(f"    FinRpt exemplars: {summary['finrpt_exemplars']}")
    print(f"    Golden exemplars: {summary['golden_exemplars']}")
    print(
        f"    Quality: mean={summary['quality_stats']['mean']:.2f}, "
        f"max={summary['quality_stats']['max']:.2f}, "
        f"min={summary['quality_stats']['min']:.2f}"
    )
    print(f"    Sections: {list(summary['sections'].keys())}")


if __name__ == "__main__":
    main()
