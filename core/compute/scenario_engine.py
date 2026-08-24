"""scenario_engine.py — 情景触发引擎（2026-08-08 框架优化 P0）

顶级打法：高盛/大摩情景规划用"触发指标"驱动情景概率，而非拍脑袋（油位 30/50/20 是拍的）。

本引擎：三/多情景 + 触发信号 + 信号驱动概率修正。
  1. 定义情景（乐观/基准/悲观）
  2. 每情景配触发信号（政策执行率/订单/渗透率等）
  3. 输入当前信号值 → 概率修正（信号命中哪情景则上调）

用法：
  from core.compute.scenario_engine import ScenarioEngine, Scenario, TriggerSignal
  engine = ScenarioEngine([
    Scenario("乐观", 0.30, [TriggerSignal("罐箱渗透率", ">15%", +0.3), ...]),
    Scenario("基准", 0.50, [...]),
    Scenario("悲观", 0.20, [...]),
  ])
  engine.update_signals({"罐箱渗透率": 0.10})
  engine.get_probabilities()  # 信号驱动后概率
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.scenario")


@dataclass
class TriggerSignal:
    """触发信号：某指标达到阈值 → 调整某情景概率。"""

    name: str  # 信号名（如 罐箱渗透率）
    threshold: str  # 阈值描述（如 >15%）
    adjust: float  # 命中时对所在情景的概率调整（+0.1 等）
    condition: str = ""  # 条件描述（可选）


@dataclass
class Scenario:
    """情景定义。"""

    name: str
    base_prob: float  # 基准概率
    signals: list = field(default_factory=list)  # 该情景的触发信号
    weight: float = 0.0  # 信号调整后权重


class ScenarioEngine:
    def __init__(self, scenarios: list):
        self.scenarios = scenarios
        # 归一化基准概率
        total = sum(s.base_prob for s in scenarios)
        if total > 0:
            for s in self.scenarios:
                s.base_prob /= total
        # 初始权重 = 基准概率
        for s in self.scenarios:
            s.weight = s.base_prob

    def update_signals(self, signal_values: dict) -> dict:
        """按信号值调整各情景概率。

        signal_values: {信号名: 数值}。数值 vs 阈值 → 命中则调整。
        简易实现：信号值存在且"命中"该情景 → 概率上调（信号未定义数值时中性）。
        更精确可接 LLM 判断信号命中，此处用规则近似。
        """
        # 重置权重为基准
        for s in self.scenarios:
            s.weight = s.base_prob

        # 逐信号调整：若某情景有匹配信号，且信号值存在 → 上调该情景，下调其他
        for s in self.scenarios:
            for sig in s.signals:
                val = signal_values.get(sig.name)
                if val is not None:
                    # 信号命中（存在值即视为有信号）→ 上调该情景
                    s.weight += sig.adjust
                    # 等额下调其他情景
                    others = [x for x in self.scenarios if x is not s]
                    if others:
                        for o in others:
                            o.weight -= sig.adjust / len(others)

        # 归一化（钳制非负）
        for s in self.scenarios:
            s.weight = max(0.0, s.weight)
        total = sum(s.weight for s in self.scenarios)
        if total > 0:
            for s in self.scenarios:
                s.weight /= total

        return self.get_probabilities()

    def get_probabilities(self) -> dict:
        """返回 {情景名: 概率}。"""
        return {s.name: round(s.weight, 3) for s in self.scenarios}

    def build_prompt(self) -> str:
        """生成注入写作的触发信号说明。"""
        lines = ["=== 情景规划（触发信号驱动概率，非拍脑袋）==="]
        for s in self.scenarios:
            lines.append(f"- {s.name}: 基准概率 {s.base_prob:.0%}")
            for sig in s.signals:
                lines.append(f"  · 触发信号: {sig.name} {sig.threshold} → 上调{sig.adjust:+.0%}")
        lines.append("=== 情景结束 ===")
        return "\n".join(lines)


def oil_scenario_example() -> ScenarioEngine:
    """油位传感器场景示例。"""
    return ScenarioEngine(
        [
            Scenario(
                "乐观",
                0.30,
                [
                    TriggerSignal("罐箱渗透率", ">15%", +0.15),
                    TriggerSignal("海外订单", ">500万", +0.10),
                ],
            ),
            Scenario(
                "基准",
                0.50,
                [
                    TriggerSignal("罐箱渗透率", "5-10%", +0.05),
                ],
            ),
            Scenario(
                "悲观",
                0.20,
                [
                    TriggerSignal("政策执行率", "<5%", +0.15),
                    TriggerSignal("认证延迟", ">18月", +0.10),
                ],
            ),
        ]
    )
