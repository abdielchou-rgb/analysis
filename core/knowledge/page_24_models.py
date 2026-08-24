# Scott Page's 24 Thinking Models Extension
# Source: The Model Thinker by Scott Page
# Extends 戴老板's 12 models with additional 12 from Page's framework

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PageModelJudgment:
    model_name: str
    category: str  # 简化模型, 概率模型, 探索模型
    direction: str  # bullish/bearish/neutral
    confidence: float  # 0.0-1.0
    insight: str


@dataclass
class PageModelResult:
    judgments: List[PageModelJudgment]
    diversity_score: float  # 模型多样性评分
    consensus: str
    recommendation: str


# Additional 12 models from Scott Page (beyond 戴老板's 12)
PAGE_MODELS = [
    {
        "name": "智慧层次结构",
        "category": "简化模型",
        "question": "数据→信息→知识→智慧的层次是否清晰?",
        "eval": lambda d: ('neutral', 0.5, '需建立数据到智慧的完整链路')
    },
    {
        "name": "幂律分布判断",
        "category": "简化模型",
        "question": "市场格局是否遵循幂律分布(头部集中)?",
        "eval": lambda d: ('bullish' if d.get('集中度', 0) > 0.4 else 'neutral', 0.6,
            f"集中度{d.get('集中度',0):.0%},{'幂律分布明显' if d.get('集中度',0)>0.4 else '分布较分散'}")
    },
    {
        "name": "正反馈循环",
        "category": "简化模型",
        "question": "是否存在强者愈强的正反馈机制?",
        "eval": lambda d: ('bullish' if d.get('网络效应', False) else 'neutral', 0.5,
            '存在网络效应/规模递增' if d.get('网络效应') else '正反馈机制不明确')
    },
    {
        "name": "路径依赖",
        "category": "简化模型",
        "question": "历史选择是否锁定了未来发展方向?",
        "eval": lambda d: ('neutral', 0.5, '需分析行业历史技术路线锁定情况')
    },
    {
        "name": "信号博弈",
        "category": "概率模型",
        "question": "市场参与者如何通过信号传递信息?高质量公司如何与低质量区分?",
        "eval": lambda d: ('neutral', 0.5, '需分析企业信号传递机制(分红/回购/管理层持股)')
    },
    {
        "name": "空间博弈",
        "category": "概率模型",
        "question": "竞争者的空间位置如何影响定价和差异化?",
        "eval": lambda d: ('neutral', 0.5, '需分析行业竞争空间结构和差异化策略')
    },
    {
        "name": "传染病模型(SIR)",
        "category": "概率模型",
        "question": "创新/趋势的扩散速度和拐点在哪里?",
        "eval": lambda d: {
            'pen': d.get('渗透率', 0),
            'speed': '加速' if d.get('渗透率', 0) < 0.5 else '减速',
            'insight': f"渗透率{d.get('渗透率',0):.0%},{'加速扩散阶段' if d.get('渗透率',0)<0.5 else '减速成熟阶段'}"
        }
    },
    {
        "name": "群体智慧",
        "category": "概率模型",
        "question": "市场共识是否比单个预测更准确?分歧程度如何?",
        "eval": lambda d: ('neutral', 0.5, '需分析市场一致预期与分歧程度')
    },
    {
        "name": "合作演化",
        "category": "探索模型",
        "question": "行业内的合作与竞争如何演化?是否存在共赢均衡?",
        "eval": lambda d: ('neutral', 0.5, '需分析产业链合作格局和竞合关系')
    },
    {
        "name": "网络结构",
        "category": "探索模型",
        "question": "行业网络(供应链/客户/合作)的结构特征是什么?",
        "eval": lambda d: ('neutral', 0.5, '需分析行业网络结构和关键节点')
    },
    {
        "name": "复杂适应系统",
        "category": "探索模型",
        "question": "行业中的参与者如何适应环境变化?涌现特征是什么?",
        "eval": lambda d: ('neutral', 0.5, '需分析行业适应性和涌现特征')
    },
    {
        "name": "随机游走与均值回归",
        "category": "探索模型",
        "question": "行业指标是随机波动还是存在均值回归?",
        "eval": lambda d: {
            'pe_deviation': d.get('pe_percentile', 0.5),
            'insight': f"PE处于{d.get('pe_percentile',0.5):.0%}分位,"
                       f"{'均值回归可能性大' if abs(d.get('pe_percentile',0.5)-0.5)>0.3 else '估值合理'}"
        }
    },
]


def run_page_models(data: dict) -> PageModelResult:
    judgments = []
    for model in PAGE_MODELS:
        try:
            result = model['eval'](data)
            if isinstance(result, dict):
                # Complex result with insight string
                direction = 'neutral'
                confidence = 0.5
                insight = str(result.get('insight', ''))
            elif isinstance(result, tuple):
                direction, confidence, insight = result
            else:
                direction, confidence, insight = 'neutral', 0.5, str(result)
            judgments.append(PageModelJudgment(
                model_name=model['name'], category=model['category'],
                direction=direction, confidence=confidence, insight=insight
            ))
        except Exception as e:
            judgments.append(PageModelJudgment(
                model_name=model['name'], category='error',
                direction='neutral', confidence=0.0, insight=str(e)
            ))

    bullish = sum(1 for j in judgments if j.direction == 'bullish')
    bearish = sum(1 for j in judgments if j.direction == 'bearish')
    categories = len(set(j.category for j in judgments if j.category != 'error'))
    diversity = min(categories / 3.0, 1.0)
    avg_conf = sum(j.confidence for j in judgments) / max(len(judgments), 1)

    if bullish > bearish + 1:
        consensus = 'aligned_bullish'
        rec = 'Page模型偏多,' + f'置信度{avg_conf:.0%}'
    elif bearish > bullish + 1:
        consensus = 'aligned_bearish'
        rec = 'Page模型偏空,' + f'置信度{avg_conf:.0%}'
    else:
        consensus = 'divergent'
        rec = 'Page模型分歧明显,需进一步验证'

    return PageModelResult(
        judgments=judgments, diversity_score=diversity,
        consensus=consensus, recommendation=rec
    )


def format_summary(r: PageModelResult) -> str:
    lines = [f'Page 24模型扩展: {r.consensus} | 多样性:{r.diversity_score:.0%}']
    for j in r.judgments:
        lines.append(f'  [{j.category}] {j.model_name}: {j.direction}({j.confidence:.0%}) - {j.insight[:60]}')
    lines.append(f'建议: {r.recommendation}')
    return chr(10).join(lines)
