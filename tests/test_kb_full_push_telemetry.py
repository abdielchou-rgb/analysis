# -*- coding: utf-8 -*-
"""2026-09-07 全量推进回归：KB/MKB 观测漏斗 + MKB 无标签兜底 + 噪声过滤。

覆盖 docs/CODEX_SELF_AUDIT_20260907.md §6 三项可单测的推进：
1. _count_injection_blocks 与写作侧截断同口径（防虚报注入条数）；
2. _inj_mkb_str 在行业标签缺失时走报告类型通用兜底（此前整块为空）；
3. 兜底召回须过滤 backtest_gold 的宏观/固收噪声标题。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.section_writer import SectionWriter, _count_injection_blocks


def _mkb_json_dir(tmp_path, monkeypatch, entries_by_cat):
    import json as _json

    import core.methodology_kb as mk

    fp = tmp_path / "methodology_knowledge_base.json"
    fp.write_text(_json.dumps(entries_by_cat, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(mk, "_FILE", fp)
    return fp


def _mkb_entry(title, seed=""):
    body = "实质性程序与三表勾稽复核、估值与盈利预测检验说明，" * 140
    return {
        "title": title,
        "topic": f"方法论主题{seed}",
        "methods": body,
        "judgment_signals": "判断信号与阈值，" * 120,
        "summary": "摘要与落地要点，" * 150,
    }


# ── 1. 注入条数统计（与写作侧截断同口径）────────────────────


def test_count_injection_blocks_counts_markers_after_truncation():
    kb = (
        "## [知识库参考] 头部说明。\n[KB1] 来源: 四大审计/收入审计\n方法论内容……" * 60  # 撑到超过 1500 字
    )
    mkb = (
        "## [方法论知识库精选] 头部。\n[MKB1] 方法条目一\n 摘要: 内容……" * 90  # 撑到超过 2000 字
    )
    m = _count_injection_blocks(kb, mkb)
    assert m["kb_count"] >= 1 and m["mkb_count"] >= 1
    assert m["kb_count"] == len(m["kb_ids"])
    assert m["mkb_count"] == len(m["mkb_ids"])
    # 截断同口径：全文条数应 >= 截断后可见条数（即统计不高估）
    full_kb_count = sum(1 for _ in __import__("re").finditer(r"\[KB\d+\]", kb))
    full_mkb_count = sum(1 for _ in __import__("re").finditer(r"\[MKB\d+\]", mkb))
    assert m["kb_count"] <= full_kb_count
    assert m["mkb_count"] <= full_mkb_count


def test_count_injection_blocks_empty_when_no_markers():
    m = _count_injection_blocks("无标记文本", "")
    assert m == {"kb_count": 0, "mkb_count": 0, "kb_ids": [], "mkb_ids": []}


# ── 2. MKB 行业标签缺失 → 报告类型通用兜底（非空且克制）──────


def test_inj_mkb_fallback_when_no_industry_tags(tmp_path, monkeypatch):
    """无 industry_tags 时 _inj_mkb_str 不再返回空块（真实库探针的盲区）。"""
    data = {
        "valuation_models": [
            _mkb_entry("DCF模型估值非上市公司应用", "a"),
            _mkb_entry("可比公司估值方法", "b"),
        ],
        "backtest_gold": [_mkb_entry("2024年春季建材行业投资策略估值修复", "c")],
    }
    _mkb_json_dir(tmp_path, monkeypatch, data)
    from pipeline.prompt_injectors_p3b import _inj_mkb_str

    out = _inj_mkb_str(
        {
            "asset": "贵州茅台",
            "report_type": "listed_company",
            "data_context": {},  # 无 biz_model.industry_tags
        }
    )
    assert "## [方法论知识库精选]" in out, "行业标签缺失时 MKB 兜底仍为空"
    assert "[MKB1]" in out, "兜底召回未产出条目"
    assert len(out) <= 2000, f"兜底块 {len(out)} 字超写作侧上限"


def test_inj_mkb_noise_filter_blocks_fixed_income_titles(tmp_path, monkeypatch):
    """兜底召回过滤"债券/固收/基金持仓"噪声（真实库实证混入源）。"""
    data = {
        "backtest_gold": [
            _mkb_entry("2024年利率债中期策略报告：债券供需与央行缩表", "noise"),
            _mkb_entry("2024年春季建材行业投资策略：估值修复可期", "eq"),
        ],
        "valuation_models": [_mkb_entry("DCF模型估值非上市公司应用", "clean")],
    }
    _mkb_json_dir(tmp_path, monkeypatch, data)
    from pipeline.prompt_injectors_p3b import _inj_mkb_str

    out = _inj_mkb_str(
        {
            "asset": "贵州茅台",
            "report_type": "listed_company",
            "data_context": {},
        }
    )
    assert "DCF模型估值非上市公司应用" in out
    assert "债券供需" not in out, "固收/债券噪声标题混入兜底召回"
    assert "央行缩表" not in out, "宏观噪声标题混入兜底召回"


def test_inj_mkb_keeps_industry_tag_path_unfiltered(tmp_path, monkeypatch):
    """有行业标签时不走通用兜底、不做噪声过滤（真实行业召回不被误杀）。"""
    data = {
        "backtest_gold": [
            _mkb_entry("2024年锂电行业年度策略：变局之下静待格局重塑", "li"),
            _mkb_entry("2024年利率债中期策略报告", "fi"),
        ]
    }
    _mkb_json_dir(tmp_path, monkeypatch, data)
    from pipeline.prompt_injectors_p3b import _inj_mkb_str

    out = _inj_mkb_str(
        {
            "asset": "宁德时代",
            "report_type": "listed_company",
            "data_context": {"biz_model": {"industry_tags": ["锂电"]}},
        }
    )
    assert "锂电行业年度策略" in out, "行业标签召回丢失"
    assert "[MKB1]" in out


# ── 3. SectionWriter 记录实际注入条数（供 e2e→IronGate 强检查）──


_KB_FAKE = (
    "## [知识库参考] 参考块\n"
    "[KB1] 来源: 四大审计方法论\n审计与勾稽复核步骤……\n"
    "[KB2] 来源: 国际投行方法论\n估值逻辑闭环……\n"
    "[KB3] 来源: 宏观分析框架\n周期判断……"
)
_MKB_FAKE = (
    "## [方法论知识库精选] 精选块\n"
    "[MKB1] 估值模型条目一\n 方法: 折现现金流……\n"
    "[MKB2] 盈利预测复核条目\n 摘要: 偏差检验……"
)


def test_serial_kb_mkb_records_injection_metrics(monkeypatch):
    """串行 _kb_mkb_for 调用后，writer 记录与截断同口径的注入条数。"""
    import pipeline.prompt_injectors_p3b as p3b

    monkeypatch.setattr(p3b, "_inj_kb_str", lambda ctx: _KB_FAKE)
    monkeypatch.setattr(p3b, "_inj_mkb_str", lambda ctx: _MKB_FAKE)
    w = SectionWriter(report_type="listed_company")
    kb, mkb = w._kb_mkb_for("测试标的")
    assert w._kb_injection_metrics == {"kb_count": 3, "mkb_count": 2}, w._kb_injection_metrics
    assert w._kb_injection_last_ids == {"kb": [1, 2, 3], "mkb": [1, 2]}
    assert kb and mkb


def test_parallel_injection_counts_recorded_via_block_stats(monkeypatch):
    """并行路径 build_injections 产出的块被统计（防 e2e 拿不到计数）。"""
    # 契约：任何注入块，计数函数必须与"写入 prompt 的截断后内容"同口径。
    # 并行路径统计的是 build_injections 返回的 kb_str/mkb_str（block 统计），
    # 与串行 _kb_mkb_for 统计一致（同一对函数 + 同一截断）。
    w = SectionWriter(report_type="listed_company")
    kb, mkb = w._kb_mkb_for("测试标的")
    m = _count_injection_blocks(kb, mkb)
    # 序列化块若无标记则计数为 0；有标记则与 writer 记录一致。
    if m["kb_count"] or m["mkb_count"]:
        assert w._kb_injection_metrics == {"kb_count": m["kb_count"], "mkb_count": m["mkb_count"]}
    else:
        assert w._kb_injection_metrics == {"kb_count": 0, "mkb_count": 0}


# ── 4. e2e 写节点 → context → validate 强检查的接线回归 ─────────


def test_record_kb_injection_metrics_writes_context_keys():
    """e2e 写节点成功路径把实际注入条数写进 context（validate 消费源）。"""
    from pipeline.e2e_orchestrator import _record_kb_injection_metrics

    class _FakeSW:
        _kb_injection_metrics = {"kb_count": 7, "mkb_count": 4}
        _kb_injection_last_ids = {"kb": [1, 3, 5], "mkb": [2]}

    ctx: dict = {}
    _record_kb_injection_metrics(ctx, _FakeSW())
    assert ctx["kb_injection_metrics"] == {
        "kb_injected": 7,
        "mkb_injected": 4,
        "kb_retrieved": 0,
        "mkb_retrieved": 0,
        "kb_ids": [1, 3, 5],
        "mkb_ids": [2],
    }


def test_write_sections_records_metrics_on_success_path_only():
    """AST 回归：P1-3 观测调用不得落进 except 内 raise 之后的死代码区。

    2026-09-07 实测回归：kb_injection_metrics 写入块连同 report_text 赋值被
    误缩进到 except RuntimeError 内（raise 之后不可达）→ context 永远无计数
    → validate 的 set_kb_injection_counts 恒为 0 → Gate 只跑弱检查。
    """
    import ast as _ast

    src = (_ROOT / "pipeline" / "e2e_orchestrator.py").read_text(encoding="utf-8")
    tree = _ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, _ast.ClassDef) and n.name == "E2ENodes")
    fn = next(n for n in cls.body if isinstance(n, _ast.FunctionDef) and n.name == "write_sections")

    total_calls: list[_ast.AST] = []
    in_handler_calls: list[_ast.AST] = []

    def _walk(node: _ast.AST, inside_handler: bool) -> None:
        if isinstance(node, _ast.ExceptHandler):
            inside_handler = True
        for child in _ast.iter_child_nodes(node):
            if isinstance(child, _ast.Call) and getattr(child.func, "id", "") == "_record_kb_injection_metrics":
                total_calls.append(child)
                if inside_handler:
                    in_handler_calls.append(child)
            _walk(child, inside_handler)

    _walk(fn, False)
    assert total_calls, "write_sections 未调用 _record_kb_injection_metrics"
    assert not in_handler_calls, "观测调用落在 except 死区，Gate 强检查将永远空跑"
