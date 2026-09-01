"""数据流管线 — 一致预测/实时宏观/另类数据的一体化接线。"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from core.models import DataPoint

logger = logging.getLogger("2hao.data_flow")


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
                    val = float(data[stock_code].get("pe_forward", 0))
                    excerpt = f"{stock_code}_pe_fwd: {val}"
                    return DataPoint(
                        name=f"{stock_code}_pe_fwd",
                        value=val,
                        unit="倍",
                        source="consensus_prices.json",
                        access_ts=datetime.now(timezone.utc).isoformat(),
                        excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
                        confidence=0.7,
                        scope="company",
                    )
            except Exception:
                pass
        excerpt = "consensus: no data"
        return DataPoint(
            name="consensus",
            value=0,
            unit="倍",
            source="fallback",
            access_ts=datetime.now(timezone.utc).isoformat(),
            excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
            confidence=0.1,
            scope="company",
        )

    def get_macro(self, indicator: str) -> DataPoint:
        for base in [Path(__file__).resolve().parent.parent.parent, Path(__file__).resolve().parent.parent]:
            fp = base / "data" / "macro_highfreq.json"
            if fp.exists():
                try:
                    data = json.loads(fp.read_text())
                    if indicator in data:
                        v = data[indicator]
                        val = float(v["value"])
                        excerpt = f"{indicator}: {val}"
                        return DataPoint(
                            name=indicator,
                            value=val,
                            unit=v.get("unit", ""),
                            source="macro_highfreq.json",
                            access_ts=datetime.now(timezone.utc).isoformat(),
                            excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
                            confidence=0.8,
                            scope="global",
                        )
                except Exception:
                    pass
        excerpt = f"{indicator}: fallback"
        return DataPoint(
            name=indicator,
            value=0,
            unit="",
            source="fallback",
            access_ts=datetime.now(timezone.utc).isoformat(),
            excerpt_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
            confidence=0.1,
            scope="global",
        )

    def status_report(self) -> str:
        lines = ["=== 数据流管线状态 ==="]
        for name, info in self.SOURCES.items():
            lines.append(f"  {name}: {info['status']} (api: {info['api']})")
        return "\n".join(lines)


if __name__ == "__main__":
    dfp = DataFlowPipeline()
    print(dfp.status_report())
