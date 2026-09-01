"""S4-1: 框架有效性统计

聚合 method_reflection_log：
- 每框架：用了多少次 / 平均 Gate 分 / 通过率
- 对比：用该框架 vs 不用（同报告类型）的 Gate 分差
输出 output/framework_effectiveness_<date>.md
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("framework_effectiveness")

OUTPUT_DIR = _ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = _ROOT / "data" / "method_reflection_log.json"


def _load_reflection_log() -> list[dict]:
    if LOG_PATH.exists():
        with open(LOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def _aggregate_by_framework(entries: list[dict]) -> dict[str, dict]:
    """按框架聚合统计。"""
    frameworks: dict[str, list[dict]] = {}

    for entry in entries:
        fw = entry.get("framework", entry.get("method", "unknown"))
        frameworks.setdefault(fw, []).append(entry)

    stats = {}
    for fw, items in frameworks.items():
        gate_scores = [i.get("gate_score", i.get("score", 0)) for i in items if i.get("gate_score") or i.get("score")]
        passed = sum(1 for i in items if i.get("passed", i.get("gate_passed", False)))

        stats[fw] = {
            "count": len(items),
            "avg_gate": sum(gate_scores) / len(gate_scores) if gate_scores else 0,
            "pass_rate": passed / len(items) if items else 0,
            "passed": passed,
        }

    return stats


def _compare_with_without(entries: list[dict]) -> list[dict]:
    """对比：用框架 vs 不用框架的 Gate 分差。"""
    by_type: dict[str, dict[str, list]] = {}

    for entry in entries:
        rt = entry.get("report_type", "unknown")
        fw = entry.get("framework", entry.get("method", ""))
        by_type.setdefault(rt, {"with_fw": [], "without_fw": []})

        if fw:
            by_type[rt]["with_fw"].append(entry)
        else:
            by_type[rt]["without_fw"].append(entry)

    comparisons = []
    for rt, groups in by_type.items():
        with_scores = [i.get("gate_score", i.get("score", 0)) for i in groups["with_fw"] if i.get("gate_score") or i.get("score")]
        without_scores = [i.get("gate_score", i.get("score", 0)) for i in groups["without_fw"] if i.get("gate_score") or i.get("score")]

        if with_scores and without_scores:
            avg_with = sum(with_scores) / len(with_scores)
            avg_without = sum(without_scores) / len(without_scores)
            comparisons.append({
                "report_type": rt,
                "with_fw_avg": avg_with,
                "without_fw_avg": avg_without,
                "diff": avg_with - avg_without,
                "with_fw_count": len(groups["with_fw"]),
                "without_fw_count": len(groups["without_fw"]),
            })

    return comparisons


def generate_framework_effectiveness_report() -> str:
    """生成框架有效性报告。"""
    entries = _load_reflection_log()
    if not entries:
        return f"# 框架有效性报告 {datetime.now().strftime('%Y-%m-%d')}\n\n无框架反射日志数据。"

    stats = _aggregate_by_framework(entries)
    comparisons = _compare_with_without(entries)

    lines = [
        f"# 框架有效性报告 {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"总记录数: {len(entries)}",
        "",
        "## 框架统计",
        "",
        "| 框架 | 使用次数 | 平均 Gate 分 | 通过率 |",
        "|------|---------|-------------|--------|",
    ]

    for fw, s in sorted(stats.items(), key=lambda x: -x[1]["count"]):
        lines.append(f"| {fw} | {s['count']} | {s['avg_gate']:.2f} | {s['pass_rate']:.1%} |")

    if comparisons:
        lines.extend(["", "## 用 vs 不用框架对比", ""])
        lines.append("| 报告类型 | 用框架 | 不用框架 | 差值 | 样本(用/不用) |")
        lines.append("|----------|--------|---------|------|--------------|")
        for c in comparisons:
            lines.append(
                f"| {c['report_type']} | {c['with_fw_avg']:.2f} | {c['without_fw_avg']:.2f} "
                f"| {c['diff']:+.2f} | {c['with_fw_count']}/{c['without_fw_count']} |"
            )

    return "\n".join(lines)


def main():
    logger.info("=== 框架有效性统计 ===")
    report = generate_framework_effectiveness_report()
    report_file = OUTPUT_DIR / f"framework_effectiveness_{datetime.now().strftime('%Y%m%d')}.md"
    report_file.write_text(report, encoding="utf-8")
    logger.info("框架有效性报告: %s", report_file)
    print(report)


if __name__ == "__main__":
    main()
