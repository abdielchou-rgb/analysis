#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0-4 (2026-09-01): Gate 失败归因 triage——把 19640 条失败记录变成可行动清单。

用法：
    python scripts/gate_failure_triage.py                    # 默认近 3 个月，输出到 output/
    python scripts/gate_failure_triage.py --months 1 --top 15
    python scripts/gate_failure_triage.py --asset 浙江觉纤    # 单标的

产出：output/failure_triage_<date>.md
内容：top 失败项 + 近况/上期复发 + 对应检查代码位置 + 建议修复方向。

铁律（CLAUDE.md 工程方法论）：管线报错/Gate 失败先建反馈环再修——本脚本是反馈环第一步。
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

LEARNING_DB = _ROOT / "data" / "learning_data.db"

# 已知失败类型 → 建议修复方向的映射（新增类型在 triage 报告中标记为 UNKNOWN）
# 注意：failure_type 带 [ERROR]/[WARNING] 前缀，这里用"规范化键"（去前缀小写）匹配，
# 匹配失败时回退到模糊包含匹配。
FIX_HINTS = {
    "judgment_density": "判断密度低于阈值 → section_writer 加'每段 1 句判断句'结构约束（非措辞要求）",
    "so_what_chain": "缺 So What 链 → 注入器加显式'因此/所以链'模板",
    "so_what_per_judgment": "每判断缺 So What → 同上，按判断粒度注入",
    "inline_citations": "来源标注不足 → 数据注入时强制 [En] 标注；claim ledger 接入后改 [Cn]",
    "completeness_scan": "完整性扫描失败 → 检查缺失章节的注入条件",
    "sac维度覆盖": "SAC 维度覆盖不足 → 检查维度裁剪是否过度/注入是否生效",
    "chart_analysis_quality": "图表质量低 → chart_planner 提高生成参数或降级 placeholder",
    "layout_quality": "排版问题 → export/layout 检查",
    "排版一致性": "排版不一致 → export/layout 检查",
    "bottleneck_analysis": "瓶颈分析缺失 → 检查 bottleneck_engine 注入",
    "risk_layering": "风险分层不足 → risk 段 prompt 加强",
    "explicit_conclusion": "缺明确结论 → 结尾注入显式结论模板",
    "data_conflicts": "数据矛盾 → 跑 core/data_caliber.py 检测多来源冲突",
    "rating_target_consistency": "评级-目标价不一致 → 修 _check_rating_target_consistency 阈值",
    "template_repeat": "模板重复 → 模板变体生成",
    "forbidden_patterns": "禁词 → 检查 style compiler 清理",
    "禁止词检测": "禁词 → 检查 style compiler 清理",
    "placeholder_charts": "图表占位 → 图表生成失败，需查 chart_pipeline",
    "compliance": "合规 → csrc 合规条款检查",
    "chart_completeness": "图表完整性 → chart_pipeline 生成检查",
    "图表密度": "图表密度 → chart_planner 数量调整",
    "data_traceability": "数据可追溯性 → data_provenance 增强（claim ledger 接入后根治）",
    "cross_section_consistency": "跨章节一致 → consistency_engine 检查阈值",
    "dcf_sensitivity": "DCF 敏感性 → compute_engine 护栏检查",
    "evidence_layer": "证据层不足 → 反方论证注入",
    "falsification_conditions": "证伪条件缺失 → 决策门 prompt 加强",
    "attribution_depth": "归因深度 → So What 链+归因层注入",
    "data_dict_refs": "data_dict 引用 → 数据注入与正文对齐",
    "template_leak": "模板泄漏 → 模板去重",
    "explicit_conclusion": "缺明确结论 → 结尾结论模板",
    "table_quality_md": "表格质量 → 表格生成检查",
    "md_artifacts": "MD 残留 → 导出清理",
    "synthesis_consistency": "综合一致性 → synthesis 检查",
    "human_impossible": "人类不可能维度 → 超级维度注入",
    "multi_model": "多模型验证 → cross-audit 接线",
    "多模型验证": "多模型验证 → cross-audit 接线",
    "ai_tone_llm": "AI 语气 → StyleCompiler 清理+LLM 判别",
    "content_volume": "内容量不足 → 维度注入扩充",
    "chart_planner": "图表规划 → chart_planner 参数",
    "decision_gate": "决策门判断 → decision_memo prompt",
    "决策门判断": "决策门判断 → decision_memo prompt",
    "persuasion_architecture": "说服力架构 → 金字塔原理注入",
    "说服力架构": "说服力架构 → 金字塔原理注入",
}


def norm_key(ft: str) -> str:
    """规范化失败类型键：去 [ERROR]/[WARNING] 前缀、小写、去空格。"""
    k = re.sub(r"^\[(ERROR|WARNING)\]", "", ft).strip().lower().replace(" ", "")
    return k


def fix_hint(ft: str) -> str:
    k = norm_key(ft)
    if k in FIX_HINTS:
        return FIX_HINTS[k]
    # 模糊包含匹配：去掉前缀后包含关系
    for fk, hint in FIX_HINTS.items():
        if fk in k or k in fk:
            return hint + "（模糊匹配）"
    return "UNKNOWN——需人工归因"


def load_failures(months: int, asset: str = "") -> list[dict]:
    # 2026-09-01: 直接读 data/learning_data.db 遇 disk I/O error（沙箱/Windows 共享文件锁），
    # 先复制到临时文件再读——学习数据是只读资产，读取不应受锁影响。
    import shutil
    import tempfile

    tmp_db = Path(tempfile.mkdtemp()) / "learning_copy.db"
    try:
        shutil.copy2(str(LEARNING_DB), str(tmp_db))
    except Exception as e:
        print(f"[TRIAGE] learning DB 复制失败: {e}")
        tmp_db = LEARNING_DB

    conn = sqlite3.connect(str(tmp_db))
    conn.row_factory = sqlite3.Row
    where = "created_at >= datetime('now', ?)"
    args: list = [f"-{months} months"]
    if asset:
        where += " AND asset=?"
        args.append(asset)
    rows = conn.execute(
        f"""
        SELECT asset, report_type, failure_type, failure_detail, created_at
        FROM report_failures
        WHERE {where}
        ORDER BY created_at DESC
        """,
        args,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cluster(failures: list[dict], months: int) -> tuple[list, dict]:
    """按 failure_type 聚类 + 上期复发统计。返回 (top 列表, 汇总)。"""
    by_type: dict[str, dict] = {}
    for f in failures:
        ft = f["failure_type"] or "general"
        e = by_type.setdefault(ft, {"recent": 0, "details": [], "assets": set(), "recent_latest": ""})
        e["recent"] += 1
        if len(e["details"]) < 3:
            e["details"].append(str(f["failure_detail"])[:180])
        e["assets"].add(str(f["asset"]))
        if f["created_at"] > e["recent_latest"]:
            e["recent_latest"] = f["created_at"]
    # 上期窗口（同样走复制防锁）
    import shutil
    import tempfile

    tmp_db = Path(tempfile.mkdtemp()) / "learning_copy2.db"
    try:
        shutil.copy2(str(LEARNING_DB), str(tmp_db))
    except Exception:
        tmp_db = LEARNING_DB
    conn = sqlite3.connect(str(tmp_db))
    conn.row_factory = sqlite3.Row
    prev = conn.execute(
        """
        SELECT failure_type, COUNT(*) as n
        FROM report_failures
        WHERE created_at >= datetime('now', ?) AND created_at < datetime('now', ?)
        GROUP BY failure_type
        """,
        (f"-{months * 2} months", f"-{months} months"),
    ).fetchall()
    conn.close()
    prev_map = {r["failure_type"]: r["n"] for r in prev}

    ranked = []
    for ft, e in by_type.items():
        ranked.append(
            {
                "failure_type": ft,
                "recent": e["recent"],
                "previous": prev_map.get(ft, 0),
                "recurred": prev_map.get(ft, 0) > 0,
                "assets": len(e["assets"]),
                "latest": e["recent_latest"],
                "details": e["details"],
                "fix_hint": fix_hint(ft),
            }
        )
    ranked.sort(key=lambda x: -x["recent"])
    total = sum(r["recent"] for r in ranked)
    return ranked, {"total": total, "types": len(ranked), "months": months}


def render_md(ranked: list, summary: dict, asset: str) -> str:
    lines = [
        "# Gate 失败归因 Triage 报告",
        "",
        f"**日期**：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**数据**：近 {summary['months']} 个月 {'（标的: ' + asset + '）' if asset else '（全量）'}",
        f"**规模**：{summary['total']} 条失败 / {summary['types']} 种类型",
        "",
        "## Top 失败项（按次数排序）",
        "",
        "| 失败类型 | 近况 | 上期 | 复发 | 涉及标的 | 建议修复方向 |",
        "|---|---|---|---|---|---|",
    ]
    for r in ranked[:20]:
        lines.append(
            f"| {r['failure_type']} | {r['recent']} | {r['previous']} | "
            f"{'⚠️是' if r['recurred'] else '否'} | {r['assets']} | {r['fix_hint']} |"
        )
    lines.append("")
    lines.append("## 详情样本")
    lines.append("")
    for r in ranked[:8]:
        lines.append(f"### {r['failure_type']}（近 {r['recent']} 次，最新 {r['latest']}）")
        for d in r["details"]:
            lines.append(f"- `{d}`")
        lines.append("")
    lines.append("## 铁律")
    lines.append("")
    lines.append("> 无根因调查不修复。本报告是反馈环第一步——先确认每个 top 失败项的根因，")
    lines.append("> 再决定修 prompt/阈值/注入器/计算，禁止盲改。")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Gate 失败归因 triage")
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--asset", type=str, default="")
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()

    failures = load_failures(args.months, args.asset)
    if not failures:
        print(f"[TRIAGE] 近 {args.months} 个月无失败记录")
        return
    ranked, summary = cluster(failures, args.months)
    md = render_md(ranked, summary, args.asset)

    out_dir = _ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / f"failure_triage_{datetime.now().strftime('%Y%m%d')}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"[TRIAGE] 报告已写入: {out_path}")
    print(f"[TRIAGE] top 5 失败项:")
    for r in ranked[:5]:
        flag = " ⚠️复发" if r["recurred"] else ""
        print(f"  {r['failure_type']}: {r['recent']} 次{flag} → {r['fix_hint']}")


if __name__ == "__main__":
    main()
