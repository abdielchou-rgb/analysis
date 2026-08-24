"""信号链自动计算引擎 — 先行/同步/滞后指标"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class SignalResult:
    leading: list[dict]
    coincident: list[dict]
    lagging: list[dict]
    direction: str


class SignalChainEngine:
    """自动信号链计算。预置通用信号库。"""
    
    SIGNALS = {
        "leading": [
            {"name": "PMI新订单", "source": "国家统计局", "description": "制造业新订单指数，领先1-2个季度"},
            {"name": "新增社融", "source": "人民银行", "description": "社会融资规模增量，领先2-3个季度"},
            {"name": "信贷脉冲", "source": "人民银行", "description": "新增信贷/GDP，领先1-2个季度"},
        ],
        "coincident": [
            {"name": "工业增加值", "source": "国家统计局", "description": "规模以上工业增加值当月同比"},
            {"name": "用电量", "source": "国家能源局", "description": "全社会用电量当月同比"},
        ],
        "lagging": [
            {"name": "产成品库存", "source": "国家统计局", "description": "工业企业产成品库存同比"},
            {"name": "CPI", "source": "国家统计局", "description": "居民消费价格指数"},
        ],
    }

    def __init__(self, industry: str = ""):
        self.industry = industry

    def calculate(self) -> SignalResult:
        return SignalResult(
            leading=self.SIGNALS["leading"],
            coincident=self.SIGNALS["coincident"],
            lagging=self.SIGNALS["lagging"],
            direction="判断中（需数据接入）",
        )

    def to_report(self) -> str:
        r = self.calculate()
        lines = ["=== 信号链 ==="]
        for label, signals in [("先行", r.leading), ("同步", r.coincident), ("滞后", r.lagging)]:
            lines.append(f"\n【{label}】")
            for s in signals:
                lines.append(f"  - {s['name']}: {s['description']}（来源: {s['source']}）")
        lines.append(f"\n方向: {r.direction}")
        return "\n".join(lines)
