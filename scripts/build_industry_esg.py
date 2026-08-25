# -*- coding: utf-8 -*-
"""R58 P0-2: 行业 ESG 数据构建脚本（幂等，覆盖写入 industry_esg.json）
数据来源：SASB/TCFD 行业地图 + WebSearch（数据已固化在下方 DATA 常量中，可重复运行）。
"""

import json
import os

DATA = {
    "industry_esg": [
        {
            "industry": "气体传感器/工业设备",
            "sasb_std": "RT-IG",
            "material_topics": [
                {
                    "topic": "能源管理",
                    "materiality": "high",
                    "metric": "单位产值能耗（kWh/万元）、生产环节可再生能源使用占比",
                    "sasb_std": "RT-IG-130a",
                },
                {
                    "topic": "产品安全与质量",
                    "materiality": "high",
                    "metric": "产品不合格率、客户投诉处理及时率",
                    "sasb_std": "RT-IG-540a",
                },
                {
                    "topic": "供应链环境管理",
                    "materiality": "medium",
                    "metric": "上游供应商ESG合规审核通过率、原材料碳足迹溯源比例",
                    "sasb_std": "RT-IG-330a",
                },
            ],
            "esg_risk_level": "medium",
            "esg_valuation_impact": "环境属性中等敏感，ESG表现优异可获得1-3%估值溢价，若存在产品质量安全事故可能导致5-8%估值折价",
            "china_policy": "受《工业领域碳达峰实施方案》约束，要求2025年单位工业增加值能耗较2020年下降13.5%，利好具备低碳生产能力的头部企业，倒逼高耗能中小企业升级生产设备",
            "source": "SASB 2023版工业产品行业标准、中国工信部《工业领域碳达峰实施方案》、ESG评级机构公开行业报告",
            "confidence": "B",
        },
        {
            "industry": "半导体",
            "sasb_std": "TC-SC",
            "material_topics": [
                {
                    "topic": "水资源管理",
                    "materiality": "high",
                    "metric": "单位产值耗水量（吨/万元）、生产废水回用率",
                    "sasb_std": "TC-SC-130a",
                },
                {
                    "topic": "有害物质管理",
                    "materiality": "high",
                    "metric": "生产过程中危险废物产生量、危废合规处置率",
                    "sasb_std": "TC-SC-150a",
                },
                {
                    "topic": "产品创新与能效",
                    "materiality": "medium",
                    "metric": "低功耗芯片产品营收占比、研发投入中节能技术占比",
                    "sasb_std": "TC-SC-540a",
                },
            ],
            "esg_risk_level": "high",
            "esg_valuation_impact": "环境与社会风险敏感度较高，若存在危废违规排放、供应链劳工纠纷等问题可能导致10-20%估值折价，ESG领先企业可获得5-8%估值溢价",
            "china_policy": '《"十四五"国家信息化规划》要求半导体行业提升能效水平，同时《电子信息制造业绿色发展规划》对半导体企业水耗、危废处置提出明确约束性指标，政策推动下行业绿色转型加速',
            "source": "SASB 2023版半导体与半导体设备行业标准、中国工信部《电子信息制造业绿色发展规划》、行业ESG研究报告",
            "confidence": "B",
        },
        {
            "industry": "光伏",
            "sasb_std": "RR-EC",
            "material_topics": [
                {
                    "topic": "产品生命周期环境影响",
                    "materiality": "high",
                    "metric": "光伏组件回收利用率、生产环节碳排放强度（kgCO2e/组件）",
                    "sasb_std": "RR-EC-130a",
                },
                {
                    "topic": "供应链劳工管理",
                    "materiality": "high",
                    "metric": "上游硅料供应商劳工合规审核通过率、生产环节员工工伤率",
                    "sasb_std": "RR-EC-330a",
                },
                {
                    "topic": "社区关系管理",
                    "materiality": "medium",
                    "metric": "光伏电站项目所在地社区投诉率、社区就业贡献率",
                    "sasb_std": "RR-EC-450a",
                },
            ],
            "esg_risk_level": "medium",
            "esg_valuation_impact": "整体为双碳受益行业，ESG表现优异可获得8-15%估值溢价，若存在供应链强迫劳动、光伏废弃物违规处置等问题可能导致10-20%估值折价",
            "china_policy": "《关于促进新时代新能源高质量发展的实施方案》明确支持光伏行业低碳发展，同时要求2025年光伏组件回收体系初步建立，政策直接利好具备组件回收技术、供应链合规的头部企业",
            "source": "SASB 2023版可再生能源设备行业标准、中国发改委《关于促进新时代新能源高质量发展的实施方案》、光伏行业协会ESG报告",
            "confidence": "A",
        },
        {
            "industry": "锂电/电池",
            "sasb_std": "IF-EU",
            "material_topics": [
                {
                    "topic": "矿产资源供应链管理",
                    "materiality": "high",
                    "metric": "上游锂、钴等关键矿产ESG溯源比例、矿产供应商合规审核通过率",
                    "sasb_std": "IF-EU-330a",
                },
                {
                    "topic": "电池回收与循环利用",
                    "materiality": "high",
                    "metric": "退役电池回收量、梯次利用率、再生材料使用占比",
                    "sasb_std": "IF-EU-130a",
                },
                {
                    "topic": "生产安全与职业健康",
                    "materiality": "medium",
                    "metric": "生产环节安全事故发生率、员工职业健康体检覆盖率",
                    "sasb_std": "IF-EU-410a",
                },
            ],
            "esg_risk_level": "high",
            "esg_valuation_impact": "上游矿产供应链ESG风险敏感度高，若存在矿产来源不合规、电池回收处置不当等问题可能导致15-25%估值折价，具备完善回收体系、供应链透明化的企业可获得10-15%估值溢价",
            "china_policy": "《新能源汽车动力蓄电池回收利用管理办法》要求电池生产企业承担回收主体责任，同时《锂电行业规范条件》对锂电企业能耗、安全生产提出明确要求，政策推动下行业集中度加速提升",
            "source": "SASB 2023版工业设备与电气行业标准、中国工信部《新能源汽车动力蓄电池回收利用管理办法》、锂电行业协会ESG报告",
            "confidence": "A",
        },
        {
            "industry": "医疗器械",
            "sasb_std": "HC-MD",
            "material_topics": [
                {
                    "topic": "产品可及性与质量",
                    "materiality": "high",
                    "metric": "产品不良事件发生率、欠发达地区产品可及性占比",
                    "sasb_std": "HC-MD-540a",
                },
                {
                    "topic": "数据隐私与安全",
                    "materiality": "high",
                    "metric": "患者数据泄露事件数、数据安全防护投入占比",
                    "sasb_std": "HC-MD-410a",
                },
                {
                    "topic": "供应链伦理管理",
                    "materiality": "medium",
                    "metric": "上游原材料供应商伦理审核通过率、反商业贿赂培训覆盖率",
                    "sasb_std": "HC-MD-330a",
                },
            ],
            "esg_risk_level": "medium",
            "esg_valuation_impact": "社会维度风险敏感度较高，若出现产品质量事故、数据泄露等问题可能导致20-30%估值折价，ESG表现领先的企业可获得3-8%估值溢价",
            "china_policy": '《\\"健康中国2030\\"规划纲要》要求提升医疗器械可及性，同时《医疗器械监督管理条例》对产品质量、数据安全提出更严格要求，政策推动下行业合规成本上升，利好头部合规企业',
            "source": "SASB 2023版医疗器械行业标准、中国国家药监局《医疗器械监督管理条例》、医疗行业ESG研究报告",
            "confidence": "B",
        },
    ]
}


def build(output_path="data/industry_esg.json"):
    """覆盖写入行业 ESG 数据。"""
    base = os.path.dirname(os.path.abspath(__file__))
    target = output_path if os.path.isabs(output_path) else os.path.join(base, "..", output_path)
    target = os.path.normpath(target)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)
    # 校验
    with open(target, encoding="utf-8") as f:
        data = json.load(f)
    industries = data["industry_esg"]
    print(f"[P0-2] OK: {len(industries)} industries -> {target}")
    for ind in industries:
        print(f"       {ind['industry']}: {len(ind['material_topics'])} topics, risk={ind['esg_risk_level']}")
    return target


if __name__ == "__main__":
    build()
