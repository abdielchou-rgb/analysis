# Business Model Classifier (勇者/能者/谋者/智者)

from __future__ import annotations
import re, logging
from dataclasses import dataclass, field

logger = logging.getLogger("2hao.biz_classifier")

@dataclass
class BizModelResult:
    biz_type: str = ""
    biz_name: str = ""
    confidence: float = 0.0
    description: str = ""
    key_metrics: list = field(default_factory=list)
    industry_tags: list = field(default_factory=list)

INDUSTRY_MAP = {
    "yongzhe": {
        "name": "勇者", "desc": "重资本扩张型制造业",
        "industries": ["机械", "电气设备", "汽车零部件", "有色", "化工",
                      "环保", "通信", "半导体", "电子制造", "军工"],
        "key_metrics": ["货币资金/有息债务", "收入/固定资产", "经营现金流/净利润"],
    },
    "nengzhe": {
        "name": "能者", "desc": "消费型和成熟型制造业",
        "industries": ["食品饮料", "家电", "汽车", "纺织服装", "医药",
                      "零售", "白酒", "乳制品", "日化"],
        "key_metrics": ["净利润增速", "ROE", "净资产增速", "现金收入比"],
    },
    "mouzhe": {
        "name": "谋者", "desc": "轻资产/灵活调整型",
        "industries": ["休闲服务", "商贸零售", "轻工制造", "纺织",
                      "传媒", "互联网", "软件"],
        "key_metrics": ["毛利率", "存货周转率", "经营杠杆系数", "财务杠杆系数"],
    },
    "zhizhe": {
        "name": "智者", "desc": "高端制造/科技型",
        "industries": ["电子", "通信", "计算机", "高端制造", "生物医药",
                      "医疗器械", "新材料", "AI", "芯片", "半导体设备"],
        "key_metrics": ["ROIC", "自由现金流", "资产再投资率", "研发收入比"],
    },
}

def classify_by_text(company_name, industry, business_desc=None):
    if business_desc is None:
        business_desc = ""
    scores = {}
    for type_id, config in INDUSTRY_MAP.items():
        score = 0.0
        matched = []
        if industry:
            for ind in config["industries"]:
                if ind.lower() in industry.lower():
                    score += 3.0
                    matched.append(ind)
        if business_desc:
            for ind in config["industries"]:
                if ind.lower() in business_desc.lower():
                    score += 2.0
                    matched.append(ind)
        if company_name:
            for ind in config["industries"]:
                if ind.lower() in company_name.lower():
                    score += 1.0
                    matched.append(ind)
        scores[type_id] = {"score": score, "matched": matched}

    if not any(s["score"] > 0 for s in scores.values()):
        return BizModelResult(biz_type="standard", biz_name="标准",
                            confidence=0.3,
                            description="无法确定类型，使用通用框架")

    best = max(scores, key=lambda k: scores[k]["score"])
    total = sum(s["score"] for s in scores.values())
    confidence = min(scores[best]["score"] / max(total, 0.1), 1.0)
    config = INDUSTRY_MAP[best]

    return BizModelResult(
        biz_type=best, biz_name=config["name"],
        confidence=round(confidence, 2),
        description=config["desc"],
        key_metrics=config["key_metrics"],
        industry_tags=config["industries"][:5],
    )

def get_scoring_adjustments(biz_type):
    adjustments = {
        "yongzhe": {"data_traceability": 1.2, "dcf_sensitivity": 1.3},
        "nengzhe": {"moat_analysis": 1.3, "decision_gate": 1.1},
        "mouzhe": {"persuasion_architecture": 1.2, "multi_model": 1.1},
        "zhizhe": {"bold_call": 1.2, "multi_model": 1.2},
    }
    return adjustments.get(biz_type, {})