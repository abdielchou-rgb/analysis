"""
Engine Bridge — 把 engine/ 16-step IB-Grade 管线接入生产 compute。

数据流:
    collected_data (akshare/tavily 原始数据)
        → 参数提取 (单位清洗/增长率推导/股本反推)
        → IronGateV2 L1/L2/L3 前置校验 (assumption 层拦截)
        → IBGradeOrchestrator 16 步计算 (Decimal 精度 + provenance)
        → compute_results["engine_ib"] (含 DCF/情景/MC/敏感性/Tornado/期望差)

单位约定 (全部绝对值, 元/股/个):
    revenue / net_profit: 元 (akshare "xxx亿" → _clean_num → 元)
    eps: 元/股
    shares = net_profit / eps: 股数 (年报口径自洽)
    price: 元/股
    → fair_value = (EV - net_debt) / shares: 元/股 ✓
"""

from __future__ import annotations

import logging

logger = logging.getLogger("2hao.engine_bridge")

try:
    from pipeline.compute_engine import _clean_num, _parse_year_key
except ImportError:  # pragma: no cover — 独立运行时兜底

    def _clean_num(v) -> float:  # type: ignore[misc]
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", "").replace(" ", "")
        if not s or s in ("--", "-", "nan", "None"):
            return 0.0
        mult = 1.0
        for unit, m in [
            ("万亿", 1e12),
            ("千亿", 1e11),
            ("百亿", 1e10),
            ("十亿", 1e9),
            ("亿", 1e8),
            ("千万", 1e7),
            ("百万", 1e6),
            ("万", 1e4),
        ]:
            if unit in s:
                mult = m
                s = s.replace(unit, "")
                break
        s = s.replace("%", "").replace("元", "").strip()
        try:
            return float(s) * mult
        except ValueError:
            return 0.0

    def _parse_year_key(yr):  # type: ignore[misc]
        if yr is None or isinstance(yr, int):
            return yr
        if not isinstance(yr, str):
            return None
        s = yr.strip()
        if len(s) >= 4 and s[:4].isdigit():
            suffix = s[4:]
            if suffix == "":
                return int(s[:4])
            if suffix.lower() == "e":
                return int(s[:4])
        return None


def _wacc_from_erp() -> float:
    """与生产 DCF 同源的 WACC（Damodaran ERP），保证跨模块一致。"""
    try:
        from core.compute.financial.damodaran_erp import DamodaranERP

        china = DamodaranERP().for_country("中国")
        total_erp = china.get("total_erp", 0.0729)
        rf, beta, cd_rate, dr, tr = 0.025, 1.0, 0.04, 0.20, 0.25
        coe = rf + beta * total_erp
        return round(coe * (1 - dr) + cd_rate * dr * (1 - tr), 4)
    except Exception:
        return 0.10


def extract_engine_params(financial_data: dict) -> dict | None:
    """从 collected_data 提取 engine 假设参数。数据不足返回 None。

    关键自洽性: shares = 年报净利润 / 年报EPS —— 两者取自 fig_revenue_trend
    同一年份, 避免季度/年报口径打架（P0-5 同源教训）。
    """
    cd = financial_data.get("chart_data", {}) or {}
    if not isinstance(cd, dict):
        return None
    val = cd.get("fig_valuation", {}) or {}
    rev_trend = cd.get("fig_revenue_trend", cd.get("revenue_history", {})) or {}
    if not isinstance(rev_trend, dict) or not isinstance(val, dict):
        return None

    # ── 1. 历史收入序列 (→ 增长率, 单位无关) ─────────────────────────
    hist: list[tuple[int, float]] = []
    for yr, info in rev_trend.items():
        y = _parse_year_key(yr)
        if y is None or y < 2000 or y > 2030:
            continue
        rev = _clean_num(info.get("revenue", info.get("营收", 0)) if isinstance(info, dict) else info)
        if rev > 0:
            hist.append((y, rev))
    hist.sort(key=lambda t: t[0])
    if len(hist) < 2:
        return None

    growth: list[float] = []
    for i in range(1, len(hist)):
        growth.append(hist[i][1] / hist[i - 1][1] - 1)
    growth = growth[-5:]
    while len(growth) < 5:
        growth.append(growth[-1] if growth else 0.08)
    growth = growth[-5:]
    growth = [max(-0.20, min(0.35, g)) for g in growth]  # L2 经济物理边界

    base_revenue = hist[-1][1]  # 元
    latest_year = hist[-1][0]

    # ── 2. 最新年报口径的净利/EPS/毛利率 (同源自洽) ──────────────────
    latest_info = rev_trend.get(str(latest_year), {}) or {}
    if not isinstance(latest_info, dict):
        latest_info = {}
    # 兼容 '2025E' 键
    for yr, info in rev_trend.items():
        if _parse_year_key(yr) == latest_year and isinstance(info, dict):
            latest_info = info
            break

    np_annual = _clean_num(latest_info.get("net_profit", latest_info.get("净利润", 0)))
    eps_annual = _clean_num(latest_info.get("eps", latest_info.get("基本每股收益", 0)))
    gm_annual = _clean_num(latest_info.get("gross_margin", latest_info.get("销售毛利率", 0)))

    # fallback: fig_valuation 的最新年报键 (P0-5)
    if np_annual <= 0:
        la = val.get("latest_annual", {}) or {}
        np_annual = _clean_num(la.get("net_profit", 0)) or _clean_num(val.get("net_profit", 0))

    # ── 3. 股本反推: 年报净利 / 年报EPS ─────────────────────────────
    shares = np_annual / eps_annual if (np_annual > 0 and eps_annual > 0) else 0.0
    if shares <= 0:
        # fallback: market_cap / price (单位歧义风险, 仅在净利/EPS 路径不可用时)
        price_mc = _clean_num(val.get("price", 0))
        mcap = _clean_num(val.get("market_cap", 0))
        if price_mc > 0 and mcap > 0:
            # yfinance 口径 mcap 为亿元 → 股数 = mcap*1e8/price; SDK 口径为元。
            # 启发式: mcap/price > 1e6 视为元口径, 否则亿元口径
            raw = mcap / price_mc
            shares = raw if raw > 1e6 else raw * 1e8
    if shares <= 0:
        return None

    # ── 4. 利润率: EBIT margin ≈ 净利率 / (1 - tax) ──────────────────
    net_margin = np_annual / base_revenue if (np_annual > 0 and base_revenue > 0) else 0.15
    if gm_annual > 0:  # 毛利率做上限约束
        net_margin = min(net_margin, gm_annual)
    tax_rate = 0.15  # 中国高新技术/一般企业综合税率近似
    ebit_margin = net_margin / (1 - tax_rate)
    ebit_margin = max(0.02, min(0.60, ebit_margin))

    # ── 5. 净债务: 资产负债率 + ROE 反推 (粗估, 无现金数据) ──────────
    # 金融业豁免（2026-09-06 golden 抓住）：银行/保险的"负债"是储户存款/
    # 保单准备金，不是债务资本——ALR 框架完全不适用（招行 ALR 91% 会推出
    # 10 万亿"净债务"→负目标价）。金融股 DCF 本身不是主估值法（PB/DDL
    # 才是），engine_ib 让位 net_debt=0 并在 assumptions 标注。
    net_debt = 0.0
    net_debt_note = ""
    roe = _clean_num(latest_info.get("roe", latest_info.get("净资产收益率", 0))) or _clean_num(val.get("roe", 0))
    alr_raw = latest_info.get("asset_liability_ratio", latest_info.get("资产负债率", ""))
    alr = _clean_num(alr_raw) if alr_raw else 0.0
    if alr > 1:  # "62.5" 百分数形态
        alr = alr / 100
    if roe > 1:
        roe = roe / 100
    _is_financial = alr >= 0.85  # 银行/保险典型 ALR 88-95%；制造业罕见 >80%
    if _is_financial:
        net_debt_note = "financial_institution_alr_exempt"
    elif roe > 0.01 and np_annual > 0:
        equity = np_annual / roe
        if 0.05 < alr < 0.95:
            total_debt = equity * alr / (1 - alr)
            net_debt = total_debt * 0.8  # 粗略扣现金, 标注 warning

    # ── 6. 价格 ──────────────────────────────────────────────────────
    price = _clean_num(val.get("price", 0))

    # ── 7. 组装 ──────────────────────────────────────────────────────
    params = {
        "ticker": str(financial_data.get("asset", ""))[:16],
        "company_name": str(financial_data.get("stock_name", financial_data.get("asset", "")))[:32],
        "base_revenue": base_revenue,
        "revenue_growth_rates": growth,
        "base_ebit_margin": round(ebit_margin, 4),
        "wacc": _wacc_from_erp(),
        "terminal_growth_rate": 0.025,
        "shares_outstanding": shares,
        "net_debt": net_debt,
        "current_price": price,
        "tax_rate": tax_rate,
        "da_pct_revenue": 0.03,
        "capex_pct_revenue": 0.04,
        "wc_pct_revenue": 0.02,
        "mc_simulations": 5000,
        "mc_seed": 20260906,  # 固定 seed——golden 回归 + 生产可复现
        "net_debt_note": net_debt_note,
    }
    return params


def run_engine_ib(financial_data: dict) -> dict:
    """Engine IB-Grade 管线生产入口。被 ComputeEngine.compute 调用。"""
    params = extract_engine_params(financial_data)
    if not params:
        return {"status": "skip", "reason": "insufficient data (need >=2y revenue + EPS/price)"}

    # ── 经济物理前置：FCF 基数必须为正 ─────────────────────────────
    # 微利/亏损高增长公司（净利率<2%、capex 重）FCF DCF 无意义——
    # TV 负值、目标价失真。机构口径此类标的走 PS/EV-EBITDA，
    # 由 comparable 路径承担，engine_ib 明确让位（诚实留白优于硬编数字）。
    fcf_base = base_fcf_estimate(params)
    if fcf_base <= 0:
        return {
            "status": "skip",
            "reason": (
                f"FCF 基数非正（margin={params['base_ebit_margin']:.1%}, "
                f"再投资率={params['da_pct_revenue'] + params['capex_pct_revenue'] + params['wc_pct_revenue']:.0%}）"
                "——微利/重投资标的不适用 FCF DCF，建议 PS/EV-EBITDA 可比法"
            ),
        }

    # ── IronGateV2 前置校验 (L1 Hard Stop / L2 经济物理 / L3 文本契约) ──
    try:
        from engine.irongate_v2 import IronGateV2

        gate = IronGateV2()
        gate_report = gate.validate(params)
        if gate_report.blocked:
            return {
                "status": "skip",
                "reason": f"IronGateV2 L1 blocked: {gate_report.block_reasons[:3]}",
            }
        if gate_report.warnings:
            logger.info("[ENGINE-IB] IronGateV2 warnings: %s", gate_report.warnings[:3])
    except Exception as e:
        logger.debug("[ENGINE-IB] IronGateV2 pre-check unavailable: %s", e)

    # ── 16-step 计算 ────────────────────────────────────────────────
    try:
        from engine.orchestrator import IBGradeOrchestrator

        obs = IBGradeOrchestrator()
        pipeline = obs.run(params)
        if not pipeline.success:
            _errs = {k: v.errors[:1] for k, v in pipeline.steps.items() if v.status == "failed"}
            return {"status": "error", "reason": f"pipeline steps failed: {list(_errs.keys())}"}

        steps = {k: v.output for k, v in pipeline.steps.items() if v.output}
        dcf = steps.get("09_dcf", {}) or {}
        mc = steps.get("11_monte_carlo", {}) or {}
        scen = steps.get("10_scenarios", {}) or {}
        tornado = steps.get("13_tornado", {}) or {}

        result = {
            "fair_value": dcf.get("fair_value"),
            "upside_pct": (
                (dcf["fair_value"] / params["current_price"] - 1) * 100
                if dcf.get("fair_value") and params.get("current_price")
                else None
            ),
            "enterprise_value": dcf.get("enterprise_value"),
            "tv_pct": dcf.get("tv_pct"),
            "confidence": dcf.get("confidence"),
            "sensitivity_matrix": dcf.get("sensitivity"),
            "scenario_weighted_target": scen.get("weighted_target"),
            "scenario_risk_reward": scen.get("risk_reward"),
            "mc_median": mc.get("median"),
            "mc_ci95": mc.get("ci_95"),
            "tornado_ranking": [
                {"param": b.get("param"), "swing": b.get("swing")} for b in (tornado.get("bars", []) or [])[:5]
            ],
            "wacc": params["wacc"],
            "assumptions": {
                "growth_rates": [round(g, 4) for g in params["revenue_growth_rates"]],
                "ebit_margin": params["base_ebit_margin"],
                "net_debt_est": params["net_debt"],
                "net_debt_note": params.get("net_debt_note", ""),
            },
            "steps_completed": sorted(pipeline.steps.keys()),
            "duration_ms": round(pipeline.total_duration_ms, 1),
        }

        # ── Reverse-DCF 期望差分析 (市场价 vs 我们的增长假设) ──────────
        try:
            from engine.reverse_dcf import ReverseDCFSolver

            solver = ReverseDCFSolver(
                current_price=params["current_price"],
                shares_outstanding=params["shares_outstanding"],
                net_debt=params["net_debt"],
                fcf_ttm=base_fcf_estimate(params),
                wacc=params["wacc"],
                terminal_growth_rate=params["terminal_growth_rate"],
            )
            rd = solver.solve_implied_growth()
            result["expectations"] = {
                "implied_growth": round(rd.implied_growth_rate, 4),
                "our_growth": params["revenue_growth_rates"][-1],
                "ev_to_fcf": round(rd.ev_to_fcf, 2),
                "converged": rd.converged,
                "warnings": rd.warnings[:2],
            }
        except Exception as e:
            logger.debug("[ENGINE-IB] reverse-dcf skip: %s", e)

        return {"status": "ok", "method": "engine_ib_v3", "result": result}

    except Exception as e:
        logger.warning("[ENGINE-IB] failed: %s", e)
        return {"status": "error", "error": str(e)[:200]}


def base_fcf_estimate(params: dict) -> float:
    """FCF 基数粗估: NOPAT + D&A - CapEx - ΔWC（比率按收入口径）。

    修复（2026-09-06）：原实现 `nopat * (1 - reinvest_ratio)` 把收入口径的
    再投资率错当 NOPAT 占比——微利公司被误判为 FCF 为正。正确算法：
    FCF = Revenue × [margin×(1-tax) + da% - capex% - wc%]。
    """
    rev = params.get("base_revenue", 0)
    margin = params.get("base_ebit_margin", 0)
    tax = params.get("tax_rate", 0.15)
    da = params.get("da_pct_revenue", 0.03)
    capex = params.get("capex_pct_revenue", 0.04)
    wc = params.get("wc_pct_revenue", 0.02)
    return rev * (margin * (1 - tax) + da - capex - wc)
