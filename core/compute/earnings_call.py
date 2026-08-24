"""吸收3: Earnings Call Analysis — 业绩会文字实录分析。

从 AlphaAnalyst 吸收的文本分析能力，但聚焦 A 股市场。

A 股的业绩会文字实录和美股不同：
  - 管理层更谨慎、语气更平
  - 前瞻性指引更少但更关键
  - 分析师问答环节的"回避信号"是核心信号

数据来源（免费）:
  - 东方财富业绩会文字实录（免费HTTP）
  - 同花顺业绩会文字实录（免费HTTP）
  - 上交所/深交所的投资者关系页面（免费）

输出:
  - tone_score: -1.0 (极负面) 到 +1.0 (极正面)
  - forward_looking_statements: 提取的前瞻性陈述列表
  - evasion_signals: 管理层回避的回答检测
  - key_metrics: 会议中提及的关键财务数字
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("v51.earnings_call")

# Parsing dependencies — all optional
HAS_REQUESTS = False
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    pass

HAS_PARSE = False
try:
    from bs4 import BeautifulSoup
    HAS_PARSE = True
except ImportError:
    pass


@dataclass
class EarningsCallResult:
    """业绩会分析结果。"""
    code: str = ""
    company: str = ""
    date: str = ""
    tone_score: float = 0.0          # -1.0 to 1.0
    tone_label: str = "中性"         # 积极/偏积极/中性/偏消极/消极
    forward_looking_statements: list = field(default_factory=list)
    evasion_signals: list = field(default_factory=list)
    key_metrics_extracted: list = field(default_factory=list)
    positive_sentence_pct: float = 0.0
    negative_sentence_pct: float = 0.0
    management_certainty: float = 0.5  # 0.0-1.0
    management_consistency: float = 0.5  # 0.0-1.0 (vs previous calls)
    summary: str = ""
    source_url: str = ""
    n_sentences: int = 0


# ── Tone analysis ────────────────────────────────────────────

POSITIVE_PATTERNS = [
    r'增长|增长显著|高速增长|超预期|好于预期',
    r'有信心|乐观|看好|积极|向好',
    r'改善|提升|增强|扩大|加速',
    r'创新高|历史最好|突破|里程碑',
    r'市场地位|领先优势|护城河|壁垒',
    r'分红|回购|股东回报|价值提升',
]

NEGATIVE_PATTERNS = [
    r'下降|下滑|放缓|收缩|萎缩',
    r'低于预期|不及预期|承压|挑战',
    r'亏损|赤字|负增长|恶化',
    r'风险|不确定|压力|困难|严峻',
    r'竞争加剧|价格战|毛利率下降',
    r'裁员|关停|减值|亏损|坏账',
]

EVASION_PATTERNS = [
    r'不便透露|暂不方便|不能披露',
    r'以公告为准|请关注后续公告',
    r'目前无法判断|不确定|不好说',
    r'这个问题比较复杂|需要综合评估',
    r'我们正在研究|还在讨论中|待定',
    r'跳过这个问题|下一个问题',
]

FORWARD_LOOKING_PATTERNS = [
    r'预计\d{4}年|我们预计|我们预期',
    r'指引|目标|计划|规划',
    r'未来\d{1,2}年|中长期|展望',
    r'产能释放|新产品上市|新业务',
    r'资本开支|capex|投资计划',
]

KEY_METRIC_PATTERNS = [
    (r'营收(\d+\.?\d*)', 'revenue'),
    (r'净利润(\d+\.?\d*)', 'net_profit'),
    (r'毛利率(\d+\.?\d*)%', 'gross_margin'),
    (r'净利率(\d+\.?\d*)%', 'net_margin'),
    (r'ROE(\d+\.?\d*)%?', 'roe'),
    (r'分红(\d+\.?\d*)元', 'dividend'),
]


class EarningsCallAnalyzer:
    """Earnings call text analyzer for A-share market."""

    @staticmethod
    def analyze(text: str, code: str = "",
                company: str = "", date: str = "") -> EarningsCallResult:
        """Analyze earnings call transcript text.

        Args:
            text: Full transcript text
            code: Stock code
            company: Company name
            date: Call date

        Returns:
            EarningsCallResult with tone, forward-looking, evasions.
        """
        result = EarningsCallResult(
            code=code,
            company=company or code,
            date=date or datetime.now().strftime("%Y-%m-%d"),
        )

        # Clean text
        text = text.strip()
        if not text:
            result.summary = "无文本内容"
            return result

        # Split into sentences
        sentences = [s.strip() for s in re.split(r'[。！？\n]', text) if len(s.strip()) > 5]
        result.n_sentences = len(sentences)

        if not sentences:
            result.summary = "无可分析的句子"
            return result

        # 1. Tone analysis
        pos_count = 0
        neg_count = 0
        for sent in sentences:
            if any(re.search(p, sent) for p in POSITIVE_PATTERNS):
                pos_count += 1
            if any(re.search(p, sent) for p in NEGATIVE_PATTERNS):
                neg_count += 1

        result.positive_sentence_pct = round(pos_count / len(sentences) * 100, 1)
        result.negative_sentence_pct = round(neg_count / len(sentences) * 100, 1)

        total_pn = pos_count + neg_count
        if total_pn > 0:
            result.tone_score = round((pos_count - neg_count) / total_pn, 3)
        else:
            result.tone_score = 0.0

        # Tone label
        if result.tone_score > 0.3:
            result.tone_label = "积极"
        elif result.tone_score > 0.1:
            result.tone_label = "偏积极"
        elif result.tone_score < -0.3:
            result.tone_label = "消极"
        elif result.tone_score < -0.1:
            result.tone_label = "偏消极"
        else:
            result.tone_label = "中性"

        # 2. Forward-looking statements
        for sent in sentences:
            if any(re.search(p, sent) for p in FORWARD_LOOKING_PATTERNS):
                result.forward_looking_statements.append(sent.strip())

        result.forward_looking_statements = result.forward_looking_statements[:10]

        # 3. Evasion signals
        for sent in sentences:
            if any(re.search(p, sent) for p in EVASION_PATTERNS):
                result.evasion_signals.append(sent.strip())

        result.evasion_signals = result.evasion_signals[:10]

        # 4. Key metrics extraction
        for sent in sentences:
            for pattern, metric_name in KEY_METRIC_PATTERNS:
                match = re.search(pattern, sent)
                if match:
                    result.key_metrics_extracted.append({
                        "metric": metric_name,
                        "value": float(match.group(1)),
                        "context": sent[:80],
                    })

        # Deduplicate metrics
        seen = set()
        unique_metrics = []
        for m in result.key_metrics_extracted:
            key = f"{m['metric']}:{m['value']}"
            if key not in seen:
                seen.add(key)
                unique_metrics.append(m)
        result.key_metrics_extracted = unique_metrics[:10]

        # 5. Management certainty (proxy: ratio of confident terms)
        high_certainty = len(re.findall(r'确定|肯定|一定|明确|承诺|保证', text))
        low_certainty = len(re.findall(r'可能|大概|或许|估计|希望|争取', text))
        total_certainty = high_certainty + low_certainty
        result.management_certainty = round(
            high_certainty / total_certainty, 2
        ) if total_certainty > 0 else 0.5

        # 6. Summary
        n_fl = len(result.forward_looking_statements)
        n_ev = len(result.evasion_signals)
        result.summary = (
            f"管理层语气{result.tone_label}（积极{result.positive_sentence_pct:.0f}%/"
            f"消极{result.negative_sentence_pct:.0f}%），"
            f"前瞻性陈述{n_fl}条，回避信号{n_ev}个，"
            f"确定性指数{result.management_certainty:.0%}"
        )

        logger.info(
            f"Earnings call analyzed: {result.company} | "
            f"tone={result.tone_label} | "
            f"forward={n_fl} | evasions={n_ev}"
        )
        return result

    @staticmethod
    def estimate_tone_direction(result: EarningsCallResult) -> str:
        """Convert tone to trading/intelligence signal direction."""
        score = result.tone_score
        if score > 0.2 and result.management_certainty > 0.5:
            return "bull"
        elif score < -0.2:
            return "bear"
        else:
            return "neutral"


# ── AlphaAnalyst-style sentiment aggregator ──────────────────

def aggregate_earnings_signal(text: str, code: str = "",
                               previous_text: str = "") -> dict:
    """Full pipeline: analyze + compare with previous + produce signal.

    Args:
        text: Current earnings call text
        code: Stock code
        previous_text: Previous earnings call text (for consistency check)

    Returns:
        Signal dict compatible with DecisionHub.
    """
    result = EarningsCallAnalyzer.analyze(text, code=code)
    signal = {
        "signal_id": f"earnings_call_{code}",
        "name": f"{code} 业绩会语气",
        "direction": EarningsCallAnalyzer.estimate_tone_direction(result),
        "strength": abs(result.tone_score),
        "source": "earnings_call",
        "details": {
            "tone_score": result.tone_score,
            "tone_label": result.tone_label,
            "forward_looking_count": len(result.forward_looking_statements),
            "evasion_count": len(result.evasion_signals),
            "management_certainty": result.management_certainty,
            "key_metrics": result.key_metrics_extracted[:5],
        },
        "summary": result.summary,
    }

    # Consistency check vs previous call
    if previous_text:
        prev_result = EarningsCallAnalyzer.analyze(previous_text)
        tone_change = result.tone_score - prev_result.tone_score
        signal["details"]["tone_change_vs_previous"] = round(tone_change, 3)
        signal["details"]["consistency"] = round(
            1.0 - min(abs(tone_change), 1.0), 2
        )
        if abs(tone_change) > 0.3:
            signal["direction"] = "bull" if tone_change > 0 else "bear"
            signal["strength"] = min(1.0, abs(tone_change) * 1.5)

    return signal
