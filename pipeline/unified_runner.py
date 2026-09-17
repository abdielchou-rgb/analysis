# -*- coding: utf-8 -*-
"""
E2E Pipeline Runner - 统一管线运行器

使用 AnalysisEngine 作为核心引擎，保持与现有管线的兼容性
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from core.analysis_context import (
    AnalysisContext,
    AnalysisMode,
    EvidenceBundle,
    FindingStore,
    Intent,
)
from core.analysis_engine import ExecutionConfig, ExecutionMode


class PipelineRunner:
    """统一管线运行器 - 使用 AnalysisEngine 作为核心引擎"""

    def __init__(self):
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from core.analysis_engine import AnalysisEngine

            self._engine = AnalysisEngine.get_instance()
        return self._engine

    async def run(
        self,
        asset: str,
        report_type: str = "industry_deep",
        style: str = "cicc",
        mode: str = "batch",
        custom_requirements: str = "",
        client_questions: List[str] = None,
        output_dir: str = "output",
        config: Dict = None,
    ) -> Dict[str, Any]:
        """统一运行入口"""

        config = config or {}
        context = config.copy()

        # 准备上下文
        context = {
            "asset": asset,
            "report_type": report_type,
            "style": style,
            "attempt": 0,
            "degradation_level": 0,
            "collected_data": {},
            "output_dir": config.get("output_dir", output_dir) if isinstance(config, dict) else output_dir,
        }

        # 创建 AnalysisEngine 配置
        mode_map = {
            "batch": ExecutionMode.BATCH,
            "interactive": ExecutionMode.INTERACTIVE,
            "fast": ExecutionMode.FAST,
            "degraded": ExecutionMode.DEGRADED,
        }

        mode_enum = mode_map.get(mode.lower(), ExecutionMode.BATCH)

        config_obj = ExecutionConfig(
            mode=mode_enum,
            max_attempts=3,
        )

        # 创建 Intent
        intent = Intent(
            asset=asset,
            report_type=report_type,
            style=style,
            mode=mode_enum,
        )

        # 创建初始 Context
        context_obj = AnalysisContext(
            version=1,
            parent_hash="",
            intent=Intent(
                asset=asset,
                report_type=report_type,
                style=style,
                mode=AnalysisMode.BATCH,
            ),
            mode=AnalysisMode.BATCH,
            evidence=EvidenceBundle(),
            methods=(),
            findings=FindingStore(),
            sections=(),
        )

        # 运行 AnalysisEngine
        engine = self._get_engine()
        await engine.initialize()

        result = await engine.run(
            asset=asset,
            report_type=report_type,
            style=style,
            mode=mode_enum,
            custom_requirements=config.get("custom_requirements", "") if isinstance(config, dict) else "",
            client_questions=config.get("client_questions") if isinstance(config, dict) else None,
        )

        # 构建结果
        context_obj = result.context
        gate_result = context_obj.get("gate_result", {}) if context_obj else {}

        return {
            "result": result,
            "context": context_obj,
            "status": result.status.value if hasattr(result, "status") else "unknown",
            "gate_score": gate_result.get("overall_score", 0) if gate_result else 0,
            "gate_passed": gate_result.get("passed", False) if gate_result else False,
        }

    def _get_engine(self):
        if self._engine is None:
            from core.analysis_engine import AnalysisEngine

            self._engine = AnalysisEngine.get_instance()
        return self._engine

    async def run_legacy_fallback(
        self, asset: str, report_type: str = "industry_deep", style: str = "cicc", **kwargs
    ) -> Dict[str, Any]:
        """回退到旧版管线"""
        logger.warning("回退到旧版管线")

        # 使用旧版编排器
        from pipeline.e2e_orchestrator import E2EOrchestratorV2

        orchestrator = E2EOrchestratorV2(
            asset=asset,
            report_type=report_type,
            style=style,
        )

        context = {
            "asset": asset,
            "report_type": report_type,
            "style": style,
            "attempt": 0,
            "degradation_level": 0,
            "collected_data": {},
            "output_dir": "output",
        }

        # 运行旧管线
        result = await orchestrator.run(context)
        return {"result": result, "legacy": True}

    async def run(
        self,
        asset: str,
        report_type: str = "industry_deep",
        style: str = "cicc",
        mode: str = "batch",
        custom_requirements: str = "",
        client_questions: List[str] = None,
        output_dir: str = "output",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        统一运行入口

        根据配置决定使用新引擎还是旧管线
        """
        if not kwargs.get("use_analysis_engine", True):
            return await self.run_legacy_fallback(asset=asset, report_type=report_type, style=style, **kwargs)

        try:
            return await self.run_new_engine(
                asset=asset,
                report_type=report_type,
                style=style,
                mode=mode,
                custom_requirements=kwargs.get("custom_requirements", ""),
                client_questions=kwargs.get("client_questions"),
                output_dir=output_dir,
            )
        except Exception as e:
            logger.error(f"AnalysisEngine 执行失败: {e}")
            if kwargs.get("fallback_to_legacy", True):
                logger.warning("回退到旧版管线")
                return await self.run_legacy_fallback(asset=asset, report_type=report_type, style=style, **kwargs)
            raise


# 便捷函数
async def run_unified(
    asset: str,
    report_type: str = "industry_deep",
    style: str = "cicc",
    mode: str = "batch",
    custom_requirements: str = "",
    client_questions: List[str] = None,
    output_dir: str = "output",
) -> Dict[str, Any]:
    """统一运行入口"""
    runner = PipelineRunner()
    return await runner.run(
        asset=asset,
        report_type=report_type,
        style=style,
        mode=mode,
        custom_requirements=custom_requirements,
        client_questions=client_questions,
        output_dir=output_dir,
    )


def run_pipeline(
    asset: str,
    report_type: str = "industry_deep",
    style: str = "cicc",
    output_dir: str = "output",
) -> Dict[str, Any]:
    """同步版本入口"""
    return asyncio.run(
        run_unified(
            asset=asset,
            report_type=report_type,
            style=style,
            mode="batch",
            output_dir=output_dir,
        )
    )


def run_workbench(
    asset: str,
    report_type: str = "decision_memo",
    style: str = "cicc",
    requirement: str = "",
    human_gate: bool = True,
    output_dir: str = "output",
) -> Dict[str, Any]:
    """Workbench 模式入口"""
    # TODO: 实现 Workbench 模式集成
    pass


# 兼容旧接口
def run_e2e_pipeline(
    asset: str,
    report_type: str = "industry_deep",
    style: str = "cicc",
    output_dir: str = "output",
) -> Dict[str, Any]:
    """兼容旧接口"""
    return run_pipeline(asset, report_type, style, output_dir)


# 导出
__all__ = [
    "PipelineRunner",
    "run_unified",
    "run_pipeline",
    "run_workbench",
    "run_e2e_pipeline",
]
