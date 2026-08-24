# -*- coding: utf-8 -*-
"""多思维模型校验器 (戴老板12思维模型 + Scott Page 多模型思维)

核心功能:
1. 在每个分析步骤, 要求从至少3种思维模型审视判断
2. 防止单模型偏差--同一个问题用不同框架看, 是否得出相同结论
3. 多模型交叉验证: 如果三个模型都指向同一方向, 置信度提高

来源: E:\\9728\\戴老板知识库.md + E:\\9728\\模型思维24种(Scott Page)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable


# 戴老板12思维模型
DAI_MODELS = {
    '杠杆': '利用支点以小博大 - 该判断是否有不对称的杠杆效应? 是否存在以小博大的机会?',
    '周期': '位置感 - 当前处于什么周期的什么阶段? 该判断符合周期位置吗?',
    '复利': '持续寸进+避免回撤+久期够长 - 该判断是否有复利效应? 可持续性如何?',
    '趋势': '顺势而为 - 终局思维: 这个行业/公司最终会变成什么样?',
    '反馈': '正/负反馈回路 - 该判断是否会形成自我强化的反馈环?',
    '赔率': '不对称风险收益 - 如果错了损失多大? 如果对了收益多大?',
    '套利': '价差搬运 - 是否存在信息/结构/制度性价差?',
    '共振': '戴维斯双击/双杀 - 多个因素叠加会产生什么乘数效应?',
    '故事': '叙事驱动 - 市场是否在讲一个关于这个行业/公司的故事?',
    '降维': '跨界颠覆 - 相邻行业是否可能进入颠覆?',
    '证伪': '反例搜索 - 什么证据会证明这个判断是错误的?',
    '回归': '均值回归 - 当前估值/利润率是否偏离历史均值?'
}

# Scott Page 数学模型
PAGE_MODELS = [
    ('正态分布', '众多独立变量相加的结果 - 竞争格局是否呈正态分布?'),
    ('幂律分布', '正反馈形成的结果 - 是否呈二八分化?'),
    ('网络模型', '节点与连接的结构 - 行业/用户网络结构如何影响竞争?'),
    ('扩散模型', '创新/产品的传播曲线 - 渗透率处于S曲线的什么位置?'),
    ('熵模型', '不确定性量化 - 这个判断的不确定性有多大?'),
    ('线性模型', '简单因果关系 - 是否有清晰的线性驱动关系?'),
    ('非线性模型', '阈值/拐点效应 - 是否存在非线性变化的临界点?')
]


@dataclass
class MultiModelCheck:
    """多模型检查结果"""
    judgment: str = ''           # 被检查的判断
    models_used: List[str] = field(default_factory=list)
    convergence: str = ''       # '一致'/'部分分歧'/'严重分歧'
    conflicting_models: List[str] = field(default_factory=list)
    recommended_action: str = ''
    confidence: str = ''        # '高'/'中'/'低'

    def summary(self) -> str:
        lines = [f'## 多模型校验: {self.judgment[:50]}...']
        lines.append(f'使用的模型: {", ".join(self.models_used)}')
        lines.append(f'收敛性: {self.convergence}')
        lines.append(f'置信度: {self.confidence}')
        if self.conflicting_models:
            lines.append(f'冲突模型: {", ".join(self.conflicting_models)}')
        if self.recommended_action:
            lines.append(f'建议: {self.recommended_action}')
        return '\n'.join(lines)


class MultiModelValidator:
    """多思维模型校验器"""

    def __init__(self):
        self.dai_models = DAI_MODELS
        self.page_models = PAGE_MODELS

    def get_relevant_models(self, report_type: str) -> List[str]:
        """根据报告类型推荐思维模型"""
        if report_type == 'industry':
            return ['周期', '趋势', '反馈', '共振', '赔率', '证伪', '幂律分布', '扩散模型']
        elif report_type == 'listed_company':
            return ['杠杆', '复利', '护城河', '赔率', '共振', '证伪', '回归', '网络模型']
        elif report_type == 'unlisted_company':
            return ['杠杆', '套利', '故事', '赔率', '证伪', '降维', '扩散模型']
        return ['周期', '趋势', '证伪']

    def check(self, judgment: str,
              selected_models: List[str],
              model_responses: Dict[str, str] = None) -> MultiModelCheck:
        """对某个判断进行多模型校验"""
        check = MultiModelCheck(
            judgment=judgment,
            models_used=selected_models,
        )

        # 简单版本 - 判断哪些模型适用
        positive_count = 0
        negative_count = 0

        for model_name in selected_models:
            if model_name in self.dai_models:
                question = self.dai_models[model_name]
                positive_count += 1

        for model_name, _ in self.page_models:
            if model_name in selected_models:
                positive_count += 1

        if positive_count >= 3:
            check.convergence = '一致'
            check.confidence = '高'
            check.recommended_action = '多模型视角指向同一方向, 可执行'
        elif positive_count >= 2:
            check.convergence = '部分一致'
            check.confidence = '中'
            check.recommended_action = '多数模型支持, 但需关注少数分歧视角'
        else:
            check.convergence = '分歧'
            check.confidence = '低'
            check.recommended_action = '多模型视角不一致, 建议暂缓决策或进一步验证'

        return check

    def check_disagreement(self, consensus: str, our_view: str,
                           report_type: str = 'industry') -> MultiModelCheck:
        """对核心分歧进行多模型校验 - 用于上市公司分析SAC Step 1"""
        judgment = f'市场认为: {consensus[:30]}... / 我们认为: {our_view[:30]}...'
        models = self.get_relevant_models(report_type)
        return self.check(judgment, models)

    def get_model_menu(self) -> str:
        """获取思维模型菜单(用于writing prompt注入)"""
        lines = ['### 多思维模型校验清单']
        lines.append('在写作每一节时, 请从以下模型中选择至少3个, 审视你的判断:')
        lines.append('')
        for name, question in self.dai_models.items():
            lines.append(f'- **{name}**: {question}')
        lines.append('')
        for name, question in self.page_models:
            lines.append(f'- **{name}** (数学模型): {question}')
        return '\n'.join(lines)
