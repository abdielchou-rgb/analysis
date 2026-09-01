"""S5-4: 类型化管线上下文——替代裸 dict，提供字段级访问和类型提示。

用法：
    from core.pipeline_context import PipelineContext
    ctx = PipelineContext(asset="柯力传感", report_type="listed_company")
    ctx.chart_data = {...}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineContext:
    """类型化管线上下文——替代裸 dict，提供字段级访问和类型提示。"""

    asset: str = ""
    ticker: str = ""
    report_type: str = "listed_company"
    industry: str = ""
    biz_type: str = ""
    style: str = "cicc"
    chart_data: dict = field(default_factory=dict)
    financials: dict = field(default_factory=dict)
    tavily: dict = field(default_factory=dict)
    compute_results: dict = field(default_factory=dict)
    collected_data: dict = field(default_factory=dict)
    macro_ctx: Any = None
    reference: dict = field(default_factory=dict)
    final_text: str = ""
    gate_result: dict = field(default_factory=dict)
    trace_id: str = ""
    checkpoint_node: str = ""
    _extra: dict = field(default_factory=dict)

    def get(self, key: str, default=None):
        """兼容 dict 风格访问。"""
        return getattr(self, key, self._extra.get(key, default))

    def set(self, key: str, value):
        """兼容 dict 风格写入。"""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self._extra[key] = value

    def update(self, data: dict):
        """批量更新。"""
        for k, v in data.items():
            self.set(k, v)

    def to_dict(self) -> dict:
        """导出为 dict（兼容旧管线）。"""
        d = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        d.update(self._extra)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineContext":
        """从 dict 构建。"""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        extra = {k: v for k, v in d.items() if k not in known}
        ctx = cls(**{k: v for k, v in d.items() if k in known})
        ctx._extra = extra
        return ctx
