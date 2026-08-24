# -*- coding: utf-8 -*-
"""2hao 数据兜底桥接层测试 — pipeline/data_enrichment.py

覆盖：充足性判定 / LocalBackfill 不崩溃 / AgentEnricher merge 与合规拒绝 /
gap manifest 写入 / data_check_only 快速检查。

可独立运行：python tests/test_data_enrichment.py
也可被 tests/run_all.py 调用：run() 返回 (n_pass, n_fail)
"""

from __future__ import annotations
import sys, os, json, tempfile, time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def run(report=None) -> tuple:
    """执行全部测试。report 可选回调 (name, ok, detail)。返回 (n_pass, n_fail)。"""
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

    from pipeline.data_enrichment import (
        DataSufficiencyChecker, AgentEnricher, LocalBackfill,
        _write_gap_manifest, make_enrich_template,
    )

    # ── 1. 充足性判定 ─────────────────────────────────────
    empty = DataSufficiencyChecker.check({})
    t("sufficiency empty -> insufficient", not empty["sufficient"])
    t("sufficiency empty has missing", len(empty["missing"]) > 0)

    full = {"chart_data": {
        "fig_revenue_trend": {"2023": 90, "2024": 100},
        "fig_profitability": {"2023": 18, "2024": 20},
        "fig_margin": {"2023": 28, "2024": 30},
        "fig_qlib_price": {"2023": 9, "2024": 10},
        "company_intro": "简介",
    }, "akshare_financials": [{"x": 1}]}
    ok_full = DataSufficiencyChecker.check(full)
    t("sufficiency full -> sufficient", ok_full["sufficient"])
    t("sufficiency full score 1.0", ok_full["score"] == 1.0)

    half = {"chart_data": {"company_intro": "简介"}}
    ok_half = DataSufficiencyChecker.check(half)
    t("sufficiency half -> insufficient", not ok_half["sufficient"])
    t("sufficiency half lists fig_revenue_trend",
      "fig_revenue_trend" in ok_half["missing"])

    # 核心财务齐备 → sufficient（辅助缺失只记 partial）
    core_only = {"chart_data": {
        "fig_revenue_trend": {"2022": 0.9, "2023": 1}, "fig_profitability": {"2022": 0.18, "2023": 0.2},
    }}
    ok_core = DataSufficiencyChecker.check(core_only)
    t("sufficiency core-only -> sufficient", ok_core["sufficient"])
    t("sufficiency core-only has partial", len(ok_core["partial_missing"]) > 0)

    # ── 2. AgentEnricher merge ────────────────────────────
    good = {
        "asset": "测试",
        "generated_by": "agent",
        "items": [
            {"type": "fig_data", "key": "fig_revenue_trend",
             "data": {"2023": 50, "2024": 60}, "source": "公司公告2026-03",
             "confidence": 0.9, "unit": "亿元"},
            {"type": "news", "items": ["新闻A", "新闻B"],
             "source": "WebSearch: 测试 2026"},
            {"type": "text", "key": "company_intro", "value": "主营测试业务",
             "source": "官网"},
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump(good, f, ensure_ascii=False); gf = f.name
    try:
        data = AgentEnricher.merge("测试", {"chart_data": {}}, gf)
        cd = data["chart_data"]
        t("enrich fig merged", "fig_revenue_trend" in cd)
        t("enrich fig value", cd["fig_revenue_trend"]["2024"] == 60)
        t("enrich news merged", cd.get("agent_news") == ["新闻A", "新闻B"])
        t("enrich text merged", cd.get("company_intro") == "主营测试业务")
        t("enrich accepted_count=3", data["enrichment"]["accepted_count"] == 3)
        t("enrich source_registry len", len(data["enrichment"]["source_registry"]) == 3)
    finally:
        os.unlink(gf)

    # ── 3. 合规拒绝 ───────────────────────────────────────
    bad = {
        "asset": "测试",
        "items": [
            {"type": "fig_data", "key": "fig_profitability",
             "data": {"2024": 99}, "source": ""},                 # 缺来源
            {"type": "fig_data", "key": "fig_UNKNOWN_KEY",
             "data": {"2024": 1}, "source": "某来源"},            # 白名单外
            {"type": "weird_type", "key": "x", "value": "y",
             "source": "某来源"},                                  # 未知类型
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        json.dump(bad, f, ensure_ascii=False); bf = f.name
    try:
        data2 = AgentEnricher.merge("测试", {"chart_data": {}}, bf)
        t("enrich rejects all 3", data2["enrichment"]["rejected_count"] == 3)
        t("enrich accept 0", data2["enrichment"]["accepted_count"] == 0)
    finally:
        os.unlink(bf)

    # enrich-file 不存在 → 不崩溃
    data3 = AgentEnricher.merge("测试", {"chart_data": {}}, "/nonexistent.json")
    t("enrich missing file no-crash", data3 == {"chart_data": {}})

    # ── 4. LocalBackfill 不崩溃 ───────────────────────────
    data4 = LocalBackfill.run("600519", {"chart_data": {}})
    t("local backfill returns dict", isinstance(data4, dict))
    t("local backfill chart_data dict", isinstance(data4.get("chart_data"), dict))
    t("local backfill no-crash", True)

    # ── 5. gap manifest ───────────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        ctx = {"output_dir": td, "collected_data": {"chart_data": {}},
               "asset": "测试600000"}
        check = {"sufficient": False,
                 "missing": ["fig_revenue_trend", "fig_profitability"],
                 "partial_missing": ["行情"], "detail": "test"}
        p = _write_gap_manifest("测试600000", ctx, check)
        t("gap manifest written", Path(p).exists())
        m = json.loads(Path(p).read_text(encoding="utf-8"))
        t("gap manifest missing_core",
          m["missing_core"] == ["fig_revenue_trend", "fig_profitability"])
        t("gap manifest next_steps", "next_steps" in m and len(m["next_steps"]) >= 1)
        t("gap manifest needs_agent", m["needs_agent"] is True)

    # ── 6. enrich 模板 ────────────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        tpl = make_enrich_template("测试", str(Path(td) / "e.json"))
        tpl_data = json.loads(Path(tpl).read_text(encoding="utf-8"))
        t("template has items", isinstance(tpl_data.get("items"), list))

    print(f"[test_data_enrichment] {n_pass} passed, {n_fail} failed")
    return n_pass, n_fail


if __name__ == "__main__":
    np_, nf_ = run()
    sys.exit(1 if nf_ > 0 else 0)
