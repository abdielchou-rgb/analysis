"""task_router.py — 任务路由器（FP8 路径光谱化落地，2026-08-07）

按任务性质选执行路径（光谱选择，替代"双轨制"二分）：
  - batch/pipeline   批量标准化 → 确定性管线（E2E+SAC+IronGate）
  - workbench        单份深度/个性化 → 工作台混合（数据层+Claude写+用户审）
  - workbench+gate   高险决策文档 → 工作台+强制人类门禁+双向溯源

路由信号：报告类型 / 意图强度（有自定义必答问题？）/ 风险等级 / 批量标志

用法：
  from core.task_router import route_task
  path = route_task(report_type="decision_memo", requirement="评估投入产出", batch=False)
  # path: {"path": "workbench+gate", "human_gate": True, "sourcing": "data_layer"}
"""

from __future__ import annotations

import logging

logger = logging.getLogger("2hao.task_router")


class TaskRouter:
    """任务 → 执行路径（光谱选择）。"""

    # 高险文档类型：必须 human-gated + 双向溯源
    HIGH_RISK_TYPES = {"decision_memo", "earnings_notes"}
    # 批量优先类型：管线更合适
    PIPELINE_PREFERRED = {"listed_company", "industry_deep"}

    def route(
        self,
        report_type: str = "listed_company",
        requirement: str = "",
        batch: bool = False,
        client: str = "",
        risk_level: str = "",
    ) -> dict:
        """路由决策。"""
        report_type = report_type or "listed_company"
        has_intent = bool(requirement or client)
        risk = risk_level or ("high" if report_type in self.HIGH_RISK_TYPES else "low")

        # 决策逻辑（光谱）
        if risk == "high":
            # 高险决策文档 → 工作台 + 强制人类门禁 + 双向溯源
            path = "workbench+gate"
            human_gate = True
            rationale = f"高险决策类型({report_type}) → 工作台+强制门禁+双向溯源"
        elif has_intent or not batch:
            # 单份深度/个性化意图 → 工作台
            path = "workbench"
            human_gate = True
            rationale = f"个性化意图({requirement[:30] or '自定义'})或单份 → 工作台混合"
        else:
            # 批量标准化 → 管线
            path = "pipeline"
            human_gate = False
            rationale = f"批量({batch})标准化类型({report_type}) → 确定性管线"

        return {
            "path": path,
            "human_gate": human_gate,
            "rationale": rationale,
            "report_type": report_type,
            "risk_level": risk,
            "batch": batch,
            "bidirectional_trace": path == "workbench+gate",  # 高险 → 双向溯源
            "requires_intent": path != "pipeline",
        }

    def suggest_execution(self, decision: dict) -> dict:
        """路由后的执行建议。"""
        path = decision["path"]
        if path == "pipeline":
            return {
                "command": "python pipeline/scheduler.py {asset} --type {report_type}",
                "notes": "确定性管线：E2E+SAC+IronGate，无需人类门禁",
            }
        elif path == "workbench":
            return {
                "command": "python -m core.workbench_executor {asset} --type {report_type} --requirement '{req}'",
                "notes": "工作台混合：数据层+AI直接写+用户审核",
            }
        else:  # workbench+gate
            return {
                "command": "python -m core.workbench_executor {asset} --type {report_type} --requirement '{req}' --human-gate",
                "notes": "工作台+强制人类门禁+双向溯源（高险决策文档）",
            }


def route_task(
    report_type: str = "listed_company",
    requirement: str = "",
    batch: bool = False,
    client: str = "",
    risk_level: str = "",
) -> dict:
    """便捷入口。"""
    return TaskRouter().route(report_type, requirement, batch, client, risk_level)
