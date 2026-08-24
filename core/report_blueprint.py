"""Report Blueprint System - V54
Defines structured templates for every report type.
Each blueprint specifies sections, chart requirements, and page budgets.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChartRequirement:
    chart_type: str  # bar, line, pie, waterfall, radar, scatter, heatmap, tornado
    title: str
    data_sources: list[str] = field(default_factory=list)
    annotations: list[str] = field(default_factory=list)
    position: str = "auto"  # section_id or "auto"


@dataclass
class SectionBlueprint:
    section_id: str
    title: str
    min_words: int = 300
    max_words: int = 1500
    required_charts: list[ChartRequirement] = field(default_factory=list)
    must_include: list[str] = field(default_factory=list)
    has_counter_argument: bool = False
    depth: str = "standard"  # deep / standard / brief


@dataclass  
class ReportBlueprint:
    report_type: str  # industry_deep / listed_company / unlisted_company
    style_profile: str = "cicc"
    total_pages: int = 25
    sections: list[SectionBlueprint] = field(default_factory=list)
    required_charts_total: int = 6
    
    def get_deep_sections(self) -> list[SectionBlueprint]:
        return [s for s in self.sections if s.depth == "deep"]
    
    def get_standard_sections(self) -> list[SectionBlueprint]:
        return [s for s in self.sections if s.depth == "standard"]


# ── Industry Deep Blueprint (30-50 pages) ──────────────────────────

INDUSTRY_DEEP_BLUEPRINT = ReportBlueprint(
    report_type="industry_deep",
    total_pages=35,
    required_charts_total=7,
    style_profile="cicc",
    sections=[
        SectionBlueprint(
            section_id="executive_summary",
            title="投资概要",
            min_words=500, max_words=2000,
            must_include=["investment_thesis", "core_disagreement", "key_metrics_table"],
            depth="deep",
        ),
        SectionBlueprint(
            section_id="industry_boundary",
            title="行业边界与定义",
            min_words=300, max_words=800,
            must_include=["l1_l2_l3_classification", "industry_chain_position"],
            depth="standard",
        ),
        SectionBlueprint(
            section_id="value_chain",
            title="价值链分析",
            min_words=600, max_words=1500,
            required_charts=[
                ChartRequirement("waterfall", "行业价值链分布"),
                ChartRequirement("pie", "利润池分布"),
            ],
            must_include=["8_layer_value_chain", "profit_pool_distribution"],
            depth="deep",
        ),
        SectionBlueprint(
            section_id="market_size",
            title="市场规模与增长驱动",
            min_words=600, max_words=1500,
            required_charts=[
                ChartRequirement("line", "市场规模趋势"),
                ChartRequirement("bar", "细分市场增长"),
            ],
            must_include=["top_down_bottom_up", "penetration_rate", "ceiling_analysis"],
            depth="deep",
        ),
        SectionBlueprint(
            section_id="supply_demand",
            title="供需分析",
            min_words=400, max_words=1000,
            required_charts=[
                ChartRequirement("bar", "供需平衡表"),
            ],
            must_include=["capacity_tracker", "demand_driver", "utilization_rate"],
            depth="standard",
        ),
        SectionBlueprint(
            section_id="competitive_landscape",
            title="竞争格局",
            min_words=500, max_words=1500,
            required_charts=[
                ChartRequirement("bar", "竞争格局（CR3/CR5）"),
                ChartRequirement("radar", "核心竞争要素对标"),
            ],
            must_include=["cr3_cr5", "moat_analysis", "entry_barriers"],
            has_counter_argument=True,
            depth="deep",
        ),
        SectionBlueprint(
            section_id="technology_roadmap",
            title="技术路线",
            min_words=400, max_words=1000,
            required_charts=[
                ChartRequirement("line", "技术成熟度曲线"),
            ],
            must_include=["current_tech", "next_gen", "roadmap_comparison"],
            depth="standard",
        ),
        SectionBlueprint(
            section_id="policy_regulation",
            title="政策传导分析",
            min_words=400, max_words=1000,
            must_include=["policy_industry_profit_stock_chain"],
            has_counter_argument=True,
            depth="standard",
        ),
        SectionBlueprint(
            section_id="financial_valuation",
            title="财务与估值分析",
            min_words=500, max_words=1500,
            required_charts=[
                ChartRequirement("tornado", "估值敏感性分析"),
                ChartRequirement("line", "PE Band"),
                ChartRequirement("heatmap", "DCF敏感性"),
            ],
            must_include=["peer_comparison", "dcf_valuation", "sensitivity"],
            has_counter_argument=True,
            depth="deep",
        ),
        SectionBlueprint(
            section_id="catalyst_risk",
            title="催化剂与风险",
            min_words=400, max_words=1000,
            must_include=["catalyst_calendar", "risk_matrix", "falsification_conditions"],
            has_counter_argument=True,
            depth="standard",
        ),
        SectionBlueprint(
            section_id="appendix",
            title="附录",
            min_words=200, max_words=500,
            must_include=["methodology", "data_sources", "risk_factors", "disclaimer"],
            depth="brief",
        ),
    ]
)


# ── Listed Company Blueprint (20-30 pages) ─────────────────────────

LISTED_COMPANY_BLUEPRINT = ReportBlueprint(
    report_type="listed_company",
    total_pages=25,
    required_charts_total=6,
    style_profile="cicc",
    sections=[
        SectionBlueprint(
            section_id="executive_summary",
            title="投资概要",
            min_words=500, max_words=2000,
            must_include=["rating", "target_price", "investment_thesis", "key_metrics"],
            depth="deep",
        ),
        SectionBlueprint(
            section_id="core_disagreement",
            title="核心分歧",
            min_words=400, max_words=1200,
            must_include=["market_consensus", "our_view", "key_variable", "consensus_gap_table"],
            depth="deep",
        ),
        SectionBlueprint(
            section_id="company_overview",
            title="公司概览",
            min_words=300, max_words=800,
            required_charts=[
                ChartRequirement("pie", "收入结构"),
            ],
            must_include=["business_model", "revenue_mix", "history_milestones"],
            depth="standard",
        ),
        SectionBlueprint(
            section_id="industry_context",
            title="行业位置",
            min_words=400, max_words=1000,
            required_charts=[
                ChartRequirement("bar", "市场份额"),
                ChartRequirement("line", "行业增长趋势"),
            ],
            depth="standard",
        ),
        SectionBlueprint(
            section_id="financial_analysis",
            title="财务深度分析",
            min_words=600, max_words=1500,
            required_charts=[
                ChartRequirement("line", "营收/利润趋势"),
                ChartRequirement("waterfall", "收入桥"),
                ChartRequirement("bar", "利润率趋势"),
            ],
            must_include=["segment_breakdown", "margin_trend", "cash_flow_quality"],
            depth="deep",
        ),
        SectionBlueprint(
            section_id="competitive_advantage",
            title="竞争优势",
            min_words=400, max_words=1200,
            must_include=["moat", "barriers_to_entry", "competitive_position"],
            has_counter_argument=True,
            depth="standard",
        ),
        SectionBlueprint(
            section_id="growth_drivers",
            title="增长驱动",
            min_words=400, max_words=1200,
            required_charts=[
                ChartRequirement("bar", "增长驱动因素分解"),
            ],
            must_include=["volume_price", "new_products", "geographic_expansion"],
            has_counter_argument=True,
            depth="deep",
        ),
        SectionBlueprint(
            section_id="valuation",
            title="估值分析",
            min_words=500, max_words=1500,
            required_charts=[
                ChartRequirement("heatmap", "DCF敏感性分析"),
                ChartRequirement("tornado", "估值敏感性"),
                ChartRequirement("scatter", "可比公司估值"),
            ],
            must_include=["dcf", "peer_valuation", "sensitivity_analysis"],
            has_counter_argument=True,
            depth="deep",
        ),
        SectionBlueprint(
            section_id="risk_factors",
            title="风险因素",
            min_words=300, max_words=800,
            must_include=["downside_risks", "falsification_conditions", "catalyst_calendar"],
            has_counter_argument=True,
            depth="standard",
        ),
        SectionBlueprint(
            section_id="appendix",
            title="附录",
            min_words=200, max_words=500,
            must_include=["methodology", "financial_summary", "risk_factors", "disclaimer"],
            depth="brief",
        ),
    ]
)


# ── Unlisted Company Blueprint (15-25 pages) ──────────────────────

UNLISTED_COMPANY_BLUEPRINT = ReportBlueprint(
    report_type="unlisted_company",
    total_pages=20,
    required_charts_total=5,
    sections=[
        SectionBlueprint(
            section_id="executive_summary",
            title="执行摘要",
            min_words=400, max_words=1500,
            must_include=["company_thesis", "valuation_range", "key_strengths"],
            depth="deep",
        ),
        SectionBlueprint(
            section_id="company_overview",
            title="公司全貌",
            min_words=300, max_words=800,
            required_charts=[
                ChartRequirement("pie", "业务结构"),
            ],
            must_include=["business_model", "revenue_model", "growth_stage"],
            depth="standard",
        ),
        SectionBlueprint(
            section_id="market_position",
            title="市场定位",
            min_words=400, max_words=1000,
            required_charts=[
                ChartRequirement("radar", "竞争要素雷达图"),
                ChartRequirement("bar", "市场份额测算"),
            ],
            must_include=["competitive_position", "market_share_estimation"],
            has_counter_argument=True,
            depth="deep",
        ),
        SectionBlueprint(
            section_id="financial_estimation",
            title="财务估算",
            min_words=400, max_words=1200,
            required_charts=[
                ChartRequirement("line", "营收趋势估算"),
                ChartRequirement("stacked_bar", "成本结构"),
            ],
            must_include=["revenue_estimation", "margin_estimation", "data_source_declaration"],
            depth="deep",
        ),
        SectionBlueprint(
            section_id="growth_strategy",
            title="增长战略",
            min_words=300, max_words=800,
            must_include=["expansion_plan", "competitive_response", "tam_sam_som"],
            has_counter_argument=True,
            depth="standard",
        ),
        SectionBlueprint(
            section_id="valuation_analysis",
            title="估值分析",
            min_words=400, max_words=1000,
            required_charts=[
                ChartRequirement("heatmap", "估值区间敏感性"),
                ChartRequirement("scatter", "可比公司估值"),
            ],
            must_include=["comparable_analysis", "valuation_range", "discount_factors"],
            has_counter_argument=True,
            depth="deep",
        ),
        SectionBlueprint(
            section_id="risk_assessment",
            title="风险评估",
            min_words=300, max_words=800,
            must_include=["key_risks", "mitigation_factors", "scenario_analysis"],
            has_counter_argument=True,
            depth="standard",
        ),
        SectionBlueprint(
            section_id="appendix",
            title="附录",
            min_words=200, max_words=500,
            must_include=["methodology", "data_source_declaration", "disclaimer"],
            depth="brief",
        ),
    ]
)


# ── Registry ────────────────────────────────────────────────────────

BLUEPRINT_REGISTRY = {
    "industry_deep": INDUSTRY_DEEP_BLUEPRINT,
    "listed_company": LISTED_COMPANY_BLUEPRINT,
    "unlisted_company": UNLISTED_COMPANY_BLUEPRINT,
}

def get_blueprint(report_type: str) -> Optional[ReportBlueprint]:
    return BLUEPRINT_REGISTRY.get(report_type)


if __name__ == "__main__":
    import json
    for rtype, bp in BLUEPRINT_REGISTRY.items():
        print(f"\n{'='*60}")
        print(f"Blueprint: {rtype} ({bp.total_pages}p, {bp.required_charts_total} charts)")
        print(f"{'='*60}")
        for s in bp.sections:
            charts = f" [{len(s.required_charts)} charts]" if s.required_charts else ""
            depth_mark = " ★" if s.depth == "deep" else ""
            print(f"  {s.section_id}: {s.title}{depth_mark}{charts}")
