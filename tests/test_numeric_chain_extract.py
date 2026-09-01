# -*- coding: utf-8 -*-
"""P4-3 (2026-09-01): 巨石拆解 characterization test——numeric_chain 迁移等价性。

Strangler Fig 纪律：拆出后行为必须不变（golden 报告 diff 为空）。
用三类文本验证：
1. 合法文本 → 通过
2. 含算术硬伤（占比数量级错/乘积尾数错）→ 拦截
3. 等价性：data_quality_mixin 委托调用 与 numeric_chain 独立函数 结果一致
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from pipeline.checks.numeric_chain import check_numeric_chain_consistency

# 真实历史硬伤样本（对齐 test_r88 的完整上下文——校验器需要完整句结构触发）
_TAM_ERROR = (
    "目标价推导：基于2026年EPS约0.70元、55倍PE，目标价=0.70×55=38.40元。"
    "中国商业航天2025年市场规模2.83万亿元，同比+21.7%。"
    "按当前汇率（约7.1）折算，中国占全球商业航天市场约8.3%。"
    "当前股价对应2025年PE约52倍，12个月上行空间约15-20%。"
)
_PRODUCT_ERROR = (
    "目标价推导：基于2026年EPS约0.70元、55倍PE，目标价=0.70×55=38.40元。"
    "本报告基于赛迪智库、Space Foundation公开数据。"
    "中国商业航天2025年市场规模2.83万亿元，同比+21.7%。"
)
_LEGIT = (
    "公司2024年营收15.58亿元，同比增长20.4%，毛利率34.5%。"
    "行业处于成长期，我们判断景气度持续。"
    "2025年总收入15.58亿元，其中国内收入11.81亿元，占总收入75.76%。"
)


class TestNumericChainExtracted:
    def test_legit_text_passes(self):
        r = check_numeric_chain_consistency(_LEGIT * 20)  # 撑过 300 字
        assert r.passed is True

    def test_tam_error_blocked(self):
        r = check_numeric_chain_consistency(_TAM_ERROR * 20)
        assert r.passed is False

    def test_product_error_blocked(self):
        r = check_numeric_chain_consistency(_PRODUCT_ERROR * 20)
        assert r.passed is False

    def test_short_text_skipped(self):
        r = check_numeric_chain_consistency("短文本")
        assert r.passed is True  # 短文本跳过

    def test_delegation_equivalent(self):
        """data_quality_mixin 委托调用与独立函数结果一致。"""
        from pipeline.checks.data_quality_mixin import DataQualityChecksMixin

        m = DataQualityChecksMixin.__new__(DataQualityChecksMixin)
        m.report_text = _TAM_ERROR * 20
        direct = check_numeric_chain_consistency(_TAM_ERROR * 20)
        delegated = m._check_numeric_chain_consistency()
        assert delegated.passed == direct.passed
