"""prompt_injectors.py — 写作 prompt 注入器注册表。

P3-audit 2026-08-24 Strangler-Fig 重构：section_writer._write_dimension_parallel
中 R16~R81 演化出的 20+ 个同构 try/import/build/serialize 注入块（约 500 行）
迁入本模块。每个注入器 = 纯函数 `(ctx) -> str`，统一由 build_injections()
驱动；任何单个注入器失败只降级自身（返回空串），不影响其他注入。

ctx 契约：
    {
      "asset": str,                # 标的名
      "report_type": str,          # 报告类型
      "data_context": dict,        # 原 self._last_data_context
      "asset_code": str,           # 原 self._asset_code
      "data_dict": dict,           # 原 self._data_dict
    }

新增注入器：写一个 `_inj_xxx(ctx)` 函数并登记进 INJECTORS 即可，
不再需要往巨石方法里找位置贴补丁。
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("2hao.injectors")


# 与 section_writer 同源的小工具（纯函数，避免循环 import）


def _sf_extract(cd: dict, *keys):
    for k in keys:
        v = cd.get(k)
        if v not in (None, "", "--", "nan"):
            return v
    return None


def _growth_rates(cd: dict) -> list:
    out = []
    for k, v in cd.items():
        if "growth" in k.lower() or "增速" in str(k):
            try:
                out.append(float(v))
            except Exception:
                pass
    return out


# ── 注入器 ──────────────────────────────────────────────────
# 命名约定：_inj_<变量名>；返回 str（空串 = 本轮无此注入）。


def _inj_fc_str(ctx):
    """R16：盈利预测模型。"""
    try:
        from core.compute.predict_model import build_forecast, build_forecast_summary

        _fc = build_forecast(ctx["data_context"])
        if _fc:
            return build_forecast_summary(_fc)
    except Exception as _e:
        logger.warning("[PREDICT] 盈利预测模型注入失败: %s", str(_e)[:80])
    return ""


def _inj_ac_str(ctx):
    """R16：反共识信号。"""
    try:
        from core.compute.anti_consensus import build_anti_consensus_prompt, detect_anti_consensus

        _ac = detect_anti_consensus(ctx["asset"], ctx["data_context"])
        if _ac and _ac.get("signals"):
            return build_anti_consensus_prompt(_ac)
    except Exception as _e:
        logger.debug("[ANTI-CONSENSUS] %s", _e)
    return ""


_METHODOLOGY_TOPIC_MAP = {
    "industry_deep": [
        "industry_lifecycle",
        "business_model",
        "profit_pool",
        "competitive_forces",
        "elasticity_analysis",
        "signal_chain",
        "policy_transmission",
        "global_competition",
        "technology_roadmap",
        "capital_market",
    ],
    "listed_company": ["business_model", "industry_lifecycle", "profit_pool", "competitive_forces"],
    "unlisted_company": ["business_model", "reference_class", "unit_economics", "exit_pathways"],
}


def _inj_mr_str(ctx):
    """R17/R71：方法论规则（按报告类型映射主题）。"""
    try:
        from core.methodology_rules import serialize_rules_for_prompt

        return serialize_rules_for_prompt(_METHODOLOGY_TOPIC_MAP.get(ctx["report_type"], ["business_model"]))
    except Exception as _e:
        logger.warning("[RULES] 方法论规则注入失败: %s", str(_e)[:80])
    return ""


def _inj_ts_str(ctx):
    """R19：三表勾稽模型。"""
    try:
        from core.compute.three_statement import build_three_statement, format_three_statement

        _ts = build_three_statement(ctx["data_context"])
        if _ts:
            return format_three_statement(_ts)
    except Exception as _e:
        logger.warning("[THREE-STMT] 三表勾稽模型注入失败: %s", str(_e)[:80])
    return ""


def _inj_hf_str(ctx):
    """R19：哈佛分析框架。"""
    try:
        from core.harvard_analysis import build_harvard_analysis, serialize_harvard_for_prompt

        _hf = build_harvard_analysis(ctx["data_context"])
        if _hf:
            return serialize_harvard_for_prompt(_hf)
    except Exception as _e:
        logger.warning("[HARVARD] 哈佛框架注入失败: %s", str(_e)[:80])
    return ""


def _inj_rdcf_str(ctx):
    """R23：反向DCF/市场隐含预期。"""
    try:
        from core.compute.patterns import build_reverse_dcf_prompt, estimate_implied_growth_full

        _cd = (ctx["data_context"] or {}).get("chart_data", {}) or {}
        _mcap = _sf_extract(_cd, "market_cap", "mcap")
        _fcf = _sf_extract(_cd, "fcf", "free_cash_flow")
        if _mcap and _fcf:
            _rd = estimate_implied_growth_full(
                market_cap=float(_mcap),
                current_fcf=float(_fcf),
                fcf_growth_rates=_growth_rates(_cd),
            )
            if _rd and getattr(_rd, "data", None):
                return build_reverse_dcf_prompt(_rd)
    except Exception as _e:
        logger.warning("[REVERSE-DCF] 反向DCF注入失败: %s", str(_e)[:80])
    return ""


def _inj_cat_str(ctx):
    """R23+R72：催化剂日历 + 4 季度结构强化后缀。"""
    out = ""
    try:
        from core.catalyst_timeline import build_catalyst_timeline, serialize_catalyst

        _ct = build_catalyst_timeline(ctx["data_context"], ctx["report_type"])
        if _ct and _ct.get("status") == "ok":
            out = serialize_catalyst(_ct)
    except Exception as _e:
        logger.debug("[CATALYST] %s", _e)
    if out:
        # R72（2026-08-05 P1）：催化剂日历最低 4 季度结构强化
        out += (
            "\n[催化剂日历结构要求] 必须覆盖未来4个季度（2026Q3/Q4/2027Q1/Q2），"
            "每季度至少1条可验证事件（如中报/年报/政策节点/行业大会等）。"
            "若某季度无可查事件，标注'暂无确定催化剂'而非跳过该季度。"
        )
    return out


def _inj_bb_str(ctx):
    """R23：多空逻辑表（Bull/Bear Matrix）。"""
    try:
        from core.bull_bear_matrix import build_bull_bear_matrix, serialize_bull_bear

        _bb = build_bull_bear_matrix(ctx["data_context"], ctx["report_type"])
        if _bb and _bb.get("status") == "ok":
            return serialize_bull_bear(_bb)
    except Exception as _e:
        logger.warning("[BULLBEAR] 多空表注入失败: %s", str(_e)[:80])
    return ""


def _inj_ur_str(ctx):
    """R23：非上市反向定价 + 里程碑时间轴（仅 unlisted）。"""
    if ctx["report_type"] != "unlisted_company":
        return ""
    try:
        from core.unlisted_reverse_valuation import build_unlisted_reverse_valuation, serialize_unlisted_reverse

        _ur = build_unlisted_reverse_valuation(ctx["data_context"])
        if _ur and _ur.get("status") == "ok":
            return serialize_unlisted_reverse(_ur)
    except Exception as _e:
        logger.debug("[UNLISTED-REV] %s", _e)
    return ""


def _inj_bn_str(ctx):
    """R20/R21：供应链瓶颈分析（Serenity 卡点法）+ 利润池/TOC/BOM 逆向。"""
    try:
        from core.bottleneck_engine import build_bottleneck_analysis, serialize_bottleneck

        _bn = build_bottleneck_analysis(ctx["data_context"], ctx["report_type"])
        if _bn:
            return serialize_bottleneck(_bn)
    except Exception as _e:
        logger.debug("[BOTTLENECK] %s", _e)
    return ""


def _inj_ma_str(ctx):
    """R70：并购估值/行业整合（compute_results.consolidation 序列化）。"""
    try:
        _cr_cons = (ctx["data_context"] or {}).get("compute_results", {}) or {}
        _cons = _cr_cons.get("consolidation", {}) or {}
        if isinstance(_cons, dict) and _cons.get("status") == "ok":
            _stage = _cons.get("consolidation_stage", "")
            _signal = _cons.get("stage_signal", "")
            _ev = _cons.get("ev_ebitda_benchmark", "")
            _top = _cons.get("top_share_signal", "")
            _ce = _cons.get("capital_efficiency_note", "")
            _cp = _cons.get("consolidator_profile", {}) or {}
            _parts = []
            if _stage:
                _parts.append(f"行业整合阶段：{_stage}")
            if _signal:
                _parts.append(f"判断信号：{_signal}")
            if _ev:
                _parts.append(f"并购EV/EBITDA基准：{_ev}x")
            if _top:
                _parts.append(f"龙头定位：{_top}")
            if _ce:
                _parts.append(f"资本配置效率：{_ce}")
            if _cp:
                _cp_role = _cp.get("profile", {}).get("role", "")
                _cp_v = _cp.get("value_creation", "")
                _cp_a = _cp.get("m_and_a_ammo", "")
                if _cp_role:
                    _parts.append(f"整合者画像：{_cp_role}（{_cp_v}、{_cp_a}）")
            if _parts:
                return "\n".join(_parts)
    except Exception as _e:
        logger.warning("[MA-VALUATION] 并购估值/行业整合注入失败: %s", str(_e)[:80])
    return ""


def _inj_ut_str(ctx):
    """R70：非上市威胁度（universe_summary.missing_players 威胁量化）。"""
    try:
        _us_threat = (ctx["data_context"] or {}).get("universe_summary", {}) or {}
        if isinstance(_us_threat, dict):
            _missing = _us_threat.get("missing_players", []) or []
            _industry = _us_threat.get("industry", "")
            _cov = _us_threat.get("coverage_rate", 1.0)
            if _missing:
                _lines = [f"非上市威胁评估（行业：{_industry}，覆盖率 {_cov:.0%}）："]
                for _mp in _missing[:8]:
                    _lines.append(
                        f"  - {_mp.get('name', '?')}：{_mp.get('role', '')}，威胁度 {_mp.get('threat_level', 'unknown')}"
                    )
                return "\n".join(_lines)
    except Exception as _e:
        logger.warning("[UNLISTED-THREAT] 非上市威胁度注入失败: %s", str(_e)[:80])
    return ""


def _inj_di_str(ctx):
    """R71：行业戴维斯双击/双杀注入（仅 industry_deep）。"""
    if ctx["report_type"] != "industry_deep":
        return ""
    try:
        _cr_val = (ctx["data_context"] or {}).get("compute_results", {}) or {}
        _val_comp = _cr_val.get("comparable_valuation", {}) or {}
        _val_dcf = _cr_val.get("dcf_valuation", {}) or {}
        _cd2 = (ctx["data_context"] or {}).get("chart_data", {}) or {}
        _eps_trend = _cd2.get("fig_eps_trend") or _cd2.get("eps_growth")
        _pe = _cd2.get("pe") or _cd2.get("fig_valuation", {}).get("pe_ttm")
        _ind_pe = _cd2.get("industry_pe") or _cd2.get("peer_valuation", {}).get("median_pe")
        if _pe and _ind_pe and _eps_trend:
            _dir_eps = (
                _eps_trend
                if isinstance(_eps_trend, str)
                else ("上行" if isinstance(_eps_trend, (int, float)) and float(_eps_trend) > 0 else "下行")
            )
            _dir_pe = "扩张" if float(_pe) < float(_ind_pe) else ("收缩" if float(_pe) > float(_ind_pe) else "持平")
            _zone = (
                "双击区（EPS↑PE↑——最佳做多窗口，业绩与估值共振向上）"
                if "上行" in str(_dir_eps) and "扩张" in _dir_pe
                else "双杀区（EPS↓PE↓——最差窗口，业绩下滑叠加估值收缩）"
                if "下行" in str(_dir_eps) and "收缩" in _dir_pe
                else "过渡区（EPS与PE方向分歧，需判断谁是主导力）"
            )
            return (
                f"行业戴维斯双击/双杀分析：EPS方向={_dir_eps}，PE方向={_dir_pe}（行业PE={_ind_pe}），"
                f"行业定位={_zone}。判断谁主导：若EPS主导→聚焦盈利周期；若PE主导→聚焦流动性/风险偏好"
            )
    except Exception as _e:
        logger.warning("[DAVIS] 行业戴维斯双击注入失败: %s", str(_e)[:80])
    return ""


def _inj_ex_str(ctx):
    """R71：退出路径分析提示（仅 unlisted）。"""
    if ctx["report_type"] != "unlisted_company":
        return ""
    _lines = [
        "退出路径分析提示（需在估值/退出章节给出）：",
        "  1) IPO：注册制/北交所/港股/美股——各自的估值倍数窗口与审核周期",
        "  2) 并购：行业整合者是谁（见非上市威胁度），潜在并购倍数（EV/EBITDA基准）",
        "  3) 下一轮融资：当前跑道长度/里程碑/down-round风险",
        "  基准率提示（Reference Class）：同阶段同类型公司真实成功概率，勿只用乐观假设",
    ]
    return "\n".join(_lines)


def _inj_esg_str(ctx):
    """R72：ESG实质性议题提示。"""
    _esg_lines = [
        "ESG实质性议题提示（SAC esg_materiality维度，需在报告ESG章节中覆盖）：",
        "  1) 环境(E)：该行业最实质性的环境议题是什么？——碳排（范围1/2/3）、危废处理、水资源",
        "  2) 社会(S)：产品安全责任、供应链人权、社区影响",
        "  3) 治理(G)：董事会独立性、反腐败、数据安全",
        "  对标标准：GRI（全球报告倡议）/ SASB（可持续会计标准委员会）/ TCFD（气候相关财务披露）",
        "  判断要求：ESG对估值的影响——是折价因素还是溢价因素？是否有诉讼/罚款/监管风险？",
    ]
    return "\n".join(_esg_lines)


def _inj_global_str(ctx):
    """R81：全球视角数据注入（全球龙头/海外对标）。"""
    try:
        _dc = ctx["data_context"] or {}
        _cd_gl = _dc.get("chart_data", {}) if isinstance(_dc, dict) else {}
        _gl_lines = []
        _gleaders = _cd_gl.get("fig_global_leaders") or _cd_gl.get("global_leaders")
        if isinstance(_gleaders, dict) and _gleaders:
            _gl_lines.append("### 全球视角：全球龙头对标（数据驱动）")
            for _k, _v in list(_gleaders.items())[:6]:
                _gl_lines.append(f"- {_k}: {str(_v)[:80]}")
        _gip = _cd_gl.get("fig_global_industry_players") or _cd_gl.get("global_industry_players")
        if isinstance(_gip, dict) and _gip:
            _gl_lines.append("### 全球行业玩家")
            for _k, _v in list(_gip.items())[:6]:
                _gl_lines.append(f"- {_k}: {str(_v)[:80]}")
        _overseas = _cd_gl.get("fig_overseas_revenue") or _cd_gl.get("overseas_revenue")
        if _overseas:
            _gl_lines.append(f"### 海外收入: {str(_overseas)[:150]}")
        if _gl_lines:
            _gl_lines.append("要求：报告必须体现全球视野——全球市场/全球龙头对标/海外竞争格局，不能只写中国市场")
            return "\n".join(_gl_lines)
    except Exception as _e:
        logger.warning("[GLOBAL] 全球视角注入失败: %s", str(_e)[:60])
    return ""


def _inj_tri_str(ctx):
    """R80 Phase3：市场规模三角验证注入。"""
    try:
        from core.triangulation import triangulate

        _tri_est = []
        _dc = ctx["data_context"] or {}
        _cd_tri = _dc.get("chart_data", {}) if isinstance(_dc, dict) else {}
        _rev = _cd_tri.get("fig_revenue_trend", {})
        if isinstance(_rev, dict) and len(_rev) >= 2:
            _yrs = sorted([y for y in _rev.keys() if str(y).isdigit()])
            if len(_yrs) >= 2:
                _latest = _rev[_yrs[-1]]
                _prev = _rev[_yrs[-2]]
                if isinstance(_latest, (int, float)) and isinstance(_prev, (int, float)) and _prev > 0:
                    _tri_est.append(
                        {"method": "行业基准", "value": float(_latest), "basis": f"{_yrs[-1]}年规模（行业报告口径）"}
                    )
                    _tri_est.append(
                        {
                            "method": "同比外推",
                            "value": float(_latest) * (1 + (_latest - _prev) / _prev),
                            "basis": f"按{_yrs[-2]}→{_yrs[-1]}增速外推",
                        }
                    )
        if len(_tri_est) >= 2:
            _tr = triangulate(_tri_est)
            return "\n## 市场规模三角验证\n" + _tr.to_text() + "\n"
    except Exception as _e:
        logger.warning("[TRIANGULATION] 注入失败: %s", str(_e)[:60])
    return ""


def _inj_geo_str(ctx):
    """R78：中美竞争/地缘政治分析注入。"""
    try:
        from core.geopolitical_engine import GeopoliticalEngine

        _geo_eng = GeopoliticalEngine()
        _geo_hint = ""
        for _kw in ("半导体", "芯片", "传感器", "光伏", "锂电", "医药", "机器人", "汽车", "通信", "AI", "材料", "军工"):
            if _kw in str(ctx["asset"]):
                _geo_hint = _kw
                break
        _geo_result = _geo_eng.analyze(industry_hint=_geo_hint)
        return _geo_eng.build_injection(_geo_result)
    except Exception as _e:
        logger.warning("[GEO] 中美竞争分析注入失败: %s", str(_e)[:80])
    return ""


def _inj_ss_str(ctx):
    """R76 Phase 5.1：做空者视角注入（Kase Short Framework）。"""
    _ss_lines = [
        "做空者视角审查（Kase Short Framework——检验报告 Bull Case 的反驳防御力）：",
        "  做空5信号：①新市场(未验证的扩张故事) ②新产品(未量产的叙事) ③新会计(收入确认/资本化变化)",
        "            ④新管理层(频繁变动/关联交易) ⑤新资本结构(债务激增/定增倒挂)",
        "  检查要求：Bull Case 的盈利增长中，有多少来自这5个'曾被做空者攻击'的渠道？",
        "  若来自这些渠道→必须给出'为什么这次不是欺诈或泡沫'的具体证据链",
        "  若报告中找不到这5信号的对应驳论→报告的 Bull Case 防御力为零",
    ]
    return "\n".join(_ss_lines)


def _inj_cc_str(ctx):
    """R76 Phase 5.2：监管合规成本（McKinsey Compliance Economics）。"""
    _cc_lines = [
        "监管合规成本分析（McKinsey Compliance Economics——认证/许可的持续成本）：",
        "  1) 安全认证成本：SIL2/SIL3/ATEX/IECEx——年检+复认证费用+人员培训（估算年度成本）",
        "  2) 行业准入认证：IATF16949(汽车)/FDA(医疗)/UL(北美)——初次认证周期与持续合规费用",
        "  3) 环保合规：危废处置/碳排报告/ESG审计——中小企业的隐性退出壁垒",
        "  判断：合规成本占营收比例→新进入者的壁垒高度；合规成本变化趋势→存量企业的费用压力",
    ]
    return "\n".join(_cc_lines)


def _inj_sf_str(ctx):
    """R76 Phase 5.4：系统失效状态（Bridgewater Sustained Failure Mode）。"""
    _sf_lines = [
        "系统失效状态提示（Bridgewater Sustained Failure Mode——不是单次证伪条件，是系统性状态）：",
        "  当前宏观环境：M1-M2剪刀差/信贷脉冲/人民币汇率/全球PMI",
        "  若这些宏观变量持续恶化→'流动性驱动→基本面驱动切换期'可能是本报告的 Sustained Failure Mode",
        "  报告必须标注：在什么系统性状态下，整个判断框架会失效（非单次事件，而是系统性状态切换）",
    ]
    return "\n".join(_sf_lines)


def _inj_cf_str(ctx):
    """R76 Phase 5.5：资金面四层剥离（Morgan Stanley Flow Monitor）。"""
    _cf_lines = [
        "资金面四层剥离（Morgan Stanley Flow Monitor——北向/公募持仓的结构性解读）：",
        "  Layer1 Hedging层：对冲资金→短期套利/事件驱动→噪音，需剥离",
        "  Layer2 Rotation层：行业轮动→资金从A行业流到B行业→判断行业Beta",
        "  Layer3 Bottom-up层：个股Alpha→机构对该公司独立判断→核心信号",
        "  Layer4 Top-down层：宏观Beta→基于GDP/汇率/流动性判断的整体仓位→宏观驱动",
        "  要求：报告中涉及北向/公募/主力资金变化时，必须区分这4层——只有剥离后Bottom-up Alpha才是真信号",
    ]
    return "\n".join(_cf_lines)


def _inj_us_str(ctx):
    """R70：UniverseBuilding 摘要注入（品牌映射/集团归属）。"""
    try:
        _us_sum = (ctx["data_context"] or {}).get("universe_summary", {}) or {}
        if isinstance(_us_sum, dict):
            _bi = _us_sum.get("brand_issues", []) or []
            _gn = _us_sum.get("group_notes", []) or []
            _note = _us_sum.get("note", "")
            _lines = []
            if _bi:
                _lines.append("品牌映射问题（需在写作中避免口径混淆）：")
                for _b in _bi[:5]:
                    _lines.append(f"  - {_b.get('brand', '')}→{_b.get('entity', '')}：{_b.get('issue', '')}")
            if _gn:
                _lines.append("集团归属提示：")
                for _g in _gn[:3]:
                    _lines.append(f"  - {_g.get('note', '')}")
            if _note:
                _lines.append(f"({_note})")
            if _lines:
                return "\n".join(_lines)
    except Exception as _e:
        logger.warning("[UNIVERSE-SUMMARY] UniverseBuilding摘要注入失败: %s", str(_e)[:80])
    return ""


def _inj_vc_str(ctx):
    """R32：估值锚交叉验证（compute_results 多形态兼容提取）。"""
    try:
        from core.valuation_crosscheck import crosscheck, serialize_crosscheck

        _dc = ctx["data_context"] or {}
        _cd = _dc.get("chart_data", {}) or {}
        _cr = _dc.get("compute_results", {}) or {}
        _vals = {}
        _dcf = _cr.get("dcf_valuation", {}) or {}
        _comp = _cr.get("comparable_valuation", {}) or {}
        _scen = _cr.get("scenario_analysis", {}) or {}
        _dcf_val = _dcf.get("target_price")
        if not _dcf_val and isinstance(_dcf.get("result"), dict):
            _dcf_val = _dcf["result"].get("fair_value")
        if not _dcf_val and isinstance(_scen.get("result"), dict):
            _dcf_val = _scen["result"].get("base_price")
        if _dcf_val:
            _vals["DCF"] = float(_dcf_val)
        _comp_val = _comp.get("target_price")
        if not _comp_val and isinstance(_comp.get("result"), dict):
            _comp_val = _comp["result"].get("implied_pe_price")
        if _comp_val:
            _vals["可比"] = float(_comp_val)
        if not _vals and ctx["asset_code"]:
            _fv = _cd.get("fig_valuation", {}) if isinstance(_cd, dict) else {}
            if isinstance(_fv, dict):
                _px = _fv.get("price") or _fv.get("current_price")
                _eps = _fv.get("eps")
                if _px and _eps and float(_eps) > 0:
                    _vals["当前PE"] = round(float(_px) / float(_eps), 1)
        if len(_vals) >= 1:
            _vc = crosscheck(_vals)
            if _vc:
                return serialize_crosscheck(_vc)
    except Exception as _e:
        logger.debug("[VAL-CROSS] %s", _e)
    return ""


def _inj_audit_str(ctx):
    """三表勾稽审计核查。"""
    try:
        from core.three_statement_audit import audit, audit_to_prompt

        _code = ctx["asset_code"]
        if _code:
            _audit = audit(_code, ctx["asset"])
            if _audit:
                return audit_to_prompt(_audit)
    except Exception as _e:
        logger.warning("[AUDIT] 三表审计核查注入失败: %s", str(_e)[:80])
    return ""


def _inj_surp_str(ctx):
    """预期差信号。"""
    try:
        from core.earnings_surprise import compute_surprise, serialize_surprise

        _code2 = ctx["asset_code"]
        if _code2:
            _s = compute_surprise(_code2)
            if _s and _s.get("status") == "ok":
                return serialize_surprise(_s)
    except Exception as _e:
        logger.debug("[SURPRISE] %s", _e)
    return ""


def _inj_pm_str(ctx):
    """对标矩阵（行业从 biz_model.industry_tags / data_dict 提取，禁止硬编码）。"""
    try:
        from core.peer_matrix import build_peer_matrix, serialize_matrix

        _code3 = ctx["asset_code"]
        if _code3:
            _ind = ""
            _ctx = ctx["data_context"] or {}
            _biz = _ctx.get("biz_model") if isinstance(_ctx, dict) else None
            if isinstance(_biz, dict):
                _tags = _biz.get("industry_tags") or []
                if _tags:
                    _ind = str(_tags[0])
            if not _ind:
                _dd_k = ctx["data_dict"] or {}
                for _kw in ("industry", "行业"):
                    if _kw in _dd_k:
                        _ind = str(_dd_k[_kw])
                        break
            _m = build_peer_matrix(_code3, ctx["asset"], _ind)
            if _m and _m.get("status") == "ok":
                return serialize_matrix(_m)
    except Exception as _e:
        logger.debug("[PEER-MATRIX] %s", _e)
    return ""


def _inj_tt_str(ctx):
    """R30：目标价追踪（分析师历史准确率档案）。"""
    try:
        from core.target_tracker import compute_tracker, format_tracker

        _tt = compute_tracker()
        if _tt:
            return format_tracker(_tt)
    except Exception as _e:
        logger.warning("[TRACKER] 目标价追踪注入失败: %s", str(_e)[:80])
    return ""


def _inj_bm_str(ctx):
    """R30：基准对标（个股 vs 指数/行业基准）。"""
    try:
        from core.benchmark_compare import compare_vs_benchmark, serialize_benchmark

        _bm = compare_vs_benchmark()
        if _bm:
            return serialize_benchmark(_bm)
    except Exception as _e:
        logger.warning("[BENCHMARK] 基准对标注入失败: %s", str(_e)[:80])
    return ""


def _inj_tm_str(ctx):
    """R70：dim-parallel 工具模块摘要（elasticity/signal_chain/moat/life_cycle/multi_model）。"""
    try:
        _cr_tm = (ctx["data_context"] or {}).get("compute_results", {}) or {}
        _tm = _cr_tm.get("tool_modules", {}).get("modules", {}) if isinstance(_cr_tm, dict) else {}
        if isinstance(_tm, dict):
            _tm_parts = []
            for t_key, t_label in [
                ("elasticity", "弹性分析"),
                ("signal_chain", "信号链"),
                ("life_cycle", "生命周期"),
                ("moat", "护城河"),
                ("multi_model", "多模型"),
            ]:
                td = _tm.get(t_key, {})
                if isinstance(td, dict) and td.get("status") != "skip":
                    _data = {k: v for k, v in td.items() if k != "status"}
                    if _data:
                        try:
                            _tm_parts.append(f"[{t_label}] {json.dumps(_data, ensure_ascii=False)[:300]}")
                        except Exception:
                            _tm_parts.append(f"[{t_label}] {str(_data)[:300]}")
            if _tm_parts:
                return "\n".join(_tm_parts)
    except Exception as _e:
        logger.warning("[TOOL-MODULES] 工具模块注入失败: %s", str(_e)[:80])
    return ""


# ── 注册表 ──────────────────────────────────────────────────
# (变量名, 注入器)。section_writer 侧按变量名取回，下游 prompt 组装零改动。

# P3-B：追加注入器（方法论置信度 / [E#] 证据清单 / 研究问题树）从子模块挂载
from pipeline.prompt_injectors_p3b import (  # noqa: E402
    _inj_analogy_str,
    _inj_consulting_str,
    _inj_esg_data_str,
    _inj_ev_str,
    _inj_kb_str,
    _inj_ma_cases_str,
    _inj_macro_str,
    _inj_market_seg_str,
    _inj_mc_str,
    _inj_mkb_str,
    _inj_policy_str,
    _inj_rp_str,
    _inj_segment_rev_str,
    _inj_valuation_kb_str,
)

INJECTORS = [
    ("fc_str", _inj_fc_str),
    ("ac_str", _inj_ac_str),
    ("mr_str", _inj_mr_str),
    ("ts_str", _inj_ts_str),
    ("hf_str", _inj_hf_str),
    ("rdcf_str", _inj_rdcf_str),
    ("cat_str", _inj_cat_str),
    ("bb_str", _inj_bb_str),
    ("ur_str", _inj_ur_str),
    ("bn_str", _inj_bn_str),
    ("ma_str", _inj_ma_str),
    ("ut_str", _inj_ut_str),
    ("di_str", _inj_di_str),
    ("ex_str", _inj_ex_str),
    ("esg_str", _inj_esg_str),
    ("global_str", _inj_global_str),
    ("tri_str", _inj_tri_str),
    ("geo_str", _inj_geo_str),
    ("ss_str", _inj_ss_str),
    ("cc_str", _inj_cc_str),
    ("sf_str", _inj_sf_str),
    ("cf_str", _inj_cf_str),
    ("us_str", _inj_us_str),
    ("vc_str", _inj_vc_str),
    ("audit_str", _inj_audit_str),
    ("surp_str", _inj_surp_str),
    ("pm_str", _inj_pm_str),
    ("tt_str", _inj_tt_str),
    ("bm_str", _inj_bm_str),
    ("_tm_str", _inj_tm_str),
    ("mc_str", _inj_mc_str),
    ("ev_str", _inj_ev_str),
    ("rp_str", _inj_rp_str),
    ("kb_str", _inj_kb_str),
    ("mkb_str", _inj_mkb_str),
    ("macro_str", _inj_macro_str),
    ("valuation_kb_str", _inj_valuation_kb_str),
    ("policy_str", _inj_policy_str),
    ("esg_data_str", _inj_esg_data_str),
    ("ma_cases_str", _inj_ma_cases_str),
    ("segment_rev_str", _inj_segment_rev_str),
    ("consulting_str", _inj_consulting_str),
    ("market_seg_str", _inj_market_seg_str),
    ("analogy_str", _inj_analogy_str),
]


# P3-B：骨架模式跳过集（重计算/长文本注入器）
SKELETON_SKIP = {
    "geo_str",
    "tri_str",
    "di_str",
    "mc_str",
    "ev_str",
    "bn_str",
    "ma_str",
    "pm_str",
    "tt_str",
    "bm_str",
}


def build_injections(
    asset: str,
    report_type: str,
    data_context: dict,
    asset_code: str = "",
    data_dict: dict = None,
    skeleton: bool = False,
    injector_skip: set | None = None,
) -> dict:
    """运行全部注入器，返回 {变量名: 内容}。

    skeleton=True 时跳过重注入（对应 settings.skeleton_mode 冒烟档）。
    injector_skip：M2 路由器给出的行业级禁用集合。
    单个注入器异常已在内部降级为空串；本层再兜一层保证永不中断写作。
    """
    _skip = injector_skip or set()
    ctx = {
        "asset": asset,
        "report_type": report_type,
        "data_context": data_context or {},
        "asset_code": asset_code or "",
        "data_dict": data_dict or {},
    }
    out = {}
    for name, fn in INJECTORS:
        if skeleton and name in SKELETON_SKIP:
            out[name] = ""
            continue
        if name in _skip:
            out[name] = ""
            continue
        try:
            out[name] = fn(ctx) or ""
        except Exception as e:  # 注入器自身漏接的最后防线
            logger.warning("[INJECTOR] %s 失败: %s", name, str(e)[:60])
            out[name] = ""
    return out
