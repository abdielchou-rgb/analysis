"""R83 内容层：决策推理引擎（decision_engine）回归测试

守护"困境→卡位→放量→延伸→投入/损失"决策链的确定性计算。
油位 v0.89 事故根因是"有结构无推理"——本测试确保决策备忘录
产出的是真实战略判断（评分/结论/金额），而非章节罗列。

可独立运行：python tests/test_r83_decision_engine.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_enrich_data() -> dict:
    """读取 enrich 数据 → 构造 chart_data dict。

    P1-audit 2026-08-24：v086 样本已被 v087_corrected 取代，
    按存在性回退；两者皆缺时抛 FileNotFoundError 由上层跳过。
    """
    for name in ("keli_oil_enrich_v087_corrected.json", "keli_oil_enrich_v086.json"):
        p = _ROOT / "data" / name
        if p.exists():
            payload = json.loads(p.read_text(encoding="utf-8"))
            break
    else:
        raise FileNotFoundError("no keli_oil_enrich_*.json fixture in data/")
    cd = {}
    for it in payload.get("items", []):
        if it.get("type") == "fig_data":
            cd[it["key"]] = it.get("data")
        elif it.get("type") == "text":
            cd[it["key"]] = it.get("value")
    return {"chart_data": cd}


def run(report=None) -> tuple:
    n_pass, n_fail = 0, 0

    def t(name, ok, detail=""):
        nonlocal n_pass, n_fail
        if ok:
            n_pass += 1
        else:
            n_fail += 1
            msg = f"  FAIL: {name} {detail}"
            print(msg)
            if report:
                report(name, ok, detail)

    from core.decision_engine import (
        DecisionEngine,
    )

    data = _load_enrich_data()
    result = DecisionEngine().analyze(data)

    # ── 1. 主入口产出完整决策链 ─────────────────────
    for key in ("decision", "dilemma", "positioning", "rampup", "adjacent", "investment"):
        t(
            f"engine has {key}",
            key in result and result[key].get("status") == "ok",
            f"status={result.get(key, {}).get('status')}",
        )

    # ── 2. 决策结论 ────────────────────────────────
    dec = result.get("decision", {})
    t(
        "decision verdict is 值得/条件/不建议",
        dec.get("verdict", "") in ("值得战略卡位", "条件性卡位", "不建议卡位"),
        str(dec.get("verdict")),
    )
    t("decision has 卡位评分", "卡位评分" in dec)
    t("decision has 执行前提(订单≥5000)", "5000" in str(dec.get("执行前提", "")))

    # ── 3. 卡位评分确定性计算 ──────────────────────
    pos = result.get("positioning", {})
    t("positioning score in 0-5", 0 <= pos.get("score", 0) <= 5.0, f"score={pos.get('score')}")
    t(
        "positioning verdict matches score",
        (pos.get("score", 0) >= 3.5 and pos.get("verdict") == "值得战略卡位")
        or (2.5 <= pos.get("score", 0) < 3.5 and pos.get("verdict") == "条件性卡位")
        or (pos.get("score", 0) < 2.5 and pos.get("verdict") == "不建议卡位"),
        f"score={pos.get('score')} verdict={pos.get('verdict')}",
    )
    t("positioning has 计算过程", "计算过程" in pos and "×" in pos.get("计算过程", ""))

    # ── 4. 困境诊断 ───────────────────────────────
    dil = result.get("dilemma", {})
    t("dilemma has struggles", len(dil.get("struggles", [])) >= 1)
    t("dilemma has strengths", len(dil.get("strengths", [])) >= 1)
    t("dilemma strengths include 盈利质量", any("盈利质量" in s.get("维度", "") for s in dil.get("strengths", [])))

    # ── 5. 放量路径 ───────────────────────────────
    ramp = result.get("rampup", {})
    t("rampup verdict mentions 订单", "订单" in str(ramp.get("verdict", "")) or "放量" in str(ramp.get("verdict", "")))
    t("rampup has 3 waves", len(ramp.get("waves", [])) == 3)
    t(
        "rampup key_variables include 久通订单",
        any("久通" in kv.get("变量", "") for kv in ramp.get("key_variables", [])),
    )

    # ── 6. 延伸产业 ───────────────────────────────
    adj = result.get("adjacent", {})
    t("adjacent verdict mentions 物位", "物位" in str(adj.get("verdict", "")))
    t(
        "adjacent upstream mentions TDK",
        "TDK" in str(adj.get("upstream", {}).get("卡脖子", "")) or "TDK" in str(adj.get("upstream", {})),
    )

    # ── 7. 投入/最坏损失（金额锚定，R87口径）────────────────
    inv = result.get("investment", {})
    worst = inv.get("worst_loss", {})
    t("worst_loss has 最大损失金额", "万" in str(worst.get("最大损失", "")))
    t("worst_loss 对标净利", "净利" in str(worst.get("对标", "")) or "归母" in str(worst.get("对标", "")))
    t("investment 运营投入上限", "万" in str(inv.get("investment", {}).get("运营投入上限(三年)", "")))

    # ── 8. 数据不足时诚实降级（不崩溃）────────────
    empty_result = DecisionEngine().analyze({"chart_data": {}})
    t("empty data doesn't crash", isinstance(empty_result, dict))
    t(
        "empty data verdict 待评估/数据不足",
        empty_result.get("decision", {}).get("verdict", "")
        in ("待评估", "不建议卡位", "条件性卡位", "待评估（数据不足）"),
        f"verdict={empty_result.get('decision', {}).get('verdict')}",
    )
    t(
        "empty data positioning status=no_data",
        empty_result.get("positioning", {}).get("status") == "no_data",
        f"status={empty_result.get('positioning', {}).get('status')}",
    )

    # ── 9. 接入 compute tool_modules ──────────────
    try:
        from pipeline.compute_engine import ComputeEngine

        ce = ComputeEngine()
        cr = ce.compute(data, report_type="decision_memo")
        tm = cr.get("tool_modules", {}).get("modules", {})
        _dmod = tm.get("decision", {})
        _inner = _dmod.get("decision", {}) if isinstance(_dmod, dict) else {}
        t("compute injects decision module", "decision" in tm, f"decision keys={list(_dmod.keys())}")
        t(
            "compute decision inner verdict present",
            "verdict" in _inner and _inner.get("verdict") == "值得战略卡位",
            f"verdict={_inner.get('verdict')}",
        )
    except Exception as e:
        t("compute injects decision module", False, f"异常: {str(e)[:80]}")

    return n_pass, n_fail


if __name__ == "__main__":
    p, f = run()
    print(f"\nR83 决策推理引擎回归测试: {p} passed, {f} failed")
    sys.exit(1 if f else 0)


# ── P1-audit 2026-08-24 收编：原 run() 只 print 不 raise，pytest 看不见 ──
def test_orphan_suite():
    try:
        _p, _f = run()
    except FileNotFoundError as e:
        import pytest

        pytest.skip(f"fixture 缺失: {e}")
    assert _f == 0, f"{_f} 个断言失败 / 共 {_p + _f} 条"
