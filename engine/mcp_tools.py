"""
MCP 工具化暴露 + Docker 部署接口。
参考 stockvaluation_io: 让外部 agent 可调用估值引擎。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MCPTool:
    """MCP 工具定义"""

    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolResult:
    """MCP 工具调用结果"""

    tool_name: str
    success: bool = True
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPEngine:
    """MCP 工具暴露引擎"""

    def __init__(self):
        self.tools: List[MCPTool] = []
        self._register_tools()

    def _register_tools(self) -> None:
        """注册所有估值工具"""
        self.tools = [
            MCPTool(
                name="dcf_valuation",
                description="运行 DCF 估值模型",
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "base_revenue": {"type": "number"},
                        "revenue_growth_rates": {"type": "array", "items": {"type": "number"}},
                        "ebit_margins": {"type": "array", "items": {"type": "number"}},
                        "wacc": {"type": "number"},
                        "terminal_growth_rate": {"type": "number"},
                    },
                    "required": ["ticker", "base_revenue"],
                },
            ),
            MCPTool(
                name="comparable_valuation",
                description="运行可比公司估值",
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "company_eps": {"type": "number"},
                        "peer_pe_ratios": {"type": "array", "items": {"type": "number"}},
                    },
                },
            ),
            MCPTool(
                name="three_statement_model",
                description="运行三表联动模型",
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "base_revenue": {"type": "number"},
                    },
                },
            ),
            MCPTool(
                name="monte_carlo_simulation",
                description="运行 Monte Carlo 模拟",
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "n_simulations": {"type": "integer", "default": 10000},
                    },
                },
            ),
            MCPTool(
                name="quality_scoring",
                description="计算 Piotroski/Altman/Beneish 质量评分",
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "financials": {"type": "object"},
                    },
                },
            ),
            MCPTool(
                name="regime_dcf",
                description="运行 Regime-Conditional DCF",
                input_schema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "regimes": {"type": "object"},
                    },
                },
            ),
        ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """调用 MCP 工具"""
        # 简化实现
        return MCPToolResult(
            tool_name=tool_name,
            success=True,
            output={"status": "executed", "arguments": arguments},
        )

    def list_tools(self) -> List[MCPTool]:
        return self.tools


# ─── Docker Configuration ───────────────────────────────────────────────────


DOCKERFILE_CONTENT = """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "engine.mcp_server:app", "--host", "0.0.0.0", "--port", "8000"]
"""

DOCKER_COMPOSE_CONTENT = """
version: '3.8'

services:
  valuation-engine:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PYTHONPATH=/app
    volumes:
      - ./data:/app/data
      - ./output:/app/output
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
"""


def generate_dockerfiles(output_dir: str = ".") -> Dict[str, str]:
    """生成 Docker 配置文件"""
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    dockerfile_path = out / "Dockerfile"
    dockerfile_path.write_text(DOCKERFILE_CONTENT.strip())

    compose_path = out / "docker-compose.yml"
    compose_path.write_text(DOCKER_COMPOSE_CONTENT.strip())

    return {
        "Dockerfile": str(dockerfile_path),
        "docker-compose.yml": str(compose_path),
    }
