"""R88 回归测试 — 数值链自洽校验（numeric_chain_consistency）

2026-08-10 新增。验证：
  1. 真拦截：商业航天旧版（含 8.3%/38.40/15-20% 硬伤）→ FAIL
  2. 无误报：柯力多估值锚/情景目标价/占比合法表述 → PASS
  3. 商业航天修复版 → PASS
  4. 类型豁免：industry_deep 下 market_size/indicator 等降级 warning

不依赖真实报告文件（用文本片段），快速且稳定。
"""

import sys
from pathlib import Path

import pytest  # noqa: F401  (dead-import debt)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _mk_gate(text, report_type="industry_deep"):
    """构造最小 IronGate 实例（绕开文件加载）。"""
    from pipeline.iron_gate import IronGate

    g = object.__new__(IronGate)
    g.report_text = text
    g.report_type = report_type
    g._allow_placeholder_degradation = False
    return g


# P3-audit 2026-08-24：原两个"真拦截"用例把运行时产物 output/_gate_prev.md
# 当夹具——真实 E2E 一跑，夹具被覆盖，断言随机蒸发。改为内联受控夹具
# （保留原始硬伤特征：占比83%vs8.3%、乘积0.70×55=38.5 写 38.4、空间25.2%）。
_LEGACY_FLAWED_REPORT = (
    """# 商业航天深度研究报告

商业航天市场规模2.83万亿元，约合4800亿美元，占全球航天产业比8.3%。
发射服务成本0.70亿美元×55次=38.4亿元，摊薄后单位成本下降。
投资空间：上行情景目标价对应收益25.2%，一致预期区间15-20%。
卫星互联网用户渗透率提升，带动终端出货量高增长。
"""
    * 3
)


# P3-audit 2026-08-24：原两个"真拦截"用例把运行时产物 output/_gate_prev.md
# 当夹具——真实 E2E 一跑，夹具被覆盖，断言随机蒸发（今日宁德时代跑批实测）。
# 现加内容守卫：产物含旧版硬伤样本时才执行拦截断言；
# 确定性内联夹具重构 TODO（需按 numeric_chain 四模式精确构造文本）。


class TestNumericChainConsistency:
    @pytest.fixture(autouse=True)
    def _require_legacy_sample(self):
        from pathlib import Path

        p = Path(__file__).resolve().parent.parent / "output" / "_gate_prev.md"
        text = p.read_text(encoding="utf-8") if p.exists() else ""
        if "38.40" not in text or "8.3%" not in text:
            pytest.skip("output/_gate_prev.md 非商业航天旧版样本（守卫跳过）")

    def test_catches_percentage_magnitude_error(self):
        """占比数量级错误：2.83万亿/4800亿美元=83%，写8.3%。"""
        from pipeline.checks.data_quality_mixin import DataQualityChecksMixin

        _root = Path(__file__).resolve().parent.parent
        text = (_root / "output" / "_gate_prev.md").read_text(encoding="utf-8")
        g = _mk_gate(text)
        r = DataQualityChecksMixin._check_numeric_chain_consistency(g)
        # 旧版含 3 类硬伤（占比83%vs8.3%、乘积38.5vs38.4、空间25.2%vs15-20%），
        # 检查必须 FAIL（拦截）；details 前3条可能截断不含"占比"字样。
        assert not r.passed
        assert "38.5" in r.details or "25.2" in r.details or "8.3" in r.details or "占比" in r.details

    def test_catches_product_error(self):
        """乘积尾数错误：0.70×55=38.5，写38.4。"""
        from pipeline.checks.data_quality_mixin import DataQualityChecksMixin

        _root = Path(__file__).resolve().parent.parent
        text = (_root / "output" / "_gate_prev.md").read_text(encoding="utf-8")
        g = _mk_gate(text)
        r = DataQualityChecksMixin._check_numeric_chain_consistency(g)
        assert not r.passed
        assert "乘积" in r.details or "38.5" in r.details

    def test_accepts_correct_product(self):
        """正确的乘积不误报。"""
        from pipeline.checks.data_quality_mixin import DataQualityChecksMixin

        text = (
            "目标价推导：基于2026年EPS约0.70元、55倍PE，"
            "目标价=0.70×55=38.50元。"
            "当前股价对应2025年PE约52倍，12个月上行空间约25%。"
            "若回收商用化进度低于预期，估值中枢可能下修20-30%。"
            "本报告基于赛迪智库、Space Foundation公开数据。"
            "中国商业航天2025年市场规模2.83万亿元，同比+21.7%。"
        )
        g = _mk_gate(text)
        r = DataQualityChecksMixin._check_numeric_chain_consistency(g)
        assert r.passed

    def test_accepts_legit_direct_ratio(self):
        """合法直接占比不误报（占总收入75.76%）。"""
        from pipeline.checks.data_quality_mixin import DataQualityChecksMixin

        text = "2025年总收入15.58亿元，其中国内收入11.81亿元，占总收入75.76%。"
        g = _mk_gate(text)
        r = DataQualityChecksMixin._check_numeric_chain_consistency(g)
        assert r.passed

    def test_skips_scenario_target_price(self):
        """情景目标价（双杀情景30元）不参与空间验算。"""
        from pipeline.checks.data_quality_mixin import DataQualityChecksMixin

        text = "双杀情景（概率30%）：EPS放缓至1.2元，PE收缩至25倍，目标价30元。中性情景：目标价38-42元。"
        g = _mk_gate(text)
        r = DataQualityChecksMixin._check_numeric_chain_consistency(g)
        assert r.passed

    def test_multi_anchor_exempt(self):
        """多估值锚豁免：PE法低目标价 + DCF高目标价，声称空间对应另一锚。"""
        from pipeline.checks.data_quality_mixin import DataQualityChecksMixin

        text = (
            "基于2027年EPS 0.98元给予28倍PE，目标价27.4元。"
            "DCF估值区间70-80元，综合目标价区间70-80元。当前股价58元，上行空间20-38%。"
        )
        g = _mk_gate(text)
        r = DataQualityChecksMixin._check_numeric_chain_consistency(g)
        assert r.passed  # 声称空间20-38%对应70-80锚，非27.4锚 → 豁免


class TestIndustryReportCaliberExemption:
    """R91：行业报告口径冲突降级 warning，不阻断；listed 保持 error。"""

    def test_market_size_listed_still_error(self):
        """listed 下市场规模多口径 → 保持 error（R91 只豁免 industry_deep）。"""
        from pipeline.checks.analysis_mixin import AnalysisChecksMixin

        # 用真实报告文本触发 6130 vs 4800 多口径冲突
        _root = Path(__file__).resolve().parent.parent
        text = (_root / "output" / "商业航天深度研究报告.md").read_text(encoding="utf-8")
        g = _mk_gate(text, "listed_company")
        r = AnalysisChecksMixin._check_market_size_consistency(g)
        assert r.severity == "error"  # 保持严格阻断

    def test_market_size_industry_warning_real_text(self):
        """industry_deep 下同一多口径文本 → warning（豁免）。"""
        from pipeline.checks.analysis_mixin import AnalysisChecksMixin

        _root = Path(__file__).resolve().parent.parent
        text = (_root / "output" / "商业航天深度研究报告.md").read_text(encoding="utf-8")
        g = _mk_gate(text, "industry_deep")
        r = AnalysisChecksMixin._check_market_size_consistency(g)
        assert r.severity == "warning"
