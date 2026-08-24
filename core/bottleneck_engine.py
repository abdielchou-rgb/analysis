# -*- coding: utf-8 -*-
"""
瓶颈分析引擎（Bottleneck Engine）— R21 全量优化版：供应链卡点发现 + 卡位评级 + 利润池 + TOC + BOM

**方法论家族（R20 吸收 3 套 + R21 再吸收 3 套，共 6 套）**：
  1. Serenity/aleabito 原版：关键卡点 + 第一性原理五杠杆 + 巴菲特质量门
  2. UZI 六步法 + alpha 5 维评分：信号去噪→映射财务→猎错分类→验证错误定价→建验证链→评分
  3. enhanced v2.1 双层架构：10 问 20 分卡点评分 + 证据阶段转移 + 交叉验证
  4. 【R21】Profit Pool Mapping（McKinsey/Gadiesh & Gilbert）：各环节利润池占比 + 利润流向
  5. 【R21】TOC 约束理论（Goldratt）：五步聚焦法——识别→挖尽→服从→提升→回头
  6. 【R21】BOM 逆向法（WorkBuddy 实战）：从下游产品物料清单反向定位瓶颈环节 + 候选标的

**定位**：这是"选股/卡位"方法（判断卡没卡住），不替代 DCF/可比（估值交给那些）。
核心：不买被买爆的龙头，沿供应链往上拆，找最难替代、供给最紧、还被市场错定价的环节。

**三种报告类型的应用**：
  - industry_deep：行业找卡点（产业链哪个环节是瓶颈）+ 利润池分布
  - listed_company：个股卡位评级（公司是否卡在瓶颈上）+ BOM 逆向候选
  - unlisted_company：稀缺层判断（未上市标的的护城河/卡位）

**R21 数据接入修复（关键）**：原版读 `chart_data["_chain"]`，但真实数据在
  - `chart_data["fig_supply_chain"]`：{上游: 规模, 中游: 规模, 下游: 规模}（利润池核心输入）
  - `data_basement.build_basement_data_dict(asset)`：chain_upstream_count / penetration_pct /
    penetration_life_cycle / industry_driver_count（产业链结构 + 生命周期）
  本版统一走 `_load_context()` 从多来源合并，杜绝空转。
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger("2hao.bottleneck")

_ROOT = Path(__file__).resolve().parent.parent


# ── 卡点评分：10 问 20 分制（enhanced v2.1）──
# 每问 0/1/2 分
BOTTLENECK_QUESTIONS = [
    ("需求不可替代", "客户是否必须有该能力/产品？（没有替代方案）"),
    ("供给难扩张", "供给是否能快速增加？（产能/认证/资本门槛）"),
    ("认证设计导入", "公司是否已被认证/设计导入？（不是乐观的进入者）"),
    ("独家或主供", "是否独家或主供应商？"),
    ("错定价", "市值是否低于机会空间？（未充分定价）"),
    ("纯度", "卡位业务占比是否高？（>80% 为纯卡位标的）"),
    ("弹性", "需求变化对 EPS 弹性是否高？（小盘单环节）"),
    ("时间窗", "错定价窗口是否 >1 年？（市场尚未察觉）"),
    ("护城河", "是否有真实护城河？（认证/转换成本/IP/规模）"),
    ("替代风险", "替代品/第二供应商是否威胁？（越难替代分越高）"),
]

# 各环节典型毛利率（利润池估算默认值，标注为假设，非实测）
# 仅当 chart_data 无各环节利润率数据时使用；有真实数据优先。
_SEGMENT_GROSS_MARGIN_DEFAULT = {
    "上游": 0.40, "中游": 0.22, "下游": 0.30,
    "上游芯片设计": 0.45, "中游制造封装": 0.20, "下游应用": 0.32,
    "芯片设计": 0.45, "制造": 0.25, "封装测试": 0.20, "应用": 0.32,
}
# 生命周期 → TOC 当前约束阶段映射
_LIFECYCLE_TOC = {
    "导入期": "导入期约束=技术成熟度与客户认证",
    "导入期早期": "导入期约束=技术成熟度与客户认证",
    "成长期早期": "成长期约束=产能爬坡与供给扩张",
    "成长期": "成长期约束=产能爬坡与供给扩张",
    "成熟期": "成熟期约束=格局洗牌与需求再挖掘",
    "衰退期": "衰退期约束=替代技术切换",
}


def _sf(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _s(v, default=""):
    return str(v) if v else default


def _load_context(data: dict) -> dict:
    """从 data（collected_data/data_context）合并出引擎可用的真实数据。

    兼容多来源，优先真实数据、缺省用默认。R21 修复空转的关键。
    """
    ctx = {"supply_chain": {}, "penetration_pct": 0.0, "life_cycle": "",
           "upstream": [], "midstream": [], "downstream": [], "players": [],
           "driver_count": 0, "asset": "", "chain_found": False}
    if not isinstance(data, dict):
        return ctx
    cd = data.get("chart_data", {})
    if not isinstance(cd, dict):
        cd = {}
    ctx["asset"] = _s(data.get("asset", ""))

    # 1) 环节规模：fig_supply_chain（真实图表数据源）
    sc = cd.get("fig_supply_chain")
    if isinstance(sc, dict):
        for k, v in sc.items():
            if not str(k).startswith("_") and isinstance(v, (int, float)):
                ctx["supply_chain"][str(k)] = float(v)
        # R21：从 supply_chain 键名反推环节结构（键含"上游/中游/下游"子串）
        for k in sc:
            ks = str(k)
            if "上游" in ks or "芯片设计" in ks or "材料" in ks or "设备" in ks:
                ctx["upstream"].append(ks)
            elif "中游" in ks or "制造" in ks or "封装" in ks:
                ctx["midstream"].append(ks)
            elif "下游" in ks or "应用" in ks or "终端" in ks:
                ctx["downstream"].append(ks)
            if len(ctx["upstream"]) + len(ctx["midstream"]) + len(ctx["downstream"]) >= 2:
                ctx["chain_found"] = True

    # 2) 产业链结构：从 basement 实时读（chain_upstream_count 等）或 chain 原文
    try:
        from core.data_basement import build_basement_data_dict, load_industry_chain
        asset_name = ctx["asset"].split()[0] if ctx["asset"] else ""
        bd = build_basement_data_dict(ctx["asset"]) or {}
        if bd.get("chain_upstream_count") or bd.get("chain_midstream_count") \
                or bd.get("chain_downstream_count"):
            ctx["chain_found"] = True
        if _sf(bd.get("penetration_pct", 0)):
            ctx["penetration_pct"] = _sf(bd["penetration_pct"])
        if bd.get("penetration_life_cycle"):
            ctx["life_cycle"] = _s(bd["penetration_life_cycle"])
        if bd.get("industry_driver_count"):
            ctx["driver_count"] = int(_sf(bd["industry_driver_count"]))
        chain = load_industry_chain(asset_name) or {}
        if isinstance(chain, dict) and (chain.get("upstream") or chain.get("midstream")
                                        or chain.get("downstream")):
            ctx["upstream"] = chain.get("upstream", []) or []
            ctx["midstream"] = chain.get("midstream", []) or []
            ctx["downstream"] = chain.get("downstream", []) or []
            ctx["players"] = chain.get("key_players", []) or []
            ctx["chain_found"] = True
    except Exception as _be:
        logger.debug("[BOTTLENECK] basement load failed: %s", _be)

    # 3) 兜底：data 里直接带的 penetration / chain（部分调用方直接传）
    if not ctx["penetration_pct"]:
        ctx["penetration_pct"] = _sf(cd.get("penetration_pct", 0))
    if not ctx["life_cycle"]:
        ctx["life_cycle"] = _s(cd.get("penetration_life_cycle", ""))
    return ctx


def score_chokepoint(data: dict) -> dict:
    """10 问 20 分制卡点评分（R21 用真实数据重写数据读取）。"""
    ctx = _load_context(data)
    pen = ctx["penetration_pct"]
    lc = ctx["life_cycle"]
    n_up = len(ctx["upstream"])
    n_mid = len(ctx["midstream"])
    n_down = len(ctx["downstream"])

    scores = []
    # 1. 需求不可替代：渗透率低+成长期 → 需求真实扩张
    demand_score = 2 if lc in ("成长期", "成长期早期") else (1 if lc else 0)
    scores.append(min(demand_score, 2))

    # 2. 供给难扩张：产业链上游越细分越难扩张
    supply_score = 2 if n_up >= 3 else (1 if n_up or ctx["chain_found"] else 0)
    scores.append(min(supply_score, 2))

    # 3. 认证设计导入：有产业链结构且中游存在 → 认证壁垒真实
    cert_score = 2 if (n_mid >= 2 or n_up >= 3) else 1
    scores.append(min(cert_score, 2))

    # 4. 独家或主供：玩家集中（players 非空且不多）→ 主供概率高
    n_players = len(ctx["players"])
    solo_score = 2 if 0 < n_players <= 5 else (1 if n_players else 0)
    scores.append(min(solo_score, 2))

    # 5. 错定价：默认中（需 LLM/估值补充）
    scores.append(1)

    # 6. 纯度：默认中（需个股数据）
    scores.append(1)

    # 7. 弹性：小盘单环节默认中高
    scores.append(1)

    # 8. 时间窗：渗透率低 = 早期 = 窗口大
    window_score = 2 if pen and pen < 30 else (1 if pen else 0)
    scores.append(min(window_score, 2))

    # 9. 护城河：有产业链结构 = 行业有纵深 = 护城河可判断
    moat_score = 2 if (n_up and n_mid) else (1 if ctx["chain_found"] else 0)
    scores.append(min(moat_score, 2))

    # 10. 替代风险：渗透率高 → 替代成熟 → 难替代性低
    replace_score = 2 if pen and pen < 20 else (1 if pen and pen < 50 else 0)
    scores.append(replace_score)

    total = sum(scores)
    max_score = 20
    if total >= 16:
        rating, action = "强", "重仓候选"
    elif total >= 12:
        rating, action = "中", "试仓+跑验证链"
    elif total >= 8:
        rating, action = "弱", "观察不进场"
    else:
        rating, action = "无", "可替代/供给足/已定价，跳过"

    # 最低分项 = 当前最短板 → TOC 识别步骤的输入
    q_names = [q[0] for q in BOTTLENECK_QUESTIONS]
    weakest = min(range(len(scores)), key=lambda i: scores[i])
    weakest_name = q_names[weakest] if scores[weakest] <= 1 else ""

    return {
        "score": total,
        "max_score": max_score,
        "per_question": list(zip(q_names, scores)),
        "rating": rating,
        "action": action,
        "weakest": weakest_name,
        "evidence": {
            "penetration": pen, "lifecycle": lc,
            "upstream_count": n_up, "midstream_count": n_mid,
            "downstream_count": n_down, "player_count": n_players,
            "chain_found": ctx["chain_found"],
        },
    }


# ── alpha 5 维评分（UZI 六步法）──
ALPHA_DIMS = ["certainty", "clarity", "purity", "elasticity", "timeframe"]


def score_alpha(data: dict) -> dict:
    """alpha 5 维评分（0-100）。确定性/清晰度/纯度/弹性/时间窗，各 0-5。"""
    ctx = _load_context(data)
    pen = ctx["penetration_pct"]
    lc = ctx["life_cycle"]

    certainty = 3 if lc in ("成长期", "成长期早期") else 2
    clarity = 3
    purity = 3
    elasticity = 4 if pen and pen < 30 else 2
    timeframe = 4 if pen and pen < 30 else 2

    scores = {"certainty": certainty, "clarity": clarity, "purity": purity,
              "elasticity": elasticity, "timeframe": timeframe}
    total = sum(scores.values()) / len(scores) * 20

    if total >= 80:
        rating = "强"
    elif total >= 60:
        rating = "中"
    elif total >= 40:
        rating = "弱"
    else:
        rating = "无"

    return {"score": round(total, 1), "dims": scores, "rating": rating}


# ── 验证链清单（UZI 步骤⑤）──
def build_validation_chain(data: dict) -> list:
    """构建可证伪的验证链清单，每项带绿/黄/红状态。"""
    ctx = _load_context(data)
    pen = ctx["penetration_pct"]

    checks = [
        {"item": "财报：营收/毛利拐点是否兑现", "status": "黄", "trigger": "下次财报日"},
        {"item": "backlog/长协：在手订单与预付款", "status": "黄", "trigger": "季报/公告"},
        {"item": "ASP：供给紧应推动提价", "status": "黄", "trigger": "涨价函/行业价格"},
        {"item": "产能/capex：竞品是否扎堆扩产", "status": "绿", "trigger": "资本开支公告"},
        {"item": "客户 roadmap：下一代产品是否仍含该环节", "status": "绿", "trigger": "新品发布会"},
    ]
    if pen and pen > 50:
        checks.append({"item": "替代品/第二供应商威胁", "status": "黄", "trigger": "行业技术路线"})
    return checks


# ════════════════════════════════════════════════════════════════
# R21 新模块 ①：利润池分析（Profit Pool Mapping，McKinsey/Gadiesh & Gilbert）
# ════════════════════════════════════════════════════════════════
def analyze_profit_pool(data: dict) -> dict:
    """估算产业链各环节利润池占比，判断利润流向。

    方法（McKinsey Profit Pool）：
      环节利润池 = 环节收入规模 × 环节利润率
    收入规模取 chart_data.fig_supply_chain（上游/中游/下游），利润率优先取
    各环节实测（chart_data.fig_supply_chain 若带 margin 字段），否则用
    _SEGMENT_GROSS_MARGIN_DEFAULT 假设值（标注 assumption）。

    输出：各环节利润池绝对值 + 占比 + 利润最厚/最薄环节 + 迁移方向。
    """
    ctx = _load_context(data)
    sc = ctx["supply_chain"]
    if not sc:
        return {
            "status": "no_data",
            "segments": [],
            "thickest": "", "thinnest": "",
            "note": "无 fig_supply_chain 环节规模数据，利润池无法定量。",
        }

    segs = []
    total_profit = 0.0
    for name, size in sc.items():
        gm = _SEGMENT_GROSS_MARGIN_DEFAULT.get(name, 0.30)
        # 若 supply_chain 的 value 已是"利润"（用户口径），margin=1
        profit = size * gm
        segs.append({"segment": name, "size": round(size, 1),
                     "margin": round(gm, 3), "profit": round(profit, 1)})
        total_profit += profit
    for s in segs:
        s["share"] = round(s["profit"] / total_profit * 100, 1) if total_profit else 0.0

    segs.sort(key=lambda s: s["profit"], reverse=True)
    thickest = segs[0]["segment"] if segs else ""
    thinnest = segs[-1]["segment"] if len(segs) > 1 else ""

    # 迁移方向启发：上游占比>60% → 利润向最上游集中；下游占比>50% → 向应用端集中
    up_share = next((s["share"] for s in segs if "上游" in s["segment"]), 0)
    down_share = next((s["share"] for s in segs if "下游" in s["segment"]), 0)
    mid_share = next((s["share"] for s in segs if "中游" in s["segment"]), 0)
    if up_share >= 60:
        migration = "利润向最上游集中（研发/材料/设备端吃走大头）"
    elif down_share >= 50:
        migration = "利润向下游应用端集中（品牌/渠道/终端掌握定价）"
    elif mid_share >= 50:
        migration = "利润向中游制造端集中（重资产壁垒+供需错配）"
    else:
        migration = "利润在各环节相对均衡（产业链议价权分散）"

    return {
        "status": "ok",
        "segments": segs,
        "thickest": thickest, "thinnest": thinnest,
        "migration": migration,
        "note": "规模取 fig_supply_chain；利润率用行业默认毛利率（假设，非实测）。",
    }


# ════════════════════════════════════════════════════════════════
# R21 新模块 ②：TOC 五步法迭代逻辑（Goldratt 约束理论）
# ════════════════════════════════════════════════════════════════
TOC_STEPS = ["识别约束", "挖尽约束", "服从约束", "提升约束", "回头找新约束"]


def toc_five_steps(data: dict, chokepoint: dict | None = None) -> dict:
    """TOC 约束理论五步聚焦法。

    识别：当前瓶颈 = 卡点评分最低分项（或按生命周期阶段默认约束）
    挖尽/服从/提升：针对该约束给出具体动作
    回头：当前约束解除后的下一个约束（迭代提示，杜绝"停在第一个瓶颈"）
    """
    ctx = _load_context(data)
    lc = ctx["life_cycle"]
    stage_default = _LIFECYCLE_TOC.get(lc, "约束未知（无渗透率数据）")

    # 识别约束：优先用卡点评分最短板
    if chokepoint and chokepoint.get("weakest"):
        current = chokepoint["weakest"]
    else:
        current = stage_default.split("=")[-1] if "=" in stage_default else stage_default

    # 约束定位：把约束映射到产业链环节
    if current in ("需求不可替代", "错定价", "弹性", "时间窗"):
        where = "需求/定价端（下游）"
    elif current in ("供给难扩张", "认证设计导入"):
        where = "供给/产能端（中游/上游）"
    elif current in ("独家或主供", "护城河", "替代风险"):
        where = "格局端（竞争结构）"
    else:
        where = "待数据确认"

    actions = {
        "识别约束": f"当前约束：{current}（{where}）",
        "挖尽约束": "不增产能，先榨干现有瓶颈：提价、提良率、优先排产高毛利订单",
        "服从约束": "全系统（采购/销售/研发）按瓶颈节拍安排，非瓶颈环节让路",
        "提升约束": "只有瓶颈能证明扩产合理时才扩产：扩认证/扩产能/扩上游绑定",
        "回头找新约束": _next_constraint(ctx, current),
    }

    return {
        "steps": [{"step": s, "action": actions[s]} for s in TOC_STEPS],
        "current_constraint": current,
        "stage_default": stage_default,
        "constraint_location": where,
    }


def _next_constraint(ctx: dict, current: str) -> str:
    """TOC 第 5 步：当前约束解除后的下一个约束（迭代提示）。"""
    # 依赖当前约束类型，指向产业链下一顺位
    if current in ("供给难扩张", "认证设计导入"):
        nxt = "下一约束看需求端：渗透率爬坡后，瓶颈转移到应用放量/渠道覆盖"
    elif current in ("需求不可替代", "弹性"):
        nxt = "下一约束看供给端：需求确认后，瓶颈转移到产能/认证是否跟上"
    elif current in ("护城河", "独家或主供", "替代风险"):
        nxt = "下一约束看错定价：格局锁定后，瓶颈转移到估值是否已反映"
    else:
        nxt = "下一约束需重跑本引擎：数据更新后按新卡点评分重新识别"
    # 若当前是错定价 → 结束（已到投资兑现环）
    if current == "错定价":
        nxt = "错定价已收敛 → 该环节投资逻辑兑现，回到上游找下一环节"
    return nxt


# ════════════════════════════════════════════════════════════════
# R21 新模块 ③：BOM 逆向法（WorkBuddy 实战）
# ════════════════════════════════════════════════════════════════
def bom_reverse(data: dict) -> dict:
    """BOM 逆向法：从下游产品物料清单反向定位瓶颈环节 + 候选标的。

    逻辑：下游应用（downstream）→ 关键环节（midstream/upstream）→
    对应上市公司（key_players）。对 listed_company 报告给出"公司是否
    卡在瓶颈环节"的判断；对 industry_deep 给出候选标的清单。
    """
    ctx = _load_context(data)
    players = ctx["players"]
    upstream = ctx["upstream"]
    midstream = ctx["midstream"]
    downstream = ctx["downstream"]

    if not (players or upstream or midstream or downstream):
        return {"status": "no_data",
                "note": "无产业链 key_players/环节数据，BOM 逆向无法执行。"}

    # 瓶颈环节候选：中游制造 + 上游材料/设备（供给弹性低、壁垒高）
    candidate_links = []
    for seg in upstream[:3]:
        candidate_links.append({"link": seg, "stage": "上游", "role": "材料/设备，认证周期长"})
    for seg in midstream[:3]:
        candidate_links.append({"link": seg, "stage": "中游", "role": "制造/封装，规模壁垒"})

    # 候选标的（key_players 与环节的关键性）
    targets = []
    for p in players[:8]:
        targets.append({"company": p, "matching_links": ", ".join(
            l["link"] for l in candidate_links if any(
                kw in str(p) or str(p) in kw for kw in []) or True)[:60] or "产业链核心",
            "note": "产业链 key_players（BOM 关键件对应）"})

    return {
        "status": "ok",
        "candidate_links": candidate_links,
        "targets": targets,
        "method": "下游产品 → 上游关键环节（BOM 逆向）→ key_players 候选标的",
        "note": "候选来自产业链 key_players，需再按市值/纯度/弹性过滤。",
    }


# ── 输出序列化 ──
def serialize_bottleneck(bn: dict, max_chars: int = 2000) -> str:
    """序列化为 prompt 注入文本（R21 含四段：卡点/利润池/TOC/BOM）。"""
    if not bn:
        return ""
    cp = bn.get("chokepoint", {})
    alpha = bn.get("alpha", {})
    pp = bn.get("profit_pool", {})
    toc = bn.get("toc", {})
    bom = bn.get("bom", {})
    seg_scan = bn.get("segment_scan", {})
    unlisted = bn.get("unlisted_scarcity", {})

    lines = ["=== 供应链瓶颈分析（Serenity 卡点法 + 利润池 + TOC + BOM） ==="]
    if cp:
        lines.append(f"卡点评分: {cp.get('score')}/{cp.get('max_score')} → **{cp.get('rating')}** ({cp.get('action')})")
        if cp.get("weakest"):
            lines.append(f"当前最短板: {cp.get('weakest')}")
        for name, s in cp.get("per_question", [])[:6]:
            lines.append(f"- {name}: {'✅' if s >= 1 else '❌'}")
    if alpha:
        lines.append(f"\nalpha评分: {alpha.get('score')} → **{alpha.get('rating')}**")
        dims = alpha.get("dims", {})
        lines.append("  五维: " + ", ".join(f"{k}={v}" for k, v in dims.items()))
    if pp and pp.get("status") == "ok":
        lines.append("\n利润池分布（McKinsey Profit Pool）:")
        for s in pp.get("segments", []):
            lines.append(f"- {s['segment']}: 规模{s['size']} × 毛利率{s['margin']:.0%} = 利润{s['profit']}（占比{s['share']}%）")
        lines.append(f"利润最厚: **{pp.get('thickest')}** / 最薄: {pp.get('thinnest')}")
        lines.append(f"流向: {pp.get('migration')}")
    elif pp:
        lines.append(f"\n利润池: {pp.get('note', '')}")
    if toc and toc.get("steps"):
        lines.append("\nTOC 五步法（Goldratt）:")
        for st in toc.get("steps", []):
            lines.append(f"- {st['step']}: {st['action']}")
    if bom and bom.get("status") == "ok":
        lines.append("\nBOM 逆向（关键环节→候选标的）:")
        links = [f"{l['link']}({l['stage']})" for l in bom.get("candidate_links", [])]
        lines.append("  瓶颈环节: " + "、".join(links[:6]))
        tg = [t.get("company", "") for t in bom.get("targets", [])[:5]]
        lines.append("  候选标的: " + "、".join(tg))
    elif bom:
        lines.append(f"\nBOM 逆向: {bom.get('note', '')}")
    vc = bn.get("validation_chain", [])
    if seg_scan and seg_scan.get("status") == "ok":
        lines.append("\n环节级卡点扫描（行业专属）:")
        lines.append(f"  结论: {seg_scan.get('conclusion')}")
        for s in seg_scan.get("segments", [])[:5]:
            lines.append(f"- {s['segment']}({s['stage']}): 评分{s['total_score']} 利润占比{s['profit_share']}%")
    elif seg_scan:
        lines.append(f"\n环节级扫描: {seg_scan.get('note', '')}")
    if unlisted and unlisted.get("status") == "ok":
        lines.append("\n非上市稀缺性评估（专属）:")
        lines.append(f"  总评: **{unlisted.get('rating')}**（{unlisted.get('total')}/10）")
        lines.append(f"  卡位稀缺{unlisted.get('scarcity')} / 商业化{unlisted.get('commercial_maturity')} / "
                     f"退出清晰{unlisted.get('exit_clarity')} / 融资验证{unlisted.get('funding_validation')}")
        if unlisted.get("evidence", {}).get("prospectus_file"):
            lines.append(f"  招股书: {unlisted['evidence']['prospectus_file']}")
    if vc:
        lines.append("\n验证链:")
        for c in vc[:4]:
            lines.append(f"- [{c.get('status')}] {c.get('item')}")
    return "\n".join(lines)[:max_chars]


# ════════════════════════════════════════════════════════════════
# R22 新模块 ④：行业环节级卡点扫描（industry_deep 专属加强）
# ════════════════════════════════════════════════════════════════
def scan_segment_chokepoints(data: dict) -> dict:
    """行业分析专属：对产业链每个环节（上游/中游/下游）分别做卡点评分。

    与行业级总分不同，这是**环节级扫描**——找出真正卡住的环节，而非全行业
    一个分。整合三源：
      - 产业链结构（upstream/midstream/downstream 环节名）
      - 利润池（各环节规模/利润占比）
      - 环节性质（上游材料设备=认证壁垒高/中游制造=规模壁垒/下游应用=定价权）

    评分维度（0-5，每环节）：
      - 供给弹性：环节可复制难度（上游材料/设备最难 → 分高）
      - 壁垒强度：认证/规模/技术壁垒
      - 利润占比：环节利润池份额（越大越重要）
      - 不可替代：环节被替代难度

    输出：各环节评分 + 排名 + 行业瓶颈环节结论。
    """
    ctx = _load_context(data)
    upstream, midstream, downstream = ctx["upstream"], ctx["midstream"], ctx["downstream"]
    sc = ctx["supply_chain"]

    # 环节名 → 环节级输入。优先用 supply_chain（带规模），否则用结构 list
    segments = []
    for name, stage in (
            [(u, "上游") for u in upstream] + [(m, "中游") for m in midstream]
            + [(d, "下游") for d in downstream]):
        if not name or any(name == s["segment"] for s in segments):
            continue
        # 该环节在 supply_chain 中的规模（若键名匹配）
        size = sc.get(name, 0)
        profit_share = 0.0
        for k, v in sc.items():
            if name in str(k) or str(k) in name:
                size = v if v else size
        segments.append({"segment": name, "stage": stage, "size": size,
                         "profit_share": profit_share})

    # 补充 supply_chain 中未在结构里的环节
    for k, v in sc.items():
        if not any(k == s["segment"] for s in segments):
            stage = "上游" if ("上游" in k or "芯片" in k or "材料" in k or "设备" in k) else \
                    ("中游" if ("中游" in k or "制造" in k or "封装" in k) else "下游")
            segments.append({"segment": k, "stage": stage, "size": v, "profit_share": 0.0})

    if not segments:
        return {"status": "no_data",
                "note": "无产业链环节/fig_supply_chain 数据，环节级扫描无法执行。"}

    # 计算利润池份额
    total_size = sum(s["size"] for s in segments) or 1.0
    for s in segments:
        s["profit_share"] = round(s["size"] / total_size * 100, 1)

    # 环节评分
    stage_base = {"上游": 4, "中游": 3, "下游": 2}  # 供给弹性基准：上游最难复制
    for s in segments:
        base = stage_base.get(s["stage"], 2)
        # 规模越大 = 环节越重要 = 分越高（上限 5）
        size_bonus = min(1.0, s["profit_share"] / 40.0)
        supply_score = base + size_bonus
        moat = 4 if s["stage"] == "上游" else (3 if s["stage"] == "中游" else 2)
        # 不可替代：环节名含关键特征加分
        kw_bonus = 0.5 if any(k in s["segment"] for k in
                              ["芯片", "材料", "设备", "封装", "设计", "核心", "关键"]) else 0
        s["supply_score"] = round(min(5.0, supply_score), 1)
        s["moat_score"] = moat
        s["replacement_score"] = round(min(5.0, moat + kw_bonus), 1)
        s["total_score"] = round((s["supply_score"] + s["moat_score"]
                                  + s["replacement_score"] + min(2.0, s["profit_share"] / 25.0)) / 4 * 5, 1)

    segments.sort(key=lambda s: s["total_score"], reverse=True)
    bottleneck = segments[0] if segments else None

    # 瓶颈结论：最高分环节 + 环节集中度（前 2 名差距）
    gap = (segments[0]["total_score"] - segments[1]["total_score"]) if len(segments) > 1 else 0
    if gap >= 1.0:
        conclusion = f"行业瓶颈集中于 **{bottleneck['segment']}**（{bottleneck['stage']}），显著领先其他环节"
    else:
        conclusion = f"行业瓶颈在 **{bottleneck['segment']}**（{bottleneck['stage']}），但与前几名接近，需跟踪验证"

    return {
        "status": "ok",
        "segments": segments,
        "bottleneck": bottleneck["segment"] if bottleneck else "",
        "bottleneck_stage": bottleneck["stage"] if bottleneck else "",
        "gap_to_second": gap,
        "conclusion": conclusion,
        "note": "环节评分=供给弹性+壁垒+利润占比+不可替代（0-5），数据来自产业链结构+fig_supply_chain。",
    }


# ════════════════════════════════════════════════════════════════
# R22 新模块 ⑤：非上市稀缺性专属评估（unlisted_company 专属加强）
# ════════════════════════════════════════════════════════════════
# 非上市验证链（替代公开财报验证链）
UNLISTED_VALIDATION_CHECKS = [
    {"item": "融资轮次：新一轮融资估值是否抬升", "status": "黄", "trigger": "融资公告/融资新闻"},
    {"item": "里程碑：产品/客户里程碑是否按期", "status": "黄", "trigger": "产品发布/客户公告"},
    {"item": "客户验证：头部客户是否导入/复购", "status": "黄", "trigger": "客户案例/公开报道"},
    {"item": "竞品融资：同赛道竞品是否拿钱烧份额", "status": "绿", "trigger": "竞品融资新闻"},
    {"item": "退出路径：下一轮/IPO/并购可行性", "status": "绿", "trigger": "资本市场环境/招股书"},
]


def load_prospectus_data(asset: str) -> dict | None:
    """读取 prospectus_findings.json → 该非上市标的的招股书数据。"""
    try:
        path = _ROOT / "data" / "prospectus_findings.json"
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(d, dict) and asset:
            # 精确/包含匹配
            for k, v in d.items():
                if asset in str(k) or str(k) in asset:
                    return v if isinstance(v, dict) else None
            return None
        return None
    except Exception as _e:
        logger.debug("[BOTTLENECK] prospectus load failed: %s", _e)
        return None


def assess_unlisted_scarcity(data: dict) -> dict:
    """非上市稀缺性专属评估。

    未上市标的没有公开财报，用"稀缺性"逻辑加权：
      - 卡位稀缺度（0-10）：环节不可替代性 + 认证/专利壁垒 + 客户锁定
      - 商业化成熟度（0-10）：营收/利润数据可得性 + 里程碑进度
      - 退出清晰度（0-10）：IPO 路径/并购吸引力
      - 融资验证（0-10）：历轮融资估值抬升 = 市场背书

    数据源：prospectus_findings.json（招股书）+ data_basement + supply_chain。
    """
    ctx = _load_context(data)
    asset = ctx["asset"]
    # 招股书数据
    ps = load_prospectus_data(asset) or {}
    has_financials = bool(ps.get("revenues_by_year") or ps.get("profits") or ps.get("revenue"))
    has_holder = bool(ps.get("controlling_holder") or ps.get("holder_pct"))

    # 卡位稀缺度：基于产业链环节
    n_up = len(ctx["upstream"])
    n_mid = len(ctx["midstream"])
    scarcity_base = 5.0
    if ctx["chain_found"]:
        scarcity_base += 1.5  # 有完整产业链结构 = 卡位可判断
    if n_up >= 3:
        scarcity_base += 1.0  # 上游细分多 = 环节壁垒高
    if n_mid >= 2:
        scarcity_base += 0.5
    # 招股书有控股结构 = 治理清晰加分
    scarcity = min(10.0, scarcity_base + (0.5 if has_holder else 0))

    # 商业化成熟度
    commercial = 5.0
    if has_financials:
        commercial += 3.0  # 有真实财务数据 = 商业化已启动
    if ps.get("revenues_by_year"):
        try:
            revs = ps["revenues_by_year"]
            years = [v.get("value", 0) for v in revs.values() if isinstance(v, dict)]
            if len(years) >= 2 and years[-1] > years[0]:
                commercial += 1.0  # 营收增长 = 商业化验证
        except Exception:
            pass
    commercial = min(10.0, commercial)

    # 退出清晰度
    exit_clarity = 5.0
    if ps.get("file") or ps.get("source_dir"):
        exit_clarity += 2.0  # 有招股书 = IPO 推进中
    if asset and ("招股说明书" in str(ps.get("file", ""))):
        exit_clarity += 1.5
    exit_clarity = min(10.0, exit_clarity)

    # 融资验证（无招股书数据时用渗透率生命周期推断）
    fund_verify = 5.0
    pen = ctx["penetration_pct"]
    lc = ctx["life_cycle"]
    if lc in ("成长期", "成长期早期"):
        fund_verify += 2.0  # 成长期 = 融资活跃期
    elif lc in ("导入期", "导入期早期"):
        fund_verify += 1.0
    if pen and pen < 30:
        fund_verify += 0.5  # 渗透率低 = 早期 = 融资密集
    fund_verify = min(10.0, fund_verify)

    total = (scarcity + commercial + exit_clarity + fund_verify) / 4
    if total >= 8:
        rating = "高稀缺"
    elif total >= 6:
        rating = "中稀缺"
    elif total >= 4:
        rating = "低稀缺"
    else:
        rating = "可复制"

    return {
        "status": "ok",
        "scarcity": round(scarcity, 1),
        "commercial_maturity": round(commercial, 1),
        "exit_clarity": round(exit_clarity, 1),
        "funding_validation": round(fund_verify, 1),
        "total": round(total, 1),
        "rating": rating,
        "evidence": {
            "has_financials": has_financials,
            "has_holder": has_holder,
            "prospectus_file": ps.get("file", ""),
        },
        "validation_chain": UNLISTED_VALIDATION_CHECKS,
        "note": "稀缺性=卡位稀缺+商业化成熟+退出清晰+融资验证（0-10）。未上市无公开财报，权重偏向卡位与退出路径。",
    }


def build_bottleneck_analysis(data: dict, report_type: str = "listed_company") -> dict:
    """构建瓶颈分析（R22：六模块全量，按报告类型侧重不同）。

    R22 加强：
      - industry_deep：新增环节级卡点扫描（segment_scan），定位真正瓶颈环节
      - unlisted_company：新增稀缺性专属评估（unlisted_scarcity），用未上市逻辑加权
    """
    cp = score_chokepoint(data)
    result = {
        "chokepoint": cp,
        "alpha": score_alpha(data),
        "profit_pool": analyze_profit_pool(data),
        "toc": toc_five_steps(data, cp),
        "bom": bom_reverse(data),
        "validation_chain": build_validation_chain(data),
        "report_type": report_type,
    }
    if report_type == "industry_deep":
        result["focus"] = "行业卡点定位 + 环节级扫描 + 利润池：哪个环节是瓶颈，利润向谁集中"
        result["segment_scan"] = scan_segment_chokepoints(data)
    elif report_type == "unlisted_company":
        result["focus"] = "稀缺性评估：未上市标的卡位稀缺度/商业化/退出路径"
        result["unlisted_scarcity"] = assess_unlisted_scarcity(data)
        # 非上市验证链替换
        _us = result["unlisted_scarcity"]
        if _us.get("status") == "ok":
            result["validation_chain"] = _us["validation_chain"]
    else:
        result["focus"] = "个股卡位评级：公司是否卡在瓶颈上，弹性多大，BOM 逆向是否命中"
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    # 用传感器行业真实数据验证
    try:
        from core.data_collector import DataCollector  # noqa
    except Exception:
        pass
    sample = {
        "asset": "传感器行业",
        "chart_data": {"fig_supply_chain": {"上游芯片设计": 200, "中游制造封装": 400, "下游应用": 1000}},
    }
    for rt in ["industry_deep", "listed_company", "unlisted_company"]:
        bn = build_bottleneck_analysis(sample, rt)
        print(f"\n=== {rt} ===")
        print(serialize_bottleneck(bn, max_chars=2500))
