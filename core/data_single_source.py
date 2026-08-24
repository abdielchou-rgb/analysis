"""关键指标单一事实源 — R82 P1 数字一致性架构。

v9 事故：渗透率 40%vs50%、份额 50%-73%、替换需求 1.2vs2.1-3.2 万套，
各章节独立生成互相矛盾。本模块：
  1. 定义关键指标（渗透率/份额/增速/市场空间/替换需求）
  2. 生成时写入前查单一事实源，矛盾拦截
  3. 供 section_writer 注入"单一事实源"约束 + Gate 一致性校验

用法：
    from core.data_single_source import validate_indicators
    issues = validate_indicators(text)  # 返回跨章节冲突
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("2hao.single_source")

# 关键指标检测模式：指标名 + 数值
_INDICATOR_PATTERNS = {
    "渗透率": r"(渗透率|覆盖率)[^。]{0,10}?(\d{1,3}(?:\.\d+)?)\s*%",
    "市场份额": r"(份额|市场占有率)[^。]{0,10}?(\d{1,3}(?:\.\d+)?)\s*%",
    "增速": r"(增速|增长率|CAGR)[^。]{0,10}?(\d{1,3}(?:\.\d+)?)\s*%",
    "替换需求": r"(替换需求|年替换|每年约)[^。]{0,10}?(\d+(?:\.\d+)?)\s*(万套|万只)",
    "市场空间": r"(市场规模|市场空间|TAM)[^。]{0,10}?(\d+(?:\.\d+)?)\s*(亿元|亿美元)",
}


def validate_indicators(text: str, tolerance: float = 0.20) -> list[str]:
    """扫描文本，检测同一关键指标的多值冲突（偏差>20%）。

    R91（2026-08-06）：上下文分组——按 单位+年份+限定词 拆簇，消除跨口径误报。
    v9 事故的 40%vs50% 渗透率冲突发生在同一口径（行业整体渗透率），必须拦截；
    但不同技术路线（磁致伸缩/雷达）、不同年份、不同地域口径（全球 vs 中国）的
    数值本就不是同一指标，混为一簇会产生大量误报（油位报告渗透率 5%-95% 实为
    智能液位仪/磁致伸缩/雷达多口径并存）。分组后仅同簇多值偏差>20% 才判冲突。
    """
    if not text:
        return []
    issues = []
    for label, pat in _INDICATOR_PATTERNS.items():
        matches = list(re.finditer(pat, text))
        if len(matches) < 2:
            continue
        # 分组键：unit|year|ctx —— 单位 + 前30字内年份 + 匹配前4字限定词
        # ctx 去数字标点，<2字视为无明确限定词（归入默认簇），保证"渗透率为40%，渗透率50%"
        # 这类同口径列举仍能被拦截；有明确限定词（磁致伸缩/雷达/中国市场等）才拆簇。
        groups: dict[str, list[float]] = {}
        for m in matches:
            try:
                num = float(m.group(2))
            except (ValueError, TypeError):
                continue
            unit = m.group(3) if m.lastindex and m.lastindex >= 3 else ""
            before30 = text[max(0, m.start() - 30) : m.start()]
            yms = re.findall(r"(20\d{2})", before30)
            year = yms[-1] if yms else ""
            raw_ctx = text[max(0, m.start() - 4) : m.start()]
            ctx_clean = re.sub(r"[\d.。，、\s%()（）]+", "", raw_ctx)
            ctx = ctx_clean if len(ctx_clean) >= 2 else ""
            # CAGR 为多年复合口径，与单年增速/增长率不同，单独成簇
            mname = m.group(1) if m.lastindex and m.lastindex >= 1 else ""
            cal = "|CAGR" if "CAGR" in mname.upper() else ""
            key = f"{unit}|{year}|{ctx}{cal}"
            groups.setdefault(key, []).append(num)
        for key, values in groups.items():
            if len(values) < 2:
                continue
            mx, mn = max(values), min(values)
            if mn > 0 and (mx - mn) / mn > tolerance:
                issues.append(f"{label}多值冲突[{key}]: {sorted(values)}（偏差>{tolerance:.0%}）")
    return issues


def single_source_prompt() -> str:
    """生成 section_writer 注入的单一事实源约束。"""
    return (
        "## [数字单一事实源] 全文关键指标必须统一：渗透率/市场份额/增速/替换需求/市场空间\n"
        "同一指标只允许一个值（来自【共享数据字典】）。若需引用不同口径，必须显式标注"
        "'口径差异：X口径Y值 vs Z口径W值'。禁止各章节自行取值导致矛盾。"
        "涉及渗透率/份额/增速等关键数字前，先查数据字典的权威值。"
    )


if __name__ == "__main__":
    test = "渗透率为40%，渗透率50%，份额65%，份额50%，增速8.7%，增速3.6%"
    issues = validate_indicators(test)
    for i in issues:
        print("冲突:", i)
    if not issues:
        print("无冲突")
