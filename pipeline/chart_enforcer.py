"""pipeline/chart_enforcer.py — Chart Manifest Generator + Post-Writing Validator

Pre-writing: generates structured chart manifest, forces LLM to reference all charts
Post-writing: validates chart embedding, counts references per chart
"""

import json
import re
import sys
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

# Default chart plans by report type
CHART_PLANS = {
    "industry_deep": [
        {"id": "market_size_global", "type": "line", "title": "全球市场规模趋势"},
        {"id": "market_size_china", "type": "line", "title": "中国市场规模趋势"},
        {"id": "tech_segments", "type": "pie", "title": "技术路线份额分布"},
        {"id": "applications", "type": "bar", "title": "下游应用领域分布"},
        {"id": "players", "type": "bar", "title": "主要企业市场份额"},
        {"id": "supply_chain", "type": "bar", "title": "产业链各环节利润率"},
    ],
    "listed_company": [
        {"id": "revenue_trend", "type": "line", "title": "营收趋势"},
        {"id": "margin_trend", "type": "line", "title": "利润率趋势"},
        {"id": "dcf_sensitivity", "type": "heatmap", "title": "DCF敏感性分析"},
        {"id": "peer_comparison", "type": "bar", "title": "可比企业估值对比"},
        {"id": "scenario_comparison", "type": "bar", "title": "情景分析对比"},
    ],
    "unlisted_company": [
        {"id": "unit_economics", "type": "bar", "title": "单位经济模型"},
        {"id": "funding_history", "type": "bar", "title": "融资历史与估值变化"},
        {"id": "competitive_position", "type": "bar", "title": "竞争定位矩阵"},
        {"id": "valuation_triangle", "type": "bar", "title": "估值三角检验"},
    ],
    "earnings_notes": [
        {"id": "surprise_analysis", "type": "bar", "title": "超预期分析"},
        {"id": "segment_breakdown", "type": "pie", "title": "分部穿透"},
    ],
}


class ChartEnforcer:
    """Chart Enforcer - pre-writing manifest + post-writing validation"""

    def __init__(self, report_type="industry_deep", style="cicc", output_dir="output/charts"):
        self.report_type = report_type
        self.style = style
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = []

    def build_manifest(self, industry=""):
        """Build structured chart manifest for writing prompt"""
        plans = CHART_PLANS.get(self.report_type, CHART_PLANS["industry_deep"])
        self.manifest = []
        for i, plan in enumerate(plans, 1):
            chart_id = plan["id"]
            title = plan["title"]
            if industry:
                title = industry + title
            chart_path = self.output_dir / ("fig%d_%s_%s.png" % (i, chart_id, self.style))
            entry = {
                "figure_num": i,
                "id": chart_id,
                "title": title,
                "path": str(chart_path.as_posix()),
                "type": plan["type"],
            }
            self.manifest.append(entry)
        return self.manifest

    def manifest_to_prompt(self, industry=""):
        """Convert manifest to prompt instructions for LLM"""
        self.build_manifest(industry)
        if not self.manifest:
            return ""
        lines = []
        lines.append("## 图表引用规则（必须遵守）")
        lines.append("")
        lines.append("以下图表已生成，你必须在报告中引用每一张：")
        lines.append("")
        for entry in self.manifest:
            lines.append("- 图%d: %s (%s)" % (entry["figure_num"], entry["title"], entry["path"]))
        lines.append("")
        lines.append("引用格式：")
        lines.append("  \u200b\u200b\u200b\u200b\u200b![\u56feN: \u56fe表标题](\u56fe表路径)")
        lines.append("  *\u56feN: \u56fe表标题。\u6570据\u6765\u6e90：XXX*")
        lines.append("")
        lines.append("每张图表必须置于相关分析段落中，前后有分析文本，不能堆在文末。")
        return "\n".join(lines)

    def validate(self, text):
        """Post-writing: validate chart embedding quality"""
        result = {
            "total_charts_in_manifest": len(self.manifest),
            "charts_referenced": 0,
            "charts_at_end": 0,
            "missing_charts": [],
            "issues": [],
        }
        if not self.manifest:
            return result

        # Find all chart references
        all_refs = list(re.finditer(r"!\[.*?\]\(.*?\)", text))

        # Check each manifest chart is referenced
        for entry in self.manifest:
            ref_path = entry["path"]
            ref_id = str(entry["figure_num"])
            ref_title = entry["title"]

            is_refd = any(ref_path in m.group() for m in all_refs)
            is_refd_by_num = any(ref_id in m.group() for m in all_refs)

            if is_refd or is_refd_by_num:
                result["charts_referenced"] += 1
            else:
                result["missing_charts"].append(entry["id"])

        # Check if charts are stacked at end
        if all_refs:
            end_threshold = int(len(text) * 0.8)
            end_refs = [m for m in all_refs if m.start() > end_threshold]
            result["charts_at_end"] = len(end_refs)
            if len(end_refs) >= len(all_refs) / 2:
                result["issues"].append("MORE THAN HALF charts stacked in last 20%% of text")

        result["pass"] = len(result["missing_charts"]) == 0 and result["charts_at_end"] < 3
        return result


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["manifest", "validate", "both"])
    parser.add_argument("--industry", default="", help="Industry name")
    parser.add_argument("--type", default="industry_deep")
    parser.add_argument("--style", default="cicc")
    parser.add_argument("--input", help="Report file for validation")
    parser.add_argument("--output", "-o", default="output/charts")
    args = parser.parse_args()

    enforcer = ChartEnforcer(args.type, args.style, args.output)

    if args.action in ("manifest", "both"):
        manifest = enforcer.build_manifest(args.industry)
        print("Chart Manifest:")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))

    if args.action in ("validate", "both") and args.input:
        text = Path(args.input).read_text(encoding="utf-8")
        result = enforcer.validate(text)
        print("\nValidation:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
