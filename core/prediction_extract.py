# -*- coding: utf-8 -*-
"""prediction_extract.py — 从报告文本提取可问责预测（预测账本入口）。

P3-A 落地：prediction_loop 此前"会记账但没人喂"。本模块在管线出口把
Bold Call/评级/目标价/EPS 区间确定性提取并写入预测账本，到期自动验证。

设计约束：
- 纯正则、零 LLM——账本数据必须与正文严格一致，不允许模型自由发挥
- 提取失败静默跳过（宁缺毋滥：账本只收高置信结构化结论）
"""

from __future__ import annotations

import re

_RATING_RE = re.compile(r"(?:投资评级|评级)[：:]?\s*(买入|增持|持有|中性|减持|卖出)")
_TARGET_RE = re.compile(r"(?:12个月)?目标价[：:为]?\s*(\d+(?:\.\d+)?)\s*元")
_EPS_RE = re.compile(r"(20\d{2}\s*[Ee]?)\s*年?\s*EPS[^\d]{0,6}(\d+(?:\.\d+)?)\s*元")
_FW_RE = re.compile(r"\[FW:([A-Za-z_]+)\]")


def _fw_context(report_text: str, pos: int) -> str:
    """M5 归因通道：预测位置前方 600 字内最近的 [FW:框架名]。"""
    window = report_text[max(0, pos - 600) : pos]
    tags = _FW_RE.findall(window)
    return tags[-1] if tags else ""


def extract_predictions(report_text: str) -> list[dict]:
    """从报告文本提取结构化预测。

    返回 [{kind, value, statement, framework}]；kind ∈ rating/target_price/eps_forecast。
    framework = 前方最近 [FW:x] 标记（M3 三件套产出），供胜率榜归因。
    """
    if not report_text:
        return []
    out: list[dict] = []

    m = _RATING_RE.search(report_text)
    if m:
        fw = _fw_context(report_text, m.start())
        stmt = f"[fw:{fw}] 投资评级：{m.group(1)}" if fw else f"投资评级：{m.group(1)}"
        out.append({"kind": "rating", "value": m.group(1), "statement": stmt, "framework": fw or None})

    m = _TARGET_RE.search(report_text)
    if m:
        v = float(m.group(1))
        if 0.5 < v < 100_000:  # 常识界：过滤占位/乱码
            fw = _fw_context(report_text, m.start())
            stmt = f"[fw:{fw}] 12个月目标价 {v} 元" if fw else f"12个月目标价 {v} 元"
            out.append({"kind": "target_price", "value": v, "statement": stmt, "framework": fw or None})

    seen_eps_years = set()
    for m in _EPS_RE.finditer(report_text):
        year = re.sub(r"\s", "", m.group(1))
        if year in seen_eps_years:
            continue
        seen_eps_years.add(year)
        v = float(m.group(2))
        if 0 < v < 10_000:
            fw = _fw_context(report_text, m.start())
            stmt = f"[fw:{fw}] {year} 年 EPS 预测 {v} 元" if fw else f"{year} 年 EPS 预测 {v} 元"
            out.append(
                {
                    "kind": "eps_forecast",
                    "value": v,
                    "statement": stmt,
                    "framework": fw or None,
                }
            )
    return out


def record_predictions(report_text: str, code: str, loop=None) -> int:
    """把提取的预测写入 prediction_loop 账本。返回记录条数。

    任何异常都吞掉——账本失败绝不阻塞主交付。
    """
    try:
        from core.prediction_loop_v2 import PredictionLoop

        pl = loop or PredictionLoop()
        n = 0
        for p in extract_predictions(report_text):
            pl.record(
                code=code,
                statement=f"[{p['kind']}] {p['statement']}",
                predictor="2hao-pipeline",
                target_value=float(p["value"]) if isinstance(p["value"], (int, float)) else None,
            )
            n += 1
        return n
    except Exception:
        return 0
