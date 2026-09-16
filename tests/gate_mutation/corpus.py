"""R1 黄金缺陷语料库 — 用"已知缺陷"反查 IronGate 的真实检出力。

## 为什么需要它

IronGate 有 105 项检查，"全部通过"是常态。但**通过率 100% 只能证明
检查项没有报错，不能证明它们能抓到东西**。门禁的价值不在"它跑完了"，
而在"该拦的它拦住了"。要量化的指标是：

    TPR(check) = 被该检查抓到的缺陷数 / 注入给它的缺陷数

这正是变异测试（mutation testing）在静态分析领域的用法——
Park & Choi 指出静态分析器必须报告**漏报（false negative）**，
否则"无告警"会被误读成"无缺陷"。

## 为什么用"差分"而不是"绝对阈值"

本项目的 golden 样本（tests/golden/gas_sensor_cicc.md，6917 字）本身
就过不了门禁（0.771 < 0.78），26 项检查在基线上就是红的——因为样本是
截断的。若用"变异体必须让检查变红"作判据，这些检查会全部假通过。

因此判据是**相对基线的变化量**：

    killed ⟺ score(变异体) - score(基线) 的方向与预期一致且幅度 ≥ EPS

同时处理**饱和**：若基线已是满分（"rise" 方向）或零分（"drop" 方向），
该变异体在数学上不可能被检出，记为 N/A 而非失败——否则会把"检查项已经
在最严状态"误判成"检查项失灵"。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

# 方向常量
DROP = "drop"  # 注入缺陷 → 期望分数下降
RISE = "rise"  # 注入合规内容 → 期望分数上升
HOLD = "hold"  # 注入**不是缺陷**的内容 → 期望检查项保持安静（不误报）


# 变异体分层——这个区分是整个 R1 的结论所在：
#
#   PATTERN：照着检查项**自己实现的检测模式**构造（读源码/文档字符串得到）。
#            它回答"这个检查项到底工不工作"。漏检 = 检查项坏了。
#   NATURAL：照着**真人评审会挑出来的毛病**构造，不管检查项怎么实现。
#            它回答"门禁能不能守住真实质量"。漏检 = 门禁有盲区
#            （检查项可能"正常工作"，只是它枚举的模式没覆盖这类缺陷）。
#   BENIGN ：注入**正确、无害**的内容。它回答"检查项会不会乱叫"。
#            误报率 FPR = 1 − 保持安静的比例。
#
# 只报一个 TPR 会把前两者混为一谈：要么冤枉检查项，要么放过盲区。
# 不报 FPR 则无法回答"门禁报的红灯有多少是真的"——TPR 单独没有意义，
# 必须和 FPR 配对（正如敏感度和特异度必须配对）。
PATTERN = "pattern"
NATURAL = "natural"
BENIGN = "benign"


@dataclass(frozen=True)
class Mutant:
    """一个"已知缺陷"（或其解药）。"""

    id: str
    target: str  # 目标检查项名（GateCheckResult.name）
    direction: str  # DROP / RISE
    tier: str  # PATTERN / NATURAL
    desc: str
    apply: Callable[[str], str]

    def __hash__(self) -> int:
        return hash(self.id)


# ── 复用小工具 ──────────────────────────────────────────────

_TAIL = "\n"


def _append(text: str, block: str) -> str:
    return text + _TAIL + block


def _strip_sources(text: str) -> str:
    """去掉全部（来源：…）/ [En] / [注N] 标注。"""
    text = re.sub(r"（来源[^）]*）", "", text)
    text = re.sub(r"\(来源[^)]*\)", "", text)
    text = re.sub(r"\[E\d+\]", "", text)
    text = re.sub(r"\[注\d+\]", "", text)
    return text


def _strip_images(text: str) -> str:
    return re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)


def _strip_tables(text: str) -> str:
    """去掉 markdown 表格（连续的 | 开头的行块）。"""
    out, skipping = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            if not skipping:
                skipping = True
            continue
        skipping = False
        out.append(line)
    return "\n".join(out)


_TEMPLATE_PHRASES = (
    "这一趋势若被证实，将显著改变我们对行业格局的既有认知",
    "上述判断仍面临需求端波动带来的下行风险扰动",
    "这一变化同时意味着，需要重新审视此前对业务结构的增长假设",
    "从更长周期看，上述趋势若持续，盈利中枢存在系统性上移的可能",
)

_MOJIBAKE = "æµæ±è§çº¤ç»´å¢éå‰‚å¸‚åœºè§„æ¨¡"

_CROSS_INDUSTRY = (
    "## 补充：动力电池产业链参照\n\n"
    "参考宁德时代与比亚迪的动力电池装机量数据，2025年全球动力电池装机量达"
    "1.2TWh，碳酸锂价格从60万元/吨回落至8万元/吨，正极材料环节产能利用率分化明显。"
    "动力电池的能量密度提升路径与气体传感器的灵敏度提升路径存在技术同构性。\n"
)

# ── 语料库 ──────────────────────────────────────────────────
#
# 覆盖三类缺陷：
#   A. 格式/卫生类（占位符、乱码、MD 残片）——应该 100% 抓到，抓不到就是检查项失灵
#   B. 数值/逻辑类（算术错、口径冲突、跨行业污染）
#   C. 内容充分性类（缺证伪、缺决策门、缺来源）——用"补上合规内容分数应上升"来验

MUTANTS: list[Mutant] = [
    # ══════════ TIER 1：PATTERN —— 照检查项自己实现的模式构造 ══════════
    # 漏检 = 检查项本身坏了（或模式从未生效）
    Mutant(
        "placeholder_xxx",
        "placeholder_xxx",
        DROP,
        PATTERN,
        "未替换占位符 XXX / TODO（检查项明确列举的模式）",
        lambda t: _append(t, "本段关键数据 XXX 待填写，TODO 后续补采。"),
    ),
    Mutant(
        "gbk_encoding",
        "gbk_encoding",
        DROP,
        PATTERN,
        "GBK mojibake 乱码（U+FFFD / 拉丁扩展+CJK 形态）",
        lambda t: _append(t, f"出口数据显示：{_MOJIBAKE}（来源：海关总署）"),
    ),
    Mutant(
        "md_artifacts_odd_fence",
        "md_artifacts",
        DROP,
        PATTERN,
        "代码块围栏 ``` 数量为奇数（检查项明确检测项 1）",
        lambda t: _append(t, "```python\nprint('unclosed')\n"),
    ),
    Mutant(
        "md_artifacts_stray_tick",
        "md_artifacts",
        DROP,
        PATTERN,
        "孤立单反引号（检查项明确检测 stray_backticks）",
        lambda t: _append(t, "此处有一个孤立的反引号 ` 未被配对。"),
    ),
    Mutant(
        "completeness_scan_year_trunc",
        "completeness_scan",
        DROP,
        PATTERN,
        "年份截断『2025-202』（检查项明确检测项 3）",
        lambda t: _append(t, "产能扩张节奏：2025-202 期间新增产线 12 条，对应年产能 800 万只。"),
    ),
    Mutant(
        "completeness_scan_short_para",
        "completeness_scan",
        DROP,
        PATTERN,
        "段落末词截半、无标点结尾（检查项明确检测项 6）",
        lambda t: _append(t, "综上，国产替代的推进节奏取决于车规认证的实际"),
    ),
    Mutant(
        "template_phrases",
        "template_phrases",
        DROP,
        PATTERN,
        "注入 4 条模板黑名单原句（≥4 应为 error）",
        lambda t: _append(t, "\n".join(f"- {p}。" for p in _TEMPLATE_PHRASES)),
    ),
    Mutant(
        "report_date",
        "report_date",
        RISE,
        PATTERN,
        "补上『报告日期：YYYY年MM月』（检查项就找这一个串）",
        lambda t: _append(t, "报告日期：2026年09月14日"),
    ),
    Mutant(
        "csrc_compliance_all5",
        "csrc_compliance",
        RISE,
        PATTERN,
        "补齐 CSRC 五要件（评级定义/利益冲突/重要提示/不构成建议/分析师资格）",
        lambda t: _append(
            t,
            "## 评级定义与说明\n\n| 评级 | 定义 |\n|---|---|\n| 买入 | 预期涨幅 >20% |\n"
            "| 增持 | 预期涨幅 5%-20% |\n| 中性 | 预期涨幅 -5%-5% |\n\n"
            "## 利益冲突披露\n\n本报告分析师不持有该标的，与研究标的无利益冲突。\n\n"
            "## 重要提示\n\n本报告基于公开信息编制。\n\n"
            "## 免责声明\n\n本报告不构成任何投资建议，不保证收益，过往业绩不代表未来表现。\n\n"
            "## 分析师资格认证\n\n本报告分析师持有 SAC 执业资格，登记编号 S1230512000001。",
        ),
    ),
    Mutant(
        "arithmetic_audit_share",
        "arithmetic_audit",
        DROP,
        PATTERN,
        "占比反算错误：318.29万股/总股本 称 0.24%（实为 1.13%，柯力案原形）",
        lambda t: _append(
            t,
            "北向资金持有 318.29万股，占总股本约0.24%（基于总市值131.23亿元、股价46.73元）。",
        ),
    ),
    Mutant(
        "chart_density",
        "图表密度",
        DROP,
        PATTERN,
        "删除全部图片嵌入（图表计数直接归零）",
        _strip_images,
    ),
    Mutant(
        "content_volume",
        "content_volume",
        DROP,
        PATTERN,
        "截断至 3000 字（远低于 10420 字门槛）",
        lambda t: t[:3000],
    ),
    Mutant(
        "core_hypothesis",
        "core_hypothesis",
        RISE,
        PATTERN,
        "补上『核心假设/可证伪/先行指标』三要素",
        lambda t: _append(
            t,
            "核心假设：国产气体传感器将在2027年实现高端车规突破。若该假设成立，"
            "先行指标为车规认证通过厂商数量与头部厂商研发投入占比；若2026年底"
            "车规认证厂商仍为 0，则假设被证伪。",
        ),
    ),
    Mutant(
        "decision_gate",
        "决策门判断",
        RISE,
        PATTERN,
        "补上决策门（时间 + 触发条件 + 动作）",
        lambda t: _append(
            t,
            "决策门：2026Q4 前若国产化率突破 25% 且头部厂商在手订单同比 >30%，"
            "则上调行业评级至增持；否则维持中性并等待 2027Q1 数据。",
        ),
    ),
    # ══════════ TIER 2：NATURAL —— 真人评审会挑出的毛病 ══════════
    # 漏检 = 门禁盲区（检查项可能正常工作，只是枚举的模式没覆盖）
    Mutant(
        "md_artifacts_unclosed_bold",
        "md_artifacts",
        DROP,
        NATURAL,
        "未闭合的加粗标记 **（常见 LLM 输出残片，检查项未枚举）",
        lambda t: _append(t, "**这是一个未闭合的加粗标记，后面没有收尾"),
    ),
    Mutant(
        "personal_narrative",
        "personal_narrative",
        DROP,
        NATURAL,
        "第一人称个人化叙述（研报不该有）",
        lambda t: _append(t, "我记得小时候家里用的就是这种传感器，那时候总觉得它不太灵敏。"),
    ),
    Mutant(
        "semantic_dedup",
        "semantic_dedup",
        DROP,
        NATURAL,
        "整段 40 行复制粘贴造成语义重复",
        lambda t: _append(t, "\n".join(t.splitlines()[:40])),
    ),
    Mutant(
        "arithmetic_audit_growth",
        "arithmetic_audit",
        DROP,
        NATURAL,
        "增长率算错：100→300 说成『同比增长 50%』（实为 200%）",
        lambda t: _append(t, "据测算，2023年营收为100亿元，2024年营收为300亿元，同比增长50%。"),
    ),
    Mutant(
        "numeric_chain_cagr",
        "numeric_chain_consistency",
        DROP,
        NATURAL,
        "复合增速与首末值不自洽：100→121 两年 却称 45%",
        lambda t: _append(
            t,
            "全球市场规模：2023年为100.0亿美元，2025年为121.0亿美元，据此三年复合增长率为45.0%。",
        ),
    ),
    Mutant(
        "data_conflicts",
        "data_conflicts",
        DROP,
        NATURAL,
        "同一指标（营收）自相矛盾：100亿 vs 500亿",
        lambda t: _append(t, "补充口径：公司2023年营收为500.0亿元（来源：年报），与前述100.0亿元存在差异。"),
    ),
    Mutant(
        "market_size_consistency",
        "market_size_consistency",
        DROP,
        NATURAL,
        "市场规模出现第三个口径，偏差 >20%",
        lambda t: _append(t, "另据第三方口径，全球市场规模（2023年）为85.0亿美元。"),
    ),
    Mutant(
        "cross_industry_contamination",
        "cross_industry_contamination",
        DROP,
        NATURAL,
        "气体传感器报告注入动力电池/宁德时代内容",
        lambda t: _append(t, _CROSS_INDUSTRY),
    ),
    Mutant(
        "invariant_audit_share_sum",
        "invariant_audit",
        DROP,
        NATURAL,
        "份额之和 ≠ 100%（45+40+35+10 = 130%）",
        lambda t: _append(
            t,
            "竞争格局：甲公司份额 45%，乙公司份额 40%，丙公司份额 35%，其余厂商合计 10%。",
        ),
    ),
    Mutant(
        "invariant_audit_float_gt_total",
        "invariant_audit",
        DROP,
        NATURAL,
        "流通市值 > 总市值（物理不可能）",
        lambda t: _append(t, "估值口径：公司总市值约131.23亿元，流通市值约136.70亿元。"),
    ),
    Mutant(
        "business_logic",
        "business_logic",
        DROP,
        NATURAL,
        "声称价值巨大但拒绝量化",
        lambda t: _append(t, "该技术路线价值巨大、意义深远，但此处无法量化，也不宜给出具体数字。"),
    ),
    Mutant(
        "source_entity",
        "source_entity",
        DROP,
        NATURAL,
        "来源退化成无实体（『据某权威机构测算』）",
        lambda t: _append(t, "补充：据某权威机构测算，2026年出货量同比增长约三成。"),
    ),
    Mutant(
        "data_traceability",
        "data_traceability",
        DROP,
        NATURAL,
        "剥离全部来源标注",
        _strip_sources,
    ),
    Mutant(
        "inline_citations",
        "inline_citations",
        DROP,
        NATURAL,
        "关键数字去掉 [En]/[注N] 内嵌引用",
        _strip_sources,
    ),
    Mutant(
        "falsification_conditions",
        "falsification_conditions",
        RISE,
        NATURAL,
        "补上可证伪条件",
        lambda t: _append(
            t,
            "证伪条件：若2027年国产化率未突破30%，或头部厂商毛利率连续两个季度低于25%，"
            "则上述 Bold Call 判断不成立。",
        ),
    ),
    Mutant(
        "explicit_conclusion",
        "explicit_conclusion",
        RISE,
        NATURAL,
        "补上明确结论（行业评级 + 受益环节 + 核心判断）",
        lambda t: _append(
            t,
            "结论：我们给予气体传感器行业**增持**评级，核心受益环节为**MEMS 芯片与封装**，"
            "核心判断是国产替代将在 2027 年进入高端车规放量期。",
        ),
    ),
    Mutant(
        "esg_materiality",
        "esg_materiality",
        RISE,
        NATURAL,
        "补上 ESG 实质性议题与估值影响",
        lambda t: _append(
            t,
            "ESG 实质性议题：本行业最实质的是生产环节的挥发性有机物排放（E）与"
            "车规安全责任（S）；其对估值的影响为折价约 3%-5%，已纳入 DCF 假设。",
        ),
    ),
    Mutant(
        "industry_consolidation",
        "industry_consolidation",
        RISE,
        NATURAL,
        "补上行业并购整合趋势与终局判断",
        lambda t: _append(
            t,
            "## 行业整合\n\n2024-2026 年行业并购 12 起，平均交易倍数 2.8x PS、18x PE，"
            "整合趋势明确；终局判断为 CR5 从 38% 提升至 55%，二三线厂商将被并购或退出。",
        ),
    ),
    Mutant(
        "geopolitical_depth",
        "geopolitical_depth",
        RISE,
        NATURAL,
        "补上中美竞争传导链量化",
        lambda t: _append(
            t,
            "地缘维度：若美国将 MEMS 芯片纳入出口管制清单，国产厂商高端产能爬坡将延迟 "
            "6-9 个月，对应 2027 年国产化率预测由 35% 下修至 28%，传导至行业增速为 -2.1pp。",
        ),
    ),
    Mutant(
        "attribution_depth",
        "attribution_depth",
        RISE,
        NATURAL,
        "补上多因子归因链（3+ Factor + CausalChain）",
        lambda t: _append(
            t,
            "归因：Factor1=车规认证进度（权重 0.35）；Factor2=上游硅片价格（权重 0.25）；"
            "Factor3=整车厂国产化意愿（权重 0.40）；SubFactor=认证周期由 18 个月缩短至 11 个月；"
            "CausalChain=认证提速 → 定点车型增加 → 出货量上修 → 毛利率改善。",
        ),
    ),
    Mutant(
        "annotation_types",
        "annotation_types",
        RISE,
        NATURAL,
        "补上 A/E/F/B 多类型标注（需 ≥3 种含 A）",
        lambda t: _append(
            t,
            "标注校验段：绝对量 120.0 [A1]；估算值 15.3 [E1]；预测值 22.8 [F1]；基准值 9.6 [B1]。",
        ),
    ),
    Mutant(
        "risk_layering",
        "risk_layering",
        RISE,
        NATURAL,
        "补上尾部风险层（四层框架缺 tail）",
        lambda t: _append(
            t,
            "## 尾部风险\n\n若主要客户整车厂因安全事故大规模召回，或上游稀土材料出口管制升级，"
            "行业需求可能在两个季度内下滑 30% 以上，此情形发生概率约 5%。",
        ),
    ),
    Mutant(
        "counterargument_strength",
        "counterargument_strength",
        RISE,
        NATURAL,
        "补上反方论证段落",
        lambda t: _append(
            t,
            "## 反方论证\n\n反对意见认为：国产替代更多发生在中低端，高端仍由博世、"
            "盛思锐主导；若下游汽车销量不及预期，需求端支撑将被证伪。"
            "我们对此的反驳是：中低端放量是高端突破的必要条件，且已有两家厂商通过车规认证。",
        ),
    ),
    Mutant(
        "meta_cognition",
        "meta_cognition",
        RISE,
        NATURAL,
        "补上置信度与盲点声明",
        lambda t: _append(
            t,
            "元认知：本判断置信度 68%；已知盲点为下游整车厂实际定点节奏未获一手验证，"
            "若该数据可得，置信度可上修至 80%。",
        ),
    ),
    Mutant(
        "table_density",
        "table_density",
        DROP,
        NATURAL,
        "删除全部 markdown 表格",
        _strip_tables,
    ),
    Mutant(
        "chart_completeness",
        "chart_completeness",
        DROP,
        NATURAL,
        "删除全部图片嵌入（应报图缺失）",
        _strip_images,
    ),

    # ══════════ TIER 3：BENIGN —— 注入**正确无害**的内容 ══════════
    # 期望：检查项保持安静。它若响了就是误报。
    # 这一层度量 FPR——没有它，TPR 单独无法回答"红灯里有多少是真的"。
    Mutant(
        "benign_arithmetic_correct_share",
        "arithmetic_audit",
        HOLD,
        BENIGN,
        "占比**算对了**的声明（318.29万/2.81亿=1.13%），不应报警",
        lambda t: _append(
            t, "北向资金持有 318.29万股，占总股本约1.13%（基于总股本2.81亿股）。"
        ),
    ),
    Mutant(
        "benign_cagr_correct",
        "numeric_chain_consistency",
        HOLD,
        BENIGN,
        "复合增速**算对了**（100→121 两年 = 10.0%），不应报警",
        lambda t: _append(
            t,
            "全球市场规模：2023年为100.0亿美元，2025年为121.0亿美元，据此两年复合增长率为10.0%。",
        ),
    ),
    Mutant(
        "benign_share_sum_100",
        "invariant_audit",
        HOLD,
        BENIGN,
        "份额之和恰好 100%（45+40+15），不应报警",
        lambda t: _append(t, "竞争格局：甲公司份额 45%，乙公司份额 40%，其余厂商合计 15%。"),
    ),
    Mutant(
        "benign_market_size_same",
        "market_size_consistency",
        HOLD,
        BENIGN,
        "同口径重述同一市场规模（28.6），不是第三口径，不应报警",
        lambda t: _append(
            t, "口径说明：前述全球市场规模（2023年）28.6亿美元，与行业协会口径一致。"
        ),
    ),
    Mutant(
        "benign_revenue_consistent",
        "data_conflicts",
        HOLD,
        BENIGN,
        "同值重述营收（100.0亿元），不是冲突，不应报警",
        lambda t: _append(t, "口径说明：公司2023年营收为100.0亿元（来源：年报），与前述口径一致。"),
    ),
    Mutant(
        "benign_standard_disclaimer",
        "template_phrases",
        HOLD,
        BENIGN,
        "标准免责声明（非黑名单模板句），不应报警",
        lambda t: _append(
            t,
            "## 免责声明\n\n本报告基于公开信息编制，仅供研究参考。"
            "分析师声明：本报告署名分析师未持有该标的。"
            "本报告所载信息来源于公开资料，我们不对其准确性作任何保证。",
        ),
    ),
    Mutant(
        "benign_wellformed_appendix",
        "completeness_scan",
        HOLD,
        BENIGN,
        "格式完整、句末有标点的附录段，不应报截断",
        lambda t: _append(
            t,
            "## 附录：术语表\n\n"
            "MEMS：微机电系统，指将机械结构与电子电路集成于同一芯片的技术。\n\n"
            "车规认证：汽车零部件满足 AEC-Q100 等可靠性标准的过程。\n\n"
            "以上术语释义用于统一本报告口径，不涉及新增判断。",
        ),
    ),
    Mutant(
        "benign_wellformed_table",
        "md_artifacts",
        HOLD,
        BENIGN,
        "管道符对齐、闭合完整的表格，不应报残片",
        lambda t: _append(
            t,
            "| 环节 | 2023年 | 2024年 | 2025年E |\n"
            "|---|---:|---:|---:|\n"
            "| MEMS 芯片 | 12.4 | 15.1 | 18.6 |\n"
            "| 封装测试 | 8.2 | 9.4 | 11.0 |\n"
            "| 模组集成 | 21.7 | 25.3 | 29.8 |",
        ),
    ),
    Mutant(
        "benign_named_source",
        "source_entity",
        HOLD,
        BENIGN,
        "具名实体的来源标注，不应报『无实体来源』",
        lambda t: _append(
            t,
            "补充：据国家统计局《中国统计年鉴2025》口径，"
            "2024年国内气体传感器产量同比增长约一成（来源：国家统计局）。",
        ),
    ),
]


# ── 已知盲区登记册 ──────────────────────────────────────────
#
# 这里是**结论**，不是待办清单的托辞：逐条抽样复核过，确认检查项本身在工作
# （例如 data_traceability 在最小样本上 1.00→0.00 正常响应、cross_industry_
# contamination 1.00→0.80 正常响应），只是它们枚举的模式没覆盖这一类缺陷。
# 换句话说：这些是"枚举式检查"的结构性盲区，不是能靠调参修掉的 bug。
#
# 登记在此的变异体在 CI 中标记为 xfail：
#   · 保持 CI 绿——不做"要么改代码要么删用例"的二选一
#   · 一旦有人把检查项升级为不变量式（R3），该用例会 XPASS，盲区被自动关闭
#
# 但 xfail 有个致命副作用：**它会让盲区永久化**。一条 xfail 挂三年没人管，
# 和删掉这条用例没有区别——都是"缺陷已知、永不修复"。所以每条盲区必须带
# 两个字段，缺一不可：
#
#   owner  —— 责任域（谁该修）。没有 owner 的登记项只是注释。
#   retire —— 退役日期。到期后 test_blind_spots_are_not_stale 会**变红**，
#             逼迫重新评估：要么修好（转 XPASS 自动关闭），要么换一份
#             更长的论证续期。续期不是免费的——必须改写 action 字段说明
#             这次续期比上次多知道了什么。
#
# 这是从"登记"变成"债务台账"的关键一步：台账有账期，登记没有。


@dataclass(frozen=True)
class BlindSpot:
    id: str
    reason: str  # 为什么它现在是盲区（根因，不是现象）
    owner: str  # 责任域
    retire: str  # 退役日期 YYYY-MM-DD，到期 CI 变红
    action: str  # 关闭它需要的最小动作（不是"优化检查项"这种空话）

    def days_left(self, today: str) -> int:
        from datetime import date

        y, m, d = (int(x) for x in today.split("-"))
        ry, rm, rd = (int(x) for x in self.retire.split("-"))
        return (date(ry, rm, rd) - date(y, m, d)).days


# 责任域划分——按检查项所属的能力域，不是按文件
OWNER_NUMERICS = "numerics"  # 数值一致性：口径、单位、守恒
OWNER_STRUCTURE = "structure"  # 结构与格式：Markdown、模板、篇幅
OWNER_ARGUMENT = "argument"  # 论证质量：出处、证伪、结论
OWNER_STYLE = "style"  # 文风与叙事：人味、重复

BLIND_SPOT_REGISTRY: dict[str, BlindSpot] = {
    b.id: b
    for b in (
        # ── 数值一致性域 ───────────────────────────────────────
        BlindSpot(
            "numeric_chain_cagr",
            "检查项只验'已声明的'链条（如'三年CAGR为X'这类显式断言），不验隐含链",
            OWNER_NUMERICS,
            "2026-10-15",
            "把'连续三年数值列'本身当作一条待验链条：任意两期应满足单调性与量级自洽，"
            "不要求报告显式写出增长率",
        ),
        BlindSpot(
            "invariant_audit_share_sum",
            "份额守恒只在'份额'与'合计'同句出现时校验，跨句/跨段落不聚合",
            OWNER_NUMERICS,
            "2026-10-15",
            "做一次'份额实体'抽取：把全文形如'X份额N%'的三元组收集起来再判和，"
            "而不是逐句正则",
        ),
        BlindSpot(
            "invariant_audit_float_gt_total",
            "流通市值 > 总市值 这条不变量未列入检查项的不变量表",
            OWNER_NUMERICS,
            "2026-10-15",
            "往不变量表加一条 float_mktcap <= total_mktcap；这是一行配置不是算法",
        ),
        BlindSpot(
            "arithmetic_audit_growth",
            "只验'占比/中值/目标价/CAGR桥'四类已枚举算式，不验裸增长率",
            OWNER_NUMERICS,
            "2026-11-15",
            "把'同比/环比增长X%'视为可验算式：反推基期值并比对文中出现的基期数",
        ),
        BlindSpot(
            "market_size_consistency",
            "基线样本已满载同类冲突，分数钉死在底部，差分不可测",
            OWNER_NUMERICS,
            "2026-12-31",
            "换一个干净的基线样本（非截断的完整报告）重测，先排除测量问题再谈检查项",
        ),
        BlindSpot(
            "data_conflicts",
            "同 market_size_consistency：基线已满载，差分判据失效",
            OWNER_NUMERICS,
            "2026-12-31",
            "同上——随基线样本替换一并复测",
        ),
        # ── 结构与格式域 ──────────────────────────────────────
        BlindSpot(
            "md_artifacts_unclosed_bold",
            "残片形态按'已枚举清单'匹配，未闭合加粗（**…）不在清单内",
            OWNER_STRUCTURE,
            "2026-10-15",
            "改用 Markdown 解析器统计未配对的 emphasis token，而非正则枚举形态",
        ),
        BlindSpot(
            "completeness_scan_short_para",
            "只对已枚举的截断形态（如年份被切）敏感，'段落过短'不在枚举内",
            OWNER_STRUCTURE,
            "2026-11-15",
            "增加'段落长度分布'不变量：低于中位数 1/3 的段落计数",
        ),
        BlindSpot(
            "table_density",
            "基线中不存在该检查项——名称不匹配，可能是未注册的幽灵检查",
            OWNER_STRUCTURE,
            "2026-10-15",
            "核对 iron_gate 注册表：若确实未注册，按 R6 处理（要么注册要么删除）",
        ),
        # ── 论证质量域 ────────────────────────────────────────
        BlindSpot(
            "source_entity",
            "实体化判定口径窄：只认'机构名+年份'式标注",
            OWNER_ARGUMENT,
            "2026-11-15",
            "放宽为'可追溯来源'判定：文件名/统计表名/法规名均可，不强制机构+年份",
        ),
        BlindSpot(
            "data_traceability",
            "检查项本身正常（1.00→0.00），但基线已 0.93，差分被压缩到不可见",
            OWNER_ARGUMENT,
            "2026-12-31",
            "随基线样本替换重测；若重测后仍盲，才是真盲区",
        ),
        BlindSpot(
            "inline_citations",
            "同 data_traceability：基线已高分，注入缺陷后分数无下行空间",
            OWNER_ARGUMENT,
            "2026-12-31",
            "同上",
        ),
        BlindSpot(
            "cross_industry_contamination",
            "检查项正常（1.00→0.80），但基线已因同类问题扣分，Δ 被吃掉",
            OWNER_ARGUMENT,
            "2026-12-31",
            "同上；另外考虑改用'绝对判据'（变异体必须让检查项变红）配合干净基线",
        ),
        BlindSpot(
            "falsification_conditions",
            "评分不随证伪条件文本变化——计分逻辑未真正读取注入内容",
            OWNER_ARGUMENT,
            "2026-11-15",
            "先确认这条不是'计分逻辑与检测逻辑脱钩'的 bug——若是 bug 则按 A 类缺陷修",
        ),
        BlindSpot(
            "explicit_conclusion",
            "需'行业评级/受益环节/核心判断'三词全中才计分，缺一即 0",
            OWNER_ARGUMENT,
            "2026-11-15",
            "改为加权计分（三选二给部分分），或把判定阈值写进文档让人可预期",
        ),
        BlindSpot(
            "annotation_types",
            "基线已 0 分，且需 ≥3 类含 A 类才计分——双重门槛",
            OWNER_ARGUMENT,
            "2026-12-31",
            "随基线样本替换重测",
        ),
        BlindSpot(
            "business_logic",
            "需'双价格带/口径冲突'等已枚举形态才命中",
            OWNER_ARGUMENT,
            "2026-11-15",
            "补充'量价背离''毛利与售价同向但成本反向'等形态；接受这是持续扩充项",
        ),
        # ── 文风与叙事域 ──────────────────────────────────────
        BlindSpot(
            "personal_narrative",
            "需第一人称+生活化词汇组合才命中，单一信号不触发",
            OWNER_STYLE,
            "2026-11-15",
            "单信号也应给低分而非零分：把'与'改成'或'并分层计分",
        ),
        BlindSpot(
            "semantic_dedup",
            "相似度阈值高于整段复制的实测相似度——阈值定得比分不出重复还高",
            OWNER_STYLE,
            "2026-10-15",
            "这不是盲区是**阈值错误**：用已知重复样本标定阈值，而不是拍脑袋",
        ),
    )
}

#: 兼容旧接口：只关心"是不是盲区"的调用方继续用这个
KNOWN_BLIND_SPOTS: frozenset[str] = frozenset(BLIND_SPOT_REGISTRY)

# 已登记误报（BENIGN 层注入了正确内容却报警）。目前为空——实测 FPR = 0.0%。
# 一旦出现误报，必须登记在此并给 owner/retire，否则 CI 直接红。
KNOWN_FALSE_ALARMS: dict[str, BlindSpot] = {}
