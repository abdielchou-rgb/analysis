"""
统一 Pydantic 意图解析契约 v2 — 整合 engine/ 与 core/ 的重复 Schema。
所有计算模块从此处读取参数，LLM 输出 JSON 必须通过此 Schema 校验。

变更:
- 新增 ReverseDCFAssumptions（逆向 DCF 求解器）
- 新增 SensitivitySurface（多维敏感性分析）
- 新增 CellProvenance（单元格级溯源）
- DCFAssumptionsV2 合并了 core/compute/valuation/dcf.py 的函数参数
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ─── Cell Provenance ──────────────────────────────────────────────────────


class CellProvenance(BaseModel):
    """单元格级溯源元数据 — 每个计算值的来源追踪"""

    cell_id: str = Field(..., description="单元格 ID, e.g. dcf.year3.fcf")
    value: float = Field(..., description="计算值")
    formula: str = Field("", description="计算公式, e.g. NOPAT + D&A - CapEx - ΔWC")
    inputs: dict[str, str] = Field(default_factory=dict, description="输入项来源")
    source_file: str = Field("", description="源代码位置, e.g. engine/dcf_model.py:92")
    source_doc: str = Field("", description="原始文档来源, e.g. 2025-10K")
    reported_tag: str = Field("", description="XBRL tag")
    reported_unit: str = Field("CNY", description="原始单位")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="提取置信度")


# ─── DCF v2 ───────────────────────────────────────────────────────────────


class DCFAssumptionsV2(BaseModel):
    """DCF 估值假设 v2 — 合并 engine/schemas.py + core/compute/valuation/dcf.py"""

    ticker: str = Field(..., description="标的代码")
    company_name: str = Field("", description="公司名称")
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

    # 终值方法
    terminal_method: str = Field("ggm", description="终值方法: ggm / exit_multiple")
    exit_ebitda_multiple: float = Field(10.0, gt=0.0, description="退出 EV/EBITDA 倍数")

    # 资本结构
    net_debt: float = Field(0.0, description="净负债 = 有息负债 - 现金（亿元）")
    shares_outstanding: float = Field(..., gt=0, description="发行在外普通股（亿股）")

    # CAPM 参数（可选）
    risk_free_rate: Optional[float] = Field(None, ge=0.0, le=0.10, description="无风险利率")
    equity_risk_premium: Optional[float] = Field(None, ge=0.0, le=0.15, description="股权风险溢价")
    beta: Optional[float] = Field(None, gt=0.0, le=5.0, description="Beta 系数")
    cost_of_debt: Optional[float] = Field(None, ge=0.0, le=0.20, description="税前债务成本")
    debt_ratio: Optional[float] = Field(None, ge=0.0, le=1.0, description="负债率 D/(D+E)")

    # 可选：当前价格
    current_price: Optional[float] = Field(None, gt=0, description="当前股价（元）")

    # 动态 WACC（Hamada）
    use_dynamic_wacc: bool = Field(False, description="是否使用动态 WACC")
    industry_beta: Optional[float] = Field(None, gt=0.0, le=5.0, description="行业平均 Beta（无杠杆）")
    target_debt_ratio: Optional[float] = Field(None, ge=0.0, le=0.8, description="目标负债率 D/(D+E)")
    tax_rate_for_beta: Optional[float] = Field(None, ge=0.0, le=0.50, description="用于 Hamada 的税率")

    @model_validator(mode="after")
    def validate_forecast_alignment(self) -> DCFAssumptionsV2:
        if len(self.revenue_growth_rates) != self.forecast_years:
            raise ValueError(
                f"revenue_growth_rates 长度 ({len(self.revenue_growth_rates)}) ≠ forecast_years ({self.forecast_years})"
            )
        if len(self.ebit_margins) != self.forecast_years:
            raise ValueError(f"ebit_margins 长度 ({len(self.ebit_margins)}) ≠ forecast_years ({self.forecast_years})")
        return self

    @model_validator(mode="after")
    def validate_dynamic_wacc(self) -> DCFAssumptionsV2:
        if self.use_dynamic_wacc:
            if self.industry_beta is None:
                raise ValueError("使用动态 WACC 时必须提供 industry_beta")
            if self.target_debt_ratio is None:
                raise ValueError("使用动态 WACC 时必须提供 target_debt_ratio")
        return self

    def compute_dynamic_wacc(self) -> float:
        """使用 Hamada 公式计算动态 WACC"""
        if not self.use_dynamic_wacc or self.industry_beta is None or self.target_debt_ratio is None:
            return self.wacc

        t = self.tax_rate_for_beta if self.tax_rate_for_beta is not None else self.tax_rate
        d_e = self.target_debt_ratio / (1 - self.target_debt_ratio) if self.target_debt_ratio < 1 else 999.0

        relevered_beta = self.industry_beta * (1 + (1 - t) * d_e)

        rf = self.risk_free_rate if self.risk_free_rate is not None else 0.025
        erp = self.equity_risk_premium if self.equity_risk_premium is not None else 0.065
        cost_of_equity = rf + relevered_beta * erp

        cod = self.cost_of_debt if self.cost_of_debt is not None else 0.04
        e_ratio = 1 - self.target_debt_ratio
        d_ratio = self.target_debt_ratio
        wacc = e_ratio * cost_of_equity + d_ratio * cod * (1 - t)

        return round(wacc, 6)

    # 向后兼容: 暴露与旧版 DCFAssumptions 相同的字段别名
    @property
    def terminal_growth(self) -> float:
        return self.terminal_growth_rate


# ─── Three-Statement v2 ──────────────────────────────────────────────────


class ThreeStatementAssumptionsV2(BaseModel):
    """三表联动假设 v2 — 统一 engine/ 与 core/ 的接口"""

    ticker: str = Field(..., description="标的代码")
    company_name: str = Field("", description="公司名称")
    forecast_years: int = Field(5, ge=3, le=10, description="预测期年数")

    # 基期数据
    base_revenue: float = Field(..., gt=0, description="基期营收（亿元）")
    revenue_growth_rates: List[float] = Field(..., min_length=3, description="逐年营收增速")
    ebit_margins: List[float] = Field(..., min_length=3, description="逐年 EBIT 利润率")
    tax_rate: float = Field(0.25, ge=0.0, le=0.50, description="有效所得税率")
    payout_ratio: float = Field(0.30, ge=0.0, le=1.0, description="股利支付率")

    # 资产负债表基期
    base_total_assets: Optional[float] = Field(None, gt=0, description="基期总资产（亿元）")
    base_total_liabilities: Optional[float] = Field(None, ge=0.0, description="基期总负债（亿元）")
    base_equity: Optional[float] = Field(None, gt=0, description="基期股东权益（亿元）")

    # 资本支出
    da_pct_revenue: float = Field(0.03, ge=0.0, le=0.20, description="折旧摊销占营收比")
    capex_pct_revenue: float = Field(0.04, ge=0.0, le=0.30, description="资本支出占营收比")
    wc_pct_revenue: float = Field(0.02, ge=-0.10, le=0.20, description="营运资金变动占营收比")

    # 资本结构
    interest_rate: float = Field(0.04, ge=0.0, le=0.20, description="有息负债利率")
    debt_growth_rate: float = Field(0.0, ge=-0.50, le=0.50, description="负债年增速")
    shares_outstanding: float = Field(1.0, gt=0, description="总股本（亿股）")

    # 可选
    current_price: Optional[float] = Field(None, gt=0, description="当前股价（元）")


# ─── Reverse DCF ─────────────────────────────────────────────────────────


class ReverseDCFAssumptions(BaseModel):
    """逆向 DCF 输入 — 从当前市值反推隐含增长率"""

    ticker: str = Field(..., description="标的代码")
    company_name: str = Field("", description="公司名称")
    current_price: float = Field(..., gt=0, description="当前股价（元）")
    shares_outstanding: float = Field(..., gt=0, description="发行在外普通股（亿股）")
    net_debt: float = Field(0.0, description="净负债（亿元）")

    # 可选输入（提高精度）
    fcf_ttm: Optional[float] = Field(None, gt=0, description="过去12个月自由现金流（亿元）")
    revenue_ttm: Optional[float] = Field(None, gt=0, description="过去12个月营收（亿元）")
    ebit_ttm: Optional[float] = Field(None, description="过去12个月 EBIT（亿元）")

    # 折现参数
    wacc: float = Field(0.10, gt=0.01, lt=0.30, description="WACC")
    tax_rate: float = Field(0.25, ge=0.0, le=0.50, description="所得税率")
    terminal_growth_rate: float = Field(0.025, ge=0.0, lt=0.06, description="终值增长率")
    forecast_years: int = Field(10, ge=5, le=20, description="预测期年数")


# ─── Monte Carlo v2 ──────────────────────────────────────────────────────


class MonteCarloAssumptionsV2(BaseModel):
    """Monte Carlo 模拟假设 v2 — 合并 engine/ 与 core/ 的接口"""

    ticker: str = Field("unknown", description="标的代码")
    company_name: str = Field("", description="公司名称")
    n_simulations: int = Field(10000, ge=1000, le=1000000, description="模拟次数")
    random_seed: Optional[int] = Field(None, description="随机种子")

    # 基期
    base_revenue: float = Field(..., gt=0, description="基期营收（亿元）")
    shares_outstanding: float = Field(..., gt=0, description="总股本（亿股）")

    # 随机变量参数
    revenue_growth_mean: float = Field(0.10, description="营收增速均值")
    revenue_growth_std: float = Field(0.05, ge=0.0, description="营收增速标准差")
    ebit_margin_mean: float = Field(0.20, description="EBIT 利润率均值")
    ebit_margin_std: float = Field(0.05, ge=0.0, description="EBIT 利润率标准差")
    wacc_mean: float = Field(0.09, description="WACC 均值")
    wacc_std: float = Field(0.01, ge=0.0, description="WACC 标准差")
    terminal_growth_mean: float = Field(0.025, description="终值增长率均值")
    terminal_growth_std: float = Field(0.005, ge=0.0, description="终值增长率标准差")

    # 相关性矩阵（4x4）
    correlation_matrix: Optional[List[List[float]]] = Field(None, description="4变量相关性矩阵")

    # 固定参数
    tax_rate: float = Field(0.25, ge=0.0, le=0.50, description="所得税率")
    net_debt: float = Field(0.0, description="净负债（亿元）")
    current_price: Optional[float] = Field(None, gt=0, description="当前股价（元）")
    forecast_years: int = Field(5, ge=3, le=10, description="预测期年数")

    @field_validator("correlation_matrix")
    @classmethod
    def validate_correlation_matrix(cls, v: list | None) -> list | None:
        if v is not None:
            n = len(v)
            for i, row in enumerate(v):
                if len(row) != n:
                    raise ValueError(f"相关性矩阵不是方阵: row {i} has {len(row)} cols, expected {n}")
        return v


# ─── Sensitivity Surface ─────────────────────────────────────────────────


class SensitivityParam(BaseModel):
    """敏感性分析参数"""

    name: str = Field(..., description="参数名")
    base_value: float = Field(..., description="基准值")
    range_pct: float = Field(0.20, gt=0.0, le=1.0, description="变动范围（±百分比）")
    steps: int = Field(5, ge=3, le=20, description="步数")


class SensitivitySurface(BaseModel):
    """多维敏感性分析配置"""

    target_metric: str = Field("target_price", description="目标指标名")
    params: List[SensitivityParam] = Field(..., min_length=2, max_length=4, description="敏感性参数")


# ─── Aggregate ───────────────────────────────────────────────────────────


class ValuationResultV2(BaseModel):
    """统一估值结果 v2"""

    method: str = Field(..., description="估值方法")
    target_price: float = Field(..., description="目标价（元/股）")
    confidence: str = Field("medium", description="置信度: high/medium/low")
    details: dict = Field(default_factory=dict, description="详细结果")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    provenance: List[CellProvenance] = Field(default_factory=list, description="计算溯源链")
