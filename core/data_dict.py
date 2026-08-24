# -*- coding: utf-8 -*-
"""
共享数据字典（Shared Data Dictionary）— R7 收敛机制核心

问题：报告发散的三层根因之一，是正文数值由 LLM 各自从记忆中抽取，
不引用数据层 → 同一数据点重复出现且口径打架（如"2023中国市场规模"
数据层给 3644.6 亿、正文自编 3450 亿）、89% 的数字无来源。

方案：把 collected_data 里的确定性数据建成一份**命名的数据字典**，
注入写作 prompt（格式 {ref:market_size_china_2024}），要求正文所有
数值必须引用字典 key 而非自由输出。IronGate 端校验：
  1. 正文出现的关键数值，是否能在数据字典中找到同源对应值；
  2. 找不到来源的"游离数字"超过阈值 → 阻断（evidence_layer 硬校验）。

本模块只做数据组织与校验，不产生内容。数据真实性由 enrich source 保障。
"""

from __future__ import annotations
import re, json
import logging
from pathlib import Path

logger = logging.getLogger("2hao.data_dict")

_ROOT = Path(__file__).resolve().parent.parent

# 数据字典允许引用的 fig_* 键（与 data_enrichment.ALLOWED_FIG_KEYS 对齐）
ALLOWED_KEYS = {
    "fig_revenue_trend", "fig_profitability", "fig_margin", "fig_roe",
    "fig_market_size_global", "fig_market_size_china", "fig_peer_comparison",
    "fig_competitive_landscape", "fig_players", "fig_supply_chain",
    "fig_market_positioning", "fig_growth_drivers", "fig_business_segments",
    "fig_tech_segments", "fig_valuation", "fig_capital_flow",
    "fig_funding_history", "fig_industry_board", "fig_business_model",
    "fig_revenue_change", "fig_profit_change", "fig_gross_margin",
    "fig_roe_trend", "fig_applications", "fig_guidance_track",
    "fig_segment_performance", "fig_margin_trend",
}


def build_data_dict(collected_data: dict | None) -> dict:
    """从 collected_data 构建扁平化的命名数据字典。

    返回 {ref_key: numeric_value}，ref_key 形如:
      market_size_china_2024 / players_韦尔股份 / margin_2024
    同时返回元信息供注入 prompt。
    """
    d = {}
    if not isinstance(collected_data, dict):
        return d
    cd = collected_data.get("chart_data", {})
    if not isinstance(cd, dict):
        return d

    # 年份序列类：{year: value}
    year_keys = ["fig_revenue_trend", "fig_profitability", "fig_margin",
                 "fig_market_size_global", "fig_market_size_china",
                 "fig_roe_trend", "fig_margin_trend"]
    for k in year_keys:
        raw = cd.get(k)
        if isinstance(raw, dict):
            for y, v in raw.items():
                if isinstance(v, (int, float)) and y.isdigit():
                    d[f"{k.replace('fig_', '')}_{y}"] = float(v)
                elif isinstance(v, dict):
                    # {year: {revenue: x, net_profit: y}} 结构
                    for sub, sv in v.items():
                        if isinstance(sv, (int, float)) and sub in ("revenue", "net_profit", "gross_margin", "roe"):
                            d[f"{k.replace('fig_', '')}_{y}_{sub}"] = float(sv)

    # 标签序列类：{label: value}
    label_keys = ["fig_applications", "fig_tech_segments", "fig_players",
                  "fig_supply_chain", "fig_growth_drivers"]
    for k in label_keys:
        raw = cd.get(k)
        if isinstance(raw, dict):
            for label, v in raw.items():
                if isinstance(v, (int, float)) and not str(label).startswith("_"):
                    d[f"{k.replace('fig_', '')}_{label}"] = float(v)

    # 公司财务类：fig_peer_comparison {company: {revenue, net_profit, pe, mcap}}
    raw_peer = cd.get("fig_peer_comparison")
    if isinstance(raw_peer, dict):
        for comp, metrics in raw_peer.items():
            if isinstance(metrics, dict):
                for mk, mv in metrics.items():
                    if isinstance(mv, (int, float)):
                        d[f"peer_{comp}_{mk}"] = float(mv)

    # R9 数据底座接入：资金面/行业基线/公司事件（Marvis 构建的本地库）
    # 只读不写，数据点带 source（见 core/data_basement.py）
    try:
        from core.data_basement import build_basement_data_dict
        asset = collected_data.get("asset", "") if isinstance(collected_data, dict) else ""
        basement = build_basement_data_dict(asset)
        for k, v in basement.items():
            if k not in d:  # 不覆盖已有数据
                d[k] = v
    except Exception as _be:
        logger.debug("[DATA-DICT] basement merge failed: %s", _be)

    return d


def serialize_data_dict(d: dict, max_items: int = 60) -> str:
    """把数据字典序列化成 prompt 注入文本。"""
    if not d:
        return ""
    items = sorted(d.items(), key=lambda kv: kv[0])[:max_items]
    lines = ["=== 共享数据字典（正文数值必须引用，禁止自编） ===",
             "格式: {ref:key} = 数值。引用示例：中国市场规模2024年为 {ref:market_size_china_2024} 亿元。"]
    # R82（2026-08-06）：市场类键强制带单位——全球市场口径为"亿美元"、
    # 中国市场口径为"亿元"，防止 LLM 把全球 46/50/54.5/65 亿美元写成"亿元"
    # （第5轮 market_size_consistency 冲突根因）。
    _unit_hint = {
        "market_size_global_": "亿美元(全球)",
        "market_size_china_": "亿元(中国)",
        "revenue_trend_": "亿元",
        "profitability_": "%",
    }
    for k, v in items:
        _suffix = ""
        for _prefix, _unit in _unit_hint.items():
            if k.startswith(_prefix):
                _suffix = "  [" + _unit + "]"
                break
        lines.append(f"  {{ref:{k}}} = {v}{_suffix}")
    lines.append("（完整字典共 %d 项，以上为前 %d 项）" % (len(d), max_items))
    return "\n".join(lines)


def validate_numeric_refs(report_text: str, data_dict: dict, max_unverified: int = 6) -> dict:
    """校验正文数字与数据字典的对应关系。

    策略（务实版）：
      - 收集正文中带 (A)/(B) 标注的"确定性数字"（实际/基准值）
      - 与数据字典做同值匹配：正文数字能在字典中找到 ≈ 同一数值 → verified
      - 无法匹配的确定性数字 → unverified（游离数字）
    FP2 数据零编造：unverified 超过阈值即告警/阻断。

    注意：预测值(E)/(F) 与推导值（毛利率、ROE 区间）不在此列——
    它们属于分析产出而非数据引用，避免误杀。
    """
    if not isinstance(report_text, str) or not report_text:
        return {"verified": 0, "unverified": 0, "unverified_values": [], "passed": True}

    # 提取带 (A) 或 (B) 标注的数值（确定性数据点）
    # 锚定：数字前不能是数字/小数点，避免匹配到被截断的子串。
    # 例："4061.2亿元(A)" 只应匹配整体 4061.2，不应再拆出 "061.2(A)"。
    pat = re.compile(
        r'(?<![\d.])(\d{2,}(?:[.,]\d{1,3})?)\s*(?:亿元|亿美元|万台|亿只|%|倍)?\s*\(([ABab])\)'
    )
    found = pat.findall(report_text)
    unverified = []
    for val_str, tag in found:
        try:
            val = float(val_str.replace(",", ""))
        except ValueError:
            continue
        # 数据字典同值匹配（容差 1%）
        # R88（2026-08-06）：过滤非数值项（brand_entity_map/ulp_* 等字符串键），
        # 否则 float - str 抛 TypeError，data_dict_refs 检查整项异常判 0 分。
        numeric_values = [dv for dv in data_dict.values()
                          if isinstance(dv, (int, float)) and not isinstance(dv, bool)]
        if any(abs(val - dv) / max(abs(dv), 1e-9) < 0.01 for dv in numeric_values):
            continue
        unverified.append((val, val_str, tag))
    passed = len(unverified) <= max_unverified
    return {
        "verified": len(found) - len(unverified),
        "unverified": len(unverified),
        "unverified_values": [f"{u}({t})" for _, u, t in unverified[:8]],
        "passed": passed,
    }


def load_data_dict_from_cache(asset: str) -> dict:
    """从 output/<asset>_data_dict.json 加载已生成的数据字典（供 IronGate 复用）。

    R11（2026-08-01 思必驰反思修复）：删除"取最新文件"兜底 —— 该逻辑在多标的并发
    跑管线时会把别的标的 data_dict 串读进来，导致 IronGate 用错误的基准比对
    （思必驰报告被拿去跟柯力传感 data_dict 比对，报出 88亿 vs 192 的假冲突）。
    现在只按 asset 精确匹配；匹配不到返回空（校验器降级为 warning，不误判）。
    """
    if asset:
        # 尝试多种文件名形态
        candidates = [
            f"{asset}_data_dict.json",
            f"{asset.split()[0]}_data_dict.json" if asset.split() else None,
        ]
        for name in candidates:
            if not name:
                continue
            cache = _ROOT / "output" / name
            if cache.exists():
                try:
                    return json.loads(cache.read_text(encoding="utf-8"))
                except Exception:
                    pass
    return {}


def save_data_dict(asset: str, d: dict) -> str:
    """持久化数据字典供 IronGate 校验复用。"""
    cache = _ROOT / "output" / f"{asset}_data_dict.json"
    cache.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(cache)
