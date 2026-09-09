# -*- coding: utf-8 -*-
"""2026-09-09 Gate 0.95 提分修复回归测试。

覆盖：
- detect_value_conflicts 指标精确匹配（跨指标误报消除 + 真冲突仍抓）
- anti_patterns 豁免逻辑（框架应用句/计数前缀/结论句式豁免 + 裸表述仍抓）
- consistency_engine 现价分簇（现价 260 vs 目标价 300 不再误判）
- so_what_chain 分母修正（合规/表格/图表/披露段排除）
- cross_industry agency_exemptions（电池行业 SNE Research 豁免）
- template_repeat 引导词内容判定（"综合判断："后接内容重复才计）
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── detect_value_conflicts（指标精确匹配） ────────────────────


class TestDetectValueConflictsPrecise:
    DD = {
        "margin_2022": 20.25,
        "margin_2024": 24.44,
        "margin_2025": 26.27,
        "net_profit_2025": 16.28,
        "roe_2022": 18.99,
    }

    def _run(self, text):
        from pipeline.checks.base import detect_value_conflicts

        return detect_value_conflicts(text, self.DD)

    def test_true_conflict_margin(self):
        # 真冲突必须抓：正文 44% vs 库 26.27%
        assert self._run("2025年毛利率录得44%（A），据公司财报。") != []

    def test_consistent_margin_ok(self):
        assert self._run("2025年毛利率26.27%（A）") == []

    def test_consistent_net_profit_ok(self):
        assert self._run("2025年净利率为16.28%（A）") == []

    def test_true_conflict_net_profit(self):
        assert self._run("2025年净利率仅10%（A）实际录得。") != []

    def test_cross_indicator_no_false_positive(self):
        # 2022 净利率 43.70% 不应与 margin_2022=20.25 比对（旧版误报根因）
        assert self._run("2022年净利率低点约43.70%（A）") == []

    def test_roe_consistent(self):
        assert self._run("公司ROE从2022年的低点约18.99%（A）修复。") == []

    def test_forecast_context_exempt(self):
        # 悲观预测是情景推演，非事实陈述
        assert self._run("若2025年净利率下滑至12%以下的悲观预测成立。") == []

    def test_silent_regex_failure_guard(self):
        # 回归护栏：regex 编译错误会被 except 静默吞掉 → 恒空转。
        # 真冲突样例必须持续非空，防 redefinition-of-group 复发。
        assert self._run("2025年毛利率为44.83%（A）。") != []


# ── anti_patterns 豁免 ──────────────────────────────────────


class TestAntiPatternsExemptions:
    def test_framework_sentence_exempt(self):
        from core.anti_patterns import scan

        t = "用【经济护城河分析框架】分析本标的下：护城河并非单一来源，而是三重叠加。"
        assert scan(t) == []

    def test_count_prefix_exempt(self):
        from core.anti_patterns import scan

        t = "可持续的竞争优势（成本+转换成本+有效规模三重护城河）是核心。"
        assert scan(t) == []

    def test_bare_claim_still_caught(self):
        from core.anti_patterns import scan

        t = "该公司护城河稳固，长期看好。竞争壁垒深厚，空间广阔。"
        hits = scan(t)
        assert len(hits) >= 2  # 至少护城河/壁垒/空间被命中


# ── consistency_engine 现价分簇 ──────────────────────────────


class TestConsistencyPriceSplit:
    def test_current_price_not_target_conflict(self):
        from pipeline.consistency_engine import check_consistency

        # 现价 260 + 目标价 300 = +15.4%，合法组合，旧版误判目标价冲突
        t = "现价若为260元（E），目标价300元（F）隐含上行空间约15.4%。"
        r = check_consistency(t)
        assert r["passed"], f"conflicts: {r['conflicts']}"

    def test_real_target_conflict_still_caught(self):
        from pipeline.consistency_engine import check_consistency

        t = "目标价260元（F）。另一处：目标价300元（F）。"
        r = check_consistency(t)
        assert not r["passed"]


# ── so_what_chain 分母修正 ───────────────────────────────────


class TestSoWhatDenominator:
    def _gate(self, text):
        from pipeline.iron_gate import IronGate

        return IronGate.from_text(text, report_type="earnings_notes", style="cicc", asset="测试")

    def test_disclosure_sections_excluded(self):
        # 合规披露段（评级定义/利益冲突/重要提示/数据缺口）不应计入分母
        _para = (
            "营收增长10%，因此我们认为盈利质量改善。这意味着投资价值提升。"
            "验证：现金流改善印证盈利真实性。从三表勾稽看，这为估值修复提供支撑。"
            "数据表明，行业需求维持增长，传导至公司订单能见度，从而盈利预测上修概率提升。"
            "我们判断，该趋势若延续，目标价存在上修空间，对投资者意味着超额收益机会。"
        )
        body = "## 一、盈利分析。\n" + _para + "\n## 二、增长驱动。\n" + _para + "\n## 三、风险证伪。\n" + _para + "\n"
        disc = (
            "## 评级定义与说明。\n| 评级 | 定义 |\n| 买入 | 涨幅>15% |\n"
            "## 利益冲突披露。\n本报告由测试撰写，无利益冲突。\n"
            "## 3.3 数据缺口与待尽调事项。\n以下数据未获取，已记录信息缺口。\n"
        )
        r = self._gate(body + disc)._check_so_what_chain()
        assert r.passed, f"score={r.score} detail={r.details}"


# ── cross_industry agency 豁免 ───────────────────────────────


class TestAgencyExemption:
    def test_battery_sne_exempt(self):
        # 电池行业报告引用 SNE Research 合法（豁免清单）
        import json

        markers = json.loads((_ROOT / "data" / "cross_industry_markers.json").read_text(encoding="utf-8"))
        exempt = markers.get("agency_exemptions", {}).get("电池", [])
        assert "SNE Research" in exempt


# ── template_repeat 引导词内容判定 ────────────────────────────


class TestTemplateRepeatLeadWord:
    def test_different_content_ok(self):
        # "综合判断："后接内容各不相同 → 不计模板重复
        from pipeline.iron_gate import IronGate

        body = (
            "## 一、分部A。\n综合判断：储能业务利润贡献提升。因此估值切换。\n"
            "## 二、分部B。\n综合判断：海外收入占比提升。这意味着溢价扩大。\n"
            "## 三、现金流。\n综合判断：现金流质量改善。验证盈利真实性。\n"
        )
        # 前置足够的分析正文避免短文跳过
        body = "分析正文" * 200 + "\n" + body
        g = IronGate.from_text(body, report_type="earnings_notes", style="cicc", asset="测试")
        r = g._check_template_repeat()
        assert "综合判断" not in (r.details or ""), f"误判: {r.details}"

    def test_duplicated_content_caught(self):
        from pipeline.iron_gate import IronGate

        body = "## 一、分部A。\n综合判断：储能业务利润贡献提升。因此估值切换。\n"
        body = body * 2  # 完全重复
        body = "分析正文" * 200 + "\n" + body
        g = IronGate.from_text(body, report_type="earnings_notes", style="cicc", asset="测试")
        r = g._check_template_repeat()
        assert "综合判断" in (r.details or ""), "真重复未被检出"
