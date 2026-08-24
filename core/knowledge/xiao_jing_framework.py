# Xiao Jing Framework - Industry Analysis (McKinsey-derived)
# Source: E:/9728/how_to_quickly_understand_an_industry.md
# Core: feasibility -> scalability -> defensibility -> profitability -> valuation -> PEST -> prosperity

from dataclasses import dataclass
from typing import Optional  # noqa: F401  (dead-import debt)


@dataclass
class XiaoJingResult:
    feasibility: dict
    scalability: dict
    defensibility: dict
    profitability: dict
    valuation_phase: str
    external: dict
    prosperity: dict
    life_cycle: str
    composite_score: float
    recommendation: str


LIFE_CYCLES = ["导入期", "成长期", "成熟期", "衰退期"]

PHASE_FOCUS = {
    "导入期": ["可行性", "外部因素"],
    "成长期": ["规模性", "防守性", "景气度"],
    "成熟期": ["盈利性", "防守性", "估值"],
    "衰退期": ["外部因素", "估值"],
}


def analyze(data: dict) -> XiaoJingResult:
    """Execute Xiao Jing's 6-dimension industry analysis"""
    lc = _determine_life_cycle(data)
    feas = _analyze_feasibility(data)
    scal = _analyze_scalability(data)
    defe = _analyze_defensibility(data)
    prof = _analyze_profitability(data)
    valu = _valuation_phase(data, lc)
    pest = _analyze_pest(data)
    pros = _analyze_prosperity(data)

    scores = [f.get("score", 0) for f in [feas, scal, defe, prof]]
    valid = [s for s in scores if s > 0]
    cs = sum(valid) / len(valid) if valid else 0.5
    rec = _recommend(cs, lc)

    return XiaoJingResult(
        feasibility=feas,
        scalability=scal,
        defensibility=defe,
        profitability=prof,
        valuation_phase=valu,
        external=pest,
        prosperity=pros,
        life_cycle=lc,
        composite_score=round(cs, 2),
        recommendation=rec,
    )


def _determine_life_cycle(data: dict) -> str:
    growth = data.get("行业增速")
    pen = data.get("渗透率")
    if pen is not None:
        if pen < 0.05:
            return "导入期"
        elif pen < 0.30:
            return "成长期"
        elif pen < 0.80:
            return "成熟期"
        else:
            return "衰退期"
    if growth is not None:
        if growth > 30:
            return "成长期"
        elif growth > 5:
            return "成熟期"
        else:
            return "衰退期"
    return "成长期"


def _analyze_feasibility(data: dict) -> dict:
    score, details = 0.5, []
    if data.get("市场需求", 0) > 0:
        score += 0.15
        details.append("存在真实市场需求")
    if data.get("技术成熟度", 0) > 0.5:
        score += 0.15
        details.append("技术路线成熟")
    if data.get("单位经济", "") == "正":
        score += 0.15
        details.append("单位经济模型正向")
    return {"score": min(score, 1.0), "details": details, "passed": score >= 0.6}


def _analyze_scalability(data: dict) -> dict:
    score, details = 0.5, []
    tam = data.get("市场空间TAM", 0)
    if tam and tam > 1000:
        score += 0.2
        details.append(f"TAM达{tam}亿,天花板足够高")
    if data.get("标准化程度", 0) > 0.6:
        score += 0.15
        details.append("产品/服务标准化程度高,容易复制")
    if data.get("网络效应", False):
        score += 0.15
        details.append("存在网络效应,规模经济明显")
    return {"score": min(score, 1.0), "details": details, "passed": score >= 0.6}


def _analyze_defensibility(data: dict) -> dict:
    score, details, moats = 0.5, [], []
    for mt in ["品牌", "转换成本", "网络效应", "规模经济", "技术领先", "许可资质"]:
        if data.get(mt, False):
            moats.append(mt)
    if len(moats) >= 3:
        score += 0.3
        details.append(f"多重护城河:{','.join(moats[:3])}")
    elif moats:
        score += 0.15
        details.append(f"单一护城河:{moats[0]}")
    else:
        details.append("未观察到明显护城河")
    return {"score": min(score, 1.0), "details": details, "passed": score >= 0.6, "moats": moats}


def _analyze_profitability(data: dict) -> dict:
    score, details = 0.5, []
    gm = data.get("毛利率", 0)
    if gm and gm > 40:
        score += 0.2
        details.append(f"毛利率{gm:.0f}%,表现优秀")
    elif gm and gm > 20:
        score += 0.1
        details.append(f"毛利率{gm:.0f}%,中等水平")
    op = data.get("营业利润率", 0)
    if op and op > 15:
        score += 0.15
        details.append(f"营业利润率{op:.0f}%,表现优秀")
    roe = data.get("roe", 0)
    if roe and roe > 15:
        score += 0.15
        details.append(f"ROE{roe:.0f}%,回报率优秀")
    return {"score": min(score, 1.0), "details": details, "passed": score >= 0.6}


_VAL_MAP = {
    "导入期": "PS/EV-User(没有利润可用PE)",
    "成长期": "PEG(关注增速与估值匹配)",
    "成熟期": "PE/PB+REE(正常利润调整)",
    "衰退期": "PB/RNAV(资产清算价值)",
}


def _valuation_phase(data: dict, phase: str) -> str:
    return _VAL_MAP.get(phase, "PE(标准估值方法)")


def _analyze_pest(data: dict) -> dict:
    results = {}
    for dim in ["政策(P)", "经济(E)", "社会(S)", "技术(T)"]:
        k = dim[0]
        v = data.get(f"pest_{k}", 0)
        results[dim] = {
            "score": v if isinstance(v, (int, float)) else 0,
            "direction": "正向" if v and v > 0 else "负向" if v and v < 0 else "中性",
        }
    return {"dimensions": results}


def _analyze_prosperity(data: dict) -> dict:
    return {
        "indicators": {
            "先行指标": data.get("先行指标", "无数据"),
            "同步指标": data.get("同步指标", "无数据"),
            "滞后指标": data.get("滞后指标", "无数据"),
        }
    }


def _recommend(score: float, phase: str) -> str:
    if score >= 0.8:
        return f"行业处于{phase},综合评分{score:.0%},全面优秀,建议重点关注"
    elif score >= 0.6:
        return f"行业处于{phase},综合评分{score:.0%},基本面良好,关注关键变量"
    elif score >= 0.4:
        return f"行业处于{phase},综合评分{score:.0%},待观望,等待更清晰信号"
    else:
        return f"行业处于{phase},综合评分{score:.0%},基本面较弱,建议谨慎"


def format_summary(r: XiaoJingResult) -> str:
    return f"""=== 肖璟六维框架 ===
生命周期: {r.life_cycle}
综合评分: {r.composite_score:.0%}
建议: {r.recommendation}
可行性: {"通过" if r.feasibility.get("passed") else "未达标"} ({r.feasibility.get("score", 0):.0%})
规模性: {"通过" if r.scalability.get("passed") else "未达标"} ({r.scalability.get("score", 0):.0%})
防守性: {"通过" if r.defensibility.get("passed") else "未达标"} ({r.defensibility.get("score", 0):.0%})
盈利性: {"通过" if r.profitability.get("passed") else "未达标"} ({r.profitability.get("score", 0):.0%})
估值阶段: {r.valuation_phase}"""
