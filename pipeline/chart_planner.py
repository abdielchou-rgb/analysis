"""
2鍙峰垎鏋愬笀 Chart Planner - 鍥捐〃棰勮鍒掑櫒(SAC椹卞姩鐗?
浠?SAC YAML 鍔犺浇鍥捐〃閰嶇疆(鍗曚竴浜嬪疄婧?;
V56 鍗囩骇: 鏁版嵁鏍煎紡褰掍竴鍖?SAC椹卞姩+涓枃鍗曚綅瑙ｆ瀽)
"""

import re as _re
import sys
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

from core.sacs import SACLoader


class ChartPlanner:
    """鍥捐〃瑙勫垝鍣?- 浠嶴AC鍔犺浇鍥捐〃閰嶇疆"""

    def __init__(self, report_type="industry_deep", style="cicc", output_dir="output/charts", industry=""):
        self.report_type = report_type
        self.style = style
        self.industry = industry or "\u8be5\u884c\u4e1a"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sac = SACLoader(report_type)
        self._chart_config = self.sac.get_chart_config()
        self._chart_plan = self._build_plan()

    _METRIC_MAP = {
        "fig_revenue_trend": "revenue",
        "fig_profitability": "net_profit",
        "fig_margin_trend": "gross_margin",
        "fig_revenue_change": "revenue",
        "fig_profit_change": "net_profit",
        "fig_gross_margin": "gross_margin",
        "fig_roe_trend": "roe",
        "fig_eps_trend": "eps",
        "fig_debt_ratio": "asset_liability_ratio",
    }

    @staticmethod
    def _parse_numeric(val) -> float | None:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if not isinstance(val, str):
            return None
        s = val.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            pass
        s = s.replace(",", "").replace("\uff0c", "")
        mult = 1.0
        if "\u4ebf" in s:
            s = s.replace("\u4ebf", "").strip()
        elif "\u4e07" in s:
            s = s.replace("\u4e07", "").strip()
            mult = 10000.0
        if "%" in s:
            s = s.replace("%", "").strip()
        nums = _re.findall(r"-?\d+\.?\d*", s)
        if nums:
            try:
                return float(nums[0]) * mult
            except ValueError:
                pass
        return None

    def _normalize_chart_data(self, raw_data, chart_id):
        if not raw_data or not isinstance(raw_data, dict):
            return {}
        keys = list(raw_data.keys())
        if not keys:
            return {}
        fv = raw_data[keys[0]]
        if isinstance(fv, dict):
            metric = self._METRIC_MAP.get(chart_id, "revenue")
            result = {}
            for year, metrics in raw_data.items():
                if isinstance(metrics, dict) and metric in metrics:
                    val = self._parse_numeric(metrics[metric])
                    if val is not None:
                        result[str(year)] = val
            return result
        result = {}
        for key, val in raw_data.items():
            parsed = self._parse_numeric(val)
            if parsed is not None:
                result[str(key)] = parsed
        return result

    def _build_plan(self):
        plan = []
        for cd in self._chart_config.get("charts", []):
            c = dict(cd)
            c["title"] = c.get("caption", "").replace("{asset}", self.industry)
            c["section"] = self._map_chart_to_section(c["id"])
            c["path"] = str(self.output_dir / ("fig%d_%s_%s.png" % (c["num"], c["id"], self.style)))
            c["index"] = c["num"]
            plan.append(c)
        return plan

    def _map_chart_to_section(self, chart_id):
        m = {
            "fig_market_size_global": "\u5e02\u573a\u7a7a\u95f4\u6821\u51c6",
            "fig_market_size_china": "\u5e02\u573a\u7a7a\u95f4\u6821\u51c6",
            "fig_tech_segments": "\u6280\u672f\u8def\u7ebf\u9a8c\u8bc1",
            "fig_applications": "\u5e02\u573a\u7a7a\u95f4\u6821\u51c6",
            "fig_players": "\u7ade\u4e89\u683c\u5c40\u91cd\u6784",
            "fig_supply_chain": "\u5229\u6da6\u8fc1\u79fb\u8def\u5f84",
            "fig_revenue_trend": "\u8d22\u52a1\u8bc1\u636e\u68c0\u9a8c",
            "fig_profitability": "\u8d22\u52a1\u8bc1\u636e\u68c0\u9a8c",
            "fig_valuation": "\u4f30\u503c\u6620\u5c04",
            "fig_peer_comparison": "\u7ade\u4e89\u4f4d\u7f6e\u786e\u8ba4",
            "fig_business_segments": "\u5206\u90e8\u5206\u6790",
            "fig_business_model": "\u5546\u4e1a\u6a21\u5f0f\u9a8c\u8bc1",
            "fig_market_positioning": "\u7ade\u4e89\u4f4d\u7f6e\u786e\u8ba4",
            "fig_growth_drivers": "\u589e\u957f\u53ef\u6301\u7eed\u6027",
            "fig_competitive_landscape": "\u7ade\u4e89\u683c\u5c40\u91cd\u6784",
            "fig_revenue_change": "\u6838\u5fc3\u6570\u5b57\u5b9a\u4f4d",
            "fig_profit_change": "\u6838\u5fc3\u6570\u5b57\u5b9a\u4f4d",
            "fig_segment_performance": "\u5206\u90e8\u5206\u6790",
            "fig_guidance_track": "\u5c55\u671b\u4e0e\u5f71\u54cd",
        }
        return m.get(chart_id, "\u5176\u4ed6")

    def plan(self):
        for i, c in enumerate(self._chart_plan):
            c["path"] = str(self.output_dir / ("fig%d_%s_%s.png" % (i + 1, c["id"], self.style)))
            c["index"] = i + 1
        return self._chart_plan

    def generate_all(self, data):
        import logging

        logger = logging.getLogger("2hao.chart_planner")
        chart_paths = {}
        placeholders = []
        real_charts = []
        rc = pc = 0
        try:
            from core.chart_engine import ChartEngine

            engine = ChartEngine(output_dir=str(self.output_dir))
            engine.set_style(self.style)
        except Exception as e:
            logger.warning("ChartEngine init failed: %s", e)
            return {"error": str(e), "placeholders": [], "real_charts": []}
        for cd in self.plan():
            cid = cd["id"]
            ct = self._infer_chart_type(cid)
            title = cd["title"]
            path = cd["path"]
            source = cd.get("source", "")
            raw = data.get(cid)
            if not raw:
                raw = data.get("chart_data", {}).get(cid, {})
            if not raw:
                raw = data.get("financials", {}).get("data", {}).get(cid, {})
            if not raw and data.get("compute_results"):
                for cr_key, cr_val in data["compute_results"].items():
                    if isinstance(cr_val, dict) and cr_val.get("status") == "ok":
                        raw = cr_val.get("data", cr_val)
            ed = self._normalize_chart_data(raw, cid)
            if not ed:
                logger.info("  %s: no data -> placeholder", cid)
                self._generate_placeholder(path, title)
                chart_paths[cid] = path
                placeholders.append(cid)
                pc += 1
                continue
            try:
                r = None
                if ct == "line_chart":
                    r = engine.line_chart(ed, title=title, save_path=path, data_source=source)
                elif ct == "pie_chart":
                    r = engine.pie_chart(ed, title=title, save_path=path, data_source=source)
                elif ct in ("bar_chart", "bar", "column"):
                    r = engine.bar_chart(ed, title=title, save_path=path, data_source=source)
                elif ct in ("heatmap", "sensitivity_heatmap"):
                    r = engine.sensitivity_heatmap(ed, title=title, save_path=path, data_source=source)
                else:
                    r = engine.bar_chart(ed, title=title, save_path=path, data_source=source)
                if r:
                    chart_paths[cid] = r
                    real_charts.append(cid)
                    rc += 1
                else:
                    logger.info("  %s: ChartEngine returned None -> placeholder", cid)
                    self._generate_placeholder(path, title)
                    chart_paths[cid] = path
                    placeholders.append(cid)
                    pc += 1
            except Exception as e:
                logger.warning("  %s: failed (%s) -> placeholder", cid, e)
                self._generate_placeholder(path, title)
                chart_paths[cid] = path
                placeholders.append(cid)
                pc += 1
        chart_paths["__meta"] = {
            "total": len(chart_paths),
            "real": rc,
            "placeholders": pc,
            "placeholder_ids": placeholders,
            "real_ids": real_charts,
        }
        logger.info("Chart generation done: %d real + %d placeholders", rc, pc)
        return chart_paths

    def _generate_placeholder(self, path, title):
        try:
            import matplotlib.patches as mp
            import matplotlib.pyplot as plt

            plt.rcParams["font.family"] = "Microsoft YaHei"
            fig, ax = plt.subplots(figsize=(8, 4.5))
            ax.set_facecolor("#F8F8F8")
            fig.patch.set_facecolor("#F8F8F8")
            ax.text(
                0.5,
                0.92,
                title,
                transform=ax.transAxes,
                fontsize=14,
                fontweight="bold",
                color="#003366",
                ha="center",
                va="center",
            )
            ax.add_patch(
                mp.FancyBboxPatch(
                    (0.15, 0.25),
                    0.7,
                    0.45,
                    boxstyle="round,pad=0.05",
                    facecolor="#FFFFFF",
                    edgecolor="#CCCCCC",
                    linestyle="--",
                    linewidth=1.5,
                )
            )
            ax.text(
                0.5,
                0.58,
                "\u6570\u636e\u83b7\u53d6\u4e2d",
                transform=ax.transAxes,
                fontsize=20,
                color="#999999",
                ha="center",
                va="center",
                fontweight="bold",
            )
            ax.text(
                0.5,
                0.42,
                "\u5b9e\u9645\u6570\u636e\u83b7\u53d6\u540e\u5c06\u66ff\u6362",
                transform=ax.transAxes,
                fontsize=10,
                color="#AAAAAA",
                ha="center",
                va="center",
            )
            ax.text(
                0.5,
                0.32,
                "\u6765\u6e90\u6807\u6ce8\uff1a\u5f85\u8865\u5145",
                transform=ax.transAxes,
                fontsize=9,
                color="#BBBBBB",
                ha="center",
                va="center",
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.3, facecolor="#F8F8F8")
            plt.close(fig)
        except Exception:
            pass

    def _infer_chart_type(self, chart_id):
        tm = {
            "fig_market_size_global": "line_chart",
            "fig_market_size_china": "line_chart",
            "fig_revenue_trend": "line_chart",
            "fig_profit_margin": "line_chart",
            "fig_profitability": "line_chart",
            "fig_margin_trend": "line_chart",
            "fig_revenue_change": "line_chart",
            "fig_profit_change": "line_chart",
            "fig_guidance_track": "line_chart",
            "fig_tech_segments": "pie_chart",
            "fig_business_segments": "pie_chart",
            "fig_segment_performance": "pie_chart",
            "fig_surprise_analysis": "pie_chart",
            "fig_applications": "bar_chart",
            "fig_players": "bar_chart",
            "fig_supply_chain": "bar_chart",
            "fig_peer_comparison": "bar_chart",
            "fig_scenario_comparison": "bar_chart",
            "fig_business_model": "bar_chart",
            "fig_market_positioning": "bar_chart",
            "fig_growth_drivers": "bar_chart",
            "fig_competitive_landscape": "bar_chart",
            "fig_unit_economics": "bar_chart",
            "fig_funding_history": "bar_chart",
            "fig_valuation_triangle": "bar_chart",
        }
        return tm.get(chart_id, "bar_chart")

    def _default_data(self, chart_id):
        return {}

    def to_markdown_table(self):
        tn = {
            "line_chart": "\u6298\u7ebf\u56fe",
            "pie_chart": "\u997c\u56fe",
            "bar_chart": "\u6761\u5f62\u56fe",
            "heatmap": "\u70ed\u529b\u56fe",
        }
        lines = [
            "| \u7f16\u53f7 | \u56fe\u8868\u540d\u79f0 | \u7c7b\u578b | \u4f4d\u7f6e |",
            "|------|---------|------|------|",
        ]
        for c in self._chart_plan:
            t = tn.get(self._infer_chart_type(c["id"]), "\u56fe\u8868")
            lines.append("| \u56fe%d | %s | %s | %s |" % (c["num"], c["title"], t, c["section"]))
        return "\n".join(lines)


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--type", default="industry_deep")
    p.add_argument("--style", default="cicc")
    args = p.parse_args()
    planner = ChartPlanner(args.type, args.style)
    for c in planner.plan():
        print("  \u56fe%d: %s (%s) -> %s" % (c["num"], c["title"], c["id"], c["path"]))


if __name__ == "__main__":
    main()
