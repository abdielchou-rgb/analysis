#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""框架吸收器 — 把新分析框架文档化并注册进 framework_registry.json。

R65（2026-08-04）FP8 元认知选择：当用户/Agent 提出新分析框架时，
提炼为注册表条目，之后可被 analyst_planner 选择使用。

用法：
  python scripts/absorb_framework.py --id ma_valuation --名称 "并购估值" \
      --report-types industry_deep,listed_company \
      --data-req "有并购案例库" --sac "行业整合与并购趋势,资本市场映射" \
      --inject "core.compute.consolidation → compute" --note "R57-R58"

  # 或从 YAML/MD 方法文档读取（待扩展）
"""
import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = _ROOT / "data" / "framework_registry.json"


def load_registry() -> dict:
    if not REGISTRY.exists():
        return {"_meta": {}, "frameworks": [], "dimension_focus_rules": []}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def save_registry(reg: dict) -> None:
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def absorb(fw_id: str, name: str, report_types: list[str], data_req: str,
           sac_dims: list[str], inject: str, note: str, when: str = "",
           exclude: str = "") -> bool:
    reg = load_registry()
    frameworks = reg.get("frameworks", [])

    # 查重
    if any(f.get("id") == fw_id for f in frameworks):
        print(f"[SKIP] 框架 {fw_id} 已存在，如需更新请手动编辑 {REGISTRY}")
        return False

    frameworks.append({
        "id": fw_id,
        "名称": name,
        "适用条件": {
            "report_types": report_types,
            "data_requirement": data_req,
            "when": when or f"需应用{name}方法",
            "exclude": exclude or "无数据/不适用",
        },
        "映射SAC": sac_dims,
        "注入方式": inject,
        "效果": {"已用次数": 0, "平均Gate分": 0.5, "评分": "unverified"},
        "备注": note,
    })
    reg["frameworks"] = frameworks
    save_registry(reg)
    print(f"[OK] 框架 {fw_id}（{name}）已注册，共 {len(frameworks)} 个框架")
    return True


def main():
    ap = argparse.ArgumentParser(description="框架吸收器")
    ap.add_argument("--id", required=True, help="框架 ID（英文短横线）")
    ap.add_argument("--名称", required=True, help="框架中文名")
    ap.add_argument("--report-types", required=True, help="适用报告类型，逗号分隔")
    ap.add_argument("--data-req", required=True, help="数据要求")
    ap.add_argument("--sac", required=True, help="映射 SAC 维度，逗号分隔")
    ap.add_argument("--inject", required=True, help="注入方式")
    ap.add_argument("--note", default="", help="备注")
    ap.add_argument("--when", default="", help="适用时机")
    ap.add_argument("--exclude", default="", help="排除条件")
    args = ap.parse_args()

    ok = absorb(
        fw_id=args.id, name=args.名称,
        report_types=[t.strip() for t in args.report_types.split(",")],
        data_req=args.data_req,
        sac_dims=[d.strip() for d in args.sac.split(",")],
        inject=args.inject, note=args.note,
        when=args.when, exclude=args.exclude,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
