"""Meta-Reasoning Layer — 元推理层

Phase 0: Context Router  — 上下文路由
Phase 1: Normalizer      — 信号归一化
Phase 2: Consistency     — 一致性检查 + 矛盾检测
Phase 3: Synthesis       — 合议 + 输出生成
Phase 4: Output          — 输出格式化

输入: compute_engine result dict (计算结果)
输出: SynthesisResult (合议 + 推荐 + 可追溯)
"""

from dataclasses import dataclass, field


@dataclass
class NormalizedSignal:
    """归一化信号 — 标准化信号结构"""

    module: str  # 合议方向
    direction: str  # bullish / bearish / neutral / mixed
    confidence: float  # 0.0 - 1.0
    insight: str  # 合议方向
    sub_signals: list[str] = field(default_factory=list)


@dataclass
class Contradiction:
    """矛盾对"""

    modules: tuple[str, str]  # 合议方向
    aspect: str  # 合议方向
    left_value: str  # 观点A的值
    right_value: str  # 观点B的值
    severity: str  # high / medium / low
    resolution: str = ""  # 信号来源列表


@dataclass
class SynthesisResult:
    """合议结果"""

    consensus_direction: str  # 合议方向
    consensus_confidence: float  # 合议方向?
    signals: list[NormalizedSignal]  # 信号来源列表
    contradictions: list[Contradiction]  # 合议方向??
    aligned_count: int  # 合议方向?
    divergent_count: int  # 合议方向?
    recommendation: str  # 合议方向
    trace: dict[str, str]  # 信号来源列表?


# ============================================================
# Phase 0: Context Router
# ============================================================

REPORT_TYPE_MODULES = {
    "industry_deep": {
        "priority": [
            "xiao_jing",  # 第一组框架 — 综合判断
            "greenwald",  # 合议方向??
            "wang_siyu",  # 合议方向??
            "thinking_models",  # 合议方向?
            "page_models",  # 合议方向
            "liu_run",  # 合议方向
        ],
        "weights": {
            "xiao_jing": 0.25,
            "greenwald": 0.25,
            "wang_siyu": 0.20,
            "thinking_models": 0.15,
            "page_models": 0.10,
            "liu_run": 0.05,
        },
    },
    "listed_company": {
        "priority": [
            "thinking_models",  # 第二组框架 — 增长+长期
            "greenwald",  # 合议方向
            "wang_siyu",  # 合议方向
            "page_models",  # 合议方向
            "kelly",  # 合议方向
            "liu_run",  # 合议方向
        ],
        "weights": {
            "thinking_models": 0.25,
            "greenwald": 0.20,
            "wang_siyu": 0.15,
            "page_models": 0.10,
            "kelly": 0.20,
            "liu_run": 0.10,
        },
    },
    "unlisted_company": {
        "priority": [
            "greenwald",  # 第三组框架 — 壁垒评估
            "wang_siyu",  # 合议方向
            "thinking_models",  # 合议方向?
            "page_models",  # 合议方向
            "liu_run",  # 合议方向
        ],
        "weights": {
            "greenwald": 0.30,
            "wang_siyu": 0.25,
            "thinking_models": 0.20,
            "page_models": 0.15,
            "liu_run": 0.10,
        },
    },
}

DEFAULT_MODULES = {
    "priority": ["xiao_jing", "greenwald", "thinking_models", "page_models", "wang_siyu", "liu_run"],
    "weights": {
        m: 1.0 / 6 for m in ["xiao_jing", "greenwald", "thinking_models", "page_models", "wang_siyu", "liu_run"]
    },
}


def get_route(report_type: str) -> dict:
    """Phase 0: Context Router — 上下文路由+框架识别"""
    return REPORT_TYPE_MODULES.get(report_type, DEFAULT_MODULES)


# ============================================================
# Phase 1: Signal Normalizer
# ============================================================


def _normalize_xiao_jing(raw: dict) -> NormalizedSignal | None:
    """路由: 框架ID → direction映射"""
    if not raw or raw.get("status") != "ok":
        return None
    result = raw.get("result", raw)
    lc = result.get("life_cycle", "")
    score = result.get("composite_score", 0.5)

    if lc in ("xiao_jing", "greenwald"):
        direction = "neutral"
        insight = f"框架判断一致(置信{score:.0%}) — 方向明确"
    elif lc in ("wang_siyu",):
        direction = "bullish"
        insight = f"框架判断谨慎(置信{score:.0%}) — 方向模糊"
    elif lc in ("thinking_models",):
        direction = "neutral"
        insight = f"框架判断分歧(置信{score:.0%}) — 多方向并存"
    else:
        direction = "bearish"
        insight = f"框架判断一致(置信{score:.0%}) — 方向明确"

    return NormalizedSignal(
        "xiao_jing",
        direction,
        float(score),
        insight,
        [
            f"LifeCycle:{lc}",
            f"Feasibility:{result.get('feasibility', {})}",
            f"Scalability:{result.get('scalability', {})}",
        ],
    )


def _normalize_greenwald(raw: dict) -> NormalizedSignal | None:
    """格林沃尔德: 壁垒评分 → direction"""
    if not raw or raw.get("status") != "ok":
        return None
    bl = raw.get("barrier_level", "?")
    bs = raw.get("barrier_score", 0.5)
    gt = raw.get("game_type", "")

    if bl in ("??", "?") and "prisoner" not in gt:
        direction = "bullish"
        insight = f"壁垒评分({bl})高于阈值{gt} — 竞争优势确认"
    elif bl in ("?",):
        direction = "neutral"
        insight = f"壁垒({bl})低于阈值{gt} — 竞争优势待验证"
    else:
        direction = "bearish"
        insight = f"壁垒评分({bl}) — 数据不足无法判断"

    return NormalizedSignal("greenwald", direction, float(bs), insight, [f"BarrierLevel:{bl}", f"GameType:{gt}"])


def _normalize_wang_siyu(raw: dict) -> NormalizedSignal | None:
    """思考模型: 多模型投票 → direction"""
    if not raw or raw.get("status") != "ok":
        return None
    ms = raw.get("market_score", 0.5)
    ct = raw.get("competition_type", "normal")
    cs = raw.get("composite_score", 0.5)

    if ct == "power_law" and cs >= 0.6:
        direction = "bullish"
        insight = f"财务排雷(置信{cs:.0%}) — 存在需关注项目"
    elif cs >= 0.5:
        direction = "neutral"
        insight = f"财务排雷(置信{cs:.0%}) — 关注{ct}"
    else:
        direction = "bearish"
        insight = f"财务排雷(置信{cs:.0%}) — 通过"

    return NormalizedSignal("wang_siyu", direction, float(cs), insight, [f"MarketScore:{ms}", f"Competition:{ct}"])


def _normalize_thinking_models(raw: dict) -> NormalizedSignal | None:
    """Page: 定价权评分 → direction"""
    if not raw or raw.get("status") != "ok":
        return None
    consensus = raw.get("consensus", "divergent")
    bullish = raw.get("bullish_count", 0)
    bearish = raw.get("bearish_count", 0)
    avg_c = raw.get("avg_confidence", 0.5)

    if consensus == "aligned" and bullish > bearish:
        direction = "bullish"
    elif consensus == "aligned" and bearish > bullish:
        direction = "bearish"
    else:
        direction = "neutral"

    insight = (
        f"综合{'看多' if direction == 'bullish' else '看空' if direction == 'bearish' else '中性'}(置信{avg_c:.0%})"
    )

    return NormalizedSignal(
        "thinking_models",
        direction,
        float(avg_c),
        insight,
        [f"Bullish:{bullish}", f"Bearish:{bearish}", f"Consensus:{consensus}"],
    )


def _normalize_page_models(raw: dict) -> NormalizedSignal | None:
    """刘润: 增长评分 → direction"""
    if not raw or raw.get("status") != "ok":
        return None
    ds = raw.get("diversity_score", 0.5)
    consensus = raw.get("consensus", "divergent")

    direction = "bullish" if consensus == "aligned" else "neutral"
    return NormalizedSignal(
        "page_models",
        direction,
        float(ds),
        f"Page评分{'一致' if consensus == 'aligned' else '分歧'}(置信{ds:.0%})",
        [f"Diversity:{ds}", f"Consensus:{consensus}"],
    )


def _normalize_serenity(raw: dict) -> NormalizedSignal | None:
    """Serenity: 六步验证 → direction"""
    if not raw or raw.get("status") != "ok":
        return None
    passed = raw.get("all_passed", False)
    failed = raw.get("failed_steps", [])

    completeness = 1.0 - (len(failed) / 9.0) if failed else 1.0
    direction = "neutral"
    if passed:
        insight = "六步验证全部通过"
    else:
        insight = f"六步验证未通过{len(failed)}项: {', '.join(failed[:3])}"

    return NormalizedSignal(
        "serenity", direction, float(completeness), insight, [f"Passed:{passed}", f"Failed:{len(failed)}/9"]
    )


def _normalize_logic_audit(raw: dict) -> NormalizedSignal | None:
    """合议: 多框架 → confidence加权"""
    if not raw or raw.get("status") != "ok":
        return None
    mece = raw.get("mece_score", 0)
    pyramid = raw.get("pyramid_score", 0)
    avg_score = (mece + pyramid) / 2.0

    if avg_score >= 0.6:
        direction = "bullish"
    elif avg_score >= 0.3:
        direction = "neutral"
    else:
        direction = "bearish"

    return NormalizedSignal(
        "logic_audit",
        direction,
        float(avg_score),
        f"MECE:{mece:.0%} 金字塔:{pyramid:.0%}",
        raw.get("recommendations", [])[:3],
    )


def _normalize_liu_run(raw: dict) -> NormalizedSignal | None:
    """路由: 框架ID → direction映射"""
    if not raw or raw.get("status") != "ok":
        return None
    cs = raw.get("composite_score", 0.5)

    if cs >= 0.7:
        direction = "bullish"
    elif cs >= 0.5:
        direction = "neutral"
    else:
        direction = "bearish"

    return NormalizedSignal(
        "liu_run",
        direction,
        float(cs),
        f"多模型合议{cs:.0%}:{'一致' if cs >= 0.7 else '中性' if cs >= 0.5 else '分歧'}",
        [],
    )


def _normalize_kelly(raw: dict) -> NormalizedSignal | None:
    """??: ?? ? direction"""
    if not raw or raw.get("status") != "ok":
        return None
    opt = raw.get("optimal_fraction", 0)
    half = raw.get("half_kelly", 0)

    if opt >= 0.5:
        direction = "bullish"
        insight = f"凯利公式(最优{opt:.0%}) — 建议建仓"
    elif opt >= 0.25:
        direction = "bullish"
        insight = f"凯利公式(半仓{half:.0%}) — 建议观望"
    elif opt > 0:
        direction = "neutral"
        insight = f"凯利公式(最优{opt:.0%}) — 建议持有"
    else:
        direction = "bearish"
        insight = "凯利公式 — 数据不足无法计算"

    return NormalizedSignal(
        "kelly", direction, float(min(opt * 2, 1.0)), insight, [f"Kelly:{opt}", f"HalfKelly:{half}"]
    )


# Module normalizer registry
NORMALIZER_REGISTRY = {
    "xiao_jing": _normalize_xiao_jing,
    "greenwald": _normalize_greenwald,
    "wang_siyu": _normalize_wang_siyu,
    "thinking_models": _normalize_thinking_models,
    "page_models": _normalize_page_models,
    "serenity": _normalize_serenity,
    "logic_audit": _normalize_logic_audit,
    "liu_run": _normalize_liu_run,
    "kelly": _normalize_kelly,
}


def normalize_all(compute_results: dict, report_type: str = "industry_deep") -> tuple[list[NormalizedSignal], dict]:
    """Phase 1: 信号归一化+加权"""
    route = get_route(report_type)
    signals = []

    for module_name in route["priority"]:
        raw = compute_results.get(module_name, {})
        normalizer = NORMALIZER_REGISTRY.get(module_name)
        if normalizer:
            signal = normalizer(raw)
            if signal:
                signals.append(signal)

    return signals, route


# ============================================================
# Phase 2: Consistency Matrix & Contradiction Detection
# ============================================================

CONTRADICTION_PAIRS = [
    (
        "xiao_jing",
        "greenwald",
        "合议",
        lambda x, g: (x.direction == "bullish" and g.direction == "bearish", "合议(看多)方向一致(看多)无矛盾"),
    ),
    (
        "thinking_models",
        "kelly",
        "看空",
        lambda t, k: (t.confidence > 0.6 and k.confidence < 0.2, "用户增长逻辑与仓位管理计算矛盾"),
    ),
    (
        "wang_siyu",
        "greenwald",
        "合议",
        lambda w, g: (
            w.direction == "bearish" and g.direction == "bullish",
            "财务排雷(通过)竞争优势(确认)增长逻辑待验证",
        ),
    ),
]


def detect_contradictions(signals: list[NormalizedSignal]) -> list[Contradiction]:
    """Phase 2: 一致性检查 + 矛盾检测"""
    sig_map = {s.module: s for s in signals}
    contradictions = []

    for m1, m2, aspect, check in CONTRADICTION_PAIRS:
        s1 = sig_map.get(m1)
        s2 = sig_map.get(m2)
        if not s1 or not s2:
            continue
        triggered, description = check(s1, s2)
        if triggered:
            contradictions.append(
                Contradiction(
                    modules=(m1, m2),
                    aspect=aspect,
                    left_value=s1.direction,
                    right_value=s2.direction,
                    severity="high",
                    resolution=description,
                )
            )

    # 信号汇总开始: 按框架分组统计
    directions = [s.direction for s in signals]
    if directions:
        aligned = max(directions.count("bullish"), directions.count("bearish"), directions.count("neutral"))
        total = len(directions)
        if aligned / total < 0.4 and len(contradictions) == 0:
            contradictions.append(
                Contradiction(
                    modules=("all", "all"),
                    aspect="合议一致性",
                    left_value="",
                    right_value="",
                    severity="medium",
                    resolution=f"合议结果({aligned}/{total})方向一致",
                )
            )

    return contradictions


# ============================================================
# Phase 3: Synthesis — 合议生成
# ============================================================


def synthesize(signals: list[NormalizedSignal], route: dict, contradictions: list[Contradiction]) -> SynthesisResult:
    """Phase 3-4: 合议 + 输出格式化"""
    if not signals:
        return SynthesisResult("neutral", 0.5, [], [], 0, 0, "数据不足无法合议", {})

    weights = route.get("weights", {})

    # 信号来源列表?
    direction_scores = {"bullish": 1.0, "neutral": 0.5, "bearish": 0.0, "mixed": 0.5}
    total_weight = 0.0
    weighted_score = 0.0

    for s in signals:
        w = weights.get(s.module, 0.1)
        weighted_score += direction_scores.get(s.direction, 0.5) * w * s.confidence
        total_weight += w

    avg_score = weighted_score / total_weight if total_weight > 0 else 0.5

    # 合议方向??
    if avg_score >= 0.65:
        consensus_dir = "bullish"
    elif avg_score <= 0.35:
        consensus_dir = "bearish"
    else:
        consensus_dir = "neutral"

    # 方向评分 (带权重)
    consistency_penalty = len(contradictions) * 0.1
    consensus_conf = max(0.1, min(1.0, avg_score - consistency_penalty))

    # ??
    bullish = sum(1 for s in signals if s.direction == "bullish")
    bearish = sum(1 for s in signals if s.direction == "bearish")

    # ??
    if contradictions:
        contradictions_text = "; ".join([f"{c.modules[0]} vs {c.modules[1]}: {c.aspect}" for c in contradictions[:2]])
        rec = f"存在{len(contradictions)}处矛盾({contradictions_text}) — 建议深入调研"
    elif consensus_dir == "bullish" and consensus_conf >= 0.6:
        rec = f"方向一致(置信{consensus_conf:.0%}) — 建议执行"
    elif consensus_dir == "bearish" and consensus_conf >= 0.6:
        rec = f"方向分歧(置信{consensus_conf:.0%}) — 建议观望"
    else:
        rec = f"数据不足(置信{consensus_conf:.0%}) — 建议补充数据"

    # Trace
    trace = {}
    for s in signals:
        trace[s.module] = f"{s.direction}(conf={s.confidence:.0%}): {s.insight[:60]}"

    return SynthesisResult(
        consensus_direction=consensus_dir,
        consensus_confidence=round(consensus_conf, 2),
        signals=signals,
        contradictions=contradictions,
        aligned_count=bullish,
        divergent_count=bearish + len(contradictions),
        recommendation=rec,
        trace=trace,
    )


# ============================================================
# Main Entry Point
# ============================================================


def run_synthesis(compute_results: dict, report_type: str = "industry_deep") -> SynthesisResult:
    """合议结果"""
    signals, route = normalize_all(compute_results, report_type)
    contradictions = detect_contradictions(signals)
    result = synthesize(signals, route, contradictions)
    return result


def synthesis_to_dict(result: SynthesisResult) -> dict:
    """Phase 4: 输出dict格式化"""
    return {
        "status": "ok",
        "method": "synthesis_engine",
        "consensus_direction": result.consensus_direction,
        "consensus_confidence": result.consensus_confidence,
        "signal_count": len(result.signals),
        "contradiction_count": len(result.contradictions),
        "aligned_count": result.aligned_count,
        "divergent_count": result.divergent_count,
        "recommendation": result.recommendation,
        "contradictions": [
            {
                "modules": c.modules,
                "aspect": c.aspect,
                "severity": c.severity,
                "left": c.left_value,
                "right": c.right_value,
                "resolution": c.resolution,
            }
            for c in result.contradictions
        ],
        "signals": [
            {"module": s.module, "direction": s.direction, "confidence": s.confidence, "insight": s.insight[:100]}
            for s in result.signals
        ],
        "trace": result.trace,
    }
