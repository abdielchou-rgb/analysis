from dataclasses import dataclass


@dataclass
class WangSiyuResult:
    matrix: dict
    market_score: float
    competition_type: str
    recommendation: str
    composite_score: float


def analyze(data: dict) -> WangSiyuResult:
    pur = data.get("purchasing_power", 0.5)
    sup = data.get("supply_capacity", 0.5)
    spr = data.get("spread_efficiency", 0.5)
    cond = data.get("applicable_conditions", 0.5)
    ms = (pur + sup + spr + cond) / 4.0
    cr3 = data.get("cr3", 0)
    if cr3 > 0.7 or data.get("network_effect", False):
        dist = "power_law"
    elif cr3 > 0.5:
        dist = "lognormal"
    else:
        dist = "normal"
    cs = round((ms + data.get("entry_barrier", 0.5)) / 2.0, 2)
    if cs >= 0.7:
        rec = "Good market structure"
    elif cs >= 0.5:
        rec = "Average conditions"
    else:
        rec = "Poor structure, caution"
    return WangSiyuResult({"market": ms, "barrier": data.get("entry_barrier", 0.5)}, ms, dist, rec, cs)
