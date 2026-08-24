# Data Stager V2 — 多后端 + 缓存 + 断路器 + 新维度
from __future__ import annotations
import logging, time, json
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.data_stager")

from core.data_backends import (
    query_financial, query_price_history, query_macro,
    get_industry_avg, circuit_status, cache_get, cache_set,
    _BACKENDS as bk
)


@dataclass
class StageContext:
    macro: dict = field(default_factory=dict)
    valuation: dict = field(default_factory=dict)
    roic: dict = field(default_factory=dict)
    moat: dict = field(default_factory=dict)
    implied: dict = field(default_factory=dict)
    sentiment: dict = field(default_factory=dict)
    industry_chain: dict = field(default_factory=dict)  # 新增
    dividend: dict = field(default_factory=dict)         # 新增
    sector: dict = field(default_factory=dict)           # 新增
    backends_used: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    timestamp: str = ""


def safe_stage(name, fn, ctx):
    try:
        t0 = time.time()
        result = fn()
        if result:
            getattr(ctx, name).update(result)
        logger.info("  Stager %s: %.0fms %s", name, (time.time()-t0)*1000,
                    "OK" if result else "empty")
    except Exception as e:
        ctx.errors.append(f"{name}: {e}")
        logger.debug("Stager %s: %s", name, e)


# ── 1. 宏观定位 ──────────────────────────────────

def stage_macro() -> dict:
    cache_key = "macro_ctx"
    cached = cache_get(cache_key)
    if cached:
        cached["_from_cache"] = True
        return cached
    raw = query_macro()
    result = {}
    if raw.get("pmi"):
        pmi = raw["pmi"]
        result["pmi_avg"] = pmi
        if pmi > 51: result["earnings_cycle"] = "expansion"
        elif pmi > 49: result["earnings_cycle"] = "trough"
        else: result["earnings_cycle"] = "contraction"
        result["earnings_detail"] = f"PMI={pmi}"
    else:
        result["earnings_cycle"] = "neutral"
        result["earnings_detail"] = "PMI数据暂缺"
    if raw.get("interest_rate"):
        r = raw["interest_rate"]
        result["interest_rate"] = r
        result["liquidity_cycle"] = "loose" if r < 2.5 else ("tight" if r > 3.5 else "neutral")
    if raw.get("cpi"):
        cpi = raw["cpi"]
        result["cpi"] = cpi
        result["policy_orientation"] = "tightening" if cpi > 3 else ("stimulus" if cpi < 1 else "neutral")
    if result:
        cache_set(cache_key, result, ttl=6)
    return result


# ── 2. 估值分位 ──────────────────────────────────

def stage_valuation(asset_code=""):
    if not asset_code: return {}
    cache_key = f"val_{asset_code[:6]}"
    cached = cache_get(cache_key)
    if cached: return cached
    raw = query_price_history(asset_code)
    result = {}
    if raw.get("prices") and len(raw["prices"]) > 10:
        p = raw["prices"]
        import numpy as np
        arr = np.array(p)
        current = float(arr[-1])
        p50 = float(np.percentile(arr, 50))
        p20 = float(np.percentile(arr, 20))
        p80 = float(np.percentile(arr, 80))
        result["current_price"] = current
        result["pct_50"] = round(p50, 2)
        result["price_vs_5y_median"] = round((current / p50 - 1) * 100, 1) if p50 > 0 else 0
        if p80 != p20:
            result["price_percentile"] = round((current - p20) / (p80 - p20) * 100, 1)
        else:
            result["price_percentile"] = 50
        result["valuation_signal"] = "cheap" if result["price_percentile"] < 30 else (
            "expensive" if result["price_percentile"] > 70 else "fair")
        cache_set(cache_key, result)
    return result


# ── 3. ROIC分析 ──────────────────────────────────

def stage_roic(asset_code="", industry=""):
    if not asset_code: return {}
    cache_key = f"roic_{asset_code[:6]}"
    cached = cache_get(cache_key)
    if cached: return cached
    raw = query_financial(asset_code)
    result = {}
    source = raw.get("source", "none")
    result["data_source"] = source
    if source == "yfinance" and raw.get("yf_info"):
        info = raw["yf_info"]
        if info.get("roe"): result["roe_latest"] = round(float(info["roe"]) * 100, 1)
        if info.get("pe"): result["pe"] = round(float(info["pe"]), 1)
        if info.get("pb"): result["pb"] = round(float(info["pb"]), 1)
        if info.get("revenue") and info.get("net_income"):
            result["net_margin_estimate"] = round(float(info["net_income"]) / float(info["revenue"]) * 100, 1)
        if result.get("roe_latest"):
            result["roic_estimate"] = round(result["roe_latest"] * 0.85, 1)
    elif source == "akshare" and raw.get("data"):
        fin = raw["data"]
        # Try to extract ROE
        if isinstance(fin, list) and len(fin) > 0:
            for key in ["净资产收益率", "roe", "ROE"]:
                for row in fin[:3]:
                    if isinstance(row, dict) and key in row:
                        try:
                            result["roe_latest"] = round(float(row[key]), 1)
                            break
                        except Exception: pass
                if result.get("roe_latest"): break
    # Fallback: industry average
    if not result.get("roe_latest") and industry:
        avg_roe = get_industry_avg(industry, "roe")
        if avg_roe:
            result["roe_latest"] = avg_roe
            result["roe_estimated"] = True
    # WACC estimate
    result["wacc_estimate"] = 9.0
    if result.get("roe_latest"):
        result["roic_estimate"] = round(result["roe_latest"] * 0.85, 1)
        result["roic_wacc_spread"] = round(result["roic_estimate"] - 9.0, 1)
    cache_set(cache_key, result, ttl=8)
    return result


# ── 4. 护城河信号 ──────────────────────────────

def stage_moat(industry=""):
    result = {"moat_signals": []}
    if not industry: return result
    mapping = {
        "白酒": ["品牌溢价", "转换成本", "定价权"], "食品饮料": ["品牌溢价", "规模经济"],
        "医药": ["专利保护", "监管牌照", "研发壁垒"], "半导体": ["技术壁垒", "资本壁垒", "客户认证"],
        "互联网": ["网络效应", "数据壁垒", "用户粘性"], "银行": ["监管牌照", "规模经济", "客户关系"],
        "家电": ["品牌溢价", "规模经济", "渠道网络"], "汽车": ["品牌溢价", "规模经济", "供应链"],
        "软件": ["转换成本", "生态锁定", "数据壁垒"], "化工": ["成本优势", "规模经济", "工艺壁垒"],
        "机械": ["技术壁垒", "服务网络", "客户粘性"], "电气设备": ["技术壁垒", "认证壁垒", "客户关系"],
    }
    for key, moats in mapping.items():
        if key in industry:
            result["moat_signals"] = moats
            break
    return result


# ── 5. 隐含增长逆推 ────────────────────────────

def stage_implied(asset_code="", industry=""):
    if not asset_code: return {}
    # Try yfinance first (more reliable PE data)
    raw = query_financial(asset_code)
    result = {}
    pe = None
    if raw.get("source") == "yfinance" and raw.get("yf_info"):
        pe = raw["yf_info"].get("pe")
    if not pe:
        avg_pe = get_industry_avg(industry, "pe") if industry else None
        if avg_pe: pe = avg_pe; result["pe_estimated"] = True
    if pe and float(pe) > 0:
        result["current_pe"] = round(float(pe), 1)
        result["implied_roe"] = round(100.0 / float(pe), 1)
        growth = get_industry_avg(industry, "growth") if industry else 10
        if growth:
            result["industry_growth"] = growth
            result["peg"] = round(float(pe) / growth, 1)
    return result


# ── 6. 资金情绪 ────────────────────────────────

def stage_sentiment():
    return {"northbound_signal": "neutral", "note": "实时情绪数据需akshare"}


# ── 7. 新增: 产业链定位 ────────────────────────

def stage_industry_chain(industry=""):
    """产业链位置：上游/中游/下游"""
    result = {"position": "未知", "dependencies": [], "customers": []}
    if not industry: return result
    mapping = {
        "上游": ["有色", "煤炭", "石油", "钢铁", "化工", "采掘", "矿产", "材料"],
        "中游制造": ["机械", "电气设备", "半导体", "电子", "通信", "军工", "建筑"],
        "下游消费": ["白酒", "食品饮料", "家电", "汽车", "医药", "零售", "服装", "传媒"],
        "下游服务": ["互联网", "软件", "银行", "券商", "保险", "房地产", "休闲服务"],
    }
    for pos, keywords in mapping.items():
        for kw in keywords:
            if kw in industry:
                result["position"] = pos
                result["industry_key"] = kw
                break
        if result["position"] != "未知": break
    # 上下游依赖关系
    deps_map = {
        "白酒": {"上游": ["粮食/包装"], "下游": ["经销商", "终端零售"]},
        "半导体": {"上游": ["硅片/设备"], "下游": ["消费电子/汽车"]},
        "汽车": {"上游": ["钢材/芯片/电池"], "下游": ["经销商/出行平台"]},
        "互联网": {"上游": ["服务器/带宽"], "下游": ["C端用户/广告主"]},
    }
    for key, dep in deps_map.items():
        if key in industry:
            result["dependencies"] = dep.get("上游", [])
            result["customers"] = dep.get("下游", [])
            break
    return result


# ── 8. 新增: 分红与股东回报 ─────────────────────

def stage_dividend(asset_code=""):
    """分红率 + 股息率 + 回购"""
    result = {}
    if not asset_code: return result
    raw = query_financial(asset_code)
    if raw.get("source") == "yfinance" and raw.get("yf_info"):
        dy = raw["yf_info"].get("dividend_yield")
        if dy: result["dividend_yield"] = round(float(dy) * 100, 2)
        de = raw["yf_info"].get("debt_to_equity")
        if de: result["debt_to_equity"] = round(float(de), 1)
        result["capital_return_signal"] = "high_yield" if result.get("dividend_yield", 0) > 3 else (
            "growth_focus" if result.get("dividend_yield", 0) < 1 else "balanced")
    return result


# ── 9. 新增: 行业轮动信号 ─────────────────────

def stage_sector(asset_code="", industry=""):
    """行业相对强度 + 资金流向"""
    result = {}
    if not industry: return result
    # 基于行业的风格标签
    style_map = {
        "成长": ["半导体", "互联网", "软件", "医药", "电子", "通信", "计算机", "传媒"],
        "价值": ["银行", "房地产", "建筑", "钢铁", "有色", "煤炭", "化工"],
        "消费": ["白酒", "食品饮料", "家电", "汽车", "零售", "服装", "医药"],
        "周期": ["有色", "钢铁", "化工", "采掘", "机械", "电气设备"],
        "防御": ["银行", "医药", "食品饮料", "公用事业"],
    }
    for style, industries in style_map.items():
        for ind in industries:
            if ind in industry:
                result.setdefault("style_tags", []).append(style)
    result["style_tags"] = list(set(result.get("style_tags", [])))
    if not result.get("style_tags"):
        result["style_tags"] = ["未分类"]
    return result


# ── 主入口 ──────────────────────────────────────

def run_all_stagers(asset_code="", industry="") -> StageContext:
    ctx = StageContext()
    ctx.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info("Data Stager V2: code=%s industry=%s", asset_code or "none", industry or "none")
    # Track which backends are available
    ctx.backends_used = [k for k, v in bk.items() if v]
    safe_stage("macro", stage_macro, ctx)
    safe_stage("valuation", lambda: stage_valuation(asset_code), ctx)
    safe_stage("roic", lambda: stage_roic(asset_code, industry), ctx)
    safe_stage("moat", lambda: stage_moat(industry), ctx)
    safe_stage("implied", lambda: stage_implied(asset_code, industry), ctx)
    safe_stage("sentiment", stage_sentiment, ctx)
    safe_stage("industry_chain", lambda: stage_industry_chain(industry), ctx)
    safe_stage("dividend", lambda: stage_dividend(asset_code), ctx)
    safe_stage("sector", lambda: stage_sector(asset_code, industry), ctx)
    logger.info("Stager done: 9 engines, %d backends, %d errors",
                len(ctx.backends_used), len(ctx.errors))
    return ctx


def stager_summary(ctx: StageContext) -> str:
    parts = ["[数据加工信号]"]
    if ctx.macro:
        ec = ctx.macro.get("earnings_cycle", "?")
        lc = ctx.macro.get("liquidity_cycle", "?")
        parts.append(f"宏观: 盈利={ec} 流动={lc}")
    if ctx.valuation:
        vs = ctx.valuation.get("valuation_signal", "?")
        pp = ctx.valuation.get("price_percentile", "?")
        parts.append(f"估值: {vs} (分位={pp}%)")
    if ctx.roic:
        rs = ctx.roic.get("roic_estimate", "?")
        ws = ctx.roic.get("wacc_estimate", "?")
        parts.append(f"ROIC: {rs}% WACC={ws}% spread={ctx.roic.get('roic_wacc_spread','?')}%")
        if ctx.roic.get("data_source"):
            parts.append(f"  数据源: {ctx.roic['data_source']}")
    if ctx.implied:
        ir = ctx.implied.get("implied_roe", "?")
        parts.append(f"隐含ROE={ir}% PE={ctx.implied.get('current_pe','?')}")
    if ctx.industry_chain:
        pos = ctx.industry_chain.get("position", "?")
        parts.append(f"产业链: {pos}")
    if ctx.dividend:
        dy = ctx.dividend.get("dividend_yield", "?")
        parts.append(f"股息率: {dy}%")
    if ctx.sector:
        st = "/".join(ctx.sector.get("style_tags", []))
        if st: parts.append(f"风格: {st}")
    if ctx.backends_used:
        parts.append(f"后端: {'+'.join(ctx.backends_used)}")
    parts.append("[/数据加工信号]")
    return "\n".join(parts)