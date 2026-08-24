"""
2号分析师 Chart Runner — 图表生成工具

Agent调用此工具生成图表。输出图表文件路径供报告使用。
"""

import sys
import matplotlib
import matplotlib.pyplot as plt
import json
import logging
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.chart_runner")


class ChartRunner:
    """图表生成器 - Agent调用此工具生成专业图表"""

    def __init__(self, style: str = "cicc", output_dir: str = "output/charts"):
        self.style = style
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._engine = None
        self._init_engine()

    def _init_engine(self):
        try:
            from core.chart_engine import ChartEngine
            self._engine = ChartEngine(output_dir=str(self.output_dir))
            self._engine.set_style(self.style)
        except Exception as e:
            logger.warning(f"ChartEngine init failed: {e}")

    def generate_all(self, compute_results: dict, report_type: str = "industry_deep") -> list:
        """生成全部图表"""
        charts = []

        if self._engine:
            try:
                # Flatten data through adapter (chart_engine can't handle nested dicts)
                from pipeline.chart_data_adapter import generate_chart_data
                flat_data = generate_chart_data(compute_results or {})
                if flat_data:
                    logger.info(f"ChartAdapter: flattened {len(flat_data)} data points from compute_results")
                result = self._engine.generate_all(
                    flat_data,
                    title_prefix="",
                    style_id=self.style,
                )
                if isinstance(result, dict):
                    for key, val in result.items():
                        if isinstance(val, dict) and val.get("path"):
                            charts.append(Path(val["path"]))
                        elif isinstance(val, str) and any(val.endswith(ext) for ext in [".png", ".svg", ".pdf", ".jpg"]):
                            charts.append(Path(val))
            except Exception as e:
                logger.warning(f"generate_all failed: {e}")

        chart_plan = {
            "industry_deep": ["market_size_trend", "competitive_landscape", "revenue_growth_comparison", "profitability_comparison", "valuation_heatmap"],
            "listed_company": ["revenue_trend", "margin_trend", "dcf_sensitivity", "peer_comparison", "scenario_comparison"],
            "unlisted_company": ["unit_economics", "funding_history", "competitive_position", "valuation_triangle"],
            "earnings_notes": ["surprise_analysis", "segment_breakdown"],
        }

        required = chart_plan.get(report_type, chart_plan["industry_deep"])
        
        # Skip placeholder generation if real charts were already generated
        if len(charts) > 0:
            logger.info(f"Real charts generated ({len(charts)}), skipping placeholders")
        else:
            # Generate placeholder PNGs for missing charts
            for chart_id in required:
                chart_path = self.output_dir / f"{chart_id}_{self.style}.png"
                if not any(chart_id in str(c) for c in charts):
                    try:
                        matplotlib.use('Agg')
                        matplotlib.rcParams['font.family'] = 'Microsoft YaHei'
                        fig, ax = plt.subplots(figsize=(8, 4.5))
                        title_map = {"market_size_trend": "市场规模趋势", "competitive_landscape": "竞争格局", "revenue_growth_comparison": "营收增长对比", "profitability_comparison": "盈利对比", "valuation_heatmap": "估值热力图"}
                        chart_title = title_map.get(chart_id, chart_id)
                        ax.text(0.5, 0.5, chart_title + '\n(等待真实数据)', transform=ax.transAxes, ha='center', va='center', fontsize=12, color='gray', style='italic')
                        ax.set_xlim(0, 1)
                        ax.set_ylim(0, 1)
                        ax.axis('off')
                        fig.savefig(str(chart_path), dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
                        plt.close(fig)
                        charts.append(chart_path)
                        logger.info(f"  Placeholder chart: {chart_id}.png (补充)")
                    except Exception as e:
                        logger.warning(f"Could not create placeholder for {chart_id}: {e}")
        return charts

    def generate_data_table(self, data: list, headers: list, title: str = "") -> str:
        """生成数据表格（markdown格式）"""
        if not headers or not data:
            return ""
        lines = [f"**{title}**" if title else "", ""]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in data:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="2hao-analyst Chart Runner")
    parser.add_argument("--input", "-i", help="Compute results JSON")
    parser.add_argument("--type", default="industry_deep")
    parser.add_argument("--style", default="cicc")
    parser.add_argument("--output", "-o", default="output/charts")
    args = parser.parse_args()

    runner = ChartRunner(style=args.style, output_dir=args.output)
    data = {}
    if args.input:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))

    charts = runner.generate_all(data, args.type)
    print(f"Generated {len(charts)} charts:")
    for c in charts:
        print(f"  - {c}")


if __name__ == "__main__":
    main()
