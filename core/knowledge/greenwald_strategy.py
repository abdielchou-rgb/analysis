"""Bruce Greenwald competitive strategy framework"""
from dataclasses import dataclass
from typing import List

@dataclass
class BarrierAssessment:
    supply_advantage: float
    demand_advantage: float
    scale_economies: float
    overall_barrier: float
    barrier_level: str

@dataclass
class GreenwaldResult:
    barriers: BarrierAssessment
    game_type: str
    recommendation: str
    confidence: float

def analyze_barriers(data: dict) -> BarrierAssessment:
    supply = data.get('supply_advantage', 0.5)
    demand = data.get('demand_advantage', 0.5)
    scale = data.get('scale_economies', 0.5)
    overall = (supply + demand + scale) / 3.0
    if overall >= 0.8: bl = '极高'
    elif overall >= 0.6: bl = '高'
    elif overall >= 0.4: bl = '中'
    elif overall >= 0.2: bl = '低'
    else: bl = '无'
    return BarrierAssessment(supply, demand, scale, round(overall, 2), bl)

def detect_game_type(data: dict) -> str:
    competitors = data.get('competitors', 0)
    price_elasticity = data.get('price_elasticity', 0.5)
    switching_cost = data.get('switching_cost', 0.5)
    if competitors <= 3 and price_elasticity < 0.3 and switching_cost > 0.5:
        return 'cooperative_game'
    elif competitors >= 5 and price_elasticity > 0.5:
        return 'prisoner_dilemma'
    elif data.get('capacity_utilization', 0.7) < 0.6:
        return 'quantity_competition'
    elif data.get('entry_barrier', 0) > 0.6:
        return 'entry_deterrence'
    else:
        return 'competitive_interaction'

def analyze(data: dict) -> GreenwaldResult:
    barriers = analyze_barriers(data)
    game_type = detect_game_type(data)
    bs = barriers.overall_barrier
    if bs > 0.6 and 'prisoner' not in game_type:
        rec = 'Healthy industry structure'
    elif bs > 0.4:
        rec = 'Moderate barriers, need differentiation'
    else:
        rec = 'Low barriers, focus on efficiency leaders'
    return GreenwaldResult(barriers, game_type, rec, round(bs, 2))
