"""
戴老板12思维模型 — 多模型校验引擎

用于在核心分歧和关键判断环节，用多个思维模型交叉校验，
避免单一视角的确认偏误。

每个模型返回: (判断方向, 置信度, 理由)
"""

from dataclasses import dataclass


@dataclass
class ModelJudgment:
    model_name: str
    model_source: str  # 来源（戴老板/芒格/索罗斯等）
    direction: str  # bullish / bearish / neutral
    confidence: float  # 0.0-1.0
    key_insight: str
    applicable: bool = True


@dataclass
class MultiModelResult:
    judgments: list[ModelJudgment]
    consensus: str  # aligned / divergent / unclear
    bullish_count: int
    bearish_count: int
    neutral_count: int
    avg_confidence: float
    recommendation: str


# 12 个思维模型
THINKING_MODELS = [
    {
        "name": "二阶思维",
        "source": "霍华德·马克斯",
        "question": "市场当前共识是什么？如果共识正确会怎样？如果共识错误会怎样？",
        "eval": lambda data: _second_order(data),
    },
    {
        "name": "反身性",
        "source": "索罗斯",
        "question": "市场参与者的认知是否在改变基本面？是否存在正反馈循环？",
        "eval": lambda data: _reflexivity(data),
    },
    {
        "name": "能力圈",
        "source": "芒格",
        "question": "我们真的理解这家公司的生意吗？护城河可持续吗？",
        "eval": lambda data: _circle_of_competence(data),
    },
    {
        "name": "安全边际",
        "source": "格雷厄姆",
        "question": "当前价格较内在价值有多少折价？最坏情景下的保护有多厚？",
        "eval": lambda data: _margin_of_safety(data),
    },
    {
        "name": "均值回归",
        "source": "统计学",
        "question": "当前估值/利润率偏离历史均值多少？偏离可持续吗？",
        "eval": lambda data: _mean_reversion(data),
    },
    {
        "name": "周期定位",
        "source": "霍华德·马克斯",
        "question": "行业处于周期的什么位置？市场情绪处于什么钟摆位置？",
        "eval": lambda data: _cycle_position(data),
    },
    {
        "name": "博弈论",
        "source": "纳什",
        "question": "主要参与者的最优策略是什么？是否存在囚徒困境？",
        "eval": lambda data: _game_theory(data),
    },
    {
        "name": "复利思维",
        "source": "巴菲特",
        "question": "公司的竞争优势能否持续产生复利？再投资回报率如何？",
        "eval": lambda data: _compounding(data),
    },
    {
        "name": "幸存者偏差",
        "source": "统计学",
        "question": "我们看到的数据是否只包含了幸存者？失败案例告诉我们什么？",
        "eval": lambda data: _survivorship_bias(data),
    },
    {
        "name": "机会成本",
        "source": "经济学",
        "question": "如果不投这个标的，最好的替代选择是什么？",
        "eval": lambda data: _opportunity_cost(data),
    },
    {
        "name": "黑天鹅/灰犀牛",
        "source": "塔勒布",
        "question": "哪些低概率高影响事件可能颠覆判断？",
        "eval": lambda data: _black_swan(data),
    },
    {
        "name": "第一性原理",
        "source": "亚里士多德/马斯克",
        "question": "剥离所有假设后，生意的本质是什么？价值创造的真实来源是什么？",
        "eval": lambda data: _first_principles(data),
    },
]


@dataclass
class AnalysisContext:
    """分析上下文数据"""

    pe_percentile: float | None = None  # 当前PE历史分位
    roe: float | None = None  # ROE (%)
    roic: float | None = None  # ROIC (%)
    gross_margin: float | None = None  # 毛利率 (%)
    gross_margin_5y_avg: float | None = None  # 5年平均毛利率
    revenue_growth: float | None = None  # 收入增速 (%)
    industry_growth: float | None = None  # 行业增速 (%)
    market_share: float | None = None  # 市占率 (%)
    debt_ratio: float | None = None  # 资产负债率 (%)
    wacc: float | None = None  # WACC (%)
    roic_minus_wacc: float | None = None  # ROIC - WACC
    moat_score: int | None = None  # 护城河评分 1-10
    competitive_advantage: str | None = None  # 竞争优势描述
    industry_cycle: str | None = None  # 行业周期位置


def run_multi_model(data: AnalysisContext) -> MultiModelResult:
    """运行全部12个思维模型"""
    judgments = []
    for model in THINKING_MODELS:
        try:
            result = model["eval"](data)
            judgments.append(result)
        except Exception as e:
            judgments.append(
                ModelJudgment(
                    model_name=model["name"],
                    model_source=model["source"],
                    direction="neutral",
                    confidence=0.0,
                    key_insight=f"模型执行失败: {e}",
                    applicable=False,
                )
            )

    bullish = sum(1 for j in judgments if j.direction == "bullish")
    bearish = sum(1 for j in judgments if j.direction == "bearish")
    neutral = sum(1 for j in judgments if j.direction == "neutral")
    avg_conf = sum(j.confidence for j in judgments if j.applicable) / max(len(judgments), 1)

    # 共识判断
    net = bullish - bearish
    if abs(net) <= 1:
        consensus = "divergent"
    elif net > 0:
        consensus = "aligned_bullish"
    else:
        consensus = "aligned_bearish"

    # 建议
    if consensus == "aligned_bullish" and avg_conf > 0.6:
        rec = "多模型共识偏多，支持看多判断"
    elif consensus == "aligned_bearish" and avg_conf > 0.6:
        rec = "多模型共识偏空，支持看空判断"
    elif consensus == "divergent":
        rec = "多模型分歧明显，需更高的安全边际"
    else:
        rec = "模型信号不明确，建议等待更清晰信号"

    return MultiModelResult(
        judgments=judgments,
        consensus=consensus,
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        avg_confidence=avg_conf,
        recommendation=rec,
    )


# 模型实现
def _second_order(data: AnalysisContext) -> ModelJudgment:
    d = "neutral"
    c = 0.5
    insight = "需进一步分析市场共识与反共识"
    return ModelJudgment("二阶思维", "霍华德·马克斯", d, c, insight)


def _reflexivity(data: AnalysisContext) -> ModelJudgment:
    d = "neutral"
    c = 0.5
    insight = "需分析基本面与市场认知的互动关系"
    return ModelJudgment("反身性", "索罗斯", d, c, insight)


def _circle_of_competence(data: AnalysisContext) -> ModelJudgment:
    if data.moat_score is not None:
        if data.moat_score >= 7:
            return ModelJudgment("能力圈", "芒格", "bullish", 0.7, f"护城河评分{data.moat_score}/10，竞争优势清晰")
        elif data.moat_score >= 4:
            return ModelJudgment("能力圈", "芒格", "neutral", 0.5, f"护城河评分{data.moat_score}/10，竞争优势一般")
        else:
            return ModelJudgment("能力圈", "芒格", "bearish", 0.6, f"护城河评分{data.moat_score}/10，竞争优势薄弱")
    return ModelJudgment("能力圈", "芒格", "neutral", 0.5, "护城河评分数据缺失")


def _margin_of_safety(data: AnalysisContext) -> ModelJudgment:
    if data.pe_percentile is not None:
        if data.pe_percentile < 0.3:
            return ModelJudgment(
                "安全边际", "格雷厄姆", "bullish", 0.7, f"PE处于历史{data.pe_percentile:.0%}分位，较低"
            )
        elif data.pe_percentile > 0.7:
            return ModelJudgment(
                "安全边际", "格雷厄姆", "bearish", 0.6, f"PE处于历史{data.pe_percentile:.0%}分位，较高"
            )
        else:
            return ModelJudgment(
                "安全边际", "格雷厄姆", "neutral", 0.5, f"PE处于历史{data.pe_percentile:.0%}分位，中等"
            )
    return ModelJudgment("安全边际", "格雷厄姆", "neutral", 0.5, "估值分位数据缺失")


def _mean_reversion(data: AnalysisContext) -> ModelJudgment:
    if data.gross_margin is not None and data.gross_margin_5y_avg is not None:
        deviation = data.gross_margin - data.gross_margin_5y_avg
        if abs(deviation) > 10:
            return ModelJudgment(
                "均值回归",
                "统计学",
                "neutral",
                0.6,
                f"毛利率{data.gross_margin:.1f}%偏离5年均值{deviation:+.1f}pp，回归风险较高",
            )
        elif deviation > 5:
            return ModelJudgment(
                "均值回归", "统计学", "bearish", 0.5, f"毛利率高于均值{deviation:+.1f}pp，可能均值回归"
            )
        elif deviation < -5:
            return ModelJudgment(
                "均值回归", "统计学", "bullish", 0.5, f"毛利率低于均值{deviation:+.1f}pp，可能均值回归上行"
            )
    return ModelJudgment("均值回归", "统计学", "neutral", 0.5, "毛利率趋势数据不足")


def _cycle_position(data: AnalysisContext) -> ModelJudgment:
    if data.industry_cycle:
        if data.industry_cycle in ["导入期", "复苏期"]:
            return ModelJudgment("周期定位", "霍华德·马克斯", "bullish", 0.6, f"行业处于{data.industry_cycle}")
        elif data.industry_cycle in ["成熟期", "繁荣期"]:
            return ModelJudgment("周期定位", "霍华德·马克斯", "neutral", 0.5, f"行业处于{data.industry_cycle}")
        elif data.industry_cycle in ["衰退期", "出清期"]:
            return ModelJudgment("周期定位", "霍华德·马克斯", "bearish", 0.6, f"行业处于{data.industry_cycle}")
    return ModelJudgment("周期定位", "霍华德·马克斯", "neutral", 0.5, "行业周期数据缺失")


def _game_theory(data: AnalysisContext) -> ModelJudgment:
    return ModelJudgment("博弈论", "纳什", "neutral", 0.5, "需分析主要参与者的策略互动")


def _compounding(data: AnalysisContext) -> ModelJudgment:
    if data.roic_minus_wacc is not None:
        if data.roic_minus_wacc > 5:
            return ModelJudgment(
                "复利思维", "巴菲特", "bullish", 0.7, f"ROIC-WACC={data.roic_minus_wacc:.1f}pp，价值创造能力强"
            )
        elif data.roic_minus_wacc > 0:
            return ModelJudgment(
                "复利思维", "巴菲特", "neutral", 0.5, f"ROIC-WACC={data.roic_minus_wacc:.1f}pp，价值创造一般"
            )
        else:
            return ModelJudgment(
                "复利思维", "巴菲特", "bearish", 0.6, f"ROIC-WACC={data.roic_minus_wacc:.1f}pp，价值在毁灭"
            )
    return ModelJudgment("复利思维", "巴菲特", "neutral", 0.5, "ROIC/WACC数据不足")


def _survivorship_bias(data: AnalysisContext) -> ModelJudgment:
    return ModelJudgment("幸存者偏差", "统计学", "neutral", 0.5, "需关注同行业失败案例的教训")


def _opportunity_cost(data: AnalysisContext) -> ModelJudgment:
    if data.wacc is not None and data.pe_percentile is not None:
        if data.pe_percentile < 0.3 and data.wacc < 8:
            return ModelJudgment("机会成本", "经济学", "bullish", 0.6, "估值低位+低利率环境，机会成本低")
    return ModelJudgment("机会成本", "经济学", "neutral", 0.5, "机会成本评估数据不足")


def _black_swan(data: AnalysisContext) -> ModelJudgment:
    if data.debt_ratio is not None and data.debt_ratio > 70:
        return ModelJudgment(
            "黑天鹅/灰犀牛", "塔勒布", "bearish", 0.6, f"负债率{data.debt_ratio:.0f}%，高杠杆下的尾部风险值得关注"
        )
    return ModelJudgment("黑天鹅/灰犀牛", "塔勒布", "neutral", 0.5, "尾部风险评估数据不足")


def _first_principles(data: AnalysisContext) -> ModelJudgment:
    return ModelJudgment("第一性原理", "亚里士多德/马斯克", "neutral", 0.5, "需回归生意的本质：单位经济模型是否成立？")


def format_summary(result: MultiModelResult) -> str:
    """生成多模型校验的中文总结"""
    lines = [
        f"多模型校验结果：{result.bullish_count}多/{result.bearish_count}空/{result.neutral_count}中性",
        f"共识方向：{'偏多' if result.consensus == 'aligned_bullish' else '偏空' if result.consensus == 'aligned_bearish' else '分歧'}",
        f"平均置信度：{result.avg_confidence:.0%}",
        f"建议：{result.recommendation}",
        "",
        "详细判断：",
    ]
    for j in result.judgments:
        if j.applicable:
            icon = {"bullish": "▲", "bearish": "▼", "neutral": "◆"}.get(j.direction, "?")
            lines.append(f"  {icon} [{j.model_name}]({j.model_source}): {j.key_insight}")
    return "\n".join(lines)


if __name__ == "__main__":
    ctx = AnalysisContext(
        pe_percentile=0.25,
        roe=15,
        roic=12,
        gross_margin=35,
        gross_margin_5y_avg=32,
        debt_ratio=45,
        wacc=8.4,
        roic_minus_wacc=3.6,
        moat_score=7,
        industry_cycle="成长期",
    )
    result = run_multi_model(ctx)
    print(format_summary(result))
