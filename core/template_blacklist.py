"""模板句黑名单 — R79 P0-1 去模板化。

油位报告圆桌评审发现：10 个万能过渡句全报告复读 3-8 次，是 LLM 被
"每段必须有 So What 链/判断密度"逼出来的填充句。真人写作是逻辑推进，
不是套话换花样。

本模块：
  1. 维护模板句黑名单（初始 10 条，评审持续补充）
  2. scan() 扫描文本，返回命中列表
  3. 供 Style Compiler 局部重写 + IronGate _check_template_phrases 使用
"""

from __future__ import annotations

import re

# 初始黑名单（来自油位报告圆桌评审，2.1 节逐条指认）
TEMPLATE_BLACKLIST = [
    "这一趋势若被证实，将显著改变我们对行业格局的既有认知",
    "上述判断仍面临需求端波动带来的下行风险扰动",
    "这一变化同时意味着，需要重新审视此前对业务结构的增长假设",
    "从更长周期看，上述趋势若持续，盈利中枢存在系统性上移的可能",
    "后续财报中相关指标的兑现情况，将是检验上述判断真伪的试金石",
    "这一迹象提示，市场当前定价可能尚未充分反映上述逻辑的潜在弹性",
    "该类数据的边际改善，往往领先于报表层面的最终体现",
    "对上述变量保持高频跟踪，是把握后续机会的必要条件",
    "驱动因素边际拐点的确认，是后续估值重估能否成立的前提",
    "该数据背后折射出的经营质量变化，比单期数值本身更值得关注",
]

# 同义变体（短语级，用于检测改写变体）
TEMPLATE_VARIANTS = [
    r"(趋势|若).{0,6}证实",
    r"下行风险扰动",
    r"重新审视此前对业务结构的增长假设",
    r"盈利中枢存在系统性上移",
    r"判断真伪的试金石",
    r"尚未充分反映",
    r"领先于报表层面的最终体现",
    r"高频跟踪",
    r"估值重估能否成立",
    r"经营质量变化",
]


def scan(text: str) -> list[dict]:
    """扫描文本，返回命中模板句列表 [{phrase, count, positions}]。"""
    hits = []
    for phrase in TEMPLATE_BLACKLIST:
        count = text.count(phrase)
        if count > 0:
            hits.append({"phrase": phrase, "count": count})
    # 变体检测（宽松匹配，用于提示改写）
    variants_found = {}
    for pat in TEMPLATE_VARIANTS:
        matches = re.findall(pat, text)
        if len(matches) >= 2:  # 同义变体出现≥2次才报
            variants_found[pat] = len(matches)
    return {
        "exact_hits": hits,
        "variant_hits": variants_found,
        "total_exact": sum(h["count"] for h in hits),
        "total_variant": sum(variants_found.values()),
    }


# 工作过程语言黑名单（2026-08-08 升级）——AI 工具痕迹，严禁出现在严肃报告正文
# 来源：油位 v2.8 复查发现（补采/差距量化/原判断需修正/战略部/---等）
WORK_PROCESS_BLACKLIST = [
    "补采",  # "竞争对手量化对标（补采 2026-08）"
    "差距量化",  # "组织承接能力分析（差距量化）"
    "原判断",  # "原判断「...」需修正"
    "需修正",  # "需修正"
    "战略部",  # "据战略部测算"
    "数据来源说明",  # 工具痕迹
    "情景修正",  # 工具痕迹
    "口径说明",  # 工具痕迹（正文应直接写口径，不标"说明"）
    "（补采）",  # 小标题带补采
    "R87 体系",  # 内部方法论代号
    "R87",  # 内部方法论代号
    "工作台",  # 内部产品代号
    "2hao",  # 内部产品代号
    "校验通过",  # 工具痕迹
    "校验发现",  # 工具痕迹
    # "双向校验" 是财务专业术语，保留；"校验" 单字不拦（避免误伤"双向校验"）
]


def scan_work_process(text: str) -> dict:
    """扫描工作过程语言（AI 工具痕迹），返回命中列表。"""
    hits = []
    for term in WORK_PROCESS_BLACKLIST:
        count = text.count(term)
        if count > 0:
            hits.append({"term": term, "count": count})
    # 段落尾部孤立 "---"（分隔线残留，非 Markdown 标题分隔）
    line_marks = re.findall(r"^\s*---\s*$", text, re.MULTILINE)
    return {
        "exact_hits": hits,
        "line_separators": len(line_marks),
        "total": sum(h["count"] for h in hits) + len(line_marks),
        "passed": (sum(h["count"] for h in hits) + len(line_marks)) == 0,
    }


# 元评论语言黑名单（2026-08-08 根因诊断）——AI"助手姿态"：教读者怎么做/解释工作过程
# 来源：油位 v4.2 清除的 10 处（建议验证/需提示/值得关注/需要说明等）
# 与 WORK_PROCESS_BLACKLIST 的区别：前者是修改痕迹（补采/---），这是"教读者/解释过程"
METACOMMENT_BLACKLIST = [
    "建议以",  # "建议以细分行业报告进一步交叉验证"
    "建议来源为",  # "建议来源为合作方自述"
    "建议对",  # "建议对这两项做季度复核"
    "建议签署",  # "建议签署合作协议前"
    "待客户访谈",  # "待客户访谈与供应商尽调验证"
    "验证后升级",  # "验证后升级为实际值"
    "升级为实际值",  # 教读者验证
    "值得关注的是",  # AI 口癖
    "需提示的",  # AI 口癖
    "需要说明",  # 解释工作过程
    "需评估",  # 元评论
    "可考虑",  # AI 口癖
    "建议以客户访谈",  # 教读者
    "可直接调取",  # 教读者尽调
    "本方案测算主体为",  # 元评论（原文"本方案测算主体为本公司主导"）
]


def scan_metacomment(text: str) -> dict:
    """扫描元评论语言（AI 助手姿态），返回命中列表。"""
    hits = []
    for term in METACOMMENT_BLACKLIST:
        count = text.count(term)
        if count > 0:
            hits.append({"term": term, "count": count})
    return {
        "exact_hits": hits,
        "total": sum(h["count"] for h in hits),
        "passed": sum(h["count"] for h in hits) == 0,
    }


def rewrite_suggestions(text: str) -> str:
    """对命中的模板句生成改写提示（返回带标记的文本，供局部重写）。"""
    result = text
    for phrase in TEMPLATE_BLACKLIST:
        if phrase in result:
            # 标记模板句，供 LLM 局部重写
            result = result.replace(phrase, f"【TEMPLATE_REWRITE:{phrase[:20]}】")
    return result


if __name__ == "__main__":
    test_text = (
        "这一趋势若被证实，将显著改变我们对行业格局的既有认知。"
        "上述判断仍面临需求端波动带来的下行风险扰动。"
        "这一趋势若被证实，将显著改变我们对行业格局的既有认知。"
    )
    r = scan(test_text)
    print("exact hits:", r["exact_hits"])
    print("total:", r["total_exact"])
    print("rewrite:", rewrite_suggestions(test_text))
