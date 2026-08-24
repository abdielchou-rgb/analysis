"""信号验证工具 (申银万国证券研究所 - 驱动力+信号验证方法论)

核心逻辑:
  信号一(先行指标) → 信号二(同步指标) → 信号三(滞后指标)
      ↓
  驱动力确认 → 投资决策(买入/卖出/持有)

21个行业关键假设表: 以损益表为标准化模板,
每个行业提炼最具解释力的外生指标。

来源: E:\\9728\\行业分析知识库_MECE - 模块一1.2
"""

from dataclasses import dataclass, field


@dataclass
class Signal:
    """单个信号定义"""

    name: str  # 信号名称
    indicator: str  # 具体指标
    direction: str  # '上升'/'下降'/'突破'/'跌破'
    threshold: str = ""  # 阈值
    data_source: str = ""  # 数据来源
    frequency: str = ""  # 更新频率
    current_status: str = ""  # 当前状态
    is_triggered: bool = False  # 是否触发

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "indicator": self.indicator,
            "direction": self.direction,
            "threshold": self.threshold,
            "source": self.data_source,
            "frequency": self.frequency,
            "status": self.current_status,
            "triggered": self.is_triggered,
        }


@dataclass
class SignalChain:
    """三级信号链"""

    industry: str = ""
    theme: str = ""  # 分析主题(如'买入信号'/'卖出信号')
    leading: list[Signal] = field(default_factory=list)  # 先行指标(1-3个)
    coincident: list[Signal] = field(default_factory=list)  # 同步指标(1-3个)
    lagging: list[Signal] = field(default_factory=list)  # 滞后指标(1-3个)
    driver: str = ""  # 驱动力确认
    decision: str = ""  # 投资决策
    confidence: str = "中"  # 置信度(高/中/低)

    @property
    def triggered_count(self) -> int:
        return sum(s.is_triggered for chain in [self.leading, self.coincident, self.lagging] for s in chain)

    @property
    def total_count(self) -> int:
        return len(self.leading) + len(self.coincident) + len(self.lagging)

    @property
    def trigger_ratio(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.triggered_count / self.total_count

    def summary(self) -> str:
        """生成信号链总结"""
        lines = [f"## 信号链分析: {self.industry} - {self.theme}"]
        lines.append(f"驱动力: {self.driver}")
        lines.append(f"决策: {self.decision} (置信度: {self.confidence})")
        lines.append(f"触发率: {self.triggered_count}/{self.total_count} = {self.trigger_ratio:.0%}")
        for label, signals in [("先行指标", self.leading), ("同步指标", self.coincident), ("滞后指标", self.lagging)]:
            for s in signals:
                icon = "✓" if s.is_triggered else "○"
                lines.append(f"  [{icon}] {label}: {s.name} ({s.indicator} {s.direction} {s.threshold})")
                if s.current_status:
                    lines.append(f"        当前: {s.current_status}")
        return "\n".join(lines)


class SignalChainBuilder:
    """信号链构建器

    核心方法论(申银万国):
    - 先行指标: 预测性最强, 先于行业基本面变化
    - 同步指标: 与行业基本面同步变化
    - 滞后指标: 确认趋势后变化

    21个行业关键假设表的构建:
    以损益表为标准化模板, 每个行业提炼最具解释力的外生指标。
    """

    # 行业关键假设表(部分 - 来自申银万国体系)
    INDUSTRY_KEY_ASSUMPTIONS = {
        "煤炭": {
            "leading": [
                ("秦皇岛港库存", "秦皇岛港煤炭库存", "连续上升>5%", "煤炭运销协会", "周"),
                ("电厂库存天数", "重点电厂煤炭库存可用天数", "突破25天", "中电联", "周"),
            ],
            "coincident": [
                ("坑口价格", "主产区煤炭坑口价", "环比变化", "煤炭运销协会", "日"),
                ("港口价格", "秦皇岛港Q5500动力煤平仓价", "同比变化", "秦皇岛煤炭网", "日"),
            ],
            "lagging": [
                ("海运费", "煤炭海运费(秦皇岛-广州)", "连续下跌>10%", "上海航运交易所", "周"),
                ("发电量", "火电发电量同比", "增速转负", "国家能源局", "月"),
            ],
        },
        "钢铁": {
            "leading": [
                ("钢材库存", "钢材社会库存", "连续下降>3周", "Mysteel", "周"),
                ("高炉开工率", "全国高炉开工率", "触底回升>2周", "Mysteel", "周"),
            ],
            "coincident": [
                ("钢材价格", "螺纹钢HRB400价格", "环比变化", "Mysteel", "日"),
                ("粗钢产量", "日均粗钢产量", "同比变化", "中钢协", "旬"),
            ],
            "lagging": [
                ("铁矿石价格", "普氏62%铁矿石指数", "企稳", "普氏能源", "日"),
                ("钢厂利润", "重点钢厂利润率", "触底回升", "中钢协", "月"),
            ],
        },
        "房地产": {
            "leading": [
                ("销售面积", "30大中城市商品房成交面积", "连续增长>4周", "Wind", "周"),
                ("按揭利率", "首套房按揭贷款利率", "下降>50bp", "融360", "月"),
            ],
            "coincident": [
                ("新开工", "房屋新开工面积同比", "收窄", "国家统计局", "月"),
                ("土地成交", "百城土地成交建面", "环比改善", "中指研究院", "周"),
            ],
            "lagging": [
                ("开发投资", "房地产开发投资完成额同比", "企稳", "国家统计局", "月"),
                ("库存", "商品房待售面积", "下降", "国家统计局", "月"),
            ],
        },
        "半导体": {
            "leading": [
                ("全球半导体销售", "全球半导体月度销售额同比", "转正>3个月", "SIA", "月"),
                ("费城半导体指数", "SOX指数", "趋势向上", "NASDAQ", "日"),
            ],
            "coincident": [
                ("晶圆代工利用率", "中芯国际/华虹产能利用率", "回升>80%", "公司公告", "季"),
                ("存储芯片价格", "DRAM NAND现货价格", "企稳回升", "DRAMeXchange", "周"),
            ],
            "lagging": [
                ("设备出货", "北美半导体设备出货额同比", "转正", "SEMI", "月"),
                ("资本开支", "主要晶圆厂资本开支指引", "上调", "公司公告", "季"),
            ],
        },
        "新能源汽车": {
            "leading": [
                ("渗透率", "新能源车月销量渗透率", "突破关键阈值", "乘联会", "月"),
                ("充电桩建设", "公共充电桩保有量同比", "增速>50%", "中国充电联盟", "月"),
            ],
            "coincident": [
                ("月销量", "新能源乘用车月销量", "同比环比双增", "乘联会", "月"),
                ("电池价格", "动力电池电芯价格", "下降趋势", "鑫椤锂电", "周"),
            ],
            "lagging": [
                ("单车盈利", "头部车企单车净利润", "改善", "公司公告", "季"),
                ("海外出口", "新能源车月度出口量", "同比增长", "海关总署", "月"),
            ],
        },
    }

    def __init__(self):
        self._assumptions = self.INDUSTRY_KEY_ASSUMPTIONS

    def build_chain(
        self, industry: str, theme: str = "行业趋势判断", driver: str = "", decision: str = ""
    ) -> SignalChain:
        """为行业构建信号链"""
        chain = SignalChain(industry=industry, theme=theme, driver=driver, decision=decision)

        assumptions = self._assumptions.get(industry, {})
        for sig_data in assumptions.get("leading", []):
            chain.leading.append(
                Signal(
                    name=sig_data[0],
                    indicator=sig_data[1],
                    direction=sig_data[2],
                    data_source=sig_data[3],
                    frequency=sig_data[4] if len(sig_data) > 4 else "",
                )
            )

        for sig_data in assumptions.get("coincident", []):
            chain.coincident.append(
                Signal(
                    name=sig_data[0],
                    indicator=sig_data[1],
                    direction=sig_data[2],
                    data_source=sig_data[3],
                    frequency=sig_data[4] if len(sig_data) > 4 else "",
                )
            )

        for sig_data in assumptions.get("lagging", []):
            chain.lagging.append(
                Signal(
                    name=sig_data[0],
                    indicator=sig_data[1],
                    direction=sig_data[2],
                    data_source=sig_data[3],
                    frequency=sig_data[4] if len(sig_data) > 4 else "",
                )
            )

        return chain

    def update_status(self, chain: SignalChain, triggers: dict[str, bool]) -> SignalChain:
        """根据实际数据更新信号触发状态"""
        for label, signals in [
            ("leading", chain.leading),
            ("coincident", chain.coincident),
            ("lagging", chain.lagging),
        ]:
            for sig in signals:
                key = f"{label}.{sig.name}"
                if key in triggers:
                    sig.is_triggered = triggers[key]
        return chain

    def get_available_industries(self) -> list[str]:
        """获取有预定义信号链的行业列表"""
        return list(self._assumptions.keys())

    def custom_chain(
        self,
        industry: str,
        theme: str,
        leading: list[tuple],
        coincident: list[tuple],
        lagging: list[tuple],
        driver: str = "",
        decision: str = "",
    ) -> SignalChain:
        """手动构建信号链(行业不在预定义表中时使用)"""
        chain = SignalChain(industry=industry, theme=theme, driver=driver, decision=decision)
        for item in leading:
            chain.leading.append(
                Signal(
                    name=item[0],
                    indicator=item[1],
                    direction=item[2],
                    data_source=item[3] if len(item) > 3 else "",
                    frequency=item[4] if len(item) > 4 else "",
                )
            )
        for item in coincident:
            chain.coincident.append(
                Signal(
                    name=item[0],
                    indicator=item[1],
                    direction=item[2],
                    data_source=item[3] if len(item) > 3 else "",
                    frequency=item[4] if len(item) > 4 else "",
                )
            )
        for item in lagging:
            chain.lagging.append(
                Signal(
                    name=item[0],
                    indicator=item[1],
                    direction=item[2],
                    data_source=item[3] if len(item) > 3 else "",
                    frequency=item[4] if len(item) > 4 else "",
                )
            )
        return chain
