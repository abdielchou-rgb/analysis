# -*- coding: utf-8 -*-
"""弹性分析工具 (王思宇框架 - 建裕基金)

量化行业需求对经济变量的敏感度:
1. 需求收入弹性 IED: 需求量变化% / 收入变化%
2. 需求价格弹性 PED: 需求量变化% / 价格变化%
3. 供给价格弹性 PES: 供给量变化% / 价格变化%
4. 交叉价格弹性 XED: 需求量变化% / 相关品价格变化%
5. 刚需/弹性分级: 综合弹性判断行业类型

来源: E:\\9728\\王思宇 关于投资分析方法的探讨
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class ElasticityLevel(Enum):
    """弹性等级"""
    HIGHLY_INELASTIC = '<0.3'  # 高度刚需
    INELASTIC = '0.3-0.8'     # 刚需
    UNIT_ELASTIC = '0.8-1.2'  # 单位弹性
    ELASTIC = '1.2-2.0'       # 弹性
    HIGHLY_ELASTIC = '>2.0'   # 高度弹性
    NEGATIVE = '<0'           # 吉芬品/反常


class DemandType(Enum):
    """需求类型 - 决定弹性敏感性"""
    NECESSITY = 'necessity'      # 刚需 -- 收入弹性<1
    INVESTMENT = 'investment'    # 投资性需求 -- 收入弹性>=1
    DISCRETIONARY = 'discretionary'  # 非刚需/可选 -- 收入弹性>1


class SupplyType(Enum):
    """供给类型"""
    FIXED = 'fixed'            # 供给固定(短期不可调)
    CONSTRAINED = 'constrained' # 供给受限(有产能瓶颈)
    FLEXIBLE = 'flexible'      # 供给灵活


@dataclass
class ElasticityProfile:
    """行业弹性画像"""
    industry: str = ''
    income_elasticity: float = None   # IED 需求收入弹性
    price_elasticity_demand: float = None   # PED 需求价格弹性
    price_elasticity_supply: float = None   # PES 供给价格弹性
    cross_price_elasticity: float = None    # XED 交叉价格弹性
    demand_type: DemandType = DemandType.NECESSITY
    supply_type: SupplyType = SupplyType.FLEXIBLE

    # 定性判断
    business_cycle_sensitivity: str = ''
    pricing_power: str = ''
    substitution_risk: str = ''

    # 弹性矩阵
    elasticity_matrix: Dict = field(default_factory=dict)

    @property
    def is_cyclical(self) -> bool:
        """高收入弹性 + 高价格弹性 = 强周期"""
        if self.income_elasticity is None:
            return None
        return self.income_elasticity >= 1.0 and (
            self.price_elasticity_demand is None or self.price_elasticity_demand >= 0.8
        )

    @property
    def is_defensive(self) -> bool:
        """低收入弹性 + 低价格弹性 = 防御型"""
        if self.income_elasticity is None:
            return None
        return self.income_elasticity < 0.5 and (
            self.price_elasticity_demand is None or self.price_elasticity_demand < 0.5
        )

    def summary(self) -> str:
        """生成弹性分析总结"""
        lines = ['## 弹性分析总结']
        if self.income_elasticity is not None:
            lines.append(f'- 需求收入弹性(IED): {self.income_elasticity:.2f} '
                         f'({"高度弹性" if self.income_elasticity>2 else "弹性" if self.income_elasticity>1.2 else "单位弹性" if self.income_elasticity>0.8 else "刚需" if self.income_elasticity>0.3 else "高度刚需"})')
        if self.price_elasticity_demand is not None:
            lines.append(f'- 需求价格弹性(PED): {self.price_elasticity_demand:.2f}')
        if self.price_elasticity_supply is not None:
            lines.append(f'- 供给价格弹性(PES): {self.price_elasticity_supply:.2f}')
        if self.cross_price_elasticity is not None:
            lines.append(f'- 交叉价格弹性(XED): {self.cross_price_elasticity:.2f}')
        lines.append(f'- 需求类型: {self.demand_type.value}')
        lines.append(f'- 周期属性: {"强周期" if self.is_cyclical else "防御型" if self.is_defensive else "中性"}')
        lines.append(f'- 定价能力: {self.pricing_power}')
        lines.append(f'- 替代风险: {self.substitution_risk}')
        if self.elasticity_matrix:
            lines.append(f'- 弹性矩阵维度: {list(self.elasticity_matrix.keys())}')
        return '\n'.join(lines)


class ElasticityAnalyzer:
    """弹性分析引擎

    核心方法论:
    - 三列九宫格 (王思宇): 现状/趋势/风险 x 市场规模/竞争/能力
    - 四弹性测度: IED / PED / PES / XED
    - 弹性矩阵: 刚需/投资性需求/非刚需 x 收入/价格/供给/交叉弹性
    """

    # 行业默认弹性系数(参考值 - 基于历史数据归纳)
    INDUSTRY_ELASTICITY_DEFAULTS = {
        # 必需消费品(防御型)
        '食品饮料': {'ied': 0.3, 'ped': 0.4, 'pes': 0.6, 'demand_type': 'necessity'},
        '医药': {'ied': 0.2, 'ped': 0.3, 'pes': 0.7, 'demand_type': 'necessity'},
        '公用事业': {'ied': 0.1, 'ped': 0.2, 'pes': 0.4, 'demand_type': 'necessity'},
        '农业': {'ied': 0.3, 'ped': 0.5, 'pes': 0.3, 'demand_type': 'necessity'},
        # 可选消费(周期型)
        '房地产': {'ied': 1.5, 'ped': 1.2, 'pes': 0.5, 'demand_type': 'investment'},
        '汽车': {'ied': 1.3, 'ped': 1.1, 'pes': 0.7, 'demand_type': 'investment'},
        '家电': {'ied': 1.0, 'ped': 0.9, 'pes': 0.8, 'demand_type': 'investment'},
        '旅游': {'ied': 1.8, 'ped': 1.3, 'pes': 0.6, 'demand_type': 'discretionary'},
        # 工业/资本品
        '钢铁': {'ied': 1.2, 'ped': 0.6, 'pes': 0.5, 'demand_type': 'investment'},
        '化工': {'ied': 1.1, 'ped': 0.7, 'pes': 0.6, 'demand_type': 'investment'},
        '机械': {'ied': 1.3, 'ped': 0.8, 'pes': 0.5, 'demand_type': 'investment'},
        # TMT
        '半导体': {'ied': 1.0, 'ped': 0.5, 'pes': 0.4, 'demand_type': 'investment'},
        '软件': {'ied': 0.8, 'ped': 0.4, 'pes': 0.9, 'demand_type': 'investment'},
    }

    def __init__(self):
        self._defaults = self.INDUSTRY_ELASTICITY_DEFAULTS

    def classify_demand_type(self, industry: str, context: Dict = None) -> DemandType:
        """判断需求类型"""
        if industry in self._defaults:
            dt = self._defaults[industry]['demand_type']
            return DemandType(dt)

        # 无默认值时的推断逻辑
        if context:
            income_elasticity = context.get('income_elasticity', 1.0)
            if income_elasticity < 0.5:
                return DemandType.NECESSITY
            elif income_elasticity < 1.5:
                return DemandType.INVESTMENT
        return DemandType.DISCRETIONARY

    def estimate_income_elasticity(self, industry: str,
                                   gdp_growth: float = None,
                                   industry_growth: float = None) -> float:
        """估算需求收入弹性"""
        if industry in self._defaults:
            return self._defaults[industry]['ied']
        # 从行业增速与GDP增速推算
        if gdp_growth and industry_growth and gdp_growth > 0:
            return round(industry_growth / gdp_growth, 2)
        return 1.0  # 默认单位弹性

    def estimate_price_elasticity(self, industry: str,
                                  market_structure: str = 'competitive') -> float:
        """估算需求价格弹性 - 受竞争格局影响"""
        base = self._defaults.get(industry, {}).get('ped', 0.8)
        # 市场结构调节
        if market_structure == 'monopoly':
            return round(base * 0.5, 2)
        elif market_structure == 'oligopoly':
            return round(base * 0.7, 2)
        elif market_structure == 'monopolistic_competition':
            return round(base * 1.0, 2)
        else:  # perfect competition
            return round(base * 1.3, 2)

    def build_elasticity_matrix(self, demand_type: DemandType,
                                is_cyclical: bool = False) -> Dict:
        """构建弹性矩阵(王思宇三段式)"""
        # 参考: 刚需/投资性需求/非刚需 x 收入弹性/价格弹性/供给弹性/交叉弹性
        matrix = {}

        if demand_type == DemandType.NECESSITY:
            matrix['收入弹性'] = '<1 (刚需特征，经济下行时需求稳定)'
            matrix['价格弹性'] = '<1 (涨价不会明显抑制需求)'
            matrix['供给弹性'] = '<1 (短期供给调节能力弱)'
            matrix['交叉弹性'] = '<1 (替代品较少)'
            matrix['周期性'] = '防御型 - 经济下行期的避风港'
        elif demand_type == DemandType.INVESTMENT:
            matrix['收入弹性'] = '>=1 (与宏观经济周期共振)'
            matrix['价格弹性'] = '>=1 (价格敏感度中等)'
            matrix['供给弹性'] = '<1 (产能建设周期长)'
            matrix['交叉弹性'] = '<=1 (替代品有限)'
            matrix['周期性'] = '强周期 - 经济上行时弹性放大' if is_cyclical else '弱周期'
        else:  # DISCRETIONARY
            matrix['收入弹性'] = '>1 (经济下行时，可选消费最先被削减)'
            matrix['价格弹性'] = '>=1 (价格敏感度高)'
            matrix['供给弹性'] = '<=1 (取决于行业特征)'
            matrix['交叉弹性'] = '>=1 (替代品丰富)'
            matrix['周期性'] = '周期型 - 可选消费弹性最大'

        return matrix

    def analyze_market_size_factors(self, industry: str,
                                    context: Dict = None) -> Dict:
        """市场规模四因素分析(王思宇框架)

        总购买力 = 目标用户数 x 频次 x 单价
        供给能力 = 生产要素获取成本 + 购买过程成本 + 使用过程成本
        传播效率 = 广播模式 + 扩散模式
        适用条件 = 细分群体 + 使用场景 + 接触渠道
        """
        return {
            'total_purchasing_power': {
                'description': '总购买力 = 目标客户数 x 需求频次 x 客单价',
                'dimensions': ['用户数', '频次', '客单价'],
                'context': context or {}
            },
            'supply_capacity': {
                'description': '供给能力分析',
                'dimensions': ['生产要素成本', '购买过程成本', '使用过程成本']
            },
            'propagation_efficiency': {
                'description': '传播效率 - 广播模式 + 扩散模式',
                'dimensions': ['广播通知概率', '群体内扩散概率', '遗忘概率']
            },
            'applicable_conditions': {
                'description': '适用条件扩展',
                'dimensions': ['细分群体', '使用场景', '接触渠道']
            }
        }

    def analyze_competitive_position(self, elasticity: ElasticityProfile,
                                     market_share_data: Dict = None) -> Dict:
        """竞争位置与弹性交叉分析"""
        result = {}
        if elasticity.price_elasticity_demand and elasticity.price_elasticity_demand < 0.5:
            result['定价权'] = '强 - 低价格弹性意味着企业有定价权'
            result['利润空间'] = '毛利保护能力强，成本可以转嫁'
        else:
            result['定价权'] = '弱 - 高价格弹性意味着企业不能轻易涨价'
            result['利润空间'] = '成本上升难以转嫁，利润承压'

        if elasticity.is_cyclical:
            result['周期风险'] = '高 - 收入弹性大，利润波动幅度大于收入波动'
        else:
            result['周期风险'] = '低 - 刚需特征，利润稳定性好'

        return result

    def full_analysis(self, industry: str,
                      gdp_growth: float = None,
                      industry_growth: float = None,
                      market_structure: str = 'competitive') -> ElasticityProfile:
        """全量弹性分析 - 一站式输出"""
        demand_type = self.classify_demand_type(industry)
        ied = self.estimate_income_elasticity(industry, gdp_growth, industry_growth)
        ped = self.estimate_price_elasticity(industry, market_structure)

        profile = ElasticityProfile(
            industry=industry,
            income_elasticity=ied,
            price_elasticity_demand=ped,
            demand_type=demand_type,
            business_cycle_sensitivity='高' if ied and ied >= 1.0 else '低',
            pricing_power='强' if ped and ped < 0.5 else '中' if ped and ped < 1.0 else '弱',
            substitution_risk='低' if demand_type == DemandType.NECESSITY else '中'
        )

        profile.elasticity_matrix = self.build_elasticity_matrix(demand_type, profile.is_cyclical)
        return profile
