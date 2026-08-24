"""三角验证模块 — R79 P2-1 无一手数据的深度打法。

顶级分析师没有一手数据时，用三种独立方法测算同一指标，交叉验证。
三个数字落在同一区间（±20%）→ 敢写；矛盾 → 找错在哪（过程即深度）。

本模块：
  1. triangulate() 对同一指标用多方法测算，输出交叉区间
  2. 供 section_writer 注入"数据方法"小节 + enrich 数据组织

用法：
    from core.triangulation import TriangulationResult, triangulate
    r = triangulate([
        {"method": "自上而下", "value": 50, "basis": "工业传感器600亿×物位占比8%"},
        {"method": "自下而上", "value": 52, "basis": "100万座加油站×单站5000元"},
        {"method": "对标外推", "value": 47, "basis": "中国172亿÷占全球35%"},
    ])
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TriangulationResult:
    """三角验证结果。"""

    values: list
    methods: list
    low: float = 0.0
    high: float = 0.0
    midpoint: float = 0.0
    spread_pct: float = 0.0
    consistent: bool = False
    note: str = ""

    def to_text(self) -> str:
        """生成可注入报告的文本。"""
        lines = [
            f"### 市场规模三角验证（{self.midpoint:.1f}，区间 {self.low:.1f}-{self.high:.1f}）",
            f"交叉区间偏差 {self.spread_pct:.0%}，{'一致' if self.consistent else '不一致（需核查口径）'}",
        ]
        for m, v in zip(self.methods, self.values):
            lines.append(f"- {m['method']}: {v}（依据: {m['basis']}）")
        if self.note:
            lines.append(f"注: {self.note}")
        return "\n".join(lines)


def triangulate(estimates: list[dict]) -> TriangulationResult:
    """多方法交叉验证。

    Args:
        estimates: [{"method": str, "value": float, "basis": str}]
    """
    values = [float(e["value"]) for e in estimates]
    methods = [{"method": e["method"], "basis": e.get("basis", "")} for e in estimates]
    if not values:
        return TriangulationResult(values=[], methods=[], note="无估算数据")

    low = min(values)
    high = max(values)
    midpoint = sum(values) / len(values)
    # 偏差 = (max-min)/midpoint
    spread = (high - low) / midpoint if midpoint else 0
    consistent = spread <= 0.20  # ±20% 内视为一致

    note = ""
    if not consistent:
        # 找离群点
        for m, v in zip(methods, values):
            if abs(v - midpoint) / midpoint > 0.2:
                note += f"{m['method']}的{v}偏离中位{midpoint:.1f}，需核查口径；"
        note += "建议显式标注口径差异"

    return TriangulationResult(
        values=values,
        methods=methods,
        low=low,
        high=high,
        midpoint=midpoint,
        spread_pct=spread,
        consistent=consistent,
        note=note,
    )


if __name__ == "__main__":
    # 自测：全球油位传感器市场
    r = triangulate(
        [
            {"method": "自上而下", "value": 50, "basis": "工业传感器600亿美元×物位占比8%"},
            {"method": "自下而上", "value": 52, "basis": "100万座加油站×单站液位仪5000元"},
            {"method": "对标外推", "value": 47, "basis": "中国172亿元÷中国占全球35%"},
        ]
    )
    print(r.to_text())
    print(f"consistent={r.consistent}, spread={r.spread_pct:.0%}")
