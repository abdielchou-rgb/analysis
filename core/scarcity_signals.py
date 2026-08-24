"""V51 L2-4 稀缺性信号词库 MVP

从 Serenity 的 9 大瓶颈原型中提取核心 4 类：
  1. 资源独占型 (Resource Exclusivity)
  2. 技术代差型 (Technology Gap)
  3. 规模壁垒型 (Scale Barrier)
  4. 时间窗口型 (Time Window)

每个瓶颈原型对应：
  - 触发条件（SAC Gate 检测到对应维度的特征）
  - 稀缺性信号词（写作中自然使用的判断句式）
  - 检查规则（Sac Gate 检测覆盖率）

FP4 设计：
  资深分析师对"稀缺性"的判断不是基于某个公式，
  而是基于对产业链物理瓶颈的实际理解。
  信号词库是帮助 agent 理解"什么算瓶颈"的工具，
  不是替代判断的公式。
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("v51.scarcity")

# ═══════════════════════════════════════════════════════════════
# 瓶颈原型定义
# ═══════════════════════════════════════════════════════════════


@dataclass
class BottleneckDef:
    id: str = ""
    name: str = ""
    description: str = ""
    trigger_conditions: list[str] = field(default_factory=list)  # SAC Gate 检测条件
    signal_keywords: list[str] = field(default_factory=list)    # 在正文中检测的信号词
    positive_patterns: list[str] = field(default_factory=list)   # 应出现的判断句式（正则）
    weight: float = 1.0  # 在 scarcity_score 中的权重


BOTTLENECKS = [
    BottleneckDef(
        id="resource_exclusivity",
        name="资源独占型",
        description="关键资源（矿产/牌照/频谱/航线）被单一或少数主体控制",
        trigger_conditions=["资源集中度>70%", "牌照壁垒", "不可复制"],
        signal_keywords=["唯一供应商", "牌照壁垒", "资源储量", "不可复制", "采矿权"],
        positive_patterns=[
            r"(唯一|独家)[^。]{5,30}(供应商|持牌|许可)",
            r"(资源|矿产|牌照|储量)[^。]{10,40}(独占|垄断|集中|控制)",
            r"(不可|无法)[^。]{5,30}(复制|替代|仿制)",
        ],
    ),
    BottleneckDef(
        id="technology_gap",
        name="技术代差型",
        description="技术领先优势形成时间窗口，追赶者需要N年才能达到同等水平",
        trigger_conditions=["技术领先", "专利壁垒", "研发投入领先"],
        signal_keywords=["技术代差", "专利壁垒", "研发投入", "良率", "性能领先"],
        positive_patterns=[
            r"(技术|工艺|制程)[代差领先][^。]{10,40}(年|节点|代)",
            r"(专利|IP|知识产权)[壁垒][^。]{10,40}",
            r"(良率|性能|效率)[^。]{10,30}(领先|差距|优势)",
        ],
    ),
    BottleneckDef(
        id="scale_barrier",
        name="规模壁垒型",
        description="产能/采购/分销的规模壁垒，单位成本随规模递减",
        trigger_conditions=["规模-利润弹性>0.3", "最小有效规模", "产能利用率"],
        signal_keywords=["最小有效规模", "产能利用率", "采购溢价", "分销密度", "单位成本"],
        positive_patterns=[
            r"(最小[有效]?规模|MES)[^。]{10,40}",
            r"(产能|开工)[利用]?率[^。]{10,30}",
            r"(单位成本|边际成本)[^。]{10,30}(递减|下降|优势)",
        ],
    ),
    BottleneckDef(
        id="time_window",
        name="时间窗口型",
        description="先发优势在特定时间窗口内不可追赶（认证周期/临床审批/产能建设）",
        trigger_conditions=["认证周期>1年", "临床审批", "先发优势"],
        signal_keywords=["认证周期", "临床Ⅲ期", "先发窗口", "后发者时间成本", "建设周期"],
        positive_patterns=[
            r"(认证|审批|临床)[^。]{5,30}(周期|时间|窗口)[^。]{10,30}",
            r"(先发|先进入)[^。]{10,40}(窗口|优势|壁垒)",
            r"(建设|开发|量产)[周期][^。]{10,30}(年|月)",
        ],
    ),
]


# ═══════════════════════════════════════════════════════════════
# 覆盖率检查
# ═══════════════════════════════════════════════════════════════


@dataclass
class BottleneckCoverage:
    bottleneck_id: str = ""
    bottleneck_name: str = ""
    activated: bool = False           # SAC Gate 是否触发
    signal_keyword_hits: int = 0      # 信号关键词命中数
    positive_pattern_hits: int = 0    # 判断句式命中数
    covered: bool = False             # 是否充分覆盖
    note: str = ""


@dataclass
class ScarcityReport:
    """稀缺性洞察覆盖报告"""
    total_activated: int = 0
    total_covered: int = 0
    coverages: list[BottleneckCoverage] = field(default_factory=list)
    scarcity_score: float = 0.0  # 0.0 ~ 1.0
    overall_judgment: str = ""


class ScarcitySignalChecker:
    """稀缺性信号词覆盖率检查器。

    用法:
        checker = ScarcitySignalChecker()
        report = checker.check(text, activated_bottlenecks=["resource_exclusivity", "technology_gap"])
        if report.scarcity_score < 0.7:
            print(f"稀缺性判断覆盖率不足: {report.scarcity_score:.1%}")
    """

    def __init__(self, bottlenecks: list[BottleneckDef] = None):
        self.bottlenecks = bottlenecks or BOTTLENECKS

    def check(self, text: str, activated_bottlenecks: list[str] = None) -> ScarcityReport:
        """检查文本对激活瓶颈的覆盖率。"""
        report = ScarcityReport()

        for bn in self.bottlenecks:
            is_activated = activated_bottlenecks and bn.id in activated_bottlenecks
            if not is_activated:
                continue

            # 统计信号关键词命中
            kw_hits = sum(1 for kw in bn.signal_keywords if kw in text)

            # 统计判断句式命中
            pat_hits = 0
            for pat in bn.positive_patterns:
                pat_hits += len(re.findall(pat, text))

            # 覆盖率判断：至少命中1个关键词或1个判断句式
            covered = kw_hits >= 1 or pat_hits >= 1

            cov = BottleneckCoverage(
                bottleneck_id=bn.id,
                bottleneck_name=bn.name,
                activated=True,
                signal_keyword_hits=kw_hits,
                positive_pattern_hits=pat_hits,
                covered=covered,
            )

            if not covered:
                cov.note = f"SAC Gate标记了'{bn.name}'瓶颈但正文中未发现对应稀缺性判断"
                logger.warning(cov.note)

            report.coverages.append(cov)

        report.total_activated = sum(1 for c in report.coverages if c.activated)
        report.total_covered = sum(1 for c in report.coverages if c.covered)

        if report.total_activated > 0:
            report.scarcity_score = report.total_covered / report.total_activated
        else:
            report.scarcity_score = 1.0  # 未激活瓶颈时默认通过

        if report.scarcity_score >= 0.75:
            report.overall_judgment = "稀缺性洞察覆盖充分"
        elif report.scarcity_score >= 0.5:
            report.overall_judgment = "部分覆盖，建议补充稀缺性判断"
        else:
            report.overall_judgment = "稀缺性洞察严重不足，请重新审视产业链瓶颈特征"

        return report

    def get_signal_words_for_bottleneck(self, bottleneck_id: str) -> list[str]:
        """获取指定瓶颈的信号词列表（用于注入写作 prompt）。"""
        for bn in self.bottlenecks:
            if bn.id == bottleneck_id:
                return bn.signal_keywords
        return []

    def get_activable_bottlenecks(self, sac_dimensions: list[dict]) -> list[str]:
        """从 SAC 维度判断可激活哪些瓶颈。"""
        activated = []
        questions = " ".join(d.get("question", "") for d in sac_dimensions)
        for bn in self.bottlenecks:
            for cond in bn.trigger_conditions:
                if cond in questions:
                    activated.append(bn.id)
                    break
        return activated
