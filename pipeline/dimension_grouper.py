"""
维度分组器（Dimension Grouper）— R15 维度级并行提速核心

把 SAC 的 12-21 个分析维度按逻辑相关性分成 4-6 个并行组，每组 2-4 维。
每组独立成文（1200-1800 字），组间弱依赖（靠骨架衔接），组内强相关（可独立分析）。

**为什么分组而不是全并行**：维度间有逻辑依赖（利润池要用市场空间结论、估值要用财务数据），
全并行会重蹈"段落乱序/重复"覆辙。按相关性分组 + 编辑合并 = 并行度提升且结构可控。

**分组原则**（基于 SAC 逻辑链 + 语义相关性）：
- 组A 市场空间：market_size / industry_boundary / supply_demand（行业规模+边界+供需）
- 组B 竞争格局：competitive / profit_pool / peer_benchmarking（格局+利润池+对标）
- 组C 技术路线：technology / life_cycle / elasticity_analysis（技术+生命周期+弹性）
- 组D 政策环境：policy / industry_chain / signal_chain（政策+产业链+信号）
- 组E 资金估值：capital_flow / capital_market / valuation_assessment（资金+估值）
- 组F 判断结论：bold_call / core_disagreement / decision_gate / falsification（核心判断+分歧+决策门+证伪）

**listed 专属**：financial_analysis / governance_esg / catalyst / accounting_penetration 并入相关组
**unlisted 专属**：funding_history / founder_team / product_tech / exit_analysis 等并入相关组
"""

from __future__ import annotations

import logging

logger = logging.getLogger("2hao.dimension_grouper")

# ── 逻辑相关组定义（按报告类型） ──
# 每个组的"代表维度"是组的主题锚点；组的维度列表是覆盖范围
GROUP_DEFS = {
    "industry_deep": {
        "A 市场空间": ["market_size", "industry_boundary", "supply_demand", "global_market_sizing"],
        "B 竞争格局": [
            "competitive",
            "profit_pool",
            "peer_benchmarking",
            "global_competition",
            "unlisted_players",
            "industry_consolidation",
        ],
        "C 技术生命周期": ["technology", "life_cycle", "elasticity_analysis"],
        "D 政策与产业链": ["policy", "industry_chain", "signal_chain", "geopolitical_risk", "esg_materiality"],
        "E 资金与资本市场": ["capital_flow", "capital_market"],
        "F 核心判断": [
            "bold_call",
            "core_disagreement",
            "decision_gate",
            "falsification",
            "investable_standouts",
            "core_hypothesis",
        ],
    },
    "listed_company": {
        "A 公司概况与商业模式": ["business_model", "financial_analysis"],
        "B 竞争与增长": [
            "competitive_position",
            "growth_drivers",
            "peer_benchmarking",
            "global_peer_comparison",
            "overseas_revenue",
            "industry_consolidation",
        ],
        "C 治理与资金": ["governance_esg", "capital_flow", "accounting_penetration", "esg_materiality"],
        "D 估值与判断": [
            "valuation_assessment",
            "catalyst",
            "falsification",
            "core_disagreement",
            "decision_gate",
            "management_quality",
            "geopolitical_exposure",
            "core_hypothesis",
        ],
    },
    "unlisted_company": {
        "A 公司基本面": ["company_profile", "business_kpi", "market_traction", "product_tech"],
        "B 团队与融资": ["founder_team", "funding_history", "capital_efficiency", "founder_risk_signals"],
        "C 竞争与估值": [
            "competitive_moat",
            "valuation_estimate",
            "reference_class_forecast",
            "deal_win_analysis",
            "global_benchmark",
        ],
        "D 退出与风险": [
            "exit_analysis",
            "exit_cycle_analysis",
            "milestone_runway_map",
            "due_diligence",
            "industry_chain",
            "overseas_expansion",
            "cross_border_dd",
        ],
        "E 判断与合规": [
            "decision_gate",
            "falsification",
            "data_declaration",
            "policy_score",
            "core_hypothesis",
            "esg_materiality",
        ],
    },
    # P0-1（2026-08-07）：决策备忘录维度分组。SAC required_dimensions 12 个维度，
    # 此前无 decision_memo 分组 → 全部落入"其他维度"默认组 → 维度未合理分组
    # → 并行写作质量退化 → E2E 只产出 2,923 字。
    "decision_memo": {
        "A 委托方问题与执行摘要": ["client_questions", "exec_summary"],
        "B 行业真相": ["market_size", "competitive", "industry_chain", "policy"],
        "C 禀赋匹配与生产路径": ["capability_gap", "production_subject", "transfer_pricing"],
        "D 财务测算与风险": ["financial_projection", "worst_case_loss"],
        "E 路线图": ["roadmap"],
    },
}

# ── 兜底：任何维度未出现在组定义时归入的默认组 ──
_DEFAULT_GROUP = "其他维度"


def group_dimensions(report_type: str, dim_ids: list[str]) -> list[dict]:
    """把维度列表分组成并行单元。

    Args:
        report_type: 报告类型（industry_deep/listed_company/unlisted_company）
        dim_ids: SAC 必需维度 id 列表（需覆盖全部）

    Returns:
        [{group_name, dimensions: [...]}, ...]，顺序按定义保持
    """
    defs = GROUP_DEFS.get(report_type, GROUP_DEFS["industry_deep"])
    # 建立 维度 -> 组 映射（规范化：去掉【新增】等后缀，前缀匹配）
    dim_to_group = {}
    for gname, dims in defs.items():
        for d in dims:
            dim_to_group[d] = gname
            # 也注册规范化形式（如 elasticity_analysis【新增】→ elasticity_analysis）
            norm = d.split("【")[0].split("（")[0]
            if norm != d:
                dim_to_group[norm] = gname
    # 未映射的维度归入默认组（或并入第一个组，保证不丢）
    groups = {}
    for gname in defs:
        groups[gname] = []
    for d in dim_ids:
        g = dim_to_group.get(d)
        if g is None:
            # 尝试规范化匹配
            norm = d.split("【")[0].split("（")[0]
            g = dim_to_group.get(norm)
        if g is None:
            g = _DEFAULT_GROUP
        groups.setdefault(g, []).append(d)

    # 组装结果，保持 defs 顺序 + 默认组在最后
    result = []
    for gname in defs:
        if groups.get(gname):
            result.append({"group_name": gname, "dimensions": groups[gname]})
    if groups.get(_DEFAULT_GROUP):
        result.append({"group_name": _DEFAULT_GROUP, "dimensions": groups[_DEFAULT_GROUP]})
    # 过滤空组
    result = [g for g in result if g["dimensions"]]
    logger.info(
        "[DIM-GROUP] %s → %d 个并行组: %s",
        report_type,
        len(result),
        [f"{g['group_name']}({len(g['dimensions'])}维)" for g in result],
    )
    return result


def verify_coverage(report_type: str, dim_ids: list[str], groups: list[dict]) -> bool:
    """验证分组是否覆盖全部维度（不丢维度）。"""
    grouped = set()
    for g in groups:
        grouped.update(g["dimensions"])
    missing = [d for d in dim_ids if d not in grouped]
    if missing:
        logger.warning("[DIM-GROUP] 分组缺失维度: %s", missing)
        return False
    return True


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    import logging

    logging.basicConfig(level=logging.INFO)
    from core.sacs import SACLoader

    for rt in ["industry_deep", "listed_company", "unlisted_company"]:
        s = SACLoader(rt)
        dims = [d["id"] for d in s.get_dimensions()]
        groups = group_dimensions(rt, dims)
        ok = verify_coverage(rt, dims, groups)
        print(f"{rt}: 覆盖={ok}, {len(groups)} 组")
        for g in groups:
            print(f"  {g['group_name']}: {g['dimensions']}")
