
# chart_pipeline.py — 独立图表生成管线（V3: 移除假数据）
import sys, os, re, json, logging
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
# 负责：1) 自动生成专业图表  2) 嵌入报告 3) 验证图表质量
# 优先使用 data_pipeline 采集的实时数据，无数据时使用智能模板数据
import sys, os, re, json, logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("2hao.chart_pipeline")

# 图表模板定义：报告类型 → 需要的图表列表
# 投行级密度：每维度 1-2 张图，一份上市公司深度报告 ~20 张图表（对标 MS/GS/JPM 每页 2 张）
CHART_TEMPLATES = {
    "listed_company": [
        # 决策门 / 核心分歧
        {"id": "decision_gate",        "type": "bar",         "title": "投资决策门",           "min": 1},
        {"id": "consensus_vs_deviation","type": "bar_line",   "title": "市场共识与预期差",     "min": 1},
        # 商业模式
        {"id": "revenue_structure",    "type": "bar",         "title": "收入结构分析",         "min": 1},
        {"id": "business_segments",    "type": "pie",         "title": "业务分部构成",         "min": 1},
        # 财务验证
        {"id": "financial_trends",     "type": "dual_axis",   "title": "营收与净利趋势",       "min": 1},
        {"id": "profit_margin",        "type": "bar_line",    "title": "利润率分析",           "min": 1},
        {"id": "cash_flow",            "type": "bar",         "title": "现金流结构",           "min": 1},
        {"id": "balance_sheet",        "type": "bar",         "title": "资产负债结构",         "min": 1},
        # 竞争位置
        {"id": "competitive_landscape","type": "bar_cluster", "title": "竞争格局对比",         "min": 1},
        {"id": "market_position",      "type": "pie",         "title": "市场份额",             "min": 1},
        {"id": "moat_analysis",        "type": "radar",       "title": "护城河雷达",           "min": 1},
        # 同业对标
        {"id": "valuation_peers",      "type": "scatter",     "title": "同业估值散点",         "min": 1},
        {"id": "peer_comparison",      "type": "bar_cluster", "title": "同业关键指标对比",     "min": 1},
        # 增长驱动
        {"id": "growth_drivers",       "type": "line",        "title": "增长驱动因素",         "min": 1},
        {"id": "industry_chain",       "type": "waterfall",   "title": "产业链价值分布",       "min": 1},
        # 治理 ESG / 管理
        {"id": "governance_esg",       "type": "radar",       "title": "治理与ESG评分",        "min": 1},
        {"id": "management_quality",   "type": "bar",         "title": "管理层质量评估",       "min": 1},
        # 估值
        {"id": "valuation_history",    "type": "line",        "title": "估值历史分位",         "min": 1},
        {"id": "dcf_sensitivity",      "type": "bar",         "title": "DCF敏感性分析",        "min": 1},
        # 资金面 / 催化剂
        {"id": "capital_flow",         "type": "bar",         "title": "资金流向",             "min": 1},
        {"id": "catalyst_timeline",    "type": "line",        "title": "催化剂时间线",         "min": 1},
    ],
    "industry_deep": [
        # 对齐 SAC chart_config（sac_industry_deep.yaml）——2026-08-01 修复
        # id 直接使用 SAC 的 fig_* 键
        {"id": "fig_market_size_global",  "type": "bar",         "title": "全球市场规模趋势",     "min": 1},
        {"id": "fig_market_size_china",   "type": "bar",         "title": "中国市场规模趋势",     "min": 1},
        {"id": "fig_supply_demand",       "type": "dual_axis",   "title": "供需平衡分析",         "min": 1},
        {"id": "fig_industry_chain",      "type": "waterfall",   "title": "产业链价值分布",       "min": 1},
        {"id": "fig_profit_pool",         "type": "bar",         "title": "盈利池分布",           "min": 1},
        {"id": "fig_competitive_landscape","type": "bar_cluster","title": "竞争格局",            "min": 1},
        {"id": "fig_market_share",        "type": "pie",         "title": "市场份额分布",         "min": 1},
        {"id": "fig_tech_trend",          "type": "line",        "title": "技术发展趋势",         "min": 1},
        {"id": "fig_tech_segments",       "type": "pie",         "title": "技术路线份额",         "min": 1},
        {"id": "fig_policy_impact",       "type": "bar",         "title": "政策影响分析",         "min": 1},
        {"id": "fig_peer_comparison",     "type": "scatter",     "title": "同业关键指标对比",     "min": 1},
        {"id": "fig_life_cycle",          "type": "line",        "title": "生命周期定位",         "min": 1},
        {"id": "unlisted_threat_map",     "type": "table",       "title": "非上市玩家威胁地图",   "min": 1},
    ],
    "unlisted_company": [
        # 对齐 SAC chart_config（sac_unlisted_company.yaml）——2026-08-01 修复
        # id 直接使用 SAC 的 fig_* 键，避免输出后需映射
        {"id": "fig_business_model",       "type": "bar",         "title": "商业模式拆解",         "min": 1},
        {"id": "fig_market_size",          "type": "bar",         "title": "市场规模与预测",       "min": 1},
        {"id": "fig_market_positioning",   "type": "radar",       "title": "市场定位矩阵",         "min": 1},
        {"id": "fig_growth_drivers",       "type": "line",        "title": "增长驱动因素",         "min": 1},
        {"id": "fig_competitive_landscape","type": "bar_cluster", "title": "竞争格局概览",         "min": 1},
        {"id": "fig_financial_trends",     "type": "dual_axis",   "title": "营收与净利趋势",       "min": 1},
        {"id": "fig_funding_history",      "type": "bar",         "title": "融资历程与估值",       "min": 1},
        {"id": "fig_industry_chain",       "type": "waterfall",   "title": "产业链价值分布",       "min": 1},
    ],
    "decision_memo": [  # R83: 决策备忘录轻量图（对齐 sac_decision_memo.yaml）
        {"id": "fig_market_size_global",  "type": "bar",         "title": "全球市场规模趋势",     "min": 1},
        {"id": "fig_market_size_china",   "type": "bar",         "title": "中国市场规模趋势",     "min": 1},
        {"id": "fig_industry_chain",      "type": "waterfall",   "title": "产业链价值分布",       "min": 1},
        {"id": "fig_competitive_landscape","type": "bar_cluster","title": "竞争格局",            "min": 1},
        {"id": "fig_production_path",     "type": "flow",        "title": "生产主体三选决策图",   "min": 1},
        {"id": "fig_roadmap",             "type": "timeline",    "title": "执行路线图",           "min": 1},
    ],
}

# data_pipeline 返回的 chart_data 键 → chart_pipeline chart_id 映射
DATA_PIPELINE_CHART_MAP = {
    "revenue_trend":      {"chart_id": "revenue_structure",     "type": "bar"},
    "profit_trend":       {"chart_id": "profit_margin",         "type": "bar_line"},
    "market_share":       {"chart_id": "market_position",       "type": "pie"},
    "valuation":          {"chart_id": "valuation_peers",       "type": "scatter"},
    "financials":         {"chart_id": "financial_trends",      "type": "dual_axis"},
    "market_size":        {"chart_id": "market_size",           "type": "bar"},
    "competitive_landscape": {"chart_id": "competitive_landscape", "type": "bar_cluster"},
    "industry_chain":     {"chart_id": "industry_chain",        "type": "waterfall"},
    "tech_trend":         {"chart_id": "tech_trend",            "type": "line"},
    "policy_impact":      {"chart_id": "policy_impact",         "type": "bar"},
    "business_model":     {"chart_id": "business_model",        "type": "bar"},
    "growth_metrics":     {"chart_id": "growth_metrics",        "type": "line"},
    "competitive_edge":   {"chart_id": "competitive_edge",      "type": "radar"},
    "market_opportunity": {"chart_id": "market_opportunity",    "type": "pie"},
}


def _render_chart_task(payload):
    """P3-audit 2026-08-24：进程池 worker（模块级函数，Windows spawn 可 pickle）。

    pyplot 全局态非线程安全 → 用进程并行；子进程内重建轻量 ChartPipeline
    （构造器仅 report_type/style/output_dir，避免 pickle 父实例）。
    """
    tmpl, chart_data, has_real_data, report_type, style, output_dir = payload
    from pipeline.chart_pipeline import ChartPipeline
    cp = ChartPipeline(report_type=report_type, style=style, output_dir=output_dir)
    return cp._generate_chart(tmpl, data=chart_data, has_real_data=has_real_data)


class ChartPipeline:
    def __init__(self, report_type="listed_company", style="cicc", output_dir="output/charts"):
        self.report_type = report_type
        self.style = style
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置matplotlib中文字体
        try:
            import core.cn_font_setup as cfs
            cfs.setup_cn_font()
        except Exception:
            pass
    
    def _get_style_colors(self):
        colors = {
            "cicc": ["#003366", "#C41E3A", "#4CB8E8", "#E8C84C", "#00A86B", "#999999"],
            "goldman_sachs": ["#051C2C", "#009688", "#4CB8E8", "#B0D4E8", "#7ED321"],
            "morgan_stanley": ["#003366", "#4CB8E8", "#B0D4E8", "#E8C84C", "#C41E3A"],
            "mckinsey": ["#003D2F", "#00A86B", "#7ED321", "#4CB8E8", "#999999"],
        }
        return colors.get(self.style, colors["cicc"])

    def _add_professional_finish(self, fig, ax, tmpl, data_source=""):
        """Add professional-grade finishing to any chart."""
        src = data_source or tmpl.get("source", "")
        if src and ax is not None:
            fig.text(0.99, -0.02, "数据来源: " + src,
                    ha="right", va="top", fontsize=7, color="#666666",
                    style="italic", transform=ax.transAxes)
        if ax is not None:
            for spine in ["top", "right"]:
                if spine in ax.spines:
                    ax.spines[spine].set_visible(False)
            ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.5)
            ax.set_axisbelow(True)
            ax.tick_params(colors="#333333", labelsize=8)
        return fig

    def _data_labels_bar(self, ax, values, fmt=".1f"):
        """Professional data labels for bar charts"""
        max_val = max(abs(v) for v in values if v is not None) if values else 1
        offset = max_val * 0.02
        for i, v in enumerate(values):
            if v is not None:
                ax.text(i, v + offset, format(v, fmt),
                       ha="center", va="bottom" if v >= 0 else "top",
                       fontsize=7, color="#333333")

    
    def generate_all(self, data=None):
        """为报告类型生成所有图表，使用实时数据。

        R51（2026-08-02）：返回 (chart_paths, template_flags)——
        template_flags: {chart_id: bool}，True 表示该图用模板数据（非实时）。
        让报告能标注"示意/数据不足"，防止模板图冒充真实证据（保护图表质量）。
        """
        data = data or {}
        templates = CHART_TEMPLATES.get(self.report_type, CHART_TEMPLATES["listed_company"])
        chart_paths = {}
        template_flags = {}
        chart_failures = {}  # P1: 显式标记生成失败的图表，供 gate 读取

        # 检查是否有实时数据源
        has_real_data = bool(data.get("sources") and any(
            v == "ok" for v in data["sources"].values()
        ))

        # 从 data_pipeline 的 chart_data 提取已格式化的数据
        pipeline_chart_data = data.get("chart_data", {})

        def _classify(tmpl, path):
            if path:
                chart_paths[tmpl["id"]] = path
                return True
            logger.info("Chart %s skipped: insufficient real data", tmpl["id"])
            chart_failures[tmpl["id"]] = "insufficient_data"
            return False

        def _prep_payload(tmpl):
            chart_data = self._extract_real_data(tmpl["id"], pipeline_chart_data, data)
            if chart_data is None and tmpl["id"] in pipeline_chart_data:
                chart_data = pipeline_chart_data[tmpl["id"]]
            return tmpl, chart_data, bool(chart_data is None)

        _use_pool = (os.environ.get("CHART_PARALLEL", "1").lower() in ("1", "true", "yes")
                     and len(templates) >= 4)
        if _use_pool:
            # P3-audit 2026-08-24：12 张串行 matplotlib → 进程池并行（渲染 CPU 密集）。
            # 任何池化异常自动回退串行，保证功能等价。
            try:
                from concurrent.futures import ProcessPoolExecutor, as_completed
                payloads = []
                for tmpl in templates:
                    _t, _cd, _is_tmpl = _prep_payload(tmpl)
                    payloads.append((_t, _cd, has_real_data, self.report_type,
                                     self.style, str(self.output_dir)))
                maxw = int(os.environ.get("CHART_PARALLEL_WORKERS", "4"))
                with ProcessPoolExecutor(max_workers=max(1, min(maxw, len(payloads)))) as ex:
                    fut_map = {ex.submit(_render_chart_task, pl): pl[0]["id"] for pl in payloads}
                    id2tmpl = {t["id"]: t for t in templates}
                    id2tmpl_flag = {pl[0]["id"]: pl[1] is None for pl in payloads}
                    for fut in as_completed(fut_map):
                        cid = fut_map[fut]
                        try:
                            path = fut.result(timeout=240)
                        except Exception as e:
                            logger.warning("Chart %s pool render failed: %s", cid, str(e)[:80])
                            path = None
                        _classify(id2tmpl[cid], path)
                        if path:
                            template_flags[cid] = id2tmpl_flag[cid]
            except Exception as pool_err:
                logger.warning("chart process pool unavailable (%s), fallback serial",
                               str(pool_err)[:80])
                _use_pool = False
        if not _use_pool:
            for tmpl in templates:
                # 尝试从 data_pipeline chart_data 映射实时数据
                chart_data = self._extract_real_data(tmpl["id"], pipeline_chart_data, data)
                # 如果映射失败，直接从 chart_data 中按 chart_id 查找
                if chart_data is None and tmpl["id"] in pipeline_chart_data:
                    chart_data = pipeline_chart_data[tmpl["id"]]
                # R51：判断该图是否用了真实数据（chart_data 非空且来自 pipeline）
                is_template = chart_data is None
                path = self._generate_chart(tmpl, data=chart_data, has_real_data=has_real_data)
                if _classify(tmpl, path):
                    template_flags[tmpl["id"]] = is_template

        # P1: 将失败标记写入 data context，供 gate 区分"静默缺失"和"声明缺失"
        data["chart_failures"] = chart_failures

        # Determine if real data was actually pulled from data_pipeline
        pipeline_chart_data = data.get("chart_data", {})
        # Real data means at least one source returned data AND we have chart_data
        used_real_data = bool(
            has_real_data
            and pipeline_chart_data
            and any(k in pipeline_chart_data for k in DATA_PIPELINE_CHART_MAP)
        )
        source_label = "real" if used_real_data else "template"
        logger.info("Generated %d/%d charts for %s (data=%s)",
                     len(chart_paths), len(templates), self.report_type, source_label)
        return chart_paths, template_flags

    def _safe_float(self, v) -> float:
        """安全转换数值，兼容 akshare 中文单位字符串"""
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", "").replace(" ", "")
        if not s or s in ("--", "-", "nan", "None"):
            return 0.0
        mult = 1.0
        for unit, m in [("万亿", 1e12), ("千亿", 1e11), ("百亿", 1e10), ("十亿", 1e9),
                        ("亿", 1e8), ("千万", 1e7), ("百万", 1e6), ("万", 1e4)]:
            if unit in s:
                mult = m
                s = s.replace(unit, "")
                break
        try:
            return float(s) * mult
        except ValueError:
            return 0.0

    def _extract_real_data(self, chart_id, pipeline_chart_data, full_data):
        """从 data_pipeline 输出提取指定图表的实时数据 - V2: 自动格式转换"""
        # 方法0: 兼容 DataCollectorV5 的 fig_* 键
        # fig_revenue_trend / fig_profitability → revenue_structure / profit_margin / financial_trends
        fig_map = {
            "revenue_structure": ["fig_revenue_trend", "fig_business_segments"],
            "profit_margin": ["fig_profitability", "fig_revenue_trend"],
            "financial_trends": ["fig_revenue_trend", "fig_profitability"],
            "valuation_peers": ["fig_valuation", "fig_peer_comparison"],
            "market_position": ["fig_peer_comparison", "fig_industry_board"],
            "business_segments": ["fig_business_segments", "fig_revenue_trend"],
            "cash_flow": ["fig_revenue_trend"],
            "balance_sheet": ["fig_revenue_trend"],
            "growth_drivers": ["fig_revenue_trend"],
            "valuation_history": ["fig_valuation"],
            "capital_flow": ["fig_capital_flow"],
            "peer_comparison": ["fig_peer_comparison"],
            "competitive_landscape": ["fig_peer_comparison"],
            "consensus_vs_deviation": ["fig_revenue_trend"],
            "decision_gate": ["fig_revenue_trend"],
            "management_quality": ["fig_revenue_trend"],
            "moat_analysis": ["fig_revenue_trend", "fig_peer_comparison"],
            "governance_esg": ["fig_revenue_trend"],
            "dcf_sensitivity": ["fig_valuation"],
            "catalyst_timeline": ["fig_revenue_trend"],
            "industry_chain": ["fig_peer_comparison"],
            "market_size": ["fig_market_size_global", "fig_market_size_china"],
            "tech_trend": ["fig_tech_segments", "fig_growth_drivers"],
            "policy_impact": ["fig_growth_drivers"],
            "business_model": ["fig_business_model"],
            "growth_metrics": ["fig_growth_drivers", "fig_revenue_trend"],
            "competitive_edge": ["fig_competitive_landscape", "fig_market_positioning"],
            "market_opportunity": ["fig_market_size_global", "fig_market_size_china"],
            "market_share": ["fig_market_size_china"],
            # 2026-08-01 修复：SAC chart_config 使用 fig_* id（unlisted/industry_deep）
            # 补充 fig_* 前缀映射，让 _extract_real_data(fig_xxx) 能命中数据键
            "fig_business_model": ["fig_business_model", "fig_revenue_trend"],
            "fig_market_size": ["fig_market_size_global", "fig_market_size_china"],
            "fig_market_positioning": ["fig_market_positioning", "fig_competitive_landscape", "fig_market_size_global"],
            "fig_growth_drivers": ["fig_growth_drivers", "fig_revenue_trend"],
            "fig_competitive_landscape": ["fig_competitive_landscape", "fig_peer_comparison"],
            "fig_financial_trends": ["fig_revenue_trend", "fig_profitability"],
            "fig_funding_history": ["fig_funding_history", "fig_valuation"],
            "fig_industry_chain": ["fig_industry_chain", "fig_peer_comparison"],
            "fig_supply_demand": ["fig_revenue_trend", "fig_market_size_global"],
            "fig_profit_pool": ["fig_revenue_trend", "fig_profitability"],
            "fig_tech_trend": ["fig_tech_trend", "fig_tech_segments", "fig_growth_drivers"],
            "fig_tech_segments": ["fig_tech_segments", "fig_market_size_china"],
            "fig_policy_impact": ["fig_growth_drivers", "fig_market_size_china"],
            "fig_peer_comparison": ["fig_peer_comparison", "fig_competitive_landscape"],
            "fig_life_cycle": ["fig_revenue_trend", "fig_market_size_global"],
            # 2026-08-01 补全：industry_deep 的 fig_* 数据键映射
            "fig_market_size_global": ["fig_market_size_global"],
            "fig_market_size_china": ["fig_market_size_china"],
            "fig_market_share": ["fig_market_share", "fig_market_size_china"],
            "unlisted_threat_map": ["unlisted_threat_map", "fig_players"],
            "fig_cash_flow": ["fig_revenue_trend", "fig_profitability"],
            "fig_profit_margin": ["fig_revenue_trend", "fig_profitability"],
            "fig_segment_analysis": ["fig_business_segments", "fig_revenue_trend"],
            # R85（2026-08-07 P0-2）：decision_memo 图集兜底映射。
            # fig_production_path（生产主体三选）/ fig_roadmap（执行路线图）属
            # "内部规划/测算"类数据（SAC source=内部测算/内部规划），无外部真实数据源；
            # 从可用测算类键（fig_revenue_trend / fig_market_size_*）兜底取值。
            # 注意：当前渲染器未实现 flow/timeline 类型，这两图允许模板降级
            # （[示意图-数据不足]），不要求真实数据；data_enrichment R85 宽容阈值
            # （decision_memo min 4/6）已保证其缺失不会把图集整体拖入 insufficient。
            "fig_production_path": ["fig_revenue_trend", "fig_market_size_global"],
            "fig_roadmap": ["fig_revenue_trend", "fig_market_size_china"],
        }
        for fid in fig_map.get(chart_id, []):
            raw = pipeline_chart_data.get(fid)
            # P0: 兼容 data_enrichment 复合结构 {"data": {...}, "unit": "...", "note": "..."}
            _enrich_extra = {}
            if raw and isinstance(raw, dict) and "data" in raw:
                if raw.get("unit"):
                    _enrich_extra["unit"] = raw["unit"]
                if raw.get("note"):
                    _enrich_extra["note"] = raw["note"]
                raw = raw["data"]
            if raw and isinstance(raw, dict):
                # 扁平 dict 快速路径：{label: value} 或 {year: value}（值全为标量）
                # 覆盖 fig_market_size_global/china、fig_market_share 等扁平数据
                # 排除需要双序列的图（financial_trends/supply_demand 需 revenue+profit）
                # 2026-08-02 修复：无前缀 financial_trends（listed_company 模板 id）也需双序列
                _dual_need = chart_id in ("financial_trends", "fig_financial_trends", "fig_supply_demand")
                _all_scalar = all(not isinstance(v, dict) for v in raw.values())
                if _all_scalar and not _dual_need:
                    _flat = {k: v for k, v in raw.items() if not str(k).startswith("_")}
                    if len(_flat) >= 2 and any(self._safe_float(v) != 0 for v in _flat.values()):
                        return {**{"labels": list(_flat.keys()),
                                "values": [self._safe_float(v) for v in _flat.values()]}, **_enrich_extra}
                # akshare annual: {year: {revenue, net_profit, gross_margin, ...}}
                years = [k for k in raw.keys() if str(k).isdigit() and 2000 <= int(k) <= 2030]
                if years:
                    years = sorted(years, key=int)
                    def _series(key):
                        vals = []
                        for y in years:
                            v = raw[y].get(key) if isinstance(raw[y], dict) else None
                            vals.append(self._safe_float(v))
                        return vals
                    def _first_nonzero(*series):
                        for s in series:
                            if any(v != 0 for v in s):
                                return s
                        return series[0] if series else []
                    if chart_id == "revenue_structure":
                        return {"labels": years, "values": _first_nonzero(
                            _series("revenue"), _series("营业收入"), _series("营业总收入"), _series("营收"))}
                    if chart_id == "profit_margin":
                        return {"labels": years, "values": _first_nonzero(
                            _series("net_profit"), _series("净利润"), _series("归母净利润"))}
                    if chart_id == "financial_trends":
                        return {"labels": years,
                                "revenue": _first_nonzero(_series("revenue"), _series("营业收入"), _series("营业总收入")),
                                "profit": _first_nonzero(_series("net_profit"), _series("净利润"), _series("归母净利润"))}
                    # 2026-08-01 修复：fig_* 财务趋势图（SAC fig_financial_trends）
                    # dual_axis 需要 revenue+profit 双序列，不能走通用 fallback 单序列
                    if chart_id in ("fig_financial_trends", "fig_supply_demand"):
                        # 兼容两种数据格式：
                        #  嵌套 {year: {revenue, net_profit}}  → _series()
                        #  扁平 {year: value}                  → 直接取值
                        rev = _first_nonzero(_series("revenue"), _series("营业收入"), _series("营业总收入"))
                        prof = _first_nonzero(_series("net_profit"), _series("净利润"), _series("归母净利润"))
                        # 扁平格式：fig_revenue_trend {year: val} / fig_profitability {year: val}
                        rev_flat = [raw.get(str(y)) for y in years] if isinstance(raw, dict) else []
                        prof_flat = []
                        pdata = pipeline_chart_data.get("fig_profitability")
                        if isinstance(pdata, dict):
                            prof_flat = [pdata.get(str(y), pdata.get(str(y)[:4])) for y in years]
                        if not any(rev) and any(x is not None for x in rev_flat):
                            rev = [self._safe_float(x) for x in rev_flat]
                        if not any(prof) and any(x is not None for x in prof_flat):
                            prof = [self._safe_float(x) for x in prof_flat]
                        if any(rev) or any(prof):
                            return {"labels": years, "revenue": rev, "profit": prof}
                        return {"labels": years, "values": rev or prof}
                    # fig_competitive_landscape（bar_cluster 需要多组 series）
                    if chart_id == "fig_competitive_landscape":
                        rev = _first_nonzero(_series("revenue"), _series("营业收入"))
                        prof = _first_nonzero(_series("net_profit"), _series("净利润"))
                        if any(rev) or any(prof):
                            return {"labels": years,
                                    "values": [rev, prof],
                                    "series": ["营收(亿)", "净利(亿)"]}
                    # fig_profit_pool：盈利池（多环节利润率）
                    if chart_id == "fig_profit_pool":
                        gm = _first_nonzero(_series("gross_margin"), _series("销售毛利率"))
                        np = _first_nonzero(_series("net_margin"), _series("净利润率"))
                        if any(gm) or any(np):
                            return {"labels": years, "values": [gm, np], "series": ["毛利率", "净利率"]}
                    # 衍生图表：同一份财务数据推导多张图（投行密度）
                    if chart_id == "growth_drivers":
                        return {"labels": years, "values": _first_nonzero(
                            _series("revenue"), _series("营业收入"))}
                    if chart_id == "cash_flow":
                        return {"labels": years, "values": _first_nonzero(
                            _series("net_profit"), _series("净利润"))}
                    if chart_id == "balance_sheet":
                        return {"labels": years, "values": _first_nonzero(
                            _series("asset_liability_ratio"), _series("资产负债率"))}
                    if chart_id == "decision_gate":
                        return {"labels": years, "values": _first_nonzero(
                            _series("roe"), _series("净资产收益率"))}
                    if chart_id == "consensus_vs_deviation":
                        return {"labels": years, "values": _first_nonzero(
                            _series("revenue"), _series("营业收入"))}
                    if chart_id == "management_quality":
                        return {"labels": years, "values": _first_nonzero(
                            _series("roe"), _series("净资产收益率"))}
                    if chart_id == "governance_esg":
                        return {"labels": years, "values": _first_nonzero(
                            _series("asset_liability_ratio"), _series("资产负债率"))}
                    if chart_id == "catalyst_timeline":
                        return {"labels": years, "values": _first_nonzero(
                            _series("revenue"), _series("营业收入"))}
                # flat dict {year: value} or {label: value}
                if all(str(k).isdigit() and 2000 <= int(k) <= 2030 for k in raw.keys()):
                    keys = sorted(raw.keys(), key=int)
                    return {**{"labels": keys, "values": [self._safe_float(raw[k]) for k in keys]}, **_enrich_extra}
                if "labels" in raw and "values" in raw:
                    return {**raw, **_enrich_extra}
                # flat dict {label: value}（分部占比/资金流/市场结构）
                flat_vals = {k: self._safe_float(v) for k, v in raw.items() if not isinstance(v, dict) and not str(k).startswith("_")}
                if len(flat_vals) >= 2 and any(v != 0 for v in flat_vals.values()):
                    return {**{"labels": list(flat_vals.keys()), "values": list(flat_vals.values())}, **_enrich_extra}
                # fig_peer_comparison: {company: {pe, mcap, ...}} → scatter 格式
                if chart_id == "valuation_peers" and all(isinstance(v, dict) for v in raw.values()):
                    names = list(raw.keys())
                    return {"peers": names,
                            "pb": [self._safe_float(raw[n].get("pb", 0)) for n in names],
                            "pe_ttm": [self._safe_float(raw[n].get("pe", raw[n].get("pe_ttm", 0))) for n in names]}
                # fig_peer_comparison → pie 格式（按市值占比）
                if chart_id == "market_position" and all(isinstance(v, dict) for v in raw.values()):
                    names = list(raw.keys())
                    mcaps = [self._safe_float(raw[n].get("mcap", raw[n].get("market_cap", 0))) for n in names]
                    if any(m > 0 for m in mcaps):
                        return {"labels": names, "values": mcaps}
                if chart_id == "valuation_peers" and "peers" in raw:
                    return raw
                if chart_id == "market_position" and ("labels" in raw or "peers" in raw):
                    return raw
                # fig_peer_comparison → bar_cluster（多组指标：营收/净利/PE）
                if chart_id in ("competitive_landscape", "peer_comparison") and all(isinstance(v, dict) for v in raw.values()):
                    names = list(raw.keys())
                    pe_vals = [self._safe_float(raw[n].get("pe", raw[n].get("pe_ttm", 0))) for n in names]
                    mcap_vals = [self._safe_float(raw[n].get("mcap", raw[n].get("market_cap", 0))) / 10000 for n in names]
                    return {"labels": names, "values": [pe_vals, mcap_vals], "series": ["PE", "市值(万亿)"]}
                # fig_revenue_trend → radar（多维财务健康度，0-10 打分）
                if chart_id == "moat_analysis":
                    raw2 = pipeline_chart_data.get("fig_revenue_trend", pipeline_chart_data.get("fig_profitability"))
                    if raw2 and isinstance(raw2, dict):
                        years2 = sorted([k for k in raw2.keys() if str(k).isdigit() and 2000 <= int(k) <= 2030], key=int)
                        if len(years2) >= 3:
                            last3 = years2[-3:]
                            def _series3(key):
                                vals = []
                                for y in last3:
                                    v = raw2[y].get(key) if isinstance(raw2[y], dict) else None
                                    vals.append(self._safe_float(v))
                                return vals
                            rev = _series3("revenue")
                            prof = _series3("net_profit")
                            gm = _series3("gross_margin")
                            roe = _series3("roe")
                            debt = _series3("asset_liability_ratio")
                            # 归一化到 0-10
                            def _norm(vals, scale=1.0):
                                m = max(abs(v) for v in vals) if any(vals) else 1
                                return [min(10, abs(v) / m * 10) for v in vals]
                            return {"labels": ["成长性", "盈利质量", "毛利率", "ROE", "财务健康"],
                                    "values": _norm(rev)}
                if chart_id == "industry_chain":
                    raw3 = pipeline_chart_data.get("fig_peer_comparison")
                    if raw3 and isinstance(raw3, dict) and all(isinstance(v, dict) for v in raw3.values()):
                        names = list(raw3.keys())
                        mcaps = [self._safe_float(raw3[n].get("mcap", raw3[n].get("market_cap", 0))) for n in names]
                        if any(m > 0 for m in mcaps):
                            total = sum(mcaps) or 1
                            return {"labels": names, "values": [round(m / total * 100, 1) for m in mcaps]}
        # 方法1: 直接查找映射
        for pipe_key, mapping in DATA_PIPELINE_CHART_MAP.items():
            if mapping["chart_id"] == chart_id and pipe_key in pipeline_chart_data:
                raw = pipeline_chart_data[pipe_key]
                if isinstance(raw, dict):
                    # Convert year->value dicts to labels/values format
                    keys = list(raw.keys())
                    # Check if keys look like years (e.g., "2021", "2022E")
                    if keys and all(k.startswith("20") or k.startswith("19") for k in keys if isinstance(k, str)):
                        # Filter out metadata keys
                        data_keys = [k for k in keys if not k.startswith("_")]
                        if data_keys:
                            return {
                                "labels": data_keys,
                                "values": [self._safe_float(raw[k]) for k in data_keys]
                            }
                    # If already has labels/values, return as-is
                    if "labels" in raw and "values" in raw:
                        return raw
                    # For market_share/valuation: return as-is (they have labels/values already)
                    if "peers" in raw or "labels" in raw:
                        return raw
                    return raw
        # 方法2: 从前面的 financials 提取
        if chart_id == "revenue_structure":
            fin = full_data.get("financials", {})
            rev = fin.get("revenue", {})
            if rev and isinstance(rev, dict):
                return {"labels": list(rev.keys()), "values": [float(v) for v in rev.values()]}
        if chart_id == "profit_margin":
            fin = full_data.get("financials", {})
            prof = fin.get("profit", {})
            if prof and isinstance(prof, dict):
                return {"labels": list(prof.keys()), "values": [float(v) for v in prof.values()]}
        if chart_id == "financial_trends":
            fin = full_data.get("financials", {})
            rev = fin.get("revenue", {})
            prof = fin.get("profit", {})
            if rev and prof:
                labels = sorted(set(list(rev.keys()) + list(prof.keys())))
                return {
                    "labels": labels,
                    "revenue": [float(rev.get(y, 0)) for y in labels],
                    "profit": [float(prof.get(y, 0)) for y in labels],
                }
    
    def _generate_chart(self, tmpl, data=None, has_real_data=False):

        cid = tmpl["id"]
        ctype = tmpl["type"]
        title = tmpl["title"]
        colors = self._get_style_colors()
        
        fig = None
        try:
            if ctype == "bar":
                fig = self._bar_chart(tmpl, colors, data)
            elif ctype == "line":
                fig = self._line_chart(tmpl, colors, data)
            elif ctype == "pie":
                fig = self._pie_chart(tmpl, colors, data)
            elif ctype == "dual_axis":
                fig = self._dual_axis(tmpl, colors, data)
            elif ctype == "bar_cluster":
                fig = self._bar_cluster(tmpl, colors, data)
            elif ctype == "bar_line":
                fig = self._bar_line(tmpl, colors, data)
            elif ctype == "scatter":
                fig = self._scatter(tmpl, colors, data)
            elif ctype == "waterfall":
                fig = self._waterfall(tmpl, colors, data)
            elif ctype == "radar":
                fig = self._radar(tmpl, colors, data)
            elif ctype == "table":
                fig = self._table_chart(tmpl, colors, data)
            
            if fig:
                path = str(self.output_dir / (cid + ".png"))
                self._add_professional_finish(fig, fig.axes[0] if fig.axes else None, tmpl)
                fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
                plt.close(fig)
                size = os.path.getsize(path)
                logger.info("  %s: %s (%.1f KB)", cid, title, size/1024)
                return path
        except Exception as e:
            logger.warning("  %s failed: %s", cid, e)
            try: plt.close(fig)
            except Exception:
                pass  # Layer 5: bare except replaced with Exception
        
    
    def _bar_chart(self, tmpl, colors, data=None):

        if data and "labels" in data and "values" in data:
            x = data["labels"]
            y = data["values"]
        else:
            return None
        fig, ax = plt.subplots(figsize=(6.5, 3.8))
        ax.bar(x, y, color=colors[0], width=0.55, edgecolor="white")
        ax.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=12)
        ax.set_ylabel("金额（亿元）", fontsize=9)
        for i, v in enumerate(y):
            ax.text(i, v+max(y)*0.02, "%.1f" % v, ha="center", fontsize=8, color=colors[0])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(labelsize=8)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7)
        plt.tight_layout()
        return fig
    
    def _line_chart(self, tmpl, colors, data=None):

        if not data or "labels" not in data or "values" not in data:
            return None
        x = np.arange(len(data["labels"]))
        labels_list = data["labels"]
        y = data["values"]
        fig, ax = plt.subplots(figsize=(6.5, 3.8))
        ax.plot(x, y, "o-", color=colors[0], linewidth=2, markersize=5, label="趋势")
        ax.set_xticks(x)
        ax.set_xticklabels(labels_list, fontsize=8)
        ax.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=12)
        ax.legend(fontsize=8, frameon=False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(labelsize=8)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7)
        plt.tight_layout()
        return fig
    
    def _dual_axis(self, tmpl, colors, data=None):

        if not data or "labels" not in data:
            return None
        x = data["labels"]
        revenue = data.get("revenue")
        profit = data.get("profit")
        if revenue is None or profit is None:
            return None
        fig, ax1 = plt.subplots(figsize=(6.5, 3.8))
        ax1.bar(x, revenue, color=colors[0], alpha=0.85, width=0.5, label="营收")
        ax2 = ax1.twinx()
        ax2.plot(x, profit, "o-", color=colors[1], linewidth=2, label="净利润")
        ax1.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=12)
        ax1.set_ylabel("营收（亿元）", fontsize=9, color=colors[0])
        ax2.set_ylabel("净利润（亿元）", fontsize=9, color=colors[1])
        l1, la1 = ax1.get_legend_handles_labels()
        l2, la2 = ax2.get_legend_handles_labels()
        ax1.legend(l1+l2, la1+la2, fontsize=8, frameon=False)
        ax1.spines["top"].set_visible(False); ax1.tick_params(labelsize=8); ax2.tick_params(labelsize=8)
        plt.setp(ax1.get_xticklabels(), rotation=30, ha="right", fontsize=7)
        plt.tight_layout()
        return fig
    
    def _bar_cluster(self, tmpl, colors, data=None):

        fig, ax = plt.subplots(figsize=(6.5, 3.8))
        if not data or "labels" not in data or "values" not in data:
            plt.close(fig)
            return None
        labels = data["labels"]
        raw_vals = data["values"]
        # 兼容两种形态：扁平列表（单组）或嵌套列表（多序列）
        if raw_vals and isinstance(raw_vals[0], list):
            series = raw_vals
        else:
            series = [raw_vals]
        n_series = len(series)
        width = 0.8 / max(n_series, 1)
        x = np.arange(len(labels))
        s_names = data.get("series") or []
        for i, s_vals in enumerate(series):
            if len(s_vals) != len(labels):
                continue
            ax.bar(x + (i - n_series / 2 + 0.5) * width, s_vals, width,
                   color=colors[i % len(colors)],
                   label=(s_names[i] if i < len(s_names) else f"组{i+1}"))
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=12)
        ax.legend(fontsize=7, frameon=False)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False); ax.tick_params(labelsize=8)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7)
        plt.tight_layout()
        return fig
    
    def _pie_chart(self, tmpl, colors, data=None):

        fig, ax = plt.subplots(figsize=(5.5, 4))
        if data and "labels" in data and "values" in data:
            labels = data["labels"]
            vals = data["values"]
        else:
            plt.close(fig)
            return None
        wedges, texts, autotexts = ax.pie(vals, labels=labels, autopct="%1.0f%%", 
                                           colors=colors[:len(labels)], startangle=90,
                                           textprops={"fontsize": 8})
        ax.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=12)
        plt.tight_layout()
        return fig
    
    def _scatter(self, tmpl, colors, data=None):

        if data and "peers" in data:
            names = data.get("peers", [])
            x = data.get("pb", [])
            y = data.get("pe_ttm", [])
        elif data and "labels" in data and "values" in data:
            names = data["labels"]
            x = list(range(len(names)))
            y = data["values"]
        else:
            return None
        fig, ax = plt.subplots(figsize=(6.5, 4.5))
        c = [colors[1]] + [colors[0]] * (len(names) - 1)
        ax.scatter(x, y, c=c, s=80, zorder=3)
        for xi, yi, ni in zip(x, y, names):
            ax.annotate(ni, (xi, yi), fontsize=7, ha="center", va="bottom")
        ax.set_xlabel("市净率(PB)", fontsize=9); ax.set_ylabel("市盈率(PE)", fontsize=9)
        ax.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=12)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False); ax.tick_params(labelsize=8)
        plt.tight_layout()
        return fig
    
    def _waterfall(self, tmpl, colors, data=None):

        if not data or "labels" not in data or "values" not in data:
            return None
        cat = data["labels"]; vals = data["values"]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(cat, vals, color=colors[:len(cat)], width=0.55, edgecolor="white")
        ax.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=12)
        ax.set_ylabel("价值占比(%)", fontsize=9)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False); ax.tick_params(labelsize=8)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7)
        plt.tight_layout()
        return fig
    
    def _radar(self, tmpl, colors, data=None):

        fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
        cat = data.get("labels") if data else None
        vals = np.array(data.get("values")) if data and data.get("values") else np.array([])
        if not cat or len(vals) < 3:
            plt.close(fig)
            return None
        N = len(cat); angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
        ax.plot(angles + angles[:1], np.concatenate((vals, [vals[0]])), "o-", color=colors[0], linewidth=2)
        ax.fill(angles + angles[:1], np.concatenate((vals, [vals[0]])), alpha=0.1, color=colors[0])
        ax.set_xticks(angles); ax.set_xticklabels(cat, fontsize=9)
        ax.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=20)
        ax.set_ylim(0, 10)
        plt.tight_layout()
        return fig
    
    def _bar_line(self, tmpl, colors, data=None):

        if not data or "labels" not in data or "values" not in data:
            return None
        x = np.arange(len(data["labels"]))
        labels = data["labels"]
        vals = data["values"]
        fig, ax = plt.subplots(figsize=(6.5, 3.8))
        ax.bar(x, vals, 0.55, color=colors[0], label=tmpl.get("title", ""))
        ax.set_xticks(x + 0.2); ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=12)
        ax.legend(fontsize=8, frameon=False)
        ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False); ax.tick_params(labelsize=8)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7)
        plt.tight_layout()
        return fig

    def _table_chart(self, tmpl, colors, data=None):
        """表格图（如非上市玩家威胁地图）。无实时数据时生成示意表，标注为模板/示意。"""
        default_headers = ["名称", "成立年份", "注册资本", "技术水平", "威胁度", "依据"]
        if data and "headers" in data and "rows" in data:
            headers = data["headers"]
            rows = data["rows"]
        else:
            headers = default_headers
            rows = []
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.axis("off")
        ax.set_title(tmpl["title"], fontsize=12, fontweight="bold", color=colors[0], pad=12)
        if rows:
            cell_text = [[str(c) for c in r] for r in rows]
            table = ax.table(cellText=cell_text, colLabels=headers, loc="center", cellLoc="left")
        else:
            # 示意表：仅表头 + 空行（数据不足保护，不编造玩家数据）
            empty_row = [""] * len(headers)
            table = ax.table(cellText=[empty_row], colLabels=headers, loc="center", cellLoc="left")
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.4)
        for (r, c), cell in table.get_celld().items():
            if r == 0:
                cell.set_facecolor(colors[0])
                cell.set_text_props(color="white", fontweight="bold")
            cell.set_edgecolor("#CCCCCC")
        if not rows:
            ax.text(0.5, 0.12, "示意：无权威数据时须在报告中显式标注数据缺口（FP2诚实边界）",
                    ha="center", va="center", fontsize=8, color="#999999", transform=ax.transAxes)
        plt.tight_layout()
        return fig

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cp = ChartPipeline("listed_company", "cicc", "output/charts")
    paths, _tf = cp.generate_all()
    print("\nGenerated %d charts:" % len(paths))
    for k, v in paths.items():
        s = os.path.getsize(v) if os.path.exists(v) else 0
        print("  %s: %s (%.1f KB)" % (k, v, s/1024))
