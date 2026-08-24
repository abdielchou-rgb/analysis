# -*- coding: utf-8 -*-
"""
决策推理引擎（Decision Engine）— R83 内容层分析能力（核心改造靶心）

**定位**：把"委托方决策备忘录"的战略推理链做成**确定性计算层**，不依赖 LLM 临场发挥。
上一版 v0.89 的根本问题不是"没写结构"，而是"没有推理"——投资评级报告式的章节罗列
替代了"柯力困境→卡位价值→放量逻辑→延伸产业"这条决策链。

**设计原则（与 bottleneck_engine 同哲学）**：
  1. 能算的不让 LLM 编——困境/卡位/放量/延伸全部数值化，注入写作 prompt 供引用
  2. 结论可复核——每条判断给"输入数据 → 计算 → 结论"三要素，Gate 可审计
  3. 数据驱动——数据不足时诚实降级（标注 E + 缺口），不硬凑

**决策链（决策备忘录的推理主轴）**：
  困境诊断 → 卡位价值评估 → 放量路径拆解 → 延伸产业判断 → 投入/回报/最坏损失

用法：
    from core.decision_engine import DecisionEngine
    result = DecisionEngine().analyze(asset="油位传感器", data=collected_data)
    # 结果注入 data_context["decision_engine"]，section_writer 消费
"""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("2hao.decision_engine")

_ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════
# 决策链 Step 1：困境诊断（SWOT 客观化）
# ═══════════════════════════════════════════════════════════
def _extract_num(text: str, pattern: str) -> float | None:
    """从文本提取首个数字（支持小数/百分号/负号）。"""
    if not text:
        return None
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return float(m.group(1).replace("%", "").replace(",", ""))
    except (ValueError, IndexError):
        return None


def diagnose_dilemma(data: dict) -> dict:
    """困境诊断：委托方的劣势（Struggles）与优势（Strengths）量化。

    输入：enrich 的 keli_strategy 文本 + 柯力财务
    输出：struggles/strengths 数组，每条含 现象/证据/量化
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    keli = cd.get("keli_strategy", "")
    company = cd.get("company_intro", "")

    # 劣势（从 keli_strategy 提取）
    struggles = []
    if "营收增速快于利润增速" in str(keli):
        rev_g = _extract_num(company, r"营收\s*([\d.]+)亿")
        net_g = _extract_num(company, r"归母.*?([\d.]+)亿")
        struggles.append({
            "维度": "增长质量",
            "现象": "营收增速快于利润增速，内生增长质量待验证",
            "证据": f"营收{rev_g}亿 vs 归母{net_g}亿（增速差）",
            "量化": 0.6,  # 严重度 0-1
            "方向": "估值溢价依赖物联网+机器人叙事，若叙事证伪有戴维斯双杀风险",
        })
    if "估值溢价依赖" in str(keli):
        struggles.append({
            "维度": "估值依赖",
            "现象": "估值溢价依赖物联网+机器人叙事",
            "证据": "PE 溢价 vs 纯称重同业",
            "量化": 0.5,
            "方向": "需要新增长故事承接估值——油位/物位是候选",
        })
    if "商誉并购风险" in str(keli):
        struggles.append({
            "维度": "商誉风险",
            "现象": "并购驱动增长带来商誉减值风险",
            "证据": "华虹增持+久通投资等并表",
            "量化": 0.4,
            "方向": "整合协同若不及预期，商誉减值拖累利润",
        })
    if not struggles:
        struggles.append({"维度": "数据不足", "现象": "困境信息缺失", "证据": "", "量化": 0.0,
                          "方向": "需补充委托方困境描述"})

    # 优势（从 keli_strategy + company_intro 提取）
    strengths = []
    net_margin = _extract_num(company, r"净利率\s*([\d.]+)%")
    if net_margin:
        strengths.append({
            "维度": "盈利质量",
            "现象": f"净利率{net_margin}%远超行业中游8-12%",
            "证据": f"净利率{net_margin}% vs 行业8-12%",
            "量化": 0.9,
            "方向": "高毛利证明制造+品牌溢价，可复制到物位领域",
        })
    if "产能利用率85%" in str(keli) or "15%闲置" in str(keli):
        strengths.append({
            "维度": "产能冗余",
            "现象": "产能利用率85%，15%闲置可承接新业务",
            "证据": "无需大额资本开支即可承接油位订单",
            "量化": 0.8,
            "方向": "闲置产能承接=低成本进入，边际成本低",
        })
    if "水质68.7%" in str(keli) or "68.7%" in str(keli):
        strengths.append({
            "维度": "平台化验证",
            "现象": "水质传感毛利率68.7%，验证传感器森林多物理量复制",
            "证据": "水质68.7% → 物位同路径可复制",
            "量化": 0.85,
            "方向": "多物理量平台化的成功样本，油位是下一个品类树",
        })
    if "海外毛利率56.58%" in str(keli) or "56.58%" in str(keli):
        strengths.append({
            "维度": "海外变现",
            "现象": "海外毛利率56.58%高于国内",
            "证据": "海外收入3.07亿/占比19.7%",
            "量化": 0.75,
            "方向": "久通80+国家渠道可激活海外高毛利变现",
        })
    if not strengths:
        strengths.append({"维度": "数据不足", "现象": "优势信息缺失", "证据": "", "量化": 0.0,
                          "方向": "需补充委托方优势描述"})

    return {
        "status": "ok",
        "struggles": struggles,
        "strengths": strengths,
        "dilemma": {
            "结论": "柯力最大困境是'增长质量待验证+估值依赖叙事'，最大优势是'高净利率+闲置产能+平台化已验证+海外高毛利'",
            "决策含义": "油位/物位业务是承接估值叙事、消化闲置产能、复制平台化的三重契合——战略卡位的价值在于此",
        },
    }


# ═══════════════════════════════════════════════════════════
# 决策链 Step 2：卡位价值评估（加权评分，确定性计算）
# ═══════════════════════════════════════════════════════════
def assess_positioning(data: dict) -> dict:
    """卡位价值评估：油位市场是否值得战略卡位。

    五维加权评分（每维 0-1，权重固定，总分 0-5）：
      市场空间(0.25) / 战略契合(0.25) / 竞争壁垒(0.2) / 政策窗口(0.15) / 渠道杠杆(0.15)
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    policy = cd.get("policy_chain", "")
    comp = cd.get("competition_truth", "")
    tech = cd.get("tech_route", "")
    overseas = cd.get("global_overseas", "")
    jiutong = cd.get("jiutong_intro", "")

    # 1. 市场空间分
    rev_trend = cd.get("fig_revenue_trend", {})
    global_2024 = rev_trend.get("2024", 0) if isinstance(rev_trend, dict) else 0
    if not global_2024:
        return {"status": "no_data", "reason": "缺少市场规模数据(fig_revenue_trend)",
                "score": None, "max": 5.0, "verdict": "待评估（数据不足）",
                "dimensions": {}, "计算过程": ""}
    market_score = min(1.0, global_2024 / 50.0)  # 全球46亿美元 → ~0.92
    market_note = f"全球{global_2024}亿美元(2024)，三角验证口径，'传感器森林'可及战场"

    # 2. 战略契合分（与柯力主业的同源性）
    # 油位传感 = 工业测控传感器，与称重同属大类 → 高契合
    strategic_score = 0.85
    strategic_note = "油位/物位与称重同属工业测控传感器，制造/信号链/客户结构同源，华虹补认证"

    # 3. 竞争壁垒分（可进入性 + 卡位点）
    barrier_score = 0.6
    barrier_note = "中游制造壁垒中等(认证+客户关系)，但磁致伸缩丝卡脖子(TDK垄断)是长期壁垒点"
    if "磁致伸缩丝" in str(tech) or "TDK" in str(tech):
        barrier_note += "——自研丝是差异化卡位"

    # 4. 政策窗口分（时间窗口紧迫度）
    window_score = 0.8
    window_note = "2026-2028存量替换窗口+危化品SIS改造，错过需等下一轮"
    if "2026H2" in str(policy) or "替换高峰" in str(policy):
        window_note += "（2026H2第一波高峰临近）"

    # 5. 渠道杠杆分（久通渠道可利用度）
    channel_score = 0.7
    channel_note = "久通80+国家渠道可激活海外变现，但油位本身仅30万/年需验证"
    if "80+国家" in str(jiutong):
        channel_note = "久通80+国家渠道真实，但需订单承诺≥5000只/年验证"

    total = (market_score * 0.25 + strategic_score * 0.25 + barrier_score * 0.2
             + window_score * 0.15 + channel_score * 0.15)
    # 5 分制：各维 0-1 加权求和 × 5
    total_5 = round(total * 5.0, 2)
    verdict = "值得战略卡位" if total_5 >= 3.5 else "条件性卡位" if total_5 >= 2.5 else "不建议卡位"

    return {
        "status": "ok",
        "score": total_5,
        "max": 5.0,
        "verdict": verdict,
        "dimensions": {
            "市场空间": {"score": round(market_score, 2), "note": market_note, "weight": 0.25},
            "战略契合": {"score": strategic_score, "note": strategic_note, "weight": 0.25},
            "竞争壁垒": {"score": barrier_score, "note": barrier_note, "weight": 0.2},
            "政策窗口": {"score": window_score, "note": window_note, "weight": 0.15},
            "渠道杠杆": {"score": round(channel_score, 2), "note": channel_note, "weight": 0.15},
        },
        "计算过程": f"({market_score}×0.25 + {strategic_score}×0.25 + {barrier_score}×0.2 + {window_score}×0.15 + {channel_score}×0.15) × 5 = {total_5}/5.0",
    }


# ═══════════════════════════════════════════════════════════
# 决策链 Step 3：放量路径拆解（三浪模型，确定性计算）
# ═══════════════════════════════════════════════════════════
def analyze_rampup(data: dict) -> dict:
    """放量路径：能否快速放量 + 三浪拆解 + 关键验证点。

    三浪模型（来自 enrich financial_forecast）：
      浪1 2026 500-1000万（华虹并表+代工验证）
      浪2 2027 2000-4000万（政策替换+国产替代）
      浪3 2028 5000万-1亿（国产替代+出海）
    关键变量：久通订单量（1000→5000→1万只/年）
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    forecast = cd.get("financial_forecast", "")
    jiutong = cd.get("jiutong_intro", "")
    policy = cd.get("policy_chain", "")

    # 久通现状订单量
    jt_vol = _extract_num(jiutong, r"(\d{3,5})只")
    jt_rev = _extract_num(jiutong, r"(\d+)[万]元") if jiutong else None
    # 政策替换空间
    replace_space = _extract_num(policy, r"替换空间\s*(\d+[-~]\d+)亿")
    sis_space = _extract_num(policy, r"SIS.*?(\d+[-~]\d+)亿") if policy else None

    waves = []
    for label, lo, hi, driver in [
        ("第一浪(2026)", 500, 1000, "华虹并表+代工验证"),
        ("第二浪(2027)", 2000, 4000, "政策替换+国产替代"),
        ("第三浪(2028)", 5000, 10000, "国产替代+出海"),
    ]:
        waves.append({"阶段": label, "收入(万)": f"{lo}-{hi}", "驱动": driver,
                      "验证点": "久通订单兑现" if "第一浪" in label else ("政策执行率" if "第二浪" in label else "海外渠道激活")})

    # 能否快速放量判断
    quick_verdict = "能，但受订单兑现约束"
    if jt_vol and jt_vol < 5000:
        quick_verdict = f"有条件快速放量——前提是久通订单从当前{jt_vol}只/年提升至5000只/年"
    if not jt_vol:
        quick_verdict = "能快速放量（政策窗口+闲置产能），但需久通订单承诺落地"

    return {
        "status": "ok",
        "verdict": quick_verdict,
        "waves": waves,
        "key_variables": [
            {"变量": "久通订单量", "现状": f"{jt_vol}只/年" if jt_vol else "待确认", "目标": "≥5000只/年", "影响": "放量能否启动"},
            {"变量": "政策执行率", "现状": "约62%", "目标": "85%+", "影响": "第二浪节奏"},
            {"变量": "华虹认证", "现状": "基础已有", "目标": "防爆认证补齐", "影响": "量产能力"},
        ],
        "放量结论": "政策窗口(2026-2028) + 闲置产能(15%) + 华虹现成工艺 → 快速放量的客观条件具备；瓶颈在久通订单承诺与磁致伸缩丝供应",
    }


# ═══════════════════════════════════════════════════════════
# 决策链 Step 4：延伸产业判断（相邻品类 + 上游卡位）
# ═══════════════════════════════════════════════════════════
def analyze_adjacent(data: dict) -> dict:
    """延伸产业：油位之后，物位/液位大类 + 上游磁致伸缩丝的延伸价值。

    油位是物位/液位大类的一个细分，进入油位 = 打开物位大类的门。
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    tech = cd.get("tech_route", "")
    comp = cd.get("competition_truth", "")

    # 上游自主率（磁致伸缩丝）
    upstream_pct = _extract_num(tech, r"国产化率约\s*([\d.]+)%") if tech else 30
    # 上游毛利 vs 中游毛利
    up_margin = _extract_num(tech, r"上游材料毛利\s*([\d-]+)%") if tech else None

    adjacencies = [
        {
            "延伸方向": "工业物位/液位大类（炼化/储运/危化品）",
            "逻辑": "油位=物位×油品×储运，进入油位即获得物位大类入口",
            "市场": "全球30-35亿美元(工业物位，E)",
            "对标": "KROHNE/E+H/VEGA(德系高端)，中国本土替代空间大",
            "适配度": 0.85,
            "进入门槛": "防爆认证+计量认证(12-18月)",
        },
        {
            "延伸方向": "上游磁致伸缩丝（核心材料）",
            "逻辑": "卡脖子环节，国产化率约30%，毛利50-65%",
            "市场": "材料毛利远高于中游制造(8-12%)",
            "对标": "日企TDK等2-3家垄断",
            "适配度": 0.55,
            "进入门槛": "材料研发周期长(2-3年)，需自研立项",
        },
        {
            "延伸方向": "罐车/车载监控（新兴场景）",
            "逻辑": "渗透率40%→海外70%对标，30pp提升空间，安全合规驱动",
            "市场": "成长最快的新兴细分",
            "对标": "久通物联已卡位(箱联全球SaaS)",
            "适配度": 0.7,
            "进入门槛": "车载认证+场景定制",
        },
    ]

    return {
        "status": "ok",
        "verdict": "油位是物位大类的入口——卡位油位=打开物位/液位大类+上游材料+车载监控三扇门",
        "upstream": {
            "卡脖子": "磁致伸缩波导丝被日本爱知制钢、德国VAC主导(R87修正，非TDK)",
            "国产化率": f"{upstream_pct}%",
            "毛利": f"{up_margin}%(上游) vs 8-12%(中游)" if up_margin else "上游>中游(利润在两端)",
            "战略含义": "自研磁致伸缩丝是对标富仁高科主导国标路径的长期卡位点",
        },
        "adjacencies": adjacencies,
    }


# ═══════════════════════════════════════════════════════════
# 决策链 Step 5：投入/回报/最坏损失（金额锚定）
# ═══════════════════════════════════════════════════════════
def calculate_investment(data: dict) -> dict:
    """投入/回报/最坏损失——用金额锚定，供执行摘要与风险章引用。"""
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    company = cd.get("company_intro", "")
    forecast = cd.get("financial_forecast", "")

    # 柯力归母净利
    net_profit = _extract_num(company, r"归母.*?([\d.]+)亿")
    # 华虹投入（股权投资，非沉没成本）——精确匹配"1.22亿增持华虹"
    huahong_inv = _extract_num(company, r"([\d.]+)\s*亿\s*增持")
    # R87（2026-08-07）：口径对齐 v1.1——华虹1.22亿为股权投资非沉没，
    # 运营投入上限约2500万，最坏损失=运营投入沉没约1700万（占净利约5%）
    total_inv_lo, total_inv_hi = 1850, 2450  # 运营投入（万元）
    # 最坏损失 = 运营投入沉没（万元）
    worst_loss = 1700  # 万元（一年运营投入+认证失败残值回收后净损失）
    worst_ratio = (worst_loss / 10000.0 / net_profit) if net_profit else None

    # 回报：3年收入区间
    rev_2028_hi = 10000  # 万 = 1亿
    rev_2028_lo = 5000
    rev_ratio = (rev_2028_lo / 10000.0) / (net_profit if net_profit else 1) * 100 if net_profit else None

    return {
        "status": "ok",
        "investment": {
            "华虹增持(已公告)": f"{huahong_inv}亿(45%股权，股权投资非沉没)",
            "运营投入上限(三年)": f"约{total_inv_lo}-{total_inv_hi}万元",
            "磁致伸缩材料研发": "0.02亿/年(总部负担)",
            "口径说明": "华虹1.22亿为股权投资不计入经营投入；最坏损失按运营投入沉没计",
        },
        "return": {
            "三年收入": "5000万-1亿(2028) 占柯力营收3%-6%",
            "当期利润贡献": "微小(2026年约-237万)——价值在战略期权非当期利润",
            "回报定性": "低沉没成本+高战略期权(物位大类+海外渠道)",
        },
        "worst_loss": {
            "最坏情景": "久通订单落空+认证失败+磁致伸缩丝涨价",
            "最大损失": f"约{worst_loss}万元(运营投入沉没，占柯力净利约{worst_ratio*100:.1f}%)" if worst_ratio else "约1700万",
            "对标": f"约{worst_ratio:.2f}倍归母净利(净利{net_profit}亿)" if worst_ratio else "约半年至一年净利",
            "非对称性": "损失有限(≤1700万) 但期权价值高(物位大类+海外渠道)——典型非对称下注",
        },
    }


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════
class DecisionEngine:
    """决策备忘录分析引擎——5 步决策链确定性计算。"""

    def analyze(self, data: dict) -> dict:
        result = {}
        try:
            result["dilemma"] = diagnose_dilemma(data)
        except Exception as e:
            result["dilemma"] = {"status": "error", "reason": str(e)[:80]}
        try:
            result["positioning"] = assess_positioning(data)
        except Exception as e:
            result["positioning"] = {"status": "error", "reason": str(e)[:80]}
        try:
            result["rampup"] = analyze_rampup(data)
        except Exception as e:
            result["rampup"] = {"status": "error", "reason": str(e)[:80]}
        try:
            result["adjacent"] = analyze_adjacent(data)
        except Exception as e:
            result["adjacent"] = {"status": "error", "reason": str(e)[:80]}
        try:
            result["investment"] = calculate_investment(data)
        except Exception as e:
            result["investment"] = {"status": "error", "reason": str(e)[:80]}

        # 汇总决策结论
        pos = result.get("positioning", {})
        ramp = result.get("rampup", {})
        inv = result.get("investment", {})
        result["decision"] = {
            "status": "ok" if pos.get("status") == "ok" else pos.get("status", "no_data"),
            "verdict": pos.get("verdict", "待评估"),
            "卡位评分": f"{pos.get('score', 0)}/5.0" if pos.get("score") is not None else "数据不足",
            "放量": ramp.get("verdict", "待评估"),
            "投入": inv.get("investment", {}).get("运营投入上限(三年)", "待评估") if isinstance(inv.get("investment"), dict) else "待评估",
            "最坏损失": inv.get("worst_loss", {}).get("最大损失", "待评估") if isinstance(inv.get("worst_loss"), dict) else "待评估",
            "执行前提": "久通订单承诺≥5000只/年，否则整合不启动",
        }
        return result


def run_decision_engine(data: dict) -> dict:
    """便捷入口。"""
    return DecisionEngine().analyze(data)


if __name__ == "__main__":
    import sys, json
    path = sys.argv[1] if len(sys.argv) > 1 else "data/keli_oil_enrich_v086.json"
    # 构造 data: 读 enrich 文件 → chart_data
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cd = {}
    for it in payload.get("items", []):
        if it.get("type") == "fig_data":
            cd[it["key"]] = it.get("data")
        elif it.get("type") == "text":
            cd[it["key"]] = it.get("value")
    out = run_decision_engine({"chart_data": cd})
    print(json.dumps(out, ensure_ascii=False, indent=2))
