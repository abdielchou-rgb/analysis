
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class LogicLayer:
    name: str
    score: float
    gaps: List[str]

@dataclass
class LiuRunResult:
    layers: Dict[str, LogicLayer]
    composite_score: float
    recommendation: str

def analyze_logic(data: dict) -> LiuRunResult:
    text = data.get('text', '') or data.get('report_text', '') or ''
    layers = {}
    checks = [
        ('right_wrong', ['three_views', 'human_nature', 'moral', 'law', 'game', 'choice'], 0.5),
        ('thinking', ['fact', 'opinion', 'position', 'belief', 'essence', 'system'], 0.5),
        ('evolution', ['ability', 'efficiency', 'leverage', 'time', 'power_law', 'compound'], 0.5),
        ('understanding', ['what', 'why', 'how', 'humor', 'boundary'], 0.5),
        ('collaboration', ['natural_law', 'tribe_law', 'universal', 'strategy', 'profit', 'trust'], 0.5),
    ]
    scores = []
    for name, kws, default in checks:
        found = sum(1 for k in kws if k in text.lower()) / len(kws)
        scores.append(found)
        gaps = [k for k in kws if k not in text.lower()]
        layers[name] = LogicLayer(name=name, score=round(found, 2), gaps=gaps[:3])
    cs = round(sum(scores) / len(scores), 2)
    if cs >= 0.7: rec = 'Complete logic structure'
    elif cs >= 0.5: rec = 'Basic logic, needs depth'
    else: rec = 'Incomplete logic structure'
    return LiuRunResult(layers, cs, rec)
