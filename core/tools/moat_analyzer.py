"""护城河分类分析工具 (戴老板四护城河 + Bruce Greenwald 竞争优势框架)

戴老板四护城河:
1. 品牌护城河 - 消费者愿意为品牌溢价买单
2. 转换成本 - 客户离开的成本太高
3. 网络效应 - 用户越多价值越大
4. 成本优势 - 规模效应或独特资源带来的低成本

格林沃德补充:
- 供应优势: 竞争者进入成本
- 需求优势: 客户忠诚度(习惯/转换成本/搜寻成本)
- 规模经济: 固定成本分摊 + 客户忠诚的组合

来源: E:\\9728\\戴老板知识库.md + E:\\9728\\企业战略博弈
"""

from dataclasses import dataclass, field
from enum import Enum


class MoatType(Enum):
    BRAND = "brand"
    SWITCHING_COST = "switching_cost"
    NETWORK_EFFECT = "network_effect"
    COST_ADVANTAGE = "cost_advantage"
    REGULATORY = "regulatory"
    TECHNOLOGY = "technology"
    SCALE_ECONOMIES = "scale_economies"


@dataclass
class MoatAssessment:
    """护城河评估"""

    type: MoatType
    strength: str  # '强'/'中'/'弱'
    durability: str  # '持久'/'可维持'/'不确定'
    source: str = ""
    quantifiable: bool = False
    evidence_points: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)


@dataclass
class CompanyMoatProfile:
    """公司护城河画像"""

    company: str = ""
    assessments: list[MoatAssessment] = field(default_factory=list)
    overall_moat: str = ""  # '宽'/'中等'/'窄'
    competitive_position: str = ""  # '领导者'/'挑战者'/'利基者'

    @property
    def strong_moats(self) -> list[MoatAssessment]:
        return [a for a in self.assessments if a.strength in ("强",)]

    @property
    def weak_moats(self) -> list[MoatAssessment]:
        return [a for a in self.assessments if a.strength in ("弱",)]

    def summary(self) -> str:
        lines = [f"## 护城河分析: {self.company}"]
        lines.append(f"整体护城河: {self.overall_moat}")
        lines.append(f"竞争位置: {self.competitive_position}")
        lines.append("")
        for a in self.assessments:
            icon = "🛡️" if a.strength == "强" else "🔶" if a.strength == "中" else "⚠️"
            lines.append(f"{icon} {a.type.value}: {a.strength}/{a.durability}")
            for e in a.evidence_points:
                lines.append(f"   · {e}")
            if a.risk_factors:
                lines.append(f"   风险: {', '.join(a.risk_factors)}")
        return "\n".join(lines)


class MoatAnalyzer:
    """护城河分析引擎"""

    MOAT_DESCRIPTIONS = {
        MoatType.BRAND: {
            "label": "品牌护城河",
            "description": "消费者愿意为品牌支付溢价",
            "indicators": ["品牌认知度", "NPS", "品牌溢价率", "复购率"],
            "strength_criteria": "强: 品牌溢价率>20%, NPS>50; 中: 10-20%, NPS30-50; 弱: <10%, NPS<30",
        },
        MoatType.SWITCHING_COST: {
            "label": "转换成本",
            "description": "客户离开的成本太高",
            "indicators": ["客户续约率", "迁移成本", "数据锁定效应", "培训依赖度"],
            "strength_criteria": "强: 续约率>90%, 迁移成本>客户年费50%",
        },
        MoatType.NETWORK_EFFECT: {
            "label": "网络效应",
            "description": "用户越多价值越大",
            "indicators": ["用户规模", "双边网络", "数据飞轮", "UGC量"],
            "strength_criteria": "强: 市场>40%份额且双边已启动",
        },
        MoatType.COST_ADVANTAGE: {
            "label": "成本优势",
            "description": "规模效应或独特资源带来的低成本",
            "indicators": ["成本差", "规模效应", "流程优势", "区位优势"],
            "strength_criteria": "强: 成本比对手低>20%",
        },
    }

    def assess(self, company: str, moat_data: dict[MoatType, dict]) -> CompanyMoatProfile:
        """评估公司护城河"""
        profile = CompanyMoatProfile(company=company)

        for moat_type, data in moat_data.items():
            assessment = MoatAssessment(
                type=moat_type,
                strength=data.get("strength", "中"),
                durability=data.get("durability", "可维持"),
                source=data.get("source", ""),
                quantifiable=data.get("quantifiable", False),
                evidence_points=data.get("evidence", []),
                risk_factors=data.get("risks", []),
            )
            profile.assessments.append(assessment)

        # 综合评分
        scores = {"强": 3, "中": 1.5, "弱": 0}
        total = sum(scores.get(a.strength, 0) for a in profile.assessments)
        if total >= 7:
            profile.overall_moat = "宽"
        elif total >= 3:
            profile.overall_moat = "中等"
        else:
            profile.overall_moat = "窄"

        return profile

    def greenwald_competitive_advantage(self, entry_barrier: str, customer_loyalty: str, scale_economy: str) -> dict:
        """格林沃德三维竞争优势判断"""
        advantages = []

        if entry_barrier == "高":
            advantages.append("供应优势: 市场进入壁垒高, 在位企业有结构性优势")
        if customer_loyalty == "高":
            advantages.append("需求优势: 客户忠诚度高, 习惯/转换成本/搜寻成本构成护城河")
        if scale_economy == "高":
            advantages.append("规模经济: 固定成本分摊大, 规模本身是竞争优势")

        result = {
            "advantages": advantages,
            "count": len(advantages),
            "has_competitive_advantage": len(advantages) >= 2,
            "judgment": (
                "具有可辩护的竞争优势"
                if len(advantages) >= 2
                else "竞争优势不明确"
                if len(advantages) >= 1
                else "无竞争优势, 依赖管理效率"
            ),
        }
        return result

    def get_dupond_analysis(self, roe: float, profit_margin: float, turnover: float, leverage: float) -> dict:
        """杜邦分析(戴老板 - ROE三层拆解)

        ROE = 利润率 x 周转率 x 杠杆率
        """
        return {
            "ROE": round(roe, 1),
            "拆解": {"利润率": round(profit_margin, 1), "周转率": round(turnover, 2), "杠杆率": round(leverage, 2)},
            "驱动类型": (
                "高利润型(品牌/技术驱动)"
                if profit_margin > 15
                else "高周转型(效率驱动)"
                if turnover > 1.5
                else "高杠杆型(金融/资本驱动)"
                if leverage > 3
                else "均衡型"
            ),
            "可复制性判断": (
                "可复制性中等-利润率依赖品牌/技术壁垒"
                if profit_margin > 15
                else "可复制性高-周转率可通过管理优化"
                if turnover > 1.5
                else "可复制性低-杠杆率受宏观和监管约束"
            ),
        }
