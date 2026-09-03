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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate against golden truth set")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--golden-dir", default="benchmark/golden")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    results = run_golden_validation(args.output_dir, args.golden_dir)
    print(json.dumps({k: v.get("delta", {}) for k, v in results.items()}, indent=2))
