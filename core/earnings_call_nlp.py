"""Earnings Call Q&A Structured Extraction — 业绩说明会问答结构化.

功能:
1. PDF解析 → 识别Q&A块
2. 结构化提取：提问者/问题/回答者/回答/主题/情感
3. 输出DataPoint供IronGate溯源
4. 支持中文/英文混合
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.models import DataPoint

logger = logging.getLogger("2hao.earnings_call")


@dataclass
class QAPair:
    """单条Q&A记录"""

    questioner: str = ""  # 提问者（机构/分析师名）
    questioner_type: str = ""  # 类型：机构/个人/媒体
    question: str = ""  # 问题全文
    answerer: str = ""  # 回答者（管理层职位/姓名）
    answer: str = ""  # 回答全文
    topics: list[str] = field(default_factory=list)  # 主题标签
    sentiment: str = "neutral"  # 情感：positive/negative/neutral
    confidence: float = 0.7  # 提取置信度
    source_page: int = 0  # 来源页码
    source_pdf: str = ""  # 来源PDF路径


# 常见管理层职位关键词
MANAGEMENT_TITLES = [
    "董事长",
    "总经理",
    "CEO",
    "CFO",
    "CTO",
    "COO",
    "副总裁",
    "VP",
    "总监",
    "董事",
    "秘书",
    "Chairman",
    "President",
    "CFO",
    "CTO",
    "COO",
    "VP",
    "Director",
    "Secretary",
]

# 常见机构关键词
INSTITUTION_KEYWORDS = [
    "证券",
    "基金",
    "资管",
    "投资",
    "银行",
    "保险",
    "Securities",
    "Capital",
    "Asset",
    "Investment",
    "Bank",
    "Fund",
    "Research",
    "Institute",
]

# 问题/回答分隔符模式
QA_SPLIT_PATTERNS = [
    r"(?:提问[:：]|问[:：]|Q[:：])\s*",
    r"(?:回答[:：]|答[:：]|A[:：])\s*",
    r"(?:分析师[:：]|投资者[:：]|机构[:：])\s*",
    r"(?:管理层[:：]|公司[:：]|董秘[:：])\s*",
]


def _is_qa_block(text: str) -> bool:
    """判断文本块是否为Q&A结构."""
    # 包含提问/回答标记
    has_q = bool(re.search(r"(提问|问|Q|提问者|分析师|投资者)[：:]", text))
    has_a = bool(re.search(r"(回答|答|A|回答者|管理层|公司|董秘)[：:]", text))
    return has_q and has_a


def _extract_questioner(text: str) -> tuple[str, str]:
    """提取提问者信息."""
    # 尝试匹配 "机构名称 分析师姓名" 模式
    patterns = [
        r"([^，,\s]{2,20}(?:证券|基金|资管|投资|银行|研究所|Institute|Capital|Securities))\s*[，,]\s*([^，,\s]{2,10})",
        r"(提问者|分析师|投资者|机构)[:：]\s*([^，,\n]{2,30})",
        r"([A-Za-z\s]{3,30})\s*[（(]([^）)]+)[）)]",  # English name (affiliation)
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            if len(match.groups()) >= 2:
                return match.group(1).strip(), match.group(2).strip()
            return match.group(1).strip(), ""

    # 简单提取第一行作为机构
    lines = text.strip().split("\n")
    if lines:
        first = lines[0].strip()
        for kw in INSTITUTION_KEYWORDS:
            if kw in first:
                return first, "机构"
    return "", ""


def _extract_answerer(text: str) -> str:
    """提取回答者信息."""
    patterns = [
        r"(回答者|管理层|公司|董秘|董事长|总经理|CEO|CFO)[:：]\s*([^，,\n]{2,20})",
        r"([^，,\n]{2,10}(?:董事长|总经理|CEO|CFO|副总裁|总监))[:：]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            if len(match.groups()) >= 2:
                return match.group(2).strip()
            return match.group(1).strip()
    return ""


def _classify_topics(question: str, answer: str) -> list[str]:
    """基于关键词分类主题."""
    text = (question + " " + answer).lower()
    topics = []

    topic_keywords = {
        "业绩指引": ["指引", "预期", "目标", "guidance", "outlook", "target"],
        "收入增长": ["收入", "营收", "营业收入", "revenue", "sales", "增长"],
        "利润率": ["毛利", "净利率", "利润率", "margin", "profitability"],
        "现金流": ["现金流", "经营性现金流", "自由现金流", "cash flow", "fcf"],
        "资本开支": ["资本开支", "capex", "投资", "扩产", "扩建"],
        "产能/产量": ["产能", "产量", "产出", "capacity", "output", "volume"],
        "价格/成本": ["价格", "成本", "原材料", "price", "cost", "raw material"],
        "竞争格局": ["竞争", "市场份额", "竞争对手", "competition", "market share"],
        "新产品/研发": ["新产品", "研发", "R&D", "创新", "技术", "pipeline"],
        "并购/投资": ["并购", "收购", "投资", "M&A", "acquisition", "investment"],
        "分红/回购": ["分红", "派息", "回购", "股东回报", "dividend", "buyback"],
        "海外业务": ["海外", "出口", "国际", "overseas", "export", "international"],
        "政策/监管": ["政策", "监管", "合规", "法规", "policy", "regulation"],
        "ESG/可持续": ["ESG", "碳中和", "可持续", "环保", "social", "governance"],
    }

    for topic, keywords in topic_keywords.items():
        if any(kw in text for kw in keywords):
            topics.append(topic)

    return topics if topics else ["其他"]


def _analyze_sentiment(question: str, answer: str) -> str:
    """简单情感分析."""
    text = (question + " " + answer).lower()

    positive_kws = [
        "增长",
        "提升",
        "改善",
        "乐观",
        "机会",
        "优势",
        "领先",
        "强劲",
        "growth",
        "improve",
        "optimistic",
        "opportunity",
        "strong",
        "lead",
    ]
    negative_kws = [
        "下降",
        "下滑",
        "压力",
        "挑战",
        "风险",
        "担忧",
        "疲软",
        "放缓",
        "decline",
        "pressure",
        "challenge",
        "risk",
        "concern",
        "weak",
        "slow",
    ]

    pos_count = sum(1 for kw in positive_kws if kw in text)
    neg_count = sum(1 for kw in negative_kws if kw in text)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


def parse_pdf_qa(pdf_path: str) -> list[QAPair]:
    """解析PDF提取Q&A.

    使用mineru_parser作为底层解析器。
    """
    from core.mineru_parser import parse_pdf

    blocks = parse_pdf(pdf_path)
    qa_pairs = []

    for i, block in enumerate(blocks):
        text = block.get("text", "") if isinstance(block, dict) else str(block)
        if not text or len(text) < 50:
            continue

        if _is_qa_block(text):
            # 分割问题和回答
            q_text = ""
            a_text = ""

            # 尝试按回答标记分割
            for pattern in [r"回答[:：]", r"答[:：]", r"A[:：]", r"管理层[:：]", r"公司[:：]", r"董秘[:：]"]:
                parts = re.split(pattern, text, maxsplit=1)
                if len(parts) == 2:
                    q_text = parts[0].strip()
                    a_text = parts[1].strip()
                    break

            if not q_text:
                # 兜底：前半段为问，后半段为答
                mid = len(text) // 2
                q_text = text[:mid].strip()
                a_text = text[mid:].strip()

            if len(q_text) < 20 or len(a_text) < 20:
                continue

            questioner, q_type = _extract_questioner(q_text)
            answerer = _extract_answerer(a_text)

            # 如果没提取到回答者，尝试从回答文本开头提取
            if not answerer and a_text:
                first_line = a_text.split("\n")[0][:50]
                for title in MANAGEMENT_TITLES:
                    if title in first_line:
                        answerer = title
                        break

            topics = _classify_topics(q_text, a_text)
            sentiment = _analyze_sentiment(q_text, a_text)

            qa_pairs.append(
                QAPair(
                    questioner=questioner,
                    questioner_type=q_type,
                    question=q_text[:1000],
                    answerer=answerer,
                    answer=a_text[:2000],
                    topics=topics,
                    sentiment=sentiment,
                    source_pdf=pdf_path,
                )
            )

    logger.info(f"Parsed {len(qa_pairs)} Q&A pairs from {pdf_path}")
    return qa_pairs


def qa_pairs_to_datapoints(qa_pairs: list[QAPair], asset: str) -> list[DataPoint]:
    """Convert QAPair list to DataPoints with provenance."""
    dps = []
    for i, qa in enumerate(qa_pairs):
        # Create DataPoint for the Q&A pair
        excerpt = f"Q: {qa.question[:100]} A: {qa.answer[:100]}"
        dp = DataPoint(
            name=f"{asset}_earnings_call_qa_{i}",
            value={
                "questioner": qa.questioner,
                "questioner_type": qa.questioner_type,
                "question": qa.question,
                "answerer": qa.answerer,
                "answer": qa.answer,
                "topics": qa.topics,
                "sentiment": qa.sentiment,
            },
            source=qa.source_pdf,
            access_ts=datetime.now(timezone.utc).isoformat(),
            excerpt_sha256=__import__("hashlib").sha256(excerpt.encode()).hexdigest(),
            confidence=qa.confidence,
            scope="company",
            unit="",
            note=f"topics={','.join(qa.topics)}; sentiment={qa.sentiment}; questioner={qa.questioner}; answerer={qa.answerer}",
        )
        dps.append(dp)

    return dps


def extract_qa_from_pdf(pdf_path: str, asset: str) -> list[DataPoint]:
    """Main entry: PDF -> QAPair -> DataPoint."""
    qa_pairs = parse_pdf_qa(pdf_path)
    return qa_pairs_to_datapoints(qa_pairs, asset)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        pdf = sys.argv[1]
        asset = sys.argv[2] if len(sys.argv) > 2 else "Test"
        dps = extract_qa_from_pdf(pdf, asset)
        for dp in dps:
            print(f"{dp.name}: {dp.value.keys() if isinstance(dp.value, dict) else dp.value}")
