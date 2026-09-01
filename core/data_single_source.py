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

    R91（2026-08-06）：上下文分组——按 单位+年份+限定词+来源 拆簇，消除跨口径误报。
    v9 事故的 40%vs50% 渗透率冲突发生在同一口径（行业整体渗透率），必须拦截；
    但不同技术路线（磁致伸缩/雷达）、不同年份、不同地域口径（全球 vs 中国）的
    数值本就不是同一指标，混为一簇会产生大量误报（油位报告渗透率 5%-95% 实为
    智能液位仪/磁致伸缩/雷达多口径并存）。分组后仅同簇多值偏差>20% 才判冲突。
    R95（2026-08-27）：引入来源标签分组——仅同一来源内的多值才判冲突。
    """
    if not text:
        return []
    issues = []
    # 来源识别模式：匹配"据/来源/基于/来自 + 实体名"
    _SOURCE_PAT = re.compile(r"(据|来源|基于|来自)\s*([^，。；\n]{2,20})")

    for label, pat in _INDICATOR_PATTERNS.items():
        matches = list(re.finditer(pat, text))
        if len(matches) < 2:
            continue
        # 分组键：unit|year|ctx|source —— 单位 + 年份 + 限定词 + 来源
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
            cal = "|CAGR" if "CAGR" in mname.upper() or "复合" in mname else ""
            ctx_text = text[max(0, m.start() - 20) : m.end() + 20]
            if any(kw in ctx_text for kw in ("十年", "复合", "CAGR", "十年复合")):
                cal = "|CAGR"
            # 来源提取：前40字内找"据/来源/基于/来自 + 实体"
            before40 = text[max(0, m.start() - 40) : m.start()]
            src_m = _SOURCE_PAT.search(before40)
            source = src_m.group(2).strip() if src_m else "unknown"
            # 来源归一化：常见别名合并
            source = _normalize_source(source)
            key = f"{unit}|{year}|{ctx}{cal}|{source}"
            groups.setdefault(key, []).append(num)
        for key, values in groups.items():
            if len(values) < 2:
                continue
            mx, mn = max(values), min(values)
            if mn > 0 and (mx - mn) / mn > tolerance:
                issues.append(f"{label}多值冲突[{key}]: {sorted(values)}（偏差>{tolerance:.0%}）")
    return issues


def _normalize_source(src: str) -> str:
    """来源归一化：常见别名合并。"""
    src = src.strip()
    aliases = {
        "公司": "公司公告",
        "年报": "年报",
        "三季报": "三季报",
        "半年报": "半年报",
        "一季报": "一季报",
        "招股书": "招股书",
        "中信": "中信证券",
        "高盛": "高盛",
        "摩根": "摩根士丹利",
        "中金": "中金公司",
        "华泰": "华泰证券",
        "国泰": "国泰君安",
        "安信": "安信证券",
        "东方财富": "东方财富",
        "同花顺": "同花顺",
        "Wind": "Wind",
        "SMM": "SMM",
        "SNE": "SNE Research",
    }
    for k, v in aliases.items():
        if k in src:
            return v
    return src


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
