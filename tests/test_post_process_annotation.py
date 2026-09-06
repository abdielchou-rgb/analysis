# -*- coding: utf-8 -*-
"""R85+ post-process %注解污染回归测试（2026-09-06 茅台 E2E 实测修复）。

事故：section_writer._post_process_for_gate 第 6 步"数值百分比上下文"对任何未被
30 字内业务词跟随的 % 插注解，把评级定义表"涨幅15%以上"插成
"涨幅15%（此水平较同业中位数明显领先，验证成本优势传导）以上"、把区间
"5%-15%"拆烂——全报告 57 处机械注解污染（template_phrases error）+
数值区间拆烂（indicator_consistency 误报）。

修复后策略：表格行不处理 / 后 45 字有业务词不处理 / 后随括注不处理 /
前 20 字已有业务含义不处理。仅真正的孤立裸 % 才补短注解。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _post(text: str) -> str:
    from pipeline.section_writer import SectionWriter

    sw = SectionWriter.__new__(SectionWriter)
    sw._attempt_num = 0
    return sw._post_process_for_gate(text, "贵州茅台", patch_chain=True)


class TestPctAnnotationGuard:
    def test_table_row_untouched(self):
        """评级/假设表行（| 开头）不插注解——boilerplate 非正文。"""
        t = "| 买入 | 未来6-12个月相对基准指数涨幅15%以上 |"
        assert _post(t) == t

    def test_range_untouched(self):
        """数值区间（5%-15%）不被拆烂插注解。"""
        t = "估值中枢下修，涨幅5%-15%区间震荡。"
        assert _post(t) == t

    def test_preceding_context_untouched(self):
        """% 前 20 字已有业务含义（增速/涨幅/率）→ 不补（"增速转负至-5%"）。"""
        t = "中报净利润首度下滑，增速转负至-5%，渠道改革进入阵痛期。"
        assert _post(t) == t

    def test_following_bizword_untouched(self):
        """% 后跟业务词（以上/占比）→ 不补。"""
        t = "高分红率叠加几乎为零的有息负债，派现比例75%以上。"
        assert _post(t) == t

    def test_no_repeat_annotation_on_clean_prose(self):
        """正常带含义正文不含任何黑名单注解句。"""
        from core.template_blacklist import scan

        t = (
            "# 测试\n\n"
            "## 财务\n"
            "毛利率提升至92.23%，ROE维持30%以上，处于历史高位。\n\n"
            "## 估值\n"
            "DCF目标价1950.27元，相对当前价上行30.0%。"
        )
        out = _post(t)
        r = scan(out)
        assert r["total_exact"] == 0, f"不应产生模板注解: {r['exact_hits']}"
