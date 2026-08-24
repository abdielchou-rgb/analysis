"""ChartService — 图表生成服务"""

import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("2hao.chart_service")


class ChartService:
    """图表生成服务，包装 ChartGen + 6种图表类型"""

    def __init__(self, output_dir: str = "outputs/charts"):
        self.output_dir = str(_ROOT / output_dir)
        self._available = False
        self._init_gen()

    def _init_gen(self):
        try:
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def generate_all(self, data: dict, asset: str = "") -> dict:
        if not self._available:
            return {}
        from pipeline.chart_gen import generate_all_charts

        return generate_all_charts(data, asset)

    def generate_sotp_waterfall(self, segments: list, asset: str) -> dict:
        if not self._available or not segments:
            return {}
        from pipeline.chart_gen import ChartGen

        cg = ChartGen(self.output_dir)
        cats = [s.get("name", "") for s in segments] + ["合计"]
        vals = [s.get("segment_value", 0) for s in segments] + [0]
        if len(cats) < 3:
            return {}
        p = cg.waterfall(cats, vals, title=f"{asset} SOTP分部估值", asset=asset)
        return {"sotp_waterfall": p} if p else {}

    def generate_revenue_roe_combo(self, revenue: dict, roe: dict, asset: str) -> dict:
        if not self._available:
            return {}
        from pipeline.chart_gen import ChartGen

        cg = ChartGen(self.output_dir)
        years = sorted(set(list(revenue.keys()) + list(roe.keys())))
        rv, rv2 = [], []
        for y in years:
            rv.append(float(revenue.get(y, 0)))
            rv2.append(float(roe.get(y, 0)))
        if len(rv) < 2:
            return {}
        p = cg.combo(
            {"labels": [str(y) for y in years], "values": rv, "label": "收入(亿元)"},
            {"labels": [str(y) for y in years], "values": rv2, "label": "ROE(%)"},
            title=f"{asset} 收入与ROE组合分析",
            asset=asset,
        )
        return {"revenue_roe_combo": p} if p else {}
