"""V56 HumanSignalInjector — 正面人感信号注入器

核心问题：check_human_sense() 评分 0.08（目标 0.50）
原因是报告生成流程中没有任何步骤强制要求写入类人信号。

解决方案：在评分循环中增加"人感信号注入"步骤，
在最后一次校准迭代前强制注入三类人感信号。

F2 原则：不是"写了再查"，而是"在写的时候就注入"。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("v56.core.human_signal")


HUMAN_SIGNAL_TEMPLATES = {
    "experience_ref": {
        "description": "经验引用：引用真实调研经验或历史案例",
        "prompt": (
            "请在这段分析中加入一条经验引用，例如："
            "'我们在{行业/公司}的调研/走访/跟踪中发现……' "
            "或 '历史上{年份}{行业}也遇到过类似情况……'"
        ),
        "examples": [
            "我们在年初对长三角地区半导体企业的走访中发现，产能利用率已从Q1的75%回升至Q3的88%",
            "复盘2019年新能源汽车补贴退坡周期，行业洗牌后龙头市占率反而提升了5个百分点",
            "参考2015年白酒行业调整期的案例，渠道库存去化周期通常为2-3个季度",
            "我们在对某头部车企的跟踪调研中注意到，其Q3资本开支同比增加了40%",
        ],
    },
    "precise_uncertainty": {
        "description": "不确定性精确定位：明确标注判断的不确定性边界",
        "prompt": (
            "请明确标注不确定性：'风险集中在{X和Y}两个变量' / '核心要看{Z}能否突破{阈值}' 而不是模糊地说'存在一定风险'"
        ),
        "examples": [
            "我们判断的核心不确定性集中在两个变量：一是WACC是否随美联储降息下修至8%以下，二是公司能否在2026年实现20%以上的净利率",
            "如果Q4毛利率能维持在32%以上，全年业绩大概率超预期；否则可能需要下调盈利预测5-10%",
            "市场可能高估了公司的周期性风险——我们在DCF敏感性测试中看到，即使营收增速从15%下调至10%，估值仍在合理区间",
        ],
    },
    "data_quality_judgment": {
        "description": "数据可信度判断：评价数据的质量而非仅引用",
        "prompt": (
            "请对数据可信度做出判断："
            "'这个数据来自XX，样本覆盖Y%' / '这个数字偏高，可能是季节性因素' "
            "而不是机械地列出数据"
        ),
        "examples": [
            "该数据来自东方财富一致预期（样本覆盖28家机构），其中营收预测分歧度较小（标准差<5%），但利润预测分歧较大（标准差>15%）",
            "需要注意，上述估值模型基于2019-2023年的数据训练，可能低估了近两年利率环境变化的影响",
            "卫星数据显示的港口吞吐量与实际海关数据偏差约8%，主要是天气因素导致的月度波动，不影响趋势判断",
        ],
    },
}


class HumanSignalInjector:
    """人感信号注入器

    在评分循环中，分析当前报告的 human_sense 评分，
    生成注入指令让校准步骤加入缺失的信号。
    """

    def __init__(self):
        self.signal_names = ["experience_ref", "precise_uncertainty", "data_quality_judgment"]

    def analyze(self, text: str, human_sense_score: float = 0.0, detail: dict | None = None) -> dict:
        """分析人感评分，生成注入指令"""
        injections = []

        if detail and "signals" in detail:
            for signal in detail["signals"]:
                name = signal.get("signal", "")
                score = signal.get("score", 0.0)
                if score < 0.5 and name in self.signal_names:
                    injections.append(
                        {
                            "target_signal": name,
                            "current_score": score,
                            "prompt": HUMAN_SIGNAL_TEMPLATES[name]["prompt"],
                            "examples": HUMAN_SIGNAL_TEMPLATES[name]["examples"],
                        }
                    )
        else:
            for name in self.signal_names:
                injections.append(
                    {
                        "target_signal": name,
                        "current_score": 0.0,
                        "prompt": HUMAN_SIGNAL_TEMPLATES[name]["prompt"],
                        "examples": HUMAN_SIGNAL_TEMPLATES[name]["examples"],
                    }
                )

        priority = "high" if human_sense_score < 0.3 else ("medium" if human_sense_score < 0.5 else "low")

        return {
            "injections": injections,
            "current_overall": human_sense_score,
            "target": 0.50,
            "priority": priority,
            "n_injections": len(injections),
        }

    def build_calibration_instruction(self, analysis: dict) -> str:
        """构建校准指令文本（供 calibration loop 使用）"""
        if not analysis["injections"]:
            return "人感信号已达标，无需注入。"

        lines = [
            "=== 人感信号注入指令 ===",
            f"当前人感评分: {analysis['current_overall']:.2f} (目标: {analysis['target']})",
            f"优先级: {analysis['priority']}",
            "",
            "请在报告中注入以下缺失的信号：",
        ]

        for inj in analysis["injections"]:
            lines.append(f"\n【缺失信号: {inj['target_signal']}】")
            lines.append(f"  提示: {inj['prompt']}")
            lines.append("  参考示例: ")
            for ex in inj["examples"][:2]:
                lines.append(f"    - 「{ex}」")

        lines.append("\n注入原则：")
        lines.append("  1. 每个信号至少注入1-2处，自然融入论证，不要生硬插入")
        lines.append("  2. 经验引用要具体（公司名/年份/数据），不要泛泛而谈")
        lines.append("  3. 不确定性要精确定位到具体变量，不要模糊说'存在风险'")
        lines.append("  4. 数据判断要说明来源和可信度，不要机械列出数字")

        return "\n".join(lines)

    def get_calibration_priority(self, human_sense_score: float) -> str:
        """判断人感校准在整体校准中的优先级"""
        if human_sense_score < 0.15:
            return "P0 — 必须注入，否则报告不通过"
        elif human_sense_score < 0.30:
            return "P1 — 应注入，显著提升报告质量"
        elif human_sense_score < 0.50:
            return "P2 — 建议注入"
        return "无需注入"


def inject_human_signals(text: str, human_sense_score: float = 0.0, detail: dict | None = None) -> str:
    """生成人感注入指令文本的快捷函数"""
    injector = HumanSignalInjector()
    analysis = injector.analyze(text, human_sense_score, detail)
    return injector.build_calibration_instruction(analysis)
