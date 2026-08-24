"""数据流管线 — 一致预测/实时宏观/另类数据的一体化接线。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("2hao.data_flow")


@dataclass
class DataPoint:
    name: str
    value: float
    unit: str
    timestamp: str
    source: str
    confidence: float = 0.7


class DataFlowPipeline:
    """统一数据流接口。mock数据，接线后切真实API。"""

    SOURCES = {
        "consensus": {"status": "mock", "api": "wind/consensus", "fallback": "data/consensus_prices.json"},
        "macro": {"status": "mock", "api": "wind/macro", "fallback": "data/macro_highfreq.json"},
        "capital_flow": {"status": "mock", "api": "akshare/capital_flow", "fallback": "data/capital_flow.json"},
    }

    def __init__(self, mode: str = "auto"):
        self.mode = mode

    def get_consensus(self, stock_code: str) -> DataPoint:
        fp = Path(__file__).resolve().parent.parent / self.SOURCES["consensus"]["fallback"]
        if fp.exists():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if stock_code in data:
                    return DataPoint(
                        f"{stock_code}_pe_fwd",
                        float(data[stock_code].get("pe_forward", 0)),
                        "倍",
                        "latest",
                        "consensus_prices.json",
                    )
            except Exception:
                pass
        return DataPoint("consensus", 0, "", "", "fallback(无数据)")

    def get_macro(self, indicator: str) -> DataPoint:
        for base in [Path(__file__).resolve().parent.parent.parent, Path(__file__).resolve().parent.parent]:
            fp = base / "data" / "macro_highfreq.json"
            if fp.exists():
                try:
                    data = json.loads(fp.read_text())
                    if indicator in data:
                        v = data[indicator]
                        return DataPoint(
                            indicator, float(v["value"]), v.get("unit", ""), v.get("date", ""), "macro_highfreq.json"
                        )
                except Exception:
                    pass
        return DataPoint(indicator, 0, "", "", "fallback")

    def status_report(self) -> str:
        lines = ["=== 数据流管线状态 ==="]
        for name, info in self.SOURCES.items():
            lines.append(f"  {name}: {info['status']} (api: {info['api']})")
        return "\n".join(lines)


if __name__ == "__main__":
    dfp = DataFlowPipeline()
    print(dfp.status_report())
