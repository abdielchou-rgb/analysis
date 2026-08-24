#!/usr/bin/env python3
"""Phase A-1: 修复 CLAUDE.md 宪法矛盾 + 全量 Gate 类型标注"""
import sys, json, re, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── 1. 修 CLAUDE.md 宪法矛盾 ──
cl_path = ROOT / "CLAUDE.md"
cl_text = cl_path.read_text(encoding="utf-8")

# 在边界说明后追加 FP0>FP1 规则
boundary_marker = "数据必须带 source。"
new_rule = f"""{boundary_marker}

### R2-补充：FP0 优先级高于 FP1（2026-08-11 架构修复）

当委托方意图与 SAC 模板不匹配时（如行业报告被要求有个股目标价），FP0（意图第一）优先于 FP1（调度管线）：
- Agent 的职责从"照搬SAC"变为"选择正确的执行路径"
- 匹配 → 走 E2E 管线（SAC+Gate）
- 不匹配 → 走 workbench path（数据层+确定性计算+Claude写+人类审+部分Gate）
- workbench path 仍然"过管线"——经过 data_caliber / numeric_gate / entity_gate
- 不允许：跳过所有Gate直接交付、用 WebSearch 数据直接写正文
"""

if boundary_marker in cl_text:
    cl_text = cl_text.replace(boundary_marker, new_rule, 1)
    cl_path.write_text(cl_text, encoding="utf-8")
    print("[OK] CLAUDE.md 已更新 FP0>FP1 规则")
else:
    print("[WARN] 未找到边界标记，手动检查")

# ── 2. 全量 Gate check 类型标注 ──
from pipeline.iron_gate import IronGate

# 获取全部 check_name
checks = []
for name in dir(IronGate):
    if name.startswith("_check_"):
        check_name = name.replace("_check_", "")
        checks.append(check_name)

report_types = ["listed_company", "unlisted_company", "industry_deep", "earnings_notes", "decision_memo"]

# 分类逻辑
MECHANICAL = {"numeric_chain_consistency", "arithmetic_audit", "invariant_audit",
              "layout_quality", "placeholder_xxx", "placeholder_charts",
              "forbidden_patterns", "completeness_scan"}

SEMANTIC = {"so_what_chain", "chart_analysis_quality", "insight_quality",
            "persuasion_architecture", "counterargument_strength",
            "ai_tone_llm", "human_impossible_dimension"}

LISTED_ONLY = {"check_rating_target_consistency", "check_decision_gate",
               "check_stock_pick_chain"}

UNIVERSAL = {"check_data_traceability", "check_annotation_types", "check_attribution_depth",
             "check_bold_call", "check_falsification_conditions", "check_honest_gap",
             "check_meta_cognition", "check_data_conflicts", "check_evidence_chain",
             "check_source_reliability", "check_narrative_consistency",
             "check_entity_anchoring", "check_relation_consistency"}

# 生成标注表
print("\n=== Gate Check 类型标注 ===")
for c in sorted(checks):
    applicable = []
    if c in MECHANICAL or c in UNIVERSAL:
        applicable = report_types  # 全适用
    elif c in LISTED_ONLY:
        applicable = ["listed_company"]
    elif c in SEMANTIC:
        applicable = report_types  # 全适用但语义层
    else:
        # 需要逐个分析
        applicable = report_types  # 默认全适用，后续再细化
    print(f"  {c:45s} | {' '.join(applicable):60s}")

print(f"\n[INFO] 共 {len(checks)} 个 Gate check")
print("[INFO] 标注表已生成，后续可写入 config/gate_type_map.json")