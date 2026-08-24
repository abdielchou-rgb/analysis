"""2hao-analyst Pipeline Contracts — 规格驱动的管线合约定义

每个 pipeline node 的输入/输出类型和验证规则。
这是 SDD（Specification-Driven Development）的核心：contract 是代码和文档的共同父级。
"""

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class Port:
    """管线节点的输入/输出端口定义"""
    name: str
    type_hint: str  # e.g., "dict", "str", "list[Path]"
    description: str
    required: bool = True


@dataclass
class PipelineNodeContract:
    """管线节点的完整合约定义"""
    node_id: str
    description: str
    inputs: list[Port] = field(default_factory=list)
    outputs: list[Port] = field(default_factory=list)
    min_score: float = 0.0  # IronGate minimum score
    timeout_s: int = 120

    def validate_output(self, output: dict) -> list[str]:
        issues = []
        for port in self.outputs:
            if port.required and port.name not in output:
                issues.append(f"Missing required output: {port.name}")
            elif port.name in output and output[port.name] is None:
                issues.append(f"Output '{port.name}' is None")
        return issues


# ── 完整管线合约定义 ──

SCHEDULER_CONTRACT = {
    "input": [
        Port("asset", "str", "股票代码或公司名"),
        Port("report_type", "str", "报告类型：industry_deep / listed_company / unlisted_company / earnings_notes"),
        Port("style", "str", "机构风格：cicc / gs / ms / mck / bcg / jpm"),
    ],
    "output": [
        Port("status", "str", "管线状态：ok / error"),
        Port("md", "str", "报告 Markdown 路径"),
        Port("docx", "str", "报告 DOCX 路径（可选）"),
        Port("gate_passed", "bool", "Iron Gate 是否通过"),
    ],
    "env_required": ["DEEPSEEK_API_KEY"],
}

E2E_ORCHESTRATOR_CONTRACT = {
    "steps": [
        ("preflight", "运行环境检查"),
        ("data_collect", "采集数据（akshare / Tavily / yfinance）"),
        ("chart_gen", "生成图表（ChartEngine / placeholder fallback）"),
        ("compute", "执行计算管线（DCF / 可比 / 场景分析）"),
        ("section_writer", "SAC 驱动三段写作"),
        ("iron_gate", "24 项质量检查"),
        ("export", "导出 DOCX + 门禁检查"),
    ],
    "min_report_length": 3000,
    "min_charts": 5,
    "min_tables": 3,
}

IRON_GATE_CONTRACT = {
    "checks": [
        "content_volume", "content_density", "aigc_fingerprint", "human_sense",
        "sac_coverage", "chart_density", "data_traceability", "format_consistency",
        "forbidden_patterns", "persuasion_architecture", "table_density",
        "moat_analysis", "decision_gate", "dcf_sensitivity", "so_what_chain",
        "bold_call", "chart_analysis_quality", "personal_narrative",
        "section_continuity", "table_quality_md", "placeholder_charts",
        "markdown_artifacts", "multi_model", "data_fidelity",
    ],
    "min_score": 0.55,
    "hard_fail": [],
}
