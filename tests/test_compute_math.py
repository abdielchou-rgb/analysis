# -*- coding: utf-8 -*-
"""P1-3 (2026-09-01): 计算引擎数学正确性测试。

run_dcf / run_comparable / run_scenario 是全仓最值钱的纯数值资产，
此前只有调用链测试、无数学正确性独立测试。本文件用手算验证核心公式。

关键公式（对照 core/compute/compute.py 实现）：
- DCF 两阶段：PV = Σ FCF_t/(1+wacc)^t；终值 = FCF_10*(1+g)/(wacc-g)，折现 10 年
- 可比：implied = eps * mean(peer_pe)
- 情景：weighted = bull*p_bull + base*p_base + bear*p_bear
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.compute.compute import DCFInput, run_comparable, run_dcf, run_scenario


class TestDCF:
    def test_simple_dcf_hand_computed(self):
        """手算验证：FCF=100, g1=10%, g2=5%, g_term=3%, wacc=10%。

        注意实现为两阶段 10 年：
        Stage1 (y1-5) 按 g1=10%：FCF_t = 100*1.1^t
          y1: 110/1.1 = 100.0
          y2: 121/1.21 = 100.0
          y3: 133.1/1.331 = 100.0
          y4: 146.41/1.4641 = 100.0
          y5: 161.051/1.61051 = 100.0 → Σ1 = 500
        Stage2 (y6-10) 按 g2=5%：
          FCF_6 = 161.051*1.05 = 169.10, PV = 169.10/1.1^6 = 95.45
          FCF_7 = 177.56, PV = 177.56/1.1^7 = 91.11
          FCF_8 = 186.44, PV = 86.99
          FCF_9 = 195.76, PV = 83.06
          FCF_10 = 205.55, PV = 79.26 → Σ2 = 435.87
        Σ = 935.87（实现输出 935.81，round 误差内）
        """
        r = run_dcf(DCFInput(free_cash_flow=100.0, growth_years_1_5=0.10, wacc=0.10))
        assert r.present_value_fcf == pytest.approx(935.8, abs=1.0)

    def test_terminal_value_gordon(self):
        """终值 = FCF_10*(1+g)/(wacc-g) 折现。

        由上面得 FCF_5 = 161.051（1-5 年按 10% 增长）。
        Stage2 (y6-10) 按 5%：FCF_10 = 161.051 * 1.05^5 = 205.54
        终值 = 205.54*1.03/(0.10-0.03) = 3025.3
        PV_终端 = 3025.3 / 1.1^10 = 3025.3/2.5937 = 1166.4
        """
        r = run_dcf(
            DCFInput(
                free_cash_flow=100.0, growth_years_1_5=0.10, growth_years_6_10=0.05, terminal_growth=0.03, wacc=0.10
            )
        )
        # 用精确递推手算验证范围
        fcf5 = 100 * 1.1**5  # 161.051
        fcf10 = fcf5 * 1.05**5  # 205.54
        tv = fcf10 * 1.03 / (0.10 - 0.03)
        pv_tv = tv / (1.1**10)
        assert r.present_value_terminal == pytest.approx(pv_tv, rel=0.01)

    def test_enterprise_equity_value(self):
        """EV = PV_FCF + PV_TV；Equity = EV - net_debt；每股 = Equity/shares。"""
        r = run_dcf(DCFInput(free_cash_flow=100.0, wacc=0.10, net_debt=50.0, shares_outstanding=10.0))
        ev = r.present_value_fcf + r.present_value_terminal
        assert r.enterprise_value == pytest.approx(ev, abs=0.1)
        assert r.equity_value == pytest.approx(ev - 50.0, abs=0.1)
        assert r.fair_value_per_share == pytest.approx((ev - 50.0) / 10.0, abs=0.1)

    def test_upside_pct(self):
        """Upside = (FV - price)/price * 100。"""
        r = run_dcf(DCFInput(free_cash_flow=100.0, wacc=0.10, shares_outstanding=10.0), current_price=8.0)
        fv = r.fair_value_per_share
        assert r.upside_pct == pytest.approx((fv - 8.0) / 8.0 * 100, abs=0.1)

    def test_zero_fcf_no_crash(self):
        """FCF=0 不崩溃，返回空结果。"""
        r = run_dcf(DCFInput())
        assert r.present_value_fcf == 0.0
        assert r.fair_value_per_share == 0.0

    def test_sensitivity_table_values(self):
        """敏感性表：每格 = 对应 wacc/tg 下的每股价值，跳过 wacc<=tg。"""
        r = run_dcf(DCFInput(free_cash_flow=100.0, wacc=0.10, terminal_growth=0.03, shares_outstanding=10.0))
        assert len(r.sensitivity_table) == 9  # 3x3 全有效
        for cell in r.sensitivity_table:
            assert cell["wacc"] > cell["terminal_growth"]
            assert cell["fair_value"] > 0
        # 低 wacc 高价值：wacc=9% 的 FV 应高于 wacc=11%
        low = next(c for c in r.sensitivity_table if c["wacc"] == 9.0 and c["terminal_growth"] == 2.5)
        high = next(c for c in r.sensitivity_table if c["wacc"] == 11.0 and c["terminal_growth"] == 2.5)
        assert low["fair_value"] > high["fair_value"]

    def test_implied_pe(self):
        """Implied PE = FV / eps。"""
        r = run_dcf(DCFInput(free_cash_flow=100.0, wacc=0.10, shares_outstanding=10.0), current_eps=1.0)
        fv = r.fair_value_per_share
        assert r.implied_pe == pytest.approx(fv / 1.0, abs=0.1)


class TestComparable:
    def test_pe_implied_price(self):
        """Implied price = eps * mean(pe)。PE=[10,20,30] → mean=20, eps=2 → 40。"""
        r = run_comparable(company_eps=2.0, company_bvps=5.0, peer_pe_list=[10, 20, 30])
        assert r.target_pe == 20.0
        assert r.implied_pe_price == pytest.approx(40.0, abs=0.01)

    def test_median_pe(self):
        """median 应取排序中间值。"""
        r = run_comparable(company_eps=1.0, company_bvps=1.0, peer_pe_list=[100, 10, 50, 20, 30])
        assert r.peers[0]["median"] == 30  # 排序 [10,20,30,50,100] 中间

    def test_pb_implied_price(self):
        r = run_comparable(company_eps=0.0, company_bvps=10.0, peer_pb_list=[1, 2, 3])
        assert r.implied_pb_price == pytest.approx(20.0, abs=0.01)

    def test_insufficient_peers_graceful(self):
        """<2 个 peers 时不崩溃、无数据。"""
        r = run_comparable(company_eps=1.0, company_bvps=1.0, peer_pe_list=[10])
        assert r.implied_pe_price == 0.0
        assert "数据不足" in r.summary

    def test_zero_eps_no_division(self):
        """eps=0 不除零。"""
        r = run_comparable(company_eps=0.0, company_bvps=1.0, peer_pe_list=[10, 20])
        assert r.implied_pe_price == 0.0

    def test_empty_peers(self):
        r = run_comparable(company_eps=1.0, company_bvps=1.0)
        assert r.implied_pe_price == 0.0
        assert r.implied_pb_price == 0.0


class TestScenario:
    def test_weighted_target(self):
        """weighted = bull*pb + base*pbase + bear*pbear。"""
        r = run_scenario(current_price=10.0, dcf_value=20.0, comparable_value=10.0)
        base = 15.0  # (20+10)/2
        bull = 15.0 * 1.2  # 18
        bear = 15.0 * 0.8  # 12
        expected = bull * 0.25 + base * 0.50 + bear * 0.25  # = 15
        assert r.weighted_target == pytest.approx(expected, abs=0.01)
        assert r.base_price == 15.0

    def test_risk_reward(self):
        """RR = upside / |downside|。"""
        r = run_scenario(current_price=10.0, dcf_value=20.0, comparable_value=10.0)
        assert r.upside == pytest.approx((r.weighted_target - 10.0) / 10.0 * 100, abs=0.1)
        assert r.risk_reward > 0

    def test_only_one_method_uses_max(self):
        """只有一个正方法时 base = max(dcf, comparable)。"""
        r = run_scenario(current_price=10.0, dcf_value=0.0, comparable_value=30.0)
        assert r.base_price == 30.0

    def test_zero_price_no_crash(self):
        r = run_scenario(current_price=0.0, dcf_value=20.0, comparable_value=10.0)
        assert r.upside == 0.0
        assert r.downside == 0.0
