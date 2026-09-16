# -*- coding: utf-8 -*-
"""
E2E Pipeline - AnalysisEngine Integration for write_sections

这个模块提供使用 AnalysisEngine 的 write_sections 节点实现，
替代原来基于 SectionWriter 的实现。
"""

from __future__ import annotations

from __future__ import annotations

from typing import Any, Dict, List, Optional
import os
import logging

logger = logging.getLogger("2hao.e2e.integration")


async def write_sections_with_analysis_engine(node_id: str, context: dict) -> dict:
    """
    使用 AnalysisEngine 执行写作阶段
    
    替代原有的 E2ENodes.write_sections 实现
    """
    from core.analysis_engine import AnalysisEngine, ExecutionConfig, ExecutionMode
    from core.analysis_context import (
        AnalysisContext, Intent, IntentType, AnalysisMode,
        EvidenceBundle, FindingStore
    )
    from core.analysis_engine import AnalysisEngine, ExecutionConfig, ExecutionMode
    from core.analysis_context import (
        AnalysisContext, Intent, IntentType, AnalysisMode,
        EvidenceBundle, FindingStore
    )
    
    # 从 context 获取必要信息
    asset = context.get("asset", "")
    report_type = context.get("report_type", "industry_deep")
    style = context.get("style", "cicc")
    
    # 创建 Intent
    from core.analysis_context import Intent, IntentType, AnalysisMode
    intent = Intent(
        asset=context.get("asset", ""),
        report_type=IntentType(report_type),
        style=context.get("style", "cicc"),
        mode=ExecutionMode.BATCH,
    )
    
    # 创建初始 Context
    context_obj = AnalysisContext(
        version=1,
        parent_hash="",
        intent=Intent(
            asset=context.get("asset", ""),
            report_type=report_type,
            style=style,
        ),
        mode=AnalysisMode.BATCH,
        evidence=None,  # 稍后填充
        methods=(),
        findings=None,
        sections=(),
    )
    
    # 准备证据包
    from core.analysis_context import EvidenceBundle, FindingStore
    evidence = EvidenceBundle()
    evidence.raw_data = context.get("collected_data", {}) or {}
    evidence.chart_data = context.get("chart_data", {}) or {}
    
    # 运行 AnalysisEngine
    engine = AnalysisEngine.get_instance()
    await engine.initialize()
    
    result = await engine.run(
        asset=context.get("asset", ""),
        report_type=context.get("report_type", "industry_deep"),
        style=context.get("style", "cicc"),
        mode=ExecutionMode.BATCH,
        custom_requirements=context.get("custom_requirements", ""),
        client_questions=context.get("client_questions"),
    )
    
    # 将结果写回 context
    context_obj = result.context
    context["report_text"] = context_obj.get("report_text", "") if context_obj else ""
    context["gate_result"] = context_obj.get("gate_result", {}) if context_obj else {}
    context["gate_result"]["overall_score"] = context_obj.get("gate_result", {}).get("overall_score", 0) if context_obj else 0
    context["gate_result"]["passed"] = context_obj.get("gate_result", {}).get("passed", False) if context_obj else False
    
    return {"report_text": context["report_text"]}


# 兼容原有接口的同步包装器（用于 AgentGraph 节点）
def write_sections_integrated(node_id: str, context: dict) -> dict:
    """
    兼容原有 AgentGraph 节点接口的同步包装器
    """
    import asyncio
    
    # 检查是否已经在事件循环中
    try:
        loop = asyncio.get_running_loop()
        # 如果已经在事件循环中，创建新任务
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, write_sections_with_analysis_engine(node_id, context))
            return future.result()
    except RuntimeError:
        # 没有运行的事件循环，直接运行
        return asyncio.run(write_sections_with_analysis_engine("write_sections", context))


# 保持兼容性的同步包装器
def write_sections_integrated(node_id: str, context: dict) -> dict:
    """
    兼容原有 AgentGraph 节点接口的同步包装器
    """
    try:
        loop = asyncio.get_running_loop()
        # 如果已经在事件循环中，创建新任务
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, write_sections_with_analysis_engine(node_id, context))
            return future.result()
    except RuntimeError:
        # 没有运行的事件循环，直接运行
        return asyncio.run(write_sections_with_analysis_engine(node_id, context))