"""
方法论规则库（Methodology Rules）— 把投行分析框架固化为"可执行判断规则"

**问题**：之前 methodology_frameworks_detailed.json 只存"文件列表"（file/topic/indicators），
没有可执行的判断规则 → LLM 只看到文件名，学不到分析步骤 → "投喂了没提升深度"。

**方案**：从方法论 PDF 提炼"判断规则"（阈值 + 逻辑 + 结论指向），存成结构化规则。
section_writer 生成时注入这些规则，LLM 真正按投行方法做判断。

**规则格式**：
{
  "rule_id": "lifecycle_stage",
  "topic": "industry_lifecycle",
  "name": "产业生命周期六阶段判断",
  "source": "长江证券-产业生命周期视角(2020)",
  "inputs": ["营收增速", "资本开支增速"],
  "rules": [
    {"condition": "营收增速>20% 且 资本开支高", "stage": "成长赛道期", "implication": "高增长高投入，看技术路线与渗透率"},
    {"condition": "...", "stage": "...", "implication": "..."}
  ],
  "decision_hints": "左侧(成长/龙头进阶)关注机会，右侧(洗牌/出清)关注格局改善"
}
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("2hao.methodology_rules")

_ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = _ROOT / "data" / "methodology_rules.json"


# ── 默认规则库（人工提炼自方法论 PDF） ──
DEFAULT_RULES = {
    "industry_lifecycle": [
        {
            "rule_id": "lifecycle_six_stage",
            "name": "产业生命周期六阶段判断（营收+资本开支双指标）",
            "source": "长江证券-供给侧行业比较系列：产业生命周期视角(2020-04)",
            "inputs": ["营收增速", "资本开支增速", "竞争格局"],
            "rules": [
                {
                    "condition": "营收高增长 + 资本开支高",
                    "stage": "成长赛道期",
                    "implication": "需求侧驱动为主，看渗透率天花板与增长持续性",
                },
                {
                    "condition": "营收增速放缓 + 资本开支仍高",
                    "stage": "由成长到洗牌",
                    "implication": "供给开始过剩，格局恶化风险上升",
                },
                {
                    "condition": "营收低增长 + 行业洗牌",
                    "stage": "洗牌期/出清末期",
                    "implication": "弱者出清，关注格局改善后的龙头",
                },
                {
                    "condition": "营收企稳 + 集中度提升",
                    "stage": "龙头进阶期",
                    "implication": "龙头份额提升，利润弹性最大",
                },
                {
                    "condition": "营收稳态 + 竞争格局稳定",
                    "stage": "稳态成熟期",
                    "implication": "低增长高确定性，看现金流与分红",
                },
            ],
            "decision_hints": "左侧(成长赛道期/龙头进阶期)关注超额收益机会，右侧(洗牌期/出清末期)关注格局改善后的龙头",
            "cross_validation": "需结合渗透率(导入/成长/成熟)与竞争格局(CR5)交叉验证",
        }
    ],
    "business_model": [
        {
            "rule_id": "model_four_types",
            "name": "商业模式四型判断（勇者/能者/谋者/智者）",
            "source": "长江证券-商业模式解构财务框架",
            "inputs": ["毛利率", "费用率", "资产周转率", "杠杆"],
            "rules": [
                {
                    "condition": "高毛利+高费用率(品牌/研发驱动)",
                    "model": "勇者模型",
                    "implication": "产品力驱动，看研发转化与品牌溢价",
                },
                {
                    "condition": "高周转+低毛利(运营驱动)",
                    "model": "能者模型",
                    "implication": "效率驱动，看供应链与规模",
                },
                {
                    "condition": "高杠杆+高ROE(资本驱动)",
                    "model": "谋者模型",
                    "implication": "杠杆驱动，看负债结构与利率敏感",
                },
                {"condition": "均衡+稳健(管理驱动)", "model": "智者模型", "implication": "管理驱动，看治理与执行"},
            ],
            "decision_hints": "先识别商业模式类型，再选对应财务分析重点（毛利/周转/杠杆/治理）",
        },
        {
            "rule_id": "small_mid_cap_stage",
            "name": "中小市值三阶段模型（市值×商业模式）",
            "source": "安信证券-商业模式解构财务框架系列二(2022-05)",
            "inputs": ["市值", "毛利率", "净利润增速", "经营层持股"],
            "rules": [
                {
                    "condition": "市值0-50亿(产品竞争力为核心)",
                    "model": "非诚勿扰型",
                    "implication": "看毛利率及其波动性+营收/长期资本+净资产增速，二次验证管理层持股",
                },
                {
                    "condition": "市值50-200亿(盈利兑现为核心)",
                    "model": "成长兑现型",
                    "implication": "看净利润增速+财务风险可控，商业模式已固定",
                },
                {
                    "condition": "市值200-500亿(走向大白马)",
                    "model": "走向大白马型",
                    "implication": "看份额提升+现金流质量，龙头进阶",
                },
            ],
            "decision_hints": "按市值区间选对应择股框架，用毛利率波动/净利增速/现金流等勾稽指标而非单纯绝对数值筛选",
        },
    ],
    "valuation": [
        {
            "rule_id": "dynamic_static_valuation",
            "name": "动态 vs 静态估值判断（广发证券估值体系）",
            "source": "广发证券-授人以渔系列报告八：估值体系，动态与静态(2022-09)",
            "inputs": ["动态PE分位数", "静态PE分位数", "盈利预期", "商誉减值", "交易集中度"],
            "rules": [
                {
                    "condition": "动态PE分位数显著高于静态PE分位数",
                    "signal": "估值偏高",
                    "implication": "行业较大概率已处于高估值位置，需警惕回调",
                },
                {
                    "condition": "动态PE分位数显著低于静态PE分位数",
                    "signal": "估值向上拐点",
                    "implication": "行业有望迎来估值向上拐点，赔率较优",
                },
                {
                    "condition": "商誉减值/一次性减记导致静态估值失真",
                    "signal": "静态估值失真",
                    "implication": "用动态估值(分析师盈利预期)替代，规避一次性减记扰动",
                },
                {
                    "condition": "交易集中度高(前10%公司占成交50%)",
                    "signal": "尾部噪音",
                    "implication": "基于重点跟踪公司而非全部公司，规避尾部估值噪音",
                },
            ],
            "decision_hints": "动态估值(盈利预期)捕捉景气预期更灵敏，静态估值(历史分位)用于拐点判断；两者结合判断估值位置",
            "cross_validation": "估值分位须基于历史区间(3-5年)，行业对比用PE-预期利润增速差优于PB-ROE",
        },
        {
            "rule_id": "peg_valuation",
            "name": "PEG 估值判断（成长股）",
            "source": "投行通用估值框架",
            "inputs": ["PE", "预期利润增速"],
            "rules": [
                {
                    "condition": "PE/预期增速 < 1",
                    "signal": "估值合理偏低",
                    "implication": "成长股估值与增速匹配，可关注",
                },
                {"condition": "PE/预期增速 > 2", "signal": "估值偏贵", "implication": "增速无法支撑估值，需警惕"},
            ],
            "decision_hints": "PEG仅适用于成长股，周期/价值股不适用",
        },
    ],
    "macro_pmi": [
        {
            "rule_id": "pmi_analysis",
            "name": "PMI 分析方法与资产配置（信达宏观方法论）",
            "source": "信达证券-宏观方法论之五：PMI分析方法与资产配置含义(2022-09)",
            "inputs": ["PMI", "新订单", "出厂价格", "产成品库存", "出口新订单"],
            "rules": [
                {"condition": "PMI > 50", "signal": "经济扩张", "implication": "相对上月扩张，制造业景气上行"},
                {"condition": "PMI < 50", "signal": "经济收缩", "implication": "相对上月收缩，需关注政策宽松预期"},
                {
                    "condition": "新订单回升+产成品库存回落",
                    "signal": "主动补库",
                    "implication": "需求改善，盈利预期向好，利好周期",
                },
                {"condition": "新订单回落+库存积压", "signal": "被动累库", "implication": "需求走弱，警惕库存周期下行"},
            ],
            "decision_hints": "PMI是环比指标，判断高低要结合季节性均值；关注四维度(需求/生产/库存/价格)；PMI新订单→GDP增速、出厂价→PPI、产成品库存→工业库存、出口新订单→出口",
            "cross_validation": "PMI新订单与GDP增速、出厂价格与PPI环比、产成品库存与工业企业库存、出口新订单与出口金额交叉验证",
        },
        {
            "rule_id": "macro_framework",
            "name": "宏观分析框架（经济核算/高频跟踪/通胀预测）",
            "source": "信达证券-宏观分析框架系列",
            "inputs": ["GDP", "PMI", "CPI", "PPI", "货币供应", "就业"],
            "rules": [
                {
                    "condition": "长期看潜在增速、短期看库存/政策周期",
                    "signal": "周期定位",
                    "implication": "区分长短期，避免用周期波动误判趋势",
                },
                {
                    "condition": "CPI-PPI剪刀差扩大",
                    "signal": "上中下游利润再分配",
                    "implication": "上游成本压力缓解，中下游盈利改善",
                },
                {"condition": "M2增速回升+社融放量", "signal": "流动性宽松", "implication": "利好成长与估值修复"},
            ],
            "decision_hints": "宏观判断先定位周期阶段(库存/政策/盈利)，再看流动性(货币/信用)，最后落到行业传导",
        },
    ],
    "strategy_profit": [
        {
            "rule_id": "profit_framework",
            "name": "盈利框架：周期与脉动（广发证券策略方法论）",
            "source": "广发证券-授人以渔系列报告七：盈利框架，周期与脉动(2022-09)",
            "inputs": ["ROE", "周转率", "利润率", "杠杆率", "现金流", "产能周期", "库存周期"],
            "rules": [
                {
                    "condition": "ROE持续上行",
                    "signal": "中长期行业配置方向",
                    "implication": "ROE上行代表行业景气持续，配置价值高",
                },
                {
                    "condition": "消费品看利润率、制造业看周转率",
                    "signal": "ROE驱动因子不同",
                    "implication": "消费品重品牌利润率，制造业重规模周转",
                },
                {
                    "condition": "市场底不晚于盈利底",
                    "signal": "盈利拐点",
                    "implication": "盈利底确认后可布局，盈利周期位置辅助判断景气",
                },
                {
                    "condition": "产能周期(扩产意愿+能力)位置低",
                    "signal": "供给压力小",
                    "implication": "产能周期是最重要的行业比较指标，供需压力小则盈利确定",
                },
            ],
            "decision_hints": "先看ROE杜邦三因子识别行业驱动(利润/周转/杠杆)，再看三周期(产能/库存/偿债)定位供需，现金流结构验证扩张姿态",
            "cross_validation": "盈利预测调整 + 估值 + 盈利周期三合一做行业比较",
        },
        {
            "rule_id": "bottom_framework",
            "name": "底部框架（否极与泰来）",
            "source": "广发证券-授人以渔系列报告二：底部框架",
            "inputs": ["估值", "盈利", "流动性", "情绪", "政策"],
            "rules": [
                {
                    "condition": "估值历史低位+盈利底确认+流动性宽松",
                    "signal": "底部区域",
                    "implication": "三重共振确认底部，可左侧布局",
                },
                {
                    "condition": "政策底→市场底→盈利底顺序出现",
                    "signal": "底部节奏",
                    "implication": "按政策/市场/盈利顺序跟踪底部演进",
                },
            ],
            "decision_hints": "底部判断需估值+盈利+流动性三因子共振，政策底先行、盈利底最后确认",
        },
    ],
}


def load_rules() -> dict:
    """加载规则库（合并默认 + 外部文件）。"""
    rules = json.loads(json.dumps(DEFAULT_RULES))  # deep copy
    if RULES_PATH.exists():
        try:
            ext = json.loads(RULES_PATH.read_text(encoding="utf-8"))
            for topic, items in ext.items():
                if isinstance(items, list):
                    rules.setdefault(topic, []).extend(items)
        except Exception as e:
            logger.warning("[RULES] 外部规则加载失败: %s", e)
    return rules


def get_topic_rules(topic: str) -> list:
    """获取某主题的规则列表。"""
    rules = load_rules()
    return rules.get(topic, [])


def serialize_rules_for_prompt(topics: list[str], max_rules: int = 3) -> str:
    """把规则序列化成 prompt 注入文本（供 section_writer 引用）。"""
    rules = load_rules()
    lines = ["=== 分析方法论规则（投行框架提炼） ==="]
    for t in topics:
        for r in rules.get(t, [])[:max_rules]:
            lines.append(f"\n【{r.get('name', t)}】(来源: {r.get('source', '')})")
            for rule in r.get("rules", [])[:4]:
                cond = rule.get("condition", "")
                stage = rule.get("stage", rule.get("model", ""))
                impl = rule.get("implication", "")
                lines.append(f"- 若{cond} → {stage}，含义: {impl}")
            hint = r.get("decision_hints", "")
            if hint:
                lines.append(f"- 决策提示: {hint}")
    return "\n".join(lines)


def save_external_rules(topic: str, items: list) -> str:
    """保存外部规则（Marvis 搜集的行业参数可固化到这里）。

    格式: data/methodology_rules.json
    {"<topic>": [{"rule_id": "...", "name": "...", "rules": [...]}]}
    """
    existing = {}
    if RULES_PATH.exists():
        try:
            existing = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing.setdefault(topic, []).extend(items)
    RULES_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(RULES_PATH)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    rules = load_rules()
    print("规则库主题:", list(rules.keys()))
    print()
    print(serialize_rules_for_prompt(["industry_lifecycle", "business_model"]))
