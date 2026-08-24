# -*- coding: utf-8 -*-
"""产业链联动分析工具 — CITIC 核心方法论

核心理念: 行业不是孤立的, 一个行业的变化会沿产业链传导。
上游价格变化 → 中游成本/利润 → 下游终端需求

来源: 圆桌会议 CITIC建议 + 行业分析知识库_MECE
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class IndustryChainNode:
    """产业链节点"""
    name: str                           # 环节名称
    typical_margin: str = ''            # 典型利润率
    key_drivers: List[str] = field(default_factory=list)
    concentration: str = ''             # 集中度: high/medium/low
    entry_barrier: str = ''             # 进入壁垒: high/medium/low
    substitution_risk: str = ''         # 替代风险


@dataclass
class ChainTransmission:
    """产业链传导关系"""
    from_node: str
    to_node: str
    transmission_mechanism: str         # 价格/成本/技术/需求
    elasticity: float = 1.0             # 传导弹性
    time_lag: str = ''                  # 时滞
    current_status: str = ''            # current transmission status


@dataclass
class IndustryChainAnalysis:
    """产业链分析结果"""
    industry: str = ''
    chain: List[IndustryChainNode] = field(default_factory=list)
    transmissions: List[ChainTransmission] = field(default_factory=list)
    bottleneck_layer: str = ''           # 瓶颈层
    profit_concentration: str = ''       # 利润集中在哪层
    chain_verdict: str = ''             # 产业链判断

    def summary(self) -> str:
        lines = [f'## 产业链联动分析: {self.industry}']
        lines.append(f'瓶颈层: {self.bottleneck_layer}')
        lines.append(f'利润集中层: {self.profit_concentration}')
        lines.append(f'产业链判断: {self.chain_verdict}')
        lines.append('')
        lines.append('### 各环节')
        for n in self.chain:
            lines.append(f'- {n.name} (利润率: {n.typical_margin}, 集中度: {n.concentration})')
            if n.key_drivers:
                lines.append(f'  驱动因素: {", ".join(n.key_drivers[:3])}')
        lines.append('')
        lines.append('### 传导关系')
        for t in self.transmissions:
            lines.append(f'- {t.from_node} → {t.to_node}: {t.transmission_mechanism} (弹性: {t.elasticity})')
        return '\n'.join(lines)


class IndustryChainAnalyzer:
    """产业链分析引擎"""

    # 预设产业链模板
    CHAIN_TEMPLATES = {
        '新能源汽车': {
            'nodes': [
                '锂矿/钴矿', '电池材料(正极/负极/电解液)', '动力电池',
                '电驱动系统', '整车制造', '充电桩/后市场'
            ],
            'profit_concentration': '当前利润集中于电池环节(宁德时代等)和上游锂矿',
            'bottleneck': '上游锂资源(供给弹性低)',
        },
        '半导体': {
            'nodes': [
                '硅片/气体/设备', '芯片设计(EDA/IP)', '晶圆代工',
                '封装测试', '分销/终端应用'
            ],
            'profit_concentration': '利润集中于设备环节和高端设计',
            'bottleneck': '光刻机/EUV设备 / 先进制程产能',
        },
        '光伏': {
            'nodes': [
                '硅料', '硅片', '电池片', '组件', '逆变器/支架', '电站运营'
            ],
            'profit_concentration': '利润在产业链内快速迁移',
            'bottleneck': '周期性瓶颈: 不同阶段瓶颈不同',
        },
        '创新药': {
            'nodes': [
                '靶点发现/CRO', '临床前研究', '临床试验(I/II/III期)',
                'CDMO生产', '商业化/医保准入'
            ],
            'profit_concentration': '利润集中于有重磅品种的商业化阶段企业',
            'bottleneck': '临床成功率(约10%) + 医保谈判定价',
        },
        '人工智能': {
            'nodes': [
                'AI芯片(GPU/TPU)', '算力基础设施(云)', '基础模型(LLM)',
                '应用层(SaaS/Agent)', '终端硬件(机器人/自动驾驶)'
            ],
            'profit_concentration': '当前利润集中于算力层(AI芯片)',
            'bottleneck': '高端AI芯片供给 + 电力能源',
        },
    }

    def analyze(self, industry: str, custom_nodes: List[str] = None) -> IndustryChainAnalysis:
        """产业链分析"""
        analysis = IndustryChainAnalysis(industry=industry)

        template = self.CHAIN_TEMPLATES.get(industry, {})
        node_names = custom_nodes or template.get('nodes', [industry])

        for name in node_names:
            analysis.chain.append(IndustryChainNode(name=name))

        analysis.profit_concentration = template.get('profit_concentration', '待分析')
        analysis.bottleneck_layer = template.get('bottleneck', '待分析')

        # 自动构建上下游传导关系
        for i in range(len(analysis.chain) - 1):
            analysis.transmissions.append(ChainTransmission(
                from_node=analysis.chain[i].name,
                to_node=analysis.chain[i+1].name,
                transmission_mechanism='价格传导(成本推动)' if i < 2 else '需求拉动',
                elasticity=0.8,
                time_lag='1-3个月' if i < 2 else '3-6个月'
            ))

        # 基于瓶颈层的产业链判断
        if analysis.bottleneck_layer and analysis.bottleneck_layer != '待分析':
            analysis.chain_verdict = f'产业链瓶颈在{analysis.bottleneck_layer}, 该环节具有最强的定价权和利润分配权'
        else:
            analysis.chain_verdict = '产业链各环节利润分配相对均衡'

        return analysis

    def get_transmission_for_prompt(self, analysis: IndustryChainAnalysis) -> str:
        """生成产业链传导分析文本"""
        return analysis.summary()
