#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iron_gate 迁移工具 — 把 IronGate 的检查方法按职责迁移到 checks/ mixin。

R61（2026-08-03）：按 Effective Python mixin 打法拆分 iron_gate.py（3537行/67检查）。

分组：
  content_format  → 内容量/密度/人感/AI/排版/完整性/模板（内容与格式）
  data_quality    → 数据溯源/冲突/口径/算术/估值/审计（数据与质量）
  analysis        → SAC覆盖/判断/并购/ESG/选股/假设（分析与框架）
  llm_checks      → ai_tone/数据验证（LLM 类，运行最慢，独立分组）

用法：
  python scripts/migrate_iron_gate.py          # 执行迁移（生成 mixin + 改 iron_gate）
  python scripts/migrate_iron_gate.py --dry-run  # 预览
"""

import argparse
import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
IRON_GATE = _ROOT / "pipeline" / "iron_gate.py"
CHECKS_DIR = _ROOT / "pipeline" / "checks"

# 检查方法 → 分组
_GROUP_MAP = {
    # 内容与格式
    "content_format": [
        "_check_content_volume",
        "_check_content_density",
        "_check_judgment_density",
        "_check_aigc_fingerprint",
        "_check_human_sense",
        "_check_format_consistency",
        "_check_layout_quality",
        "_check_completeness_scan",
        "_check_template_repeat",
        "_check_semantic_repeat",
        "_check_forbidden_patterns",
        "_check_markdown_artifacts",
        "_check_personal_narrative",
        "_check_section_continuity",
        "_check_table_quality_md",
    ],
    # 数据与质量
    "data_quality": [
        "_check_data_traceability",
        "_check_annotation_types",
        "_check_data_type_annotation",
        "_check_data_fidelity",
        "_check_data_source_accuracy",
        "_check_data_dict_refs",
        "_check_data_conflicts",
        "_check_arithmetic_audit",
        "_check_invariant_audit",
        "_check_valuation_integrity",
        "_check_financial_value_consistency",
        "_check_financial_fraud_signals",
        "_check_rating_target_consistency",
        "_check_cross_section_consistency",
        "_check_synthesis_consistency",
        "_check_evidence_layer",
    ],
    # 分析与框架
    "analysis": [
        "_check_sac_coverage",
        "_check_chart_density",
        "_check_chart_completeness",
        "_check_global_perspective",
        "_check_financial_statements_coverage",
        "_check_persuasion_architecture",
        "_check_table_density",
        "_check_moat_analysis",
        "_check_multi_model",
        "_check_decision_gate",
        "_check_dcf_sensitivity",
        "_check_so_what_chain",
        "_check_explicit_conclusion",
        "_check_attribution_depth",
        "_check_falsification_conditions",
        "_check_template_leak",
        "_check_meta_cognition",
        "_check_so_what_per_judgment",
        "_check_subjective_scoring",
        "_check_bold_call",
        "_check_chart_analysis_quality",
        "_check_forecast_presence",
        "_check_bottleneck_analysis",
        "_check_risk_layering",
        "_check_stock_pick_chain",
        "_check_unlisted_threat",
        "_check_tam_bottomup",
        "_check_regional_penetration",
        "_check_industry_consolidation",
        "_check_core_hypothesis",
        "_check_esg_materiality",
        "_check_evidence_chain",
        "_check_placeholder_charts",
    ],
    # LLM 类
    "llm_checks": [
        "_check_ai_tone_by_llm",
        "_check_human_impossible_dimension",
        "_check_llm_data_verification",
    ],
}

# 分组 → 类名
_CLASS_NAMES = {
    "content_format": "ContentFormatChecksMixin",
    "data_quality": "DataQualityChecksMixin",
    "analysis": "AnalysisChecksMixin",
    "llm_checks": "LlmChecksMixin",
}


def extract_method_source(src: str, method_name: str) -> str | None:
    """用 AST 提取方法的源码文本（含装饰器）。"""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "IronGate":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    # 提取源码
                    lines = src.split("\n")
                    start = item.lineno - 1
                    end = item.end_lineno
                    # 包含装饰器
                    for dec in item.decorator_list:
                        dl = getattr(dec, "lineno", None)
                        if dl:
                            start = min(start, dl - 1)
                    return "\n".join(lines[start:end])
    return None


def find_methods_in_class(src: str) -> list[str]:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "IronGate":
            return [
                n.name
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("_check_")
            ]
    return []


def build_mixin_file(group: str, methods: list[str], src: str) -> str:
    """生成 mixin 文件内容。"""
    class_name = _CLASS_NAMES[group]
    header = f'''# -*- coding: utf-8 -*-
"""IronGate 检查 Mixin — {group} 类检查。

R61（2026-08-03 迁移）：由 scripts/migrate_iron_gate.py 自动生成。
方法原样迁移自 pipeline/iron_gate.py，签名不变，IronGate 继承后行为零变化。
"""


class {class_name}:
    """{group} 类检查方法。"""
'''
    body = []
    for m in methods:
        code = extract_method_source(src, m)
        if code:
            # 缩进调整：方法体从类内 4 空格 → mixin 类内 4 空格（保持一致）
            body.append(code)
        else:
            print(f"  ⚠️ 未找到 {m}")
    return header + "\n\n".join(body) + "\n"


def main():
    ap = argparse.ArgumentParser(description="iron_gate 迁移")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = IRON_GATE.read_text(encoding="utf-8")
    all_checks = find_methods_in_class(src)
    print(f"IronGate 检查方法: {len(all_checks)}")

    # 校验分组覆盖
    grouped = set()
    for g, methods in _GROUP_MAP.items():
        grouped.update(methods)
    missing = set(all_checks) - grouped
    extra = grouped - set(all_checks)
    if missing:
        print(f"⚠️ 未分组的检查方法: {missing}")
    if extra:
        print(f"⚠️ 分组中不存在的方法: {extra}")
    print(f"分组覆盖: {len(grouped & set(all_checks))}/{len(all_checks)}")

    if args.dry_run:
        print("[DRY-RUN] 未写文件")
        return

    # 生成 mixin 文件
    CHECKS_DIR.mkdir(parents=True, exist_ok=True)
    for g, methods in _GROUP_MAP.items():
        fname = CHECKS_DIR / f"{g}_mixin.py"
        content = build_mixin_file(g, [m for m in methods if m in all_checks], src)
        fname.write_text(content, encoding="utf-8")
        print(f"  生成 {fname.name} ({len([m for m in methods if m in all_checks])} 方法)")

    print("✅ Mixin 文件已生成。下一步：IronGate 继承 + 删除原方法（需人工确认）")


if __name__ == "__main__":
    main()
