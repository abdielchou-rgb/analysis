"""
1号分析师 V30 — 可比公司估值模型

基于 PE/PB/PS/EV/EBITDA 多维度对标分析。

工作模式：
  - "manual": 手动指定可比公司列表（当前实现）
  - "auto": 基于行业分类自动选取（未来扩展）

由于 baostock 只提供单个公司的 API 查询，可比公司数据需要
逐个拉取。当前采用"手动指定可比公司列表"模式。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from core.models import AnnualFinancials, StructuredData
# V57: conditional import - fall back gracefully if V30 unavailable
try:
    from compute.V30_compute.layer1_data.connectors.a_share import BaostockConnector
    _HAS_V30 = True
except ImportError:
    _HAS_V30 = False
    BaostockConnector = None

logger = logging.getLogger("v30.valuation.comparable")


@dataclass
class ComparableResult:
    """可比公司估值分析结果。"""
    company: str
    stock_code: str
    metrics: dict                           # {metric_name: {company_or_industry: value}}
    company_values: dict                     # 标的公司各指标值
    peer_percentiles: dict                   # {metric: 标的公司在可比组中的百分位}
    avg_premium_discount: dict               # {metric: 相对行业平均的溢价/折价%}
    peer_list: list[str]                     # 可比公司代码列表
    peer_names: list[str]                    # 可比公司名称列表
    industry_avg: dict                       # 行业平均值
    target_implied_values: dict              # 基于可比倍数推算的目标估值
    warnings: list[str] = field(default_factory=list)


def compute_comparable(
    l1_data: StructuredData,
    peer_codes: Optional[list[str]] = None,
    peer_names: Optional[list[str]] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> ComparableResult:
    """
    可比公司估值分析。

    拉取可比公司的财务数据，计算 PE/PB/PS/EV/EBITDA 等多维度对标指标。

    Args:
        l1_data: 标的公司的 L1 结构化数据
        peer_codes: 可比公司代码列表 (e.g. ["sh.600519", "sz.000858"])
        peer_names: 可比公司名称列表（与 peer_codes 对应）
        start_year: 数据起始年份（默认与标的公司一致）
        end_year: 数据结束年份（默认与标的公司一致）

    Returns:
        ComparableResult: 可比分析结果
    """
    company = l1_data.profile.stock_name
    stock_code = l1_data.profile.stock_code

    if peer_codes is None:
        peer_codes = []
        peer_names = []

    if peer_names is None:
        peer_names = peer_codes  # 用代码当名字

    if start_year is None or end_year is None:
        years = sorted(l1_data.years_covered)
        if start_year is None:
            start_year = years[0] if years else 2020
        if end_year is None:
            end_year = years[-1] if years else 2024

    # ── 1. 获取可比公司数据 ──
    peer_data: list[dict] = []
    if not _HAS_V30:
        return {"error": "V30 data connectors unavailable", "peers": []}
    conn = BaostockConnector()

    for code, name in zip(peer_codes, peer_names):
        try:
            peer_l1 = conn.fetch_full(code, start_year, end_year)
            if peer_l1.financials:
                last = peer_l1.financials[-1]
                earliest = peer_l1.financials[0]
                peer_entry = _extract_peer_metrics(last, earliest, name or code)
                peer_data.append(peer_entry)
                logger.info(f"[可比] 获取 {name or code} 数据成功: 营收={last.revenue}")
            else:
                logger.warning(f"[可比] {name or code} 无财务数据")
        except Exception as e:
            logger.warning(f"[可比] 获取 {name or code} 失败: {e}")
            continue

    conn.logout()

    # ── 2. 提取标的公司自身指标 ──
    target_last = l1_data.financials[-1] if l1_data.financials else None
    target_first = l1_data.financials[0] if len(l1_data.financials) > 1 else target_last
    target_metrics = _extract_peer_metrics(target_last, target_first, company)
    company_values = target_metrics.get("metrics", {})

    # ── 3. 构建多维度对标矩阵 ──
    metric_names = [
        "pe_ttm", "pb", "ps", "ev_ebitda",
        "gross_margin", "net_margin", "roe",
        "revenue_yoy", "profit_yoy",
    ]

    # 组织指标数据: {metric: {company: value}}
    metrics_organized: dict[str, dict] = {}
    for metric in metric_names:
        metric_dict: dict[str, Optional[float]] = {}
        metric_dict[company] = target_metrics.get("metrics", {}).get(metric)
        for entry in peer_data:
            peer_name = entry.get("name", "")
            metric_dict[peer_name] = entry.get("metrics", {}).get(metric)
        metrics_organized[metric] = metric_dict

    # ── 4. 计算行业平均和标的百分位 ──
    peer_values_only: dict[str, list[float]] = {}
    for metric in metric_names:
        values: list[float] = []
        for entry in peer_data:
            v = entry.get("metrics", {}).get(metric)
            if v is not None and v > 0:
                values.append(v)
        peer_values_only[metric] = values

    industry_avg = {}
    peer_percentiles = {}
    avg_premium_discount = {}
    target_implied_values = {}

    for metric in metric_names:
        values = peer_values_only[metric]
        target_val = company_values.get(metric)

        # 行业平均（排除异常值>3倍标准差）
        if values:
            filtered = _filter_outliers(values)
            avg_val = sum(filtered) / len(filtered) if filtered else None
        else:
            avg_val = None
        industry_avg[metric] = round(avg_val, 4) if avg_val else None

        # 百分位
        if target_val is not None and values:
            sorted_vals = sorted(values)
            rank = sum(1 for v in sorted_vals if v <= target_val)
            percentile = round(rank / len(sorted_vals) * 100, 1)
            peer_percentiles[metric] = percentile
        else:
            peer_percentiles[metric] = None

        # 溢价/折价
        if target_val is not None and avg_val and avg_val > 0:
            premium = round((target_val - avg_val) / avg_val * 100, 2)
            avg_premium_discount[metric] = premium
        else:
            avg_premium_discount[metric] = None

        # 基于可比倍数推算目标价（估值类指标）
        if metric in ("pe_ttm", "pb", "ps", "ev_ebitda") and avg_val and target_val:
            if target_last and target_last.net_profit is not None and target_last.total_shares:
                shares_yi = target_last.total_shares / 1e8
                if metric == "pe_ttm":
                    implied_pe_price = round(target_last.eps * avg_val if target_last.eps else 0, 2)
                    target_implied_values[f"基于{metric}"] = implied_pe_price
                elif metric == "pb" and target_last.roe is not None:
                    # PB = ROE * PE
                    pass

    # 添加基于 PE 和 PS 的隐含估值
    if target_last is not None:
        if target_last.net_profit is not None and target_last.total_shares:
            shares_yi = target_last.total_shares / 1e8
            eps = target_last.net_profit / shares_yi if shares_yi > 0 else 0
            avg_pe = industry_avg.get("pe_ttm")
            if avg_pe and eps > 0:
                target_implied_values["基于行业平均PE"] = round(eps * avg_pe, 2)

            if target_last.revenue and shares_yi > 0:
                ps_per_share = target_last.revenue / shares_yi
                avg_ps = industry_avg.get("ps")
                if avg_ps:
                    target_implied_values["基于行业平均PS"] = round(ps_per_share * avg_ps, 2)

    warnings = []
    if not peer_data:
        warnings.append("未能获取任何可比公司数据")

    result = ComparableResult(
        company=company,
        stock_code=stock_code,
        metrics=metrics_organized,
        company_values=company_values,
        peer_percentiles=peer_percentiles,
        avg_premium_discount=avg_premium_discount,
        peer_list=peer_codes,
        peer_names=[e.get("name", "") for e in peer_data],
        industry_avg=industry_avg,
        target_implied_values=target_implied_values,
        warnings=warnings,
    )

    return result


def compute_comparable_with_existing_data(
    company: str,
    stock_code: str,
    target_financials: list[AnnualFinancials],
    peer_data_list: list[dict],
    peer_codes: list[str],
    peer_names: list[str],
) -> ComparableResult:
    """
    使用已有（预拉取）的可比公司数据执行分析。

    适用于前端已缓存可比公司数据的场景，避免重复拉取。

    Args:
        company: 标的公司名称
        stock_code: 标的公司代码
        target_financials: 标的公司财务数据
        peer_data_list: 可比公司预拉取数据列表
        peer_codes: 可比公司代码列表
        peer_names: 可比公司名称列表

    Returns:
        ComparableResult
    """
    target_last = target_financials[-1] if target_financials else None
    target_first = target_financials[0] if len(target_financials) > 1 else target_last
    target_metrics = _extract_peer_metrics(target_last, target_first, company)
    company_values = target_metrics.get("metrics", {})

    peer_data = []
    for entry, code, name in zip(peer_data_list, peer_codes, peer_names):
        m = _extract_peer_metrics(
            entry["latest"], entry.get("earliest"), name or code
        )
        peer_data.append(m)

    # 与原方法相同的对标逻辑
    metric_names = [
        "pe_ttm", "pb", "ps", "ev_ebitda",
        "gross_margin", "net_margin", "roe",
        "revenue_yoy", "profit_yoy",
    ]

    metrics_organized: dict[str, dict] = {}
    for metric in metric_names:
        metric_dict: dict[str, Optional[float]] = {}
        metric_dict[company] = company_values.get(metric)
        for entry in peer_data:
            peer_name = entry.get("name", "")
            metric_dict[peer_name] = entry.get("metrics", {}).get(metric)
        metrics_organized[metric] = metric_dict

    peer_values_only: dict[str, list[float]] = {}
    for metric in metric_names:
        values = []
        for entry in peer_data:
            v = entry.get("metrics", {}).get(metric)
            if v is not None and v > 0:
                values.append(v)
        peer_values_only[metric] = values

    industry_avg = {}
    peer_percentiles = {}
    avg_premium_discount = {}
    target_implied_values = {}

    for metric in metric_names:
        values = peer_values_only[metric]
        target_val = company_values.get(metric)

        if values:
            filtered = _filter_outliers(values)
            avg_val = sum(filtered) / len(filtered) if filtered else None
        else:
            avg_val = None
        industry_avg[metric] = round(avg_val, 4) if avg_val else None

        if target_val is not None and values:
            sorted_vals = sorted(values)
            rank = sum(1 for v in sorted_vals if v <= target_val)
            percentile = round(rank / len(sorted_vals) * 100, 1)
            peer_percentiles[metric] = percentile
        else:
            peer_percentiles[metric] = None

        if target_val is not None and avg_val and avg_val > 0:
            premium = round((target_val - avg_val) / avg_val * 100, 2)
            avg_premium_discount[metric] = premium
        else:
            avg_premium_discount[metric] = None

    if target_last is not None and target_last.total_shares:
        shares_yi = target_last.total_shares / 1e8
        if shares_yi > 0:
            if target_last.net_profit:
                eps = target_last.net_profit / shares_yi
                avg_pe = industry_avg.get("pe_ttm")
                if avg_pe and eps > 0:
                    target_implied_values["基于行业平均PE"] = round(eps * avg_pe, 2)
            if target_last.revenue:
                ps_per_share = target_last.revenue / shares_yi
                avg_ps = industry_avg.get("ps")
                if avg_ps:
                    target_implied_values["基于行业平均PS"] = round(ps_per_share * avg_ps, 2)

    return ComparableResult(
        company=company,
        stock_code=stock_code,
        metrics=metrics_organized,
        company_values=company_values,
        peer_percentiles=peer_percentiles,
        avg_premium_discount=avg_premium_discount,
        peer_list=peer_codes,
        peer_names=peer_names,
        industry_avg=industry_avg,
        target_implied_values=target_implied_values,
    )


# ═══════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════


def _extract_peer_metrics(
    latest: Optional[AnnualFinancials],
    earliest: Optional[AnnualFinancials],
    name: str,
) -> dict:
    """从年度财务数据提取可比指标。"""
    metrics: dict[str, Optional[float]] = {}

    if latest is None:
        return {"name": name, "metrics": metrics}

    # PE = 价格 / EPS（需要实时价格，使用历史近似）
    # 由于无法获取实时股价，PE 用 行业均值替代，或留空
    metrics["pe_ttm"] = None  # 需要外部输入股价

    # PB（同样需要股价，但可用净资产推算隐含PB）
    # 这里只记录 ROE 和净利率等独立指标
    metrics["pb"] = _safe_div(latest.revenue, latest.net_profit) if latest.revenue else None

    # PS（需要市值，同样留空）
    metrics["ps"] = None

    # EV/EBITDA（复杂，留空）
    metrics["ev_ebitda"] = None

    # 利润率
    metrics["gross_margin"] = latest.gross_margin
    metrics["net_margin"] = latest.net_margin

    # ROE
    metrics["roe"] = latest.roe

    # 增速
    metrics["revenue_yoy"] = latest.yoy_revenue
    metrics["profit_yoy"] = latest.yoy_net_profit

    # 资产负债率
    metrics["liability_to_asset"] = latest.liability_to_asset

    # 总资产周转率
    metrics["asset_turnover"] = latest.asset_turnover

    return {"name": name, "metrics": metrics, "latest": latest, "earliest": earliest}


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """安全除法。"""
    if a is None or b is None or b == 0:
        return None
    return round(a / b, 4)


def _filter_outliers(values: list[float], n_stds: float = 3.0) -> list[float]:
    """剔除超出 n_stds 标准差的值。"""
    if len(values) < 3:
        return values
    mean_val = sum(values) / len(values)
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    std_val = variance ** 0.5
    return [v for v in values if abs(v - mean_val) <= n_stds * std_val]


def format_comparable_for_report(cr: ComparableResult) -> str:
    """将可比分析格式化为报告文本块。"""
    lines = []
    lines.append(f"## 可比公司分析: {cr.company}")
    lines.append("")

    # 可比公司列表
    lines.append(f"**可比公司 ({len(cr.peer_names)}家)**: {', '.join(cr.peer_names)}")
    lines.append("")

    # 多维度对标表
    metric_labels = {
        "pe_ttm": "PE(TTM)",
        "pb": "PB",
        "ps": "PS",
        "ev_ebitda": "EV/EBITDA",
        "gross_margin": "毛利率(%)",
        "net_margin": "净利率(%)",
        "roe": "ROE(%)",
        "revenue_yoy": "营收增速(%)",
        "profit_yoy": "净利增速(%)",
        "liability_to_asset": "资产负债率(%)",
        "asset_turnover": "总资产周转率",
    }

    # 表头
    all_names = [cr.company] + cr.peer_names
    headers = ["指标", f"**{cr.company}**"] + cr.peer_names + ["行业平均", "溢价/折价", "百分位"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")

    for metric, label in metric_labels.items():
        row = [label]
        metric_data = cr.metrics.get(metric, {})

        # 标的公司值
        target_v = metric_data.get(cr.company)
        row.append(str(round(target_v, 2)) if target_v is not None else "N/A")

        # 可比公司值
        for pname in cr.peer_names:
            v = metric_data.get(pname)
            row.append(str(round(v, 2)) if v is not None else "N/A")

        # 行业平均
        avg_v = cr.industry_avg.get(metric)
        row.append(str(round(avg_v, 2)) if avg_v is not None else "N/A")

        # 溢价/折价
        premium = cr.avg_premium_discount.get(metric)
        if premium is not None:
            sign = "+" if premium > 0 else ""
            row.append(f"{sign}{premium:.1f}%")
        else:
            row.append("N/A")

        # 百分位
        pct = cr.peer_percentiles.get(metric)
        row.append(f"第{round(pct)}百分位" if pct is not None else "N/A")

        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    # 隐含估值
    if cr.target_implied_values:
        lines.append("### 可比法隐含估值")
        lines.append("")
        lines.append("| 方法 | 隐含目标价(元) |")
        lines.append("|------|---------------|")
        for method, price in cr.target_implied_values.items():
            lines.append(f"| {method} | {price:.2f} |")
        lines.append("")

    # 警告
    if cr.warnings:
        lines.append("### 警告")
        for w in cr.warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)
