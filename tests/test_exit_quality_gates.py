# -*- coding: utf-8 -*-
"""P2-4 / P0-2 (2026-09-01): 出口质量红线测试——乱码/裸来源锚点拦截。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from pipeline.checks.base import GateCheckResult
from pipeline.checks.content_format_mixin import ContentFormatChecksMixin


def _make_mixin(text: str):
    """构造最小 mixin 实例（只带 report_text）。"""
    mixin = ContentFormatChecksMixin.__new__(ContentFormatChecksMixin)
    mixin.report_text = text
    return mixin


class TestGbkEncoding:
    def test_clean_text_passes(self):
        m = _make_mixin("# 正常报告\n\n核心判断：买入。数据来源：2025年年报。")
        r = m._check_gbk_encoding()
        assert r.passed is True

    def test_replacement_char_blocked(self):
        m = _make_mixin("报告正文出现�替换字符")
        r = m._check_gbk_encoding()
        assert r.passed is False
        assert r.severity == "error"

    def test_gbk_mojibake_blocked(self):
        # 审计实测：'æµæ±è§çº¤' 是 '浙江觉纤' 的 GBK 乱码形态
        m = _make_mixin("标的名称：æµæ±è§çº¤，业绩增长")
        r = m._check_gbk_encoding()
        assert r.passed is False

    def test_control_chars_blocked(self):
        m = _make_mixin("正文\x00\x01含控制字符")
        r = m._check_gbk_encoding()
        assert r.passed is False


class TestPlaceholderSource:
    def test_clean_source_passes(self):
        m = _make_mixin("目标价 38.40 元（数据来源：公司2025年年度报告，2026-03-28）")
        r = m._check_placeholder_source()
        assert r.passed is True

    def test_bare_company_source_blocked(self):
        m = _make_mixin("目标价 38.40 元（数据来源：公司年度报告）")
        r = m._check_placeholder_source()
        assert r.passed is False
        assert r.severity == "error"

    def test_bare_generic_source_blocked(self):
        m = _make_mixin("营收 15 亿（来源：公开资料）")
        r = m._check_placeholder_source()
        assert r.passed is False

    def test_specific_source_not_blocked(self):
        m = _make_mixin("营收 15 亿（来源：Wind 一致预期）")
        r = m._check_placeholder_source()
        assert r.passed is True
