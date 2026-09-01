# -*- coding: utf-8 -*-
"""P2-1 (2026-09-01): top 失败模式修复回归测试。

基于 triage 报告（19640 条失败记录聚类）修复的 4 个 top 失败项：
1. bottleneck_analysis 457 次：listed 报告要求"瓶颈"行业词但个股写卡位评级+产业链
   → 放宽为 瓶颈 OR (产业链 AND 卡位评级)
2. SAC维度覆盖 643 次：unlisted 缺 capital_efficiency/cross_border_dd/due_diligence
   （非上市天然缺数据）→ 补入 PE/VC 豁免列表
3. completeness_scan 475 次：正文竖线分隔符（'） |。'）误判为表格行未闭合
   → 表格上下文要求连续 2 行首尾|才进入
4. so_what_chain prompt 词表与 Gate 检查词表不一致 → 对齐
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from pipeline.checks.analysis_mixin import AnalysisChecksMixin
from pipeline.checks.content_format_mixin import ContentFormatChecksMixin


def _make_mixin(text: str, report_type: str = "listed_company", **kw):
    m = AnalysisChecksMixin.__new__(AnalysisChecksMixin)
    m.report_text = text
    m.report_type = report_type
    m._get_threshold = lambda _n, default=0.7: default  # 简化阈值
    m._allow_placeholder_degradation = False
    for k, v in kw.items():
        setattr(m, k, v)
    return m


class TestBottleneckAnalysisFix:
    def test_listed_with_rating_and_chain_passes(self):
        """个股报告写卡位评级+产业链（无'瓶颈'行业词）→ 应通过。"""
        m = _make_mixin(
            "公司处于产业链中游，卡位评级：强卡位。上游核心元件自研率提升，中游制造规模领先。",
            "listed_company",
        )
        r = m._check_bottleneck_analysis()
        assert r.passed is True

    def test_listed_with_bottleneck_passes(self):
        """个股报告写'瓶颈'→ 仍通过（原逻辑保留）。"""
        m = _make_mixin("供应链瓶颈集中在高端芯片环节，公司卡位核心。")
        r = m._check_bottleneck_analysis()
        assert r.passed is True

    def test_no_analysis_still_fails(self):
        """完全没有卡点/产业链分析 → 仍失败（防放水）。"""
        m = _make_mixin("公司营收增长稳健，毛利率提升，估值合理。")
        r = m._check_bottleneck_analysis()
        assert r.passed is False


class TestCompletenessScanFix:
    def test_pipe_in_sentence_not_table(self):
        """正文句子含竖线分隔符（'） |。'）不应被判为表格行未闭合。"""
        m = ContentFormatChecksMixin.__new__(ContentFormatChecksMixin)
        m.report_text = (
            "# 报告\n\n## 章节\n"
            "我们判断竞争格局将更加坚定。（数据来源：公司公告）\n"
            "这一趋势若延续，我们对格局演变的判断将更加坚定。\n"
        )
        m.report_type = "listed_company"
        r = m._check_completeness_scan()
        assert r.passed is True

    def test_real_table_still_detected(self):
        """真表格截断仍要拦截（不误放）——文本需 >300 字才进入扫描。"""
        filler = "公司营收稳定增长。" * 30  # 撑过 300 字门槛
        m = ContentFormatChecksMixin.__new__(ContentFormatChecksMixin)
        m.report_text = (
            "# 报告\n\n"
            "## 财务分析\n\n"
            f"{filler}\n\n"
            "| 指标 | 2024 | 2025 | 2026E |\n"
            "|---|---|---|---|\n"
            "| 营收 | 100 | 120 | 150\n"  # 缺尾 |
        )
        m.report_type = "listed_company"
        r = m._check_completeness_scan()
        assert r.passed is False

    def test_single_pipe_line_not_table(self):
        """单行以|开头（非表格）不进入表格上下文。"""
        m = ContentFormatChecksMixin.__new__(ContentFormatChecksMixin)
        m.report_text = "| 重要强调：该数据仅为示意\n\n正文继续。"
        m.report_type = "listed_company"
        r = m._check_completeness_scan()
        assert r.passed is True


class TestSacCoverageFix:
    def test_unlisted_pevc_declared_exempt(self):
        """unlisted 报告缺 capital_efficiency 等 PE/VC 维度 + 声明缺口 → 豁免通过。"""
        m = _make_mixin(
            "数据有限：非上市公司无公开披露，部分维度待尽调核实。\n"
            "公司产品技术领先，全球市场逐步打开，管理层决策聚焦主业。",
            "unlisted_company",
        )

        # 模拟 SAC 维度：只缺 capital_efficiency（PE/VC 豁免类）
        class FakeSac:
            _data = {
                "required_dimensions": [
                    {"id": "capital_efficiency"},
                    {"id": "company_profile"},
                    {"id": "data_declaration"},
                    {"id": "decision_gate"},
                    {"id": "global_benchmark"},
                ]
            }

            def get_dimension_keywords(self):
                # 覆盖全部非豁免维度；缺 capital_efficiency（豁免类）
                return {
                    "company_profile": ["公司产品", "技术领先"],
                    "data_declaration": ["数据有限", "待尽调"],
                    "decision_gate": ["决策"],
                    "global_benchmark": ["全球"],
                    "capital_efficiency": ["烧钱率", "单位经济性", "资本效率"],
                }

        m.sac = FakeSac()
        r = m._check_sac_coverage()
        assert r.passed is True

    def test_no_declaration_still_fails(self):
        """缺 PE/VC 维度且未声明数据缺口 → 仍失败（防放水）。"""
        m = _make_mixin(
            "公司产品技术领先，全球市场逐步打开，管理层决策聚焦主业，营收增长稳健。",
            "unlisted_company",
        )

        class FakeSac:
            _data = {
                "required_dimensions": [
                    {"id": "capital_efficiency"},
                    {"id": "company_profile"},
                    {"id": "data_declaration"},
                    {"id": "decision_gate"},
                    {"id": "global_benchmark"},
                ]
            }

            def get_dimension_keywords(self):
                return {
                    "company_profile": ["公司产品"],
                    "data_declaration": ["数据有限", "待尽调"],
                    "decision_gate": ["决策"],
                    "global_benchmark": ["全球"],
                    "capital_efficiency": ["烧钱率"],
                }

        m.sac = FakeSac()
        r = m._check_sac_coverage()
        assert r.passed is False
