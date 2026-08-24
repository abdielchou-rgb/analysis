# -*- coding: utf-8 -*-
"""R30 全量补齐工程计划测试（预测闭环/目标价/勾稽/预期差/估值锚/对标/基准）

覆盖模块1/2/6/7/8/9 的关键行为。
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── 模块1：预测质量门槛 ────────────────────────────────────────
def test_forward_pick_quality_gate():
    from core.forward_picks import ForwardPicksDB, ForwardPick

    db = ForwardPicksDB()
    # 不合格被拒
    bad = ForwardPick(pick_id="t_bad", direction="neutral", base_target=0,
                      conviction="", asset_code="")
    assert not db.append(bad), "neutral/无目标价/无conviction 应被拒"

    # 合格被接受（R64 完整度：须带 anchor_nav 净值锚点）
    good = ForwardPick(pick_id="t_good", asset_code="603662", asset_name="柯力",
                       direction="bull", base_target=50.0,
                       conviction="high", created_at="2026-08-02", anchor_nav=2.5,
                       report_type="listed_company", verification_status="pending")
    assert db.append(good), "合格预测应被接受"
    # R64：缺 anchor_nav 应被拒（净值锚点是验证收益的基础）
    good_missing_nav = ForwardPick(pick_id="t_good2", asset_code="603662", asset_name="柯力",
                                   direction="bull", base_target=50.0, conviction="high",
                                   created_at="2026-08-02",
                                   report_type="listed_company")
    assert not db.append(good_missing_nav), "缺 anchor_nav 应被拒"
    # 清理
    picks = [p for p in db.load_all() if p.pick_id not in ("t_good", "t_good2")]
    db._rewrite_all(picks)


def test_purge_low_quality():
    from core.forward_picks import ForwardPicksDB
    db = ForwardPicksDB()
    # 手动塞一条垃圾
    from core.forward_picks import ForwardPick
    bad = ForwardPick(pick_id="t_purge", direction="neutral", base_target=0,
                      conviction="", asset_code="X", asset_name="X",
                      created_at="2026-01-01")
    # 直接写（绕过 append 校验，模拟历史数据）
    with open(db.path, "a", newline="", encoding="utf-8-sig") as f:
        import csv
        w = csv.DictWriter(f, fieldnames=db.HEADERS)
        w.writerow(dict(pick_id="t_purge", asset_code="X", asset_name="X",
                        report_type="", created_at="2026-01-01", direction="neutral",
                        base_target="0", bull_target="0", bear_target="0",
                        current_price="0", conviction="", core_thesis="",
                        key_variable="", falsification="", verified_at="",
                        actual_price="", actual_return="", benchmark_return="",
                        alpha="", verification_status="pending", invalidation="",
                        notes=""))
    n = db.purge_low_quality()
    assert n >= 1, "垃圾预测应被清理"


# ── 模块6：三表勾稽 ────────────────────────────────────────────
def test_three_statement_audit():
    from core.three_statement_audit import audit
    r = audit("603662")
    assert r["status"] == "ok", f"审计应执行: {r.get('note')}"
    assert r["total_checks"] > 0, "应有勾稽检查项"
    assert "passed" in r and "failed_checks" in r


# ── 模块7：预期差 ──────────────────────────────────────────────
def test_earnings_surprise():
    from core.earnings_surprise import compute_surprise
    s = compute_surprise("603662")
    # 柯力有一致预期（12家）
    assert s.get("status") == "ok", f"应有数据: {s}"
    assert s.get("consensus_eps") == 1.2, "柯力一致预期 EPS 应为 1.2"


# ── 模块8：估值锚交叉验证 ──────────────────────────────────────
def test_valuation_crosscheck():
    from core.valuation_crosscheck import crosscheck
    # 柯力场景：差异 23%
    cc = crosscheck({"DCF": 54.0, "PE": 44.0, "可比": 48.0})
    assert cc["gap_pct"] > 0.20, "差异>20%应检测"
    assert not cc["passed"], "差异大应标记需声明"
    assert cc["final"] == 48.0, "中值应为 48"

    # 一致场景
    cc2 = crosscheck({"DCF": 48.0, "PE": 46.0})
    assert cc2["passed"], "差异小应通过"


# ── 模块8：隐含 FCF margin ────────────────────────────────────
def test_implied_fcf_margin():
    from core.compute.patterns import estimate_implied_fcf_margin
    rd = estimate_implied_fcf_margin(market_cap=131, revenue=15.58)
    assert rd.data["implied_fcf_margin"] > 0, "应有隐含 FCF margin"
    assert rd.signal in ("bull", "bear", "neutral")


# ── 模块9：基准检验 ────────────────────────────────────────────
def test_benchmark_compare():
    from core.benchmark_compare import compare_vs_benchmark
    b = compare_vs_benchmark()
    assert "hit_rate" in b and "excess" in b


# ── 模块9：对标矩阵 ────────────────────────────────────────────
def test_peer_matrix():
    from core.peer_matrix import build_peer_matrix
    m = build_peer_matrix("603662", "柯力传感", "半导体")
    assert m["status"] == "ok", f"应有对标: {m.get('note')}"
    assert len(m["peers"]) > 0, "应有可比公司"


# ── R32 回归：中文名资产也能触发 R30 模块（Bug A/B 修复验证）─────────
# 真实管线里 orchestrator 把 asset 规范化为中文名（如"柯力传感"），
# 而三个模块内部用 re.search(r"(\d{6})", asset) 提取代码 → 中文名匹配不到
# → 模块静默跳过 → 报告缺估值交叉/勾稽/预期差/对标。本测试锁定该接线。
def test_asset_code_resolve_from_chinese_name():
    """resolve_asset 必须能从中文名解析出 6 位代码（section_writer 依赖此）。"""
    from core.asset_resolver import resolve_asset
    a = resolve_asset("柯力传感")
    assert a.code == "603662", f"中文名应解析出代码: {a.code}"


def test_r30_modules_trigger_with_chinese_asset():
    """用中文名资产触发 R30 模块，验证不是静默空转。"""
    from core.three_statement_audit import audit, audit_to_prompt
    from core.earnings_surprise import compute_surprise, serialize_surprise
    from core.peer_matrix import build_peer_matrix, serialize_matrix

    # 模拟 section_writer 修复后的提取逻辑：先 resolve_asset 拿 code
    from core.asset_resolver import resolve_asset
    asset = "柯力传感"
    _obj = resolve_asset(asset)
    _code = _obj.code or ""
    assert _code, "中文名必须解析出代码"

    # 三表勾稽
    r = audit(_code, asset)
    assert r["status"] == "ok", f"勾稽应执行: {r.get('note')}"
    assert len(audit_to_prompt(r)) > 100, "勾稽 prompt 应有实质内容"

    # 预期差
    s = compute_surprise(_code)
    assert s and s.get("status") == "ok", f"预期差应执行: {s}"
    assert len(serialize_surprise(s)) > 0, "预期差 prompt 应有内容"

    # 对标矩阵
    m = build_peer_matrix(_code, asset, "半导体")
    assert m["status"] == "ok", f"对标应执行: {m.get('note')}"
    assert len(serialize_matrix(m)) > 100, "对标 prompt 应有实质内容"


def test_valuation_crosscheck_compat_real_structure():
    """交叉验证必须兼容 compute_results 的真实结构 {result:{fair_value}}。"""
    from core.valuation_crosscheck import crosscheck, serialize_crosscheck
    # 模拟 compute_engine._run_v51_dcf 返回的真实结构
    _cr = {
        "dcf_valuation": {"status": "ok", "result": {"fair_value": 54.0}},
        "comparable_valuation": {"status": "ok", "result": {"implied_pe_price": 44.0}},
    }
    _vals = {}
    _dcf = _cr.get("dcf_valuation", {}) or {}
    _comp = _cr.get("comparable_valuation", {}) or {}
    _dcf_val = _dcf.get("target_price")
    if not _dcf_val and isinstance(_dcf.get("result"), dict):
        _dcf_val = _dcf["result"].get("fair_value")
    if _dcf_val:
        _vals["DCF"] = float(_dcf_val)
    _comp_val = _comp.get("target_price")
    if not _comp_val and isinstance(_comp.get("result"), dict):
        _comp_val = _comp["result"].get("implied_pe_price")
    if _comp_val:
        _vals["可比"] = float(_comp_val)
    assert "DCF" in _vals, "应从 result.fair_value 提取 DCF 锚"
    assert "可比" in _vals, "应从 result.implied_pe_price 提取可比锚"
    cc = crosscheck(_vals)
    assert cc["gap_pct"] > 0.20, "54 vs 44 应标记差异"
    assert not cc["passed"], "差异大应标记需声明"
    assert len(serialize_crosscheck(cc)) > 50, "交叉验证 prompt 应有实质内容"


def test_dimension_parallel_signature_receives_calib():
    """R32-D：_write_dimension_parallel 必须接收 calib_str/plan_str。

    此前的 NameError（calib_str 未定义）导致维度并行每次静默回退普通写，
    R30 模块注入从未真正生效。本测试锁定方法签名。
    """
    import inspect
    from pipeline.section_writer import SectionWriter
    sig = inspect.signature(SectionWriter._write_dimension_parallel)
    params = list(sig.parameters.keys())
    assert "calib_str" in params, "维度并行必须接收 calib_str"
    assert "plan_str" in params, "维度并行必须接收 plan_str"


def test_dimension_parallel_writes_r30_prompts():
    """R32-D：维度并行路径下，R30 模块 prompt 真正注入 LLM。"""
    import os
    import core.deepseek_client as dsc
    from pipeline.section_writer import SectionWriter
    import pipeline.section_writer as _sw

    captured = []
    _orig_dsc = dsc.call_deepseek
    # section_writer 顶层 `from core.deepseek_client import call_deepseek`
    # 持有的是引用副本，必须 mock 模块内名字才能拦截。
    _orig_sw = _sw.call_deepseek

    def _spy(messages, **kw):
        captured.append(messages)
        return {'choices': [{'message': {'role': 'assistant',
                                         'content': '# 报告\n' + '测试内容足够长。' * 30}}]}

    dsc.call_deepseek = _spy
    _sw.call_deepseek = _spy
    try:
        sw = SectionWriter('listed_company', 'cicc')
        data_ctx = {'chart_data': {'fig_revenue_trend': {'2024': 12.95, '2025': 15.58},
                                   'fig_profitability': {'2024': 2.61, '2025': 3.41},
                                   'fig_valuation': {'price': 46.73, 'eps': 0.586}},
                    'compute_results': {}}
        # 复现 write() 的前置准备（比调完整 write() 快得多）
        sw._chart_paths = {}
        sw._last_data_context = data_ctx
        sw._asset_code = "603662"  # write() 中由 resolve_asset 设置
        sw._data_bundle = sw._build_data_bundle(data_ctx)
        data_str = sw._serialize_data(data_ctx)
        chart_md = sw._build_chart_md('柯力传感')
        from core.data_dict import build_data_dict, serialize_data_dict
        sw._data_dict = build_data_dict(data_ctx)
        _dd_str = serialize_data_dict(sw._data_dict)
        from core.data_caliber import build_caliber_meta, serialize_caliber_annotations
        calib_str = serialize_caliber_annotations(build_caliber_meta(sw._data_dict))
        from core.report_planner import build_report_plan, serialize_plan
        plan_str = serialize_plan(build_report_plan('listed_company'))
        out = sw._write_dimension_parallel(
            '柯力传感', data_str, chart_md, _dd_str, '', '', '', '', None,
            'deepseek', calib_str, plan_str)
        assert out and len(out) > 100, "维度并行应产出报告"
        all_text = ' '.join(m[-1]['content'] for m in captured if m and m[-1].get('content'))
        # R30 模块必须出现在注入 prompt 中（标题带章节提示后缀，用宽松关键词）
        assert '三表勾稽验证' in all_text or '三表勾稽' in all_text, "三表勾稽应注入"
        assert '预期差信号' in all_text or '预期差' in all_text, "预期差应注入"
        assert '对标矩阵' in all_text, "对标矩阵应注入"
        assert '估值锚交叉验证' in all_text or '估值锚' in all_text, "估值交叉验证应注入"
    finally:
        dsc.call_deepseek = _orig_dsc
        _sw.call_deepseek = _orig_sw


# ── R38 回归：预测模型字段兼容 + 异常尾部剔除 ────────────────
def test_predict_model_flat_margin_keys():
    """R38：扁平键 margin_2025 形态应被预测模型读取（不再兜底 5%）。"""
    from core.compute.predict_model import build_forecast
    cd = {
        "fig_revenue_trend": {"2023": 12.95, "2024": 10.72, "2025": 15.58},
        "fig_profitability": {"2023": 3.12, "2024": 2.61, "2025": 3.41},
        "margin_2023": 43.05, "margin_2024": 43.12, "margin_2025": 44.83,
        "fig_valuation": {"price": 46.73, "market_cap": 131.23},
    }
    fc = build_forecast({"chart_data": cd}, "listed_company")
    assert fc, "预测应产出"
    # 毛利率应为 44.83 附近，而非兜底 5.0%
    f_26 = fc["forecast"].get("2026E", {})
    assert f_26.get("gross_margin", 0) > 30, f"毛利率应≈44.8而非兜底: {f_26.get('gross_margin')}"
    # EPS 应为合理值（净利/股本=净利/2.81），不是天文数字
    assert 0 < f_26.get("eps", 0) < 10, f"EPS应合理: {f_26.get('eps')}"


def test_predict_model_anomalous_tail_year():
    """R38：异常尾部年份（单季误入全年）应被剔除，base_year 落在完整年份。"""
    from core.compute.predict_model import build_forecast
    cd = {
        "fig_revenue_trend": {"2023": 12.95, "2024": 10.72, "2025": 15.58, "2026": 3.58},
        "fig_profitability": {"2023": 3.12, "2024": 2.61, "2025": 3.41, "2026": 0.41},
        "margin_2023": 43.05, "margin_2024": 43.12, "margin_2025": 44.83,
        "fig_valuation": {"price": 46.73, "market_cap": 131.23},
    }
    fc = build_forecast({"chart_data": cd}, "listed_company")
    assert fc, "预测应产出"
    assert fc["base_year"] == 2025, f"base_year 应为 2025（剔除异常2026）: {fc['base_year']}"
    # 2026E 营收应在 15.58 基础上合理增长，而非 3.58 的继续
    f_26 = fc["forecast"].get("2026E", {})
    assert f_26.get("revenue", 0) > 10, f"2026E营收应>10（基于15.58外推）: {f_26.get('revenue')}"


# ── R39 回归：统一财务数据提取层（数据契约）──────────────
def test_financial_extract_both_forms():
    """R39：统一提取层兼容 fig_* 字典和扁平键两种形态。"""
    from core.financial_extract import extract_financial_history

    # 扁平键形态（data_dict 缓存）
    flat = {
        "revenue_trend_2023": 10.72, "revenue_trend_2025": 15.58,
        "profitability_2023": 3.12, "profitability_2025": 3.41,
        "margin_2023": 43.05, "margin_2025": 44.83,
    }
    h1 = extract_financial_history(flat)
    assert h1.get("2025", {}).get("revenue") == 15.58, "扁平键营收应提取"
    assert abs(h1.get("2025", {}).get("gross_margin", 0) - 44.83) < 0.1, "扁平键毛利率应提取"

    # fig_* 字典形态（管线实时）
    fig = {"chart_data": {"fig_revenue_trend": {"2025": 15.58},
                          "fig_profitability": {"2025": 3.41},
                          "fig_margin": {"2025": 44.83}}}
    h2 = extract_financial_history(fig)
    assert h2.get("2025", {}).get("revenue") == 15.58, "fig_* 营收应提取"
    assert abs(h2.get("2025", {}).get("gross_margin", 0) - 44.83) < 0.1, "fig_* 毛利率应提取"


def test_financial_extract_shares_from_mcap():
    """R39：股本从市值/价格反推（亿元/元=亿股）。"""
    from core.financial_extract import extract_shares
    shares = extract_shares({"fig_valuation": {"price": 46.73, "market_cap": 131.23}})
    assert abs(shares - 2.81) < 0.1, f"股本应从市值/价格反推: {shares}"


if __name__ == "__main__":
    import traceback
    passed = 0
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
