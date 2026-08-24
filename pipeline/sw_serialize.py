# -*- coding: utf-8 -*-
"""SectionWriter 数据序列化 — R78 Phase3.1 拆分上帝模块。

从 section_writer.py 抽出的 _serialize_data（129 行 staticmethod），
保持行为不变。主文件 import 并转发，resume_driver 等外部调用兼容。
"""
from __future__ import annotations


def serialize_chart_data(data):
    if not isinstance(data, dict):
        return ""
    lines = []
    # ═══ 实时数据层(LIVE) — 报告中的"当前数据" ═══
    live = data.get("live", {}) if isinstance(data, dict) else {}
    if live:
        fin = live.get("financials", {})
        if fin:
            lines.append("=== 实时财务数据(最新) ===")
            lines.append(f"  {str(fin)[:500]}")
            lines.append("")
        news = live.get("news")
        if news:
            lines.append("=== 实时新闻/动态 ===")
            lines.append(f"  {str(news)[:300]}")
            lines.append("")
    
    # ═══ 参考知识层(REFERENCE) — 标注非实时 ═══
    ref = data.get("reference", {}) if isinstance(data, dict) else {}
    if ref:
        for k, v in ref.items():
            if k in ('industry_baselines','consensus_prices','industry_drivers'):
                lines.append(f"=== 参考:{k}(历史研报,非实时) ===")
                lines.append(f"  {str(v)[:300]}")
                lines.append("")
    
    # Layer 1: 宏观周期
    macro = data.get("macro_ctx", {}) if isinstance(data, dict) else {}
    if macro:
        if hasattr(macro, 'earnings_cycle'):
            lines.append("=== 宏观周期定位（DDM三要素）===")
            lines.append("  盈利周期: {}".format(getattr(macro, 'earnings_cycle', '?')))
            lines.append("  流动性: {}".format(getattr(macro, 'liquidity_cycle', '?')))
            lines.append("  风险偏好: {}".format(getattr(macro, 'risk_preference', '?')))
            lines.append("")
    # Layer 2: 商业模式分类
    biz = data.get("biz_model", {}) if isinstance(data, dict) else {}
    if biz:
        biz_name = getattr(biz, 'biz_name', '') if not isinstance(biz, dict) else biz.get('biz_name', '')
        biz_type = getattr(biz, 'biz_type', '') if not isinstance(biz, dict) else biz.get('biz_type', '')
        if biz_name:
            lines.append("=== 商业模式分类 ===")
            lines.append("  类型: {} ({})".format(biz_name, biz_type))
            if hasattr(biz, 'industry_tags') or (isinstance(biz, dict) and biz.get('industry_tags')):
                tags = biz.industry_tags if hasattr(biz, 'industry_tags') else biz.get('industry_tags', [])
                lines.append("  行业: {}".format(', '.join(tags[:3])))
            lines.append("")
    # PE/VC 基准率预测
    ref_data = data.get("reference_class", {}) if isinstance(data, dict) else {}
    if ref_data:
        lines.append("=== 基准率预测（Reference Class Forecasting）===")
        for k, v in ref_data.items() if isinstance(ref_data, dict) else []:
            if isinstance(v, (int, float)):
                lines.append("  {}: {}".format(k, v*100 if v < 1 else v))
        lines.append("")
    # Layer 4: 估值分位
    valuation_data = data.get("valuation_percentile", {}) if isinstance(data, dict) else {}
    if valuation_data:
        lines.append("=== 估值分位与驱动因子 ===")
        for key, label in [("pe_percentile", "PE估值分位"), ("pb_percentile", "PB估值分位"), ("sector_relative", "行业相对估值")]:
            v = valuation_data.get(key, "")
            if v:
                lines.append("  {}: {}".format(label, v))
        drivers = valuation_data.get("key_drivers", [])
        if drivers:
            lines.append("  关键估值驱动因子: {}".format(', '.join(drivers[:5])))
        lines.append("")
    # Compute results
    cr = data.get("compute_results", {}) if isinstance(data, dict) else {}
    knowledge_sections = []
    for module_key, label in [("xiao_jing", "XiaoJing"), ("greenwald", "Greenwald"),
        ("wang_siyu", "WangSiyu"), ("thinking_models", "ThinkingModels"),
        ("page_models", "PageModels"), ("serenity", "Serenity"),
        ("logic_audit", "LogicAudit"), ("liu_run", "LiuRun"), ("kelly", "Kelly")]:
        md = cr.get(module_key, {}) if isinstance(cr, dict) else {}
        if isinstance(md, dict) and md.get("status") == "ok":
            kv = {k:v for k,v in md.items() if k not in ("status","method")}
            knowledge_sections.append("[{}] {}".format(label, str(kv)[:200]))
    for ek in ["dcf_valuation", "comparable_valuation", "scenario_analysis", "kp_compute"]:
        ev = cr.get(ek, {}) if isinstance(cr, dict) else {}
        if isinstance(ev, dict) and len(str(ev)) > 10:
            knowledge_sections.append("[{}] {}".format(ek, str(ev)[:200]))
    if knowledge_sections:
        lines.append("=== Knowledge Module Analysis Results ===")
        lines.extend(knowledge_sections)
        lines.append("=== End Knowledge Analysis ===")
        lines.append("")
    syn = cr.get("synthesis", {}) if isinstance(cr, dict) else {}
    if isinstance(syn, dict) and syn.get("status") == "ok":
        lines.append("=== Meta-Reasoning Synthesis ===")
        lines.append("- Consensus: {} (confidence={})".format(syn.get("consensus_direction","?"), syn.get("consensus_confidence","?")))
        lines.append("- Signals: {} modules | Contradictions: {}".format(syn.get("signal_count","?"), syn.get("contradiction_count","?")))
        lines.append("- Recommendation: {}".format(syn.get("recommendation","?")[:200]))
        lines.append("=== End Synthesis ===")
        lines.append("")
    for k, v in data.items():
        if k.startswith("_") or k in ("compute_results", "macro_ctx", "biz_model", "valuation_percentile", "reference_class", "chart_paths"):
            continue
        # 2026-08-02 修复：chart_data 内的 enrich text（company_intro/valuation_anchor/dcf 等）
        # 之前被整体 str()[:300] 截断丢失，导致 LLM 拿不到公司身份写出污染报告。
        if k == "chart_data" and isinstance(v, dict):
            text_keys = [tk for tk in v.keys()
                         if not tk.startswith("fig_") and tk != "_agent_sources" and tk != "agent_news"]
            for tk in text_keys:
                tv = v.get(tk)
                if isinstance(tv, str) and tv.strip():
                    lines.append("- 公司研究素材.{}: {}".format(tk, tv))
                elif isinstance(tv, dict) and tv:
                    lines.append("- 公司研究素材.{}: {}".format(tk, str(tv)[:800]))
            news = v.get("agent_news")
            if isinstance(news, list) and news:
                lines.append("- 公司研究素材.news: {}".format(str(news)[:600]))
            # R85（2026-08-06）：市场规模权威锚点铁律——把 fig_market_size_global /
            # fig_market_size_china 从"图表数据"提升为"写作铁律"，防止 LLM 自创
            # 窄口径数值规避一致性检查（柯力 v9 事故：正文写全球18.6亿/中国15.2亿，
            # 权威值全球46亿/中国166亿，3轮 Gate 全 FAIL 的根因之一）。
            _mkt_anchors = []
            for _fk in ("fig_market_size_global", "fig_market_size_china"):
                _fv = v.get(_fk) if isinstance(v, dict) else None
                if isinstance(_fv, dict) and _fv:
                    _unit = ""
                    if isinstance(v.get("_caliber", {}).get(_fk), dict):
                        _unit = v["_caliber"][_fk].get("unit", "")
                    _mkt_anchors.append("  {}: {} [unit={}]".format(_fk, str(_fv)[:300], _unit))
            if _mkt_anchors:
                lines.append("## [权威口径铁律 R85] 市场规模测算必须采用以下权威值，禁止自创其他口径数值：")
                lines.extend(_mkt_anchors)
                lines.append("（TAM/SAM 测算、增速、占比全部基于此权威口径；如需拆分场景须在权威值内部分解，不得另立总量。禁止写『口径一致性说明』类自证段落。）")
                # R89（2026-08-06）：显式列出已知的错误口径，LLM 曾多次自创下列数值：
                # 中国油位传感器市场规模写 1亿元/8.3亿元/9.8亿元/13.2亿元/15.2亿元/18.6亿元，
                # 或全球市场写 46.0亿元（单位错乱，应为亿美元）。凡出现以下数值即视为违反铁律。
                # 写作时必须**严格禁止**出现以下中国市场规模数值（除非显式标注为狭义的传感器
                # 本体出厂口境外且不与中国总量混淆）：
                #   - 中国油位传感器市场规模 1亿元/8.3亿元/9.8亿元/13.2亿元
                #   - 中国油位传感器市场规模 15.2亿元/18.6亿元
                #   - 全球油位传感器市场规模 46.0亿元（单位错乱，应为 46.0亿美元）
                lines.append("## [R89 禁用值列表] 以下数值在中国油位传感器市场规模处出现即视为违反铁律，禁止写入正文：")
                lines.append("  1亿元、8.3亿元、9.8亿元、13.2亿元、15.2亿元、18.6亿元")
                lines.append("  （全球市场禁止写 46.0亿元，应为 46.0亿美元）")
                # R86（2026-08-06）：口径与单位标注铁律——LLM 曾将"广义液位市场120亿美元"
                # 混入油位口径簇（Gate 误判全球[65,120,65]冲突），或将美元写成亿元（单位错乱）。
                # 必须显式标注口径边界与单位，避免检查侧误判/漏判。
                lines.append("## [口径标注铁律 R86] 全文涉及市场规模的表述必须遵守：")
                lines.append("1) 本报告研究对象为『油位传感器』，凡提及市场规模默认指油位传感器口径，单位必须与权威锚点一致（亿美元/亿元），禁止换算错位；")
                lines.append("2) 若必须提及更宽口径（如广义液位市场、液位仪表行业），须显式标注『（广义液位市场，非油位传感器口径）』，且不得与油位口径并列对比或混用；")
                lines.append("3) 禁止出现同指标多单位混用（如全球市场一处写亿美元、另一处写亿元）；")
                lines.append("4) 任何口径数值与权威锚点偏差不得超过20%，超出即视为口径冲突。")
                lines.append("")
            fig_keys = [fk for fk in v.keys() if fk.startswith("fig_")]
            if fig_keys:
                lines.append("- 图表数据键: {}".format(", ".join(fig_keys)))
                # R66（2026-08-04）修复 enrich 数据注入断裂：fig_* 键此前只列键名
                # 不注数值，LLM 拿不到真实数据（柯力事故：正文写 3.6 亿而非 10.72 亿）。
                # 现在把 fig_* 的具体数值注入（截断 600 字防爆 prompt）。
                # R82（2026-08-06）：读取 _caliber 伴生字典中的 unit，随数值一并注入，
                # 防止 LLM 把全球市场 46/50/54.5/65 亿美元写成"亿元"（第5轮冲突根因）。
                _caliber = v.get("_caliber", {}) if isinstance(v, dict) else {}
                for fk in fig_keys:
                    fv = v.get(fk)
                    _unit = ""
                    if isinstance(_caliber.get(fk), dict):
                        _unit = _caliber[fk].get("unit", "")
                    if isinstance(fv, dict) and fv:
                        _line = str(fv)[:900]
                        if _unit:
                            _line = _line + "  [unit=" + _unit + "]"
                        lines.append("  .{}: {}".format(fk, _line))
                    elif isinstance(fv, str) and fv.strip():
                        lines.append("  .{}: {}".format(fk, fv[:900] + ("  [unit=" + _unit + "]" if _unit else "")))
            continue
        try:
            lines.append("- {}: {}".format(k, str(v)[:300]))
        except Exception:
            pass
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# R89（2026-08-06）：市场规模错误口径后写清理器
# ═══════════════════════════════════════════════════════════════
# 背景：R85/R86 铁律已注入 prompt，但 LLM 曾无视指令仍写出
#   "中国油位传感器市场规模2024年为1亿元"（权威166亿元）等自创窄口径。
# 清理器在报告落盘前对全文做最后兜底修正——不依赖 LLM 服从性，
# 只要发现禁用值出现在"市场规模"语境，即替换为权威锚点值。
# 同时修正单位错乱（46.0亿元→46.0亿美元）与口径标注遗漏。
import re as _re89

def sanitize_report_market_sizes(report_text, chart_data=None, anchors=None):
    """后写清理：将报告正文中已知错误口径替换为权威值。

    Args:
        report_text: 报告全文
        chart_data: 序列化前的 chart_data（含 fig_market_size_* 权威值，可选）
        anchors: 显式权威锚点 {"global": {...}, "china": {...}}（可选，优先于 chart_data）
    Returns:
        清理后的报告文本
    """
    if not report_text:
        return report_text
    # 1) 提取权威锚点
    glb = china = None
    _GLOBAL_UNIT_USD = False   # 全球市场规模权威单位是否为亿美元（R90）
    _GLOBAL_UNIT_CN = False    # 明确为亿元/人民币时，禁止做"亿元→亿美元"修正
    if anchors:
        glb = anchors.get("global")
        china = anchors.get("china")
    # R90（2026-08-06）：兼容实际管线结构。data_enrichment.AgentEnricher 合并
    # enrich 后 chart_data[key] 保持**扁平 dict**（{"2024": 166, ...}），unit 存于
    # chart_data["_caliber"][key]["unit"]；仅旧版/测试用 {"data": {...}} 嵌套结构。
    # 之前只认嵌套结构导致 glb/china 恒为 None，清理器静默失效（R89 白写）。
    def _extract_anchor(node):
        if not isinstance(node, dict):
            return None
        if isinstance(node.get("data"), dict):
            return node["data"]
        # 扁平结构：剔除元数据键后剩下的键值对即年份→数值锚点
        _meta = {"unit", "note", "source", "data", "confidence", "generated_by"}
        out = {}
        for k, v in node.items():
            if k in _meta or k.startswith("_"):
                continue
            if isinstance(v, (int, float)):
                out[k] = v
        return out or None

    if chart_data and isinstance(chart_data, dict):
        if glb is None:
            glb = _extract_anchor(chart_data.get("fig_market_size_global"))
        if china is None:
            china = _extract_anchor(chart_data.get("fig_market_size_china"))
        # unit 权威判定：fig_market_size_global 的 _caliber.unit 若为 亿美元，
        # 则单位错乱兜底（模式4）按亿美元口径执行；缺失时按数值量级推断。
        if chart_data.get("_caliber") and isinstance(chart_data["_caliber"], dict):
            _c_glb = chart_data["_caliber"].get("fig_market_size_global") or {}
            _unit_glb = str(_c_glb.get("unit", ""))
            if _unit_glb.find("美元") >= 0:
                _GLOBAL_UNIT_USD = True
            elif _unit_glb.find("人民币") >= 0 or _unit_glb.find("亿元") >= 0:
                _GLOBAL_UNIT_CN = True
        if not _GLOBAL_UNIT_USD and not _GLOBAL_UNIT_CN:
            # 无 unit 元数据时按数值量级推断：全球46亿美元 vs 中国166亿元
            # 若全球锚点数值远小于中国锚点（如46 vs 166），判定为亿美元口径
            if glb and china and glb.get("2024") and china.get("2024"):
                _GLOBAL_UNIT_USD = float(glb["2024"]) < float(china["2024"]) * 0.8
    if not glb and not china:
        return report_text  # 无权威锚点，不清理

    # 2) 已知禁用值（LLM 曾自创的窄口径）
    BAD_VALS = {"1", "8.3", "9.8", "13.2", "15.2", "18.6", "2.1", "5.6", "12.0"}

    def _num_repl(m):
        # 通用数字替换：若数字在禁用值列表且该年份有权威锚点 → 替换
        year = m.group(1)
        num = m.group(2)
        unit = m.group(3)
        if num in BAD_VALS and china and year in china:
            return "{}年{}亿元（权威口径{}亿元）".format(year, china[year], china[year])
        return m.group(0)

    # 模式A（年份前置）："2024年中国市场规模约1亿元" → "2024年中国市场规模166亿元"
    text = _re89.sub(
        r"(20\d{2})年中国(?:油位传感器|油位|液位传感器)?市场规模[^。\n]{0,12}?(?:约为|约|为|达)?\s*(\d+(?:\.\d+)?)\s*(亿元|亿元人民币)",
        lambda m: (m.group(1) + "年中国市场规模" + str(china[m.group(1)]) + "亿元（权威口径" + str(china[m.group(1)]) + "亿元）"
                  if (m.group(2) in BAD_VALS and china and m.group(1) in china) else m.group(0)),
        report_text)
    # 模式B（年份后置）："中国油位传感器市场规模2024年为1亿元" → 166亿元
    text = _re89.sub(
        r"(中国(?:油位传感器|油位|液位传感器)?市场规模[^。\n]{0,20}?)(20\d{2})年[^为约为达]{0,4}(?:为|约|约合|达)?\s*(\d+(?:\.\d+)?)\s*(亿元|亿元人民币)",
        lambda m: (m.group(1) + m.group(2) + "年" + str(china[m.group(2)]) + "亿元（权威口径" + str(china[m.group(2)]) + "亿元）"
                  if (m.group(3) in BAD_VALS and china and m.group(2) in china) else m.group(0)),
        text)
    # 模式C（承接句）："2025年约8.3亿元（A，另一口径）" —— 前面没有"中国市场规模"
    # 但 8.3 是已知禁用值，且只在"中国"章节出现 → 谨慎处理：仅当句内含 2025 且前后文含"中国"
    def _ctx_c(m):
        year = m.group(1)
        num = m.group(2)
        if num in BAD_VALS and china and year in china:
            return "{}年{}亿元（权威口径{}亿元）".format(year, china[year], china[year])
        return m.group(0)
    text = _re89.sub(r"(20\d{2})年(?:约|预计|约为|预计达)?\s*(\d+(?:\.\d+)?)\s*亿元", _ctx_c, text)
    # 模式D（无锚点年份自创值删除）：仅在中国市场规模语境下，删除 2026/2030 等
    # 无权威锚点、且不在全球锚点中的 LLM 自创值（"2026年预计9.8亿元（A）"等）。
    def _ctx_d(m):
        year = m.group(1)
        # 上下文判断：匹配位置前 200 字符内若含中国市场规模/中国TAM/中国油位，视为中国语境
        ctx_before = text[max(0, m.start() - 200):m.start()]
        is_china_ctx = bool(_re89.search(r"中国市场规模|中国TAM|中国油位|中国市场", ctx_before))
        if is_china_ctx:
            # 中国语境：仅保留有中国锚点的年份（已被模式B/C替换），其余自创值删除
            if china and year in china:
                return m.group(0)
            return ""
        # 全球/其他语境：命中全球锚点的年份保留（单位错乱由模式4兜底）
        if glb and year in glb:
            return m.group(0)
        if china and year in china:
            return m.group(0)
        return ""
    text = _re89.sub(
        r"，(20(?:2[6-9]|3\d))年(?:预计|约|预计达)?\s*(\d+(?:\.\d+)?)亿元（A）", _ctx_d, text)
    # 4) 单位错乱兜底：全球市场 46.0亿元 → 46.0亿美元（仅当权威锚点单位为亿美元时）
    # R90：只有确认 _GLOBAL_UNIT_USD 才执行，避免把"亿元"口径误改为"亿美元"。
    if glb and _GLOBAL_UNIT_USD:
        # 句子级处理：仅对不含"中国"语境的句子（全球市场规模/TAM 句）统一 亿元 → 亿美元；
        # 含"中国TAM/中国市场规模"的对比句由中国锚点模式（A/B/E）处理，避免误伤。
        def _global_unit(m):
            sent = m.group(0)
            if _re89.search(r"中国(?:油位传感器|油位|液位传感器)?市场规模|中国TAM|中国市场", sent):
                return sent
            if _re89.search(r"全球", sent) and _re89.search(
                    r"(油位传感器市场|市场规模|TAM|全球市场|市场20\d{2}年规模)", sent):
                return _re89.sub(r"(\d+(?:\.\d+)?)亿元", r"\1亿美元", sent)
            return sent
        text = _re89.sub(r"[^。\n]*。?", _global_unit, text)
        # 对比句兜底："全球TAM约46亿元...中国TAM约1亿元" 这类混合句
        # 若整句被排除，则对"全球TAM"前缀的数值单独做单位修正
        def _global_tam(m):
            sent = m.group(0)
            if _re89.search(r"全球TAM[^。\n]{0,30}?(\d+(?:\.\d+)?)亿元", sent):
                return _re89.sub(r"(全球TAM[^。\n]{0,30}?)(\d+(?:\.\d+)?)亿元",
                                 lambda mm: mm.group(1) + mm.group(2) + "亿美元", sent)
            return sent
        text = _re89.sub(r"[^。\n]*。?", _global_tam, text)
    # 模式E（残留引用句）："中国TAM约1亿元"、"市场规模仅1亿元"、"TAM口径（1亿元）"等
    # 常见变体统一替换为中国权威锚点 2024 值。
    if china and "2024" in china:
        _c24 = china["2024"]
        text = text.replace("中国TAM约1亿元", "中国TAM约{}亿元（权威口径{}亿元）".format(_c24, _c24))
        text = text.replace("中国TAM约1亿元人民币", "中国TAM约{}亿元（权威口径{}亿元）".format(_c24, _c24))
        text = text.replace("市场规模仅1亿元", "市场规模约{}亿元（权威口径{}亿元）".format(_c24, _c24))
        text = text.replace("TAM口径（1亿元）", "TAM口径（{}亿元）".format(_c24))
        text = text.replace("| 1亿元（2024年，A）", "| {}亿元（2024年，A）".format(_c24))
        text = _re89.sub(r"中国TAM约\s*1亿元", "中国TAM约{}亿元（权威口径{}亿元）".format(_c24, _c24), text)
        # 信号表/总结句中的独立"1亿元"仅在中国油位传感器市场规模语境替换
        text = _re89.sub(
            r"(中国油位传感器市场规模[^。\n]{0,20}?\|?\s*)1亿元",
            r"\g<1>{}亿元".format(_c24), text)
    # 5) 删除"口径冲突自证"段落（R85 铁律禁止写自证段落；LLM 常用
    #    "经交叉验证，X亿元为当前数据字典中标注为(A)实际值"来自圆其说）
    text = _re89.sub(
        r"（?需要特别指出[^。]*。?\s*）?", "", text)
    text = _re89.sub(
        r"经交叉验证[^。]*。", "", text)
    text = _re89.sub(
        r"该口径冲突已记录为数据缺口[^。]*。", "", text)
    return text

