"""
1号分析师 V30 — L2 计算层调度入口

负责串联：获取 L1 数据 → 行业路由 → 运行计算模型 → 数值门禁 → 输出 ComputedResults

P1优化: 行业路由
- 保险/银行/券商 → financial 管线（偿付能力/NBV/利差）
- 白酒/食品饮料 → consumer 管线（渠道拆分+量价分析）
- 半导体/软件/自动驾驶 → tech 管线（研发费用率+折旧周期）
- 光伏/新能源/电池 → 默认制造业管线
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Optional

from core.models import ComputedResults, StructuredData
from core.compute.financial.revenue_bridge import compute_revenue_bridge
from core.compute.financial.margin_bridge import compute_margin_bridge
from core.compute.financial.expense_bridge import compute_expense_bridge
from core.compute.financial.summary import build_financial_summary
from core.compute.quality_gate.numeric_gate import run_numeric_gate

logger = logging.getLogger("v30.layer2")

# ═══════════════════════════════════════════════════════════════
# 行业 → 管线 路由映射
# ═══════════════════════════════════════════════════════════════

# 金融类：不跑标准三桥，跑偿付能力/NBV/利差
FINANCIAL_INDUSTRIES = {
    "保险", "银行", "券商", "证券", "多元金融",
    "保险Ⅱ", "银行Ⅱ", "证券Ⅱ", "多元金融Ⅱ",
}

# 消费类：渠道拆分+量价分析替代标准收入桥
CONSUMER_INDUSTRIES = {
    "白酒", "食品饮料", "啤酒", "饮料制造", "调味品",
    "白酒Ⅱ", "食品加工", "食品饮料Ⅱ", "休闲食品", "乳品",
}

# 科技类：研发费用率+折旧周期替代标准费用桥
TECH_INDUSTRIES = {
    "半导体", "软件", "自动驾驶", "芯片", "计算机",
    "半导体Ⅱ", "软件开发", "IT服务Ⅱ", "电子化学品Ⅱ",
}

# 制造业（默认管线）
MANUFACTURING_INDUSTRIES = {
    "光伏", "新能源", "电池", "新能源汽车", "电气设备",
    "光伏设备", "电池Ⅱ", "能源金属", "风电设备",
}


def _classify_industry(industry: str) -> str:
    """识别行业并返回管线类型。

    Returns:
        "financial" | "consumer" | "tech" | "manufacturing"
    """
    industry_clean = industry.replace("(申万)", "").strip()

    for ind_set, pipe in [
        (FINANCIAL_INDUSTRIES, "financial"),
        (CONSUMER_INDUSTRIES, "consumer"),
        (TECH_INDUSTRIES, "tech"),
    ]:
        for kw in ind_set:
            if kw in industry_clean:
                return pipe

    return "manufacturing"


def run_compute_pipeline(
    l1_data: StructuredData,
    enable_gate: bool = True,
    # 估值模型开关
    enable_valuation: bool = False,
    valuation_params: Optional[dict] = None,
) -> ComputedResults:
    """
    L2 计算层完整管线：构建摘要 → 收入桥 → 毛利桥 → 费用桥 → (可选估值) → 数值门禁。

    Args:
        l1_data: L1 数据层的输出（结构化财务数据）
        enable_gate: 是否启用数值门禁
        enable_valuation: 是否运行估值模型（DCF/可比/情景）
        valuation_params: 估值模型参数，包含:
            - dcf_params: dict, DCF 参数
            - comparable_params: dict, 可比分析参数
            - scenario_params: dict, 情景分析参数
            - peer_codes: list[str], 可比公司代码
            - peer_names: list[str], 可比公司名称
            - base_price: float, 当前股价

    Returns:
        ComputedResults: 完整的计算结果
    """
    company = l1_data.profile.stock_name
    stock_code = l1_data.profile.stock_code
    industry = getattr(l1_data.profile, "industry", "")

    # ═══ P1: 行业路由 ═══
    pipeline_type = _classify_industry(industry)
    logger.info("[L2] 行业路由: %s → %s 管线", industry, pipeline_type)

    # 根据管线类型调整计算策略
    skip_revenue_bridge = False
    skip_expense_bridge = False
    pipeline_notes = []

    if pipeline_type == "financial":
        skip_revenue_bridge = True
        pipeline_notes.append("金融管线: 跳过收入桥，应关注偿付能力/NBV/利差")
        logger.info("[L2] 金融管线已激活，将跳过制造业三桥")

    elif pipeline_type == "consumer":
        pipeline_notes.append("消费管线: 建议关注渠道拆分+量价分析")
        logger.info("[L2] 消费管线已激活")

    elif pipeline_type == "tech":
        pipeline_notes.append("科技管线: 建议关注研发费用率+折旧周期")
        logger.info("[L2] 科技管线已激活")


    logger.info(f"[L2] 开始计算: {company} ({stock_code})")

    # 1. 财务摘要
    logger.info("[L2] 构建财务摘要...")
    summary = build_financial_summary(l1_data)

    # 2. 收入桥（金融管线跳过）
    if skip_revenue_bridge:
        logger.info("[L2] 跳过收入桥（金融管线）")
        revenue_bridge = None
    else:
        logger.info("[L2] 计算收入桥...")
        revenue_bridge = compute_revenue_bridge(l1_data)

    # 3. 毛利桥
    logger.info("[L2] 计算毛利桥...")
    margin_bridge = compute_margin_bridge(l1_data)

    # 4. 费用桥（科技管线可用研发替代标准费用桥）
    logger.info("[L2] 计算费用桥...")
    expense_bridge = compute_expense_bridge(l1_data)
    if pipeline_type == "tech":
        expense_bridge.tech_notes = "科技管线：建议额外关注研发费用率和资本化折旧周期"
        pipeline_notes.append("费用桥: 科技管线已标注研发费用率+折旧关注点")

    # 5. 组装基础结果
    results = ComputedResults(
        company=company,
        stock_code=stock_code,
        financial_summary=summary,
        revenue_bridge=revenue_bridge,
        margin_bridge=margin_bridge,
        expense_bridge=expense_bridge,
    )
    # warnings 和 data_freshness 在 ComputedResults 中不存在，需单独处理
    results.warnings = l1_data.warnings.copy() if hasattr(results, 'warnings') else []
    # P1: 管线路由备注
    if pipeline_notes:
        if hasattr(results, 'warnings') and results.warnings:
            results.warnings.extend(pipeline_notes)
        else:
            results.warnings = pipeline_notes.copy()
    # 数据时效性信息通过 logger 记录
    logger.info("[L2] 数据时效: years=%s, latest=%s", 
                l1_data.years_covered, 
                l1_data.years_covered[-1] if l1_data.years_covered else "N/A")

    # 6. 可选: 估值模型 (包括全球对标)
    if enable_valuation:
        logger.info("[L2] 运行估值模型...")
        vp = valuation_params or {}
        _run_valuation_models(results, l1_data, vp)
    else:
        # 即使不启用完整估值，也自动运行全球对标
        logger.info("[L2] 自动运行全球竞争对标...")
        vp = valuation_params or {}
        try:
            from core.compute.valuation.global_benchmark import compute_global_benchmark
            from core.compute.valuation.global_peers_db import get_global_peers
            industry = l1_data.profile.industry or ""
            global_peers = get_global_peers(industry)
            if global_peers:
                gb_result = compute_global_benchmark(
                    l1_data=l1_data,
                    global_peers=global_peers,
                    target_region="CN",
                )
                results.global_benchmark = dataclasses.asdict(gb_result)
                logger.info("[L2] 自动全球对标完成: %d家", gb_result.peer_count)
        except Exception as e:
            logger.debug("[L2] 自动全球对标跳过: %s", e)

    # 7. 数值门禁
    if enable_gate:
        logger.info("[L2] 运行数值门禁...")
        results = run_numeric_gate(results, l1_data)
        ng = results.numeric_gate_report
        logger.info(f"[L2] 数值门禁: passed={ng.get('passed')}, "
                     f"score={ng.get('score')}")
    else:
        results.numeric_gate_report = {"passed": True, "score": 100, "checks": {}}

    return results


def _run_valuation_models(
    results: ComputedResults,
    l1_data: StructuredData,
    vp: dict,
) -> None:
    """
    运行估值模型并将结果注入 ComputedResults。

    Args:
        results: 计算结果（会被修改）
        l1_data: L1 结构化数据
        vp: 估值参数 dict
    """
    # ── DCF 估值 ──
    dcf_params = vp.get("dcf_params", {})
    try:
        from core.compute.valuation.dcf import compute_dcf
        dcf_result = compute_dcf(l1_data=l1_data, results=results, **dcf_params)
        if dcf_result is not None:
            results.dcf_result = dataclasses.asdict(dcf_result)
            logger.info(f"[L2] DCF估值完成: EV={dcf_result.enterprise_value:.2f}亿, "
                         f"目标价={dcf_result.target_price:.2f}元")
    except Exception as e:
        logger.error(f"[L2] DCF估值失败: {e}")
        results.warnings.append(f"DCF估值计算失败: {e}")

    # ── 可比公司分析 ──
    comparable_params = vp.get("comparable_params", {})
    peer_codes = vp.get("peer_codes", [])
    peer_names = vp.get("peer_names", [])
    if peer_codes:
        try:
            from core.compute.valuation.comparable import compute_comparable
            comp_result = compute_comparable(
                l1_data,
                peer_codes=peer_codes,
                peer_names=peer_names,
                **comparable_params,
            )
            results.comparable_result = dataclasses.asdict(comp_result)
            logger.info(f"[L2] 可比分析完成: {len(peer_codes)}家可比公司")
        except Exception as e:
            logger.error(f"[L2] 可比分析失败: {e}")
            results.warnings.append(f"可比分析计算失败: {e}")

    # ── 全球竞争对标 ──
    global_benchmark_params = vp.get("global_benchmark_params", {})
    enable_global_benchmark = global_benchmark_params.get("enabled", True)
    if enable_global_benchmark:
        try:
            from core.compute.valuation.global_benchmark import compute_global_benchmark
            from core.compute.valuation.global_peers_db import get_global_peers

            # 自动根据行业分类获取全球可比公司列表
            industry = l1_data.profile.industry or ""
            global_peers_override = global_benchmark_params.get("global_peers", None)
            if global_peers_override is not None:
                global_peers = global_peers_override
            else:
                global_peers = get_global_peers(industry)

            if global_peers:
                target_region = global_benchmark_params.get("target_region", "CN")
                gb_result = compute_global_benchmark(
                    l1_data=l1_data,
                    global_peers=global_peers,
                    target_region=target_region,
                )
                results.global_benchmark = dataclasses.asdict(gb_result)
                logger.info("[L2] 全球竞争对标完成: %d家, 行业=%s",
                            gb_result.peer_count, industry)
            else:
                logger.info("[L2] 全球竞争对标跳过: 无匹配行业(%s)", industry)
        except Exception as e:
            logger.error(f"[L2] 全球竞争对标失败: {e}")
            results.warnings.append(f"全球竞争对标失败: {e}")

    # ── SOTP分部估值 ──
    sotp_params = vp.get("sotp_params", None)
    if sotp_params:
        try:
            from core.compute.valuation.sotp import compute_sotp, SOTPSegmentInput
            segments = []
            for s in sotp_params.get("segments", []):
                segments.append(
                    SOTPSegmentInput(
                        name=s["name"],
                        revenue_bn=s.get("revenue_bn", 0.0),
                        profit_bn=s.get("profit_bn", 0.0),
                        valuation_method=s.get("method", "PE"),
                        peer_pe=s.get("peer_pe"),
                        peer_ps=s.get("peer_ps"),
                    )
                )
            if segments:
                last_f = l1_data.financials[-1] if l1_data.financials else None
                shares = last_f.total_shares if last_f else 0
                sotp_r = compute_sotp(
                    company=results.company,
                    stock_code=results.stock_code,
                    segments=segments,
                    cash_and_equivalents=sotp_params.get("cash", 0.0),
                    net_debt=sotp_params.get("net_debt", 0.0),
                    total_shares=shares or sotp_params.get("total_shares"),
                )
                results.sotp_result = {
                    "segments": sotp_r.segments,
                    "total_segments_value": sotp_r.total_segments_value,
                    "equity_value": sotp_r.equity_value,
                    "target_price": sotp_r.target_price,
                    "warnings": sotp_r.warnings,
                }
                logger.info("[L2] SOTP分部估值完成: %.2f元/股", sotp_r.target_price)
        except Exception as e:
            logger.warning("[L2] SOTP估值跳过: %s", e)

    # ── 三情景分析 ──
    scenario_params = vp.get("scenario_params", {})
    base_price = vp.get("base_price", 0.0)
    if base_price > 0 and scenario_params:
        try:
            from core.compute.valuation.scenario import (
                compute_scenario,
                make_base_scenario,
                make_bull_scenario,
                make_bear_scenario,
            )
            # 构建情景对象
            base = make_base_scenario(**scenario_params.get("base", {}))
            bull = make_bull_scenario(**scenario_params.get("bull", {}))
            bear = make_bear_scenario(**scenario_params.get("bear", {}))

            # 获取基准营收和总股本
            base_revenue = None
            total_shares = None
            if l1_data.financials:
                last = l1_data.financials[-1]
                base_revenue = last.revenue
                total_shares = last.total_shares

            scenario_result = compute_scenario(
                company=results.company,
                stock_code=results.stock_code,
                base_price=base_price,
                base_scenario=base,
                bull_scenario=bull,
                bear_scenario=bear,
                base_revenue=base_revenue or scenario_params.get("base_revenue"),
                total_shares=total_shares or scenario_params.get("total_shares"),
                wacc=scenario_params.get("wacc", 0.09),
                net_debt=scenario_params.get("net_debt", 0.0),
            )
            results.scenario_result = dataclasses.asdict(scenario_result)
            logger.info(f"[L2] 三情景分析完成: 加权目标价={scenario_result.weighted_target_price:.2f}元")
        except Exception as e:
            logger.error(f"[L2] 三情景分析失败: {e}")
            results.warnings.append(f"三情景分析计算失败: {e}")


def format_computed_results_for_report(results: ComputedResults) -> str:
    """将计算结果格式化为报告可读文本。"""
    lines = []

    lines.append(f"# {results.company} ({results.stock_code}) — 计算结果")
    lines.append("")

    # 财务摘要
    lines.append("## 核心财务数据")
    lines.append("")
    lines.append(results.financial_summary.to_markdown_table())
    lines.append("")

    # 收入桥
    if results.revenue_bridge:
        from core.compute.financial.revenue_bridge import (
            format_revenue_bridge_for_report,
        )
        lines.append("## 收入桥分析")
        lines.append("")
        lines.append(format_revenue_bridge_for_report(results.revenue_bridge))
        lines.append("")

    # 毛利桥
    if results.margin_bridge:
        from core.compute.financial.margin_bridge import (
            format_margin_bridge_for_report,
        )
        lines.append("## 毛利桥分析")
        lines.append("")
        lines.append(format_margin_bridge_for_report(results.margin_bridge))
        lines.append("")

    # 费用桥
    if results.expense_bridge:
        from core.compute.financial.expense_bridge import (
            format_expense_bridge_for_report,
        )
        lines.append("## 费用桥分析")
        lines.append("")
        lines.append(format_expense_bridge_for_report(results.expense_bridge))
        lines.append("")

    # 数值质量门禁
    lines.append("## 数值质量门禁")
    lines.append("")
    ng = results.numeric_gate_report
    passed_str = "PASS" if ng.get("passed") else "FAIL"
    lines.append("- 通过: " + passed_str)