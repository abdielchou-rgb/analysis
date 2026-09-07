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
import re

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

    2026-09-07 兜底（知识保留率审计断点2）：当次采集若 akshare 网络失败只留下
    margin 序列（无 fig_revenue_trend/fig_valuation），engine_ib 会静默 skip →
    引擎算了但报告从未引用顶级方法论。现增加 repo 资产兜底：从
    data/segment_revenue.json（300 标的当年营收）+ data/consensus_prices.json
    （EPS）构造单年锚 + 保守增长率，来源标注 repo_fallback（诚实，非编造）。
    """
    import json as _json
    from pathlib import Path as _Path

    _root = _Path(__file__).resolve().parent.parent
    cd = financial_data.get("chart_data", {}) or {}
    if not isinstance(cd, dict):
        cd = {}
    val = cd.get("fig_valuation", {}) or {}
    rev_trend = cd.get("fig_revenue_trend", cd.get("revenue_history", {})) or {}
    if not isinstance(rev_trend, dict) or not isinstance(val, dict):
        rev_trend, val = {}, {}

    # 资产代码解析（茅台 → 600519）
    asset_raw = str(financial_data.get("asset", financial_data.get("stock_name", "")))
    asset_code = ""
    _m_code = re.search(r"(\d{6})", asset_raw)
    if _m_code:
        asset_code = _m_code.group(1)
    else:
        try:
            from core.asset_resolver import resolve_asset

            asset_code = resolve_asset(asset_raw).code
        except Exception:
            pass

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

    # ── 1b. repo 资产兜底（segment_revenue + consensus）────────────
    _repo_fallback = False
    if len(hist) < 2 and asset_code:
        try:
            _sr_path = _root / "data" / "segment_revenue.json"
            _cp_path = _root / "data" / "consensus_prices.json"
            if _sr_path.exists() and _cp_path.exists():
                _sr = _json.loads(_sr_path.read_text(encoding="utf-8"))
                _cp = _json.loads(_cp_path.read_text(encoding="utf-8"))
                _sentry = _sr.get(asset_code) or {}
                _centry = _cp.get(asset_code) or {}
                _segs = _sentry.get("segments") if isinstance(_sentry, dict) else None
                _period = (_sentry.get("period") or "") if isinstance(_sentry, dict) else ""
                _py = int(_period[:4]) if _period[:4].isdigit() else 0
                _rev_total = 0.0
                if isinstance(_segs, list):
                    for _s in _segs:
                        if isinstance(_s, dict) and _s.get("revenue"):
                            _rev_total += float(_s["revenue"])
                _eps = 0.0
                for _k in ("eps_2026e", "eps_2027e", "eps_2028e"):
                    if isinstance(_centry, dict) and _centry.get(_k):
                        _eps = float(_centry[_k])
                        break
                if _py >= 2015 and _rev_total > 0:
                    # 单年锚：当年 + 上一年按保守 8% 回溯（机构默认），增长率用默认
                    hist = [(_py - 1, _rev_total / 1.08), (_py, _rev_total)]
                    _repo_fallback = True
                    # 供股本反推：consensus EPS 优先；净利润无法从 repo 单年确定时
                    # 用净利率反推（net_margin 由 fig_profitability/数据给定或默认 0.15），
                    # 但茅台等净利率~50% 的高利润标的若拿不到净利会用默认低估——
                    # 故宁可让下游走"诊断性 skip"，也不硬编错误净利率。
                    val.setdefault("repo_eps", _eps)
                    val.setdefault("_repo_fallback", True)
                    logger.info(
                        "[ENGINE-IB][REPO-FALLBACK] %s 用 segment_revenue %d 营收 %.2f亿 + consensus EPS %.2f",
                        asset_code,
                        _py,
                        _rev_total / 1e8,
                        _eps,
                    )
        except Exception as _fe:
            logger.debug("[ENGINE-IB][REPO-FALLBACK] failed: %s", _fe)
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
    # 2026-09-07（断点2 repo 兜底）：营收来自 segment_revenue 时 latest_info 为空，
    # EPS 需从 fig_valuation.net_profit/EPS 或 repo_eps 取。
    if eps_annual <= 0:
        _val_eps = _clean_num(val.get("eps", 0))
        if _val_eps > 0:
            eps_annual = _val_eps
        elif val.get("repo_eps"):
            eps_annual = _clean_num(val["repo_eps"])

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
        # 2026-09-07：price 缺失时传 None（schema current_price: Optional[gt=0]），
        # 而非 0.0——pydantic gt=0 会拒绝 0 → DCF step9 校验失败。DCF fair_value
        # 不需要 price（upside_pct 留 None），price=0 不应阻断估值计算。
        "current_price": price if price and price > 0 else None,
        "tax_rate": tax_rate,
        "da_pct_revenue": 0.03,
        "capex_pct_revenue": 0.04,
        "wc_pct_revenue": 0.02,
        "mc_simulations": 5000,
        "mc_seed": 20260906,  # 固定 seed——golden 回归 + 生产可复现
        "net_debt_note": net_debt_note,
    }
    return params


def _diagnose_missing(financial_data: dict) -> str:
    """诊断 engine_ib 参数缺失的具体输入层（2026-09-07 断点2 可视化）。

    返回人类可读的缺失清单，使数据采集侧的缺口可见可修（而非静默 skip）。
    """
    from pathlib import Path as _P

    _root = _P(__file__).resolve().parent.parent
    cd = (financial_data.get("chart_data") or {}) if isinstance(financial_data, dict) else {}
    if not isinstance(cd, dict):
        cd = {}
    missing = []
    rev_trend = cd.get("fig_revenue_trend", cd.get("revenue_history", {}))
    if not isinstance(rev_trend, dict) or len(rev_trend) < 2:
        # repo 兜底是否可用？
        asset_raw = str(financial_data.get("asset", ""))
        code = ""
        _m = re.search(r"(\d{6})", asset_raw)
        if _m:
            code = _m.group(1)
        sr_ok = (_root / "data" / "segment_revenue.json").exists()
        if sr_ok and code:
            missing.append(f"营收序列(≥2y)缺失；已尝试 repo segment_revenue[{code}] 兜底但仍需净利润")
        else:
            missing.append(
                f"营收序列(≥2y)缺失（chart_data.fig_revenue_trend 仅 {len(rev_trend) if isinstance(rev_trend, dict) else 0} 年）"
            )
    val = cd.get("fig_valuation", {})
    np_ok = False
    if isinstance(val, dict):
        np_ok = bool(val.get("net_profit") or val.get("price") or val.get("market_cap"))
    if not np_ok:
        missing.append("fig_valuation 缺 net_profit/price/market_cap（无法反推股本/价格）")
    if not missing:
        missing.append("参数提取失败但未定位到明确缺失键（数据形态异常）")
    return "engine_ib 参数不足: " + "; ".join(missing)


def run_engine_ib(financial_data: dict) -> dict:
    """Engine IB-Grade 管线生产入口。被 ComputeEngine.compute 调用。"""
    params = extract_engine_params(financial_data)
    if not params:
        # 2026-09-07（断点2 诊断化）：静默 skip → 明确报缺哪些输入，供数据采集侧对症。
        return {"status": "skip", "reason": _diagnose_missing(financial_data)}

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
            "sensitivity_wacc_range": dcf.get("sensitivity_wacc_range"),
            "sensitivity_g_range": dcf.get("sensitivity_g_range"),
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
