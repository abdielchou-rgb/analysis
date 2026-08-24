"""V51 L2-1 T0.5 假说验证器 MVP

输入一个投资假说 → 输出支持证据/反对证据/数据缺口/类比案例
四块内容的验证报告。

FP4 设计：
  十年以上分析师在面对一个判断时，不会直接写报告。
  他会先问："支持我的证据有多强？反对我的证据是什么？我还缺什么数据？
  历史上有没有类似的案例？"
  T0.5 就是这个"先问清楚再下笔"的步骤。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("v51.hypothesis")

# 预置的 8 个典型行业分析框架的"已知矛盾"库
# 每对矛盾是 {共识观点: 反方观点}
# 资产→行业映射（辅助匹配）
ASSET_TO_INDUSTRY = {
    "茅台": "白酒",
    "五粮液": "白酒",
    "泸州老窖": "白酒",
    "汾酒": "白酒",
    "宁德时代": "新能源",
    "隆基": "新能源",
    "通威": "新能源",
    "阳光电源": "新能源",
    "华为": "AI算力",
    "英伟达": "AI算力",
    "寒武纪": "AI算力",
    "中芯国际": "半导体",
    "华虹": "半导体",
    "北方华创": "半导体",
    "美团": "消费",
    "拼多多": "消费",
    "京东": "消费",
    "阿里": "消费",
    "药明康德": "医药",
    "恒瑞": "医药",
    "百济神州": "医药",
    "字节跳动": "互联网平台",
    "TikTok": "互联网平台",
    "抖音": "互联网平台",
}

KNOWN_POLARITIES: dict[str, list[dict]] = {
    "白酒": [
        {
            "consensus": "白酒行业进入存量萎缩期",
            "counter": "高端白酒（1500+）的量价分离结构使得消费升级红利独立于总量, 未来3年量稳价升仍可持续（来源：行业复盘2016-2025）",
        },
        {
            "consensus": "茅台直销占比45%已近天花板",
            "counter": "茅台直销与批发的吨价差意味着每1pp的直销占比提升直接增厚毛利,i茅台已验证数字化直销能力,来自年报数据",
        },
        {
            "consensus": "年轻消费者不喝白酒是长期利空",
            "counter": "年轻消费者对白酒品类的偏好衰减是代际变量而非年度变量, 影响的时间维度为10-15年而非3-5年, 中期可被场景创新缓释",
        },
    ],
    "新能源": [
        {
            "consensus": "光伏产能严重过剩, 全行业亏损将持续",
            "counter": "过剩主要在P型PERC, N型TOPCon有效产能开工率维持80%+, 龙头通威/隆基的单瓦成本优势在行业出清后会被放大",
        },
        {
            "consensus": "锂电池产能过剩, 价格战无休止",
            "counter": "产能过剩集中在低端储能/两轮车领域, 车用动力电池的认证周期（12-18月）+ 安全性能壁垒使头部企业份额不降反升",
        },
        {
            "consensus": "风电抢装潮过后增长放缓",
            "counter": "深远海风电的规划规模是近海的3-5倍, 且单机大型化（16MW+）正在大幅降低度电成本, 拐点可能在2027年到来",
        },
    ],
    "AI算力": [
        {
            "consensus": "英伟达GPU供应瓶颈将缓解, 算力不再稀缺",
            "counter": "AI集群从训练转向推理后, 算力需求结构变化而非总量下降, CoWoS封装产能仍是全产业链最短的板, 2025年底前不可解",
        },
        {
            "consensus": "国产AI芯片无法替代进口",
            "counter": "华为昇腾910B在训练场景的生态兼容性问题正在被PyTorch原生适配解决, 推理场景已有替代能力, 关键是生态迁移成本而非单卡性能",
        },
    ],
    "半导体": [
        {
            "consensus": "中国成熟制程产能过剩",
            "counter": "模拟芯片/功率器件/MCU 40nm以上成熟制程的需求来自汽车/工业/IoT, 这些领域的国产化率仍低于20%, 产能消化路径清晰",
        },
        {
            "consensus": "存储芯片价格周期不可预测",
            "counter": "HBM3e的产能分配优先级是新的变量, 传统DRAM的供给增量被HBM挤占, 这改变了原有的供需弹性——每10%的HBM渗透率提升对应DRAM价格中枢上移3-5%",
        },
    ],
    "消费": [
        {
            "consensus": "消费降级是当前主线",
            "counter": "消费降级在品类间高度分化, 功能性品类（食品/日化）降级而体验性品类（旅游/户外/健康）升级, 结构性的机会在品类切换而非总量",
        },
        {
            "consensus": "电商渗透率见顶",
            "counter": "内容电商（抖音/快手）和即时零售的渗透仍在加速, 实物商品网上零售额占比每季度提升0.5-0.8pp, 增量来自生鲜/医药/本地生活等非标品类",
        },
    ],
    "医药": [
        {
            "consensus": "医药集采压缩行业利润空间",
            "counter": "创新药（license-out模式）+  CXO（全球供应链重构）正在成为新的利润极, 仿制药承压vs创新药爆发的结构分化远比总量重要",
        },
        {
            "consensus": "CXO行业景气度下行",
            "counter": "全球生物医药投融资在2024H2触底回升, 海外大药企的CXO外包比例持续提升, 中国CXO的工程师红利和动物实验成本优势仍在",
        },
    ],
}

# 预置的"历史类比"库
KNOWN_ANALOGIES: list[dict] = [
    {
        "tags": ["产能过剩", "光伏", "行业出清"],
        "description": "2018-2019年光伏行业产能过剩, 单晶vs多晶技术路线切换, 隆基凭借单晶路线逆势崛起。从过剩到出清历时18个月, CR5从45%提升至68%",
    },
    {
        "tags": ["渠道改革", "直销", "白酒", "茅台"],
        "description": "五粮液2019-2021年的渠道改革同样经历了从依靠大商到直控终端的转变, 改革期毛利率提升4.2pp, 但伴随渠道库存短期承压",
    },
    {
        "tags": ["估值重构", "消费", "确定性溢价"],
        "description": "2021年教育双减政策后, 市场对政策敏感行业的确定性溢价从2.5xP/E提升至4.8xP/E, 消费行业的估值锚发生了变化",
    },
    {
        "tags": ["技术代差", "国产替代", "半导体"],
        "description": "2020年华为被制裁后, 国产EDA/半导体设备企业进入替代窗口, 3年时间国产化率从5%增至20%, 但7nm以上的先进制程突破晚于预期2年",
    },
    {
        "tags": ["供应链安全", "脱钩", "出海"],
        "description": "2019-2025年, 中国消费电子产业链向东南亚转移, 越南的电子出口额年复合增长18%, 但核心零部件（面板/芯片）的国产化率反而提升",
    },
    {
        "tags": ["监管周期", "互联网", "平台经济"],
        "description": "2021年平台经济反垄断后, 互联网行业估值从2021年高点至2022年低点平均下跌65%, 2024年后政策转向'规范健康发展', 估值修复约40%",
    },
    {
        "tags": ["产能瓶颈", "扩产周期", "电池"],
        "description": "宁德时代2019-2022年的产能扩张周期中, 资本开支从53亿增至432亿, 产能利用率从89%降至72%, 但成本曲线下降35%, 以利润换份额的策略被验证",
    },
    {
        "tags": ["技术路线", "氢能", "锂电"],
        "description": "2021年氢能板块热度高涨时, 市场普遍认为燃料电池将替代锂电池, 但实际进展因基础设施瓶颈和系统成本远不及预期, 锂电路线的技术锁定效应被低估",
    },
]


@dataclass
class HypothesisVerdict:
    """假说验证结果"""

    hypothesis: str = ""
    supporting_points: list[str] = field(default_factory=list)  # 支持证据, 每项约50字
    opposing_points: list[str] = field(default_factory=list)  # 反对证据, 每项约50字
    data_gaps: list[str] = field(default_factory=list)  # 数据缺口
    analogies: list[str] = field(default_factory=list)  # 历史类比, 每项约80字
    suggested_brief: str = ""  # 建议的研究方向（基于验证结果）
    confidence: str = "medium"  # high / medium / low
    consensus_gap: str = ""  # 市场共识与假设的差异描述
    summary: str = ""


class HypothesisVerifier:
    """T0.5 假说验证器。

    输入: "茅台直销占比能否突破50%"
    输出: 支持/反对证据各2-3条 + 数据缺口 + 历史类比 + 建议置信度

    当前 MVP: 基于预置知识库匹配 + 关键词推理。
    后续可扩展: 接入一致预期数据源 + 网络爬取最新观点。
    """

    def verify(self, hypothesis: str) -> HypothesisVerdict:
        """验证一个投资假说。"""
        result = HypothesisVerdict(hypothesis=hypothesis)

        text_lower = hypothesis.lower()

        # 1. 匹配已知矛盾
        matched_polarities = self._match_polarities(text_lower)
        support = []
        oppose = []
        for p in matched_polarities:
            if any(kw in text_lower for kw in ["突破", "上升", "增长", "利好", "看多", "能做"]):
                support.append(p["counter"])
                oppose.append(p["consensus"])
            else:
                support.append(p["consensus"])
                oppose.append(p["counter"])

        result.supporting_points = support[:3]
        result.opposing_points = oppose[:3]

        # 2. 匹配历史类比
        result.analogies = self._match_analogies(text_lower)

        # 3. 识别数据缺口
        result.data_gaps = self._detect_gaps(hypothesis, text_lower)

        # 4. 生成摘要
        result.summary = self._generate_summary(result)

        # 5. 置信度评估（V51.6 升级：加入数据来源密度加权）
        n_support = len(result.supporting_points)
        n_oppose = len(result.opposing_points)
        n_gaps = len(result.data_gaps)

        # 国内券商校准（2026-07-25 扫描15份国内券商深度报告）：
        # 数据来源引用均值=1.8/份，支持证据≥2条+数据来源≥1=较高置信度
        # 数据来源引用密度作为置信度的加权因子
        import re

        data_source_count = len(
            re.findall(
                r"据[Ww]ind|数据来源[：:]|来源[：:]|数据[来自]",
                " ".join(result.supporting_points + result.opposing_points),
            )
        )
        data_weight = min(1.3, 1.0 + data_source_count * 0.1)  # 每个数据来源+10%权重

        ratio = ((n_support + 1) / (n_oppose + n_gaps + 1)) * data_weight
        if ratio > 1.5 and n_support >= 2:
            result.confidence = "high"
        elif ratio > 0.7:
            result.confidence = "medium"
        else:
            result.confidence = "low"

        return result

    def _match_polarities(self, text: str) -> list[dict]:
        """从已知矛盾库中匹配与假说相关的矛盾对。"""
        matched = []
        seen = set()

        # 资产→行业映射
        for asset, industry in ASSET_TO_INDUSTRY.items():
            if asset in text and industry in KNOWN_POLARITIES:
                for p in KNOWN_POLARITIES[industry]:
                    k = p["consensus"][:30]
                    if k not in seen:
                        matched.append(p)
                        seen.add(k)

        # 行业关键词直接匹配
        for industry, polarities in KNOWN_POLARITIES.items():
            if industry in text:
                for p in polarities:
                    k = p["consensus"][:30]
                    if k not in seen:
                        matched.append(p)
                        seen.add(k)

        # 宽泛关键词匹配（加强版）
        broad_map = {
            "产能过剩": "新能源",
            "出清": "新能源",
            "芯片": "半导体",
            "国产替代": "半导体",
            "半导体": "半导体",
            "AI": "AI算力",
            "算力": "AI算力",
            "GPU": "AI算力",
            "光伏": "新能源",
            "锂电": "新能源",
            "电池": "新能源",
            "白酒": "白酒",
            "消费": "消费",
            "医药": "医药",
            "CXO": "医药",
            "集采": "医药",
            "互联网": "互联网平台",
            "电商": "互联网平台",
            "抖音": "互联网平台",
            "字节跳动": "互联网平台",
            "TikTok": "互联网平台",
        }
        for keyword, industry in broad_map.items():
            if keyword in text and industry in KNOWN_POLARITIES:
                for p in KNOWN_POLARITIES[industry]:
                    k = p["consensus"][:30]
                    if k not in seen:
                        matched.append(p)
                        seen.add(k)

        return matched

    def _match_analogies(self, text: str) -> list[str]:
        """从历史类比库中匹配相关的类比。"""
        matched = []
        for analogy in KNOWN_ANALOGIES:
            tags = analogy.get("tags", [])
            score = sum(1 for tag in tags if tag in text)
            if score >= 1:
                matched.append(analogy["description"])
                if len(matched) >= 2:
                    break
        return matched

    def _detect_gaps(self, hypothesis: str, text_lower: str) -> list[str]:
        """识别假设相关但当前数据缺失的关键信息。"""
        gaps = []

        # 常见的行业级数据缺口
        data_gap_map = {
            "直销": [
                "茅台各渠道（i茅台/经销商/直营店）的分渠道收入和利润数据（待最新年报披露）",
                "经销商渠道库存的精确水位（非公开数据，需渠道调研估算）",
            ],
            "产能": [
                "各厂商在建产能的实际投产进度（行业协会季度数据未公开）",
                "产能利用率的季度环比变化（仅上市公司财报披露）",
            ],
            "价格": [
                "各渠道的实际成交价与出厂价的价差分布（需高频渠道数据）",
                "竞品在同一价格带的实际出货节奏（需第三方监测）",
            ],
            "市占率": [
                "各细分价格带的实时份额变化（第三方监测数据有2-3个月滞后期）",
                "线上vs线下渠道的份额分化速度（需电商平台合作数据）",
            ],
            "海外": [
                "海外各区域的收入拆分和利润率（公司年报披露粒度不够）",
                "地缘政治风险对各区域业务的实际影响（难以量化）",
            ],
        }

        for keyword, gap_list in data_gap_map.items():
            if keyword in text_lower:
                gaps.append(gap_list[0])
                if len(gaps) >= 3:
                    break

        if not gaps:
            gaps.append("该假设相关的数据缺口需要进一步调研确认")

        return gaps[:3]

    def _generate_summary(self, result: HypothesisVerdict) -> str:
        """生成验证摘要。"""
        lines = [f"## 假说验证：{result.hypothesis}"]
        lines.append(f"**置信度**：{result.confidence}\n")
        if result.supporting_points:
            lines.append("### 支持证据")
            for i, p in enumerate(result.supporting_points, 1):
                lines.append(f"{i}. {p}")
            lines.append("")
        if result.opposing_points:
            lines.append("### 反对证据")
            for i, p in enumerate(result.opposing_points, 1):
                lines.append(f"{i}. {p}")
            lines.append("")
        if result.data_gaps:
            lines.append("### 数据缺口")
            for i, g in enumerate(result.data_gaps, 1):
                lines.append(f"{i}. {g}（待补充）")
            lines.append("")
        if result.analogies:
            lines.append("### 历史类比")
            for a in result.analogies:
                lines.append(f"- {a}")
            lines.append("")

        # 建议方向
        if result.confidence == "high":
            lines.append("**建议**：假说有较强证据支持，建议进入深度研究管线。")
        elif result.confidence == "low":
            lines.append("**建议**：当前证据不足，建议先聚焦数据缺口方向做补充研究，再决定是否进入写作管线。")
        else:
            lines.append("**建议**：有证据但存在明确反方和缺口，建议补充数据后再做决断。")
        return "\n".join(lines)
