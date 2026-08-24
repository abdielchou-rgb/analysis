# -*- coding: utf-8 -*-
"""
本地数据底座读取器 — 读取 Marvis 构建的新数据源，转成 chart_data 可消费的格式。

数据源：
  data/capital_flow.db      资金面（北向/两融/公募）
  data/industry_baselines.json  行业基线（申万三级 PE/PB/股息率）
  data/company_events.db    公司事件（财报/分红/增减持/公告）

R9（2026-08-01 数据底座接入）：让资金面/行业基线/公司事件进入 collected_data，
供 data_dict 构建 + section_writer 注入 prompt + IronGate 校验。
FP2 合规：所有数据点带 source（akshare_* / 本地库），不编造。
"""
from __future__ import annotations
import json
import re
import sqlite3
import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("2hao.data_basement")


def _connect(db_name: str) -> sqlite3.Connection | None:
    """连接 data/ 下的 SQLite 库，不存在则返回 None。"""
    path = _ROOT / "data" / db_name
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.debug("[BASEMENT] %s 连接失败: %s", db_name, e)
        return None


# ─────────────────────────────────────────────
# 资金面 capital_flow.db
# ─────────────────────────────────────────────
def load_capital_flow(code: str | None = None, limit: int = 30) -> dict | None:
    """读取资金面数据 → fig_capital_flow 格式。

    返回 {north_net_latest, north_net_5d, margin_balance_latest, ...} 或 None
    code 为 6 位数字；无 code 时返回市场级汇总。
    """
    conn = _connect("capital_flow.db")
    if conn is None:
        return None
    result = {}
    try:
        # 北向资金：市场级日度净流入（无个股维度，取最近值/5日均）
        rows = conn.execute(
            "SELECT date, net_flow FROM northbound_daily "
            "WHERE net_flow IS NOT NULL ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
        if rows:
            flows = [r["net_flow"] for r in rows if r["net_flow"] is not None]
            if flows:
                result["north_net_latest"] = round(flows[0], 2)
                result["north_net_5d"] = round(sum(flows[:5]) / max(len(flows[:5]), 1), 2)
                result["north_net_20d_avg"] = round(sum(flows) / max(len(flows), 1), 2)
                result["north_latest_date"] = str(rows[0]["date"])
                result["_north_source"] = "akshare_hsgt"

        # 两融余额（市场级）
        mrows = conn.execute(
            "SELECT date, margin_balance FROM margin_daily "
            "WHERE margin_balance IS NOT NULL ORDER BY date DESC LIMIT 1").fetchall()
        if mrows:
            result["margin_balance_latest"] = round(mrows[0]["margin_balance"] / 1e8, 2)  # 亿元
            result["margin_latest_date"] = str(mrows[0]["date"])
            result["_margin_source"] = "akshare_sse/szse"

        # 公募持仓：个股维度
        if code:
            frows = conn.execute(
                "SELECT fund_name, stock_name, shares, market_value FROM fund_holding "
                "WHERE stock_code=? AND shares > 0 ORDER BY market_value DESC LIMIT 5",
                (code,)).fetchall()
            if frows:
                result["fund_holdings"] = [
                    {"fund": r["fund_name"] or "—", "shares": r["shares"],
                     "market_value": r["market_value"]} for r in frows
                ]
                result["_fund_source"] = "akshare"
    except Exception as e:
        logger.debug("[BASEMENT] capital_flow 读取失败: %s", e)
    finally:
        conn.close()
    return result if result else None


# ─────────────────────────────────────────────
# 行业基线 industry_baselines.json
# ─────────────────────────────────────────────
def load_industry_baseline(industry_hint: str = "") -> dict | None:
    """读取行业基线 → fig_industry_board 补充。

    industry_hint: 行业关键词（如 "半导体"/"白酒"），用于模糊匹配申万行业名。
    返回 {industry, pe_ttm, pb, dividend_yield, stock_count, source} 或 None。
    """
    path = _ROOT / "data" / "industry_baselines.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sectors = data.get("sectors", [])
        if not sectors:
            return None
        # 精确/模糊匹配行业名
        best = None
        if industry_hint:
            for s in sectors:
                name = str(s.get("sector_name", ""))
                if industry_hint in name:
                    best = s
                    break
            if best is None:
                # 取 PE 最高的相近行业（启发式，避免空）
                cands = [s for s in sectors if s.get("pe_ttm") is not None]
                best = max(cands, key=lambda s: s["pe_ttm"]) if cands else sectors[0]
        else:
            # 无提示：取全市场代表性指标（PE 中位数等）
            pes = [s["pe_ttm"] for s in sectors if s.get("pe_ttm") is not None]
            best = {
                "sector_name": "全市场",
                "pe_ttm_median": sorted(pes)[len(pes)//2] if pes else None,
                "n_sectors": len(sectors),
            }
        if best and "sector_name" not in best:
            best["sector_name"] = "全市场"
        return best
    except Exception as e:
        logger.debug("[BASEMENT] industry_baselines 读取失败: %s", e)
        return None


# ─────────────────────────────────────────────
# 公司事件 company_events.db
# ─────────────────────────────────────────────
def load_company_events(code: str, limit: int = 20) -> dict | None:
    """读取公司事件 → fig_company_events 格式。

    返回 {earnings_latest, dividends_count, share_changes_count, latest_events: [...]}
    """
    conn = _connect("company_events.db")
    if conn is None:
        return None
    result = {}
    try:
        # 最新财报
        erows = conn.execute(
            "SELECT report_date, revenue, net_profit FROM earnings "
            "WHERE ticker=? AND revenue > 0 ORDER BY report_date DESC LIMIT 2",
            (code,)).fetchall()
        if erows:
            latest = erows[0]
            result["latest_report_date"] = str(latest["report_date"])
            result["latest_revenue"] = round(latest["revenue"] / 1e8, 2) if latest["revenue"] else 0
            result["latest_net_profit"] = round(latest["net_profit"] / 1e8, 2) if latest["net_profit"] else 0
            result["_earnings_source"] = "akshare"

        # 分红/增减持计数
        result["dividend_count"] = conn.execute(
            "SELECT COUNT(*) FROM dividends WHERE ticker=?", (code,)).fetchone()[0]
        result["share_change_count"] = conn.execute(
            "SELECT COUNT(*) FROM share_changes WHERE ticker=?", (code,)).fetchone()[0]

        # 最近增减持事件
        sc = conn.execute(
            "SELECT change_date, shareholder, change_type, change_shares FROM share_changes "
            "WHERE ticker=? AND change_shares != 0 ORDER BY change_date DESC LIMIT 5",
            (code,)).fetchall()
        if sc:
            result["recent_share_changes"] = [
                {"date": r["change_date"], "shareholder": r["shareholder"],
                 "type": r["change_type"], "shares": r["change_shares"]} for r in sc
            ]
    except Exception as e:
        logger.debug("[BASEMENT] company_events 读取失败: %s", e)
    finally:
        conn.close()
    return result if result else None


# ─────────────────────────────────────────────
# 统一入口：给 data_dict 用的扁平化 key
# ─────────────────────────────────────────────
def build_basement_data_dict(asset: str = "") -> dict:
    """把新数据源转成 data_dict 扁平 key（供 data_dict.build_data_dict 合并）。

    返回 {capital_north_net_5d: x, industry_pe_ttm: y, ...} 等。
    asset 可含 6 位代码。
    """
    d = {}
    code = ""
    asset_name = ""
    if asset:
        # R26（2026-08-02 全量修复缺陷1）：统一资产解析层
        try:
            from core.asset_resolver import resolve_asset
            _a = resolve_asset(asset)
            code = _a.code
            asset_name = _a.name
        except Exception:
            m = re.search(r"(\d{6})", asset)
            code = m.group(1) if m else ""
            asset_name = asset.split()[0] if asset else ""

    # R48（2026-08-02 标的隔离）：无有效 A 股代码时，禁止拉取 A 股特有字段
    # （资金面/两融/北向/一致预期/治理ESG）。此前非上市公司（如云迹科技）
    # 无 code 时仍调用 load_capital_flow("") 等 → 返回市场级数据冒充个股数据，
    # 造成 data_dict 混入"capital_north_net_latest"等 A 股字段（跨标的串标）。
    _has_a_share_code = bool(code and code.isdigit() and len(code) == 6)

    cf = load_capital_flow(code)
    if cf and _has_a_share_code:
        for k, v in cf.items():
            if isinstance(v, (int, float)) and not k.startswith("_"):
                d[f"capital_{k}"] = v

    ib = load_industry_baseline()
    if ib:
        if ib.get("pe_ttm") is not None:
            d["industry_pe_ttm"] = float(ib["pe_ttm"])
        if ib.get("pb") is not None:
            d["industry_pb"] = float(ib["pb"])
        if ib.get("dividend_yield") is not None:
            d["industry_dividend_yield"] = float(ib["dividend_yield"])

    if _has_a_share_code:
        ce = load_company_events(code)
        if ce:
            for k, v in ce.items():
                if isinstance(v, (int, float)) and not k.startswith("_"):
                    d[f"event_{k}"] = v

    # R10 接入 Round3 新数据源：个股资金面 / 一致预期 / 治理ESG
    # R48：仅 A 股标的拉取（非上市无这些数据，拉取会串标）
    if _has_a_share_code:
        sf = load_stock_fund_flow(code)
        if sf:
            for k, v in sf.items():
                if isinstance(v, (int, float)) and not k.startswith("_"):
                    d[f"flow_{k}"] = v
        cs = load_consensus(code)
        if cs:
            for k, v in cs.items():
                if isinstance(v, (int, float)) and not k.startswith("_"):
                    d[f"consensus_{k}"] = v
        gv = load_governance(code)
        if gv:
            for k, v in gv.items():
                if isinstance(v, (int, float)) and not k.startswith("_"):
                    d[f"gov_{k}"] = v

    # R14 接入 Round4 新数据源：行业供需/政策/产业链/渗透率 + 宏观/全球/美股
    try:
        # R26：用统一解析得到的名字（若未解析到则用原始兜底）
        _asset_name = asset_name or (asset.split()[0] if asset else "")
        # 行业供需（行业名模糊匹配）
        ind = load_industry_driver(_asset_name)
        if ind:
            d["industry_driver_count"] = len(ind)
            for i, pt in enumerate(ind[:5]):
                if isinstance(pt, str):
                    d[f"industry_driver_{i}"] = pt[:100]
        # 政策（行业名匹配，取方向评分）
        pol = load_policy(_asset_name)
        if pol:
            d["policy_count"] = len(pol)
            dirs = [p.get("direction", 0) for p in pol if isinstance(p, dict)]
            d["policy_dir_avg"] = round(sum(dirs) / max(len(dirs), 1), 2) if dirs else 0
        # 产业链（行业匹配）
        chain = load_industry_chain(_asset_name)
        if chain:
            d["chain_upstream_count"] = len(chain.get("upstream", []))
            d["chain_midstream_count"] = len(chain.get("midstream", []))
            d["chain_downstream_count"] = len(chain.get("downstream", []))
        # 渗透率（行业匹配，取首个渗透率）
        pen = load_penetration(_asset_name)
        if pen:
            d["penetration_pct"] = float(pen.get("penetration_pct", 0))
            d["penetration_life_cycle"] = pen.get("life_cycle", "")
        # 全球龙头（ticker 匹配）
        gb = load_global_leaders(code)
        if gb:
            d["global_leader_pe"] = float(gb.get("pe_ttm", 0)) if gb.get("pe_ttm") else 0
            d["global_leader_mcap"] = float(gb.get("market_cap_b", 0)) if gb.get("market_cap_b") else 0
            # R57：海外营收占比（中国公司全球发力命题数据支撑）
            if gb.get("overseas_revenue_pct") is not None:
                d["global_leader_overseas_pct"] = float(gb["overseas_revenue_pct"])
                d["global_leader_name"] = str(gb.get("company", ""))[:30]
        # 美股财务（ticker 匹配）
        us = load_us_stock(code)
        if us:
            d["us_revenue"] = float(us.get("revenue", 0)) if us.get("revenue") else 0
            d["us_pe"] = float(us.get("pe_ttm", 0)) if us.get("pe_ttm") else 0
        # 宏观（取最新值）
        macro = load_macro_latest()
        if macro:
            for k, v in macro.items():
                if isinstance(v, (int, float)):
                    d[f"macro_{k}"] = v
        gmacro = load_global_macro_latest()
        if gmacro:
            for k, v in gmacro.items():
                if isinstance(v, (int, float)):
                    d[f"gmacro_{k}"] = v
        # R18 估值模型知识：从投行 Excel 估值模型提取的参数（WACC/g/风险）
        vk = load_valuation_knowledge(code, _asset_name)
        if vk:
            for k, v in vk.items():
                if isinstance(v, (int, float)):
                    d[f"val_{k}"] = v
    except Exception as _e:
        logger.debug("[BASEMENT] Round4 merge failed: %s", _e)

    # R53（2026-08-03 Marvis 数据扩采）：宏观高频/质押率/领先指标/美国高频
    try:
        # 宏观高频（各指标最新值）
        hf = load_macro_highfreq()
        if hf:
            for k, v in hf.items():
                if isinstance(v, (int, float)):
                    d[k] = v
        # 领先指标库（M1-M2剪刀差/信贷脉冲/专项债/能繁母猪）
        li = load_leading_indicators()
        if li:
            for k, v in li.items():
                if isinstance(v, (int, float)):
                    d[k] = v
        # 美国高频（CFNAI/WEI/盈亏平衡通胀率）
        uhf = load_us_highfreq()
        if uhf:
            for k, v in uhf.items():
                if isinstance(v, (int, float)):
                    d[k] = v
        # 大股东质押率（A股标的，code 匹配）
        if _has_a_share_code:
            pr = load_pledge_ratio(code)
            if pr:
                for k, v in pr.items():
                    if isinstance(v, (int, float)):
                        d[k] = v
    except Exception as _e:
        logger.debug("[BASEMENT] R53 merge failed: %s", _e)

    # R55（2026-08-03 Marvis 全球视野扩采）：全球玩家/渗透率错位/细分市场/非上市威胁
    try:
        _ind_name = asset_name or (asset.split()[0] if asset else "")
        if _ind_name:
            # 全球玩家映射（行业匹配）
            gip = load_global_industry_players(_ind_name)
            if gip:
                for k, v in gip.items():
                    if isinstance(v, (int, float)):
                        d[k] = v
                    elif isinstance(v, str):
                        d[k] = v
            # 区域渗透率错位（行业匹配）
            rp = load_regional_penetration(_ind_name)
            if rp:
                for k, v in rp.items():
                    if isinstance(v, (int, float)) or isinstance(v, str):
                        d[k] = v
            # 细分市场规模全球拆分（行业匹配）
            gms = load_global_market_segments(_ind_name)
            if gms:
                for k, v in gms.items():
                    if isinstance(v, (int, float)):
                        d[k] = v
                    elif isinstance(v, str):
                        d[k] = v
            # 非上市关键玩家（行业匹配）
            ulp = load_unlisted_players(_ind_name)
            if ulp:
                for k, v in ulp.items():
                    if isinstance(v, (int, float)):
                        d[k] = v
                    elif isinstance(v, str):
                        d[k] = v
            # R81（2026-08-06）：品牌-实体映射注入——写作必须"品牌与实体分清"
            # （如 Tokheim 品牌≠托肯恒山实体、GVR 属 Vontier 而非 Dover）。
            # Gate 覆盖完整性检查对照 brand_entity_mapping.json，若正文未落实
            # 映射（实体全称/集团归属错误）即 FAIL；数据注入让写作 prompt 可引用。
            _bem = _load_json("brand_entity_mapping.json")
            if isinstance(_bem, dict) and _bem.get("mappings"):
                _mapped = []
                for _m in _bem["mappings"]:
                    if not isinstance(_m, dict):
                        continue
                    _b = str(_m.get("brand", ""))[:20]
                    _e = str(_m.get("entity", ""))[:40]
                    _g = str(_m.get("parent_group", _m.get("group", "")))[:30]
                    if _b:
                        _mapped.append(f"{_b}->{_e}({_g})")
                if _mapped:
                    d["brand_entity_map"] = "；".join(_mapped[:24])
            # R57：行业龙头海外营收占比（中国公司全球发力）
            _gl_ind = load_global_leaders(industry=_ind_name)
            if _gl_ind:
                if _gl_ind.get("overseas_revenue_pct") is not None:
                    d["ind_leader_overseas_pct"] = float(_gl_ind["overseas_revenue_pct"])
                    d["ind_leader_name"] = str(_gl_ind.get("company", ""))[:30]
            # R57：一致预期目标价可用性（驱动估值降级策略）
            if _has_a_share_code:
                _tp = load_consensus_target_price(code)
                if _tp:
                    if _tp.get("target_price_available"):
                        d["target_price_available"] = True
                        if _tp.get("target_price"):
                            d["consensus_target_price"] = float(_tp["target_price"])
                    else:
                        d["target_price_available"] = False
                        d["target_price_unavailable_reason"] = str(_tp.get("reason", ""))[:60]
    except Exception as _e:
        logger.debug("[BASEMENT] R55 merge failed: %s", _e)
    return d


# ─────────────────────────────────────────────
# Round4 新表：行业供需/政策/产业链/渗透率 + 宏观/全球/美股
# ─────────────────────────────────────────────
def _load_json(name: str):
    path = _ROOT / "data" / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("[BASEMENT] %s 读取失败: %s", name, e)
        return None


def load_industry_driver(industry: str) -> list | None:
    """读取行业供需 industry_drivers.json → 该行业文本条目列表。

    R21（2026-08-02 全量优化）：精确/包含 → 短词兜底（去"行业/产业"后缀），
    再降级到近义关键词表（传感器→仪器仪表/工控/半导体）。
    """
    d = _load_json("industry_drivers.json")
    if not isinstance(d, dict) or not industry:
        return None
    for ind, items in d.items():
        if industry in str(ind) or (str(ind) in industry and len(str(ind)) >= 4):
            return items if isinstance(items, list) else None
    core = (industry.replace("行业", "").replace("产业", "").replace("制造", "")
            .replace("公司", "").strip())
    if len(core) >= 2:
        for ind, items in d.items():
            if core in str(ind) or (str(ind) in core and len(str(ind)) >= 4):
                return items if isinstance(items, list) else None
    # 近义词兜底：传感器行业 → 仪器仪表/工控/消费电子
    SYN = {"传感": ["仪器仪表", "工控", "消费电子"], "机器人": ["机器人", "工控"],
           "半导体": ["半导体", "半导体设备"], "智能穿戴": ["消费电子", "科技"]}
    for kw, alts in SYN.items():
        if kw in core:
            for alt in alts:
                if alt in d and isinstance(d[alt], list):
                    return d[alt]
    return None


def load_policy(industry: str) -> list | None:
    """读取政策库 policy_db.json → 该行业政策列表。"""
    d = _load_json("policy_db.json")
    if not isinstance(d, dict) or not industry:
        return None
    ps = d.get("policies", [])
    matched = [p for p in ps if isinstance(p, dict) and industry in str(p.get("industry", ""))]
    return matched if matched else None


def load_industry_chain(industry: str) -> dict | None:
    """读取产业链 industry_chain.json → 该行业链条。

    R21（2026-08-02 全量优化）：兼容 v6.0 新 schema（industries list，name 字段）
    与旧 schema（chains list，industry 字段）。匹配：精确 → 包含 → 拼音/别名兜底。
    """
    if not industry:
        return None
    d = _load_json("industry_chain.json")
    if not isinstance(d, dict):
        return None
    chains = d.get("industries", d.get("chains", []))
    if not isinstance(chains, list):
        return None
    # 1) 精确匹配（name 或 industry 字段）
    for c in chains:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name", c.get("industry", "")))
        if name == industry or (industry and industry in name):
            return c
    # 2) 反向包含（如 industry="传感器行业"，链条目名="半导体"）
    #    对"XX行业/XX产业/XX制造"后缀做短词匹配
    core = (industry.replace("行业", "").replace("产业", "").replace("制造", "")
            .replace("公司", "").strip())
    if len(core) >= 2:
        for c in chains:
            if not isinstance(c, dict):
                continue
            name = str(c.get("name", c.get("industry", "")))
            # 2026-08-03 修复：`name in core` 方向（通用链名 ⊂ 复合请求）防误匹配。
            # 反例：请求"气体传感器" → core="气体传感器"，链"传感器"（柯力/称重专用）
            # 因 "传感器" in "气体传感器" 误命中，导致气体传感器报告写入柯力/称重内容。
            # 门禁：该方向仅允许链名 ≥4 字（通用 3 字头名词如"传感器"被拒；
            # 合法精确匹配仍由第 1 步捕获）。
            if core in name or (name in core and len(name) >= 4):
                return c
    # 3) 公司名匹配（R33）：调用方常传公司名（如"柯力传感"），
    #    命中链条 key_players 即返回该行业链条
    for c in chains:
        if not isinstance(c, dict):
            continue
        kps = c.get("key_players", [])
        if isinstance(kps, list):
            for kp in kps:
                s = str(kp)
                if s and (s == industry or s in industry or industry in s):
                    return c
    return None


def load_penetration(industry: str) -> dict | None:
    """读取渗透率 industry_penetration.json → 该行业首个渗透率。

    R21（2026-08-02 全量优化）：兼容新 schema（顶层 list，industry 字段）
    与旧 schema（dict.penetration list）。匹配：包含 → 短词兜底。
    """
    if not industry:
        return None
    d = _load_json("industry_penetration.json")
    if isinstance(d, list):
        ps = d
    elif isinstance(d, dict):
        ps = d.get("penetration", [])
    else:
        return None
    if not isinstance(ps, list):
        return None
    # 1) 包含匹配
    for p in ps:
        if isinstance(p, dict) and industry in str(p.get("industry", "")):
            return p
    # 2) 短词兜底（2026-08-03 防误匹配：反向包含方向要求链名 ≥4 字，
    #    避免"传感器"⊂"气体传感器"类通用头名词误命中专用条目）
    core = (industry.replace("行业", "").replace("产业", "").replace("制造", "")
            .replace("公司", "").strip())
    if len(core) >= 2:
        for p in ps:
            if isinstance(p, dict):
                p_ind = str(p.get("industry", ""))
                if core in p_ind or (p_ind in core and len(p_ind) >= 4):
                    return p
    return None


def load_global_leaders(code: str = "", industry: str = "") -> dict | None:
    """读取全球龙头 global_leaders.json → ticker 匹配 或 行业匹配。

    R57（2026-08-03）：Marvis 增补后 global_leaders.json 含 167 家，
    31 家带 overseas_revenue_pct（海外营收占比——中国公司全球发力命题的数据支撑）。
    返回单家龙头（ticker 匹配）或行业龙头摘要（行业匹配）。
    """
    d = _load_json("global_leaders.json")
    ls = d.get("leaders", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
    # ticker 匹配（个股）
    if code:
        for l in ls:
            if isinstance(l, dict) and code == str(l.get("ticker", "")).split(".")[0]:
                return l
    # 行业匹配（行业报告，返回该行业海外营收最高的中国龙头摘要）
    if industry:
        _cn_leaders = []
        for l in ls:
            if not isinstance(l, dict):
                continue
            _ind = str(l.get("industry", ""))
            _cn = str(l.get("country", "")).upper() == "CN"
            if industry in _ind or _ind in industry:
                if _cn and l.get("overseas_revenue_pct"):
                    _cn_leaders.append(l)
        if _cn_leaders:
            _top = max(_cn_leaders, key=lambda x: x.get("overseas_revenue_pct", 0))
            return {"industry": _top.get("industry", ""),
                    "company": _top.get("company", ""),
                    "ticker": _top.get("ticker", ""),
                    "overseas_revenue_pct": _top.get("overseas_revenue_pct"),
                    "overseas_revenue_pct_source": _top.get("overseas_revenue_pct_source", "")}
    return None


def load_consensus_target_price(code: str = "") -> dict | None:
    """读取一致预期目标价 consensus_prices.json → code 匹配。

    R57（2026-08-03）：Marvis 更新后 1,272 条，目标价免费源不可得
    （target_price_available=false 显式标注）。读取该标注，供系统决定降级策略。
    返回 {target_price, target_price_available, reason}。
    """
    d = _load_json("consensus_prices.json")
    if not isinstance(d, dict):
        return None
    # consensus_prices 以 PDF 文件名为 key，需在 value 里找 code/公司
    if code:
        for k, v in d.items():
            if isinstance(v, dict) and code in str(k):
                return {
                    "target_price": v.get("target_price"),
                    "target_price_available": v.get("target_price_available", False),
                    "reason": v.get("target_price_reason", ""),
                    "rating": v.get("rating", ""),
                }
    return None


def load_us_stock(code: str) -> dict | None:
    """读取美股 us_stocks.db → ticker 匹配。"""
    if not code:
        return None
    conn = _connect("us_stocks.db")
    if conn is None:
        return None
    try:
        r = conn.execute(
            "SELECT * FROM us_stocks WHERE ticker=? ORDER BY as_of DESC LIMIT 1", (code,)).fetchone()
        if r:
            return dict(r)
        return None
    except Exception as e:
        logger.debug("[BASEMENT] us_stocks 读取失败: %s", e)
        return None
    finally:
        conn.close()


def load_macro_latest() -> dict | None:
    """读取宏观序列 macro_series.json → 各序列最新值。"""
    d = _load_json("macro_series.json")
    if not isinstance(d, dict):
        return None
    result = {}
    for k, series in d.items():
        if isinstance(series, list) and series:
            last = series[-1]
            if isinstance(last, dict):
                val = last.get("value")
                if val is not None:
                    try:
                        result[k] = float(val)
                    except (TypeError, ValueError):
                        pass
    return result if result else None


def load_global_macro_latest() -> dict | None:
    """读取全球宏观 global_macro.json → 各序列最新值。"""
    d = _load_json("global_macro.json")
    if not isinstance(d, dict):
        return None
    result = {}
    for k, series in d.items():
        if isinstance(series, list) and series:
            last = series[-1]
            if isinstance(last, dict):
                val = last.get("value")
                if val is not None:
                    try:
                        result[k] = float(val)
                    except (TypeError, ValueError):
                        pass
    return result if result else None


# ─────────────────────────────────────────────
# R53（2026-08-03 Marvis 数据扩采）：宏观高频/质押率/领先指标/美国高频
# ─────────────────────────────────────────────
def load_macro_highfreq(limit: int = 5) -> dict | None:
    """读取宏观高频 macro_highfreq.json → 各指标最新值 + 近 N 期变化。

    Marvis R53 交付：19 组指标（螺纹钢/原油/玻璃/沥青/PTA/BDI/运价/30城房价等）。
    返回 {hf_螺纹钢期货主力_收盘价: latest, ...}，并附近 5 期涨跌方向。
    """
    d = _load_json("macro_highfreq.json")
    if not isinstance(d, dict) or not d:
        return None
    result = {}
    for k, item in list(d.items())[:limit]:
        if isinstance(item, dict):
            data = item.get("data", [])
            if isinstance(data, list) and data:
                try:
                    last = data[-1].get("value")
                    if last is not None:
                        result[f"hf_{k}"] = float(last)
                except (TypeError, ValueError):
                    pass
    return result if result else None


def load_pledge_ratio(code: str) -> dict | None:
    """读取大股东质押率 pledge_ratio.json → code 匹配。

    Marvis R53 交付：3,301 只（东财股权质押明细，股东层面质押率上限代理）。
    返回 {pledge_ratio_pct: x}。
    """
    if not code:
        return None
    d = _load_json("pledge_ratio.json")
    if not isinstance(d, list):
        return None
    for item in d:
        if isinstance(item, dict) and str(item.get("code", "")) == str(code):
            pr = item.get("pledgeRatio")
            if pr is not None:
                return {"pledge_ratio_pct": float(pr)}
    return None


def load_leading_indicators() -> dict | None:
    """读取领先指标库 leading_indicators.json → 各指标最新值。

    Marvis R53 交付：M1-M2剪刀差/信贷脉冲/专项债/能繁母猪/土地成交。
    返回 {lead_M1-M2剪刀差: latest, ...}。
    """
    d = _load_json("leading_indicators.json")
    if not isinstance(d, dict) or not d:
        return None
    result = {}
    for k, item in d.items():
        if isinstance(item, dict):
            lv = item.get("latest_value")
            if lv is not None:
                try:
                    result[f"lead_{k}"] = float(lv)
                except (TypeError, ValueError):
                    pass
    return result if result else None


def load_us_highfreq() -> dict | None:
    """读取美国高频 us_highfreq.json → 各序列最新值。

    Marvis R53 交付：CFNAI/WEI/T5YIFR/T10YIE（FRED）。
    返回 {us_hf_CFNAI: latest, ...}。
    """
    d = _load_json("us_highfreq.json")
    if not isinstance(d, dict) or not d:
        return None
    result = {}
    for k, item in d.items():
        if isinstance(item, dict):
            data = item.get("data", [])
            if isinstance(data, list) and data:
                try:
                    last = data[-1].get("value")
                    if last is not None:
                        result[f"us_hf_{k}"] = float(last)
                except (TypeError, ValueError):
                    pass
    return result if result else None


# ─────────────────────────────────────────────
# R55（2026-08-03 Marvis 全球视野扩采）：全球玩家/渗透率错位/细分市场/非上市威胁
# ─────────────────────────────────────────────
def load_global_industry_players(industry: str) -> dict | None:
    """读取细分行业全球玩家映射 global_industry_players.json → 行业名匹配。

    Marvis R55 交付：8 行业 × 平均 6.4 家全球玩家（Honeywell/Sensirion/台积电等）。
    返回 {gip_{industry}_players: n, gip_{industry}_top1: 第一名, ...}。
    """
    if not industry:
        return None
    d = _load_json("global_industry_players.json")
    if not isinstance(d, dict):
        return None
    # 精确匹配行业名（含子串匹配）
    entry = d.get(industry)
    if not entry:
        for k in d:
            if k in industry or industry in k:
                entry = d[k]
                break
    if not entry or not isinstance(entry, dict):
        return None
    players = entry.get("players", [])
    if not players:
        return None
    result = {"gip_player_count": len(players)}
    for i, p in enumerate(players[:5]):
        if isinstance(p, dict):
            result[f"gip_player_{i+1}"] = str(p.get("name", ""))[:40]
            if p.get("market_share_est"):
                result[f"gip_share_{i+1}"] = float(p["market_share_est"])
    return result if result else None


def load_regional_penetration(industry: str) -> dict | None:
    """读取区域渗透率参照 regional_penetration.json → 行业名匹配。

    Marvis R55 交付：中国 vs 海外领先国渗透率错位（时光机判断数据）。
    返回 {rp_china_pen, rp_leading_pen, rp_gap_years, rp_leading_country}。
    """
    if not industry:
        return None
    d = _load_json("regional_penetration.json")
    if not isinstance(d, dict):
        return None
    entry = d.get(industry)
    if not entry:
        for k in d:
            if k in industry or industry in k:
                entry = d[k]
                break
    if not entry or not isinstance(entry, dict):
        return None
    result = {}
    # 渗透率可能是字符串区间（"20-30（估算，2023）"）或数字
    cp = entry.get("china_penetration_pct")
    if cp is not None:
        result["rp_china_pen"] = str(cp)[:30]
    lp = entry.get("leading_penetration_pct")
    if lp is not None:
        result["rp_leading_pen"] = str(lp)[:30]
    gap = entry.get("gap_years_est")
    if gap is not None:
        try:
            result["rp_gap_years"] = float(gap)
        except (TypeError, ValueError):
            result["rp_gap_years"] = str(gap)[:20]
    lc = entry.get("leading_country")
    if lc:
        result["rp_leading_country"] = str(lc)[:30]
    return result if result else None


def load_global_market_segments(industry: str) -> dict | None:
    """读取细分市场规模全球拆分 global_market_segments.json → 行业名匹配。

    Marvis R55 交付：全球TAM/中国TAM/各细分全球+中国规模。
    返回 {gms_global_tam, gms_china_tam, gms_segment_count, gms_seg_1: ...}。
    """
    if not industry:
        return None
    d = _load_json("global_market_segments.json")
    if not isinstance(d, dict):
        return None
    entry = d.get(industry)
    if not entry:
        for k in d:
            if k in industry or industry in k:
                entry = d[k]
                break
    if not entry or not isinstance(entry, dict):
        return None
    result = {}
    gt = entry.get("global_tam_2025")
    if isinstance(gt, dict) and gt.get("value"):
        try:
            result["gms_global_tam"] = float(gt["value"])
        except (TypeError, ValueError):
            pass
        result["gms_global_tam_unit"] = str(gt.get("unit", ""))[:10]
    ct = entry.get("china_tam_2025")
    if isinstance(ct, dict) and ct.get("value"):
        try:
            result["gms_china_tam"] = float(ct["value"])
        except (TypeError, ValueError):
            pass
        result["gms_china_tam_unit"] = str(ct.get("unit", ""))[:10]
    segs = entry.get("segments", {})
    if isinstance(segs, dict) and segs:
        result["gms_segment_count"] = len(segs)
        for i, (seg_name, seg_data) in enumerate(list(segs.items())[:3]):
            if isinstance(seg_data, dict):
                result[f"gms_seg_{i+1}"] = str(seg_name)[:20]
                if seg_data.get("global"):
                    result[f"gms_seg{i+1}_global"] = seg_data["global"]
    return result if result else None


def load_unlisted_players(industry: str) -> dict | None:
    """读取非上市关键玩家 unlisted_players.json → 行业名匹配。

    Marvis R55 交付：非上市玩家威胁度判断（FP2 诚实边界——无数据标定性）。
    返回 {ulp_count, ulp_threat_high, ulp_1: 玩家名+威胁度}。
    """
    if not industry:
        return None
    d = _load_json("unlisted_players.json")
    if not isinstance(d, dict):
        return None
    entry = d.get(industry)
    if not entry:
        for k in d:
            if k in industry or industry in k:
                entry = d[k]
                break
    if not entry or not isinstance(entry, dict):
        return None
    players = entry.get("players", [])
    if not players:
        return None
    result = {"ulp_count": len(players)}
    threat_high = sum(1 for p in players if isinstance(p, dict) and p.get("threat_level") == "high")
    result["ulp_threat_high"] = threat_high
    for i, p in enumerate(players[:3]):
        if isinstance(p, dict):
            name = str(p.get("name", ""))[:30]
            threat = str(p.get("threat_level", ""))[:10]
            result[f"ulp_{i+1}"] = f"{name}({threat})"
    return result if result else None
# ─────────────────────────────────────────────
def load_stock_fund_flow(code: str, limit: int = 30) -> dict | None:
    """读取个股资金面 stock_fund_flow 表 → 扁平指标。

    返回 {north_hold_latest, north_hold_5d_avg, margin_latest, lhb_latest, ...}
    """
    conn = _connect("capital_flow.db")
    if conn is None:
        return None
    result = {}
    try:
        # 北向持仓（最新值 + 5日均）
        nr = conn.execute(
            "SELECT date, value FROM stock_fund_flow WHERE code=? AND metric='north_hold_shares' "
            "AND value IS NOT NULL ORDER BY date DESC LIMIT ?", (code, limit)).fetchall()
        if nr:
            vals = [r["value"] for r in nr]
            result["north_hold_latest"] = round(vals[0], 2)
            result["north_hold_5d_avg"] = round(sum(vals[:5]) / max(len(vals[:5]), 1), 2)
            result["north_hold_date"] = str(nr[0]["date"])
            result["_north_hold_source"] = "akshare: stock_hsgt_individual_em"
        # 两融余额（最新）
        mr = conn.execute(
            "SELECT date, value FROM stock_fund_flow WHERE code=? AND metric='margin_balance' "
            "AND value IS NOT NULL ORDER BY date DESC LIMIT 1", (code,)).fetchone()
        if mr:
            result["margin_balance_latest"] = round(mr["value"] / 1e8, 2)  # 亿元
            result["margin_balance_date"] = str(mr["date"])
            result["_margin_source"] = "akshare: stock_margin_detail"
        # 龙虎榜净买（最新）
        lr = conn.execute(
            "SELECT date, value FROM stock_fund_flow WHERE code=? AND metric='lhb_net_buy' "
            "AND value IS NOT NULL ORDER BY date DESC LIMIT 1", (code,)).fetchone()
        if lr:
            result["lhb_net_buy_latest"] = round(lr["value"], 2)
            result["lhb_date"] = str(lr["date"])
            result["_lhb_source"] = "akshare: stock_lhb_detail_em"
    except Exception as e:
        logger.debug("[BASEMENT] stock_fund_flow 读取失败: %s", e)
    finally:
        conn.close()
    return result if result else None


def load_consensus(code: str) -> dict | None:
    """读取一致预期 consensus 表 → 扁平指标。

    返回 {eps_2026e, eps_2027e, eps_2028e, rating_buy, n_analysts,
           revision_slope, revision_breadth, ...}
    R53（2026-08-03）：Marvis 扩采后表含 revision_slope/revision_breadth
    （预测斜率——"景气预期斜率"框架核心数据）。
    """
    conn = _connect("consensus_estimates.db")
    if conn is None:
        return None
    result = {}
    try:
        r = conn.execute(
            "SELECT * FROM consensus WHERE code=? ORDER BY as_of DESC LIMIT 1", (code,)).fetchone()
        if r:
            for col in ["eps_2026e", "eps_2027e", "eps_2028e", "target_price_avg",
                        "rating_buy", "rating_hold", "rating_sell", "n_analysts",
                        "revision_slope", "revision_breadth"]:
                val = r[col]
                if val is not None:
                    result[col] = float(val) if isinstance(val, (int, float)) else val
            result["_consensus_source"] = "akshare: stock_profit_forecast_ths/stock_research_report_em"
            # R53：revision_slope 有值 → 记录预测斜率可用（景气预期框架）
            if result.get("revision_slope") is not None:
                result["_has_revision_slope"] = True
    except Exception as e:
        logger.debug("[BASEMENT] consensus 读取失败: %s", e)
    finally:
        conn.close()
    return result if result else None


def load_governance(code: str) -> dict | None:
    """读取治理/ESG governance 表 → 扁平指标。

    返回 {shareholder_count_latest, esg_score_latest, pledge_ratio_latest}
    """
    conn = _connect("company_events.db")
    if conn is None:
        return None
    result = {}
    try:
        # 股东户数最新
        sc = conn.execute(
            "SELECT date, value FROM governance WHERE code=? AND metric='shareholder_count' "
            "AND value IS NOT NULL ORDER BY date DESC LIMIT 1", (code,)).fetchone()
        if sc:
            result["shareholder_count_latest"] = round(sc["value"], 0)
            result["shareholder_count_date"] = str(sc["date"])
            result["_gdhs_source"] = "akshare: stock_zh_a_gdhs_detail_em"
        # ESG 最新
        esg = conn.execute(
            "SELECT date, value, extra FROM governance WHERE code=? AND metric='esg_score' "
            "AND value IS NOT NULL ORDER BY date DESC LIMIT 1", (code,)).fetchone()
        if esg:
            result["esg_score_latest"] = round(esg["value"], 2)
            result["esg_grade"] = str(esg["extra"])[:20]
            result["esg_date"] = str(esg["date"])
            result["_esg_source"] = "akshare: stock_esg_hz_sina"
        # 质押比例最新
        pr = conn.execute(
            "SELECT date, value FROM governance WHERE code=? AND metric='pledge_ratio' "
            "AND value IS NOT NULL ORDER BY date DESC LIMIT 1", (code,)).fetchone()
        if pr:
            result["pledge_ratio_latest"] = round(pr["value"], 2)
            result["_pledge_source"] = "akshare: stock_gpzy_pledge_ratio_em"
    except Exception as e:
        logger.debug("[BASEMENT] governance 读取失败: %s", e)
    finally:
        conn.close()
    return result if result else None


# ─────────────────────────────────────────────
# R18 估值模型知识（投行 Excel 估值模型提取）
# ─────────────────────────────────────────────
def load_valuation_knowledge(code: str, asset_name: str = "") -> dict | None:
    """读取估值模型知识 valuation_models_knowledge.json → 按公司/行业匹配。

    返回 {wacc, terminal_growth, ...} 扁平 key。
    """
    path = _ROOT / "data" / "valuation_models_knowledge.json"
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    models = d.get("models", {}) if isinstance(d, dict) else {}
    if not models:
        return None
    # 匹配公司名（资产名包含公司关键词）
    best = None
    if asset_name:
        for comp, m in models.items():
            if comp and asset_name and comp in asset_name or (asset_name in comp):
                best = m
                break
    if best is None and code:
        # 按文件名代码匹配（如 002049）
        for comp, m in models.items():
            fname = m.get("file", "")
            if code in fname:
                best = m
                break
    if best is None:
        # R44（2026-08-02 全量审计修复）：消除"取任意一个"跨资产串标风险。
        # 23 个模型覆盖芯片/地产/消费/医药/家电等（WACC 6%–15%），无匹配时取任意会
        # 注入错误估值参数，导致 DCF 估值偏差 2–3 倍。改为返回 None + warning。
        logger.warning(
            "[BASEMENT] 未匹配到估值模型（asset=%s, code=%s），跳过估值知识注入",
            asset_name, code,
        )
        return None
    if not best:
        return None
    result = {}
    if best.get("wacc"):
        try:
            result["wacc"] = float(best["wacc"])
        except (TypeError, ValueError):
            pass
    if best.get("terminal_growth"):
        try:
            result["terminal_growth"] = float(best["terminal_growth"])
        except (TypeError, ValueError):
            pass
    if best.get("risk_flags"):
        result["risk_flags_count"] = len(best["risk_flags"])
    return result if result else None
