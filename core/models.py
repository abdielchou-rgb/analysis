"""V51 core models — all data models for the analyst system.

架构收敛 V51.4: 计算引擎模型已从 V30 schema 迁移到此。
所有 core/compute/ 模块直接从 core.models 导入，不再依赖 V30。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ReportType(str, Enum):
    EARNINGS_NOTES = "earnings_notes"
    INDUSTRY_DEEP = "industry_deep"
    LISTED_COMPANY = "listed_company"
    UNLISTED_COMPANY = "unlisted_company"
    IPO_ANALYSIS = "ipo_analysis"
    EVENT_REVIEW = "event_review"


class ReportDepth(str, Enum):
    BRIEF = "brief"
    STANDARD = "standard"
    DEEP = "deep"


class Direction(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"


class InputMode(str, Enum):
    STRUCTURED = "A"
    SEMI_STRUCTURED = "B"
    FALLBACK = "C"


class EvidenceLevel(str, Enum):
    COMPUTED = "L0_computed"
    FILING = "L1_filing"
    MEDIA = "L2_media"
    ESTIMATE = "L3_estimate"
    ANALYST = "L4_analyst"
    INFERENCE = "L5_inference"
    PENDING = "L9_pending"


class SectionType(str, Enum):
    JUDGMENT = "judgment"
    EVIDENCE = "evidence"
    COUNTER = "counter"
    TRANSITION = "transition"
    SYNTHESIS = "synthesis"


class EditingType(str, Enum):
    WEAK_EVIDENCE = "weak_evidence"
    BIASED_JUDGMENT = "biased_judgment"
    LOGIC_GAP = "logic_gap"
    STYLE_MISMATCH = "style_mismatch"
    STRUCTURE = "structure"
    VERBOSE = "verbose"


@dataclass
class WritingBrief:
    asset: str = ""
    asset_code: str = ""
    asset_market: str = ""
    report_type: ReportType = ReportType.LISTED_COMPANY
    input_mode: InputMode = InputMode.FALLBACK
    core_thesis_direction: Direction = Direction.NEUTRAL
    core_thesis_point: str = ""
    market_consensus: str = ""
    our_view: str = ""
    key_variable: str = ""
    time_window: str = "12 months"
    report_depth: str = "standard"
    required_sections: list[str] = field(default_factory=list)
    emphasis_points: list[str] = field(default_factory=list)
    source_materials: list[str] = field(default_factory=list)
    analyst_viewpoints: dict[str, str] = field(default_factory=dict)
    style_profile: str = "cicc"
    target_length: str = "10_pages"
    data_requirements: list[str] = field(default_factory=list)
    analyst_signature: str = ""
    analyst_notes: str = ""
    created_at: str = ""
    brief_id: str = ""
    hypothesis: str | None = None
    hypothesis_report: dict | None = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.brief_id:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.brief_id = f"WB_{ts}_{self.asset_code or 'UNKNOWN'}"

    def to_dict(self) -> dict:
        return {
            "asset": self.asset,
            "report_type": self.report_type.value if self.report_type else "",
            "input_mode": self.input_mode.value if self.input_mode else "C",
            "core_thesis": {
                "direction": self.core_thesis_direction.value if self.core_thesis_direction else "neutral",
                "point": self.core_thesis_point,
            },
            "style_profile": self.style_profile,
            "brief_id": self.brief_id,
            "created_at": self.created_at,
            "hypothesis": self.hypothesis,
        }

    @classmethod
    def from_dict(cls, d: dict) -> WritingBrief:
        t = d.get("core_thesis", {})
        rt = d.get("report_type", "listed_company")
        return cls(
            asset=d.get("asset", ""),
            asset_code=d.get("asset_code", ""),
            asset_market=d.get("asset_market", ""),
            report_type=ReportType(rt) if rt in ReportType._value2member_map_ else ReportType.LISTED_COMPANY,
            input_mode=InputMode(d.get("input_mode", "C")),
            core_thesis_direction=Direction(t.get("direction", "neutral")),
            core_thesis_point=t.get("point", ""),
            market_consensus=t.get("market_consensus", ""),
            our_view=t.get("our_view", ""),
            key_variable=t.get("key_variable", ""),
            time_window=t.get("time_window", "12 months"),
            style_profile=d.get("style_profile", "cicc"),
            hypothesis=d.get("hypothesis"),
            hypothesis_report=d.get("hypothesis_report"),
            analyst_signature=d.get("analyst_signature", ""),
            required_sections=d.get("required_sections", []),
            emphasis_points=d.get("emphasis_points", []),
            source_materials=d.get("source_materials", []),
            data_requirements=d.get("data_requirements", []),
            analyst_notes=d.get("analyst_notes", ""),
            brief_id=d.get("brief_id", ""),
            created_at=d.get("created_at", ""),
        )


@dataclass
class EvidenceItem:
    content: str = ""
    source: str = ""
    level: EvidenceLevel = EvidenceLevel.ESTIMATE
    support_direction: str = "neutral"
    relevance_score: float = 0.5


@dataclass
class HypothesisReport:
    hypothesis: str = ""
    supporting_evidence: list[EvidenceItem] = field(default_factory=list)
    opposing_evidence: list[EvidenceItem] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    similar_cases: list[str] = field(default_factory=list)
    suggested_confidence: str = "medium"
    summary: str = ""


@dataclass
class DataPoint:
    name: str = ""
    value: Any = None
    unit: str = ""
    source: str = ""                    # 必填：URL 或 文档路径
    access_ts: str = ""                 # 必填：ISO8601 抓取时间
    excerpt_sha256: str = ""            # 必填：原文片段 SHA256（前 200 字）
    confidence: float = 0.5             # 0-1
    scope: str = ""                     # 公司/行业/全球
    year: int | None = None
    unit: str = ""                      # 亿元/元/倍/%
    source_level: str = ""              # L1_filing / L2_media / L3_estimate / L4_analyst / L5_inference
    is_estimate: bool = False
    fiscal_year: int | None = None
    note: str = ""

    def __post_init__(self):
        """Validate provenance completeness."""
        if not self.source:
            raise ValueError(f"DataPoint {self.name}: source is required")
        if not self.access_ts:
            raise ValueError(f"DataPoint {self.name}: access_ts is required")
        if not self.excerpt_sha256:
            raise ValueError(f"DataPoint {self.name}: excerpt_sha256 is required")
        if not self.unit:
            raise ValueError(f"DataPoint {self.name}: unit is required")
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"DataPoint {self.name}: confidence must be 0-1")


@dataclass
class FinancialSummary:
    """兼容 V30 的 FinancialSummary。"""

    company: str = ""
    years: list[int] = field(default_factory=list)
    items: dict = field(default_factory=dict)
    revenue_bridge: dict | None = None
    margin_bridge: dict | None = None
    profit_quality: dict | None = None
    cash_flow: dict | None = None
    roe_decomposition: dict | None = None
    peer_comparison: dict | None = None
    three_gate: dict | None = None
    dcf_valuation: dict | None = None
    scenario_analysis: dict | None = None

    def to_markdown_table(self) -> str:
        lines = []
        headers = ["指标"] + [str(y) for y in self.years] + ["来源"]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for name, values in self.items.items():
            row = [name]
            for y in self.years:
                val = values.get(str(y), values.get(y, "N/A"))
                row.append(str(val))
            row.append("[ak]")
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)


@dataclass
class SACEntry:
    sac_id: str = ""
    name: str = ""
    applies_to: list[str] = field(default_factory=list)
    required_dimensions: list[dict] = field(default_factory=list)
    evidence_requirements: dict = field(default_factory=dict)
    forbidden_patterns: list[str] = field(default_factory=list)
    pre_workflow: list[dict] = field(default_factory=list)
    verification_rules: dict | None = None
    logic_chain: list[dict] = field(default_factory=list)  # 共识三: 因果链


@dataclass
class StyleProfile:
    style_id: str = ""
    name: str = ""
    colors: dict = field(default_factory=dict)
    typography: dict = field(default_factory=dict)
    charts: dict = field(default_factory=dict)
    writing: dict = field(default_factory=dict)
    expression_dna: dict | None = None


@dataclass
class KnowledgePackage:
    brief: WritingBrief | None = None
    data_points: list[DataPoint] = field(default_factory=list)
    financials: FinancialSummary | None = None
    sac: SACEntry | None = None
    style: StyleProfile | None = None
    bluebook_patterns: list[dict] = field(default_factory=list)
    tyc_data: dict | None = None
    data_gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)


@dataclass
class ArgumentSection:
    section_id: str = ""
    title: str = ""
    section_type: SectionType = SectionType.JUDGMENT
    thesis: str = ""
    counter_thesis: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    counter_evidence_ids: list[str] = field(default_factory=list)
    required_citations: int = 0
    data_gaps: list[str] = field(default_factory=list)
    sub_points: list[str] = field(default_factory=list)
    style_rules: list[str] = field(default_factory=list)
    has_alternative_view: bool = False


@dataclass
class ArgumentScaffold:
    brief_id: str = ""
    title: str = ""
    core_disagreement: dict = field(default_factory=dict)
    sections: list[ArgumentSection] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    analyst_confirmed: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class EditCase:
    case_id: str = ""
    report_id: str = ""
    analyst_id: str = "anonymous"
    original_text: str = ""
    correction_type: EditingType = EditingType.WEAK_EVIDENCE
    correction_action: str = ""
    corrected_text: str = ""
    report_type: str = ""
    section_type: str = ""
    style_profile: str = ""
    persisted: bool = False
    created_at: str = ""


@dataclass
class VersionRecord:
    version_id: str = ""
    brief_id: str = ""
    created_at: str = ""
    content_hash: str = ""
    source_map: dict = field(default_factory=dict)
    edits: list[dict] = field(default_factory=list)
    analyst_signature: str = ""


@dataclass
class ValidationResult:
    passed: bool = True
    dimension_check: dict | None = None
    citation_check: dict | None = None
    forbidden_check: dict | None = None
    style_deviation: dict | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Deliverable:
    report_md: str = ""
    version: VersionRecord | None = None
    validation: ValidationResult | None = None
    scaffold: ArgumentScaffold | None = None
    brief: WritingBrief | None = None
    knowledge_package: KnowledgePackage | None = None
    chart_paths: dict[str, str] = field(default_factory=dict)
    export_paths: dict[str, str] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# 计算引擎模型（V51.4 架构收敛：从 V30 schema 迁移）
# ═══════════════════════════════════════════════════════════════

# 新增：AssumptionTree（V51.6 对标130家估值模型的假设树）
# 美团模型的四层驱动因子拆解启示：
#   Layer 1: TAM → Layer 2: 渗透率 → Layer 3: 份额 → Layer 4: 变现率
# 每个层次都有历史数据验证 + 预测假设 + 增长率减速假设


@dataclass
class AssumptionNode:
    """假设树的单个节点。"""

    name: str = ""
    value: float = 0.0
    unit: str = ""
    growth_rate: float | None = None  # 同比增速
    description: str = ""
    source: str = ""  # 数据来源或假设理由
    is_historical: bool = False  # True=历史数据, False=预测假设
    confidence: str = "medium"  # high/medium/low


@dataclass
class AssumptionTree:
    """完整假设树 — 从驱动因子到财务预测，

    结构对标投行估值模型的"假设总表"：
    ├── 行业假设（TAM/渗透率/增速）
    ├── 公司假设（份额/定价/单位经济）
    ├── 利润假设（毛利率/费用率/税率）
    ├── 资本假设（WACC 逐项拆解）
    └── 终值假设（永续增长率/Exit Multiple）
    """

    # 行业层
    industry_tam: list[AssumptionNode] = field(default_factory=list)
    penetration_rate: AssumptionNode | None = None
    industry_growth: AssumptionNode | None = None

    # 公司层
    market_share: AssumptionNode | None = None
    revenue_drivers: list[AssumptionNode] = field(default_factory=list)  # 量/价/结构
    unit_economics: dict = field(default_factory=dict)  # 单位经济模型

    # 利润层
    margin_assumptions: dict = field(default_factory=dict)
    cost_drivers: list[AssumptionNode] = field(default_factory=list)
    tax_rate: float | None = None

    # 资本层（WACC 逐项拆解）
    wacc_assumptions: dict = field(default_factory=dict)
    # wacc_assumptions = {
    #   "risk_free_rate": 0.03,    # 无风险利率
    #   "equity_risk_premium": 0.06,  # 股权风险溢价
    #   "beta": 1.35,              # 贝塔系数
    #   "cost_of_equity": 0.111,   # 股权成本 = Rf + Beta * ERP
    #   "cost_of_debt": 0.03,      # 债务成本
    #   "debt_ratio": 0.0,         # 目标资本结构
    #   "wacc": 0.111,             # 加权平均资本成本
    #   "wacc_notes": "",          # 关键假设说明
    # }

    # 终值层
    terminal_growth: float | None = None
    exit_multiple: float | None = None

    # 审计信息
    created_at: str = ""
    data_quality: str = "draft"  # draft / verified / audited
    warnings: list[str] = field(default_factory=list)


@dataclass
class AnnualFinancials:
    stock_code: str = ""
    stock_name: str = ""
    fiscal_year: int = 0
    revenue: float | None = None
    net_profit: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    total_cogs: float | None = None
    operating_profit: float | None = None
    roe: float | None = None
    eps: float | None = None
    total_shares: int | None = None
    yoy_revenue: float | None = None
    yoy_net_profit: float | None = None
    cash_and_equivalents: float | None = None
    accounts_receivable: float | None = None
    inventory: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    total_equity: float | None = None
    operating_cf: float | None = None
    investing_cf: float | None = None
    financing_cf: float | None = None
    liability_to_asset: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    asset_turnover_ratio: float | None = None
    source: str = "akshare"
    data_quality: str = "unverified"

    @property
    def revenue_change_pct(self) -> float | None:
        return self.yoy_revenue

    @property
    def profit_change_pct(self) -> float | None:
        return self.yoy_net_profit


@dataclass
class CompanyProfile:
    stock_code: str = ""
    stock_name: str = ""
    industry: str | None = None
    status: str | None = None


@dataclass
class StructuredData:
    profile: CompanyProfile = field(default_factory=CompanyProfile)
    financials: list[AnnualFinancials] = field(default_factory=list)
    years_covered: list[int] = field(default_factory=list)
    quality_report: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.years_covered:
            self.years_covered = sorted([f.fiscal_year for f in self.financials])

    def get_financial(self, year: int) -> AnnualFinancials | None:
        for f in self.financials:
            if f.fiscal_year == year:
                return f
        return None


@dataclass
class RevenueBridge:
    company: str = ""
    period: str = ""
    total_revenue_growth_pct: float = 0.0
    total_revenue_change_abs: float = 0.0
    drivers: list[dict] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    confidence: str = "medium"


@dataclass
class MarginBridge:
    company: str = ""
    period: str = ""
    gross_margin_prev: float = 0.0
    gross_margin_current: float = 0.0
    gross_margin_change: float = 0.0
    drivers: list[dict] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    confidence: str = "medium"


@dataclass
class ExpenseBridge:
    company: str = ""
    period: str = ""
    expense_rates: list[dict] = field(default_factory=list)
    expense_structure_trend: str = ""
    margin_gap_trend: str = ""
    data_gaps: list[str] = field(default_factory=list)
    confidence: str = "medium"


@dataclass
class ComputedResults:
    company: str = ""
    stock_code: str = ""
    financial_summary: FinancialSummary | None = None
    revenue_bridge: RevenueBridge | None = None
    margin_bridge: MarginBridge | None = None
    expense_bridge: ExpenseBridge | None = None
    dcf_result: dict | None = None
    comparable_result: dict | None = None
    scenario_result: dict | None = None
    sotp_result: dict | None = None
    global_benchmark: dict | None = None
    numeric_gate_report: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
