"""
2号分析师 Data Credibility — 数据可信度与交叉验证引擎

FP2要求: 数据零错误。多源冲突时必须标注置信度和分歧。
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.data_credibility")


@dataclass
class DataPoint:
    """单个数据点"""
    name: str
    value: float
    unit: str = ""
    source: str = ""
    timestamp: str = ""
    confidence: float = 0.5  # 0-1
    fiscal_year: Optional[int] = None


@dataclass
class SourceConflict:
    """数据源冲突"""
    data_name: str
    sources: dict  # source_name -> value
    difference_pct: float
    resolution: str = "unresolved"  # resolved / average / flag / use_highest


class DataCredibilityEngine:
    """数据可信度引擎

    功能:
    1. 多源交叉验证
    2. 数据合理性检查（PE不能为负、毛利率0-100%等）
    3. 来源信誉评分
    4. 冲突检测与自动解决
    """

    # 合理值范围
    RANGE_CHECKS = {
        "pe_ratio": (-50, 500),
        "pb_ratio": (0, 50),
        "gross_margin": (0, 1),
        "net_margin": (-1, 1),
        "revenue_growth": (-1, 5),
        "net_profit_growth": (-5, 10),
        "roe": (-1, 1),
        "debt_ratio": (0, 1),
        "current_ratio": (0, 20),
        "dividend_yield": (0, 0.2),
        "market_cap": (0, 1e13),
    }

    # 来源信誉评分
    SOURCE_REPUTATION = {
        "公司公告": 0.95,
        "交易所数据": 0.90,
        "Wind": 0.90,
        "Bloomberg": 0.90,
        "中金研究": 0.85,
        "中信研究": 0.85,
        "GS Research": 0.85,
        "MS Research": 0.85,
        "JPM Research": 0.85,
        "东方财富": 0.75,
        "akshare": 0.70,
        "新浪财经": 0.65,
        "雪球": 0.50,
        "新闻媒体": 0.45,
        "Crawl4AI": 0.40,
        "Unknown": 0.30,
    }

    def __init__(self):
        self.conflicts = []

    def validate(self, data_points: list) -> list:
        """验证数据点列表，返回带质量标记的结果"""
        validated = []
        for dp in data_points:
            # 范围检查
            range_check = self._check_range(dp.name, dp.value)
            # 来源信誉
            reputation = self.SOURCE_REPUTATION.get(dp.source, 0.30)
            # 综合置信度
            confidence = dp.confidence * 0.4 + reputation * 0.4 + (0.2 if range_check["passed"] else 0.0)

            validated.append({
                **dp.__dict__,
                "validated_confidence": round(confidence, 2),
                "range_check": range_check["passed"],
                "range_issues": range_check.get("issues", []),
                "source_reputation": reputation,
            })
        return validated

    def cross_validate(self, data_points: list) -> dict:
        """交叉验证：检测多源冲突"""
        # 按名称分组
        by_name = {}
        for dp in data_points:
            if dp.name not in by_name:
                by_name[dp.name] = []
            by_name[dp.name].append(dp)

        results = {"resolved": [], "conflicts": [], "total_points": len(data_points)}

        for name, points in by_name.items():
            if len(points) < 2:
                # 单源，直接使用
                results["resolved"].append(self._single_source(points[0]))
                continue

            # 多源交叉验证
            conflict = self._detect_conflict(points)
            if conflict["has_conflict"]:
                results["conflicts"].append(conflict)
                self.conflicts.append(conflict)
                # 推荐值
                if conflict["difference_pct"] < 10:
                    # 差异<10%，取平均
                    resolved_value = sum(p.value for p in points) / len(points)
                    results["resolved"].append({
                        "name": name,
                        "value": resolved_value,
                        "resolution": "average",
                        "confidence": 0.7,
                        "sources": [p.source for p in points],
                    })
                elif conflict["difference_pct"] < 30:
                    # 差异10-30%，取信誉最高的
                    best = max(points, key=lambda p: self.SOURCE_REPUTATION.get(p.source, 0.30))
                    results["resolved"].append({
                        "name": name,
                        "value": best.value,
                        "resolution": "use_highest_reputation",
                        "confidence": 0.5,
                        "sources": [best.source],
                        "discrepancy_note": f"数据分歧{conflict['difference_pct']:.0f}%，采用{best.source}数据",
                    })
                else:
                    # 差异>30%，标记为高冲突
                    best = max(points, key=lambda p: self.SOURCE_REPUTATION.get(p.source, 0.30))
                    results["resolved"].append({
                        "name": name,
                        "value": best.value,
                        "resolution": "flagged",
                        "confidence": 0.3,
                        "sources": [best.source],
                        "discrepancy_note": f"⚠️ 严重数据分歧({conflict['difference_pct']:.0f}%)！建议人工核实",
                    })
            else:
                results["resolved"].append(self._single_source(points[0]))

        return results

    def _check_range(self, name: str, value: float) -> dict:
        """范围检查"""
        for key, (low, high) in self.RANGE_CHECKS.items():
            if key in name.lower() or any(k in name.lower() for k in key.split("_")):
                if value < low or value > high:
                    return {"passed": False, "issues": [f"{name}={value} 超出合理范围[{low}, {high}]"]}
        return {"passed": True, "issues": []}

    def _detect_conflict(self, points: list) -> dict:
        """检测多源冲突"""
        values = [p.value for p in points]
        if not values:
            return {"has_conflict": False}

        max_v, min_v = max(values), min(values)
        if max_v == 0:
            return {"has_conflict": False, "difference_pct": 0}

        diff_pct = abs(max_v - min_v) / abs(max_v) * 100
        return {
            "has_conflict": diff_pct > 5,
            "data_name": points[0].name,
            "values": {p.source: p.value for p in points},
            "difference_pct": round(diff_pct, 1),
            "max_source": max(points, key=lambda p: p.value).source,
            "min_source": min(points, key=lambda p: p.value).source,
        }

    def _single_source(self, dp: DataPoint) -> dict:
        """单源数据处理"""
        return {
            "name": dp.name,
            "value": dp.value,
            "resolution": "single_source",
            "confidence": self.SOURCE_REPUTATION.get(dp.source, 0.30),
            "sources": [dp.source],
        }

    def generate_report_section(self, validated: dict) -> str:
        """生成数据质量章节（供报告使用）"""
        lines = ["### 数据质量与可信度说明", ""]

        if validated.get("conflicts"):
            lines.append("**数据分歧说明:**")
            for c in validated["conflicts"][:5]:
                lines.append(f"- {c['data_name']}: 多源数据存在{c['difference_pct']:.0f}%差异")
                for src, val in c["values"].items():
                    lines.append(f"  - {src}: {val}")
            lines.append("")

        lines.append("**数据来源:**")
        total = validated.get("total_points", 0)
        resolved = len(validated.get("resolved", []))
        lines.append(f"- 共{total}个数据点，{resolved}个已解析")
        lines.append("- 数据来源标注于各图表和表格底部")
        lines.append("- 多源数据已交叉验证，分歧处已标注")

        return "\n".join(lines)


def main():
    """测试"""
    engine = DataCredibilityEngine()
    
    # 示例
    points = [
        DataPoint("revenue_2025", 1500, "亿", "公司公告", confidence=0.9),
        DataPoint("revenue_2025", 1480, "亿", "wind", confidence=0.85),
        DataPoint("pe_ratio", 35, "倍", "akshare", confidence=0.6),
        DataPoint("gross_margin", 0.75, "", "新浪财经", confidence=0.5),
    ]

    # 验证
    validated = engine.validate(points)
    print("=== 验证结果 ===")
    for v in validated:
        print(f"  {v['name']}: {v['value']} (置信度: {v['validated_confidence']:.2f})")

    # 交叉验证
    cv = engine.cross_validate(points)
    print(f"\n=== 交叉验证 ===")
    print(f"  总数据点: {cv['total_points']}")
    print(f"  已解析: {len(cv['resolved'])}")
    print(f"  冲突: {len(cv['conflicts'])}")
    for c in cv['conflicts']:
        print(f"  ⚠️ {c['data_name']}: {c['difference_pct']:.0f}% 差异")

    print(f"\n{engine.generate_report_section(cv)}")


if __name__ == "__main__":
    main()
