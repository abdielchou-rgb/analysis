# -*- coding: utf-8 -*-
"""Phase B2 eval 体系单元测试：score 对象化 / run_evalset / diff_runs / value_lock / report_quality。

覆盖 mini-GEPA 闭环 + 数值锁定 + 确定性质量回归的基础逻辑（不调真实 LLM，
judge 回复用桩注入）。
"""

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_FAKE_JUDGE_CONTENT = (
    '{"factual_accuracy": {"score": 5, "reason": "多处数据无来源或A/E/F估算，自造风险高"}, '
    '"citation_completeness": {"score": 3, "reason": "大量关键论断无具体来源，无法回溯验证"}, '
    '"logical_depth": {"score": 6, "reason": "有So What与反方但部分推导重复"}, '
    '"industry_understanding": {"score": 6, "reason": "白酒价值链基本把握但框架应用生硬"}, '
    '"falsifiability": {"score": 4, "reason": "有证伪条件但缺催化剂跟踪"}, '
    '"expression_quality": {"score": 5, "reason": "结构清晰但有AI腔"}}'
)


class TestRubricScoreObject:
    def test_score_object_shape_and_reasons(self, monkeypatch):
        """judge 结构化输出 → score 对象（value+reason+type），reason 不截断丢失。"""
        import core.deepseek_client as dc
        import eval.rubric_score as rs

        monkeypatch.setattr(
            dc, "call_llm", lambda *a, **k: {"choices": [{"message": {"content": _FAKE_JUDGE_CONTENT}}]}
        )
        r = rs.score_report("# 报告\n\n" * 100)
        assert r["total"] == pytest.approx(4.85, abs=0.01)
        s = r["scores"]["citation_completeness"]
        assert s["type"] == "numeric" and s["value"] == 3
        assert "无具体来源" in s["reason"]  # 理由完整保留（Langfuse score model 对齐）

    def test_weakest_feedback_actionable(self, monkeypatch):
        """weakest_feedback 抽出最低维度理由 → mini-GEPA 修正指令输入。"""
        import core.deepseek_client as dc
        import eval.rubric_score as rs

        monkeypatch.setattr(
            dc, "call_llm", lambda *a, **k: {"choices": [{"message": {"content": _FAKE_JUDGE_CONTENT}}]}
        )
        r = rs.score_report("# 报告\n\n" * 100)
        fb = rs.weakest_feedback(r)
        assert fb["dim"] == "citation_completeness"
        assert fb["score"] == 3
        assert fb["actionable"] is True  # 理由足够具体

    def test_backward_compat_flat_json(self, monkeypatch):
        """兼容旧 judge 扁平输出 {dim: int}。"""
        import core.deepseek_client as dc
        import eval.rubric_score as rs

        flat = '{"factual_accuracy": 5, "citation_completeness": 3, "logical_depth": 6, "industry_understanding": 6, "falsifiability": 4, "expression_quality": 5}'
        monkeypatch.setattr(dc, "call_llm", lambda *a, **k: {"choices": [{"message": {"content": flat}}]})
        r = rs.score_report("x" * 500)
        assert r["dimensions"]["citation_completeness"] == 3
        assert r["scores"]["logical_depth"]["value"] == 6

    def test_dims_of_both_shapes(self):
        import eval.rubric_score as rs

        new = {"scores": {"a": {"value": 7, "reason": "x"}}}
        old = {"dimensions": {"a": 7}}
        assert rs._dims_of(new)["a"] == 7
        assert rs._dims_of(old)["a"] == 7


class TestEvalsetRunDiff:
    def _make_run(self, tmp_path, run_id, totals):
        """构造最小 run 目录结构。"""
        import eval.run_evalset as re_  # noqa: F401  (确保模块可导入)

        d = tmp_path / "runs" / run_id
        d.mkdir(parents=True)
        for asset, total in totals.items():
            dims = {
                k: max(1, int(total))
                for k in [
                    "factual_accuracy",
                    "citation_completeness",
                    "logical_depth",
                    "industry_understanding",
                    "falsifiability",
                    "expression_quality",
                ]
            }
            (d / f"{asset}.json").write_text(
                json.dumps({"asset": asset, "total": total, "dimensions": dims, "commit": run_id}),
                encoding="utf-8",
            )
        return d

    def test_diff_detects_regression(self, tmp_path, monkeypatch):
        import eval.diff_runs as dr

        monkeypatch.setattr(dr, "RUNS_DIR", tmp_path / "runs")
        self._make_run(tmp_path, "base", {"茅台": 4.85, "柯力": 6.0})
        self._make_run(tmp_path, "new", {"茅台": 4.2, "柯力": 6.3})
        r = dr.diff_runs("base", "new")
        assert r["status"] == "ok"
        assert r["per_asset"]["茅台"]["regression"] is True  # 4.85→4.2 回归被抓
        assert r["n_regressed"] == 1
        assert r["dim_agg"]["logical_depth"]["delta"] == pytest.approx(0, abs=0.01)

    def test_evalset_json_valid(self):
        import eval.report_quality as rq

        data = json.loads((rq._ANALYST_ROOT / "eval" / "evalset.json").read_text(encoding="utf-8"))
        assert len(data["reports"]) >= 1


class TestValueLock:
    def _engine(self, fv=1950.27):
        return {
            "engine_ib": {
                "status": "ok",
                "result": {"fair_value": fv, "scenario_weighted_target": 1883.1, "mc_median": 1960.6},
            }
        }

    def test_passes_when_target_matches_engine(self):
        from eval.value_lock import lock_report

        text = "# 估值\n\n我们给出12个月目标价 1950.27 元，基于DCF。"
        r = lock_report(text, self._engine())
        assert r["passed"] is True, r["hard_fails"]

    def test_flags_invented_target_price(self):
        from eval.value_lock import lock_report

        text = "# 估值\n\n我们给出12个月目标价 800.00 元，我们认为严重低估。"
        r = lock_report(text, self._engine())
        assert r["passed"] is False
        assert any("自造目标价" in f for f in r["hard_fails"])

    def test_skips_without_engine(self):
        from eval.value_lock import lock_report

        r = lock_report("# 估值\n\n目标价 100 元", {})
        assert r["skipped"] == "no_engine_ib"

    def test_family_tolerance(self):
        """mc_median 家族值（±3%）也通过。"""
        from eval.value_lock import lock_report

        text = "合理价位 1960 元"  # mc_median 1960.6 附近
        r = lock_report(text, self._engine())
        assert r["passed"] is True


class TestReportQuality:
    def test_clean_report_passes_all(self, tmp_path):
        """构造符合当前管线契约的报告 → 7 项断言全过。"""
        import eval.report_quality as rq

        clean = (
            "# 贵州茅台深度报告\n\n"
            "报告日期：2026年09月 | 分析师：2号分析师\n\n"
            "## 估值\n"
            "DCF目标价 1950.27 元。\n\n"
            "## 附录：数据溯源注释\n"
            "[注1] 数据键 fig_margin｜论断：毛利率稳定在90%。\n\n"
            "## 认知边界（未验证假设，诚实留白）\n"
            "- 假设『价: 提价能力』：本报告未验证该判断。\n\n"
            "以上假设在后续数据补采后验证。\n\n"
            "## 风险\n"
            "心智占位是护城河核心；若批价跌破2000元则证伪。"
        )
        checks = rq._checks_for(clean)
        failed = [c for c in checks if not c["passed"]]
        assert failed == [], f"失败: {[c['check'] for c in failed]}"

    def test_annotation_pollution_caught(self):
        """机械注解复读（上轮手工抓的污染类型）被 Q1/Q5 拦截。"""
        import eval.report_quality as rq

        polluted = (
            "# 报告\n\n毛利率 92%（此水平较同业中位数明显领先，验证成本优势传导）-87%（此水平较同业中位数明显领先，验证成本优势传导）。\n\n"
            * 5
        )
        checks = rq._checks_for(polluted)
        q1 = [c for c in checks if c["check"] == "Q1_no_annotation_repeat"][0]
        q6 = [c for c in checks if c["check"] == "Q6_ranges_intact"][0]
        assert q1["passed"] is False
        assert q6["passed"] is False  # 区间被注解拆烂
