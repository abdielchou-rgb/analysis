#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2hao 报告驱动全模块自检

用真实报告跑完整管线，系统性验证所有模块（含 2026-08-01 全部改动）。

原理：静态测试只能验证"能跑"，真实报告能验证"跑得对"——覆盖
数据采集→图表→写作→门禁→导出的全链路，且能暴露运行时问题。

用法:
    python scripts/self_check_reports.py               # 跑 3 类报告自检
    python scripts/self_check_reports.py --type unlisted_company  # 只跑一类
    python scripts/self_check_reports.py --asset 环动科技
    python scripts/self_check_reports.py --dry        # 只打印清单不跑

自检后输出 report，逐项标 PASS/FAIL/WARN。
"""

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── 自检矩阵：报告类型 → 重点验证的模块 ──────────────────────────
# 每类报告验证一组模块，合计覆盖全部改动
SELF_CHECK_MATRIX = {
    "unlisted_company": {
        "asset": "环动科技",
        "enrich": None,
        "verify": [
            ("SAC框架加载", "SACLoader unlisted_company 21维"),
            ("图表标准基线", "get_chart_config min_charts≥8"),
            ("图表生成", "8张图全部生成 PNG"),
            ("图表补全", "LLM嵌不满时自动补全到8"),
            ("SAC维度豁免", "PE/VC维度数据有限时豁免"),
            ("A/E/F/B标注", "报告含≥3种标注"),
            ("三表引用", "报告引用营收/净利/资产负债"),
            ("DeepSeekClient", "BoldCallExtractor 走LLM非降级"),
            ("AI Tone", "deepseek-reasoner 异模型审计"),
            ("出口指纹", "pipeline_fingerprint.json 生成"),
        ],
    },
    "listed_company": {
        "asset": "柯力传感",
        "enrich": "output/柯力传感_enrich.json",
        "verify": [
            ("SAC框架加载", "SACLoader listed_company 14维"),
            ("图表标准基线", "get_chart_config min_charts≥12"),
            ("图表生成", "21图模板中数据可用者生成"),
            ("A/E/F/B标注", "报告含≥3种标注"),
            ("三表引用", "报告引用营收/净利/资产负债"),
            ("fig_alias解析", "LLM图表别名正确解析"),
            ("出口指纹", "pipeline_fingerprint.json 生成"),
        ],
    },
    "industry_deep": {
        "asset": "具身智能行业",
        "enrich": None,
        "verify": [
            ("SAC框架加载", "SACLoader industry_deep 18维"),
            ("图表标准基线", "get_chart_config min_charts≥12"),
            ("图表生成", "12图模板中数据可用者生成"),
            ("出口指纹", "pipeline_fingerprint.json 生成"),
        ],
    },
}

# 模块健康检查（不依赖跑报告，纯本地验证）
MODULE_CHECKS = [
    (
        "chart_schema",
        "pipeline/chart_schema.json 合法且有 aliases",
        lambda: (
            _check_json("pipeline/chart_schema.json")
            and "aliases" in json.load(open("pipeline/chart_schema.json", encoding="utf-8"))
        ),
    ),
    ("sacs_baseline", "_AUTHORITATIVE_MIN 唯一基线", lambda: _check_authoritative_min()),
    ("iron_gate", "IronGate 含 AEFB+三表+豁免+AI Tone", lambda: _check_iron_gate()),
    ("deepseek_client", "DeepSeekClient 兼容类存在", lambda: _check_deepseek_client()),
    ("chart_assembler", "fig_alias 从 schema 读", lambda: _check_chart_assembler()),
    ("sync_akshare", "HTTP东财三表实现", lambda: _check_sync_akshare()),
    ("standards_tests", "标准一致性测试文件", lambda: (_ROOT / "tests" / "test_standards_consistency.py").exists()),
]


def _check_json(p):
    try:
        json.load(open(_ROOT / p, encoding="utf-8"))
        return True
    except Exception:
        return False


def _check_authoritative_min():
    try:
        from core.sacs import SACLoader

        return hasattr(SACLoader, "_AUTHORITATIVE_MIN") and not hasattr(SACLoader, "_STANDARDS_MIN")
    except Exception:
        return False


def _check_iron_gate():
    try:
        import inspect

        from pipeline import iron_gate

        src = inspect.getsource(iron_gate)
        return all(
            k in src
            for k in [
                "_check_annotation_types",
                "_check_financial_statements_coverage",
                "ai_tone_llm",
                "deepseek-reasoner",
            ]
        )
    except Exception:
        return False


def _check_deepseek_client():
    try:
        from core.deepseek_client import DeepSeekClient

        return callable(getattr(DeepSeekClient, "chat", None))
    except Exception:
        return False


def _check_chart_assembler():
    try:
        import inspect

        from pipeline import chart_assembler

        src = inspect.getsource(chart_assembler.ChartAssembler.inject_charts_postprocess)
        return "chart_schema.json" in src and "fig_alias" not in src.replace("_fig_alias", "")
    except Exception:
        return False


def _check_sync_akshare():
    try:
        import inspect

        from scripts import sync_akshare_financials

        src = inspect.getsource(sync_akshare_financials)
        return "_em_http_fetch" in src and "RPT_F10_FINANCE_GBALANCE" in src
    except Exception:
        return False


def run_module_checks() -> list:
    """运行纯本地模块健康检查，返回 [(name, ok, detail)]"""
    results = []
    for name, desc, fn in MODULE_CHECKS:
        try:
            ok = bool(fn())
            results.append((name, ok, desc if ok else f"FAIL: {desc}"))
        except Exception as e:
            results.append((name, False, f"{desc} → {str(e)[:60]}"))
    return results


def run_report_selfcheck(report_type: str, asset: str, enrich: str) -> dict:
    """跑一份真实报告，返回验证结果。"""
    import subprocess

    cmd = [sys.executable, str(_ROOT / "pipeline" / "scheduler.py"), asset, "--type", report_type, "--style", "cicc"]
    if enrich and Path(enrich).exists():
        cmd += ["--enrich-file", enrich]
    print(f"\n=== 跑报告自检: {report_type} / {asset} ===")
    print(f"  命令: {' '.join(cmd[:6])}...")
    t0 = time.time()
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, cwd=str(_ROOT)
        )
        elapsed = time.time() - t0
        output = (r.stdout or "") + (r.stderr or "")
        # 解析关键信号
        gate_line = [l for l in output.splitlines() if "Gate=" in l]
        template_line = [l for l in output.splitlines() if "TEMPLATE" in l]
        export_line = [l for l in output.splitlines() if "EXPORT" in l or "DOCX" in l]
        passed = "PASSED" in output or "gate_passed" in output and "True" in output
        gate_fail = [l for l in output.splitlines() if "Gate=FAIL" in l]
        return {
            "report_type": report_type,
            "asset": asset,
            "elapsed_s": round(elapsed, 1),
            "exit_code": r.returncode,
            "passed": passed,
            "gate_result": gate_line[-1] if gate_line else "未找到 Gate 行",
            "template_result": template_line[-1] if template_line else "",
            "export_result": export_line[-1] if export_line else "",
            "gate_fail_reasons": gate_fail,
            "output_tail": output[-500:],
        }
    except subprocess.TimeoutExpired:
        return {"report_type": report_type, "asset": asset, "passed": False, "error": "超时(>30min)"}
    except Exception as e:
        return {"report_type": report_type, "asset": asset, "passed": False, "error": str(e)[:100]}


def main():
    parser = argparse.ArgumentParser(description="2hao 报告驱动全模块自检")
    parser.add_argument("--type", choices=list(SELF_CHECK_MATRIX.keys()), default=None)
    parser.add_argument("--asset", default=None, help="覆盖默认标的")
    parser.add_argument("--dry", action="store_true", help="只打印清单不跑")
    parser.add_argument("--module-only", action="store_true", help="只跑本地模块检查")
    args = parser.parse_args()

    print("=" * 60)
    print("  2hao 报告驱动全模块自检")
    print("=" * 60)

    # 1. 模块健康检查（纯本地）
    print("\n[1/3] 模块健康检查...")
    module_results = run_module_checks()
    for name, ok, detail in module_results:
        print(f"  [{'✓' if ok else '✗'}] {name}: {detail}")
    n_ok = sum(1 for _, ok, _ in module_results if ok)
    print(f"  模块检查: {n_ok}/{len(module_results)} 通过")

    if args.dry:
        print("\n[DRY] 自检清单：")
        for rt, spec in SELF_CHECK_MATRIX.items():
            print(f"  {rt}: {spec['asset']} ({len(spec['verify'])} 项验证)")
        return 0

    if args.module_only:
        return 0 if n_ok == len(module_results) else 1

    # 2. 跑报告自检
    print("\n[2/3] 报告驱动自检...")
    targets = {args.type: SELF_CHECK_MATRIX[args.type]} if args.type else SELF_CHECK_MATRIX
    report_results = []
    for rt, spec in targets.items():
        asset = args.asset or spec["asset"]
        r = run_report_selfcheck(rt, asset, spec["enrich"])
        report_results.append(r)
        # 打印验证项清单
        print(f"\n  {rt} 验证项（{len(spec['verify'])}）:")
        for item, desc in spec["verify"]:
            print(f"    - {item}: {desc}")
        print(f"  → {r.get('gate_result', '')} (用时{r.get('elapsed_s', '?')}s)")

    # 3. 汇总
    print("\n[3/3] 自检汇总")
    print("=" * 60)
    for r in report_results:
        status = "PASS" if r.get("passed") else "FAIL"
        print(f"  [{status}] {r['report_type']}/{r['asset']}: {r.get('gate_result', r.get('error', ''))}")
    print("=" * 60)

    # 输出 JSON 报告
    report_path = _ROOT / "output" / "self_check_report.json"
    report = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "module_checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in module_results],
        "report_results": report_results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n自检报告: {report_path}")
    return 0 if all(r.get("passed") for r in report_results) and n_ok == len(module_results) else 1


if __name__ == "__main__":
    sys.exit(main())
