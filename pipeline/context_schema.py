"""context_schema.py — 管线上下文类型化契约（单一事实源）。

P3-audit 2026-08-24：此前 21 个节点共享裸 dict，键名靠字符串约定，
双键兜底（collected_data/data_context）与 typo 风险无从机械防范。
本模块把全部已知键显式化为 TypedDict：

1. PipelineContext —— 运行时仍是 dict（零行为变更），但 IDE/类型检查器
   可校验；新增键必须先在此登记
2. new_context() —— 统一构造入口（默认值集中于此）
3. unknown_keys() —— 契约漂移检测：节点写入了未登记键即报警

后续演进路径：output_contract 从字段类型自动生成 → 节点并行调度前提。
"""

from __future__ import annotations

from typing import Any, TypedDict


class PipelineContext(TypedDict, total=False):
    # ── 任务身份 ──
    trace_id: str  # R78 一次运行一个可追溯 ID
    asset: str  # 标的名
    asset_id: str  # 标的代码
    report_type: str  # listed_company/industry_deep/unlisted_company/earnings_notes/decision_memo
    style: str  # 机构风格 cicc/gs/...
    output_dir: str  # 输出目录
    enrich_file: str | None  # agent 补数 JSON 路径
    force: bool  # 强制重跑
    user_context: dict[str, Any]
    custom_requirement: str
    client_questions: list[dict] | None  # R83 必答问题清单

    # ── 迭代状态 ──
    attempt: int  # 当前写改轮次（0-based）
    degradation_level: int  # FP7b 视觉降级等级
    runtime_score: float  # 动态质量分
    skeleton_mode: bool  # 骨架模式
    dimension_parallel: bool
    draft_provider: str
    _data_cached: bool  # 重试间采集缓存标记
    _prev_report_text: str  # 组级局部重写的上一轮文本
    _intent_plan: dict | None
    _docx_path: str

    # ── 数据层 ──
    collected_data: dict[str, Any]  # DataCollectorV5 产出（含 sources）
    data_sufficiency: dict[str, Any]  # 充足度评估
    data_context: dict[str, Any]  # 写作侧数据上下文（chart_data/compute_results/...）
    chart_data: dict[str, Any]  # 图表数据键值（fig_* → payload）
    data_credibility: float
    provenance: dict | None
    scarcity_signals: list[Any]
    macro_ctx: Any  # 宏观周期定位
    biz_model: Any  # 商业模式分类
    universe_summary: dict[str, Any]  # 玩家清单/品牌映射
    chart_paths: dict[str, str]
    chart_template_flags: dict[str, bool]

    # ── 计算/规划 ──
    compute_results: dict[str, Any]
    hypothesis: str
    hypothesis_result: dict | None
    analysis_plan: Any  # R67 计划实例
    intent_plan: dict | None
    scaffold: Any
    cross_validation: Any
    state_anchor: dict[str, Any]
    plan_str: str  # 写作规划文本
    calib_str: str  # 口径标注文本

    # ── 写作与门禁 ──
    report_text: str
    final_text: str
    compiled_text: str
    gate_result: dict[str, Any]
    gate_feedback: str  # 修订轮反馈
    learning_findings: str
    compliance_result: Any
    template_result: Any
    template_blocked: bool
    template_block_reasons: list[str]
    stage_summary: dict[str, Any]


CONTEXT_KEYS = frozenset(PipelineContext.__annotations__.keys())


def new_context(**overrides) -> PipelineContext:
    """统一构造入口：默认值 + 覆盖项。未知键直接抛错（防 typo 潜伏）。"""
    ctx: PipelineContext = {
        "runtime_score": 0.5,
        "hypothesis_result": None,
        "collected_data": {},
        "chart_paths": {},
        "report_text": "",
        "final_text": "",
        "learning_findings": "",
        "gate_feedback": "",
        "provenance": None,
        "gate_result": {},
        "attempt": 0,
    }
    for k, v in overrides.items():
        if k not in CONTEXT_KEYS:
            raise KeyError(f"PipelineContext 未登记键: {k!r}——请先在 context_schema.py 登记")
        ctx[k] = v
    return ctx


def unknown_keys(ctx: dict) -> list[str]:
    """返回 ctx 中未登记的键（下划线私有键除外）。用于契约漂移监控。"""
    return sorted(k for k in ctx.keys() if k not in CONTEXT_KEYS and not k.startswith("_"))
