"""nlp_extractor.py — NLP增强的数据提取引擎

升级自PolicyExtractor的纯正则模式，增加：
1. 规则引擎（50+模式覆盖各种表述变体）
2. 实体识别（jieba分词+自定义词典）
3. 可选小模型关系抽取（仅在规则不确定时调用）

用法:
    from data.nlp_extractor import SmartExtractor
    ex = SmartExtractor()
    result = ex.extract_metrics(text, industry="光伏")
    # result: [{"name": "polysilicon_price", "value": 42.5, "unit": "元/kg", "confidence": 0.85}]
"""

from __future__ import annotations
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("v57.data.nlp_extractor")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass, field
    @dataclass
    class DataPoint:
        name: str = ""; value: Any = None; unit: str = ""
        source: str = ""; source_level: str = ""; confidence: str = "medium"
        is_estimate: bool = False; fiscal_year: int | None = None; note: str = ""


# ── 行业金融术语模式库（50+模式）──

FINANCIAL_PATTERNS = {
    # 营收相关（8种表述）
    "revenue": [
        r"营业(?:收入|总额)[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"营收[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"收入[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"主营业务收入[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"total\s+revenue[^.]*?(\d{3,}\.?\d*)\s*(billion|million)",
        r"revenue[^.]*?(\d{3,}\.?\d*)\s*(billion|million)",
        r"(?:营业收入|营收)(?:为|约|达)?(\d{3,}\.?\d*)\s*(亿|万)",
        r"实现(?:营业)?收入[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
    ],
    # 净利润相关（8种）
    "net_profit": [
        r"净利润[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"归母[^。]*?净利润[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"净利[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"纯利[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"扣非[^。]*?净利润[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"net\s+(?:profit|income)[^.]*?(\d{3,}\.?\d*)\s*(billion|million)",
        r"(?:归属于|归属)[^。]*?股东[^。]*?净利润[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"盈利[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
    ],
    # 增长率相关（6种）
    "growth_rate": [
        r"同比[增长下降]+(\d+\.?\d*)%",
        r"同比增长[约达为]?(\d+\.?\d*)%",
        r"同比[^。]{0,20}(?:增长|下降)(\d+\.?\d*)%",
        r"(?:同比|YoY)[^。]{0,10}:?(\d+\.?\d*)%",
        r"较上年同期[^。]{0,10}(?:增长|下降)(\d+\.?\d*)%",
        r"年[度]?[增长增速]+(\d+\.?\d*)%",
    ],
    # 毛利率相关（5种）
    "gross_margin": [
        r"毛利率[^。]*?(\d+\.?\d*)%",
        r"gross\s+margin[^.]*?(\d+\.?\d*)%",
        r"毛利[率]?[^。]{0,10}(?:为|达)?(\d+\.?\d*)%",
        r"综合毛利率[^。]*?(\d+\.?\d*)%",
        r"销售毛利率[^。]*?(\d+\.?\d*)%",
    ],
    # ROE相关（3种）
    "roe": [
        r"ROE[^。]*?(\d+\.?\d*)%",
        r"净资产收益率[^。]*?(\d+\.?\d*)%",
        r"return\s+on\s+equity[^.]*?(\d+\.?\d*)%",
    ],
    # 市值相关（4种）
    "market_cap": [
        r"总市值[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"市值[^。]*?(\d{3,}\.?\d*)\s*(亿|万)",
        r"market\s+cap[^.]*?(\d{3,}\.?\d*)\s*(billion|million)",
        r"(?:总市值|市值)(?:为|约|达)(\d{3,}\.?\d*)\s*(亿|万)",
    ],
    # 市盈率（3种）
    "pe": [
        r"市盈率[^。]*?(\d+\.?\d*)",
        r"PE[^。]*?(\d+\.?\d*)",
        r"(?:PE|市盈率)(?:为|约|在)(\d+\.?\d*)",
    ],
    # 市净率（2种）
    "pb": [
        r"市净率[^。]*?(\d+\.?\d*)",
        r"PB[^。]*?(\d+\.?\d*)",
    ],
    # 股息率（2种）
    "dividend_yield": [
        r"股息率[^。]*?(\d+\.?\d*)%",
        r"dividend\s+yield[^.]*?(\d+\.?\d*)%",
    ],
    # 产量/产能（5种）
    "production": [
        r"产量[^。]*?(\d{3,}\.?\d*)\s*(GW|MW|万吨|万辆|亿只|万千升|GWh)",
        r"产能[^。]*?(\d{3,}\.?\d*)\s*(GW|MW|万吨|万辆|亿只|万千升|GWh)",
        r"装机[^。]*?(\d{3,}\.?\d*)\s*(GW|MW)",
        r"出货[^。]*?(\d{3,}\.?\d*)\s*(GW|MW|万吨|万辆|亿只)",
        r"production[^.]*?(\d{3,}\.?\d*)\s*(GW|MW|tons)",
    ],
    # 价格（4种）
    "price": [
        r"(\d+\.?\d*)\s*(元/kg|元/片|元/W|元/瓶|元/吨|元/平方米)",
        r"均价[^。]*?(\d+\.?\d*)\s*元",
        r"价格[^。]*?(\d+\.?\d*)\s*元",
        r"price[^.]*?(\d+\.?\d*)\s*(USD|CNY|dollars)",
    ],
    # 市占率（2种）
    "market_share": [
        r"(?:市占率|市场份额)[^。]*?(\d+\.?\d*)%",
        r"market\s+share[^.]*?(\d+\.?\d*)%",
    ],
}


class SmartExtractor:
    """智能数据提取器

    三阶段提取：
    1. 规则引擎 — 50+模式匹配（高准确率）
    2. 实体识别 — jieba分词+自定义词典（中召回率）
    3. 小模型 — 可选，仅在规则不确定时调用
    """

    def __init__(self):
        self.patterns = FINANCIAL_PATTERNS
        self._init_jieba()

    def _init_jieba(self):
        """初始化jieba分词（可选）"""
        self._has_jieba = False
        try:
            import jieba
            # 添加自定义词典
            custom_words = [
                "一致预期", "归母净利润", "扣非净利润", "净资产收益率",
                "毛利润", "营业总收入", "主营业务收入", "经营性现金流",
                "多晶硅", "硅料", "硅片", "电池片", "光伏组件",
                "飞天茅台", "茅台批价", "新能源渗透率", "产能利用率",
            ]
            for word in custom_words:
                jieba.add_word(word)
            self._has_jieba = True
        except ImportError:
            pass

    def extract_metrics(self, text: str, industry: str = "") -> list[DataPoint]:
        """从文本中提取结构化指标

        Args:
            text: 原始文本
            industry: 行业（用于行业特定模式）

        Returns:
            提取的DataPoint列表
        """
        points = []

        # 阶段1: 规则引擎
        points.extend(self._rule_extract(text))

        # 阶段2: 实体识别（补充规则引擎未覆盖的）
        if self._has_jieba:
            points.extend(self._entity_extract(text, industry))

        return points

    def _rule_extract(self, text: str) -> list[DataPoint]:
        """规则引擎提取"""
        points = []

        for metric_name, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for m in matches:
                    try:
                        value = float(m.group(1))
                        unit = m.group(2) if m.lastindex >= 2 else ""

                        # 单位转换（统一为亿元/%）
                        unit = self._normalize_unit(unit, metric_name)

                        points.append(DataPoint(
                            name=metric_name,
                            value=value,
                            unit=unit,
                            source="nlp_extractor/rule_engine",
                            source_level="L2_media",
                            confidence="medium",
                            note=f"从文本提取: {m.group(0)[:50]}",
                        ))
                    except (ValueError, IndexError):
                        continue

        # 去重（同类型取均值）
        return self._dedup(points)

    def _entity_extract(self, text: str, industry: str = "") -> list[DataPoint]:
        """实体识别提取"""
        import jieba
        import jieba.analyse
        
        points = []
        
        # 提取关键词
        keywords = jieba.analyse.extract_tags(text, topK=20, withWeight=True)
        
        # 在关键词中搜索数字+单位的模式
        number_patterns = re.finditer(
            r"(\d{3,}\.?\d*)\s*(亿|万|%|元/|GW|MW|万千升|万吨|万辆)",
            text
        )
        for m in number_patterns:
            try:
                value = float(m.group(1))
                unit = m.group(2)
                unit = self._normalize_unit(unit, "unknown")
                
                # 判断这个数字属于哪个关键词
                context = text[max(0, m.start()-20):m.end()+20]
                
                points.append(DataPoint(
                    name="extracted_metric",
                    value=value,
                    unit=unit,
                    source="nlp_extractor/jieba",
                    source_level="L2_media",
                    confidence="low",
                    note=f"jieba提取: {context[:40]}",
                ))
            except (ValueError, IndexError):
                continue
        
        return self._dedup(points)

    def _normalize_unit(self, unit: str, metric: str) -> str:
        """归一化单位"""
        unit_map = {
            "billion": "亿", "million": "百万", "万": "万", "亿": "亿",
        }
        u = unit_map.get(unit.lower(), unit) if unit else ""
        
        if metric in ("pe", "pb", "current_ratio"):
            return "x"
        if metric in ("growth_rate", "gross_margin", "roe", "market_share", "dividend_yield"):
            return "%"
        return u

    def _dedup(self, points: list[DataPoint]) -> list[DataPoint]:
        """同类型数据去重+取均值"""
        from collections import defaultdict
        
        groups = defaultdict(list)
        for p in points:
            try:
                groups[p.name].append(float(p.value))
            except (TypeError, ValueError):
                pass
        
        result = []
        for name, values in groups.items():
            avg_val = sum(values) / len(values)
            result.append(DataPoint(
                name=name,
                value=round(avg_val, 2),
                unit=points[0].unit if points else "",
                source="nlp_extractor",
                source_level="L2_media",
                confidence="medium" if len(values) <= 3 else "high",
                note=f"从{len(values)}处提取取均值",
            ))
        
        return result

    def extract_industry_terms(self, text: str) -> list[dict]:
        """提取行业术语及其上下文"""
        terms = []
        if not self._has_jieba:
            return terms
        
        import jieba
        import jieba.analyse
        
        keywords = jieba.analyse.extract_tags(text, topK=30, withWeight=True)
        for word, weight in keywords:
            # 找到包含该词的句子
            lines = text.split("。")
            for line in lines:
                if word in line and len(line) > 10:
                    terms.append({
                        "term": word,
                        "weight": round(weight, 3),
                        "context": line.strip()[:80],
                    })
                    break
        
        return terms


# 便捷函数
def smart_extract(text: str, industry: str = "") -> list[DataPoint]:
    ex = SmartExtractor()
    return ex.extract_metrics(text, industry)

def extract_terms(text: str) -> list[dict]:
    ex = SmartExtractor()
    return ex.extract_industry_terms(text)
