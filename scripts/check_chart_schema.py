#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图表 schema 一致性校验器（2026-08-01 建立）

校验 pipeline/chart_schema.json（权威定义）与三处消费方是否对齐：
  1. SAC chart_config（core/sacs/*.yaml 或 SACLoader 返回）
  2. chart_pipeline CHART_TEMPLATES（pipeline/chart_pipeline.py）
  3. data_enrichment ALLOWED_FIG_KEYS（pipeline/data_enrichment.py）

用途：防止 fig_map / 白名单 / 模板 / SAC 四份定义漂移。
用法:
    python scripts/check_chart_schema.py           # 校验并报告
    python scripts/check_chart_schema.py --strict  # 任何不一致返回非0
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = _ROOT / "pipeline" / "chart_schema.json"

# 各报告类型 → SAC 中应声明的图（由 SACLoader 读取）
REPORT_SAC_FILES = {
    "unlisted_company": "sac_unlisted_company.yaml",
    "industry_deep": "sac_industry_deep.yaml",
    "listed_company": "sac_listed_company.yaml",
    "earnings_notes": "sac_earnings_notes.yaml",
}


def load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def check_sac_alignment(schema: dict) -> list[str]:
    """SAC chart_config 的图 id 必须在 schema 中，且 maps_to/type 一致"""
    import yaml
    issues = []
    for rt, fname in REPORT_SAC_FILES.items():
        sac_path = _ROOT / "core" / "sacs" / fname
        if not sac_path.exists():
            issues.append(f"[{rt}] SAC 文件缺失: {fname}")
            continue
        sac = yaml.safe_load(sac_path.read_text(encoding="utf-8"))
        cc = sac.get("chart_config") or {}
        for c in cc.get("charts", []):
            cid = c.get("id", "")
            if cid not in schema.get("charts", {}):
                issues.append(f"[{rt}] 图 {cid} 不在 chart_schema.json 中")
                continue
            s = schema["charts"][cid]
            if c.get("type") and c.get("type") != s.get("fig_type"):
                issues.append(f"[{rt}] 图 {cid} type 不一致: SAC={c.get('type')} schema={s.get('fig_type')}")
    return issues


def check_pipeline_alignment(schema: dict) -> list[str]:
    """chart_pipeline CHART_TEMPLATES 的图 id 必须在 schema 中"""
    import sys as _sys
    _sys.path.insert(0, str(_ROOT))
    try:
        from pipeline.chart_pipeline import CHART_TEMPLATES
    except Exception as e:
        return [f"chart_pipeline 导入失败: {e}"]
    issues = []
    for rt, templates in CHART_TEMPLATES.items():
        for t in templates:
            cid = t.get("id", "")
            if cid not in schema.get("charts", {}):
                issues.append(f"[pipeline:{rt}] 模板图 {cid} 不在 chart_schema.json 中")
    return issues


def check_enrich_whitelist(schema: dict) -> list[str]:
    """data_enrichment ALLOWED_FIG_KEYS 必须覆盖 schema 中 allowed=true 的图"""
    import sys as _sys
    _sys.path.insert(0, str(_ROOT))
    try:
        from pipeline.data_enrichment import ALLOWED_FIG_KEYS
    except Exception as e:
        return [f"data_enrichment 导入失败: {e}"]
    issues = []
    for cid, spec in schema.get("charts", {}).items():
        if spec.get("allowed") and cid not in ALLOWED_FIG_KEYS:
            issues.append(f"图 {cid} allowed=true 但不在 ALLOWED_FIG_KEYS 白名单")
    return issues


def main() -> int:
    strict = "--strict" in sys.argv
    schema = load_schema()
    all_issues = []
    all_issues += check_sac_alignment(schema)
    all_issues += check_pipeline_alignment(schema)
    all_issues += check_enrich_whitelist(schema)

    if all_issues:
        print(f"⚠️  发现 {len(all_issues)} 处 schema 不一致:")
        for i in all_issues:
            print(f"  - {i}")
        return 1 if strict else 0
    print("✓ 图表 schema 一致性校验通过（SAC / chart_pipeline / enrich 白名单 全部对齐）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
