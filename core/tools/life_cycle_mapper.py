# -*- coding: utf-8 -*-
"""生命周期重心映射工具 (肖璟<如何快速了解一个行业>+ 戴老板周期思维)

核心方法论:
1. 肖璟: 行业不同生命周期阶段, 分析重心完全不同
2. 戴老板: 周期五条件判断法(价格历史低位/行业惨淡/需求刚性/供给弹性低/催化剂)

来源: E:\\9728\\如何快速了解一个行业 - 肖璟.md  +  E:\\9728\\戴老板知识库.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class LifeCycleStage:
    """行业生命周期阶段"""
    INTRODUCTION = '导入期'    # 技术路线验证期
    GROWTH = '成长期'          # 渗透率快速提升期
    MATURITY = '成熟期'        # 竞争格局稳定期
    DECLINE = '衰退期'         # 替代品侵蚀期


@dataclass
class LifeCycleAnalysis:
    """生命周期分析结果"""
    industry: str = ''
    stage: str = ''
    next_stage: str = ''         # 下一阶段
    time_to_next: str = ''       # 预计到达下一阶段的时间
    analysis_focus: Dict = field(default_factory=dict)  # 分析重心
    key_variables: List = field(default_factory=list)   # 核心变量
    typical_metrics: List = field(default_factory=list)  # 典型指标

    def summary(self) -> str:
        lines = [f'## 生命周期分析: {self.industry}']
        lines.append(f'当前阶段: {self.stage}')
        if self.next_stage:
            lines.append(f'下一阶段: {self.next_stage} ({self.time_to_next})')
        lines.append('')
        lines.append('### 分析重心')
        for key, val in self.analysis_focus.items():
            lines.append(f'- {key}: {val}')
        lines.append('')
        lines.append('### 核心变量')
        for v in self.key_variables:
            lines.append(f'- {v}')
        lines.append('')
        lines.append('### 典型指标')
        for m in self.typical_metrics:
            lines.append(f'- {m}')
        return '\n'.join(lines)


class LifeCycleMapper:
    """生命周期重心映射器"""

    # 各阶段分析重心映射表
    FOCUS_MAP = {
        LifeCycleStage.INTRODUCTION: {
            '分析重心': '技术路线是否可行, 产品-市场匹配(PMF)验证',
            '行业问题': '技术路线之争-哪条路线会胜出?',
            '研究重点': [
                '技术路线对比: 主流/下一代/颠覆性',
                '专利布局与研发投入',
                '融资能力(烧钱速度)',
                '早期用户反馈与PMF',
                '监管政策起步'
            ],
            '核心变量': [
                '技术迭代速度',
                '融资规模与估值',
                '关键专利数量',
                '试用用户增速',
                '补贴/税收优惠政策'
            ],
            '典型指标': [
                '研发投入/营收比',
                '专利授权数',
                '风险投资额',
                '早期用户留存率',
                '单位成本下降曲线(学习曲线)'
            ]
        },
        LifeCycleStage.GROWTH: {
            '分析重心': '渗透率能到多少, 增长质量如何, 单位经济模型是否跑通',
            '行业问题': '渗透率天花板在哪? 谁在超车?',
            '研究重点': [
                '渗透率曲线(当前vs饱和)',
                'S曲线加速拐点判断',
                '单位经济模型(LTV/CAC)',
                '竞争格局裂变',
                '产能扩张节奏'
            ],
            '核心变量': [
                '渗透率(当前vs饱和)',
                '用户增速与留存',
                '市场份额变化',
                '产能扩张计划',
                '毛利率趋势'
            ],
            '典型指标': [
                '渗透率及环比变化',
                'CAC(客户获取成本)',
                'LTV(客户生命周期价值)',
                'LTV/CAC比率(>3为健康)',
                '行业总产能扩张速度'
            ]
        },
        LifeCycleStage.MATURITY: {
            '分析重心': '竞争格局怎么变, 龙头企业护城河是否稳固',
            '行业问题': '格局固化还是重洗? 定价权在谁手里?',
            '研究重点': [
                '市场集中度CR3/CR5/CR10',
                '差异化空间判断',
                '客户粘性与转换成本',
                '可扩展性边界',
                '成本结构对比'
            ],
            '核心变量': [
                '市场份额(龙头vs追赶者)',
                '利润率差异',
                '客户留存率',
                '品牌溢价',
                '产能利用率'
            ],
            '典型指标': [
                'HHI指数(赫芬达尔)',
                'CR3/CR5集中度',
                '龙头vs行业平均ROE差',
                '前十大客户集中度',
                '资本开支/折旧比'
            ]
        },
        LifeCycleStage.DECLINE: {
            '分析重心': '替代产品何时出现, 存量博弈中的赢家是谁',
            '行业问题': '还能赚多久? 替代品冲击速度如何?',
            '研究重点': [
                '替代品渗透率与性能对比',
                '存量市场结构与退出壁垒',
                '剩余需求刚性',
                '成本衰减曲线',
                '政策/法规变化'
            ],
            '核心变量': [
                '替代品渗透率',
                '替代品相对性价比',
                '行业退出速度',
                '剩余客户粘性',
                '监管态度'
            ],
            '典型指标': [
                '替代品渗透率变化',
                '原产品价格跌幅',
                '产能退出速度',
                '龙头企业ROE',
                '现金流/营收比'
            ]
        }
    }

    def __init__(self):
        pass

    def analyze(self, industry: str, stage: str,
                penetration_rate: float = None,
                growth_rate: float = None,
                market_share_cr3: float = None,
                substitute_penetration: float = None) -> LifeCycleAnalysis:
        """执行生命周期分析"""
        analysis = LifeCycleAnalysis(industry=industry, stage=stage)

        # 映射分析重心
        focus = self.FOCUS_MAP.get(stage, {})
        analysis.analysis_focus = focus
        analysis.key_variables = focus.get('核心变量', [])
        analysis.typical_metrics = focus.get('典型指标', [])

        # 判断下一阶段
        if stage == LifeCycleStage.INTRODUCTION:
            if penetration_rate and penetration_rate > 0.05:
                analysis.next_stage = LifeCycleStage.GROWTH
                analysis.time_to_next = '渗透率突破10%时进入'
            else:
                analysis.next_stage = LifeCycleStage.GROWTH
                analysis.time_to_next = '技术路线确定后1-2年'
        elif stage == LifeCycleStage.GROWTH:
            if penetration_rate and penetration_rate > 0.5:
                analysis.next_stage = LifeCycleStage.MATURITY
                analysis.time_to_next = '渗透率超过50%时进入'
            elif growth_rate and growth_rate < 0.15:
                analysis.next_stage = LifeCycleStage.MATURITY
                analysis.time_to_next = '增速降至15%以下时进入'
            else:
                analysis.next_stage = LifeCycleStage.MATURITY
                analysis.time_to_next = '3-5年'
        elif stage == LifeCycleStage.MATURITY:
            if substitute_penetration and substitute_penetration > 0.3:
                analysis.next_stage = LifeCycleStage.DECLINE
                analysis.time_to_next = '替代品渗透率超30%时进入'
            else:
                analysis.next_stage = LifeCycleStage.DECLINE
                analysis.time_to_next = '替代技术成熟后5-10年'

        return analysis

    def get_cycle_stocks_five_conditions(self, industry: str,
                                         price_level: str = '中等',
                                         industry_sentiment: str = '正常',
                                         demand_rigidity: str = '中等',
                                         supply_elasticity: str = '中等',
                                         catalyst: str = '') -> Dict:
        """戴老板周期股五条件判断法"""
        conditions = {
            'condition_1_price': {
                'label': '价格处于历史低位',
                'current': price_level,
                'score': 1 if price_level == '低位' else 0.5 if price_level == '中等偏低' else 0
            },
            'condition_2_sentiment': {
                'label': '行业整体惨淡',
                'current': industry_sentiment,
                'score': 1 if industry_sentiment == '惨淡' else 0.5 if industry_sentiment == '低迷' else 0
            },
            'condition_3_demand': {
                'label': '产品需求刚性',
                'current': demand_rigidity,
                'score': 1 if demand_rigidity == '强' else 0.5 if demand_rigidity == '中等' else 0
            },
            'condition_4_supply': {
                'label': '供给弹性低(产能建设慢)',
                'current': supply_elasticity,
                'score': 1 if supply_elasticity == '低' else 0.5 if supply_elasticity == '中等' else 0
            },
            'condition_5_catalyst': {
                'label': '出现催化剂事件',
                'current': catalyst,
                'score': 1 if catalyst else 0
            }
        }
        total = sum(c['score'] for c in conditions.values())
        conditions['total_score'] = total
        conditions['max_score'] = 5
        conditions['verdict'] = (
            '强烈买入信号' if total >= 4 else
            '买入信号' if total >= 3 else
            '关注信号' if total >= 2 else
            '未满足条件'
        )
        return conditions
