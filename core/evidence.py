"""V50+ EvidenceLevel — L0 added for computed/deterministic values"""

from __future__ import annotations
from enum import Enum


class EvidenceLevel(str, Enum):
    """证据等级 —— 扩展为 7 级，新增 L0（计算确定性数字）

    原始框架 L1-L7（V24），优化后：
    L0 = 计算确定 (computed) — 从API抓取并经过确定性Python计算得出的数字
    L1 = 财报/官方披露 (filing)
    L2 = 媒体/第三方 (media)
    L3 = 基于模型的估算 (estimate)
    L4 = 分析师调研 (analyst)
    L5 = 从已知推导的合理推论 (inference)
    L9 = 数据缺口 (pending)

    关键区别：
    - L0 和 L1 在读者眼中看起来可能都是"数字"，但 L0 是可精确复现的，
      L1 是财报原文。Liar's Dividend 的核心是区分这两者。
    - 报告正文中对 L0 数字的表述应是"数据引擎计算得出"而非"据年报"
    """
    COMPUTED = "L0_computed"
    FILING = "L1_filing"
    MEDIA = "L2_media"
    ESTIMATE = "L3_estimate"
    ANALYST = "L4_analyst"
    INFERENCE = "L5_inference"
    PENDING = "L9_pending"
