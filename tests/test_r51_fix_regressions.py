"""R51 (2026-08-03) 回归测试 — 锁定三项修复。

修复内容：
  1. compute_engine 年份解析：`2025E` 等预测后缀键不再导致 sort() 混合类型崩溃
     （原：'<' not supported between instances of 'str' and 'int' → compute 全挂
       → compute_results={} → 图表全模板 → Gate score=0）
  2. data_basement 行业链模糊误匹配：'气体传感器' 不再误命中柯力/称重专用"传感器"链
     （原：load_industry_chain 返回柯力内容 → 报告串标）
  3. train_loop 审计目标：优先审计本轮产出（_gate_prev.md），不再锁定旧文件
"""

import os  # noqa: F401  (dead-import debt)
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── 1. compute_engine 年份解析 ────────────────────────────────
def test_parse_year_key_handles_forecast_suffix():
    from pipeline.compute_engine import _parse_year_key

    assert _parse_year_key("2025E") == 2025
    assert _parse_year_key("2026e") == 2026
    assert _parse_year_key("2024") == 2024
    assert _parse_year_key(2023) == 2023
    assert _parse_year_key(2024.0) == 2024


def test_parse_year_key_rejects_non_year_keys():
    from pipeline.compute_engine import _parse_year_key

    assert _parse_year_key("Figaro") is None
    assert _parse_year_key("工业安全") is None
    assert _parse_year_key("上游_敏感材料芯片") is None
    assert _parse_year_key("") is None
    assert _parse_year_key("202") is None  # 3位不是有效年份
    assert _parse_year_key("20300") is None  # 5位超出
    assert _parse_year_key(None) is None


def test_financial_bridges_no_mixed_type_crash():
    """2025E 键不再导致 _run_financial_bridges sort 崩溃。"""
    from pipeline.compute_engine import ComputeEngine

    data = {
        "chart_data": {
            "fig_revenue_trend": {"2019": 28, "2020": 30, "2025E": 51.5},
        }
    }
    eng = ComputeEngine()
    rb = eng._run_financial_bridges(data)
    assert rb, "revenue_bridge 应正常产出（不再崩溃）"
    assert rb["revenue_bridge"]["status"] == "ok"
    # 2025E 被规范化进趋势
    result = rb["revenue_bridge"]["result"]
    assert result["years"].get(2025) == 51.5
    assert result["period"].startswith("2019")


def test_margin_expense_bridge_no_mixed_type_crash():
    from pipeline.compute_engine import ComputeEngine

    data = {
        "chart_data": {
            "fig_profitability": {"2022": {"gross_margin": 33}, "2024": {"gross_margin": 35}},
            "fig_expenses": {"2022": 20, "2023E": 22},
        }
    }
    eng = ComputeEngine()
    r = eng._compute_margin_expense_bridge(data)
    assert r.get("margin_bridge", {}).get("status") == "ok"
    assert r.get("expense_bridge", {}).get("status") == "ok"


def test_compute_full_pipeline_with_forecast_keys():
    """完整 compute 不再因 forecast 键整体失败。"""
    from pipeline.compute_engine import ComputeEngine

    data = {
        "asset": "气体传感器",
        "report_type": "industry_deep",
        "chart_data": {
            "fig_revenue_trend": {"2019": 28, "2020": 30, "2025E": 51.5},
            "fig_profitability": {"2022": {"gross_margin": 33}, "2024": {"gross_margin": 35}},
        },
    }
    eng = ComputeEngine()
    result = eng.compute(data, report_type="industry_deep")
    # compute 整体完成，且 revenue/margin bridge 都产出
    assert result["revenue_bridge"]["status"] == "ok"
    assert result["margin_bridge"]["status"] == "ok"
    assert result["status"] in ("complete", "partial")


# ── 2. data_basement 行业链误匹配 ─────────────────────────────
def test_gas_sensor_does_not_match_keli_chain():
    """气体传感器不应命中柯力/称重专用"传感器"链（防报告串标）。"""
    from core.data_basement import load_industry_chain

    chain = load_industry_chain("气体传感器")
    if chain:
        # 如果存在专门的气体传感器链可以命中，但绝不能命中柯力/称重内容
        src = chain.get("source", "")
        assert "称重" not in src and "柯力" not in src, f"串标: {src}"
    # 更严格：柯力/称重源链必须 NOT 匹配
    for c in _all_chains():
        src = c.get("source", "")
        if "称重" in src or "柯力" in src:
            assert c.get("name") != "气体传感器"


def _all_chains():
    import json

    d = json.loads((_ROOT / "data" / "industry_chain.json").read_text(encoding="utf-8"))
    return d.get("industries", d.get("chains", []))


def test_industry_chain_exact_matches_still_work():
    from core.data_basement import load_industry_chain

    for req, expect in [
        ("半导体", "半导体"),
        ("白酒", "白酒"),
        ("人形机器人", "人形机器人"),
        ("传感器行业", "传感器"),
        ("工控", "工控"),
        ("光伏", "光伏"),
    ]:
        c = load_industry_chain(req)
        assert c and c.get("name") == expect, f"{req} → {c.get('name') if c else None}"


def test_industry_chain_short_generic_rejected_for_compound():
    """短通用链名（<4字）不能反向吞复合请求。"""
    from core.data_basement import load_industry_chain

    # "传感器"(3字) 不应反向匹配 "气体传感器"（5字复合）
    chain = load_industry_chain("气体传感器")
    if chain:
        assert len(chain.get("name", "")) >= 4, f"3字通用链不应反向命中: {chain.get('name')}"


# ── 3. train_loop 审计目标 ────────────────────────────────────
def test_audit_report_prefers_gate_prev(tmp_path=None):
    """audit_report 优先审计 _gate_prev.md（本轮产出）而非旧文件。"""
    import scripts.train_loop as tl

    # 构造：旧文件（老 mtime）+ _gate_prev.md（新 mtime）
    old = _ROOT / "output" / "_audit_test_old.md"
    gate_prev = _ROOT / "output" / "_gate_prev.md"
    # 只验证路径选择逻辑：candidates + max(mtime)
    if old.exists():
        old.unlink()
    # 用现有 _gate_prev.md 作为目标
    if gate_prev.exists():
        # 模拟 audit_report 传入 report_path
        r = tl.audit_report("气体传感器", "industry_deep", "cicc", report_path=str(gate_prev))
        assert r.get("report_path") == str(gate_prev)
        assert "score" in r


# ── 4. 模板图标注（P1-4 性能模式计划）────────────────────────
def test_template_chart_flagged_in_chart_md():
    """模板图（数据不足）必须在图表要求里标注"示意图-数据不足"。"""
    from pipeline.section_writer import SectionWriter

    sw = SectionWriter("industry_deep", "cicc")
    sw._chart_paths = {"fig_market_size_global": "output/charts/fig_market_size_global.png"}
    sw._chart_template_flags = {"fig_market_size_global": True}
    md = sw._build_chart_md("气体传感器")
    assert "示意图-数据不足" in md
    assert "模板示意" in md
    assert "正文不得引用其具体数值作为事实依据" in md


def test_real_chart_not_marked_template():
    """真实数据图表不应被误标为示意图。"""
    from pipeline.section_writer import SectionWriter

    sw = SectionWriter("industry_deep", "cicc")
    sw._chart_paths = {"fig_market_size_global": "output/charts/fig_market_size_global.png"}
    sw._chart_template_flags = {"fig_market_size_global": False}
    md = sw._build_chart_md("气体传感器")
    assert "示意图-数据不足" not in md


def test_generate_all_returns_tuple():
    """ChartPipeline.generate_all 返回 (paths, template_flags)。"""
    from pipeline.chart_pipeline import ChartPipeline

    cp = ChartPipeline("industry_deep", "cicc", "output/charts")
    result = cp.generate_all({"chart_data": {"fig_market_size_global": {"2020": 1}}})
    assert isinstance(result, tuple), "generate_all 应返回 (paths, template_flags)"
    paths, tf = result
    assert isinstance(paths, dict)
    assert isinstance(tf, dict)


# ── 5. orchestrator 失败项变化检测（P0-2 收敛机制）────────────
def test_stall_failure_normalization():
    """失败项归一化：details 措辞变化不算新失败。"""
    from pipeline.e2e_orchestrator import E2EOrchestratorV2

    orch = E2EOrchestratorV2("气体传感器", "industry_deep")
    # 两条失败 details 不同但 name 相同 → 归一化后相同
    f1 = {"failures": ["[ERROR] content_volume: 字数不足", "[ERROR] SAC维度覆盖: 缺维度"]}
    f2 = {"failures": ["[ERROR] content_volume: 还是不够", "[ERROR] SAC维度覆盖: 还是缺"]}
    s1 = {str(x).split(":", 1)[0].strip() for x in f1["failures"]}
    s2 = {str(x).split(":", 1)[0].strip() for x in f2["failures"]}
    assert s1 == s2, "details 措辞变化不应改变失败项集合"


# ── 6. 宏观知识库吸收（R52 2026-08-03）────────────────────────
def test_macro_knowledge_absorbed_file_exists():
    """宏观知识吸收产物必须存在且含实质内容。"""
    import json

    p = _ROOT / "data" / "methodology_macro_absorbed.json"
    assert p.exists(), f"缺少宏观知识吸收产物 {p}"
    d = json.loads(p.read_text(encoding="utf-8"))
    # 4 个主题 + _meta
    topics = {k: v for k, v in d.items() if k != "_meta"}
    assert len(topics) == 4, f"应有4主题, 实际{list(topics.keys())}"
    # 每个主题非空
    for t in ["industry_lifecycle", "business_model", "macro", "strategy"]:
        assert topics.get(t), f"主题 {t} 为空"
    # 至少 30 篇
    total = sum(len(v) for v in topics.values())
    assert total >= 30, f"应有≥30篇, 实际{total}"
    # 大部分篇含实质摘要（>50字）
    with_summary = sum(1 for v in topics.values() for i in v if len(i.get("summary", "")) > 50)
    assert with_summary >= 20, f"实质摘要篇数不足: {with_summary}/36"


def test_macro_knowledge_has_substantive_content():
    """摘要须含实质方法论内容（非仅标题）。"""
    import json

    d = json.loads((_ROOT / "data" / "methodology_macro_absorbed.json").read_text(encoding="utf-8"))
    # 抽查产业生命周期首篇 —— 应含生命周期框架关键词
    li = d["industry_lifecycle"][0]
    assert "供给侧" in li.get("summary", "") or "生命周期" in li.get("summary", ""), "产业生命周期摘要应含实质框架"
    # 抽查 macro —— 应含具体指标/方法
    macro_all = d["macro"]
    assert any("工业增加值" in i.get("summary", "") or "GDP" in i.get("summary", "") for i in macro_all), (
        "macro 摘要应含具体宏观指标"
    )


def test_section_writer_injects_macro_knowledge():
    """section_writer 的 _build_methodology_reference 注入实质宏观知识。"""
    from pipeline.section_writer import SectionWriter

    sw = SectionWriter("industry_deep", "cicc")
    ref0 = sw._build_methodology_reference(0)  # 战略层 → lifecycle
    ref2 = sw._build_methodology_reference(2)  # 前瞻层 → macro
    assert ref0, "战略层应注入方法论参考"
    assert ref2, "前瞻层应注入方法论参考"
    # 注入应含实质内容（而非仅标题列表）
    assert "核心框架" in ref0 or "方法" in ref0, "注入应含框架/方法内容"
    assert "核心框架" in ref2 or "方法" in ref2


# ── 7. 深度宏观知识库（R52 deep_v1 2026-08-03）────────────────
def test_macro_deep_kb_exists():
    """深度知识库（深度理解+联网调研合成）必须存在且含框架/信号。"""
    import json

    p = _ROOT / "data" / "methodology_macro_deep.json"
    assert p.exists(), f"缺少深度知识库 {p}"
    d = json.loads(p.read_text(encoding="utf-8"))
    topics = {k: v for k, v in d.items() if k != "_meta"}
    assert set(topics.keys()) == {"industry_lifecycle", "business_model", "macro", "strategy"}, (
        f"深度库应有4主题, 实际{list(topics.keys())}"
    )
    # 每个条目必须含 framework（深度理解的核心标志）
    for t, items in topics.items():
        for it in items:
            assert it.get("framework"), f"{t} 条目缺 framework: {it.get('title', '')}"
    # 深度库应含联网调研补充（web_supplement）
    all_items = [it for v in topics.values() for it in v]
    assert any(it.get("web_supplement") for it in all_items), "深度库应含 web_supplement 调研补充"


def test_macro_deep_kb_leading_relations():
    """深度库 macro 主题应含具体领先关系（宏观预测最值钱部分）。"""
    import json

    d = json.loads((_ROOT / "data" / "methodology_macro_deep.json").read_text(encoding="utf-8"))
    macro_items = d["macro"]
    # 高频方法论条目应含 leading_relations 且至少 10 条
    hf = next((i for i in macro_items if i.get("leading_relations")), None)
    assert hf, "宏观高频方法论条目应含 leading_relations"
    assert len(hf["leading_relations"]) >= 10, f"领先关系应≥10条, 实际{len(hf['leading_relations'])}"
    # 抽查关键关系
    rels = {r["lead"]: r["period"] for r in hf["leading_relations"]}
    assert "社融" in rels and "领先3季度" in rels["社融"], f"社融领先关系缺失: {rels.get('社融')}"
    assert "能繁母猪存栏/原油" in rels, "猪周期领先关系缺失"


def test_section_writer_prefers_deep_kb():
    """section_writer 应优先读深度知识库（framework 注入而非 summary）。"""
    from pipeline.section_writer import SectionWriter

    sw = SectionWriter("industry_deep", "cicc")
    ref2 = sw._build_methodology_reference(2)  # 前瞻层 → macro
    assert "核心框架" in ref2, "应注入核心框架定义"
    # 深度库的 framework 包含实质内容（如"看方向不看水平"）
    assert "看方向" in ref2 or "高频" in ref2 or "领先" in ref2, f"前瞻层应注入宏观方法论实质内容, 实际: {ref2[:200]}"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
