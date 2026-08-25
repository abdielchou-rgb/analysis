#!/usr/bin/env python3
"""三层架构迁移脚本 — 将核心计算模块迁移到三层架构目录结构

Layer 1 (providers): 确定性计算服务层（非 LLM，可审计，可复现）
Layer 2 (fallback): 自动兜底层（LLM 不可用时降级）
Layer 3 (audit): 审计追踪层（全链路可追溯）
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_COMPUTE = Path(__file__).resolve().parent.parent / "core" / "compute"
LAYER1 = Path(__file__).resolve().parent.parent / "pipeline" / "layer1_providers"
LAYER2 = Path(__file__).resolve().parent.parent / "pipeline" / "layer2_fallback"
LAYER3 = Path(__file__).resolve().parent.parent / "pipeline" / "layer3_audit"

# Layer 1: 确定性服务层（非 LLM，可审计，可复现）
LAYER1_MODULES = {
    "valuation": [
        "dcf.py",
        "reverse_dcf.py",
        "comparable.py",
        "monte_carlo.py",
        "real_option.py",
        "eva.py",
        "peg.py",
        "lbo.py",
        "sotp.py",
    ],
    "financial": [
        "dupont.py",
        "factor_decomp.py",
        "three_statement.py",
    ],
    "engines": [
        "signal_chain.py",
        "multi_debate.py",
    ],
    "other": [
        "data_caliber.py",
        "data_provenance.py",
        "predict_model.py",
    ],
}

# Layer 2: 自动兜底层（LLM 不可用时降级）
LAYER2_MODULES = {
    "llm": [
        "deepseek_client.py",
    ],
    "data": [
        "data_enrichment.py",
        "data_feeds.py",
    ],
    "fp5": [
        "fp5_feedback.py",
    ],
    "llm_providers": [
        "llm_provider.py",
        "agent_provider.py",
    ],
}

# Layer 3: 审计追踪层
LAYER3_MODULES = [
    "iron_gate.py",
    "checks/base.py",
    "checks/data_quality_mixin.py",
    "checks/analysis_mixin.py",
    "checks/llm_checks_mixin.py",
    "checks/coverage_mixin.py",
    "checks/content_format_mixin.py",
    "core/data_provenance.py",
    "core/data_contract.py",
    "pipeline/fp5_feedback.py",
]


def create_layer_dirs():
    """创建三层目录结构"""
    dirs = [
        "pipeline/layer1_providers/valuation",
        "pipeline/layer1_providers/financial",
        "pipeline/layer1_providers/engines",
        "pipeline/layer2_fallback/llm",
        "pipeline/layer2_fallback/data",
        "pipeline/layer2_fallback/fp5",
        "pipeline/layer3_audit",
    ]
    for d in [
        Path(__file__).resolve().parent.parent / "pipeline" / d
        for d in [
            "layer1_providers",
            "layer1_providers/valuation",
            "layer1_providers/financial",
            "layer1_providers/engines",
            "layer2_fallback",
            "layer2_fallback/llm",
            "layer2_fallback/data",
            "layer2_fallback/fp5",
            "layer3_audit",
        ]
    ]:
        d.mkdir(parents=True, exist_ok=True)
        print(f"Created: {d}")


def create_layer_init(layer_path: Path, modules: list, layer_name: str):
    """创建层的 __init__.py，导出所有模块的公共 API"""
    content = f"# {layer_name} - 自动生成的导出\n"
    content += "# 自动生成于迁移脚本\n\n"

    exports = []
    for mod in modules:
        mod_name = mod.replace(".py", "")
        if layer_name == "Layer 1":
            # Layer 1: 计算模块
            if mod in [
                "dcf.py",
                "reverse_dcf.py",
                "comparable.py",
                "monte_carlo.py",
                "real_option.py",
                "eva.py",
                "peg.py",
                "lbo.py",
                "sotp.py",
            ]:
                exports = [
                    "DCFResult",
                    "compute_dcf",
                    "ReverseDCF",
                    "ReverseDCFResult",
                    "ComparableResult",
                    "MonteCarloValuation",
                    "MCResult",
                    "RealOption",
                    "RealOptionResult",
                    "EVAModel",
                    "EVAResult",
                    "AltmanZScore",
                    "PEGValuation",
                    "PEGResult",
                    "LBOModel",
                    "LBOResult",
                    "SOTPValuation",
                    "DupontAnalysis",
                    "RevenueAttribution",
                    "AttributionResult",
                    "SignalChainEngine",
                    "SignalResult",
                    "MultiModelDebate",
                    "DebateResult",
                ]
    content += "\n".join([f"from . import {m}" for m in modules]) + "\n"
    # 简化：只导出模块名
    exports = "\n".join([f"from . import {m.replace('.py', '')}" for m in modules])
    content += exports + "\n"

    init_path = Path(__file__).resolve().parent.parent / "pipeline" / layer_name / "__init__.py"
    init_path.parent.mkdir(parents=True, exist_ok=True)
    init_path.write_text(content, encoding="utf-8")
    print(f"Created: {init_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="三层架构迁移脚本")
    parser.add_argument("--dry-run", action="store_true", help="预览不执行")
    parser.add_argument("--apply", action="store_true", help="执行迁移")
    args = parser.parse_args()

    if not (args.dry_run or args.apply):
        print("请指定 --dry-run 或 --apply")
        return

    print("=== 三层架构迁移开始 ===")
    create_layer_dirs()

    # 创建各层 __init__.py
    LAYER1 = Path(__file__).resolve().parent.parent / "pipeline" / "layer1_providers"
    LAYER2 = Path(__file__).resolve().parent.parent / "pipeline" / "layer2_fallback"
    LAYER3 = Path(__file__).resolve().parent.parent / "pipeline" / "layer3_audit"

    # 这里简化处理，实际迁移需要更细致的文件移动和 import 重写
    print("Layer 1 (providers): 确定性计算模块")
    print("  - valuation: dcf, reverse_dcf, comparable, monte_carlo, real_option, eva, peg, lbo, sotp")
    print("  - financial: dupont, factor_decomp, three_statement")
    print("  - engines: signal_chain, multi_debate")
    print("  - data: data_caliber, data_provenance, predict_model")

    print("\nLayer 2 (fallback): LLM 降级 + 数据兜底 + FP5 反馈")
    print("  - llm: deepseek_client")
    print("  - data: data_enrichment, data_feeds")
    print("  - fp5: fp5_feedback")

    print("\nLayer 3 (audit): 审计追踪层")
    print("  - iron_gate, checks/, data_provenance, data_contract")
    print("  - fp5_feedback")

    print("\n[INFO] 目录结构已创建，需手动完成模块迁移和 import 路径更新")
    print("后续步骤：")
    print("1. 将 core/compute/valuation/*.py 复制到 pipeline/layer1_providers/valuation/")
    print("  并更新 import 路径")
    print("  2. 创建 pipeline/layer1_providers/__init__.py 导出所有公共 API")
    print("  3. 更新 pipeline/e2e_orchestrator.py 等文件的 import 路径")
    print("  4. 运行回归测试验证迁移正确性")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="三层架构迁移脚本")
    parser.add_argument("--dry-run", action="store_true", help="预览不执行")
    parser.add_argument("--apply", action="store_true", help="执行迁移")
    args = parser.parse_args()

    if not (args.dry_run or args.apply):
        print("请指定 --dry-run 或 --apply")
    else:
        main()

if __name__ == "__main__":
    main()
