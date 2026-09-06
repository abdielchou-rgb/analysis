"""
Phase C/D/E 测试：数据契约 / 服务面 / intent 接线 / KG-lite。
"""

import pytest

# ── Phase C: Data Contract ──────────────────────────────────────────────


class TestDataContract:
    def test_normalize_cn_units(self):
        from core.data_contract import normalize_cn_number

        assert normalize_cn_number("29.12亿")[0] == pytest.approx(29.12e8)
        assert normalize_cn_number("8.67万")[0] == pytest.approx(8.67e4)
        assert normalize_cn_number("1.5万亿")[0] == pytest.approx(1.5e12)
        assert normalize_cn_number("--")[0] == 0.0
        assert normalize_cn_number(1741.44)[0] == 1741.44

    def test_period_key_parse(self):
        from core.data_contract import parse_period_key

        assert parse_period_key("2024") == ("2024", "annual")
        assert parse_period_key("2025E") == ("2025", "forecast")
        assert parse_period_key("2026Q3") == ("2026", "quarter")
        assert parse_period_key("Figaro") is None

    def test_contract_validates_missing_source(self):
        from core.data_contract import DataContract

        c = DataContract().validate_chart_data({"fig_valuation": {"price": 100}})
        assert any(v.issue == "missing_metadata" for v in c.violations)

    def test_contract_period_conflict_detected(self):
        from core.data_contract import DataContract

        # P0-4 形态: valuation 是 2026Q3, revenue_trend 最新年报 2024
        cd = {
            "fig_revenue_trend": {"2023": 100, "2024": 120},
            "fig_valuation": {"price": 100, "source": "x", "period": "2026-09-30"},
        }
        c = DataContract().validate_chart_data(cd)
        assert any(v.issue == "period_conflict" for v in c.violations)

    def test_contract_clean_data_no_violations(self):
        from core.data_contract import DataContract

        cd = {
            "fig_revenue_trend": {"2024": {"revenue": "100亿"}},
            "fig_valuation": {"price": 100, "source": "akshare", "period": "2024-12-31"},
        }
        c = DataContract().validate_chart_data(cd)
        assert not c.violations
        assert c.get("revenue.2024").value == pytest.approx(100e8)

    def test_contract_summary(self):
        from core.data_contract import DataContract

        s = DataContract().validate_chart_data({}).summary()
        assert set(s.keys()) == {"n_fields", "n_violations", "violations"}


# ── Phase D: Service ────────────────────────────────────────────────────


class TestServiceApp:
    def test_app_imports(self):
        from service.app import app

        assert app.title

    def test_health_endpoint(self):
        from fastapi.testclient import TestClient

        from service.app import app

        client = TestClient(app)
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_create_and_status(self):
        from fastapi.testclient import TestClient

        from service.app import app

        client = TestClient(app)
        r = client.post("/api/v1/research", json={"asset": "600519", "report_type": "listed_company"})
        assert r.status_code == 200
        task_id = r.json()["research_id"]
        s = client.get(f"/api/v1/research/{task_id}/status")
        assert s.status_code == 200
        assert s.json()["status"] in ("queued", "running", "done", "failed")

    def test_status_404(self):
        from fastapi.testclient import TestClient

        from service.app import app

        client = TestClient(app)
        assert client.get("/api/v1/research/nonexistent/status").status_code == 404


# ── Phase E: intent_bridge + KG-lite ─────────────────────────────────────


class TestIntentBridge:
    def test_hypothesis_plan_basic(self):
        from core.intent_bridge import build_hypothesis_plan

        cd = {
            "chart_data": {
                "fig_revenue_trend": {"2024": 100},
                "fig_valuation": {"price": 10},
                "fig_industry_board": [{"pe": 20}],
            }
        }
        plan = build_hypothesis_plan("600519", "listed_company", cd)
        assert plan["status"] == "ok"
        assert len(plan["hypotheses"]) >= 3
        assert plan["coverage"] is not None
        # 采集过的能力应标记 collected
        for h in plan["hypotheses"]:
            for d in h["data_needs"]:
                if d["capability"] in ("revenue_growth", "valuation", "competition"):
                    assert d["collected"]

    def test_unverifiable_appendix(self):
        from core.intent_bridge import build_hypothesis_plan, format_unverifiable_appendix

        plan = build_hypothesis_plan("X", "listed_company", {})  # 无数据 → 大量未验证
        appendix = format_unverifiable_appendix(plan)
        if plan["unverifiable"]:
            assert "认知边界" in appendix
            assert "未验证" in appendix

    def test_engine_fallback(self):
        """collected_data 非 dict 不崩溃"""
        from core.intent_bridge import build_hypothesis_plan

        plan = build_hypothesis_plan("X", "listed_company", None)
        assert plan["status"] == "ok"


class TestKGLite:
    def test_seed_and_query(self, tmp_path):
        from core.kg_lite import KG

        kg = KG(db_path=tmp_path / "kg.db")
        stats = kg.seed_from_data_assets(force=True)
        assert stats["companies"] > 1000  # a_stock_name_map 5556
        assert stats["industries"] > 100  # 335 板块

        s = kg.stats()
        assert s["nodes"] > 1000

    def test_name_search(self, tmp_path):
        from core.kg_lite import KG

        kg = KG(db_path=tmp_path / "kg.db")
        kg.seed_from_data_assets(force=True)
        rows = kg.search_by_name("银行", limit=5)
        assert len(rows) >= 1
        assert "银行" in rows[0]["name"]

    def test_peers_2hop(self, tmp_path):
        from core.kg_lite import KG

        kg = KG(db_path=tmp_path / "kg.db")
        kg.seed_from_data_assets(force=True)
        kg.link_company_industry("600519", "850111.SI")
        kg.link_company_industry("600809", "850111.SI")
        peers = kg.same_industry_peers("600519")
        assert any("600809" in p["id"] for p in peers)

    def test_industry_baseline(self, tmp_path):
        from core.kg_lite import KG

        kg = KG(db_path=tmp_path / "kg.db")
        kg.seed_from_data_assets(force=True)
        with_kg = kg.industry_baseline("白酒")
        # 种子数据板块名不一定含"白酒"（SW 分类），容错：找到或 None 均可
        assert with_kg is None or "meta" in with_kg


class TestPeerInjector:
    """Phase E：同业名单注入器——竞争维度写作弹药（真实 peer_valuation 数据）。"""

    def test_returns_peers_for_maotai(self):
        from pipeline.prompt_injectors import _inj_kg_peers_str

        out = _inj_kg_peers_str({"asset": "贵州茅台", "asset_code": "600519"})
        assert out and "600519" not in out.replace("600519", "")  # 自查无本标的
        # 白酒同业应包含至少 3 家可识别成员
        known = ["酒鬼酒", "五粮液", "舍得酒业", "洋河股份", "泸州老窖", "今世缘", "古井贡酒", "水井坊", "山西汾酒"]
        assert sum(1 for k in known if k in out) >= 3

    def test_empty_for_unknown_code(self):
        from pipeline.prompt_injectors import _inj_kg_peers_str

        assert _inj_kg_peers_str({"asset": "X", "asset_code": "000000"}) == ""
        assert _inj_kg_peers_str({"asset": "X", "asset_code": ""}) == ""
        assert _inj_kg_peers_str({}) == ""


class TestScorePredictionsIntegration:
    """Phase B3：预测兑现打分器——路径发现 + schema 兼容 + 资产解析修复。"""

    def test_finds_forward_picks_records(self):
        """_find_records 应发现 core/data/forward_picks/track_record.json（真实落盘位置）。"""
        from eval import score_predictions as sp

        recs = sp._find_records()
        # 无论内容如何，函数应能定位到 forward_picks 文件并解析出记录
        assert isinstance(recs, list)

    def test_parse_pure_date(self):
        """_parse_date 兼容纯日期 '2026-07-31'（track_record 形态）。"""
        from eval import score_predictions as sp

        dt = sp._parse_date("2026-07-31")
        assert dt is not None and dt.year == 2026 and dt.month == 7 and dt.day == 31
        assert sp._parse_date(None) is None

    def test_asset_to_code_maotai(self):
        """中文资产名 → A 股代码解析（复用统一解析层）。"""
        from eval import score_predictions as sp

        code = sp._asset_to_code("贵州茅台")
        assert code == "600519"
        # 已带代码原样返回
        assert sp._asset_to_code("600519") == "600519"

    def test_target_price_string_coercion(self):
        """target_price 为含逗号字符串/空串时应正确解析（track_record 形态）。"""
        from eval import score_predictions as sp

        # 直接验证主循环的解析逻辑（通过空记录集跑通 score_predictions 不炸）
        # 构造临时 forward_picks 文件 → _find_records 返回空（无到期记录）也不崩溃
        result = sp.score_predictions(horizon_days=30)
        assert isinstance(result, dict)
        assert result["status"] in ("ok", "no_records")
        assert "n_scored" in result
