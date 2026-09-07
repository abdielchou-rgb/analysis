"""
Engine Bridge 集成测试 — engine/ 16-step 管线接入生产 compute。
用真实 akshare 数据形态（中文字符串单位）验证端到端。
"""

import pytest

# 真实茅台形态数据（akshare 返回的中文字符串单位）
MOUTAI_LIKE = {
    "asset": "600519 贵州茅台",
    "report_type": "listed_company",
    "chart_data": {
        "fig_revenue_trend": {
            "2021": {
                "revenue": "1094.64亿",
                "net_profit": "524.60亿",
                "gross_margin": "91.54%",
                "roe": "29.90%",
                "eps": "41.76",
                "asset_liability_ratio": "26.31%",
            },
            "2022": {
                "revenue": "1275.55亿",
                "net_profit": "627.16亿",
                "gross_margin": "91.87%",
                "roe": "30.26%",
                "eps": "49.93",
                "asset_liability_ratio": "25.28%",
            },
            "2023": {
                "revenue": "1505.60亿",
                "net_profit": "747.34亿",
                "gross_margin": "91.96%",
                "roe": "34.19%",
                "eps": "59.49",
                "asset_liability_ratio": "21.36%",
            },
            "2024": {
                "revenue": "1741.44亿",
                "net_profit": "862.28亿",
                "gross_margin": "91.93%",
                "roe": "36.24%",
                "eps": "68.64",
                "asset_liability_ratio": "18.71%",
            },
        },
        "fig_valuation": {
            "price": 1500.0,
            "market_cap": 18800,
            "pe": 22.0,
            "source": "akshare",
        },
        "fig_profitability": {},
    },
}

# 缺数据形态
THIN_DATA = {
    "asset": "000000",
    "chart_data": {"fig_revenue_trend": {"2024": 100.0}},  # 只有 1 年
}


class TestExtractEngineParams:
    def test_extract_moutai_like(self):
        from pipeline.engine_bridge import extract_engine_params

        p = extract_engine_params(MOUTAI_LIKE)
        assert p is not None
        # 收入单位: 元
        assert p["base_revenue"] == pytest.approx(1741.44e8, rel=1e-6)
        # 5 年增长率（3 个历史增长率 + padding）
        assert len(p["revenue_growth_rates"]) == 5
        # 股本 = 净利/EPS = 862.28e8/68.64 ≈ 12.56e8 股
        assert p["shares_outstanding"] == pytest.approx(862.28e8 / 68.64, rel=1e-4)
        # EBIT margin = 净利率/(1-tax)，受毛利率上限约束
        assert 0.02 <= p["base_ebit_margin"] <= 0.60
        # WACC 来自 ERP 模块 (0.07~0.13 区间)
        assert 0.05 < p["wacc"] < 0.15
        assert p["current_price"] == 1500.0

    def test_growth_rates_from_history(self):
        from pipeline.engine_bridge import extract_engine_params

        p = extract_engine_params(MOUTAI_LIKE)
        g = p["revenue_growth_rates"]
        # 2022 增长率 ≈ 16.5%，2023 ≈ 18.0%，2024 ≈ 15.7%
        assert g[0] == pytest.approx(1275.55 / 1094.64 - 1, rel=1e-3)
        assert g[2] == pytest.approx(1741.44 / 1505.60 - 1, rel=1e-3)

    def test_thin_data_returns_none(self):
        from pipeline.engine_bridge import extract_engine_params

        assert extract_engine_params(THIN_DATA) is None

    def test_repo_fallback_extracts_moutai_params(self):
        """2026-09-07 断点2：当次采集缺 fig_revenue_trend 时，用 repo segment_revenue
        + consensus_prices 兜底（茅台 1687.7亿营收 + EPS），engine 参数应能提取。"""
        from pipeline.engine_bridge import extract_engine_params

        # 模拟当次采集只有 fig_valuation（净利/EPS/价），无营收序列
        fd = {
            "asset": "600519 贵州茅台",
            "chart_data": {
                "fig_valuation": {"net_profit": 862.28e8, "eps": 68.64, "price": 1500.0},
            },
        }
        p = extract_engine_params(fd)
        assert p is not None, "repo 兜底应能提取参数"
        # segment_revenue 茅台 2025 ≈ 1688 亿（兜底营收）
        assert p["base_revenue"] > 1500e8, f"营收应来自 repo segment_revenue: {p['base_revenue']}"
        # 股本 = 862.28e8 / 68.64
        assert p["shares_outstanding"] == pytest.approx(862.28e8 / 68.64, rel=0.15)

    def test_repo_fallback_thin_asset_still_none(self):
        """无 repo 覆盖的标的（000000）即便有部分数据，缺营收仍返回 None。"""
        from pipeline.engine_bridge import extract_engine_params

        fd = {"asset": "000000", "chart_data": {"fig_valuation": {"net_profit": 1e8, "eps": 1.0}}}
        assert extract_engine_params(fd) is None

    def test_net_debt_from_alr_roe(self):
        from pipeline.engine_bridge import extract_engine_params

        p = extract_engine_params(MOUTAI_LIKE)
        # 茅台低负债，net_debt 应很小但 >= 0
        assert p["net_debt"] >= 0
        # equity = 862.28/0.3624 ≈ 2378亿; debt = 2378*0.1871/0.8129 ≈ 547亿; net ≈ 438亿
        assert p["net_debt"] == pytest.approx(547e8 * 0.8, rel=0.2)


class TestRunEngineIB:
    def test_full_bridge_run(self):
        from pipeline.engine_bridge import run_engine_ib

        r = run_engine_ib(MOUTAI_LIKE)
        assert r["status"] == "ok", r.get("reason", r.get("error"))
        res = r["result"]

        # 16 步核心输出
        assert res["fair_value"] and res["fair_value"] > 0
        assert 0 < res["tv_pct"] < 1
        assert res["enterprise_value"] > 0
        assert res["scenario_weighted_target"] > 0
        assert res["mc_median"] > 0
        assert len(res["sensitivity_matrix"]) == 5
        assert res["upside_pct"] is not None

        # 期望分析
        exp = res["expectations"]
        assert exp["implied_growth"] >= -0.05
        assert exp["ev_to_fcf"] > 0

        # 步骤完整性
        assert "09_dcf" in res["steps_completed"]
        assert "10_scenarios" in res["steps_completed"]
        assert "11_monte_carlo" in res["steps_completed"]
        assert "13_tornado" in res["steps_completed"]

    def test_thin_data_skips(self):
        from pipeline.engine_bridge import run_engine_ib

        r = run_engine_ib(THIN_DATA)
        assert r["status"] == "skip"
        # 2026-09-07 诊断化：reason 从 "insufficient data" 改为中文诊断（缺营收/估值键）
        assert "参数不足" in r["reason"] or "insufficient" in r["reason"]

    def test_fair_value_sane_vs_price(self):
        """DCF fair_value 不应偏离现价 100 倍（数量级检查）"""
        from pipeline.engine_bridge import run_engine_ib

        r = run_engine_ib(MOUTAI_LIKE)
        if r["status"] == "ok":
            fv = r["result"]["fair_value"]
            price = MOUTAI_LIKE["chart_data"]["fig_valuation"]["price"]
            assert 0.05 < fv / price < 20

    def test_repo_fallback_full_chain_computes(self):
        """2026-09-07 断点2+3 完整链路：采集缺营收序列但 repo segment_revenue +
        consensus EPS + 现价齐备时，engine_ib 应算出 fair_value + 隐含增长。

        这是"引擎顶级方法论真正进报告"的最小闭环验证（茅台真实财务形态）。
        """
        from pipeline.engine_bridge import run_engine_ib

        fd = {
            "asset": "贵州茅台",
            "stock_name": "贵州茅台",
            "chart_data": {
                "fig_valuation": {"net_profit": "862.28亿", "eps": "68.64", "price": 1500.0},
            },
        }
        r = run_engine_ib(fd)
        assert r["status"] == "ok", f"repo 兜底应能完成 DCF: {r.get('reason')}"
        fv = r["result"]["fair_value"]
        # 茅台现价 ~1500，DCF 值应在合理区间
        assert 500 < fv < 2500, f"fair_value 超出合理区间: {fv}"
        # 期望分析含隐含增长
        exp = r["result"].get("expectations", {})
        assert "implied_growth" in exp
        assert "09_dcf" in r["result"].get("steps_completed", [])


class TestComputeEngineIntegration:
    def test_compute_engine_calls_bridge(self):
        """生产 ComputeEngine.compute 应产出 engine_ib 键"""
        from pipeline.compute_engine import ComputeEngine

        r = ComputeEngine().compute(MOUTAI_LIKE, report_type="listed_company")
        assert "engine_ib" in r
        assert r["engine_ib"]["status"] in ("ok", "skip", "error")
        if r["engine_ib"]["status"] == "ok":
            # engine-IB ok 时应为 primary_target_price 首选
            assert r.get("primary_target_source") == "Engine-IB"
            assert r.get("primary_target_price") == r["engine_ib"]["result"]["fair_value"]


class TestIronGateV2Precheck:
    def test_l1_blocks_extreme_wacc(self):
        """WACC <= g 时 L1 应拦截"""
        from pipeline.engine_bridge import extract_engine_params

        p = extract_engine_params(MOUTAI_LIKE)
        if p:
            p["wacc"] = 0.02  # < terminal_growth 0.025
            from engine.irongate_v2 import IronGateV2

            gate = IronGateV2()
            report = gate.validate(p)
            assert report.blocked
