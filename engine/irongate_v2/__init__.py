"""
IronGate 2.0 — 三层分级校验系统。

层级:
- L1 (Hard Stop): 会计恒等式、结构性约束 → 失败则阻断管线
- L2 (Economic Physics): 商业/金融逻辑边界 → 失败则修正参数
- L3 (Text-Numeric Contract): 叙述与数值一致性 → 失败则报告给文本层
"""

from engine.irongate_v2.registry import GateSeverity, GateVerdict, IronGateV2

__all__ = ["IronGateV2", "GateSeverity", "GateVerdict"]
