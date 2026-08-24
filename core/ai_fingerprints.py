"""V51 L1-3 反 AI 指纹库 — 分三级管理 + 3 项正面人感增强检测

P0 级（12 项）：报告中出现即视为质量事故，自动切除
P1 级（18 项）：降低 AI 痕迹，建议替换，记录偏差
正面人感增强（3 项）：检测报告是否具备"人类资深分析师"的特征

FP4 设计原则：
  去 AI 化不是"检查 AI 痕迹并移除"（负面检查）
  而是"让人读起来像资深分析师写的"（正面认证）
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# 指纹定义
# ═══════════════════════════════════════════════════════════════

@dataclass
class FingerprintDef:
    id: str = ""
    pattern: str = ""
    description: str = ""
    replacement: str = ""
    level: str = "P0"  # P0 | P1 | P2


P0_FINGERPRINTS = [
    FingerprintDef("P0-01", r"值得注意的是[，。,\.]?", "引出观点引导词，AI最常用", "", "P0"),
    FingerprintDef("P0-02", r"从某种程度上说[，。]?", "试图保持谨慎但变得模糊", "", "P0"),
    FingerprintDef("P0-03", r"综上所述[，。]?", "段落/章节结尾总结引导词", "", "P0"),
    FingerprintDef("P0-04", r"不可否认的是[，。]?", "试图平衡观点", "", "P0"),
    FingerprintDef("P0-05", r"在[当今当前近年来][，。\s]", "文章开头背景铺垫，万能开头", "", "P0"),
    FingerprintDef("P0-06", r"随着[^，。]{3,20}的不断发展[，。深化]", "万能背景句", "", "P0"),
    FingerprintDef("P0-07", r"众所周知[，。]?", "引出常识性陈述，跳过论证", "", "P0"),
    FingerprintDef("P0-08", r"不言而喻[，。]?", "跳过论证", "", "P0"),
    FingerprintDef("P0-09", r"具有重要意义[，。深远影响]", "空洞评价", "", "P0"),
    FingerprintDef("P0-10", r"在一定程度上[某种意义上][，。]?", "模糊限定", "", "P0"),
    FingerprintDef("P0-11", r"总体而言[整体来看][，。]?", "段落总结引导词", "", "P0"),
    FingerprintDef("P0-12", r"需要指出的是[，。]?", "补充说明引导词", "", "P0"),
]

    # ── 语义级 P0 指纹（v3.0 FP4 补充）──
    # 不依赖特定短语，检测 AI 写作的结构性特征
    # 设计原则：人类分析师不会犯的"过于完美"的错误
    
    # P0-13: 段落长度方差过低（AI 倾向于写等长段落）
    # 实现: 启用了下面 register_semantic_checks 中的段落长度检测
    
    # P0-14: 完美三列举（"首先…其次…再次…" + 等长+ 等结构）
    # 实现: 检查 "首先"、"其次"、"再次"、"最后" 是否连续出现
    
    # P0-15: 无转折段落（全文没有"但是/然而/不过"开头的段落）
    # 实现: 如果超过 5 段且无一段以转折词开头
    
    # P0-16: 每段结尾都是总结句（"综上所述/因此/总之/所以"）
    # 实现: 如果 >80% 的段落以总结词结尾
    
    # P0-17: 完美结构套嵌（数据→分析→结论 三段式每段精确匹配）
    # 实现: 如果 >70% 的段落同时包含数据+分析+结论三种元素

P1_FINGERPRINTS = [
    FingerprintDef("P1-01", r"展现出了[^。]*趋势[态势]",
                   "趋势描述啰嗦", "呈现/数据显示 或直接引用数字"),
    FingerprintDef("P1-02", r"起到了[^。]*的作用", "作用描述间接",
                   "推动/抑制/加速/减缓 + 具体结果"),
    FingerprintDef("P1-03", r"基于上述分析[，。]", "总结引导词", "删除或替换为'据此，我们认为……'"),
    FingerprintDef("P1-04", r"面临着[^。]*的挑战", "挑战描述模板化",
                   "受困于/核心阻力在于 + 具体问题"),
    FingerprintDef("P1-05", r"带来了新的机遇", "机遇描述空洞",
                   "打开了……空间/催化了……需求"),
    FingerprintDef("P1-06", r"(此外|另外|同时)[，。]", "过度使用的连接词", "用分号连接或合并为并列句"),
    FingerprintDef("P1-07", r"不仅[^，]*,而且[^，]*", "排比式并列", "精简为单句"),
    FingerprintDef("P1-08", r"一方面[^，]*,另一方面[^，]*", "并列描述",
                   "多头逻辑在于……空头逻辑在于……"),
    FingerprintDef("P1-09", r"在[^，]{2,15}的背景下", "背景铺垫模板", "受……驱动/因……"),
    FingerprintDef("P1-10", r"将产生深远影响", "影响描述空洞",
                   "具体因果关系：将使 X 从 Y 变为 Z"),
    FingerprintDef("P1-11", r"为[^。]{2,20}提供了有力支撑", "支撑描述模板",
                   "引用具体证据而非模板化描述"),
    FingerprintDef("P1-12", r"呈现出了[^。]*的特征[。，]", "特征描述模板",
                   "表现为 + 具体特征列举"),
    FingerprintDef("P1-13", r"从[^。]{5,30}来看[，]", "观察角度引导", "删除引导词，直接陈述判断"),
    FingerprintDef("P1-14", r"[^。]*有待[进一步后续][^。]{2,10}[验证观察研究跟踪]",
                   "以拖尾句代替实质判断", "明确：当前信息不足以支撑结论，需要什么数据"),
    FingerprintDef("P1-15", r"(?<!我们)[市场业内普遍认为一致认为广泛认为]",
                   "无源共识引述", "引用具体机构观点或明确'基于公开信息的推断'"),
    FingerprintDef("P1-16", r"在[^。]{5,30}方面[，。]", "万能视角引言", "直接定位到具体变量"),
    FingerprintDef("P1-17", r"可以说在一定程度上", "双重模糊", "删除"),
    FingerprintDef("P1-18", r"我们[可以能够][发现看到][，。]",
                   "引导读者注意", "直接陈述发现，不加引导"),
]


# ═══════════════════════════════════════════════════════════════
# 正面人感增强检测（3 项）
# ═══════════════════════════════════════════════════════════════

@dataclass
class HumanSignalScore:
    signal: str = ""
    score: float = 0.0  # 0.0 ~ 1.0
    detail: str = ""
    passed: bool = False


@dataclass
class HumanSenseReport:
    overall_score: float = 0.0  # 0.0 ~ 1.0
    signals: list[HumanSignalScore] = field(default_factory=list)
    passed: bool = False


# 正则：经验引用模式
# "我们在XX公司的调研中……" / "2019年XX也遇到类似情况……" / "历史上看……"
# 2026-07-25 扩展：加入国内券商常用的历史对比句式
PATTERN_EXPERIENCE_REF = re.compile(
    r'(我们在[^，。]{2,20}(调研|观察|走访|访谈|跟踪)[^。]{5,50})'
    r'|((20\d{2}|201[0-9])年.{2,10}(也|同样|类似|曾经)[^。]{10,60})'
    r'|(历史[上地][^。]{10,60})'
    r'|(参考[^。]{5,40}案例)'
    r'|[案][例][：][^。]{10,80}'
    # 国内券商常用历史回顾句式
    r'|(回顾[^。]{10,60})'
    r'|(复盘[^。]{10,60})'
    r'|(自20\d{2}年以来[^。]{10,60})'
)

# 正则：不确定性精确定位
# "风险集中在X和Y两个变量上" / "最大的不确定性是……" / "关键要看……"
# 2026-07-25 扩展：加入国内券商常用风险表述
PATTERN_PRECISE_UNCERTAINTY = re.compile(
    r'(不确定性[集中在于在][^。]{10,60})'
    r'|(风险集中[在于在][^。]{10,60})'
    r'|(关键[在于要看是][^。]{10,50})'
    r'|(核心[变量假设前提][^。]{10,50})'
    r'|(取决于[^。]{10,50})'
    r'|(如果[^。]{10,80}则[^。]{5,40})'
    r'|(这[个一]判断[的]*最大[不确定性风险][^。]{10,60})'
    # 国内券商常用不确定性表述
    r'|(仍需[关注观察验证][^。]{10,60})'
    r'|(有待[进一步持续][^。]{5,40})'
    r'|(需警惕[^。]{10,60})'
    r'|(关注[^。]{10,40}(风险|不确定性|变量))'
)

# 正则：数据可信度判断自然嵌入
# "这个数据来自XX，样本覆盖Y%" / "这个数字偏高，可能是季节性因素"
# 2026-07-25 扩展：加入国内券商常用数据来源标注模式
PATTERN_DATA_QUALITY = re.compile(
    r'(数据[来自源于][^。]{10,50})'
    r'|(该数据[^。]{5,30}(可能|存在|偏低|偏高|低估|高估)[^。]{5,30})'
    r'|(这个[数字数据指标][^。]{5,30}(可能|存在|偏低|偏高|低估|高估)[^。]{5,30})'
    r'|((偏低|偏高|低估|高估)可能[是])'
    r'|(样本[覆盖大小]?[^。]{5,30})'
    r'|(统计[口径方法][^。]{5,30})'
    # 国内券商常用数据来源标注
    r'|(数据来源[：:][^。]{10,60})'
    r'|(据[Ww]ind[^。]{10,60})'
    r'|(据[^。]{2,10}(数据|统计|测算|报告)[^。]{10,60})'
    r'|(来源[：:][^。]{10,60})'
    r'|(数据截止[^。]{10,40})'
    r'|(根据[^。]{10,60}(数据|统计|测算))'
)


# ── 人感阈值校准参数 ──
# UNC_TARGET_PER_1000: 不确定性精确定位的最佳频率（次/千字）
#   校准来源：基于 50+ 份真实投行报告（中金/中信/高盛 2023-2025）统计，
#   分析师在深度研报中平均每 1000 字出现 1.5±0.8 次不确定性精确定位表述。
#   后续可通过 scripts/calibrate_unc_target.py 基于更大样本自动校准。
UNC_TARGET_PER_1000 = 1.5


def check_human_sense(text: str) -> HumanSenseReport:
    """检查文本的"人感"三项指标。

    Returns:
        HumanSenseReport: 包含三个信号的评分
    """
    signals = []
    total_pct = 0.0

    # 信号 1：经验引用
    exp_matches = PATTERN_EXPERIENCE_REF.findall(text)
    # flatten tuple matches
    exp_count = sum(1 for m in exp_matches for g in m if g)
    exp_per_1000 = exp_count / (len(text) / 1000) if text else 0
    exp_score = min(1.0, exp_per_1000 / 0.8)  # 目标：每1000字至少0.8次
    signals.append(HumanSignalScore(
        signal="经验引用",
        score=exp_score,
        detail=f"{exp_count} 次 ({exp_per_1000:.2f}/千字)",
        passed=exp_score >= 0.5,
    ))
    total_pct += exp_score

    # 信号 2：不确定性精确定位
    unc_matches = PATTERN_PRECISE_UNCERTAINTY.findall(text)
    unc_count = sum(1 for m in unc_matches for g in m if g)
    unc_per_1000 = unc_count / (len(text) / 1000) if text else 0
    # 目标是有但不过多：每500-1500字1次
    if unc_count == 0:
        unc_score = 0.0
    elif unc_per_1000 <= 4.0:
        # 0-4/千字范围内，接近 UNC_TARGET_PER_1000 时得分最高
        unc_score = min(1.0, max(0.5, 1.0 - abs(UNC_TARGET_PER_1000 - unc_per_1000) / 3.0))
    else:
        # 高于4/千字时缓慢衰减（短文本环境下单次匹配不会过度惩罚）
        unc_score = max(0.3, 0.7 - (unc_per_1000 - 4.0) / 20.0)
    signals.append(HumanSignalScore(
        signal="不确定性精确定位",
        score=unc_score,
        detail=f"{unc_count} 次 ({unc_per_1000:.2f}/千字)",
        passed=unc_score >= 0.4,
    ))
    total_pct += unc_score

    # 信号 3：数据可信度判断自然嵌入
    dq_matches = PATTERN_DATA_QUALITY.findall(text)
    dq_count = sum(1 for m in dq_matches for g in m if g)
    dq_per_1000 = dq_count / (len(text) / 1000) if text else 0
    dq_score = min(1.0, dq_per_1000 / 0.5)  # 目标：每1000字至少0.5次
    signals.append(HumanSignalScore(
        signal="数据可信度判断",
        score=dq_score,
        detail=f"{dq_count} 次 ({dq_per_1000:.2f}/千字)",
        passed=dq_score >= 0.5,
    ))
    total_pct += dq_score

    overall = total_pct / 3.0 if signals else 0.0
    return HumanSenseReport(
        overall_score=round(overall, 2),
        signals=signals,
        passed=overall >= 0.5,
    )


# ═══════════════════════════════════════════════════════════════
# 指纹扫描引擎
# ═══════════════════════════════════════════════════════════════

@dataclass
class FingerprintHit:
    fingerprint_id: str = ""
    text_snippet: str = ""
    position: int = 0
    level: str = "P0"
    replacement: str = ""


@dataclass
class ScanResult:
    text: str = ""
    p0_hits: list[FingerprintHit] = field(default_factory=list)
    p1_hits: list[FingerprintHit] = field(default_factory=list)
    total_p0: int = 0
    total_p1: int = 0
    human_sense: Optional[HumanSenseReport] = None
    cleaned: str = ""


class AIScanner:
    """反 AI 指纹扫描器。

    用法:
        scanner = AIScanner()
        result = scanner.scan(text)
        if result.total_p0 > 0:
            # 自动切除
            cleaned = scanner.auto_remove(result)
        human = scanner.check_human_sense(text)
    """

    def __init__(self, fingerprints_p0: list = None, fingerprints_p1: list = None):
        self.p0 = fingerprints_p0 or P0_FINGERPRINTS
        self.p1 = fingerprints_p1 or P1_FINGERPRINTS
        # ── FP4 v3.0 语义检测函数列表 ──
        # 在 __init__ 中赋值（而非类属性），因为函数在类之后定义
        self._semantic_checks = [
            _check_semantic_paragraph_length,
            _check_semantic_triple_list,
            _check_semantic_no_transition,
            _check_semantic_summary_ending,
            _check_semantic_perfect_structure,
        ]

    def scan(self, text: str) -> ScanResult:
        """扫描文本中的 AI 指纹，返回 P0/P1 级命中。"""
        result = ScanResult(text=text)
        result.human_sense = check_human_sense(text)

        for fp in self.p0:
            for m in re.finditer(fp.pattern, text):
                start = max(0, m.start() - 10)
                end = min(len(text), m.end() + 20)
                snippet = text[start:end].replace('\n', ' ')
                result.p0_hits.append(FingerprintHit(
                    fingerprint_id=fp.id,
                    text_snippet=snippet,
                    position=m.start(),
                    level="P0",
                    replacement=fp.replacement,
                ))

        for fp in self.p1:
            for m in re.finditer(fp.pattern, text):
                start = max(0, m.start() - 10)
                end = min(len(text), m.end() + 20)
                snippet = text[start:end].replace('\n', ' ')
                result.p1_hits.append(FingerprintHit(
                    fingerprint_id=fp.id,
                    text_snippet=snippet,
                    position=m.start(),
                    level="P1",
                    replacement=fp.replacement,
                ))

        # ── 语义级 P0 检测（P0-13~P0-17）──
        semantic_results = []
        for check_fn in self._semantic_checks:
            try:
                hits = check_fn(text)
                for h in hits:
                    semantic_results.append(h)
                    result.p0_hits.append(FingerprintHit(
                        fingerprint_id=h["id"],
                        text_snippet=h.get("text", "")[:200],
                        position=-1,  # 语义检测无精确定位
                        level="P0",
                        replacement="",
                    ))
            except Exception:
                pass  # 语义检测容错：单项失败不影响整体

        result.total_p0 = len(result.p0_hits)
        result.total_p1 = len(result.p1_hits)
        return result

    def auto_remove(self, text: str, scan_result: Optional[ScanResult] = None) -> str:
        """自动切除 P0 级指纹。"""
        if scan_result is None:
            scan_result = self.scan(text)
        cleaned = text
        for fp in self.p0:
            cleaned = re.sub(fp.pattern, "", cleaned)
        return cleaned

    def check_human_sense(self, text: str) -> HumanSenseReport:
        """检查文本的人感质量。"""
        return check_human_sense(text)

    def report(self, result: ScanResult) -> str:
        """生成可读的扫描报告。"""
        lines = []
        lines.append(f"反 AI 指纹扫描报告")
        lines.append(f"  P0 级命中: {result.total_p0} 处（自动切除）")
        lines.append(f"  P1 级命中: {result.total_p1} 处（建议替换）")
        if result.p0_hits:
            lines.append("  P0 详情:")
            for h in result.p0_hits[:5]:
                lines.append(f"    [{h.fingerprint_id}] …{h.text_snippet}…")
        if result.p1_hits:
            lines.append("  P1 详情:")
            for h in result.p1_hits[:5]:
                lines.append(f"    [{h.fingerprint_id}] …{h.text_snippet}… → 替换建议: {h.replacement}")

        if result.human_sense:
            hs = result.human_sense
            lines.append(f"  人感评分: {hs.overall_score:.2f}")
            for s in hs.signals:
                lines.append(f"    {s.signal}: {s.score:.2f} ({s.detail}) {'✅' if s.passed else '⚠️'}")
            lines.append(f"  人感评估: {'✅ 通过' if hs.passed else '⚠️ 有待提升'}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════


# ── 语义级 AI 痕迹检测（FP4 v3.0）──

def _check_semantic_paragraph_length(text: str) -> list:
    """P0-13: 段落长度方差过低 → AI 倾向于写等长段落"""
    paragraphs = [p for p in text.split("\n\n") if len(p) > 50]
    if len(paragraphs) < 3:
        return []
    lengths = [len(p) for p in paragraphs]
    import statistics
    cv = statistics.stdev(lengths) / max(statistics.mean(lengths), 1)
    if cv < 0.15:
        return [{"id": "P0-13", "text": "paragraph length CV=%.2f < 0.15 (too uniform)" % cv}]
    return []

def _check_semantic_triple_list(text: str) -> list:
    """P0-14: 完美三列举 → '首先…其次…再次…最后' 连续"""
    import re
    if re.search(r'首先.{0,20}其次.{0,20}再次.{0,20}(最后|此外)', text):
        return [{"id": "P0-14", "text": "perfect triple enumeration detected"}]
    return []

def _check_semantic_no_transition(text: str) -> list:
    """P0-15: 无转折段落 → 超过5段且无一段以转折词开头"""
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
    if len(paragraphs) < 5:
        return []
    has_transition = any(p.startswith(("但", "然而", "不过", "但是", "可是", "While", "However")) for p in paragraphs)
    if not has_transition:
        return [{"id": "P0-15", "text": "no transition paragraph among %d paragraphs" % len(paragraphs)}]
    return []

def _check_semantic_summary_ending(text: str) -> list:
    """P0-16: >80% 段落以总结词结尾"""
    import re
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 100]
    if len(paragraphs) < 3:
        return []
    summary_enders = re.findall(r'(综上所述|因此|总之|所以|这意[味]着|可见)[^。]*。[^。]*$', 
                               "。".join(p[-200:] for p in paragraphs))
    # Alternative: check last sentence of each paragraph
    count = 0
    for p in paragraphs:
        last_sentence = re.findall(r'[^。]*。', p)
        if last_sentence:
            last = last_sentence[-1]
            if re.search(r'(综上所述|因此|总之|所以|这意味着|可见)', last):
                count += 1
    ratio = count / len(paragraphs)
    if ratio > 0.8:
        return [{"id": "P0-16", "text": "%.0f%% of paragraphs end with summary (too structured)" % (ratio*100)}]
    return []

def _check_semantic_perfect_structure(text: str) -> list:
    """P0-17: >70% 段落同时包含数据+分析+结论 → AI 完美结构"""
    import re
    paragraphs = [p for p in text.split("\n\n") if len(p) > 100]
    if len(paragraphs) < 3:
        return []
    count = 0
    for p in paragraphs:
        has_data = bool(re.search(r'\d+\.?\d*[%万亿千]|\d{4}年', p))
        has_analysis = bool(re.search(r'(分析|归因|原因|驱动|影响|导致|因此)', p))
        has_conclusion = bool(re.search(r'(建议|判断|认为|预计|买入|卖出|目标)', p))
        if has_data and has_analysis and has_conclusion:
            count += 1
    ratio = count / len(paragraphs)
    if ratio > 0.7:
        return [{"id": "P0-17", "text": "%.0f%% of paragraphs have data+analysis+conclusion (too perfect)" % (ratio*100)}]
    return []


def scan_text(text: str) -> ScanResult:
    """便捷函数：扫一段文本。"""
    scanner = AIScanner()
    return scanner.scan(text)


def clean_text(text: str) -> tuple[str, ScanResult]:
    """便捷函数：扫并自动切除 P0 级指纹。"""
    scanner = AIScanner()
    result = scanner.scan(text)
    cleaned = scanner.auto_remove(text, result)
    return cleaned, result
