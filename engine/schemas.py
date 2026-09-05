"""
Pydantic 意图解析契约 — 强制约束 LLM 提取的投研假设参数结构。
LLM 输出 JSON 时必须通过此 Schema 校验，否则拒绝进入计算层。
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ─── DCF ────────────────────────────────────────────────────────────────────


class DCFAssumptions(BaseModel):
    """DCF 估值假设 — LLM 提取的结构化参数"""

    ticker: str = Field(..., description="标的代码")
    company_name: str = Field(..., description="公司名称")
    forecast_years: int = Field(5, ge=3, le=10, description="预测期年数")

    # 基期数据
    base_revenue: float = Field(..., gt=0, description="基期营收（亿元）")
    base_ebit_margin: float = Field(..., ge=-0.5, le=1.0, description="基期 EBIT 利润率")

    # 预测期序列（长度必须 = forecast_years）
    revenue_growth_rates: List[float] = Field(
        ..., min_length=3, description="逐年营收增速，如 [0.15, 0.12, 0.10, 0.08, 0.05]"
    )
    ebit_margins: List[float] = Field(..., min_length=3, description="逐年 EBIT 利润率")

    # 资本支出假设
    da_pct_revenue: float = Field(0.03, ge=0.0, le=0.20, description="折旧摊销占营收比")
    capex_pct_revenue: float = Field(0.04, ge=0.0, le=0.30, description="资本支出占营收比")
    wc_pct_revenue: float = Field(0.02, ge=-0.10, le=0.20, description="营运资金变动占营收比")

    # 折现与终值
    tax_rate: float = Field(0.25, ge=0.0, le=0.50, description="有效所得税率")
    wacc: float = Field(..., gt=0.01, lt=0.30, description="加权平均资本成本")
    terminal_growth_rate: float = Field(0.025, ge=0.0, lt=0.06, description="永续增长率 g")

    # 资本结构
    net_debt: float = Field(0.0, description="净负债 = 有息负债 - 现金（亿元）")
    shares_outstanding: float = Field(..., gt=0, description="发行在外普通股（亿股）")

    # CAPM 参数（可选，用于 WACC 透明拆解）
    risk_free_rate: Optional[float] = Field(None, ge=0.0, le=0.10, description="无风险利率")
    equity_risk_premium: Optional[float] = Field(None, ge=0.0, le=0.15, description="股权风险溢价")
    beta: Optional[float] = Field(None, gt=0.0, le=5.0, description="Beta 系数")
    cost_of_debt: Optional[float] = Field(None, ge=0.0, le=0.20, description="税前债务成本")
    debt_ratio: Optional[float] = Field(None, ge=0.0, le=1.0, description="负债率 D/(D+E)")

    # 可选：当前价格（用于计算 upside）
    current_price: Optional[float] = Field(None, gt=0, description="当前股价（元）")

    # 动态 WACC 参数（可选，用于 Hamada 公式）
    use_dynamic_wacc: bool = Field(False, description="是否使用动态 WACC（Hamada 公式）")
    industry_beta: Optional[float] = Field(None, gt=0.0, le=5.0, description="行业平均 Beta（无杠杆）")
    target_debt_ratio: Optional[float] = Field(None, ge=0.0, le=0.8, description="目标负债率 D/(D+E)")
    tax_rate_for_beta: Optional[float] = Field(None, ge=0.0, le=0.50, description="用于 Hamada 的税率")

    @field_validator("revenue_growth_rates", "ebit_margins")
    @classmethod
    def validate_list_length(cls, v: list) -> list:
        return v

    @model_validator(mode="after")
    def validate_forecast_alignment(self) -> "DCFAssumptions":
        if len(self.revenue_growth_rates) != self.forecast_years:
            raise ValueError(
                f"revenue_growth_rates 长度 ({len(self.revenue_growth_rates)}) ≠ forecast_years ({self.forecast_years})"
            )
        if len(self.ebit_margins) != self.forecast_years:
            raise ValueError(f"ebit_margins 长度 ({len(self.ebit_margins)}) ≠ forecast_years ({self.forecast_years})")
        return self

    @model_validator(mode="after")
    def validate_dynamic_wacc(self) -> "DCFAssumptions":
        if self.use_dynamic_wacc:
            if self.industry_beta is None:
                raise ValueError("使用动态 WACC 时必须提供 industry_beta")
            if self.target_debt_ratio is None:
                raise ValueError("使用动态 WACC 时必须提供 target_debt_ratio")
        return self

    def compute_dynamic_wacc(self) -> float:
        """使用 Hamada 公式计算动态 WACC

        步骤：
        1. relevered_beta = industry_beta × [1 + (1 - T) × D/E]
        2. cost_of_equity = risk_free_rate + relevered_beta × equity_risk_premium
        3. wacc = E/(D+E) × cost_of_equity + D/(D+E) × cost_of_debt × (1 - T)
        """
        if not self.use_dynamic_wacc or self.industry_beta is None or self.target_debt_ratio is None:
            return self.wacc

        t = self.tax_rate_for_beta if self.tax_rate_for_beta is not None else self.tax_rate
        d_e = self.target_debt_ratio / (1 - self.target_debt_ratio) if self.target_debt_ratio < 1 else 999.0

        # Hamada 公式
        relevered_beta = self.industry_beta * (1 + (1 - t) * d_e)

        # CAPM
        rf = self.risk_free_rate if self.risk_free_rate is not None else 0.025
        erp = self.equity_risk_premium if self.equity_risk_premium is not None else 0.065
        cost_of_equity = rf + relevered_beta * erp

        # WACC
        cod = self.cost_of_debt if self.cost_of_debt is not None else 0.04
        e_ratio = 1 - self.target_debt_ratio
        d_ratio = self.target_debt_ratio
        wacc = e_ratio * cost_of_equity + d_ratio * cod * (1 - t)

        return round(wacc, 6)


# ─── Comparable ─────────────────────────────────────────────────────────────


class ComparableAssumptions(BaseModel):
    """可比公司估值假设"""

    ticker: str = Field(..., description="标的代码")
    company_name: str = Field(..., description="公司名称")

    # 标的公司指标
    company_eps: float = Field(..., description="每股收益（元）")
    company_bvps: float = Field(..., description="每股净资产（元）")
    company_revenue_per_share: float = Field(0.0, ge=0.0, description="每股营收（元）")
    company_ebitda_per_share: float = Field(0.0, ge=0.0, description="每股 EBITDA（元）")

    # 可比公司倍数（至少 3 家）
    peer_pe_ratios: List[float] = Field(..., min_length=3, description="可比公司 PE 列表")
    peer_pb_ratios: List[float] = Field(default_factory=list, description="可比公司 PB 列表")
    peer_ps_ratios: List[float] = Field(default_factory=list, description="可比公司 PS 列表")
    peer_ev_ebitda: List[float] = Field(default_factory=list, description="可比公司 EV/EBITDA 列表")

    current_price: Optional[float] = Field(None, gt=0, description="当前股价（元）")

    @field_validator("peer_pe_ratios")
    @classmethod
    def validate_pe_positive(cls, v: list) -> list:
        for i, pe in enumerate(v):
            if pe <= 0:
                raise ValueError(f"peer_pe_ratios[{i}] = {pe} ≤ 0，PE 必须为正")
        return v


# ─── Scenario ───────────────────────────────────────────────────────────────


class ScenarioDetail(BaseModel):
    """单个情景的参数"""

    revenue_growth_rates: List[float] = Field(..., min_length=1, description="逐年营收增速")
    operating_margin: float = Field(..., ge=-0.5, le=1.0, description="稳态营业利润率")
    terminal_growth: float = Field(0.025, ge=0.0, lt=0.06, description="终值增长率")
    probability: float = Field(0.33, gt=0.0, le=1.0, description="情景概率")


class ScenarioAssumptions(BaseModel):
    """情景分析假设"""

    ticker: str = Field(..., description="标的代码")
    company_name: str = Field(..., description="公司名称")
    base_price: float = Field(..., gt=0, description="当前股价（元）")

    bull: ScenarioDetail = Field(..., description="乐观情景")
    base: ScenarioDetail = Field(..., description="基准情景")
    bear: ScenarioDetail = Field(..., description="悲观情景")

    wacc: float = Field(0.09, gt=0.01, lt=0.30, description="WACC")
    projection_years: int = Field(5, ge=3, le=10, description="预测期年数")
    tax_rate: float = Field(0.25, ge=0.0, le=0.50, description="所得税率")
    base_revenue: Optional[float] = Field(None, gt=0, description="基期营收（亿元）")
    total_shares: Optional[float] = Field(None, gt=0, description="总股本（亿股）")
    net_debt: float = Field(0.0, description="净负债（亿元）")

    @model_validator(mode="after")
    def validate_probabilities(self) -> "ScenarioAssumptions":
        total = self.bull.probability + self.base.probability + self.bear.probability
        if abs(total - 1.0) > 0.02:
            raise ValueError(f"情景概率之和 = {total:.2%}，应接近 100%")
        return self

    @model_validator(mode="after")
    def validate_monotonicity(self) -> "ScenarioAssumptions":
        bull_margin = self.bull.operating_margin
        base_margin = self.base.operating_margin
        bear_margin = self.bear.operating_margin
        if not (bull_margin >= base_margin >= bear_margin):
            raise ValueError(
                f"情景利润率应单调递减: bull={bull_margin:.1%} ≥ base={base_margin:.1%} ≥ bear={bear_margin:.1%}"
            )
        return self


# ─── SOTP ───────────────────────────────────────────────────────────────────


class ValuationMethod(str, Enum):
    PE = "PE"
    PS = "PS"
    EV_EBITDA = "EV-EBITDA"
    DCF = "DCF"


class SOTPSegment(BaseModel):
    """SOTP 分部估值项"""

    name: str = Field(..., description="分部名称")
    revenue: float = Field(..., ge=0.0, description="营收（亿元）")
    profit: float = Field(..., description="净利润（亿元）")
    valuation_method: ValuationMethod = Field(ValuationMethod.PE, description="估值方法")
    peer_multiple: float = Field(..., gt=0.0, description="可比倍数")
    description: str = Field("", description="分部说明")


class SOTPAssumptions(BaseModel):
    """分部加总估值假设"""

    ticker: str = Field(..., description="标的代码")
    company_name: str = Field(..., description="公司名称")

    segments: List[SOTPSegment] = Field(..., min_length=1, description="估值分部列表")
    cash_and_equivalents: float = Field(0.0, ge=0.0, description="现金及等价物（亿元）")
    net_debt: float = Field(0.0, description="净负债（亿元）")
    non_core_assets: float = Field(0.0, description="非核心资产价值（亿元）")
    total_shares: float = Field(..., gt=0, description="总股本（亿股）")

    current_price: Optional[float] = Field(None, gt=0, description="当前股价（元）")


# ─── Aggregate ──────────────────────────────────────────────────────────────


class ValuationResult(BaseModel):
    """统一估值结果"""

    method: str = Field(..., description="估值方法")
    target_price: float = Field(..., description="目标价（元/股）")
    confidence: str = Field("medium", description="置信度: high/medium/low")
    details: dict = Field(default_factory=dict, description="详细结果")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
