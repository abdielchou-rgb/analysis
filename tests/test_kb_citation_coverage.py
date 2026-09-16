"""P1-2 KB 引用覆盖检查测试（2026-09-07 收尾，验收报告 R4 修复项）。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.checks.kb_citation_mixin import check_kb_citation_coverage

# GateCheckResult 对 <300 字文本跳过评估；测试用长文本确保走到真实判定分支。
_PAD = "本公司是一家专注于核心业务的上市公司，主营产品覆盖多个细分领域。近年来营收保持稳健增长，毛利率维持在行业中等偏上水平，经营现金流健康。管理层在年报中披露了未来三年的战略规划，强调研发投入与技术壁垒建设。行业层面，下游需求稳步扩张，竞争格局相对清晰，头部企业份额持续提升。" * 3  # ~300+ 字

# 中性填充——不含任何方法论关键词，专用于"零痕迹应失败"用例
_PAD_NEUTRAL = "第一段经营叙述主要围绕主营业务收入与成本结构展开，数据来自定期披露文件，相关口径已在附注说明。第二段补充了资产负债表与现金流量表的主要项目变动及其原因，分析以已审阅财务资料为基础。第三段记录管理层对经营环境与后续安排的公开表述，内容未做进一步推断，仅作事实罗列以供参考。" * 3


def test_short_text_skipped():
    r = check_kb_citation_coverage("短文本", injected_kb_count=5)
    assert r.passed is True
    assert "skipped" in r.details


def test_no_injection_count_weak_check_fail():
    """无注入计数 + 正文无 KB/方法论痕迹 → 弱检查失败(warning)。"""
    text = _PAD_NEUTRAL
    r = check_kb_citation_coverage(text)
    assert r.passed is False
    assert r.severity == "warning"


def test_no_injection_count_weak_check_pass():
    text = _PAD + "我们用DCF折现分析了利润池与竞争格局，得出护城河判断。"
    r = check_kb_citation_coverage(text)
    assert r.passed is True


def test_injection_but_zero_citation_fails():
    """注入 5 条 KB 但正文 0 引用 → 强检查失败（文档 P1-2 的核心场景）。"""
    text = _PAD + "本报告分析了公司的收入与成本。经营数据如下表所示。"
    r = check_kb_citation_coverage(text, injected_kb_count=5, injected_mkb_count=0)
    assert r.passed is False
    assert "覆盖率" in r.details


def test_injection_with_citations_passes():
    text = _PAD + "据[KB1]宏观框架与[KB2]估值方法，结合[方法论:DCF]我们给出判断。"
    r = check_kb_citation_coverage(text, injected_kb_count=3, injected_mkb_count=1)
    assert r.passed is True


def test_error_mode_when_requested():
    text = _PAD + "本报告没有引用注入的方法论知识，只陈述经营事实。"
    r = check_kb_citation_coverage(text, injected_kb_count=4, mode="error")
    assert r.passed is False
    assert r.severity == "error"


# ── IronGate 接线回归（2026-09-07）：P1-2 从"独立纯函数"变为"门禁真跑" ──


def _iron_gate_text(methodology_hint: str) -> str:
    body = (
        "本公司是一家专注于核心业务的上市公司，主营产品覆盖多个细分领域。"
        "近年来营收保持稳健增长，毛利率维持在行业中等偏上水平，经营现金流健康。"
        "管理层在年报中披露了未来三年的战略规划，强调研发投入与技术壁垒建设。"
        "行业层面，下游需求稳步扩张，竞争格局相对清晰，头部企业份额持续提升。"
        "我们结合行业景气度与公司竞争力给出判断，具体测算见后文。"
    )
    return (body * 4) + methodology_hint


def test_iron_gate_runs_kb_citation_check():
    """kb_citation_coverage 已注册进 IronGate run_all（弱检查：无注入计数）。"""
    from pipeline.iron_gate import IronGate

    text = _iron_gate_text("我们用DCF折现模型与三表勾稽复核交叉验证了盈利预测。")
    gate = IronGate.from_text(text, report_type="listed_company")
    report = gate.run_all()
    names = {c.name for c in report.checks}
    assert "kb_citation_coverage" in names, "kb_citation_coverage 未注册进 run_all"
    row = next(c for c in report.checks if c.name == "kb_citation_coverage")
    assert row.passed is True, row.details
    assert row.severity == "warning", "弱检查应为 warning 级（不阻断）"


def test_iron_gate_strong_check_fails_when_injection_not_cited():
    """e2e 传入注入计数 → 正文 0 引用必须告警（文档 P1-2 核心场景）。"""
    from pipeline.iron_gate import IronGate

    text = _iron_gate_text("本报告陈述经营事实并给出数据表格。")
    gate = IronGate.from_text(text, report_type="listed_company")
    gate.set_kb_injection_counts(kb_count=5, mkb_count=3)
    r = gate._check_kb_citation_coverage()
    assert r.passed is False, r.details
    assert "覆盖率" in r.details


def test_iron_gate_strong_check_passes_when_cited():
    from pipeline.iron_gate import IronGate

    text = _iron_gate_text(
        "据[KB1]宏观框架与[KB2]审计复核方法，结合[KB3][KB4][KB5]估值与回测基线，"
        "并参考[MKB1][MKB2][MKB3]方法论精选，我们给出判断。"
    )
    gate = IronGate.from_text(text, report_type="listed_company")
    gate.set_kb_injection_counts(kb_count=5, mkb_count=3)
    r = gate._check_kb_citation_coverage()
    assert r.passed is True, r.details
