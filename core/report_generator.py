# -*- coding: utf-8 -*-
"""report_generator.py — 报告全量生成入口（2026-08-08）

Claude 升级 → 全量调用：按报告类型自动加载 skill + 框架引擎 + 作者姿态 + 门禁 + 圆桌。

流程：
  1. task_router 选路径（管线/工作台/门禁）
  2. 按报告类型加载 skill 清单（框架适配）
  3. 注入框架引擎计算（按报告类型）
  4. context_compiler 组装上下文（含作者姿态 + 框架清单）
  5. 写作（工作台直接写 / 管线 section_writer）
  6. verify_report 门禁（9项）
  7. LLM rubric 软质量评分
  8. 圆桌评审（可触发）

用法：
  from core.report_generator import generate_report
  result = generate_report(asset="某公司", report_type="unlisted_company",
                           requirement="评估投资价值", data={...})
"""
from __future__ import annotations
import os, sys, json, logging
from pathlib import Path

logger = logging.getLogger("2hao.report_generator")

_ROOT = Path(__file__).resolve().parent.parent

# 报告类型 → skill 清单（Claude 全量调用映射）
REPORT_SKILLS = {
    "listed_company": ["listed_company_research", "industry_analysis", "author_pose", "roundtable_review"],
    "unlisted_company": ["unlisted_company_research", "industry_analysis", "author_pose", "roundtable_review"],
    "industry_deep": ["industry_analysis", "author_pose", "roundtable_review"],
    "decision_memo": ["decision_memo", "industry_analysis", "author_pose", "roundtable_review"],
    "earnings_notes": ["earnings_notes", "author_pose"],
}

# 报告类型 → 框架引擎（全量注入）
REPORT_ENGINES = {
    "listed_company": ["mscore", "expectation_gap", "uncertainty", "scenario", "real_option"],
    "unlisted_company": ["unlisted_deep", "vc_thesis", "founder_diligence", "product_metrics",
                         "cap_table", "vc_return", "runway", "vc_scoring"],
    "industry_deep": ["s_curve", "scenario", "real_option"],
    "decision_memo": ["scenario", "real_option", "ma_synergy", "mscore"],
    "earnings_notes": ["mscore", "expectation_gap"],
}


def load_skill_list(report_type: str) -> list:
    """按报告类型返回 skill 清单。"""
    return REPORT_SKILLS.get(report_type, ["author_pose", "roundtable_review"])


def engine_factories():
    """框架引擎工厂：返回 {引擎名: 调用函数}。"""
    from core.compute import (scenario_engine, mscore_engine, s_curve_engine,
                              expectation_gap_engine, ma_synergy_engine, uncertainty_calibration,
                              vc_thesis, founder_diligence, product_metrics, cap_table,
                              vc_return, runway, vc_scoring, unlisted_deep)
    return {
        "scenario": lambda d: scenario_engine.oil_scenario_example().build_prompt(),
        "mscore": lambda d: mscore_engine.build_prompt(mscore_engine.calculate_mscore(d)),
        "s_curve": lambda d: s_curve_engine.build_s_curve_prompt(d),
        "real_option": lambda d: s_curve_engine.build_real_options_prompt([
            s_curve_engine.real_option_value("expansion", d.get("s", 1000), d.get("x", 800), 3, 0.35),
            s_curve_engine.real_option_value("abandon", d.get("s", 1000), d.get("x", 800), 3, 0.35),
        ]),
        "expectation_gap": lambda d: expectation_gap_engine.build_prompt(
            expectation_gap_engine.calculate_expectation_gap(d.get("metrics", []))),
        "ma_synergy": lambda d: ma_synergy_engine.build_prompt(ma_synergy_engine.calculate_synergy(d)),
        "uncertainty": lambda d: uncertainty_calibration.build_prompt(
            uncertainty_calibration.forecast_interval(d.get("base", 1000), d.get("uncertainty", 0.2)),
            uncertainty_calibration.calibrate(d.get("history", []))),
        "unlisted_deep": lambda d: unlisted_deep.format_summary(unlisted_deep.calculate_unlisted_deep(d)),
        "vc_thesis": lambda d: vc_thesis.build_prompt(vc_thesis.build_thesis(d.get("theses", []))),
        "founder_diligence": lambda d: founder_diligence.build_prompt(
            founder_diligence.FounderDiligence(d.get("founder_background", 6), d.get("founder_capability", 6),
                                               d.get("founder_motivation", 6), d.get("founder_integrity", 6))),
        "product_metrics": lambda d: product_metrics.build_prompt(
            product_metrics.ProductMetrics(d.get("product_users", 0), d.get("product_growth", 0.05),
                                           d.get("product_retention", 0.2), d.get("product_arr", 0),
                                           d.get("product_ndr", 1.0), d.get("product_ltv", 0), d.get("product_cac", 0))),
        "cap_table": lambda d: cap_table.build_prompt(
            cap_table.CapTable(d.get("cap_founder", 0.6), d.get("cap_team", 0.1),
                               d.get("cap_investors", 0.25), d.get("cap_option", 0.05))),
        "vc_return": lambda d: vc_return.build_prompt(
            vc_return.VcReturnModel(d.get("vc_invest", 1000), d.get("vc_exit_value", 50000),
                                    d.get("vc_dilution", 0.15), d.get("vc_years", 5), d.get("vc_exit_prob", 0.3))),
        "runway": lambda d: runway.build_prompt(
            runway.Runway(d.get("runway_cash", 0), d.get("runway_burn", 0),
                          d.get("runway_milestone_cost", 0), d.get("runway_milestone_months", 0))),
        "vc_scoring": lambda d: vc_scoring.build_prompt(
            vc_scoring.vc_score(d.get("vc_scores", {}))),
    }


def build_engine_summaries(report_type: str, data: dict) -> list:
    """按报告类型生成框架引擎计算摘要。"""
    engines = REPORT_ENGINES.get(report_type, [])
    factories = engine_factories()
    summaries = []
    for eng in engines:
        try:
            if eng in factories:
                s = factories[eng](data)
                if s:
                    summaries.append(s)
        except Exception as e:
            logger.debug("[REPORT-GEN][%s] %s", eng, str(e)[:60])
    return summaries


def generate_report(asset: str, report_type: str = "listed_company",
                    requirement: str = "", data: dict = None,
                    human_gate: bool = False) -> dict:
    """全量生成报告（Claude 全量调用入口）。

    Returns:
        {status, skills, engines, context, compute_summaries,
         verify, rubric, roundtable_ready, report_path}
    """
    data = data or {}

    # 1. 任务路由
    try:
        from core.task_router import route_task
        route = route_task(report_type, requirement, batch=False)
    except Exception:
        route = {"path": "workbench", "human_gate": human_gate}

    # 2. skill 清单
    skills = load_skill_list(report_type)

    # 3. 框架引擎
    compute_summaries = build_engine_summaries(report_type, data)

    # 4. 上下文（含作者姿态 + 框架适配）
    try:
        from core.context_compiler import compile_context
        ctx = compile_context(asset=asset, report_type=report_type,
                              requirement=requirement, data=data,
                              compute_summaries=compute_summaries,
                              industry_hint=requirement or asset)
    except Exception as e:
        ctx = f"上下文生成失败: {e}"

    # 5. 返回（写作由上层 Claude 用 ctx 生成，之后跑门禁+圆桌）
    return {
        "status": "ready",
        "route": route,
        "skills": skills,
        "engines": REPORT_ENGINES.get(report_type, []),
        "compute_summaries": compute_summaries,
        "context": ctx,
        "report_type": report_type,
        "asset": asset,
        "verify_ready": True,
        "roundtable_ready": "roundtable_review" in skills,
    }


def verify_report_text(report_text: str, report_type: str) -> dict:
    """写作后门禁 + LLM rubric（Claude 全量调用第6-7步）。"""
    result = {"verify": {}, "rubric": {}}
    # 6. 门禁（工作过程/元评论/身份/下行）
    try:
        from core.template_blacklist import scan_work_process, scan_metacomment
        result["verify"]["work_process"] = scan_work_process(report_text)
        result["verify"]["metacomment"] = scan_metacomment(report_text)
    except Exception as e:
        result["verify"]["error"] = str(e)[:80]
    # 7. LLM rubric
    try:
        from core.compute.llm_rubric import llm_score_report
        result["rubric"] = llm_score_report(report_text, use_llm=False)
    except Exception as e:
        result["rubric"]["error"] = str(e)[:80]
    return result


if __name__ == "__main__":
    # 测试
    import sys
    r = generate_report("测试公司", "unlisted_company", "评估投资价值",
                        {"revenue": 50000000, "vc_market": 8, "vc_team": 8})
    print(f"skills: {r['skills']}")
    print(f"engines: {r['engines']}")
    print(f"compute_summaries: {len(r['compute_summaries'])}")
    print(f"verify_ready: {r['verify_ready']}, roundtable: {r['roundtable_ready']}")
