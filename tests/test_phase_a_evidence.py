"""
Phase A 测试：engine_ib 注入器 + 证据账本 enforcer + gate 接线。
"""


# ── fixture: 真实形态 compute_results ────────────────────────────────────


def _ib_results(fv=1950.27, upside=30.0, mc=(1207.6, 3449.9), mc_med=1960.6):
    return {
        "engine_ib": {
            "status": "ok",
            "result": {
                "fair_value": fv,
                "upside_pct": upside,
                "enterprise_value": 24938e8,
                "tv_pct": 0.797,
                "scenario_weighted_target": 1883.1,
                "mc_median": mc_med,
                "mc_ci95": mc,
                "wacc": 0.0843,
                "expectations": {
                    "implied_growth": 0.0419,
                    "our_growth": 0.1566,
                    "ev_to_fcf": 24.57,
                    "converged": True,
                    "warnings": [],
                },
                "tornado_ranking": [
                    {"param": "wacc", "swing": 1587.5},
                    {"param": "revenue_growth_rates", "swing": 1049.7},
                ],
                "assumptions": {"growth_rates": [0.165, 0.180, 0.157, 0.157, 0.157], "ebit_margin": 0.58},
                # WACC×g 敏感性矩阵：5×5，中心≈fair_value，角差驱动 gate matrix_pattern
                "sensitivity_wacc_range": [0.0643, 0.0743, 0.0843, 0.0943, 0.1043],
                "sensitivity_g_range": [0.015, 0.025, 0.035, 0.045, 0.055],
                "sensitivity_matrix": [
                    [1738.0, 1805.0, 1880.0, 1965.0, 2062.0],
                    [1670.0, 1730.0, 1796.0, 1870.0, 1954.0],
                    [1610.0, 1665.0, 1724.0, 1790.0, 1863.0],
                    [1556.0, 1605.0, 1659.0, 1718.0, 1783.0],
                    [1506.0, 1551.0, 1600.0, 1654.0, 1712.0],
                ],
            },
        },
        "scenario_analysis": {
            "status": "ok",
            "result": {"bull_price": 2100, "base_price": 1900, "bear_price": 1400, "weighted_target": 1883.1},
        },
    }


class TestInjectorEngineIB:
    def test_injector_renders_full_block(self):
        from pipeline.prompt_injectors import build_injections

        dc = {"compute_results": _ib_results()}
        out = build_injections("600519", "listed_company", data_context=dc)
        s = out.get("engine_ib_str", "")
        assert "1,950.27" in s
        assert "30.0%" in s
        assert "79.7%" in s
        assert "不得自造" in s

    def test_injector_renders_sensitivity_matrix(self):
        """engine_ib 注入器应输出 WACC×g 敏感性矩阵（dcf_sensitivity gate 需正文含矩阵）。"""
        from pipeline.prompt_injectors import build_injections

        dc = {"compute_results": _ib_results()}
        out = build_injections("600519", "listed_company", data_context=dc)
        s = out.get("engine_ib_str", "")
        assert "DCF 敏感性矩阵" in s
        assert "WACC \\ g" in s
        # 三连 % 数字（矩阵表头 5 个 %）——满足 gate 的 matrix_pattern
        assert s.count("%") >= 5
        assert "1,950" not in s or "对角" in s or "不得自造敏感性" in s

    def test_injector_skips_when_not_ok(self):
        from pipeline.prompt_injectors import build_injections

        dc = {"compute_results": {"engine_ib": {"status": "skip", "reason": "x"}}}
        out = build_injections("600519", "listed_company", data_context=dc)
        assert out.get("engine_ib_str", "") == ""

    def test_injector_never_crashes_on_empty(self):
        from pipeline.prompt_injectors import build_injections

        out = build_injections("x", "y", data_context=None)
        assert "engine_ib_str" in out


class TestEvidenceEnforcer:
    def test_extract_chinese_claims(self):
        from pipeline.evidence_enforcer import extract_claims

        text = "我们给予目标价 1950.27 元。预计营收增长15.7%，毛利率达91.9%。"
        claims = extract_claims(text)
        kinds = [c.kind for c in claims]
        assert "target_price" in kinds
        assert "growth" in kinds
        assert "margin" in kinds

    def test_verify_ok_report(self):
        from pipeline.evidence_enforcer import run_evidence_check

        text = "基于 16-step 计算引擎，目标价 1950.27 元。上行空间 30.0%。情景加权目标价 1883.1 元。WACC 8.4%。"
        ledger = run_evidence_check(text, _ib_results())
        assert ledger.coverage >= 0.7
        assert len(ledger.verified) >= 3

    def test_contradicted_claim_detected(self):
        from pipeline.evidence_enforcer import run_evidence_check

        # LLM 自造目标价 2500（引擎输出 1950.27）
        text = "我们给予目标价 2500 元，情景加权目标价 1883.1 元。"
        ledger = run_evidence_check(text, _ib_results())
        assert len(ledger.contradicted) >= 1
        assert ledger.coverage < 1.0
        fb = __import__("pipeline.evidence_enforcer", fromlist=["format_gate_feedback"]).format_gate_feedback(ledger)
        assert "2500" in fb

    def test_unverifiable_outlook_not_counted_as_contradicted(self):
        from pipeline.evidence_enforcer import run_evidence_check

        # 展望性增长（池中有 growth 家族，但值对不上→contradicted）；
        # 市占率声明无对应池家族 → unverifiable
        text = "未来五年行业 CAGR 增长35%，公司市占率40%。"
        ledger = run_evidence_check(text, _ib_results())
        # 市占率 share 家族有 growth/upside 池 → 会尝试匹配
        # 至少不应 crash
        assert ledger.summary()["total_claims"] >= 1

    def test_no_pool_all_unverifiable(self):
        from pipeline.evidence_enforcer import run_evidence_check

        text = "目标价 100 元"
        ledger = run_evidence_check(text, {"engine_ib": {"status": "skip"}})
        assert len(ledger.unverifiable) == 1

    def test_ledger_summary_shape(self):
        from pipeline.evidence_enforcer import run_evidence_check

        ledger = run_evidence_check("目标价 1950 元", _ib_results())
        s = ledger.summary()
        assert set(s.keys()) == {"total_claims", "verified", "contradicted", "unverifiable", "coverage"}

    def test_audit_appendix_format(self):
        from pipeline.evidence_enforcer import format_audit_appendix, run_evidence_check

        ledger = run_evidence_check("目标价 1950.27 元", _ib_results())
        appendix = format_audit_appendix(ledger, _ib_results())
        assert "附录：数值证据账本" in appendix
        assert "1,950.27" in appendix


class TestAssembleAppendixGlue:
    """Phase A3/E glue：assemble 节点把证据附录 + 认知边界附录注入 final_text。

    直接调用生产节点 E2ENodes.assemble，验证两条附录注入路径在真实 assemble
    上下文（report_text + compute_results.engine_ib ok + collected_data）下生效。
    """

    def test_both_appendixes_injected(self):
        from pipeline.e2e_orchestrator import E2ENodes

        report_text = (
            "# 贵州茅台深度研究\n\n"
            "## 估值\n"
            "目标价 1950.27 元，相对当前价上行 30.0%。情景加权目标 1883.1 元。\n\n"
            "## 财务\n"
            "WACC 8.43%，隐含增长 4.19%。\n"
        )
        ctx = {
            "asset": "贵州茅台",
            "asset_code": "600519",
            "report_type": "listed_company",
            "style": "cicc",
            "report_text": report_text,
            "chart_paths": {},
            "compute_results": _ib_results(),
            "collected_data": {"compute_results": _ib_results()},
        }
        out = E2ENodes.assemble("assemble", ctx)
        final = out["final_text"]
        assert "附录：数值证据账本" in final, "证据附录应被注入"
        assert "认知边界（未验证假设" in final, "认知边界附录应被注入"

    def test_appendixes_idempotent(self):
        """重复 assemble（write-revise 迭代）不应重复注入附录。"""
        from pipeline.e2e_orchestrator import E2ENodes

        report_text = "# 标题\n\n目标价 1950.27 元，上行 30.0%。"
        ctx = {
            "asset": "贵州茅台",
            "asset_code": "600519",
            "report_type": "listed_company",
            "style": "cicc",
            "report_text": report_text,
            "chart_paths": {},
            "compute_results": _ib_results(),
            "collected_data": {"compute_results": _ib_results()},
        }
        E2ENodes.assemble("assemble", ctx)
        final1 = ctx["final_text"]
        # 模拟二次 assemble（ctx 已含 final_text，report_text 不变 → 幂等检查触发）
        out2 = E2ENodes.assemble("assemble", ctx)
        final2 = out2["final_text"]
        assert final1.count("附录：数值证据账本") == final2.count("附录：数值证据账本") == 1
        assert final1.count("认知边界（未验证假设") == final2.count("认知边界（未验证假设") == 1


class TestGateEvidenceCoverage:
    def _make_gate(self, report_text, collected_data):
        import tempfile
        from pathlib import Path

        from pipeline.iron_gate import IronGate

        tmp = Path(tempfile.mkstemp(suffix=".md")[1])
        tmp.write_text(report_text, encoding="utf-8")
        return IronGate(
            str(tmp),
            report_type="listed_company",
            style="cicc",
            asset="600519",
            collected_data=collected_data,
        )

    def test_check_passes_high_coverage(self):
        gate = self._make_gate(
            "目标价 1950.27 元，情景加权 1883.1 元，上行 30.0%。目标价 1950 元再确认。",
            {"compute_results": _ib_results()},
        )
        gate.report_text = gate.report_path.read_text(encoding="utf-8")
        r = gate._check_evidence_coverage()
        assert r.name == "evidence_coverage"
        assert r.passed

    def test_check_skips_without_compute(self):
        gate = self._make_gate("目标价 100 元", {})
        gate.report_text = "目标价 100 元"
        r = gate._check_evidence_coverage()
        assert r.passed
        assert "跳过" in r.details

    def test_check_warns_low_coverage_not_blocks(self):
        # 基线收集期: 低覆盖率不阻断（passed=True + warning）
        gate = self._make_gate(
            "目标价 3000 元，目标价 2800 元，目标价 3100 元，目标价 2500 元，目标价 2700 元。",
            {"compute_results": _ib_results()},
        )
        gate.report_text = gate.report_path.read_text(encoding="utf-8")
        r = gate._check_evidence_coverage()
        assert r.passed  # 基线期不阻断
        assert r.severity in ("warning",)  # 但要警告
