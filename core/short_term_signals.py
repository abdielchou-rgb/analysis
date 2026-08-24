# -*- coding: utf-8 -*-
"""3M/6M 短周期预测信号 — R78 Phase2.4 预测闭环加速。

背景：预测闭环的 forward_picks 是长周期（2027-08 到期），一年才能验证一次。
FP5 演化没有快速反馈数据。本模块从现有资金面/宏观数据生成 3 个月内可验证的
短周期信号，写入 forward_picks，让演化在三个月内有反馈。

用法：
    from core.short_term_signals import analyze_short_term_signals
    signals = analyze_short_term_signals("603662")   # 返回信号列表
"""
from __future__ import annotations
import logging
from datetime import datetime

logger = logging.getLogger("2hao.short_term_signals")

# 北向持仓 5 日均 vs 最新值的显著性阈值（%）
_NORTH_TREND_THRESHOLD = 0.02   # 2% 变动
_LHB_MIN_ABS = 5000000          # 龙虎榜净买 500 万元


def _code_from_asset(asset: str) -> str:
    """从标的提取 6 位代码。"""
    import re
    m = re.search(r"(\d{6})", str(asset))
    return m.group(1) if m else ""


def _fmt_signal(asset: str, direction: str, key_variable: str,
                falsification: str, confidence: str, note: str) -> dict:
    return {
        "asset": asset,
        "direction": direction,
        "key_variable": key_variable,
        "falsification": falsification,
        "conviction": confidence,
        "core_thesis": note,
        "horizon_months": 3,
    }


def analyze_short_term_signals(asset: str) -> list[dict]:
    """生成 3 个月内可验证的短周期信号（资金面驱动）。

    信号类型：
      1. 北向趋势：5日均 vs 最新值偏离>2% → 增/减持方向
      2. 两融余额：趋势方向（上升/下降）
      3. 龙虎榜：净买>500万 → 短期动量

    返回信号 dict 列表；数据缺失时返回空列表（不编造）。
    """
    code = _code_from_asset(asset)
    signals = []
    if not code:
        return signals

    try:
        from core.data_basement import load_stock_fund_flow, load_capital_flow
    except Exception:
        return signals

    # 个股资金面
    try:
        sf = load_stock_fund_flow(code) or {}
    except Exception:
        sf = {}
    if sf:
        _latest = sf.get("north_hold_latest")
        _avg5 = sf.get("north_hold_5d_avg")
        if _latest is not None and _avg5 and _avg5 > 0:
            _chg = (_latest - _avg5) / _avg5
            if abs(_chg) > _NORTH_TREND_THRESHOLD:
                direction = "bull" if _chg > 0 else "bear"
                signals.append(_fmt_signal(
                    asset, direction,
                    key_variable="北向持仓变化",
                    falsification="北向持仓 5 日均值反向回归超 2%",
                    confidence="medium",
                    note=f"北向持仓 {_chg*100:+.1f}% vs 5日均 (最新 {_latest:.0f}万股)",
                ))
        # 龙虎榜
        _lhb = sf.get("lhb_net_buy_latest")
        if _lhb is not None and abs(_lhb) > _LHB_MIN_ABS:
            signals.append(_fmt_signal(
                asset, "bull" if _lhb > 0 else "bear",
                key_variable="龙虎榜净买",
                falsification="龙虎榜净买方向 10 日内反转",
                confidence="low",
                note=f"龙虎榜净买 {_lhb/1e4:.0f}万元",
            ))

    # 市场级资金面（北向整体）
    try:
        cf = load_capital_flow(limit=20) or {}
    except Exception:
        cf = {}
    if cf:
        _n_latest = cf.get("north_net_latest")
        _n_5d = cf.get("north_net_5d")
        if _n_latest is not None and _n_5d is not None:
            # 北向整体净流入持续 → 市场情绪偏暖（辅助信号）
            pass  # 不单独成信号，避免过度生成

    logger.info("[SHORT-SIGNAL] %s: 生成 %d 个短周期信号", asset, len(signals))
    return signals


def record_short_term_signals(asset: str, report_type: str = "listed_company") -> int:
    """把短周期信号写入独立台账 data/short_term_signals.csv。

    为什么不用 forward_picks：R64 质量门槛强制 anchor_nav（qlib 净值锚点），
    短周期资金面信号无净值锚点——伪造锚点违反 FP2 诚实边界。
    独立台账 3M 后用实际股价/资金面验证，达成快速反馈而不编造锚点。
    """
    signals = analyze_short_term_signals(asset)
    if not signals:
        return 0
    import csv
    import os
    from pathlib import Path
    from datetime import datetime

    path = Path(__file__).resolve().parent.parent / "data" / "short_term_signals.csv"
    headers = ["signal_id", "asset", "asset_code", "created_at", "verify_by",
               "direction", "conviction", "key_variable", "core_thesis",
               "falsification", "horizon_months", "status"]
    exists = path.exists()
    written = 0
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not exists:
            w.writeheader()
        for s in signals:
            code = _code_from_asset(s["asset"])
            sig_id = f"{code or 'NA'}-{s['direction']}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            w.writerow({
                "signal_id": sig_id,
                "asset": s["asset"],
                "asset_code": code,
                "created_at": datetime.now().isoformat(),
                "verify_by": (datetime.now().replace(
                    month=datetime.now().month + s.get("horizon_months", 3))).isoformat(),
                "direction": s["direction"],
                "conviction": s["conviction"],
                "key_variable": s["key_variable"],
                "core_thesis": s["core_thesis"],
                "falsification": s["falsification"],
                "horizon_months": s.get("horizon_months", 3),
                "status": "pending",
            })
            written += 1
    logger.info("[SHORT-SIGNAL] %s: 写入 %d 个短周期信号到 %s", asset, written, path)
    return written


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "603662"
    sigs = analyze_short_term_signals(target)
    print(f"{target}: {len(sigs)} signals")
    for s in sigs:
        print(f"  [{s['direction']}] {s['core_thesis'][:60]}")
