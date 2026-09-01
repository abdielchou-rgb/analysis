"""报告定制化配置模块。

Phase 2.1: ReportCustomization 数据类
支持维度权重、篇幅控制、风格定制等多维度定制化。
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReportCustomization:
    """报告定制化配置"""

    # 1. 维度权重定制
    dimension_weights: dict[str, float] = None  # {"headline": 1.5, "key_surprise": 2.0}

    # 2. 篇幅控制
    length: str = "standard"  # short / standard / detailed
    max_words: int = None  # 覆盖 length 的精确控制

    # 3. 写作重点
    focus_dimensions: list[str] = None  # ["valuation", "risk"] 重点维度
    skip_dimensions: list[str] = None   # ["governance"] 可跳过维度

    # 4. 风格定制
    style_preset: str = "cicc"  # cicc/gs/ms/mck/bcg/jpm
    style_blend: dict[str, float] = None  # {"cicc": 0.7, "gs": 0.3} 混合风格

    # 5. 数据源偏好
    data_sources: list[str] = None  # ["akshare", "yfinance", "tavily"]

    # 6. 输出格式
    output_formats: list[str] = None  # ["md", "docx", "pdf"]

    # 7. 语气/语言
    tone: str = "formal"  # formal / conversational / technical
    language: str = "zh-CN"  # zh-CN / en-US

    # 8. 附加内容
    include_executive_summary: bool = True
    include_appendix: bool = True
    include_charts: bool = True

    def __post_init__(self):
        """初始化后处理"""
        if self.dimension_weights is None:
            self.dimension_weights = {}
        if self.focus_dimensions is None:
            self.focus_dimensions = []
        if self.skip_dimensions is None:
            self.skip_dimensions = []
        if self.style_blend is None:
            self.style_blend = {}
        if self.data_sources is None:
            self.data_sources = []
        if self.output_formats is None:
            self.output_formats = ["md"]

    def get_effective_weights(self) -> dict[str, float]:
        """获取有效维度权重（合并 dimension_weights 和 focus_dimensions）"""
        weights = dict(self.dimension_weights)
        # focus_dimensions 权重 x2
        for dim in self.focus_dimensions:
            if dim in weights:
                weights[dim] *= 2.0
            else:
                weights[dim] = 2.0
        return weights

    def get_words_per_dim(self) -> int:
        """根据篇幅配置获取每维度目标字数"""
        length_map = {
            "short": 300,
            "standard": 500,
            "detailed": 800,
        }
        return length_map.get(self.length, 500)

    def get_total_word_range(self) -> tuple[int, int]:
        """获取总字数范围"""
        range_map = {
            "short": (1500, 2500),
            "standard": (3000, 5000),
            "detailed": (6000, 10000),
        }
        return range_map.get(self.length, (3000, 5000))

    def get_evidence_min(self) -> int:
        """获取最少证据数"""
        evidence_map = {
            "short": 1,
            "standard": 2,
            "detailed": 3,
        }
        return evidence_map.get(self.length, 2)

    def is_counter_evidence_required(self) -> bool:
        """是否需要反方论证"""
        return self.length != "short"

    def should_skip_dimension(self, dim_id: str) -> bool:
        """检查维度是否应跳过"""
        return dim_id in self.skip_dimensions

    def get_dimension_weight(self, dim_id: str) -> float:
        """获取指定维度的权重"""
        weights = self.get_effective_weights()
        return weights.get(dim_id, 1.0)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "dimension_weights": self.dimension_weights,
            "length": self.length,
            "max_words": self.max_words,
            "focus_dimensions": self.focus_dimensions,
            "skip_dimensions": self.skip_dimensions,
            "style_preset": self.style_preset,
            "style_blend": self.style_blend,
            "data_sources": self.data_sources,
            "output_formats": self.output_formats,
            "tone": self.tone,
            "language": self.language,
            "include_executive_summary": self.include_executive_summary,
            "include_appendix": self.include_appendix,
            "include_charts": self.include_charts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReportCustomization":
        """从字典创建配置"""
        if not data:
            return cls()
        return cls(
            dimension_weights=data.get("dimension_weights"),
            length=data.get("length", "standard"),
            max_words=data.get("max_words"),
            focus_dimensions=data.get("focus_dimensions"),
            skip_dimensions=data.get("skip_dimensions"),
            style_preset=data.get("style_preset", "cicc"),
            style_blend=data.get("style_blend"),
            data_sources=data.get("data_sources"),
            output_formats=data.get("output_formats"),
            tone=data.get("tone", "formal"),
            language=data.get("language", "zh-CN"),
            include_executive_summary=data.get("include_executive_summary", True),
            include_appendix=data.get("include_appendix", True),
            include_charts=data.get("include_charts", True),
        )

    @classmethod
    def from_request(cls, asset: str, report_type: str = "industry_deep", **kwargs) -> "ReportCustomization":
        """从请求参数创建配置"""
        return cls(**kwargs)


@dataclass
class ReportRequest:
    """用户报告请求"""
    asset: str
    report_type: str = "industry_deep"
    style: str = "cicc"

    # 定制化选项
    customization: Optional[ReportCustomization] = None

    # 快捷定制
    length: str = "standard"
    focus: list[str] = None
    skip: list[str] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.focus is None:
            self.focus = []
        if self.skip is None:
            self.skip = []

    def to_customization(self) -> ReportCustomization:
        """转换为定制化配置"""
        if self.customization:
            return self.customization
        return ReportCustomization(
            dimension_weights=self._parse_weights(),
            length=self.length,
            focus_dimensions=self.focus,
            skip_dimensions=self.skip,
            style_preset=self.style,
        )

    def _parse_weights(self) -> dict:
        """解析维度权重"""
        if not self.focus:
            return {}
        return {dim: 2.0 for dim in self.focus}  # 重点维度权重 x2
