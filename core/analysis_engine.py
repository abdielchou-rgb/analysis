# -*- coding: utf-8 -*-
"""
AnalysisEngine - 统一分析引擎入口

核心原则：
- 唯一执行入口：Workbench 和 Pipeline 都通过此入口
- AnalysisContext 单例贯穿全链路
- 认知层单例化：Intent Parser、Method Selector、Finding Store、Verification Engine 只有一个实现
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.analysis_context import (
    AnalysisContext,
    AnalysisMode,
    EvidenceBundle,
    FindingStore,
    Intent,
    IntentType,
)


class ExecutionMode(Enum):
    INTERACTIVE = "interactive"
    BATCH = "batch"
    FAST = "fast"
    DEGRADED = "degraded"


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


def _default_timeout_per_stage():
    return {
        "intent": 5.0,
        "research": 30.0,
        "data": 90.0,
        "compute": 30.0,
        "write": 180.0,
        "gate": 30.0,
        "revision": 120.0,
        "export": 30.0,
    }


def _default_fallback_models():
    return ["deepseek", "zhipu", "openrouter"]


@dataclass(frozen=True)
class ExecutionConfig:
    """执行配置 - 不可变"""

    mode: "ExecutionMode" = ExecutionMode.BATCH
    max_attempts: int = 3
    timeout_per_stage: Dict[str, float] = field(default_factory=_default_timeout_per_stage)
    enable_cache: bool = True
    fallback_models: List[str] = field(default_factory=lambda: ["deepseek", "zhipu", "openrouter"])
    max_llm_calls: int = 100
    wall_clock_budget: float = 600.0


@dataclass
class ExecutionResult:
    """执行结果"""

    status: "ExecutionStatus"
    context: Optional["AnalysisContext"] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class AnalysisEngine:
    """
    统一分析引擎 - 唯一执行入口

    Workbench (interactive) 和 Pipeline (batch) 都通过此入口执行。
    保证认知层单例化：Intent Parser、Method Selector、Finding Store、Verification Engine 只有一个实现。
    """

    _instance: Optional["AnalysisEngine"] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        # 核心组件（延迟初始化）
        self._intent_parser = None
        self._method_selector = None
        self._method_executor = None
        self._finding_store = None
        self._verification_engine = None
        self._section_generator = None
        self._report_assembler = None

        # 运行时状态
        self._active_contexts: Dict[str, "AnalysisContext"] = {}
        self._execution_history: List["AnalysisContext"] = []

    async def initialize(self):
        """初始化所有核心组件"""
        if self._intent_parser is not None:
            return

        # 延迟导入避免循环依赖
        from core.analysis_context import FindingStore
        from core.intent_parser import IntentParser
        from core.method_registry import MethodExecutor
        from core.method_selector import MethodSelector
        from core.report_assembler import ReportAssembler
        from core.section_generator import SectionGenerator
        from core.verification_engine import VerificationEngine

        self._intent_parser = IntentParser()
        self._method_selector = MethodSelector()
        self._method_executor = MethodExecutor()
        self._finding_store = FindingStore()
        self._verification_engine = VerificationEngine()
        self._section_generator = SectionGenerator()
        self._report_assembler = ReportAssembler()

    async def run(
        self,
        asset: str,
        report_type: str = "industry_deep",
        style: str = "cicc",
        mode: ExecutionMode = ExecutionMode.BATCH,
        custom_requirements: Optional[str] = None,
        client_questions: Optional[List[str]] = None,
        config: Optional["ExecutionConfig"] = None,
    ) -> "ExecutionResult":
        """
        统一执行入口

        Args:
            asset: 分析标的
            report_type: 报告类型
            style: 写作风格
            mode: 执行模式
            custom_requirements: 自定义需求
            client_questions: 委托方问题清单
            config: 执行配置

        Returns:
            ExecutionResult: 执行结果包含 context 和 metrics
        """
        await self.initialize()

        config = config or ExecutionConfig(mode=mode)
        started_at = datetime.now()

        # 创建初始 Context
        intent = Intent(
            asset=asset,
            report_type=IntentType(report_type),
            style=style,
            mode=ExecutionMode(mode.value) if isinstance(mode, ExecutionMode) else ExecutionMode.BATCH,
            custom_requirements=frozenset([custom_requirements]) if custom_requirements else frozenset(),
            client_questions=tuple(client_questions) if client_questions else tuple(),
        )

        context = AnalysisContext(
            version=1,
            parent_hash="",
            intent=intent,
            mode=ExecutionMode(mode.value) if isinstance(mode, ExecutionMode) else AnalysisMode.BATCH,
            evidence=EvidenceBundle(),
            methods=(),
            findings=FindingStore(),
            sections=(),
        )

        # 执行阶段
        try:
            context = await self._execute_pipeline(context, config)
            status = ExecutionStatus.COMPLETED
        except Exception as e:
            status = ExecutionStatus.FAILED
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                context=None,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(),
            )

        completed_at = datetime.now()
        return ExecutionResult(
            status=status,
            context=context,
            metrics=self._compute_metrics(context, started_at, completed_at),
            started_at=started_at,
            completed_at=completed_at,
        )

    async def _execute_pipeline(self, context: "AnalysisContext", config: "ExecutionConfig") -> "AnalysisContext":
        """执行完整流水线"""
        # 阶段 1: Intent 解析
        context = await self._stage_intent(context)

        # 阶段 2: 研究规划
        context = await self._stage_research(context)

        # 阶段 3: 数据采集
        context = await self._stage_data(context)

        # 阶段 4: 方法选择
        context = await self._stage_method_selection(context)

        # 阶段 4: 计算执行
        context = await self._stage_compute(context)

        # 阶段 5: 发现生成
        context = await self._stage_findings(context)

        # 阶段 6: 章节生成
        context = await self._stage_write(context)

        # 阶段 7: 验证
        context = await self._stage_verify(context)

        # 阶段 8: 修订（如需要）
        if context.gate_results and not context.gate_results.passed:
            context = await self._stage_revise(context)

        # 阶段 8: 导出
        context = await self._stage_export(context)

        return context

    # ===== 阶段实现（占位，后续 Phase 2-4 填充）=====

    async def _stage_intent(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 1: Intent 解析"""
        return context

    async def _stage_research(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 2: 研究规划"""
        return context

    async def _stage_data(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 3: 数据采集"""
        return context

    async def _stage_method_selection(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 4: 方法选择"""
        return context

    async def _stage_compute(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 5: 计算执行"""
        return context

    async def _stage_findings(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 6: 发现生成"""
        return context

    async def _stage_write(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 7: 章节生成"""
        return context

    async def _stage_verify(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 7: 验证"""
        return context

    async def _stage_revise(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 9: 修订"""
        return context

    async def _stage_export(self, context: "AnalysisContext") -> "AnalysisContext":
        """阶段 10: 导出"""
        return context

    def _compute_metrics(self, context: "AnalysisContext", started: datetime, completed: datetime) -> Dict[str, Any]:
        """计算执行指标"""
        return {
            "total_time": (completed - started).total_seconds(),
            "gate_score": context.gate_results.score if context.gate_results else 0,
            "sections_count": len(context.sections),
            "findings_count": len(context.findings.findings),
            "evidence_count": len(context.evidence.chart_data),
        }

    @classmethod
    def get_instance(cls) -> "AnalysisEngine":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = AnalysisEngine()
        return cls._instance


# 便捷函数
async def run_analysis(
    asset: str, report_type: str = "industry_deep", style: str = "cicc", mode: str = "batch", **kwargs
) -> "ExecutionResult":
    """便捷函数：运行分析"""
    engine = AnalysisEngine.get_instance()
    return await engine.run(asset=asset, report_type=report_type, style=style, mode=ExecutionMode(mode), **kwargs)
