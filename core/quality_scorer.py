"""V52 QualityScorer — 8-dimension positive writing quality assessment.
Zero LLM dependency. All regex-based heuristics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class DimensionScore:
    score: float = 0.0
    detail: str = ""
    signals: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class QualityScore:
    narrative_grip: DimensionScore = field(default_factory=DimensionScore)
    surprise_premium: DimensionScore = field(default_factory=DimensionScore)
    concreteness: DimensionScore = field(default_factory=DimensionScore)
    depth_chain: DimensionScore = field(default_factory=DimensionScore)
    structure: DimensionScore = field(default_factory=DimensionScore)
    evidence_density: DimensionScore = field(default_factory=DimensionScore)
    actionability: DimensionScore = field(default_factory=DimensionScore)
    precision: DimensionScore = field(default_factory=DimensionScore)
    source_credibility: DimensionScore = field(default_factory=DimensionScore)
    experience_citation: DimensionScore = field(default_factory=DimensionScore)
    overall: float = 0.0
    per_section: dict[str, dict] = field(default_factory=dict)
    passed: bool = False


URGENCY_KW = [
    "关键",
    "出乎意料",
    "拐点",
    "分歧",
    "市场忽略",
    "本质",
    "核心矛盾",
    "不可逆",
    "超预期",
    "转折",
    "核心",
    "临界点",
    "结构性",
]
SURPRISE_M = [
    "但",
    "然而",
    "不过",
    "我们的判断不同",
    "市场共识认为",
    "我们认为",
    "关键分歧在于",
    "但我们的",
    "但市场",
    "与市场预期不同",
    "超出预期",
    "低于预期",
]
VAGUE_Q = ["很多", "大量", "显著", "某种程度上", "一定程度", "较为", "相对", "比较", "整体上"]
REASON_W = ["因为", "所以", "因此", "这意味着", "导致", "从而", "进而", "根源在于"]
JUDGMENT_V = [
    "我们认为",
    "预计",
    "核心判断",
    "关键分歧",
    "估值是",
    "风险在",
    "结论是",
    "我们判断",
    "核心结论",
    "我们预计",
    "我们测算",
    "关键在于",
    "本质是",
    "核心矛盾",
    "核心逻辑",
    "投资逻辑",
    "建议",
    "买入",
    "增持",
    "中性",
    "减持",
]
EVIDENCE_P = [
    r"据[^。，]{2,15}[年报公告数据来源]",
    r"来[自源于][^。，]{2,15}[数据统计]",
    r"（来源[：:][^）]+）",
    r"\[来源[：:][^\]]+\]",
    r"数据来源[：:][^。，]+",
    r"[年报半年报季报招股书研报公告][^。，]{0,5}[显示表明披露]",
    r"[数据统计调研测算][^。，]{0,5}[显示表明]",
    r"来源于[^。，]{2,20}",
]
ACTION_W = ["建议", "推荐", "关注", "预计目标价", "上调", "下调", "买入", "卖出", "增持", "减持"]
PRECISE_U = [r"\d+%", r"\u00b1\d+", r"概率\d+", r"区间"]
FUZZY_U = ["有待观察", "需要关注", "值得注意", "需持续关注"]


class QualityScorer:
    WEIGHTS = {
        "narrative_grip": 0.10,
        "surprise_premium": 0.15,
        "concreteness": 0.15,
        "depth_chain": 0.10,
        "structure": 0.10,
        "evidence_density": 0.15,
        "actionability": 0.10,
        "precision": 0.05,
        "source_credibility": 0.05,
        "experience_citation": 0.05,
    }
    MIN_PASSING = 0.90

    def score(self, text: str, context: dict | None = None) -> QualityScore:
        if not text or not text.strip():
            return QualityScore()
        result = QualityScore()
        result.narrative_grip = self._narrative_grip(text)
        result.surprise_premium = self._surprise_premium(text)
        result.concreteness = self._concreteness(text)
        result.depth_chain = self._depth_chain(text)
        result.structure = self._structure(text)
        result.evidence_density = self._evidence_density(text)
        result.actionability = self._actionability(text)
        result.precision = self._precision(text)
        result.source_credibility = self._source_credibility(text)
        result.experience_citation = self._experience_citation(text)
        result.per_section = self._per_section(text)
        result.overall = round(sum(getattr(result, d).score * w for d, w in self.WEIGHTS.items()), 2)
        # 零容忍门禁：所有维度必须 >= 0.50，不能有任何单项短板
        # 这是执行约束——防止任何维度被忽视
        MIN_DIM = 0.50
        all_dims_pass = all(getattr(result, dim).score >= MIN_DIM for dim in self.WEIGHTS.keys())
        result.passed = result.overall >= self.MIN_PASSING and all_dims_pass
        if not all_dims_pass:
            failing = [d for d in self.WEIGHTS.keys() if getattr(result, d).score < MIN_DIM]
            result.overall = round(result.overall, 2)  # keep score, but mark fails
        return result

    def report(self, s: QualityScore) -> str:
        lines = [f"Quality Score: {s.overall:.2f}/1.00 {'PASS' if s.passed else 'NEEDS WORK'}", ""]
        for dim, weight in sorted(self.WEIGHTS.items(), key=lambda x: -x[1]):
            ds = getattr(s, dim)
            bar = "#" * int(ds.score * 15) + "-" * (15 - int(ds.score * 15))
            lines.append(f"  {dim:20s} [{bar}] {ds.score:.2f}")
            for issue in ds.issues[:2]:
                lines.append(f"    ! {issue}")
        return "\n".join(lines)

    def _narrative_grip(self, text: str) -> DimensionScore:
        ds = DimensionScore()
        first = self._first_para(text)[:300]
        count = sum(1 for k in URGENCY_KW if k in first)
        ds.score = round(min(count / 2.0, 1.0), 2)  # 原3.0降至2.0
        if count > 0:
            ds.signals.append(f"首段 {count} urgency kw")
        else:
            ds.issues.append("首段无 urgency 关键词")
        return ds

    def _surprise_premium(self, text: str) -> DimensionScore:
        ds = DimensionScore()
        count = sum(len(re.findall(re.escape(m), text)) for m in SURPRISE_M)
        expected = max(len(text) / 500, 1.0)
        ds.score = round(min(count / expected, 1.0), 2)
        ds.signals.append(f"对比标记 {count} 处")
        return ds

    def _concreteness(self, text: str) -> DimensionScore:
        ds = DimensionScore()
        numeric = len(re.findall(r"\d+\.?\d*%?", text))
        vague = sum(len(re.findall(re.escape(v), text)) for v in VAGUE_Q)
        total = numeric + vague
        if total == 0:
            ds.score = 0.3
            return ds
        ratio = numeric / max(vague, 1)
        ds.score = round(min(ratio / 5.0, 1.0), 2)
        ds.signals.append(f"数字:{numeric} 模糊:{vague} 比值:{ratio:.1f}")
        return ds

    def _depth_chain(self, text: str) -> DimensionScore:
        ds = DimensionScore()
        positions = sorted([m.start() for rw in REASON_W for m in re.finditer(re.escape(rw), text)])
        count = len(positions)
        if count < 2:
            ds.score = 0.3
            ds.issues.append(f"推理链不足({count}处)")
            return ds
        if count >= 6:
            ds.score = 0.9
        elif count >= 4:
            ds.score = 0.7
        else:
            # 少于4处时检查间距是否合理
            spans = [positions[i + 1] - positions[i] for i in range(count - 1)]
            avg_span = sum(spans) / len(spans)
            if avg_span <= 2000:
                ds.score = 0.6
            else:
                ds.score = 0.5
        ds.signals.append(f"推理词 {count} 处")
        return ds

    def _structure(self, text: str) -> DimensionScore:
        ds = DimensionScore()
        secs = re.split(r"\n##\s+", text)
        if len(secs) <= 1:
            ds.score = 0.3
            return ds
        # 检查每节前100字符(含分析判断词)而非仅标题行，排除附录
        ok = 0
        total = 0
        for s in secs[1:]:
            if not s.strip():
                continue
            if "附录" in s[:50]:
                continue
            total += 1
            if any(j in s[:100] for j in JUDGMENT_V):
                ok += 1
        if total == 0:
            total = 1
        ds.score = round(ok / max(total, 1), 2)
        ds.signals.append(f"{ok}/{total} 有效章节含判断句")
        return ds

    def _evidence_density(self, text: str) -> DimensionScore:
        ds = DimensionScore()
        paras = [p for p in text.split("\n\n") if p.strip()]
        if not paras:
            return ds
        count = sum(len(re.findall(p, text)) for p in EVIDENCE_P)
        # 也检查通用数据引用模式
        generic_sources = len(
            re.findall(
                r"(数据来源|来源[：:]|据[^。，]{2,20}[显示表明]|根据[^。，]{2,20}数据|年报[显示表明]|季度[报告显示])",
                text,
            )
        )
        total = count + generic_sources
        density = total / len(paras)
        ds.score = round(min(density / 0.4, 1.0), 2)
        if total > 0:
            ds.signals.append(f"{total} 引用/{len(paras)} 段={density:.2f}")
        else:
            ds.issues.append("未检测到数据引用")
        return ds

    def _actionability(self, text: str) -> DimensionScore:
        ds = DimensionScore()
        count = sum(len(re.findall(re.escape(a), text)) for a in ACTION_W)
        ds.score = round(min(count / 5.0, 1.0), 2)
        if count > 0:
            ds.signals.append(f"行动词 {count} 处")
        else:
            ds.issues.append("无投资行动指向")
        return ds

    def _precision(self, text: str) -> DimensionScore:
        ds = DimensionScore()
        precise = sum(len(re.findall(p, text)) for p in PRECISE_U)
        fuzzy = sum(len(re.findall(f, text)) for f in FUZZY_U)
        # Detect fake precision: exact numbers without bounds (e.g., "目标价2500元" without range)
        fake_precise = len(re.findall(r"目标价[\s]?\d+[\s]?元", text))
        if fake_precise > 0 and precise == 0:
            ds.score = 0.2
            ds.issues.append(f"伪精确: {fake_precise} 处目标价无区间")
            ds.signals.append(f"伪精确:{fake_precise}")
            return ds
        if precise + fuzzy == 0:
            ds.score = 0.5
            return ds
        ratio = precise / max(fuzzy, 1)
        ds.score = round(min(ratio / 3.0, 1.0), 2)
        ds.signals.append(f"精确:{precise} 模糊:{fuzzy} 真精确比:{ratio:.1f}")
        return ds

    def _per_section(self, text: str) -> dict:
        secs = re.split(r"\n##\s+", text)
        results = {}
        for i, s in enumerate(secs[1:]):
            lines = [l for l in s.strip().split("\n") if l.strip()]
            if not lines:
                continue
            title = lines[0][:25]
            body = "\n".join(lines[1:]) if len(lines) > 1 else ""
            scores = self.score(body) if body else QualityScore()
            avg = round(sum(getattr(scores, d).score * w for d, w in self.WEIGHTS.items()), 2) if body else 0
            results[f"sec{i + 1}_{title}"] = {"avg": avg}
        return results

    def _experience_citation(self, text: str) -> DimensionScore:
        """Detect experience-based citations — a key human signal."""
        ds = DimensionScore()
        # Senior analyst phrases that refer to domain experience
        exp_signals = [
            "从.*经验",
            "在.*行业中",
            "在.*领域",
            "在我覆盖的",
            "历史上",
            "过去.*年",
            "长期跟踪",
            "持续关注",
            "从行业规律来看",
            "从历史规律来看",
        ]
        count = sum(1 for p in exp_signals if re.search(p, text))
        ds.score = round(min(count / 3.0, 1.0), 2)
        if count > 0:
            ds.signals.append(f"经验引用 {count} 处")
        else:
            ds.issues.append("无经验引用")
        return ds

    def _source_credibility(self, text: str) -> DimensionScore:
        """Detect whether sources are differentiated by credibility."""
        ds = DimensionScore()
        # Check for credibility differentiation signals
        credible_signals = re.findall(r"(公司公告|官方数据|公司披露|年报数据|招股说明书)", text)
        estimation_signals = re.findall(r"(测算|估算|推测|假设|模型计算)", text)
        total_sources = len(re.findall(r"来源[：:]", text))
        if total_sources < 2:
            ds.score = 0.5
            ds.signals.append("来源较少，无需分档")
            return ds
        # Credibility differentiation = both hard data AND estimation sources exist
        has_differentiation = len(credible_signals) > 0 and len(estimation_signals) > 0
        ds.score = 0.8 if has_differentiation else 0.3
        if has_differentiation:
            ds.signals.append(f"可信度分级: {len(credible_signals)} 处硬数据 + {len(estimation_signals)} 处测算")
        else:
            ds.issues.append("未区分数据来源可信度")
            if credible_signals:
                ds.signals.append(f"仅有硬数据引用 ({len(credible_signals)} 处)")
            elif estimation_signals:
                ds.signals.append(f"仅有测算引用 ({len(estimation_signals)} 处)")
        return ds

    @staticmethod
    def _first_para(text: str) -> str:
        text = re.sub(r"^#\s+[^\n]+\n", "", text).strip()
        for p in text.split("\n\n"):
            stripped = p.strip()
            if len(stripped) <= 30:
                continue
            # Skip metadata blocks (author/date/institution headers)
            if (
                stripped.startswith("**报告")
                or stripped.startswith("**分析师")
                or stripped.startswith("**执业")
                or stripped.startswith("**机构")
                or stripped.startswith("**日期")
            ):
                continue
            return stripped
        return text[:500]


class DeepSeekQualityScorer:
    """使用DeepSeek的语义质量评分器 - 替代regex关键词检测"""

    def score(self, text: str, report_type: str = "industry_deep") -> dict:
        """返回语义质量评分(0-1)和详细反馈"""
        if len(text) < 500:
            return {"overall": 0.0, "issues": ["报告过短"]}

        try:
            from core.deepseek_client import call_deepseek

            prompt = (
                """你是一位顶级券商研究部质量控制总监。请严格评估以下分析师报告的质量。

## 评分维度（每项0-10分）
1. 论证深度(0-10): 因果链完整度、数据支撑、反方论证
2. 数据质量(0-10): 来源标注、时效性、交叉验证
3. 可读性(0-10): 自然语言、无AI套话、有分析师语气
4. 专业性(0-10): 术语准确、行业知识深度、分析框架运用
5. 结构完整(0-10): 章节完整、逻辑递进、核心判断突出

## 评分标准
- 9-10: 中金/高盛/McKinsey级别顶级报告
- 7-8: 一级券商优质报告
- 5-6: 合格的分析报告
- 3-4: 有明显缺陷
- 0-2: 不合格

## 报告文本
"""
                + text[:4000]
                + """

返回JSON格式: {{"overall": 7.5, "dimensions": {{"argument_depth": 7, "data_quality": 8, "readability": 7, "expertise": 6, "structure": 8}}, "issues": ["数据来源需要更多交叉验证"], "suggestions": ["增加企业财务对比表"]}}
"""
            )

            result = call_deepseek(
                [
                    {"role": "system", "content": "你是一位严格的质控总监。返回JSON评分。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1024,
                # 修复（2026-09-04）：此前缺省 provider="opencode_go"（未注册）→
                # 全量回退打 zhipu 加剧 429。质控评分走 deepseek。
                provider="deepseek",
            )

            content = result["choices"][0]["message"]["content"]
            import json
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                overall = data.get("overall", 5.0) / 10.0
                return {
                    "overall": overall,
                    "issues": data.get("issues", []),
                    "suggestions": data.get("suggestions", []),
                }
        except Exception:
            pass

        return {"overall": 0.5, "issues": ["DeepSeek评分失败"], "suggestions": []}
