# -*- coding: utf-8 -*-
"""P0-1 / P0-2 / P0-3 回归测试：KB/MKB 注入三硬伤（2026-09-07 修复）。

背景（深度审计，docs/MASTER_REVIEW_AND_KB_PLAN_20260907.md §10）：
- P0-1：维度并行路径把 KB/MKB 等 15 个注入块整体包在 `if _tm_str:` 内，
  tool_modules 为空时知识库方法论全部丢失。
- P0-2：串行写作路径（_build_prompt_v4 / _build_skeleton_prompt）从不注入 KB/MKB，
  与并行路径产出不一致。
- P0-3：knowledge_base.search 白名单漏掉 01-宏观/08-四大审计/09-国际投行三个
  方法论目录，且过滤代码复制三份。

本文件守护三处修复不再回归。
"""

import ast
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.section_writer import SectionWriter, _assemble_data_injection_tail

KB_HEADER = "## [知识库参考]"
MKB_HEADER = "## [方法论知识库精选]"
TOOL_MODULE_HEADER = "## 工具模块数据"

_KB_FAKE = (
    KB_HEADER + " 以下段落来自内部知识库（券商研报/方法论），供分析框架参考：\n"
    "[KB1] 来源: 示例研报\n审计勾稽与三表复核示例段落……"
)
_MKB_FAKE = MKB_HEADER + " 以下来自内部券商研报/估值模型知识库：\n1. 高盛估值框架……"


# ── P0-1：KB/MKB 与 _tm_str 总开关解耦 ───────────────────────


def test_tail_injects_kb_mkb_when_tool_modules_empty():
    """tm 为空 → KB/MKB 块仍出现（修复前整段被 if _tm_str 吞掉）。"""
    tail = _assemble_data_injection_tail(
        tm_str="",
        ev_str="",
        mc_str="",
        rp_str="",
        macro_str="",
        valuation_kb_str="",
        policy_str="",
        esg_data_str="",
        ma_cases_str="",
        segment_rev_str="",
        consulting_str="",
        market_seg_str="",
        analogy_str="",
        kb_str=_KB_FAKE,
        mkb_str=_MKB_FAKE,
    )
    assert KB_HEADER in tail, "tool_modules 为空时 KB 注入丢失（P0-1 未修复）"
    assert MKB_HEADER in tail, "tool_modules 为空时 MKB 注入丢失（P0-1 未修复）"
    assert TOOL_MODULE_HEADER not in tail


def test_tail_keeps_blocks_and_order_when_tm_present():
    """tm 非空时保持原输出：工具模块头在前，KB/MKB 紧随其后。"""
    tail = _assemble_data_injection_tail(
        tm_str="弹性 5 档",
        ev_str="## [证据编号清单]\n[E1] fig_revenue = ...",
        mc_str="",
        rp_str="",
        macro_str="",
        valuation_kb_str="",
        policy_str="",
        esg_data_str="",
        ma_cases_str="",
        segment_rev_str="",
        consulting_str="",
        market_seg_str="",
        analogy_str="",
        kb_str=_KB_FAKE,
        mkb_str=_MKB_FAKE,
    )
    assert tail.index(TOOL_MODULE_HEADER) < tail.index(KB_HEADER)
    assert KB_HEADER in tail and MKB_HEADER in tail


def test_tail_empty_when_all_inputs_empty():
    assert _assemble_data_injection_tail(*([""] * 15)) == ""


# ── P0-2：串行写作路径补齐 KB/MKB ────────────────────────────


def _patched_writer(monkeypatch, report_type="listed_company"):
    """把 _inj_kb_str/_inj_mkb_str 换成 canned 输出，避免真实 KB/DB/文件依赖。"""
    import pipeline.prompt_injectors_p3b as p3b

    monkeypatch.setattr(p3b, "_inj_kb_str", lambda ctx: _KB_FAKE)
    monkeypatch.setattr(p3b, "_inj_mkb_str", lambda ctx: _MKB_FAKE)
    return SectionWriter(report_type=report_type)


def test_kb_mkb_for_returns_same_injections_as_parallel(monkeypatch):
    """_kb_mkb_for 复用并行路径同款 _inj_kb_str/_inj_mkb_str，无两套实现。"""
    w = _patched_writer(monkeypatch)
    kb, mkb = w._kb_mkb_for("测试标的")
    assert KB_HEADER in kb and MKB_HEADER in mkb


def test_kb_mkb_for_empty_when_injector_skipped(monkeypatch):
    """M2 行业路由器禁用 kb_str/mkb_str 时，串行路径同样降级为空。"""
    w = _patched_writer(monkeypatch)
    monkeypatch.setattr(w, "_route_skip_for", lambda asset: {"kb_str", "mkb_str"})
    kb, mkb = w._kb_mkb_for("测试标的")
    assert kb == "" and mkb == ""


def test_build_prompt_v4_includes_kb_mkb(monkeypatch):
    """串行/骨架深化正文 prompt（_build_prompt_v4）必须含 KB/MKB 块头。"""
    w = _patched_writer(monkeypatch)
    seg = {"label": "战略层：决策门→核心分歧", "idx": 0, "dimension_ids": ["business_model"]}
    prompt = w._build_prompt_v4(
        0,
        seg,
        "测试标的",
        [],
        "营收 100 亿",
        "fig_revenue",
        "",
        "",
    )
    assert KB_HEADER in prompt, "_build_prompt_v4 未注入 KB（P0-2 未修复）"
    assert MKB_HEADER in prompt, "_build_prompt_v4 未注入 MKB（P0-2 未修复）"


def test_build_skeleton_prompt_includes_kb_mkb(monkeypatch):
    """骨架 prompt 也必须带 KB/MKB（并行路径 skeleton_mode 下本就注入）。"""
    w = _patched_writer(monkeypatch)
    seg = {"label": "战略层", "idx": 0, "dimension_ids": ["business_model"]}
    prompt = w._build_skeleton_prompt(0, seg, "测试标的", ["商业模式"], "营收 100 亿", "fig_revenue")
    assert KB_HEADER in prompt
    assert MKB_HEADER in prompt


# ── P0-3：知识库检索 allowlist 修正 + 去重 ────────────────────


_ALLOWLIST_METHODOLOGY = {"01-宏观分析框架", "08-四大审计方法论", "09-国际投行方法论"}


def _build_tmp_kb(tmp_path, monkeypatch):
    """在 tmp 下造一个迷你 KB（含方法论目录 + Excel/PPT 教学目录）。"""
    import core.knowledge_base as kb

    kb_dir = tmp_path / "知识库"
    monkeypatch.setattr(kb, "KB_DIR", kb_dir)
    monkeypatch.setattr(kb, "DB_PATH", tmp_path / "kb_fts.db")

    docs = {
        "01-宏观分析框架/macro.md": (
            "宏观分析框架：信用周期与库存周期叠加决定估值锚。货币信用脉冲领先盈利周期约两个季度，"
            "M1 同比与 PPI 的剪刀差可用于三表勾稽与盈利复核。宏观流动性宽松阶段，估值中枢整体上移，"
            "成长板块的远期贴现因子下降，盈利质量高、现金流稳定的公司应获得估值溢价。"
        ),
        "08-四大审计方法论/audit.md": (
            "四大审计方法论：审计、勾稽、复核是年度审计的三大支柱。收入确认必须执行实质性程序，"
            "控制测试覆盖关键控制点。审计师对销售与收款循环执行函证与凭证复核，三表勾稽关系不一致时"
            "须出具调整分录并复核底稿。国际四大会计师事务所的项目质量控制要求报告出具前完成独立复核，"
            "确保审计证据充分且适当。"
        ),
        "09-国际投行方法论/ib.md": (
            "国际投行方法论：高盛与摩根士丹利的三表勾稽与行业框架，盈利预测用自下而上模型，"
            "估值锚与审计复核结果交叉验证，卖方研究底稿须完整可追溯。盈利预测一旦调整，"
            "目标价与评级同步更新，形成从预测假设到投资结论的估值逻辑闭环。"
        ),
        "05-Excel知识库/excel.md": (
            "Excel 知识库：VLOOKUP 与 INDEX/MATCH 的教学示例，财务建模模板，数据透视表操作指引，"
            "单元格引用与快捷键速查表，图表与透视表联动刷新技巧，属于办公软件操作教学素材，"
            "不构成行业分析方法论素材。"
        ),
        "06-PPT排版美学/ppt.md": (
            "PPT 排版美学：配色与留白规范、图表美化与动画切换技巧、版式设计原则与字体搭配建议，"
            "母版与占位符的高效使用方法，属于演示文稿制作的教学内容。本文档仅供内部 Office 教学使用，"
            "不构成投资分析方法论参考素材。"
        ),
    }
    for rel, text in docs.items():
        p = kb_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    kb.build_index(force=True)
    return kb


def test_relevant_categories_allow_methodology_dirs(tmp_path, monkeypatch):
    """01/08/09 方法论目录必须在 allowlist 内，Excel/PPT 教学目录被排除。"""
    kb = _build_tmp_kb(tmp_path, monkeypatch)
    conn = sqlite3.connect(str(kb.DB_PATH))
    try:
        cats = kb._relevant_categories(conn)
    finally:
        conn.close()
    for method_dir in _ALLOWLIST_METHODOLOGY:
        assert method_dir in cats, f"{method_dir} 仍被白名单误杀（P0-3 未修复）"
    assert "05-Excel知识库" not in cats
    assert "06-PPT排版美学" not in cats


def test_search_can_hit_audit_methodology(tmp_path, monkeypatch):
    """search 默认路径能命中 08-四大审计方法论（修复前被关键词白名单过滤）。"""
    kb = _build_tmp_kb(tmp_path, monkeypatch)
    hits = kb.search("审计 勾稽 复核", top_k=10)
    cats = {h["category"] for h in hits}
    assert cats, "tmp KB 应至少命中 08-四大审计方法论"
    assert "08-四大审计方法论" in cats, f"审计方法论检索为空: {hits}"
    assert "05-Excel知识库" not in cats, "Excel 教学目录混入检索结果"


def test_search_balanced_guarantees_small_methodology_categories(tmp_path, monkeypatch):
    """类别均衡检索：08/09 小体量方法论目录在通用资产查询下仍必须出结果。

    回归背景（2026-09-07 实证）：真实 FTS 里 04-回测基线库 7.6 万 chunk，
    top-k 全局检索在任意股票查询下被 03/04 填满，08（17）/09（10）方法论
    目录实际不可见。search_balanced 按 allowlist 逐类别取 top-2 治此病。
    """
    kb = _build_tmp_kb(tmp_path, monkeypatch)
    hits = kb.search_balanced("宁德时代 公司研究 估值", per_category=2)
    cats = {h["category"] for h in hits}
    assert "08-四大审计方法论" in cats, f"类别均衡检索丢审计方法论: {cats}"
    assert "09-国际投行方法论" in cats, f"类别均衡检索丢国际投行方法论: {cats}"
    assert "01-宏观分析框架" in cats, f"类别均衡检索丢宏观框架: {cats}"
    assert "05-Excel知识库" not in cats, "Excel 教学目录混入类别均衡检索"
    # 去重保证：同一 source 最多出现一次（FTS top-n 内同文件多 chunk 只留一）
    sources = [h["source"] for h in hits]
    assert len(sources) == len(set(sources)), f"search_balanced 未去重: {sources}"


def test_inj_kb_str_uses_balanced_search_and_carries_category(tmp_path, monkeypatch):
    """K-07 注入器走 search_balanced，输出带目录归属（审计/投行方法论可见）。"""
    _build_tmp_kb(tmp_path, monkeypatch)
    from pipeline.prompt_injectors_p3b import _inj_kb_str

    out = _inj_kb_str(
        {
            "asset": "宁德时代",
            "report_type": "listed_company",
            "data_context": {},
        }
    )
    assert "## [知识库参考]" in out, "注入器输出缺 KB 参考头"
    assert "四大审计" in out, "注入块未体现审计方法论目录来源"
    assert "国际投行" in out, "注入块未体现国际投行方法论目录来源"
    assert "[KB1]" in out, "注入块缺 [KB#] 引用锚点（P1-2 消费端计数依赖）"


def test_kb_category_filter_deduped_and_single_source():
    """P0-3 源码守卫：过滤逻辑与 _indexed_categories 不再复制粘贴。"""
    src = (Path("core/knowledge_base.py")).read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs = [
        n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef,)) and n.name == "_indexed_categories"
    ]
    assert len(defs) == 1, f"_indexed_categories 仍有 {len(defs)} 份重复定义"
    assert src.count("def _relevant_categories(") == 1
    assert src.count("def _indexed_categories(") == 1
    assert src.count("for c in _indexed_categories") == 0, "旧的关键词白名单代码仍在"


# ── 1500 字截断契约 + 方法论目录置前（2026-09-07 P1 增强回归） ──


def _build_full_tmp_kb(tmp_path, monkeypatch):
    """造一个 7 个放行目录齐备的迷你库，逼近真实库形态（真实 08/09 仅 17/10 chunk）。"""
    import core.knowledge_base as kb

    kb_dir = tmp_path / "知识库"
    monkeypatch.setattr(kb, "KB_DIR", kb_dir)
    monkeypatch.setattr(kb, "DB_PATH", tmp_path / "kb_fts.db")

    filler = (
        "本标的所处环节需结合公司研究与估值方法逐条判断。"
        "框架要点必须应用到正文并给出针对本标的的结论，不能只列框架名。\n\n"
    ) * 8
    docs = {
        "01-宏观分析框架/macro-framework.md": (
            "宏观分析框架：信用周期、库存周期、利率、流动性与 GDP 增速决定估值锚。"
            "货币信用脉冲领先盈利周期两个季度，宏观流动性宽松阶段估值中枢整体上移。"
            + filler
        ),
        "02-行业与公司研究/industry-company.md": (
            "行业与公司研究：产业链位置、景气度与竞争格局决定增长质量。"
            "对销售与收款环节的核查要落到行业数据与公司口径。"
            + filler
        ),
        "03-估值与测算/valuation-model.md": (
            "估值与测算：DCF 折现、敏感性分析与可比模型互为印证，"
            "盈利预测假设须可回溯。"
            + filler
        ),
        "04-回测基线库/backtest-baseline.md": (
            "回测基线库：历史估值判断结论与方法的回测基线，供本次预测做校准。"
            + filler
        ),
        "07-原始文档提取/raw-extract.md": (
            "原始文档提取：深度研究原文与公司分析资料的结构化提取，"
            "保留口径与出处。"
            + filler
        ),
        "08-四大审计方法论/audit-methodology.md": (
            "四大审计方法论：审计、勾稽、复核、函证与收入确认的实质性程序。"
            "三表勾稽关系不一致须出具调整分录并复核底稿。"
            + filler
        ),
        "09-国际投行方法论/ib-methodology.md": (
            "国际投行方法论：高盛与摩根士丹利研报结构，"
            "自下而上盈利模型与估值逻辑闭环。"
            + filler
        ),
    }
    for rel, text in docs.items():
        p = kb_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    kb.build_index(force=True)
    return kb


def test_inj_kb_str_block_stays_under_writer_cap(tmp_path, monkeypatch):
    """真实库形态（7 目录 × 每目录 1 条）下注入块整体 ≤ 写作侧 1500 字上限。

    回归背景：section_writer 对 kb_str 做 [:1500] 硬截断；若注入块超过上限，
    排在块尾的目录会被切掉。_inj_kb_str 必须让整块在截断前完整到达模型，
    方法论目录置前只是最后防线，不是主保障。
    """
    _build_full_tmp_kb(tmp_path, monkeypatch)
    from pipeline.prompt_injectors_p3b import _inj_kb_str

    out = _inj_kb_str(
        {
            "asset": "宁德时代",
            "report_type": "listed_company",
            "data_context": {},
        }
    )
    assert out, "7 目录迷你库不应返回空注入块"
    assert len(out) <= 1500, (
        f"KB 注入块 {len(out)} 字 > 写作侧 1500 上限，块尾会被截断；"
        "需收紧 snippet 或减少每目录条数"
    )
    sliced = out[:1500]
    for marker in ("四大审计方法论", "国际投行方法论", "宏观分析框架"):
        assert marker in sliced, f"1500 上限内丢失方法论目录 {marker}"


def test_search_balanced_orders_methodology_dirs_first(tmp_path, monkeypatch):
    """08/09/01 方法论目录在 search_balanced 输出中置前，防截断优先切方法论。"""
    kb = _build_full_tmp_kb(tmp_path, monkeypatch)
    hits = kb.search_balanced("宁德时代 公司研究 估值", per_category=1)
    cats = [h["category"] for h in hits]
    assert cats[:3] == [
        "08-四大审计方法论",
        "09-国际投行方法论",
        "01-宏观分析框架",
    ], f"方法论目录未置前: {cats}"
    assert "05-Excel知识库" not in cats and "06-PPT排版美学" not in cats


# ── MKB 块级预算（2026-09-07 P1 修复：整块 ≤ 写作侧 2000 上限，防块尾截断） ──


def _mkb_fat_entry(seed: str) -> dict:
    """构造格式化后单条约 400+ 字的条目（超过 80 字实质门槛）。"""
    return {
        "title": f"方法条目{seed}完整标题",
        "topic": f"主题{seed}",
        "methods": "实质性程序与三表勾稽复核步骤说明，" * 130,
        "judgment_signals": "判断信号与敏感性阈值说明，" * 110,
        "summary": "摘要与落地注意点说明，" * 160,
    }


def test_format_block_budget_drops_whole_tail_entries():
    """max_chars 预算只整条丢弃尾部条目，绝不半截截断单条内容。"""
    from core.methodology_kb import format_block

    entries = [_mkb_fat_entry(str(i)) for i in range(6)]
    full = format_block(entries)
    capped = format_block(entries, max_chars=2000)
    assert len(full) > 2000, f"fixture 应造出超预算块: {len(full)}"
    assert len(capped) <= 2000, f"块级预算失效: {len(capped)}"
    assert "方法条目0完整标题" in capped, "预算内头部条目丢失"
    assert "方法条目5完整标题" not in capped, "尾部条目被半截截断而非整条丢弃"


def test_inj_mkb_str_respects_writer_cap_when_hits(tmp_path, monkeypatch):
    """MKB 命中时整块 ≤ 2000 字（写作侧 mkb_str[:2000] 上限）。"""
    import json as _json

    import core.methodology_kb as mk
    from pipeline.prompt_injectors_p3b import _inj_mkb_str

    data = {
        "backtest_gold": [
            {
                "title": "金牌研报复盘：宁德时代盈利预测复盘",
                "topic": "复盘",
                "methods": "复盘盈利预测偏差来源、目标价与评级联动检验，" * 130,
                "judgment_signals": "预测偏差超阈值时的信号说明，" * 110,
                "summary": "历史金牌研报复盘的偏差来源归纳，" * 160,
            }
        ]
    }
    fp = tmp_path / "methodology_knowledge_base.json"
    fp.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(mk, "_FILE", fp)
    out = _inj_mkb_str(
        {
            "asset": "宁德时代",
            "report_type": "listed_company",
            "data_context": {},
        }
    )
    assert "## [方法论知识库精选]" in out, "MKB 注入块头缺失"
    assert "[MKB1]" in out, "资产命中但 MKB 块为空"
    assert len(out) <= 2000, f"MKB 注入块 {len(out)} 字 > 2000，会被写作侧截断"
