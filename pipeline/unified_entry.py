# -*- coding: utf-8 -*-
"""
Unified Entry Point - 统一分析入口

统一 Workbench 和 Pipeline 的执行入口，使用 AnalysisEngine 作为核心引擎。
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.analysis_engine import ExecutionConfig, ExecutionMode


@dataclass
class UnifiedRunConfig:
    """统一运行配置"""

    asset: str
    report_type: str = "industry_deep"
    style: str = "cicc"
    mode: str = "batch"  # batch, interactive, fast
    custom_requirements: str = ""
    client_questions: List[str] = None
    output_dir: str = "output"
    max_attempts: int = 3
    human_gate: bool = False  # Workbench 模式是否需要人工门禁
    requirement: str = ""  # Workbench 特有：决策需求

    def __post_init__(self):
        if self.client_questions is None:
            self.client_questions = []


@dataclass
class UnifiedRunResult:
    """统一运行结果"""

    success: bool
    report_path: Optional[str] = None
    markdown_path: Optional[str] = None
    docx_path: Optional[str] = None
    gate_score: float = 0.0
    gate_passed: bool = False
    error: Optional[str] = None
    context: Any = None
    metrics: Dict = None


class UnifiedAnalyzer:
    """统一分析器 - 统一 Workbench 和 Pipeline 的执行入口"""

    def __init__(self):
        self._engine = None

    @property
    def engine(self):
        if not hasattr(self, "_engine") or self._engine is None:
            from core.analysis_engine import AnalysisEngine

            self._engine = AnalysisEngine.get_instance()
        return self._engine

    async def run(self, config: UnifiedRunConfig) -> UnifiedRunResult:
        """统一运行入口"""
        try:
            # 创建执行配置
            mode_map = {"batch": "batch", "interactive": "interactive", "fast": "fast", "degraded": "degraded"}

            config = ExecutionConfig(
                mode=config.mode if isinstance(config.mode, str) else config.mode.value,
                max_attempts=config.max_attempts,
            )

            # 运行引擎
            result = await self.engine.run(
                asset=config.asset,
                report_type=config.report_type,
                style=config.style,
                mode=ExecutionMode(config.mode) if isinstance(config.mode, str) else config.mode,
                custom_requirements=config.requirement or config.custom_requirements,
                client_questions=config.client_questions,
            )

            # 构建结果
            context = result.context
            gate_result = context.get("gate_result", {}) if context else {}

            return UnifiedRunResult(
                success=result.status == "completed",
                markdown_path=context.get("report_path") if context else None,
                docx_path=context.get("_docx_path") if context else None,
                gate_score=context.get("gate_result", {}).get("overall_score", 0) if context else 0,
                gate_passed=context.get("gate_result", {}).get("passed", False) if context else False,
                error=result.error,
                context=context,
                metrics=result.metrics,
            )

        except Exception as e:
            return UnifiedRunResult(success=False, error=str(e))

    async def run_workbench(self, config: UnifiedRunConfig) -> UnifiedRunResult:
        """Workbench 模式运行 - 包含人工门禁"""
        config.human_gate = True
        config.mode = "interactive"
        return await self.run(config)

    async def run_pipeline(self, config: UnifiedRunConfig) -> UnifiedRunResult:
        """Pipeline 模式运行 - 批量处理"""
        config.human_gate = False
        config.mode = "batch"
        return await self.run(config)


# 便捷函数
async def run_analysis(
    asset: str,
    report_type: str = "industry_deep",
    style: str = "cicc",
    mode: str = "batch",
    custom_requirements: str = "",
    client_questions: List[str] = None,
    output_dir: str = "output",
    max_attempts: int = 3,
) -> UnifiedRunResult:
    """便捷函数：运行分析"""
    config = UnifiedRunConfig(
        asset=asset,
        report_type=report_type,
        style=style,
        mode=mode,
        custom_requirements=custom_requirements,
        client_questions=client_questions or [],
        output_dir=output_dir,
        max_attempts=3,
    )
    analyzer = UnifiedAnalyzer()
    return await analyzer.run(config)


async def run_workbench(
    asset: str,
    report_type: str = "decision_memo",
    style: str = "cicc",
    requirement: str = "",
    human_gate: bool = True,
    output_dir: str = "output",
) -> UnifiedRunResult:
    """便捷函数：运行 Workbench 模式"""
    config = UnifiedRunConfig(
        asset=asset,
        report_type=report_type,
        style=style,
        mode="interactive",
        custom_requirements="",
        requirement=requirement,
        human_gate=human_gate,
        output_dir=output_dir,
    )
    analyzer = UnifiedAnalyzer()
    return await analyzer.run_workbench(config)


async def run_pipeline(
    asset: str,
    report_type: str = "industry_deep",
    style: str = "cicc",
    output_dir: str = "output",
) -> UnifiedRunResult:
    """便捷函数：运行 Pipeline 模式"""
    config = UnifiedRunConfig(
        asset=asset,
        report_type=report_type,
        style=style,
        mode="batch",
        output_dir=output_dir,
    )
    analyzer = UnifiedAnalyzer()
    return await analyzer.run_pipeline(config)


# CLI 入口
async def main():
    import argparse

    parser = argparse.ArgumentParser(description="二号分析师 - 统一分析入口")
    parser.add_argument("asset", help="分析标的")
    parser.add_argument(
        "--type",
        default="industry_deep",
        choices=["listed_company", "industry_deep", "unlisted_company", "earnings_notes", "decision_memo"],
    )
    parser.add_argument("--style", default="cicc", choices=["cicc", "gs", "mck", "ms", "jpm", "bcg"])
    parser.add_argument("--mode", default="batch", choices=["batch", "interactive", "fast"])
    parser.add_argument("--requirement", default="", help="决策需求")
    parser.add_argument("--human-gate", action="store_true", help="启用人工门禁")
    parser.add_argument("--output", default="output", help="输出目录")

    args = parser.parse_args()

    config = UnifiedRunConfig(
        asset=args.asset,
        report_type=args.type,
        style=args.style,
        mode=args.mode,
        human_gate=args.human_gate,
        output_dir=args.output,
    )

    analyzer = UnifiedAnalyzer()
    result = await UnifiedAnalyzer().run(config)

    if result.success:
        print("✅ 分析完成")
        if result.markdown_path:
            print(f"📄 Markdown: {result.markdown_path}")
        if result.docx_path:
            print(f"📄 DOCX: {result.docx_path}")
        print(f"Gate Score: {result.gate_score:.2f} ({'通过' if result.gate_passed else '未通过'})")
    else:
        print(f"❌ 分析失败: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
