"""
Golden Compute 回归测试（Phase B1，2026-09-06）。

目的：三个固定 fixture（高毛利白酒型 / 银行低毛利型 / 增长亏损型）→
engine 16-step 管线 → 快照 fair_value / 情景 / MC / 期望差。

这是 CI 级回归防线：MC correlation bug（2026-09-06 修复，中位数 718→1420）
这类静默数值漂移，靠它拦截，不再依赖人眼。

确定性保证：
- DCF: Decimal 50 位精度
- MC: 固定 seed → Box-Muller 同序列
- 三表/情景: 纯算术

快照更新（有意变更后）：pytest --snapshot-update 或删 GOLDEN 字典重跑生成。
"""

import json
from pathlib import Path

import pytest

SNAPSHOT_FILE = Path(__file__).parent / "golden_compute_snapshots.json"

# ── 三个资产画像 fixture ────────────────────────────────────────────────

BAIJIU = {  # 高毛利、稳增长、低负债（茅台型）
    "asset": "600519",
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
        "fig_valuation": {"price": 1500.0, "market_cap": 18800},
    },
}

BANK = {  # 低毛利、高杠杆（银行型）
    "asset": "600036",
    "chart_data": {
        "fig_revenue_trend": {
            "2021": {
                "revenue": "3312亿",
                "net_profit": "1199亿",
                "gross_margin": "100%",
                "roe": "17.0%",
                "eps": "4.69",
                "asset_liability_ratio": "90.5%",
            },
            "2022": {
                "revenue": "3447亿",
                "net_profit": "1380亿",
                "gross_margin": "100%",
                "roe": "17.1%",
                "eps": "5.26",
                "asset_liability_ratio": "90.4%",
            },
            "2023": {
                "revenue": "3391亿",
                "net_profit": "1466亿",
                "gross_margin": "100%",
                "roe": "16.2%",
                "eps": "5.63",
                "asset_liability_ratio": "90.7%",
            },
            "2024": {
                "revenue": "3374亿",
                "net_profit": "1483亿",
                "gross_margin": "100%",
                "roe": "14.5%",
                "eps": "5.83",
                "asset_liability_ratio": "91.0%",
            },
        },
        "fig_valuation": {"price": 40.0, "market_cap": 10100},
    },
}

GROWTH_LOSS = {  # 增长+微利（新能源亏损型）
    "asset": "688xxx",
    "chart_data": {
        "fig_revenue_trend": {
            "2021": {
                "revenue": "40亿",
                "net_profit": "0.5亿",
                "gross_margin": "18%",
                "roe": "0.6%",
                "eps": "0.04",
                "asset_liability_ratio": "55%",
            },
            "2022": {
                "revenue": "82亿",
                "net_profit": "2亿",
                "gross_margin": "20%",
                "roe": "2.0%",
                "eps": "0.13",
                "asset_liability_ratio": "58%",
            },
            "2023": {
                "revenue": "166亿",
                "net_profit": "4亿",
                "gross_margin": "22%",
                "roe": "3.5%",
                "eps": "0.25",
                "asset_liability_ratio": "60%",
            },
            "2024": {
                "revenue": "290亿",
                "net_profit": "6亿",
                "gross_margin": "24%",
                "roe": "4.5%",
                "eps": "0.36",
                "asset_liability_ratio": "62%",
            },
        },
        "fig_valuation": {"price": 25.0, "market_cap": 420},
    },
}

FIXTURES = {"baijiu": BAIJIU, "bank": BANK, "growth_loss": GROWTH_LOSS}


def _run_engine(financial_data: dict) -> dict:
    """跑 bridge → 16-step，抽核心数值。MC 固定 seed 由 bridge 参数控制。"""
    from pipeline.engine_bridge import run_engine_ib

    r = run_engine_ib(financial_data)
    assert r["status"] == "ok", r.get("reason", r.get("error"))
    res = r["result"]
    return {
        "fair_value": round(res["fair_value"], 2),
        "upside_pct": round(res["upside_pct"] or 0, 2),
        "tv_pct": round(res["tv_pct"] * 100, 2),
        "scenario_weighted": round(res["scenario_weighted_target"], 2),
        "mc_median": round(res["mc_median"], 2),
        "implied_growth_pct": round(res["expectations"]["implied_growth"] * 100, 3),
        "ev_to_fcf": round(res["expectations"]["ev_to_fcf"], 2),
    }


def _load_or_init_snapshots() -> dict:
    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    # 首次生成（golden run）——只收可跑 fixture（growth_loss 走 skip 路径不收）
    snaps = {name: _run_engine(fd) for name, fd in FIXTURES.items() if name in ("baijiu", "bank")}
    SNAPSHOT_FILE.write_text(json.dumps(snaps, ensure_ascii=False, indent=2), encoding="utf-8")
    return snaps


GOLDEN = _load_or_init_snapshots()


@pytest.mark.parametrize("name", ["baijiu", "bank"])
def test_golden_snapshot(name):
    current = _run_engine(FIXTURES[name])
    expected = GOLDEN[name]
    for key, exp_val in expected.items():
        assert current[key] == pytest.approx(exp_val, abs=0.51), (
            f"{name}.{key} 漂移: golden={exp_val} current={current[key]} — "
            f"若为有意变更，删除 {SNAPSHOT_FILE.name} 重新生成并 review diff"
        )


def test_growth_loss_skips_with_reason():
    """微利重投资标的: FCF DCF 无意义 → bridge 诚实让位（skip + 可比法建议），
    不产出负目标价污染报告。"""
    from pipeline.engine_bridge import run_engine_ib

    r = run_engine_ib(FIXTURES["growth_loss"])
    assert r["status"] == "skip"
    assert "FCF" in r["reason"]
    assert "可比法" in r["reason"] or "PS" in r["reason"]


def test_cross_method_convergence():
    """质量守恒：同一资产 DCF / 情景加权 / MC 中位数应在同一数量级（<3.5x）。
    这是当初发现 MC correlation bug 的启发式——当时 MC 腰斩到 0.36x。
    """
    for name in ("baijiu", "bank"):
        r = _run_engine(FIXTURES[name])
        vals = [r["fair_value"], r["scenario_weighted"], r["mc_median"]]
        ratio = max(vals) / max(min(vals), 1e-9)
        assert ratio < 3.5, f"{name} 三法发散: ratio={ratio:.2f} {vals}"


def test_economic_sanity_all():
    """经济合理域: TV% ∈ (30%, 95%)；隐含增长 ∈ (-5%, 30%)"""
    for name in ("baijiu", "bank"):
        r = _run_engine(FIXTURES[name])
        assert 30 <= r["tv_pct"] <= 95, f"{name} tv_pct={r['tv_pct']}"
        assert -5 <= r["implied_growth_pct"] <= 30, f"{name} implied_g={r['implied_growth_pct']}"


def test_mc_deterministic_with_seed():
    """固定 seed → MC 中位数逐次复现（golden 回归的前提）"""
    a = _run_engine(FIXTURES["baijiu"])
    b = _run_engine(FIXTURES["baijiu"])
    assert a["mc_median"] == b["mc_median"]
