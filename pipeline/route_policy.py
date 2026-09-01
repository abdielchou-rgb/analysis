"""route_policy.py — 双模式节点级混编路由（2026-08-07）

替代 run_reports.py 的 MODE_LLM 整篇映射。双模式 = 路由策略差异，不是 provider 全换：
  - perf  性能模式：DeepSeek 扛关键链 + Marvis 后台预取 + OpenRouter 圆桌
  - train 训练模式：Marvis 大量产草稿 + DeepSeek 终审关键链（合并/修订质量红线）

关键设计：
  - merge（合并组装）两个模式都走 DeepSeek（质量重灾区，ACL 2025）
  - L0 全 Python（模式无关，0 token）
  - train 模式 Marvis 产 + DeepSeek 抽检修订，吃满免费额度但质量付费兜底
  - roundtable 用"异于本模式主力"的源（防同源偏差）

用法：
  from pipeline.route_policy import resolve_provider, route_info
  p = resolve_provider("merge", mode="train")  # -> "deepseek"
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("2hao.route_policy")

# 模式 → 节点 → provider 路由策略（2026-08-30: opencode_go 已损坏，写作任务切 zhipu）
ROUTE_POLICY = {
    "perf": {
        "write": "zhipu",  # 论点单元写作：zhipu/glm-4.7
        "skeleton": "zhipu",  # 骨架/大纲：zhipu
        "merge": "deepseek",  # 合并组装：DeepSeek（质量红线）
        "revise": "zhipu",  # 修订（Gate 反馈）：zhipu
        "extract": "openrouter",  # 轻量提取/分类：OpenRouter flash
        "prefetch": "agent_provider",  # 后台预取：Marvis 免费
        "roundtable": "opencode_zen",  # 终局圆桌：OpenCode Zen 异源
        "research_planner": "zhipu",  # 研究规划：zhipu（快速）
    },
    "train": {
        "write": "agent_provider",  # 论点单元写作：Marvis（免费训练）
        "skeleton": "agent_provider",  # 骨架：Marvis
        "merge": "openrouter",  # 合并组装：OpenRouter（质量红线，永不 Marvis）
        "revise": "agent_provider",  # 修订：Marvis（训练用）
        "extract": "agent_provider",  # 提取：Marvis
        "prefetch": "",  # 训练模式不需要预取（自己就是免费）
        "roundtable": "openrouter",  # 圆桌：OpenRouter（异于训练源 Marvis）
    },
}

# 节点别名归一化
_NODE_ALIASES = {
    "write": "write",
    "section": "write",
    "group": "write",
    "draft": "write",
    "merge": "merge",
    "assemble": "merge",
    "editor": "merge",
    "revise": "revise",
    "edit": "revise",
    "fix": "revise",
    "extract": "extract",
    "classify": "extract",
    "summarize": "extract",
    "skeleton": "skeleton",
    "outline": "skeleton",
    "plan": "skeleton",
    "research_planner": "research_planner",
    "roundtable": "roundtable",
    "critic": "roundtable",
    "review": "roundtable",
    "prefetch": "prefetch",
}


def resolve_provider(node_type: str, mode: str = "", fallback: str = "opencode_go") -> str:
    """按节点类型 + 模式解析 provider。

    优先级：环境变量（NODE_PROVIDER_<节点> 可覆盖）> 路由策略 > fallback。
    未配置/空 → fallback（opencode_go，免费 provider）。
    """
    mode = mode or os.environ.get("RUN_MODE", "") or "perf"
    node = _NODE_ALIASES.get(node_type, node_type)
    policy = ROUTE_POLICY.get(mode, ROUTE_POLICY["perf"])
    # 环境变量覆盖：NODE_PROVIDER_MERGE=deepseek 等
    env_override = os.environ.get(f"NODE_PROVIDER_{node.upper()}")
    if env_override:
        return env_override
    return policy.get(node, fallback) or fallback


def route_info(mode: str = "") -> dict:
    """返回当前模式的路由策略全览（可观测/审计用）。"""
    mode = mode or os.environ.get("RUN_MODE", "") or "perf"
    policy = ROUTE_POLICY.get(mode, ROUTE_POLICY["perf"])
    return {"mode": mode, "policy": policy}


def is_marvis(node_type: str, mode: str = "") -> bool:
    """判断某节点在当前模式是否走 Marvis（agent_provider）。"""
    return resolve_provider(node_type, mode) == "agent_provider"


def merge_mode_llm_map() -> dict:
    """兼容旧接口：返回 run_reports 的 MODE_LLM 映射（train 主 provider）。"""
    return {
        "perf": "deepseek",
        "train": ROUTE_POLICY["train"]["write"],  # agent_provider
    }
