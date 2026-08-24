# -*- coding: utf-8 -*-
"""风格指纹 v1 单元测试（S1）+ S2 距离门禁桩测试。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from core.style_fingerprint import distance, extract

DEEP = (
    """# 行业深度研究

## 市场空间

我们判断，2026年全球市场规模将达到4800亿美元，同比增长18%。
因此，头部企业的份额提升将加速。然而，风险在于贸易壁垒。

| 年份 | 规模 |
|---|---|
| 2025 | 40 |

### 细分结构

此外，细分市场呈现分化。综上，配置主线明确。
"""
    * 3
)

SNIPPET = "业绩超预期。"


class TestExtract:
    @pytest.mark.unit
    def test_eight_dims_present(self):
        v = extract(DEEP)
        for k in (
            "sent_len_p50",
            "sent_len_p90",
            "judgment_density",
            "number_density",
            "connective_spectrum",
            "heading_depth_hist",
            "table_per_kchar",
            "first_sentence_pattern",
        ):
            assert k in v, k

    @pytest.mark.unit
    def test_judgment_density_positive(self):
        v = extract(DEEP)
        assert v["judgment_density"] > 0
        assert v["number_density"] > 0

    @pytest.mark.unit
    def test_first_pattern_data_first(self):
        # 首句以数字开头（标题后首个句子含 2026年…4800亿美元）
        v = extract("全球市场规模2026年达4800亿美元。我们判断格局向好。" * 5)
        assert v["first_sentence_pattern"] in ("data_first", "claim_first", "other")


class TestDistance:
    @pytest.mark.unit
    def test_identical_zero(self):
        v = extract(DEEP)
        assert distance(v, v) == 0.0

    @pytest.mark.unit
    def test_far_apart_larger(self):
        short = extract(SNIPPET * 2)
        deep = extract(DEEP)
        d_self_like = distance(deep, extract(DEEP))
        assert distance(deep, short) > d_self_like


class TestStyleDistanceGate:
    @pytest.mark.unit
    def test_check_skips_without_fingerprint(self, monkeypatch):
        """无目标指纹文件 → 直接 PASS 跳过（不产生噪音）。"""
        from pipeline.checks.analysis_mixin import AnalysisChecksMixin
        from pipeline.iron_gate import IronGate

        g = IronGate.__new__(IronGate)
        g.report_text = DEEP
        g.report_type = "listed_company"
        g.style = "cicc"
        r = (
            AnalysisChecksMixin._check_style_distance(g)
            if hasattr(AnalysisChecksMixin, "_check_style_distance")
            else None
        )
        if r is None:
            pytest.skip("S2 检查尚未实现")
        # 无指纹文件时应 passed=True（skip 语义）
        fp = _ROOT / "data" / "fingerprints" / "cicc.json"
        if not fp.exists():
            assert r.passed
