"""V52 Financial Data Type System — granularity-aware metric enum + auto-annotation.

Design:
  - 解决归母 vs 扣非 口径混淆问题
  - 每个 FinancialMetric 携带：口径、单位、适用财报位置
  - 在 DataPoint 创建时自动标注口径
  - 下游模块（CrossValidator / DataProvenance）依赖此类型系统做口径匹配
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MetricGranularity(str, Enum):
    """口径层级"""

    ATTRIBUTABLE = "归母"  # 归属于母公司股东的
    DEDUCTED = "扣非"  # 扣除非经常性损益
    CONSOLIDATED = "合并"  # 合并报表口径
    OPERATING = "营业"  # 营业口径（不含非经常）
    GROSS = "毛额"  # 毛额（未扣除项）
    NET = "净额"  # 净额（已扣除项）


class MetricCategory(str, Enum):
    """指标类别"""

    PROFIT = "利润"
    REVENUE = "营收"
    CASHFLOW = "现金流"
    BALANCE = "资产负债"
    VALUATION = "估值"
    OPERATION = "经营"
    MARKET = "市场"


class FinancialStatement(str, Enum):
    """财报位置"""

    P_L = "利润表"
    BS = "资产负债表"
    CF = "现金流量表"
    NOTE = "附注"
    DERIVED = "计算导出"


@dataclass(frozen=True)
class FinancialMetric:
    """完整的财务指标定义，含口径+类别+财报位置+优先信源"""

    id: str  # 内部标识符
    name: str  # 中文名
    category: MetricCategory
    granularity: MetricGranularity
    statement: FinancialStatement
    unit: str = "亿"  # 默认单位
    preferred_sources: list[str] = field(default_factory=list)  # 优先信源
    aliases: list[str] = field(default_factory=list)  # 别称
    parent_metric: str | None = None  # 父指标（用于口径关联）


# ── 核心财务指标注册表 ──────────────────────────────────────

METRIC_REGISTRY: dict[str, FinancialMetric] = {}


def _register(m: FinancialMetric) -> FinancialMetric:
    METRIC_REGISTRY[m.id] = m
    for alias in m.aliases:
        METRIC_REGISTRY[alias] = m
    return m


# 利润类
_register(
    FinancialMetric(
        id="attributable_net_profit",
        name="归母净利润",
        category=MetricCategory.PROFIT,
        granularity=MetricGranularity.ATTRIBUTABLE,
        statement=FinancialStatement.P_L,
        aliases=["归母净利", "归属于母公司股东的净利润", "net_profit_attributable"],
        preferred_sources=["eastmoney", "akshare_consensus"],
    )
)
_register(
    FinancialMetric(
        id="deducted_net_profit",
        name="扣非净利润",
        category=MetricCategory.PROFIT,
        granularity=MetricGranularity.DEDUCTED,
        statement=FinancialStatement.P_L,
        aliases=["扣非净利", "扣除非经常性损益后净利润", "net_profit_deducted"],
        preferred_sources=["eastmoney", "akshare_consensus"],
        parent_metric="attributable_net_profit",
    )
)
_register(
    FinancialMetric(
        id="total_revenue",
        name="营业收入",
        category=MetricCategory.REVENUE,
        granularity=MetricGranularity.CONSOLIDATED,
        statement=FinancialStatement.P_L,
        aliases=["营收", "total_revenue", "营业总收入"],
        preferred_sources=["eastmoney", "company_filing"],
    )
)
_register(
    FinancialMetric(
        id="operating_profit",
        name="营业利润",
        category=MetricCategory.PROFIT,
        granularity=MetricGranularity.OPERATING,
        statement=FinancialStatement.P_L,
        aliases=["op_profit", "operating_income"],
        preferred_sources=["eastmoney"],
    )
)
_register(
    FinancialMetric(
        id="gross_margin",
        name="毛利率",
        category=MetricCategory.PROFIT,
        granularity=MetricGranularity.GROSS,
        statement=FinancialStatement.DERIVED,
        unit="%",
        aliases=["gross_margin_pct"],
        preferred_sources=["eastmoney", "derived"],
    )
)
_register(
    FinancialMetric(
        id="net_margin",
        name="净利率",
        category=MetricCategory.PROFIT,
        granularity=MetricGranularity.NET,
        statement=FinancialStatement.DERIVED,
        unit="%",
        aliases=["net_margin_pct"],
        preferred_sources=["eastmoney", "derived"],
    )
)
_register(
    FinancialMetric(
        id="revenue_yoy",
        name="营收同比增速",
        category=MetricCategory.REVENUE,
        granularity=MetricGranularity.CONSOLIDATED,
        statement=FinancialStatement.DERIVED,
        unit="%",
        aliases=["revenue_growth", "营收增速", "revenue_yoy_pct"],
        preferred_sources=["eastmoney", "derived"],
    )
)
_register(
    FinancialMetric(
        id="profit_yoy",
        name="利润同比增速",
        category=MetricCategory.PROFIT,
        granularity=MetricGranularity.ATTRIBUTABLE,
        statement=FinancialStatement.DERIVED,
        unit="%",
        aliases=["profit_growth", "利润增速", "profit_yoy_pct"],
        preferred_sources=["eastmoney", "derived"],
        parent_metric="attributable_net_profit",
    )
)

# 现金流类
_register(
    FinancialMetric(
        id="operating_cash_flow",
        name="经营活动现金流净额",
        category=MetricCategory.CASHFLOW,
        granularity=MetricGranularity.CONSOLIDATED,
        statement=FinancialStatement.CF,
        aliases=["经营现金流", "operating_cf", "OCF"],
        preferred_sources=["eastmoney", "company_filing"],
    )
)
_register(
    FinancialMetric(
        id="free_cash_flow",
        name="自由现金流",
        category=MetricCategory.CASHFLOW,
        granularity=MetricGranularity.NET,
        statement=FinancialStatement.DERIVED,
        aliases=["FCF", "自由现金流", "free_cash_flow"],
        preferred_sources=["eastmoney", "derived"],
    )
)
# ── A 股特色指标 ──
_register(
    FinancialMetric(
        id="ocf_to_np_ratio",
        name="经营性现金流/净利润比",
        category=MetricCategory.CASHFLOW,
        granularity=MetricGranularity.NET,
        statement=FinancialStatement.DERIVED,
        unit="x",
        aliases=["OCF/NP", "现金流净利润比", "经营现金流对净利润覆盖率", "ocf_np_ratio"],
        preferred_sources=["eastmoney", "derived"],
        parent_metric="attributable_net_profit",
    )
)
_register(
    FinancialMetric(
        id="deducted_non_recurring",
        name="扣非净利润（非经常性损益）",
        category=MetricCategory.PROFIT,
        granularity=MetricGranularity.DEDUCTED,
        statement=FinancialStatement.NOTE,
        aliases=["非经常性损益", "non_recurring_pnl"],
        preferred_sources=["eastmoney", "company_filing"],
    )
)
_register(
    FinancialMetric(
        id="pe_ttm",
        name="市盈率(TTM)",
        category=MetricCategory.VALUATION,
        granularity=MetricGranularity.NET,
        statement=FinancialStatement.DERIVED,
        unit="x",
        aliases=["PE", "市盈率", "pe_ratio"],
        preferred_sources=["eastmoney", "tencent_kline"],
    )
)
_register(
    FinancialMetric(
        id="pb",
        name="市净率",
        category=MetricCategory.VALUATION,
        granularity=MetricGranularity.NET,
        statement=FinancialStatement.DERIVED,
        unit="x",
        aliases=["PB", "市净率", "pb_ratio"],
        preferred_sources=["eastmoney"],
    )
)
_register(
    FinancialMetric(
        id="market_cap",
        name="总市值",
        category=MetricCategory.MARKET,
        granularity=MetricGranularity.CONSOLIDATED,
        statement=FinancialStatement.DERIVED,
        aliases=["市值", "mcap", "market_cap"],
        preferred_sources=["eastmoney", "tencent_kline"],
    )
)
_register(
    FinancialMetric(
        id="circulating_market_cap",
        name="流通市值",
        category=MetricCategory.MARKET,
        granularity=MetricGranularity.CONSOLIDATED,
        statement=FinancialStatement.DERIVED,
        aliases=["流通市值", "circulating_mcap"],
        preferred_sources=["eastmoney"],
    )
)


# ── 口径匹配与标注函数 ──────────────────────────────────────


def resolve_metric(name: str) -> FinancialMetric | None:
    """按名称或别称解析财务指标定义。"""
    if name in METRIC_REGISTRY:
        return METRIC_REGISTRY[name]
    # 模糊匹配：去除空格和下划线后比对
    normalized = name.strip().lower().replace(" ", "").replace("_", "")
    for m_id, metric in METRIC_REGISTRY.items():
        if m_id == normalized:
            return metric
        for alias in metric.aliases:
            if alias.strip().lower().replace(" ", "").replace("_", "") == normalized:
                return metric
    return None


def get_granularity_label(name: str) -> str:
    """获取口径标签（用于行文标注）。"""
    metric = resolve_metric(name)
    if metric is None:
        return ""
    return f"（{metric.granularity.value}口径）"


def reconcile_granularities(
    points: list,
) -> dict[str, list]:
    """口径调和：检测同一母公司指标下是否存在多口径冲突。

    Returns:
        {"conflicts": [("归母净利润", ["attributable", "deducted"], [...])],
         "warnings": ["Q1 净利润存在归母247.62亿 vs 扣非263.41亿"]}
    """
    from collections import defaultdict

    by_parent: dict[str, list] = defaultdict(list)
    for dp in points:
        metric = resolve_metric(dp.name) if hasattr(dp, "name") else None
        parent = metric.parent_metric or (metric.id if metric else dp.name)
        by_parent[parent].append(dp)

    conflicts = []
    warnings = []
    for parent_id, dps in by_parent.items():
        gran_set = set()
        for dp in dps:
            metric = resolve_metric(dp.name) if hasattr(dp, "name") else None
            if metric:
                gran_set.add(metric.granularity.value)
        if len(gran_set) > 1:
            conflicts.append((parent_id, list(gran_set), dps))
            values = []
            for dp in dps:
                if not (hasattr(dp, "value") and dp.value is not None):
                    continue
                metric = resolve_metric(dp.name) if hasattr(dp, "name") else None
                gran_str = metric.granularity.value if metric else "?"
                values.append(f"{gran_str}={dp.value}{dp.unit or ''}")
            warnings.append(f"{parent_id} 存在多口径：{' vs '.join(values)}")
    return {"conflicts": conflicts, "warnings": warnings}


__all__ = [
    "FinancialMetric",
    "MetricGranularity",
    "MetricCategory",
    "FinancialStatement",
    "METRIC_REGISTRY",
    "resolve_metric",
    "get_granularity_label",
    "reconcile_granularities",
]
