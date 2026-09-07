# -*- coding: utf-8 -*-
"""2026-09-07 茅台 E2E 事故回归测试：跨行业污染 + 标题/占位符。

覆盖三个修复：
1. section_writer._inject_report_header：强制正确标题（LLM 把组字母"A"写成
   "# A公司深度研究"）+ 清除未解析 {ref:...} 占位
2. 删除碳酸锂/锂电池硬编码模板后 section_writer 不残留该内容
3. IronGate 新增 _check_cross_industry_contamination：白酒报告含锂电池术语 → 拦截
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestReportHeaderEnforcement:
    def test_wrong_asset_title_replaced(self):
        """组字母误当资产名的标题（# A公司深度研究）被替换为真实资产名。"""
        from pipeline.section_writer import SectionWriter

        t = "# A公司深度研究：品牌驱动的社交货币引擎\n\n正文内容"
        r = SectionWriter._inject_report_header(t, "贵州茅台")
        first = r.split("\n")[0]
        assert first.startswith("# 贵州茅台深度研究")
        assert "A公司" not in first

    def test_correct_title_untouched(self):
        from pipeline.section_writer import SectionWriter

        t = "# 贵州茅台深度研究报告\n\n正文"
        r = SectionWriter._inject_report_header(t, "贵州茅台")
        assert r.split("\n")[0] == "# 贵州茅台深度研究报告"

    def test_unresolved_ref_placeholder_stripped(self):
        """_data_dict 缺 key 时残留的 {ref:...} 占位不得进入交付文本。"""
        from pipeline.section_writer import SectionWriter

        t = "# 贵州茅台深度研究\n\n2026E EPS {ref:consensus_eps_2026e} 元"
        r = SectionWriter._inject_report_header(t, "贵州茅台")
        assert "{ref:" not in r

    def test_non_first_line_title_fixed(self):
        """标题不在首行（前有决策门 preamble）时仍被修复。"""
        from pipeline.section_writer import SectionWriter

        t = "一、决策门判断：该标的值得深度分析。\n\n# A公司深度研究：品牌\n\n正文"
        r = SectionWriter._inject_report_header(t, "贵州茅台")
        assert "# 贵州茅台深度研究" in r
        assert r.count("A公司") == 0


class TestNoCarbonateFabrication:
    def test_section_writer_has_no_carbonate_template(self):
        """碳酸锂硬编码模板已从代码删除（不再污染任何标的）。"""
        t = (_ROOT / "pipeline" / "section_writer.py").read_text(encoding="utf-8")
        # 仅允许注释/说明中的提及（如移除记录），禁止活动模板代码
        active = [ln for ln in t.splitlines() if "碳酸锂" in ln or "SMM 2026" in ln or "单 Wh" in ln or "单Wh" in ln]
        # 活动代码行（非 # 注释、非纯字符串说明）应为空
        fabricating = [
            ln
            for ln in active
            if not ln.lstrip().startswith("#") and ('f"' in ln or "f'" in ln or "template" in ln.lower())
        ]
        assert not fabricating, f"仍存在活动碳酸锂模板: {fabricating}"


class TestCrossIndustryContamination:
    def _make(self, asset, text):
        from pipeline.checks.data_quality_mixin import DataQualityChecksMixin

        m = DataQualityChecksMixin.__new__(DataQualityChecksMixin)
        m.report_text = text
        m.asset = asset
        m.collected_data = {}
        return m

    def _pad(self):
        return "背景段落，行业格局与公司地位讨论。营收利润持续增长，估值合理。\n\n" * 20

    def test_baijiu_report_with_lithium_terms_flagged(self):
        """白酒报告被注入锂电池论证（茅台 E2E 事故形态）→ 拦截。"""
        m = self._make(
            "贵州茅台",
            "市场担忧碳酸锂价格反弹压缩单Wh利润，据SMM周报。茅台长协锁定60%成本。\n\n" * 3 + self._pad(),
        )
        r = m._check_cross_industry_contamination()
        assert r.passed is False
        assert "白酒" in r.details and "碳酸锂" in r.details

    def test_clean_baijiu_report_passes(self):
        """纯白酒内容（本行业术语）→ 不误报。"""
        m = self._make(
            "贵州茅台",
            "批价企稳回升，五粮液泸州老窖汾酒竞争清晰，经销商打款积极。酱香基酒产能。\n\n" * 3 + self._pad(),
        )
        r = m._check_cross_industry_contamination()
        assert r.passed is True

    def test_battery_report_own_terms_pass(self):
        """宁德时代谈碳酸锂/电芯是本行业 → 不误报。"""
        m = self._make(
            "宁德时代",
            "碳酸锂价格影响电芯成本，SMM周报跟踪长协订单，动力电池出货放量。\n\n" * 3 + self._pad(),
        )
        r = m._check_cross_industry_contamination()
        assert r.passed is True

    def test_check_registered_in_irongate(self):
        """新检查已注册进 IronGate 检查链。"""
        from pipeline.iron_gate import IronGate

        assert hasattr(IronGate, "_check_cross_industry_contamination")
