"""
数据口径层（Data Caliber）— R28 全量修复方向A

**问题**：数据进了管道但没带单位/时期/来源元数据，LLM 只能猜：
  - 毛利率 5.0%（单季值？全年值？比值？）vs 34.5%（另一个来源）
  - 北向 -67.75（万元？亿元？）
  - 盈利预测 3.4 亿 vs 20 亿（两个模型并存）
  → 同一指标多来源矛盾，系统不检测，LLM 全写进正文。

**方案**：
  1. 每个进入正文的数值必须带口径元数据 {unit, period, source, as_of}
  2. 数据字典序列化时注入单位/时期标注（prompt 明示"不得臆断单位"）
  3. 冲突检测器：同一指标多来源差异 >20% → 告警/阻断，强制 LLM 声明"存在两套口径"

**口径元数据规则**：
  - unit: 万元/亿元/元/百分比/比值/倍/户/股
  - period: 单季(Q1)/全年(A)/TTM/累计
  - source: 来源（baostock/akshare/enrich/history/basement）
  - as_of: 数据日期

本模块只做数据组织与校验，不产生内容（FP2）。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("2hao.data_caliber")

_ROOT = Path(__file__).resolve().parent.parent

# ── 口径规则：字段名特征 → 推断单位/时期 ──
# key 含这些特征的字段，默认单位/时期
UNIT_RULES = [
    # (key 特征, 单位, 时期)
    (["market_size", "规模"], "亿元", "全年"),
    (["revenue", "营收", "MBRevenue"], "亿元", "全年"),
    (["net_profit", "净利", "净利润"], "亿元", "全年"),
    (["profitability"], "亿元", "全年"),
    (["margin", "毛利率", "毛利", "gross"], "百分比", "全年"),
    (["roe"], "百分比", "全年"),
    (["pe", "PE", "市盈率"], "倍", "TTM"),
    (["pb", "PB", "市净率"], "倍", "最新"),
    (["eps"], "元", "TTM"),
    (["shareholder", "股东户数"], "户", "最新"),
    (["flow_north", "北向"], "万元", "累计"),
    (["margin_balance", "两融"], "万元", "最新"),
    (["flow_margin"], "亿元", "最新"),
    (["dividend", "分红"], "元", "全年"),
]

# 指标中文名 → 标准口径（供报告正文校验）
INDICATOR_CALIBER = {
    "毛利率": {"unit": "百分比", "period": "全年", "threshold_gap": 20},
    "margin": {"unit": "百分比", "period": "全年", "threshold_gap": 20},
    "净利率": {"unit": "百分比", "period": "全年", "threshold_gap": 20},
    "roe": {"unit": "百分比", "period": "全年", "threshold_gap": 20},
    "营业收入": {"unit": "亿元", "period": "全年", "threshold_gap": 20},
    "营收": {"unit": "亿元", "period": "全年", "threshold_gap": 20},
    "revenue": {"unit": "亿元", "period": "全年", "threshold_gap": 20},
    "净利润": {"unit": "亿元", "period": "全年", "threshold_gap": 20},
    "净利": {"unit": "亿元", "period": "全年", "threshold_gap": 20},
    "net_profit": {"unit": "亿元", "period": "全年", "threshold_gap": 20},
    "profitability": {"unit": "亿元", "period": "全年", "threshold_gap": 20},
    "PE": {"unit": "倍", "period": "TTM", "threshold_gap": 30},
    "市盈率": {"unit": "倍", "period": "TTM", "threshold_gap": 30},
    "pe": {"unit": "倍", "period": "TTM", "threshold_gap": 30},
    "北向": {"unit": "万元", "period": "累计", "threshold_gap": 20},
    "两融": {"unit": "万元", "period": "最新", "threshold_gap": 20},
}


def infer_caliber(key: str) -> dict:
    """根据 key 特征推断默认口径。"""
    cal = {"unit": "", "period": "", "source": "unknown", "as_of": ""}
    for features, unit, period in UNIT_RULES:
        if any(f in key for f in features):
            cal["unit"] = unit
            cal["period"] = period
            break
    return cal


def infer_caliber_with_source(key: str, source_meta: dict | None = None) -> dict:
    """根据 key 特征推断口径，支持外部来源元数据优先。

    来源元数据优先级高于硬编码 UNIT_RULES，解决同一 key 在不同来源中
    含义不同（如 consensus 预测值为亿元但 basement 原始值为万元）的问题。

    Args:
        key: 数据字段名
        source_meta: 外部来源元数据 {key: {unit, period, source, ...}}，
                     若提供且包含该 key 的明确单位，则优先使用

    Returns:
        cal dict，与 infer_caliber 返回格式一致
    """
    # 来源元数据优先
    if source_meta and key in source_meta:
        sm = source_meta[key]
        if sm.get("unit"):
            return {
                "unit": sm["unit"],
                "period": sm.get("period", ""),
                "source": sm.get("source", "unknown"),
                "as_of": sm.get("as_of", ""),
            }
    # 回退到硬编码推断
    return infer_caliber(key)


def build_caliber_meta(data_dict: dict) -> dict:
    """为 data_dict 每个 key 构建口径元数据。

    返回 {ref_key: {unit, period, source, as_of}}
    """
    meta = {}
    if not isinstance(data_dict, dict):
        return meta
    for key, val in data_dict.items():
        cal = infer_caliber(key)
        # source 推断：basement 来源的 key 带前缀
        if key.startswith("capital_") or key.startswith("flow_"):
            cal["source"] = "capital_flow.db"
        elif key.startswith("consensus_"):
            cal["source"] = "consensus_estimates.db"
        elif key.startswith("gov_") or key.startswith("event_"):
            cal["source"] = "company_events.db"
        elif key.startswith("industry_") or key.startswith("chain_"):
            cal["source"] = "industry_baselines/chain"
        elif key.startswith("macro_") or key.startswith("gmacro_"):
            cal["source"] = "macro_series.json"
        elif key.startswith("val_"):
            cal["source"] = "valuation_knowledge"
        meta[key] = cal
    return meta


def serialize_caliber_annotations(meta: dict, max_items: int = 40) -> str:
    """序列化口径标注，注入 prompt 供 LLM 正确理解单位/时期。

    格式: {ref:key} = 值 <unit=亿元, period=全年, source=...>
    """
    if not meta:
        return ""
    lines = [
        "=== 数据口径标注（正文引用数值时必须带单位/时期） ===",
        "规则：以下每个数值标注了单位/时期，正文引用时禁止臆断单位。",
    ]
    for i, (k, cal) in enumerate(meta.items()):
        if i >= max_items:
            break
        unit = cal.get("unit") or ""
        period = cal.get("period") or ""
        src = cal.get("source") or ""
        # 兜底：UNIT_RULES 推断为空时，检查 INDICATOR_CALIBER
        if not unit:
            for ind_name, ind_cal in INDICATOR_CALIBER.items():
                if ind_name in k:
                    unit = ind_cal.get("unit", "")
                    if not period:
                        period = ind_cal.get("period", "")
                    break
        unit = unit or "?"
        period = period or "?"
        src = src or "?"
        lines.append(f"  {k}: unit={unit}, period={period}, source={src}")
    lines.append("（完整口径标注共 %d 项）" % len(meta))
    return "\n".join(lines)


# ── 冲突检测器 ────────────────────────────────────────────────
def detect_value_conflicts(data_dict: dict, threshold_pct: float = 20.0) -> list:
    """检测 data_dict 中同一指标的多来源冲突。

    规则：key 规范化后（去前缀/数字）相同的指标，值差异超过阈值 → 冲突。
    返回 [{indicator, values:[{key, value, unit}], gap_pct, severity}]
    """
    if not isinstance(data_dict, dict):
        return []
    # 按指标名聚类（规范化 key：去年份/去前缀/去表名）
    clusters = {}
    for key, val in data_dict.items():
        if not isinstance(val, (int, float)):
            continue
        norm = _normalize_indicator(key)
        if not norm:
            continue
        clusters.setdefault(norm, []).append((key, val))

    # R33（2026-08-02）+ R88（2026-08-06）：时间序列豁免——同一指标按年份分布的
    # 序列（如 revenue_trend_2024..2030、margin_2014..2025）是同一来源的趋势/预测数据，
    # 不是"多来源口径冲突"，整组跳过。
    # R88 修复：不再要求年份"连续递增"——行业报告常见稀疏预测点（2024/2025/2026/2030），
    # 若强制连续会把 2024=46 与 2030=65 误判为 41% 冲突（data_conflicts 反复误报根因）。
    # 真正的冲突（如 fig_margin_2025 全年 34.5% vs fig_margin_2026q1 单季 5.0%）
    # 特征是同一年份出现多条（len(years) != len(entries)），仍正常检测。
    def _is_timeseries_group(entries):
        if len(entries) < 3:
            return False
        years = set()
        for _k, _v in entries:
            m = re.search(r"_(\d{4})(?:q\d)?$", _k)
            if not m:
                return False
            years.add(int(m.group(1)))
        if len(years) != len(entries):
            return False  # 同一年份出现多条 → 真实多来源，需检测
        return True  # 年份互不重复 → 时间序列/预测点组，豁免

    conflicts = []
    for indicator, entries in clusters.items():
        if len(entries) < 2:
            continue
        if _is_timeseries_group(entries):
            continue
        # 计算两两最大差异
        vals = [v for _, v in entries]
        vmax, vmin = max(vals), min(vals)
        if vmin == 0:
            continue
        gap = abs(vmax - vmin) / abs(vmin) * 100
        if gap > threshold_pct:
            cal = INDICATOR_CALIBER.get(indicator, {})
            unit = cal.get("unit", "")
            conflicts.append(
                {
                    "indicator": indicator,
                    "entries": [{"key": k, "value": v, "unit": unit} for k, v in entries],
                    "gap_pct": round(gap, 1),
                    "severity": "error" if gap > threshold_pct * 2 else "warning",
                    "suggestion": f"同一指标 {indicator} 多来源差异 {gap:.0f}%，正文必须标注'存在两套口径，本报告采用X'",
                }
            )
    return conflicts


def _normalize_indicator(key: str) -> str:
    """规范化指标名：去表名前缀/年份/后缀，识别核心指标。"""
    # 去明确表名前缀（注意：margin_/revenue_/profit_ 是核心指标名，不能去掉）
    k = key
    for pre in [
        "fig_",
        "capital_",
        "flow_",
        "consensus_",
        "gov_",
        "event_",
        "industry_",
        "chain_",
        "macro_",
        "gmacro_",
        "val_",
        "peer_",
    ]:
        k = k.replace(pre, "")
    # 去年份/时期后缀（4位数字 或 2026q1 等）
    k = re.sub(r"_\d{4}$", "", k)
    k = re.sub(r"_\d{4}[qQ]\d$", "", k)
    k = re.sub(r"^\d{4}$", "", k)
    # 去尾部描述符
    k = re.sub(r"_(latest|cur|avg|5d|20d|count|trend|rank)$", "", k)
    # R33（2026-08-02）：保证金/融资融券类余额（margin_balance）归"两融"细分
    # 口径：capital_margin_balance=融资余额、flow_margin_balance=融券余额，
    # 二者数值天然不同量级，不能归并为同一指标互相比较（否则必误报冲突）。
    # 注意：capital_/flow_ 前缀在上一循环已被去除，须用原始 key 判断。
    if "balance" in k and "margin" in k:
        if key.startswith("capital"):
            return "两融_融资"
        if key.startswith("flow"):
            return "两融_融券"
        return "两融"
    # 识别核心指标
    # P3-audit 2026-08-24 真 bug 修复：原 `if ind in k` 裸子串匹配把任何
    # 尾部含 "pe" 的键（如 revision_slope→'pe'）聚进 PE 冲突簇，
    # 产出 "值相差375040%" 式荒谬误报（宁德时代 earnings_notes 实测触发）。
    # 边界规则：仅禁止紧邻字母/数字（下划线视作分词符，允许 gross_margin、
    # pe_forward 这类惯例形态）；中文指标保持子串。
    for ind in INDICATOR_CALIBER:
        if not ind.isascii():
            if ind in k:
                return ind
            continue
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(ind)}(?![A-Za-z0-9])", k):
            return ind
    return ""


def check_report_units(report_text: str, data_dict: dict) -> dict:
    """校验报告正文的数值单位标注。

    规则：正文中出现带 (A)/(B) 的确定性数值，若 data_dict 对应指标单位是
    "亿元"/"万元"等，正文数值必须带单位或上下文能推断，否则告警。
    """
    if not isinstance(report_text, str) or not report_text:
        return {"passed": True, "issues": [], "checked": 0}
    issues = []
    checked = 0
    # 提取带标注的数值
    pat = re.compile(r"([-]?\d[\d,.]*)\s*(亿元|万元|亿|万|%|倍|元|户|股)?\s*\(([ABab])\)")
    for m in pat.finditer(report_text):
        val_str, unit_str, tag = m.group(1), m.group(2) or "", m.group(3)
        checked += 1
        try:
            val = float(val_str.replace(",", ""))
        except ValueError:
            continue
        # 无单位的大额数值（可能单位缺失）
        if not unit_str and abs(val) > 10000:
            issues.append(
                {
                    "value": val_str,
                    "tag": tag,
                    "issue": f"数值 {val_str} 无单位标注（绝对值>10000，疑似缺亿元/万元）",
                }
            )
    passed = len(issues) <= 5  # 容忍少量
    return {"passed": passed, "issues": issues, "checked": checked}


# ── 下行一致性检查（2026-08-07 圆桌油位 v2.3 硬伤落地）──────────────────


def detect_downstream_conflicts(report_text: str, params: dict | None = None) -> list:
    """检测"下行数字口径不一致"——最坏敞口/止损线/悲观NPV 混用。

    油位 v2.3 硬伤：最坏敞口2100万 vs 止损线2450万 vs 悲观NPV -1100万 三口径混用，
    老板无法判断"最坏亏多少"。本检查提取三类下行数字，比对量级一致性。

    params 可选覆盖（测试用）：{"worst_exposure": 2100, "stop_loss": 2450, "pessimistic_npv": -1100}
    无 params 时从 report_text 正则提取。
    """
    import re as _re

    issues = []

    # 1. 从参数或文本提取三类下行数字（单位：万元）
    def _find(pattern, param_key=None):
        if params and param_key and param_key in params:
            return params[param_key]
        m = _re.search(pattern, report_text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                return None
        return None

    worst = _find(r"(?:最坏(?:情形)?资金?敞口|资金敞口|最坏损失)[^0-9]{0,10}约?([0-9,]+)", "worst_exposure")
    stop = _find(r"(?:止损|退出|累计运营投入达|触发)[^0-9]{0,10}(?:累计运营投入达|触发)?([0-9,]+)万", "stop_loss")
    pess = _find(
        r"(?:悲观[^0-9]{0,10}(?:NPV|情景)?|悲观情景.*?NPV)\s*[^0-9-]{0,5}([-+]?[0-9,]+)\s*万", "pessimistic_npv"
    )

    # 止损线 vs 最坏敞口：止损触发点通常应 ≤ 最坏敞口（在耗尽'最坏'前止损）。
    # 若止损线显著大于最坏敞口（>10%），说明"最坏"定义小于止损触发 → 下行边界混乱。
    # 但若报告已说明两者量纲不同（累计运营投入 vs 资金敞口），降级为 warning（已说明，非矛盾）。
    _has_explanation = any(
        k in report_text for k in ("量纲不同", "口径说明", "统一口径", "两个数字服务于不同", "不矛盾")
    )
    if worst and stop and stop > worst * 1.10:
        _sev = "warning" if _has_explanation else "error"
        issues.append(
            {
                "type": "downstream_conflict",
                "severity": _sev,
                "worst_exposure_wan": worst,
                "stop_loss_wan": stop,
                "gap_wan": round(stop - worst, 0),
                "issue": f"最坏敞口({worst:.0f}万) 小于止损线({stop:.0f}万)——"
                f"止损触发点比'最坏'还大"
                + (
                    "，但报告已说明量纲不同（累计运营投入 vs 资金敞口），降级提醒"
                    if _has_explanation
                    else "，下行边界定义混乱，需统一口径"
                ),
            }
        )
    if pess is not None and worst and pess > 0 and worst > 0:
        # 悲观NPV为正与最坏敞口为正矛盾（悲观应亏损或低于最坏）
        issues.append(
            {
                "type": "downstream_conflict",
                "severity": "warning",
                "issue": f"悲观NPV({pess:.0f}万) 为正但与最坏敞口({worst:.0f}万)并存——"
                f"若最坏敞口是现金投入，悲观NPV应显著为负，需说明量纲关系",
            }
        )
    if not worst and not stop and not pess:
        return issues  # 无下行数字，跳过
    return issues


def detect_timeline_conflicts(report_text: str, params: dict | None = None) -> list:
    """检测"时间线矛盾"——认证周期 vs 盈亏平衡/量产时间。

    油位 v2.3 硬伤：认证12-18个月，但2026Q3启动→2027Q2盈亏平衡（仅9个月），
    认证未完成不可能量产盈亏平衡。本检查提取关键时间线节点，判断可达性。

    params 可选覆盖：{"certification_months": 15, "start_q": "2026Q3", "breakeven_q": "2027Q2"}
    """
    import re as _re

    issues = []
    # 认证周期（月）
    cert_months = None
    if params and "certification_months" in params:
        cert_months = params["certification_months"]
    else:
        m = _re.search(r"认证[^0-9]{0,15}?([0-9]{1,2})\s*[-~到]\s*([0-9]{1,2})\s*个月", report_text)
        if m:
            cert_months = (float(m.group(1)) + float(m.group(2))) / 2  # 区间取中值
        else:
            m = _re.search(r"认证[^0-9]{0,15}?([0-9]{1,2})\s*个月", report_text)
            if m:
                cert_months = float(m.group(1))
    # 启动季度与盈亏平衡季度
    start_q = params.get("start_q") if params else None
    bk_q = params.get("breakeven_q") if params else None
    if not start_q:
        m = _re.search(r"2026\s*(?:年)?\s*第?\s*([一二三四Q1-4])季度", report_text)
        if m:
            start_q = f"2026Q{_cn_q(m.group(1))}"
    if not bk_q:
        # 找到"盈亏平衡"位置，向前找最近（最靠近）的季度日期
        _bk_pos = report_text.find("盈亏平衡")
        if _bk_pos > 0:
            _before = report_text[max(0, _bk_pos - 40) : _bk_pos]
            _dates = list(_re.finditer(r"(20\d{2})\s*(?:年)?\s*第?\s*([一二三四Q1-4])季度", _before))
            if _dates:
                m = _dates[-1]  # 最靠近盈亏平衡的
                bk_q = f"{m.group(1)}Q{_cn_q(m.group(2))}"
            else:
                m = _re.search(r"盈亏平衡[^。]{0,20}?(20\d{2})\s*(?:年)?\s*第?\s*([一二三四Q1-4])季度", report_text)
                if m:
                    bk_q = f"{m.group(1)}Q{_cn_q(m.group(2))}"

    def _q_to_num(q: str) -> int:
        import re as _r

        m = _r.search(r"(20\d{2})Q?([1-4])", q or "")
        if m:
            return int(m.group(1)) * 4 + int(m.group(2))
        return 0

    if cert_months and start_q and bk_q:
        _start_n = _q_to_num(start_q)
        _bk_n = _q_to_num(bk_q)
        if _start_n and _bk_n:
            _elapsed = (_bk_n - _start_n) * 3  # 季差 → 月
            if cert_months > _elapsed + 3:  # +3 容忍
                issues.append(
                    {
                        "type": "timeline_conflict",
                        "severity": "error",
                        "certification_months": cert_months,
                        "elapsed_months": _elapsed,
                        "issue": f"认证需 {cert_months:.0f} 个月，但 {start_q}→{bk_q} 仅 {_elapsed} 个月——"
                        f"认证未完成前不可能量产盈亏平衡，时间线矛盾，需澄清认证起点或延后盈亏平衡",
                    }
                )
    return issues


def detect_assumption_concentration(report_text: str, params: dict | None = None) -> list:
    """检测"关键假设脆弱性"——少数假设驱动大部分价值（80% 价值由2个假设驱动）。

    油位 v2.3：报告自述"项目价值约80%由毛利率+罐箱渗透率驱动"，但未强制压力测试。
    本检查识别此类"价值集中度"声明，标记需压力测试。
    """
    import re as _re

    issues = []
    if params and "concentration" in params:
        _c = params["concentration"]
        issues.append(
            {
                "type": "assumption_concentration",
                "severity": "warning",
                "concentration": _c,
                "issue": f"项目价值 {_c} 由少数假设驱动——需对这些假设做压力测试（±30%波动）+季度复核",
            }
        )
        return issues
    m = _re.search(
        r"(?:价值|NPV|项目价值|价值量)[^0-9]{0,6}(?:约|近|约)?\s*([0-9]{1,3})%[^。]{0,20}(?:驱动|决定|来自|贡献)",
        report_text,
    )
    if not m:
        m = _re.search(r"([0-9]{1,3})%\s*(?:的)?(?:价值|NPV|项目价值)[^。]{0,15}(?:驱动|决定|来自)", report_text)
    if m:
        pct = int(m.group(1))
        if pct >= 60:
            issues.append(
                {
                    "type": "assumption_concentration",
                    "severity": "warning",
                    "concentration": f"{pct}%",
                    "issue": f"项目价值 {pct}% 由少数假设驱动——需压力测试（±30%波动）+季度复核承诺",
                }
            )
    return issues


def _cn_q(q: str) -> str:
    """中文季度/数字 → 数字。一→1，二→2，Q1→1。"""
    _map = {"一": "1", "二": "2", "三": "3", "四": "4", "Q1": "1", "Q2": "2", "Q3": "3", "Q4": "4"}
    return _map.get(str(q).upper(), str(q))


def run_downstream_checks(report_text: str, params: dict | None = None) -> dict:
    """一站式运行三个下行/时间线/假设集中度检查（供 Gate 调用）。"""
    result = {
        "downstream": detect_downstream_conflicts(report_text, params),
        "timeline": detect_timeline_conflicts(report_text, params),
        "assumption": detect_assumption_concentration(report_text, params),
        "passed": True,
    }
    for group in ("downstream", "timeline"):
        for item in result[group]:
            if item.get("severity") == "error":
                result["passed"] = False
                break
    return result


if __name__ == "__main__":
    # 测试冲突检测
    sample = {
        "fig_margin_2025": 34.5,
        "fig_margin_2026q1": 5.0,
        "revenue_2025": 15.58,
        "profitability_2025": 1.68,
    }
    conflicts = detect_value_conflicts(sample)
    print("冲突检测:", conflicts if conflicts else "无")
    meta = build_caliber_meta(sample)
    print("\n口径标注:")
    print(serialize_caliber_annotations(meta))
