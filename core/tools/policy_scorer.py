# -*- coding: utf-8 -*-
"""政策力度评分工具 — CICC/CITIC 核心分析维度

将产业政策从定性判断升级为量化评分:
1. 政策方向评分(鼓励/中性/限制)
2. 政策执行率追踪(中央vs地方)
3. 政治周期定位
4. 政策博弈分析

来源: 圆桌会议CICC/CITIC建议 + 行业分析知识库_模块九
"""
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime


@dataclass
class PolicyAssessment:
    """政策评估结果"""
    industry: str = ''
    policy_direction: str = ''       # 鼓励/中性/限制
    policy_score: float = 0.0        # -10 到 +10
    execution_rate: float = 0.0      # 执行率 0-100%
    political_cycle: str = ''        # 当前政治周期定位
    key_policies: List[str] = field(default_factory=list)
    subsidy_status: str = ''         # 补贴阶段: 培育/退坡/退出
    regulatory_risk: str = ''        # 监管风险: high/medium/low

    def summary(self) -> str:
        lines = [f'## 政策分析: {self.industry}']
        lines.append(f'政策方向: {self.policy_direction} (评分: {self.policy_score:+.1f}/10)')
        lines.append(f'执行率: {self.execution_rate:.0f}%')
        lines.append(f'政治周期: {self.political_cycle}')
        lines.append(f'补贴阶段: {self.subsidy_status}')
        lines.append(f'监管风险: {self.regulatory_risk}')
        if self.key_policies:
            lines.append('\n关键政策:')
            for p in self.key_policies:
                lines.append(f'  - {p}')
        return '\n'.join(lines)


class PolicyScorer:
    """政策评分引擎 — 将产业政策量化为可比较的分数"""

    # 政策方向关键词
    POLICY_KEYWORDS = {
        'encourage': [
            '鼓励', '支持', '大力', '扶持', '补贴', '优惠', '免税',
            '优先', '重点', '专项资金', '示范', '标杆', '推广'
        ],
        'restrict': [
            '限制', '禁止', '淘汰', '整治', '关停', '压减',
            '环保红线', '产能置换', '减量替代', '负面清单'
        ],
        'neutral': [
            '规范', '引导', '促进', '完善', '健全', '优化', '调整'
        ]
    }

    # 中国政治周期
    POLITICAL_CYCLES = [
        ('两会', '3月', '政策密集出台期'),
        ('政治局会议', '4月/7月/10月/12月', '政策方向定调'),
        ('中央经济工作会议', '12月', '次年经济工作部署'),
        ('五中全会', '5年一次', '五年规划建议'),
        ('党代会', '5年一次', '重大政治方向'),
        ('三中全会', '5年一次', '重大改革部署'),
    ]

    def score_policy(self, industry: str,
                     policy_texts: List[str] = None,
                     policy_direction: str = '中性',
                     execution_rate: float = 0.5,
                     subsidy_phase: str = '成熟') -> PolicyAssessment:
        """政策量化评分"""
        score = 0.0

        # 方向评分
        if policy_direction == '鼓励':
            score = 5.0
        elif policy_direction == '中性':
            score = 0.0
        else:
            score = -5.0

        # 补贴阶段调整
        if subsidy_phase == '培育':
            score += 3.0  # 补贴高峰期
        elif subsidy_phase == '退坡':
            score -= 2.0  # 补贴正在退出
        elif subsidy_phase == '已退出':
            score -= 4.0  # 补贴已退出

        # 执行率调整
        score *= (0.5 + execution_rate * 0.5)  # 执行率越低, 实际效果越差

        # 政策文本分析提升评分精度
        if policy_texts:
            text = ' '.join(policy_texts)
            encourage_count = sum(1 for kw in self.POLICY_KEYWORDS['encourage'] if kw in text)
            restrict_count = sum(1 for kw in self.POLICY_KEYWORDS['restrict'] if kw in text)
            score += min(encourage_count * 0.5, 5.0)  # 每出现一个鼓励词+0.5
            score -= min(restrict_count * 0.5, 5.0)   # 每出现一个限制词-0.5

        # 计算监管风险
        if score >= 3:
            regulatory_risk = 'low'
        elif score >= -2:
            regulatory_risk = 'medium'
        else:
            regulatory_risk = 'high'

        return PolicyAssessment(
            industry=industry,
            policy_direction=policy_direction,
            policy_score=max(-10, min(10, score)),
            execution_rate=execution_rate,
            political_cycle=self._get_current_cycle(),
            subsidy_status=subsidy_phase,
            regulatory_risk=regulatory_risk,
        )

    def _get_current_cycle(self) -> str:
        """定位当前政治周期"""
        now = datetime.now()
        month = now.month
        if month == 3:
            return '两会: 政策密集出台期'
        elif month in [4, 7, 10]:
            return '政治局会议前后: 政策方向关注期'
        elif month == 12:
            return '中央经济工作会议: 次年部署关键期'
        else:
            return '常规期: 政策执行与督察'

    def get_policy_context_for_prompt(self, assessment: PolicyAssessment) -> str:
        """生成政策分析上下文"""
        return assessment.summary()

    def check_policy_in_report(self, report_text: str) -> Dict[str, bool]:
        """检查报告中政策分析的深度"""
        import re
        checks = {
            'policy_direction': bool(re.search(r'政策方向|鼓励|限制|中性', report_text)),
            'policy_score': bool(re.search(r'政策评分|政策力度|政策强度', report_text)),
            'execution_rate': bool(re.search(r'执行率|落地|落实', report_text)),
            'political_cycle': bool(re.search(r'两会|中央经济工作|党代会|五中全会', report_text)),
            'subsidy': bool(re.search(r'补贴|退坡|扶持', report_text)),
        }
        return checks
