"""
2号分析师 Compute Engine V3 — 三路径计算引擎

Path 1: V30 StructuredData (当 DataCollector 产出匹配的结构化数据时)
Path 2: V51 直接参数 API (当结构化数据不可用时，直接从 data dict 提取参数)
Path 3: compute_from_kp 统一入口 (最简路径，只需几个关键参数)

新增:
- Damodaran ERP 集成 → WACC 不再硬编码
- Pattern Library 集成 → deterministic pattern detection
- DecisionHub 集成 → 数学信号融合
- Global Benchmark 集成 → 全球同业对标
"""

import sys, json, logging
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.compute_engine.v3")

# ============================================================
# Knowledge Module Imports (E:/9728 All Integrated)
# ============================================================
_KNOWLEDGE_MODULES_LOADED = False
_THINKING_MODELS_LOADED = False
_KELLY_LOADED = False

try:
    from core.knowledge.xiao_jing_framework import analyze as xiao_jing_analyze
    from core.knowledge.page_24_models import run_page_models
    from core.knowledge.serenity_chain import run_serenity
    from core.knowledge.logic_models import audit_logic
    from core.knowledge.greenwald_strategy import analyze as greenwald_analyze
    from core.knowledge.wang_siyu_analysis import analyze as wang_siyu_analyze
    from core.knowledge.liu_run_logic import analyze_logic as liu_run_analyze
    _KNOWLEDGE_MODULES_LOADED = True
except ImportError as e:
    import logging as _lg2
    _lg2.getLogger("2hao.compute_engine.v3").warning(f"Knowledge modules not loaded: {e}")

try:
    from core.thinking_models import run_multi_model, MultiModelResult
    _THINKING_MODELS_LOADED = True
except ImportError as e:
    import logging as _lg3
    _lg3.getLogger("2hao.compute_engine.v3").warning(f"Thinking models not loaded: {e}")

try:
    from core.compute.kelly_formula import kelly_bet, KellyResult
    _KELLY_LOADED = True
except ImportError as e:
    import logging as _lg4
    _lg4.getLogger("2hao.compute_engine.v3").warning(f"Kelly not loaded: {e}")

_SYNTHESIS_LOADED = False
try:
    from core.synthesis.synthesis_engine import run_synthesis, synthesis_to_dict
    _SYNTHESIS_LOADED = True
except ImportError as e:
    import logging as _lg5
    _lg5.getLogger("2hao.compute_engine.v3").warning(f"Synthesis not loaded: {e}")


def _parse_year_key(yr) -> int | None:
    """将年份键规范化为 int。

    兼容 '2024' → 2024、'2024E'/'2025E'（E 后缀预测年份）→ 2024/2025。
    返回 None 表示该键不是有效年份（如 'Figaro'、'工业安全'、'上游_敏感材料芯片'）。
    修复：混合类型 list 导致 sort() 抛 `'<' not supported between instances of 'str' and 'int'`
    → 单模块抛异常 → compute() 整体失败 → compute_results={} → 图表全模板 → Gate score=0。
    """
    if yr is None:
        return None
    if isinstance(yr, int):
        return yr
    if isinstance(yr, float):
        return int(yr) if yr.is_integer() else None
    if not isinstance(yr, str):
        return None
    s = yr.strip()
    # 预测年份后缀：'2025E' / '2026e'（大小写均可）→ 2025 / 2026
    if len(s) >= 4 and s[:4].isdigit():
        suffix = s[4:]
        if len(s) == 4 and suffix == "":
            return int(s)
        if suffix.lower() == "e":
            return int(s[:4])
        return None
    return None


def _clean_num(v) -> float:
    """清洗 akshare 中文单位数值：'29.12亿' → 29.12e8, '8.67万' → 8.67e4, '--' → 0"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace(" ", "")
    if not s or s in ("--", "-", "nan", "None", ""):
        return 0.0
    mult = 1.0
    for unit, m in [("万亿", 1e12), ("千亿", 1e11), ("百亿", 1e10), ("十亿", 1e9),
                    ("亿", 1e8), ("千万", 1e7), ("百万", 1e6), ("万", 1e4)]:
        if unit in s:
            mult = m
            s = s.replace(unit, "")
            break
    # 处理百分比/符号残留
    s = s.replace("%", "").replace("元", "").strip()
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


class ComputeEngine:
    """计算引擎 V3 — 三路径计算"""

    def __init__(self):
        self._pipeline = None
        self._damodaran = None
        self._patterns = None
        self._decision_hub = None

    def compute(self, financial_data: dict, report_type: str = "listed_company") -> dict:
        result = {"status": "incomplete"}

        # Path 1: V30 StructuredData
        structured = self._build_v30_structured(financial_data)
        if structured and structured.financials:
            pipeline_results = self._run_v30_pipeline(structured)
            if pipeline_results:
                result.update(pipeline_results)

        # Path 2: V51 直接参数
        dcf_params = self._extract_dcf_params(financial_data)
        comp_params = self._extract_comparable_params(financial_data)

        if dcf_params:
            dcf_result = self._run_v51_dcf(dcf_params, financial_data)
            if dcf_result:
                result["dcf_valuation"] = dcf_result
        if comp_params:
            comp_result = self._run_v51_comparable(comp_params)
            if comp_result:
                result["comparable_valuation"] = comp_result
        if dcf_params and comp_params:
            scenario = self._run_v51_scenario(dcf_params, comp_params, financial_data)
            if scenario:
                result["scenario_analysis"] = scenario

        bridges = self._run_financial_bridges(financial_data)
        if bridges:
            result.update(bridges)

        kp_result = self._try_compute_from_kp(financial_data)
        if kp_result:
            result["kp_compute"] = kp_result

        result["damodaran_erp"] = self._compute_damodaran_erp()
        result["pattern_signals"] = self._run_pattern_detection(financial_data)
        result["fusion_decision"] = self._run_decision_fusion(result.get("pattern_signals", {}))
        result["sotp_valuation"] = self._compute_sotp(financial_data)
        result["global_benchmark"] = self._compute_global_benchmark(financial_data)
        # R58（2026-08-03）：并购整合评估——接入 consolidation 模块
        try:
            result["consolidation"] = self._run_consolidation(financial_data)
        except Exception as _ce:
            logger.debug("[CONSOLIDATION] %s", _ce)
        industry = financial_data.get("report_type", "")
        result["industry_router"] = self._get_industry_pipeline(industry)
        me_bridges = self._compute_margin_expense_bridge(financial_data)
        result.update(me_bridges)
        result["numeric_gate"] = self._run_numeric_gate(result)
        result["heritage"] = {"status": "removed", "reason": "Heritage DEPRECATED"}

        # === Knowledge Module Integration ===
        result["xiao_jing"] = self._run_xiao_jing(financial_data)
        result["page_models"] = self._run_page_models(financial_data)
        result["serenity"] = self._run_serenity_chain(financial_data)
        result["logic_audit"] = self._run_logic_audit(financial_data)
        result["greenwald"] = self._run_greenwald(financial_data)
        result["wang_siyu"] = self._run_wang_siyu(financial_data)
        result["liu_run"] = self._run_liu_run(financial_data)
        result["kelly"] = self._run_kelly(financial_data)
        result["thinking_models"] = self._run_thinking_models(financial_data)
        result["synthesis"] = self._run_synthesis(result)
        # R59（2026-08-03）：接线 core/tools 5 个新工具
        result["tool_modules"] = self._run_tool_modules(financial_data)

        ok_modules = [k for k, v in result.items() if isinstance(v, dict) and v.get("status") == "ok"]
        error_modules = [k for k, v in result.items() if isinstance(v, dict) and v.get("status") == "error"]
        result["_summary"] = {"ok": len(ok_modules), "error": len(error_modules), "modules_ok": ok_modules}
        if ok_modules and not error_modules:
            result["status"] = "complete"
        elif ok_modules:
            result["status"] = "partial"
        return result

    def _build_v30_structured(self, data: dict):
        try:
            from core.models import StructuredData, CompanyProfile, AnnualFinancials
        except ImportError:
            return None

        profile = CompanyProfile(stock_code="", stock_name=data.get("asset", ""), industry=data.get("report_type", ""))
        financials = []
        revenue_data, profit_data = {}, {}

        cd = data.get("chart_data", {})
        rev_raw = cd.get("fig_revenue_trend", cd.get("revenue_history", cd.get("revenue", {})))
        profit_raw = cd.get("fig_profitability", cd.get("profit_history", cd.get("net_profit", {})))

        if isinstance(rev_raw, dict):
            for year_str, val in rev_raw.items():
                try:
                    year = _parse_year_key(year_str)
                    if year is None or year < 2000 or year > 2030:
                        continue
                except Exception:
                    continue
                if isinstance(val, dict):
                    revenue_data[year] = _clean_num(val.get("revenue", val.get("营收", val.get("营业收入", 0))))
                    profit_data[year] = _clean_num(val.get("net_profit", val.get("净利润", 0)))
                else:
                    revenue_data[year] = _clean_num(val)

        if isinstance(profit_raw, dict) and not profit_data:
            for year_str, val in profit_raw.items():
                try:
                    year = _parse_year_key(year_str)
                    if year is None or year < 2000 or year > 2030:
                        continue
                except Exception:
                    continue
                if isinstance(val, dict):
                    profit_data[year] = _clean_num(val.get("net_profit", val.get("净利润", 0)))
                else:
                    profit_data[year] = _clean_num(val)

        all_years = sorted(set(list(revenue_data.keys()) + list(profit_data.keys())))
        for year in all_years:
            financials.append(AnnualFinancials(stock_code="", stock_name=data.get("asset", ""),
                fiscal_year=year, revenue=revenue_data.get(year, 0), net_profit=profit_data.get(year, 0),
                source="tavily+akshare", data_quality="estimated"))

        return StructuredData(profile=profile, financials=financials) if financials else None

    def _run_v30_pipeline(self, structured) -> dict:
        try:
            from core.compute.pipeline import run_compute_pipeline
            pr = run_compute_pipeline(structured, enable_gate=True, enable_valuation=True)
            if pr:
                return {"_v30_pipeline": {"status": "ok", "revenue_bridge": pr.revenue_bridge,
                    "margin_bridge": pr.margin_bridge, "expense_bridge": pr.expense_bridge, "numeric_gate": pr.numeric_gate_report}}
        except Exception as e:
            logger.debug("V30 pipeline: %s", e)
        return {}

    def _extract_dcf_params(self, data: dict) -> dict:
        cd = data.get("chart_data", {})
        val = cd.get("fig_valuation", {})
        price = float(val.get("price", 0)) if val.get("price") else 0
        shares = float(val.get("shares", 0)) if val.get("shares") else 0
        net_debt = float(val.get("net_debt", 0)) if val.get("net_debt") else 0
        fcf = float(val.get("free_cash_flow", val.get("fcf", 0))) if val.get("free_cash_flow", val.get("fcf")) else 0
        eps = float(val.get("eps", 0)) if val.get("eps") else 0
        bvps = float(val.get("bvps", 0)) if val.get("bvps") else 0
        if not any([price, shares, fcf, eps]): return {}
        return {"price": price, "shares": shares, "net_debt": net_debt, "fcf": fcf, "eps": eps, "bvps": bvps}

    def _extract_comparable_params(self, data: dict) -> dict:
        cd = data.get("chart_data", {})
        val = cd.get("fig_valuation", {})
        eps = float(val.get("eps", 0)) if val.get("eps") else 0
        bvps = float(val.get("bvps", 0)) if val.get("bvps") else 0
        price = float(val.get("price", 0)) if val.get("price") else 0
        if not eps and not bvps: return {}
        return {"eps": eps, "bvps": bvps, "price": price}

    def _compute_wacc_with_erp(self) -> float:
        try:
            from core.compute.financial.damodaran_erp import DamodaranERP
            china = DamodaranERP().for_country("中国")
            total_erp = china.get("total_erp", 0.0729)
            rf, beta, cd_rate, dr, tr = 0.025, 1.0, 0.04, 0.20, 0.25
            coe = rf + beta * total_erp
            return round(coe * (1 - dr) + cd_rate * dr * (1 - tr), 4)
        except Exception:
            return 0.10

    def _run_v51_dcf(self, params: dict, data: dict) -> dict:
        try:
            from core.compute.compute import DCFInput, run_dcf
            wacc = self._compute_wacc_with_erp()
            inp = DCFInput(free_cash_flow=params["fcf"], shares_outstanding=params["shares"] or 1,
                          net_debt=params["net_debt"], wacc=wacc)
            result = run_dcf(inp, current_price=params["price"], current_eps=params.get("eps", 0))
            if result and result.fair_value_per_share > 0:
                # R56（2026-08-03）：估值规则护栏——知识库规则校验 DCF 结果
                _guards = []
                try:
                    from core.compute.valuation_guardrails import validate_dcf_guards
                    _sensitivity = getattr(result, "sensitivity_table", None)
                    _tv_pct = 0.0
                    if isinstance(_sensitivity, dict) and _sensitivity.get("enterprise_value"):
                        _ev = _sensitivity.get("enterprise_value", 0)
                        _tv = _sensitivity.get("terminal_value", 0)
                        if _ev and _tv:
                            _tv_pct = _tv / _ev
                    _guards = validate_dcf_guards(
                        dcf_result=result,
                        wacc=wacc,
                        terminal_growth=getattr(inp, "terminal_growth", 0.0) or 0.0,
                        tv_pct=_tv_pct,
                        fair_value=result.fair_value_per_share,
                    )
                except Exception as _ge:
                    logger.debug("[DCF-GUARD] %s", _ge)
                _result = {
                    "fair_value": round(result.fair_value_per_share, 2), "upside_pct": result.upside_pct,
                    "implied_pe": result.implied_pe, "enterprise_value": result.enterprise_value,
                    "equity_value": result.equity_value, "assumptions": result.assumptions,
                    "sensitivity_table": result.sensitivity_table, "wacc": f"{wacc*100:.1f}%",
                }
                if _guards:
                    _result["guardrail_issues"] = _guards
                    logger.warning("[DCF-GUARD] %d 项估值护栏触发: %s", len(_guards), _guards[0])
                return {"status": "ok", "method": "V51_direct", "result": _result}
            return {"status": "skip", "reason": f"DCF zero fair_value"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_v51_comparable(self, params: dict) -> dict:
        try:
            from core.compute.compute import run_comparable
            result = run_comparable(company_eps=params.get("eps", 0), company_bvps=params.get("bvps", 0))
            if result and result.summary:
                _result = {
                    "target_pe": result.target_pe, "implied_pe_price": result.implied_pe_price,
                    "peers": result.peers, "summary": result.summary}
                # R56/FP4：可比估值护栏
                try:
                    from core.compute.valuation_guardrails import validate_comparable_guards
                    _guards = validate_comparable_guards(
                        target_pe=getattr(result, "target_pe", 0) or 0,
                        implied_price=getattr(result, "implied_pe_price", 0) or 0,
                        peer_count=len(result.peers) if hasattr(result, "peers") and result.peers else 0,
                        company_eps=params.get("eps", 0) or 0,
                    )
                    if _guards:
                        _result["guardrail_issues"] = _guards
                        logger.warning("[COMP-GUARD] %d 项可比护栏触发: %s", len(_guards), _guards[0])
                except Exception as _ge:
                    logger.debug("[COMP-GUARD] %s", _ge)
                return {"status": "ok", "method": "V51_direct", "result": _result}
            return {"status": "skip", "reason": "comparable empty"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_v51_scenario(self, dcf_params: dict, comp_params: dict, data: dict) -> dict:
        try:
            from core.compute.compute import DCFInput, run_dcf, run_scenario
            wacc = self._compute_wacc_with_erp()
            inp = DCFInput(free_cash_flow=dcf_params["fcf"], shares_outstanding=dcf_params["shares"] or 1,
                          net_debt=dcf_params["net_debt"], wacc=wacc)
            dcf_val = run_dcf(inp, dcf_params.get("price", 0), dcf_params.get("eps", 0)).fair_value_per_share
            current_price = dcf_params.get("price", 0) or comp_params.get("price", 0)
            if current_price <= 0: return {"status": "skip", "reason": "no price"}
            scenario = run_scenario(current_price, dcf_val, dcf_val * 0.85)
            _result = {
                "bull_price": round(scenario.bull_price, 2), "base_price": round(scenario.base_price, 2),
                "bear_price": round(scenario.bear_price, 2), "weighted_target": round(scenario.weighted_target, 2),
                "upside_pct": scenario.upside, "downside_pct": scenario.downside,
                "risk_reward_ratio": scenario.risk_reward}
            # R56/FP4：情景分析护栏（单调性/风险收益比/极差）
            try:
                from core.compute.valuation_guardrails import validate_scenario_guards
                _guards = validate_scenario_guards(
                    bull=scenario.bull_price, base=scenario.base_price,
                    bear=scenario.bear_price, risk_reward=scenario.risk_reward)
                if _guards:
                    _result["guardrail_issues"] = _guards
                    logger.warning("[SCEN-GUARD] %d 项情景护栏触发: %s", len(_guards), _guards[0])
            except Exception as _ge:
                logger.debug("[SCEN-GUARD] %s", _ge)
            return {"status": "ok", "method": "V51_direct", "result": _result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_financial_bridges(self, data: dict) -> dict:
        result = {}
        cd = data.get("chart_data", {})
        rev_data = cd.get("fig_revenue_trend", cd.get("revenue_history", {}))
        if isinstance(rev_data, dict) and len(rev_data) >= 2:
            yrs = []
            for yr, val in rev_data.items():
                try:
                    y = _parse_year_key(yr)
                    if y is None:
                        continue  # 跳过非年份键（如 '2025E' 之外的文本键）
                    v = float(val.get("revenue", val) if isinstance(val, dict) else val) if val else 0
                    yrs.append((y, v))
                except Exception:
                    pass  # Layer 5: bare except replaced with Exception
            yrs.sort(key=lambda t: t[0])
            if len(yrs) >= 2:
                g = round((yrs[-1][1] - yrs[0][1]) / yrs[0][1] * 100, 2) if yrs[0][1] > 0 else 0
                result["revenue_bridge"] = {"status": "ok", "method": "direct_extract",
                    "result": {"period": f"{yrs[0][0]}->{yrs[-1][0]}", "total_revenue_growth_pct": g,
                        "base_revenue": yrs[0][1], "current_revenue": yrs[-1][1], "years": dict(yrs)}}
        return result

    def _try_compute_from_kp(self, data: dict) -> dict:
        try:
            from core.compute.compute import compute_from_kp
            cd = data.get("chart_data", {})
            val = cd.get("fig_valuation", {})
            price = float(val.get("price", 0)) if val.get("price") else 0
            eps = float(val.get("eps", 0)) if val.get("eps") else 0
            bvps = float(val.get("bvps", 0)) if val.get("bvps") else 0
            fcf = float(val.get("free_cash_flow", val.get("fcf", 0))) if val.get("free_cash_flow", val.get("fcf")) else 0
            shares = float(val.get("shares", 0)) if val.get("shares") else 0
            if not any([price, eps, fcf, shares]): return {"status": "skip", "reason": "insufficient KP data"}
            result = compute_from_kp(price=price, eps=eps, bvps=bvps, fcf=fcf, shares=shares, current_price=price)
            if result: return {"status": "ok", "method": "compute_from_kp", "result": result}
            return {"status": "skip", "reason": "kp empty"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _compute_damodaran_erp(self) -> dict:
        try:
            from core.compute.financial.damodaran_erp import DamodaranERP
            china = DamodaranERP().for_country("中国")
            return {"status": "ok", "method": "DamodaranERP", "result": {
                "country": "中国", "rating": china.get("rating", "A1"),
                "default_spread": china.get("default_spread", 0),
                "country_risk_premium": china.get("country_risk_premium", 0),
                "mature_market_erp": china.get("mature_market_erp", 0.0596),
                "total_erp": china.get("total_erp", 0.0729)}}
        except Exception as e:
            return {"status": "skip", "reason": f"DamodaranERP: {e}"}

    def _run_pattern_detection(self, data: dict) -> dict:
        try:
            from core.compute.patterns import detect_all
            cd = data.get("chart_data", {})
            fd = {}
            rev = cd.get("fig_revenue_trend", {})
            if isinstance(rev, dict):
                for yr, val in rev.items():
                    try:
                        y = _parse_year_key(yr)
                        if y is None:
                            continue
                        if isinstance(val, dict):
                            fd[y] = {"revenue": val.get("revenue", val.get("营业收入", 0)),
                                     "net_profit": val.get("net_profit", val.get("净利润", 0)),
                                     "gross_margin": val.get("gross_margin", val.get("毛利率", 0))}
                        else:
                            fd[y] = {"revenue": float(val)} if val else {"revenue": 0}
                    except Exception:
                        pass  # Layer 5: bare except replaced with Exception
            if not fd: return {"status": "skip", "reason": "no financial time series"}
            results = detect_all(fd)
            return {"status": "ok", "method": "PatternLibrary", "result": {
                pid: {"pattern_name": pr.pattern_name, "signal": pr.signal,
                      "confidence": pr.confidence, "reasoning": pr.reasoning}
                for pid, pr in results.items()}}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_decision_fusion(self, pattern_results: dict) -> dict:
        if not pattern_results or pattern_results.get("status") != "ok":
            return {"status": "skip", "reason": "no pattern results"}
        try:
            from core.compute.decision_hub import DecisionHub, from_pattern_results
            signals = from_pattern_results(pattern_results.get("result", {}))
            if not signals: return {"status": "skip", "reason": "no non-neutral signals"}
            d = DecisionHub.fuse(signals)
            return {"status": "ok", "method": "DecisionHub", "result": {
                "bull_prob": round(d.bull_prob, 4), "bear_prob": round(d.bear_prob, 4),
                "neutral_prob": round(d.neutral_prob, 4), "conviction": round(d.conviction, 4),
                "n_signals": d.n_signals, "dominant_signal": d.dominant_signal}}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    # ============================================================
    # Knowledge Module Runners (E:/9728 All Integrated)
    # ============================================================

    def _run_xiao_jing(self, data: dict) -> dict:
        try:
            result = xiao_jing_analyze(data)
            return {"status": "ok", "method": "xiao_jing", "life_cycle": result.life_cycle, "composite_score": result.composite_score, "recommendation": result.recommendation}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_page_models(self, data: dict) -> dict:
        try:
            result = run_page_models(data)
            return {"status": "ok", "method": "page_models", "diversity_score": result.diversity_score, "consensus": result.consensus, "recommendation": result.recommendation}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_serenity_chain(self, data: dict) -> dict:
        try:
            import json as _j
            text = data.get("text", "") or data.get("report_text", "") or _j.dumps(data, ensure_ascii=False)
            result = run_serenity(text)
            return {"status": "ok", "method": "serenity", "all_passed": result.all_passed, "failed_steps": result.failed_steps}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_logic_audit(self, data: dict) -> dict:
        try:
            import json as _j
            text = data.get("text", "") or data.get("report_text", "") or _j.dumps(data, ensure_ascii=False)
            result = audit_logic(text)
            return {"status": "ok", "method": "logic_audit", "mece_score": result.mece_score, "pyramid_score": result.pyramid_principle, "recommendations": result.recommendations}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_greenwald(self, data: dict) -> dict:
        try:
            result = greenwald_analyze(data)
            return {"status": "ok", "method": "greenwald", "barrier_level": result.barriers.barrier_level, "barrier_score": result.barriers.overall_barrier, "game_type": result.game_type, "recommendation": result.recommendation}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_wang_siyu(self, data: dict) -> dict:
        try:
            result = wang_siyu_analyze(data)
            return {"status": "ok", "method": "wang_siyu", "market_score": result.market_score, "competition_type": result.competition_type, "composite_score": result.composite_score, "recommendation": result.recommendation}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_liu_run(self, data: dict) -> dict:
        try:
            result = liu_run_analyze(data)
            return {"status": "ok", "method": "liu_run", "composite_score": result.composite_score, "recommendation": result.recommendation}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_kelly(self, data: dict) -> dict:
        try:
            upside = data.get("kelly_upside", 0) or data.get("upside_pct", 0)
            downside = data.get("kelly_downside", 0) or data.get("downside_pct", 1)
            wp = data.get("kelly_win_prob", 0) or data.get("win_prob", 0.5)
            if upside <= 0:
                return {"status": "skip", "reason": "no_upside_data"}
            r = kelly_bet(upside, max(downside, 1), wp)
            return {"status": "ok", "method": "kelly", "optimal_fraction": r.optimal_fraction, "half_kelly": r.half_kelly, "odds_ratio": r.odds_ratio, "edge": r.edge, "interpretation": r.interpretation}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_thinking_models(self, data: dict) -> dict:
        try:
            result = run_multi_model(data)
            return {"status": "ok", "method": "thinking_models", "consensus": result.consensus, "bullish_count": result.bullish_count, "bearish_count": result.bearish_count, "avg_confidence": result.avg_confidence, "recommendation": result.recommendation}
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    def _run_synthesis(self, compute_results: dict) -> dict:
        """Meta-Reasoning Synthesis - Phase 4"""
        try:
            rt = compute_results.get("report_type", "industry_deep")
            r = run_synthesis(compute_results, rt)
            return synthesis_to_dict(r)
        except Exception as e:
            return {"status": "skip", "reason": str(e)}

    # ════════════════════════════════════════════
    # R59：接线 core/tools 5 个新工具
    # ════════════════════════════════════════════
    def _run_tool_modules(self, data: dict) -> dict:
        """接线 elasticity/signal_chain/moat/life_cycle/multi_model 工具。

        此前这些工具在 core/tools/ 存在但主管线 0 引用（"造零件≠组装整机"）。
        现在在 compute 中调用，把结构化结果注入，供对应 SAC 维度写正文。
        """
        cd = data.get("chart_data", {})
        val = cd.get("fig_valuation", {})
        industry = str(val.get("industry", data.get("industry", "")) or "")
        company = str(val.get("company", data.get("company", "")) or "")

        modules = {}
        # 1. 弹性分析（elasticity_analysis 维度）
        try:
            from core.tools.elasticity_analyzer import ElasticityAnalyzer
            ea = ElasticityAnalyzer()
            demand = ea.classify_demand_type(industry) if industry else None
            # DemandType 是枚举，is_cyclical 是 ElasticityProfile 的方法
            _is_cyc = None
            _profile = ea.estimate_income_elasticity(industry) if industry and hasattr(ea, "estimate_income_elasticity") else None
            if _profile and hasattr(_profile, "is_cyclical"):
                _is_cyc = _profile.is_cyclical()
            modules["elasticity"] = {
                "demand_type": demand.value if demand and hasattr(demand, "value") else "unknown",
                "is_cyclical": _is_cyc,
            }
        except Exception as e:
            modules["elasticity"] = {"status": "skip", "reason": str(e)[:60]}

        # 2. 信号链（signal_chain 维度）——triggered_count/total_count 是属性
        try:
            from core.tools.signal_chain import SignalChainBuilder
            scb = SignalChainBuilder()
            chain = scb.build_chain(industry) if industry else None
            if chain:
                modules["signal_chain"] = {
                    "triggered": chain.triggered_count,
                    "total": chain.total_count,
                    "leading": [s.name for s in chain.leading][:3] if hasattr(chain, "leading") else [],
                    "coincident": [s.name for s in chain.coincident][:3] if hasattr(chain, "coincident") else [],
                    "lagging": [s.name for s in chain.lagging][:3] if hasattr(chain, "lagging") else [],
                    "confidence": chain.confidence if hasattr(chain, "confidence") else "",
                }
            else:
                modules["signal_chain"] = {"status": "skip", "reason": "no chain data"}
        except Exception as e:
            modules["signal_chain"] = {"status": "skip", "reason": str(e)[:60]}

        # 3. 护城河（competitive 维度补充）——需要 moat_data 结构化输入
        try:
            from core.tools.moat_analyzer import MoatAnalyzer, MoatType
            ma = MoatAnalyzer()
            # 从 chart_data 提取护城河特征（若无则用空 dict，工具会返回窄护城河）
            _moat_data = {
                MoatType.TECHNOLOGY: {"strength": "中", "durability": "可维持",
                                      "source": "data_dict", "evidence": ["研发投入"], "risks": ["技术迭代"]},
                MoatType.BRAND: {"strength": "中", "durability": "可维持",
                                 "source": "data_dict", "evidence": ["品牌认知"], "risks": ["竞争"]},
            } if company else {}
            moat = ma.assess(company, _moat_data) if company else None
            if moat:
                modules["moat"] = {
                    "overall": moat.overall_moat if hasattr(moat, "overall_moat") else "unknown",
                    "strong": [m.type.value if hasattr(m.type, "value") else str(m.type)
                               for m in moat.assessments if m.strength == "强"][:3],
                    "summary": moat.summary() if hasattr(moat, "summary") else "",
                }
            else:
                modules["moat"] = {"status": "skip", "reason": "no company"}
        except Exception as e:
            modules["moat"] = {"status": "skip", "reason": str(e)[:60]}

        # 4. 生命周期（life_cycle 维度）——需要 stage 参数
        try:
            from core.tools.life_cycle_mapper import LifeCycleMapper
            lcm = LifeCycleMapper()
            # 从 data 判断阶段（渗透率/增速），默认成长期
            _pen = val.get("penetration_pct")
            _growth = val.get("growth_rate")
            _stage = "growth"
            if _pen is not None and float(_pen) < 0.05:
                _stage = "introduction"
            elif _pen is not None and float(_pen) > 0.5:
                _stage = "maturity"
            lc = lcm.analyze(industry, _stage, penetration_rate=float(_pen) if _pen else None,
                             growth_rate=float(_growth) if _growth else None) if industry else None
            if lc:
                modules["life_cycle"] = {
                    "stage": lc.stage.value if hasattr(lc, "stage") and hasattr(lc.stage, "value") else str(getattr(lc, "stage", "")),
                    "next_stage": str(getattr(lc, "next_stage", "")),
                    "time_to_next": str(getattr(lc, "time_to_next", "")),
                    "summary": lc.summary() if hasattr(lc, "summary") else "",
                }
            else:
                modules["life_cycle"] = {"status": "skip", "reason": "no data"}
        except Exception as e:
            modules["life_cycle"] = {"status": "skip", "reason": str(e)[:60]}

        # 5. 多模型校验（FP3 协作维度）
        try:
            from core.tools.multi_model_validator import MultiModelValidator
            mmv = MultiModelValidator()
            models = mmv.get_relevant_models("industry_deep") if hasattr(mmv, "get_relevant_models") else []
            modules["multi_model"] = {
                "models": models[:5],
                "menu": mmv.get_model_menu() if hasattr(mmv, "get_model_menu") else "",
            }
        except Exception as e:
            modules["multi_model"] = {"status": "skip", "reason": str(e)[:60]}

        # 6. R83（2026-08-07）：决策推理引擎（decision_memo 核心内容层）
        # 把"困境→卡位→放量→延伸→投入/损失"决策链做成确定性计算，
        # 注入写作 prompt 供 decision_memo 引用——根治"报告无推理"问题。
        try:
            from core.decision_engine import DecisionEngine
            de = DecisionEngine().analyze(data)
            _verdict = de.get("decision", {}).get("verdict", "")
            if _verdict and "待评估" not in str(_verdict):
                de["status"] = "ok"
                modules["decision"] = de
            else:
                modules["decision"] = {"status": "skip", "reason": "no verdict/data"}
        except Exception as e:
            modules["decision"] = {"status": "skip", "reason": str(e)[:60]}

        ok = {k: v for k, v in modules.items() if v.get("status") != "skip"}
        return {"status": "ok" if ok else "skip", "modules": modules, "ok_count": len(ok)}

# ============================================================
# APPENDIX: 遗漏模块补丁 — 追加到 compute_engine.py 末尾
# 包含: SOTP, NumericGate, IndustryRouter, GlobalBenchmark, MarginBridge, ExpenseBridge
# ============================================================

    # ════════════════════════════════════════════
    # Heritage 方法论
    # ════════════════════════════════════════════
    
    def _extract_sotp_segments(self, data: dict) -> list:
        """从 data dict 提取业务分部数据"""
        cd = data.get("chart_data", {})
        segments_raw = cd.get("fig_segments", cd.get("segments", {}))
        if not isinstance(segments_raw, dict):
            return []

        segments = []
        for name, info in segments_raw.items():
            if isinstance(info, dict):
                segments.append({
                    "name": name,
                    "revenue": float(info.get("revenue", info.get("营收", 0)) or 0),
                    "profit": float(info.get("profit", info.get("净利润", info.get("net_profit", 0))) or 0),
                    "method": info.get("method", "PE"),
                    "pe": float(info.get("pe", 0)) if info.get("pe") else None,
                    "ps": float(info.get("ps", 0)) if info.get("ps") else None,
                })
            elif isinstance(info, (int, float)):
                segments.append({"name": name, "revenue": float(info), "profit": 0,
                                 "method": "PS", "pe": None, "ps": 15.0})
        return segments

    def _compute_sotp(self, data: dict) -> dict:
        """SOTP 分部加总估值"""
        try:
            from core.compute.valuation.sotp import compute_sotp, SOTPSegmentInput

            cd = data.get("chart_data", {})
            val = cd.get("fig_valuation", {})
            segments_raw = self._extract_sotp_segments(data)
            if not segments_raw:
                return {"status": "skip", "reason": "no segment data"}

            seg_inputs = []
            for s in segments_raw:
                seg_inputs.append(SOTPSegmentInput(
                    name=s["name"], revenue_bn=s["revenue"], profit_bn=s["profit"],
                    valuation_method=s["method"], peer_pe=s["pe"], peer_ps=s["ps"],
                    description=s.get("description", ""),
                ))

            cash = float(val.get("cash_equivalents", 0)) if val.get("cash_equivalents") else 0
            net_debt = float(val.get("net_debt", 0)) if val.get("net_debt") else 0
            shares = int(float(val.get("shares", 0))) if val.get("shares") else 0

            result = compute_sotp(
                company=data.get("asset", ""), stock_code="",
                segments=seg_inputs, cash_and_equivalents=cash,
                net_debt=net_debt, total_shares=shares,
            )
            if result and result.total_segments_value > 0:
                return {"status": "ok", "method": "SOTP", "result": {
                    "total_segments_value": result.total_segments_value,
                    "equity_value": result.equity_value,
                    "target_price": result.target_price,
                    "segments": result.segments,
                    "warnings": result.warnings,
                    "formatted": "",  # from format_sotp_for_report
                }}
            return {"status": "skip", "reason": "SOTP produced zero value"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ════════════════════════════════════════════
    # Numeric Gate 数值门禁
    # ════════════════════════════════════════════
    def _run_numeric_gate(self, compute_results: dict) -> dict:
        """验证计算结果的数值合理性"""
        checks = []

        # 检查 DCF
        dcf = compute_results.get("dcf_valuation", {})
        if dcf.get("status") == "ok":
            r = dcf.get("result", {})
            fv = r.get("fair_value", 0)
            if fv <= 0:
                checks.append({"module": "dcf", "issue": "fair_value<=0", "severity": "error"})
            elif fv > 10000:
                checks.append({"module": "dcf", "issue": f"fair_value={fv}异常高", "severity": "warn"})

        # 检查增长率
        rb = compute_results.get("revenue_bridge", {})
        if rb.get("status") == "ok":
            g = rb.get("result", {}).get("total_revenue_growth_pct", 0)
            if abs(g) > 500:
                checks.append({"module": "revenue", "issue": f"growth={g}%异常", "severity": "warn"})

        return {"status": "ok" if not any(c["severity"]=="error" for c in checks) else "error",
                "checks": checks, "n_checks": len(checks),
                "n_errors": sum(1 for c in checks if c["severity"]=="error")}

    # ════════════════════════════════════════════
    # Industry Router 行业路由
    # ════════════════════════════════════════════
    FINANCIAL_INDUSTRIES = {"保险","银行","券商","证券","多元金融"}
    CONSUMER_INDUSTRIES = {"白酒","食品饮料","啤酒","饮料制造","调味品","乳品"}
    TECH_INDUSTRIES = {"半导体","软件","自动驾驶","芯片","计算机","人工智能","AI","SaaS"}
    MANUFACTURING_INDUSTRIES = {"光伏","新能源","电池","新能源汽车","电气设备","新材料"}

    def _classify_industry(self, industry_label: str) -> str:
        """行业分类路由"""
        if not industry_label: return "manufacturing"
        for kw_set, pipe in [(self.FINANCIAL_INDUSTRIES, "financial"),
                             (self.CONSUMER_INDUSTRIES, "consumer"),
                             (self.TECH_INDUSTRIES, "tech")]:
            for kw in kw_set:
                if kw in industry_label: return pipe
        return "manufacturing"

    def _get_industry_pipeline(self, industry: str) -> dict:
        """获取行业特定管线配置"""
        pipe = self._classify_industry(industry)
        configs = {
            "financial": {"valuation_prefer": "PB", "key_metrics": ["roe","pb","nbv","net_interest_margin"]},
            "consumer": {"valuation_prefer": "PE", "key_metrics": ["revenue_growth","gross_margin","channel_count"]},
            "tech": {"valuation_prefer": "PS", "key_metrics": ["r_and_d_pct","revenue_growth","gross_margin"]},
            "manufacturing": {"valuation_prefer": "PE", "key_metrics": ["revenue_growth","gross_margin","capacity_utilization"]},
        }
        return configs.get(pipe, configs["manufacturing"])

    # ════════════════════════════════════════════
    # Global Benchmark 全球对标（简化版，不依赖yfinance）
    # ════════════════════════════════════════════
    def _compute_global_benchmark(self, data: dict) -> dict:
        """全球同业对标 (简化版，零API依赖)"""
        try:
            cd = data.get("chart_data", {})
            val = cd.get("fig_valuation", {})
            peers_data = cd.get("fig_industry_board", cd.get("peers", []))

            target_pe = float(val.get("pe", val.get("pe_ttm", 0))) if val.get("pe", val.get("pe_ttm")) else None
            target_ps = float(val.get("ps", 0)) if val.get("ps") else None
            target_roe = float(val.get("roe", 0)) if val.get("roe") else None

            if not any([target_pe, target_ps, target_roe]) and not peers_data:
                return {"status": "skip", "reason": "no benchmark data"}

            # 从 peers/list 提取行业均值
            peer_metrics = {"pe": [], "ps": [], "roe": [], "gross_margin": []}
            if isinstance(peers_data, list):
                for p in peers_data:
                    if isinstance(p, dict):
                        if p.get("pe"): peer_metrics["pe"].append(float(p["pe"]))
                        if p.get("ps"): peer_metrics["ps"].append(float(p["ps"]))
                        if p.get("roe"): peer_metrics["roe"].append(float(p["roe"]))

            def safe_avg(vals):
                return round(sum(vals)/len(vals), 2) if vals else None

            industry = data.get("report_type", "")
            pipe = self._classify_industry(industry)

            return {"status": "ok", "method": "GlobalBenchmark_simple", "result": {
                "industry_pipeline": pipe,
                "preferred_metric": "PS" if pipe=="tech" else "PB" if pipe=="financial" else "PE",
                "target_pe": target_pe,
                "industry_avg_pe": safe_avg(peer_metrics.get("pe",[])),
                "target_roe": target_roe,
                "industry_avg_roe": safe_avg(peer_metrics.get("roe",[])),
                "n_peers": len(peer_metrics.get("pe",[])),
                "peer_count": len(peers_data) if isinstance(peers_data, list) else 0,
                "industry": industry,
            }}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ════════════════════════════════════════════
    # R58：并购整合评估（consolidation 模块接入）
    # ════════════════════════════════════════════
    def _run_consolidation(self, data: dict) -> dict:
        """并购整合评估——行业集中度/整合阶段/整合者画像。

        从 chart_data 提取 CR3/CR5、行业市值、龙头信息，调用
        core.compute.consolidation 判断行业整合态势。供 industry_consolidation
        维度写正文。
        """
        try:
            from core.compute.consolidation import consolidation_assessment, consolidator_profile
            cd = data.get("chart_data", {})
            val = cd.get("fig_valuation", {})
            industry = str(val.get("industry", data.get("industry", "")) or "")
            # 提取行业集中度（enrich 或 chart_data）
            cr3 = val.get("cr3") or val.get("cr3_pct")
            cr5 = val.get("cr5") or val.get("cr5_pct")
            mcap = val.get("market_cap", val.get("mcap_b"))
            roic = val.get("roic")
            wacc = val.get("wacc")
            net_cash = val.get("net_cash")

            if not industry and cr3 is None:
                return {"status": "skip", "reason": "no consolidation data"}

            result = consolidation_assessment(
                industry=industry,
                cr3=float(cr3) if cr3 else None,
                cr5=float(cr5) if cr5 else None,
                top_company_mcap_b=float(mcap) if mcap else None,
            )
            if roic is not None or wacc is not None:
                profile = consolidator_profile(
                    roic=float(roic) if roic else None,
                    wacc=float(wacc) if wacc else None,
                    mcap_b=float(mcap) if mcap else None,
                    net_cash_b=float(net_cash) if net_cash else None,
                )
                result["consolidator_profile"] = profile
            result["status"] = "ok"
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ════════════════════════════════════════════
    # Margin + Expense Bridge (增强版)
    # ════════════════════════════════════════════
    def _compute_margin_expense_bridge(self, data: dict) -> dict:
        """利润率与费用率分解"""
        cd = data.get("chart_data", {})
        result = {}

        # Margin bridge
        margin_raw = cd.get("fig_profitability", cd.get("margin_history", {}))
        if isinstance(margin_raw, dict) and len(margin_raw) >= 2:
            yrs = []
            for yr, val in margin_raw.items():
                try:
                    y = _parse_year_key(yr)
                    if y is None:
                        continue
                    v = float(val.get("gross_margin", val.get("毛利率", val)) if isinstance(val, dict) else val) if val else 0
                    yrs.append((y, v))
                except Exception:
                    pass  # Layer 5: bare except replaced with Exception
            yrs.sort(key=lambda t: t[0])
            if len(yrs) >= 2:
                result["margin_bridge"] = {"status": "ok", "method": "direct_extract", "result": {
                    "current_gross_margin": yrs[-1][1],
                    "trend": dict(yrs),
                    "change": round(yrs[-1][1] - yrs[0][1], 2),
                    "direction": "improving" if yrs[-1][1] > yrs[0][1] else "declining",
                }}

        # Expense bridge
        expense_raw = cd.get("fig_expenses", cd.get("expense_history", {}))
        if isinstance(expense_raw, dict) and len(expense_raw) >= 2:
            yrs_e = []
            for yr, val in expense_raw.items():
                try:
                    y = _parse_year_key(yr)
                    if y is None:
                        continue
                    v = float(val if not isinstance(val, dict) else val.get("expense_ratio", val.get("费用率", 0)))
                    yrs_e.append((y, v))
                except Exception:
                    pass  # Layer 5: bare except replaced with Exception
            yrs_e.sort(key=lambda t: t[0])
            if len(yrs_e) >= 2:
                result["expense_bridge"] = {"status": "ok", "method": "direct_extract", "result": {
                    "current_expense_ratio": yrs_e[-1][1],
                    "trend": dict(yrs_e),
                    "change": round(yrs_e[-1][1] - yrs_e[0][1], 2),
                    "direction": "improving" if yrs_e[-1][1] < yrs_e[0][1] else "deteriorating",
                }}

        return result



