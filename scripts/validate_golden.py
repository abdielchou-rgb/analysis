"""Golden truth set validation runner.

Compares generated reports against golden truth set (benchmark/golden/).
Computes delta metrics for CI regression detection.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("2hao.golden_validation")


def load_golden_set(golden_dir: str = "benchmark/golden") -> list[dict]:
    """Load all golden truth items from directory.

    Returns list of {name, path, content_hash, content_length}
    """
    golden_path = Path(golden_dir)
    if not golden_path.exists():
        return []

    items = []
    for item in golden_path.rglob("*.md"):
        content = item.read_text(encoding="utf-8")
        content_hash = __import__("hashlib").sha256(content.encode("utf-8")).hexdigest()[:16]
        items.append({
            "name": item.stem,
            "path": str(item),
            "relative_path": str(item.relative_to(golden_path)),
            "content_hash": content_hash,
            "content_length": len(content),
            "line_count": content.count("\n") + 1,
        })

    return items


def compute_text_similarity(text1: str, text2: str) -> float:
    """Compute simple text similarity (Jaccard on words).

    Returns 0.0 to 1.0
    """
    words1 = set(re.findall(r'\w+', text1.lower()))
    words2 = set(re.findall(r'\w+', text2.lower()))

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union) if union else 0.0


def compute_structure_similarity(text1: str, text2: str) -> float:
    """Compare document structure (headings, sections, tables).

    Returns 0.0 to 1.0
    """
    def get_structure(text):
        headings = re.findall(r'^#{1,6}\s+.+', text, re.MULTILINE)
        tables = text.count("|")
        lists = text.count("- ") + text.count("* ")
        return {
            "heading_count": len(headings),
            "table_markers": tables,
            "list_items": lists,
            "total_length": len(text),
        }

    s1 = get_structure(text1)
    s2 = get_structure(text2)

    # Simple similarity based on structure counts
    scores = []
    for key in ["heading_count", "table_markers", "list_items"]:
        if s1[key] == 0 and s2[key] == 0:
            scores.append(1.0)
        elif s1[key] == 0 or s2[key] == 0:
            scores.append(0.0)
        else:
            scores.append(1.0 - abs(s1[key] - s2[key]) / max(s1[key], s2[key]))

    return sum(scores) / len(scores) if scores else 0.0


def validate_against_golden(
    generated_path: str,
    golden_items: list[dict] = None,
    golden_dir: str = "benchmark/golden",
) -> dict:
    """Validate a generated report against golden truth set.

    Args:
        generated_path: Path to generated report
        golden_items: Pre-loaded golden items (if None, loads from golden_dir)
        golden_dir: Directory containing golden truth set

    Returns:
        {similarity_scores, best_match, structure_match, delta}
    """
    gen_path = Path(generated_path)
    if not gen_path.exists():
        return {"error": f"Generated report not found: {generated_path}"}

    gen_content = gen_path.read_text(encoding="utf-8")

    if golden_items is None:
        golden_items = load_golden_set(golden_dir)

    if not golden_items:
        return {"error": "No golden truth items found"}

    # Compare against all golden items
    similarities = []
    for item in golden_items:
        golden_content = Path(item["path"]).read_text(encoding="utf-8")
        word_sim = compute_text_similarity(gen_content, golden_content)
        struct_sim = compute_structure_similarity(gen_content, golden_content)
        combined = 0.6 * word_sim + 0.4 * struct_sim

        similarities.append({
            "golden_name": item["name"],
            "word_similarity": round(word_sim, 4),
            "structure_similarity": round(struct_sim, 4),
            "combined_similarity": round(combined, 4),
        })

    # Sort by combined similarity
    similarities.sort(key=lambda x: x["combined_similarity"], reverse=True)

    best = similarities[0] if similarities else None
    avg_combined = sum(s["combined_similarity"] for s in similarities) / len(similarities)

    return {
        "generated_file": generated_path,
        "golden_count": len(golden_items),
        "similarities": similarities[:5],  # Top 5
        "best_match": best,
        "average_similarity": round(avg_combined, 4),
        "delta": {
            "word_vs_best": round(best["word_similarity"], 4) if best else 0,
            "structure_vs_best": round(best["structure_similarity"], 4) if best else 0,
            "combined_vs_best": round(best["combined_similarity"], 4) if best else 0,
        },
    }


def run_golden_validation(
    output_dir: str = "output",
    golden_dir: str = "benchmark/golden",
) -> dict:
    """Run golden validation on all generated reports in output directory.

    Returns validation results for each report.
    """
    output_path = Path(output_dir)
    golden_items = load_golden_set(golden_dir)

    results = {}
    for report_file in output_path.glob("*.md"):
        if report_file.name.startswith("gate_"):
            continue  # Skip gate reports
        result = validate_against_golden(
            str(report_file),
            golden_items=golden_items,
            golden_dir=golden_dir,
        )
        results[report_file.name] = result

    # Save results
    out_path = output_path / "golden_validation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info("[GOLDEN] Validated %d reports against %d golden items",
                len(results), len(golden_items))

    return results


# ============================================================
# P0-5: Numeric golden truth validation
# ============================================================

def load_numeric_golden_set(golden_dir: str = "benchmark/golden_numeric") -> list[dict]:
    """Load numeric golden truth set (JSON format).

    Each item has: asset, report_id, field, canonical, source, tolerance.
    """
    golden_path = Path(golden_dir)
    if not golden_path.exists():
        return []

    items = []
    for json_file in golden_path.rglob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                items.extend(data)
            else:
                items.append(data)
        except Exception as e:
            logger.warning("[GOLDEN-NUMERIC] Failed to load %s: %s", json_file, e)

    return items


def extract_numeric_values(report_text: str) -> dict[str, list[float]]:
    """Extract numeric values from report text for key fields.

    Returns: {field_name: [extracted_values]}
    """
    extracted = {}

    # Target price patterns
    tp_patterns = [
        r"目标价[：:\s]*(\d+\.?\d*)\s*[元]",
        r"target\s*price[：:\s]*(\d+\.?\d*)",
        r"给予.*?(\d+\.?\d*)\s*元.*?目标",
    ]
    tp_values = []
    for pat in tp_patterns:
        matches = re.findall(pat, report_text, re.IGNORECASE)
        tp_values.extend([float(m) for m in matches])
    if tp_values:
        extracted["target_price"] = tp_values

    # Revenue patterns (亿元)
    rev_patterns = [
        r"营收.*?(\d+\.?\d*)\s*亿",
        r"收入.*?(\d+\.?\d*)\s*亿",
        r"营业收入.*?(\d+\.?\d*)\s*亿",
    ]
    rev_values = []
    for pat in rev_patterns:
        matches = re.findall(pat, report_text)
        rev_values.extend([float(m) for m in matches])
    if rev_values:
        extracted["revenue"] = rev_values

    # PE ratio patterns
    pe_patterns = [
        r"(\d+\.?\d*)\s*倍.*?PE",
        r"PE.*?(\d+\.?\d*)\s*倍",
        r"市盈率.*?(\d+\.?\d*)",
    ]
    pe_values = []
    for pat in pe_patterns:
        matches = re.findall(pat, report_text, re.IGNORECASE)
        pe_values.extend([float(m) for m in matches])
    if pe_values:
        extracted["pe_ratio"] = pe_values

    return extracted


def validate_numeric_values(
    report_text: str,
    golden_items: list[dict],
    asset_filter: str = None,
) -> dict:
    """Validate numeric values in report against golden truth set.

    Args:
        report_text: Generated report content
        golden_items: List of golden numeric truth items
        asset_filter: Only validate for this asset (optional)

    Returns:
        {total_checks, passed, failed, unverifiable, details}
    """
    if not golden_items:
        return {"error": "No golden numeric items loaded"}

    extracted = extract_numeric_values(report_text)
    results = {"total_checks": 0, "passed": 0, "failed": 0, "unverifiable": 0, "details": []}

    for item in golden_items:
        asset = item.get("asset", "")
        field = item.get("field", "")
        canonical = item.get("canonical", 0)
        tolerance = item.get("tolerance", 0.01)
        allow_values = item.get("allow_report_values", [canonical])

        if asset_filter and asset != asset_filter:
            continue

        results["total_checks"] += 1

        # Check if field was extracted
        if field not in extracted or not extracted[field]:
            results["unverifiable"] += 1
            results["details"].append({
                "asset": asset,
                "field": field,
                "status": "unverifiable",
                "reason": "field_not_found_in_report",
            })
            continue

        # Check if any extracted value matches
        values = extracted[field]
        matched = False
        for val in values:
            # Check against allowed values
            for allowed in allow_values:
                if abs(val - allowed) / max(abs(allowed), 1e-10) <= tolerance:
                    matched = True
                    break
            if matched:
                break

        if matched:
            results["passed"] += 1
            results["details"].append({
                "asset": asset,
                "field": field,
                "status": "passed",
                "canonical": canonical,
                "extracted": values[:3],
            })
        else:
            results["failed"] += 1
            results["details"].append({
                "asset": asset,
                "field": field,
                "status": "failed",
                "canonical": canonical,
                "extracted": values[:3],
                "reason": f"no_match_within_tolerance_{tolerance}",
            })

    # Summary
    results["pass_rate"] = round(results["passed"] / max(results["total_checks"], 1), 4)
    results["fail_rate"] = round(results["failed"] / max(results["total_checks"], 1), 4)

    return results


def run_numeric_validation(
    output_dir: str = "output",
    golden_dir: str = "benchmark/golden_numeric",
) -> dict:
    """Run numeric validation on all generated reports."""
    output_path = Path(output_dir)
    golden_items = load_numeric_golden_set(golden_dir)

    if not golden_items:
        return {"error": "No numeric golden items found"}

    results = {}
    for report_file in output_path.glob("*.md"):
        if report_file.name.startswith("gate_"):
            continue
        report_text = report_file.read_text(encoding="utf-8")
        result = validate_numeric_values(report_text, golden_items)
        results[report_file.name] = result

    # Save results
    out_path = output_path / "golden_numeric_validation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    total = sum(r.get("total_checks", 0) for r in results.values())
    passed = sum(r.get("passed", 0) for r in results.values())
    failed = sum(r.get("failed", 0) for r in results.values())

    logger.info("[GOLDEN-NUMERIC] Validated %d reports: %d/%d passed, %d failed",
                len(results), passed, total, failed)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate against golden truth set")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--golden-dir", default="benchmark/golden")
    parser.add_argument("--numeric", action="store_true", help="Run numeric validation")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.numeric:
        results = run_numeric_validation(args.output_dir)
        print(json.dumps({k: {"pass_rate": v.get("pass_rate", 0), "failed": v.get("failed", 0)} for k, v in results.items()}, indent=2))
    else:
        results = run_golden_validation(args.output_dir, args.golden_dir)
        print(json.dumps({k: v.get("delta", {}) for k, v in results.items()}, indent=2))
