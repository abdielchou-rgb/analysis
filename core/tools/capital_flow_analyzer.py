# -*- coding: utf-8 -*-
"""资金面分析工具 — CICC/CITIC 核心分析维度

涵盖:
1. 北向资金（沪深港通）近30日净流入
2. 公募基金仓位与重仓股变动
3. 两融余额变化
4. ETF净申购/赎回
5. 大股东增减持动态
6. 限售股解禁日历
7. 产业资本动向

来源: 圆桌会议 CICC/CITIC 建议
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CapitalFlowSnapshot:
    """资金面快照"""
    northbound_30d_net: float = 0.0       # 北向近30日净流入(亿元)
    northbound_trend: str = 'neutral'      # 趋势: inflow/outflow/neutral
    mutual_fund_position: float = 0.0      # 公募仓位(%)
    margin_balance: float = 0.0            # 两融余额(亿元)
    margin_trend: str = 'neutral'          # 趋势: rising/falling/neutral
    etf_net_subscription: float = 0.0      # ETF净申购(亿元)
    major_shareholder_net: float = 0.0     # 大股东增减持净额(亿元)
    lockup_expiry_next_3m: float = 0.0     # 未来3个月解禁市值(亿元)
    industry_sentiment: str = 'neutral'    # 行业情绪: bullish/bearish/neutral

    def summary(self) -> str:
        lines = ['## 资金面分析']
        nbi = '净流入' if self.northbound_30d_net > 0 else '净流出' if self.northbound_30d_net < 0 else '平衡'
        lines.append(f'- 北向资金(30日): {abs(self.northbound_30d_net):.1f}亿 {nbi}')
        lines.append(f'- 公募仓位: {self.mutual_fund_position:.1f}%')
        lines.append(f'- 两融余额: {self.margin_balance:.0f}亿 ({self.margin_trend})')
        lines.append(f'- ETF净申赎: {self.etf_net_subscription:.1f}亿')
        lines.append(f'- 大股东增减持: {self.major_shareholder_net:.1f}亿')
        lines.append(f'- 未来3月解禁: {self.lockup_expiry_next_3m:.0f}亿')
        lines.append(f'- 行业情绪: {self.industry_sentiment}')
        return '\n'.join(lines)


class CapitalFlowAnalyzer:
    """资金面分析引擎"""

    def analyze_industry_flow(self, industry: str,
                              northbound_data: Dict = None,
                              fund_data: Dict = None,
                              margin_data: Dict = None) -> CapitalFlowSnapshot:
        """行业资金面综合分析"""
        snapshot = CapitalFlowSnapshot()

        # 北向资金
        if northbound_data:
            snapshot.northbound_30d_net = northbound_data.get('net_inflow_30d', 0)
            snapshot.northbound_trend = 'inflow' if snapshot.northbound_30d_net > 10 else \
                                        'outflow' if snapshot.northbound_30d_net < -10 else 'neutral'

        # 公募基金
        if fund_data:
            snapshot.mutual_fund_position = fund_data.get('position_pct', 85.0)

        # 两融
        if margin_data:
            snapshot.margin_balance = margin_data.get('balance', 0)
            snapshot.margin_trend = margin_data.get('trend', 'neutral')

        # 综合情绪
        positive_signals = sum([
            snapshot.northbound_trend == 'inflow',
            snapshot.margin_trend == 'rising',
        ])
        negative_signals = sum([
            snapshot.northbound_trend == 'outflow',
            snapshot.margin_trend == 'falling',
        ])
        snapshot.industry_sentiment = 'bullish' if positive_signals > negative_signals else \
                                      'bearish' if negative_signals > positive_signals else 'neutral'

        return snapshot

    def get_context_for_prompt(self, snapshot: CapitalFlowSnapshot) -> str:
        """生成用于注入writing prompt的资金面上下文"""
        return snapshot.summary()

    def check_capital_flow_in_report(self, report_text: str) -> Dict[str, bool]:
        """检查报告中是否包含了资金面分析"""
        import re
        checks = {
            'northbound': bool(re.search(r'北向资金|沪深港通|外资', report_text)),
            'mutual_fund': bool(re.search(r'公募|基金仓位|机构持仓', report_text)),
            'margin': bool(re.search(r'两融|融资融券|杠杆资金', report_text)),
            'major_shareholder': bool(re.search(r'大股东|增减持|产业资本', report_text)),
            'lockup_expiry': bool(re.search(r'解禁|限售股', report_text)),
        }
        return checks
