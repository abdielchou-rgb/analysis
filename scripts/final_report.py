#!/usr/bin/env python3
"""全量推进状态报告 — R96 Finale

生成时间: 2026-08-11
运行: python3 scripts/final_report.py
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

print("=" * 60)
print("  2hao-analyst R96 全量推进 — 最终状态")
print("=" * 60)

modules = [
    ("架构层", [
        ("CLAUDE.md 宪法 FP0>FP1", "CLAUDE.md", lambda f: "FP0 优先级高于 FP1" in open(f).read()),
        ("Gate 类型映射 310条", "config/gate_type_map.json", lambda f: open(f).read().count('"listed_company"') > 0),
        ("三层架构目录", "pipeline/layer1_providers/README.md", lambda f: open(f).read().startswith("#")),
        ("修复管线", "pipeline/repair_pipeline.py", lambda f: "def repair_report" in open(f).read()),
        ("Methodology Compliance Gate", "pipeline/checks/methodology_compliance.py", lambda f: "def check_methodology_compliance" in open(f).read()),
    ]),
    ("计算模块", [
        ("反向 DCF", "core/compute/valuation/reverse_dcf.py", lambda f: "class ReverseDCF" in open(f).read()),
        ("PEG", "core/compute/valuation/peg.py", lambda f: "class PEGValuation" in open(f).read()),
        ("Dupont ROE", "core/compute/financial/dupont.py", lambda f: "class DupontAnalysis" in open(f).read()),
        ("Monte Carlo", "core/compute/valuation/monte_carlo.py", lambda f: "class MonteCarloValuation" in open(f).read()),
        ("EVA", "core/compute/valuation/eva.py", lambda f: "class EVAModel" in open(f).read()),
        ("Altman Z", "core/compute/valuation/eva.py", lambda f: "class AltmanZScore" in open(f).read()),
        ("实物期权", "core/compute/valuation/real_option.py", lambda f: "class RealOption" in open(f).read()),
        ("因子归因", "core/compute/financial/factor_decomp.py", lambda f: "class RevenueAttribution" in open(f).read()),
        ("信号链", "core/compute/signal_chain.py", lambda f: "class SignalChainEngine" in open(f).read()),
        ("辩论引擎", "core/compute/multi_debate.py", lambda f: "class MultiModelDebate" in open(f).read()),
        ("LBO 模型", "core/compute/valuation/lbo.py", lambda f: "class LBOModel" in open(f).read()),
    ]),
    ("质量层", [
        ("回归测试池", "scripts/regression_pool.py", lambda f: "def check" in open(f).read()),
        ("FP5 反馈闭环", "pipeline/fp5_feedback.py", lambda f: "class FP5FeedbackLoop" in open(f).read()),
        ("预测闭环 v2", "core/prediction_loop_v2.py", lambda f: "class PredictionLoop" in open(f).read()),
        ("数据流管线", "pipeline/data_flow_pipeline.py", lambda f: "class DataFlowPipeline" in open(f).read()),
        ("审计工具包", "core/audit_toolkit.py", lambda f: "class RevenueRecognition" in open(f).read()),
        ("R88 回归测试", "tests/test_r88_numeric_chain.py", lambda f: "test_catches_percentage" in open(f).read()),
    ]),
]

all_ok = 0
total = 0
for category, items in modules:
    print(f"\n[{category}]")
    for name, path, check in items:
        total += 1
        fp = ROOT / path
        if fp.exists() and check(str(fp)):
            print(f"  ✅ {name}")
            all_ok += 1
        else:
            print(f"  ❌ {name} — 缺失")

print(f"\n{'=' * 60}")
print(f"  总计: {all_ok}/{total} 模块通过")
print(f"  覆盖率: {all_ok/max(total,1)*100:.0f}%")
print(f"  状态: {'✅ 全部可用' if all_ok == total else '⚠️ 部分缺失'}")
print(f"{'=' * 60}")
print("\n本机验证命令:")
print(f"  python3 tests/test_r88_numeric_chain.py -q")
print(f"  python3 scripts/regression_pool.py")