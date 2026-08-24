"""policy_extractor.py — 政策传导链提取器

从政策文本中提取"政策->行业->企业层面->影响方向"四层传导链。

用法:
    from legacy.data_platform.policy_extractor import PolicyTransmissionExtractor
    ex = PolicyTransmissionExtractor()
    chain = ex.extract_transmission_chain(policy_text)
"""

from __future__ import annotations
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("v57.data.policy_extractor")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class DataPoint:
        name: str = ""
        value: Any = None
        unit: str = ""
        source: str = ""
        source_level: str = ""
        confidence: str = "medium"
        is_estimate: bool = False
        fiscal_year: int | None = None
        note: str = ""


INDUSTRY_TAGS = {
    "新能源": ["新能源", "光伏", "风电", "储能", "氢能", "锂电", "新能源汽车"],
    "半导体": ["半导体", "芯片", "集成电路", "光刻", "EDA"],
    "人工智能": ["人工智能", "大模型", "AI", "智能计算", "算力"],
    "生物医药": ["生物医药", "创新药", "医疗器械", "CXO"],
    "消费": ["消费", "零售", "电商", "餐饮", "旅游"],
    "金融": ["金融", "银行", "保险", "证券", "资本"],
    "房地产": ["房地产", "住房", "楼市", "旧改"],
    "制造业": ["制造", "工业", "装备", "智能制造"],
    "数字经济": ["数字经济", "数据要素", "SaaS", "云计算"],
    "环保": ["环保", "碳", "排放", "绿色", "ESG"],
}


class PolicyTransmissionExtractor:
    name = "policy_extractor"

    INTENSITY_KEYWORDS = {
        "强": ["大力", "强制", "必须", "严格", "重点", "全力", "坚决", "加快", "确保"],
        "中": ["鼓励", "支持", "推动", "促进", "引导", "优化", "完善", "规范"],
        "弱": ["探索", "研究", "考虑", "酝酿", "逐步", "有条件", "适时"],
    }
    DIRECTION_POSITIVE = [
        "利好",
        "促进",
        "支持",
        "推动",
        "鼓励",
        "补贴",
        "减免",
        "加大投入",
        "放宽",
        "扩大",
        "扶持",
        "优惠",
    ]
    DIRECTION_NEGATIVE = [
        "限制",
        "禁止",
        "反对",
        "整治",
        "处罚",
        "提高门槛",
        "加强监管",
        "收紧",
        "压缩",
        "削减",
        "淘汰",
    ]

    def extract_transmission_chain(self, text: str, source_name: str = "") -> dict:
        result = {
            "policy_name": self._extract_name(text),
            "issuing_body": self._extract_issuing_body(text),
            "intensity": self._classify_intensity(text),
            "related_industries": self._extract_industries(text),
            "transmission_chain": self._build_chain(text),
            "expected_impact": self._extract_impact(text),
            "data_points": [],
        }
        dp_src = source_name or result.get("issuing_body", "policy_extractor")
        for cl in result["transmission_chain"]:
            result["data_points"].append(
                DataPoint(
                    name="policy_transmission",
                    value=cl.get("impact_statement", ""),
                    unit="",
                    source=dp_src,
                    source_level="L1_filing",
                    confidence="medium" if result["intensity"] != "弱" else "low",
                    note=f"产业政策传导链:{cl.get('layer', '')}->{cl.get('industry', '')}->{cl.get('direction', '')}",
                )
            )
        return result

    def _extract_name(self, text: str) -> str:
        m = re.search(r"《([^》]+)》", text)
        if m:
            return m.group(1)
        m = re.search(r"关于[^。]{5,60}(通知|意见|办法|方案|规划|决定)", text)
        if m:
            return m.group(0)[:60]
        return text[:50] if text else "未知政策"

    def _extract_issuing_body(self, text: str) -> str:
        bodies = [
            "国务院",
            "工信部",
            "发改委",
            "证监会",
            "科技部",
            "财政部",
            "央行",
            "银保监会",
            "金融监管总局",
            "商务部",
            "自然资源部",
            "生态环境部",
            "住建部",
            "交通运输部",
        ]
        for body in bodies:
            if body in text[:500]:
                return body
        m = re.search(r"([\u4e00-\u9fa5]{2,4}(?:部|委|局|行|院|办))", text[:300])
        return m.group(1) if m else "未知"

    def _classify_intensity(self, text: str) -> str:
        scores = {"强": 0, "中": 0, "弱": 0}
        for level, keywords in self.INTENSITY_KEYWORDS.items():
            for kw in keywords:
                scores[level] += text.count(kw)
        return max(scores, key=scores.get) if any(scores.values()) else "中"

    def _extract_industries(self, text: str) -> list[dict]:
        industries = []
        for industry, tags in INDUSTRY_TAGS.items():
            matched = [tag for tag in tags if tag in text]
            if matched:
                pos_count = sum(1 for d in self.DIRECTION_POSITIVE if d in text)
                neg_count = sum(1 for d in self.DIRECTION_NEGATIVE if d in text)
                direction = "利好" if pos_count > neg_count + 1 else ("利空" if neg_count > pos_count + 1 else "中性")
                industries.append(
                    {
                        "industry": industry,
                        "direction": direction,
                        "matched_keywords": matched,
                        "relevance": len(matched) / max(len(tags), 1),
                    }
                )
        return sorted(industries, key=lambda x: x["relevance"], reverse=True)

    def _build_chain(self, text: str) -> list[dict]:
        chain = []
        industries = self._extract_industries(text)
        for ind in industries:
            chain.append(
                {
                    "layer": "1_政策信号",
                    "policy": self._extract_name(text),
                    "industry": ind["industry"],
                    "direction": ind["direction"],
                    "intensity": self._classify_intensity(text),
                    "impact_statement": f"政策({self._extract_name(text)[:20]})对{ind['industry']}行业{ind['direction']}",
                }
            )
            chain.append(
                {
                    "layer": "2_行业影响",
                    "policy": self._extract_name(text),
                    "industry": ind["industry"],
                    "direction": ind["direction"],
                    "impact_statement": f"{ind['industry']}行业受政策影响，方向{ind['direction']}",
                }
            )
            chain.append(
                {
                    "layer": "3_企业层面",
                    "policy": self._extract_name(text),
                    "industry": ind["industry"],
                    "direction": ind["direction"],
                    "impact_statement": f"传导路径：{ind['industry']}行业企业将受到{ind['direction']}影响",
                }
            )
        return chain

    def _extract_impact(self, text: str) -> str:
        m = re.search(r"(预期|预计|将)[^。]{10,100}。", text)
        return m.group(0)[:100] if m else ""


def extract_policy_chain(text: str, source: str = "") -> dict:
    ex = PolicyTransmissionExtractor()
    return ex.extract_transmission_chain(text, source)
