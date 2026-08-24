"""数据契约校验 — R78 Phase1.1。

为 chart_data 和 enrich_file 定义结构约束（JSON Schema 风格），
防止结构漂移导致下游静默失败。

用法：
    from core.data_contract import validate_chart_data, validate_enrich_file, validate_enrich_item
"""

from __future__ import annotations

import logging

logger = logging.getLogger("2hao.data_contract")

# ── enrich_file 契约 ─────────────────────────────────────────
# 顶层：{asset, generated_by, items: [...]}
# item.type ∈ {fig_data, news, text}
# fig_data 必含: key(白名单内), data(dict/list 非空), source(非空)
# news 必含: items(非空列表), source
# text 必含: key, value(非空), source

# R78（2026-08-05 Phase1.1）：白名单从 data_enrichment 导入（单一事实源），
# 避免双份维护导致契约与实际允许键不一致（曾漏 fig_players/fig_applications 等）。
try:
    from pipeline.data_enrichment import ALLOWED_FIG_KEYS
except Exception:
    ALLOWED_FIG_KEYS = set()


def validate_enrich_item(item: dict) -> tuple[bool, str]:
    """校验单个 enrich item。返回 (ok, reason)。"""
    if not isinstance(item, dict):
        return False, "item 非 dict"
    itype = item.get("type", "")
    source = item.get("source", "").strip()
    if not source:
        return False, "缺 source（FP2 数据溯源必须）"
    if itype == "fig_data":
        key = item.get("key", "")
        if key not in ALLOWED_FIG_KEYS:
            return False, f"key 不在白名单: {key}"
        data = item.get("data")
        if not isinstance(data, (dict, list)) or not data:
            return False, "fig_data.data 必须为非空 dict/list"
        return True, ""
    elif itype == "news":
        items = item.get("items", [])
        if not isinstance(items, list) or not items:
            return False, "news.items 必须为非空列表"
        return True, ""
    elif itype == "text":
        key = item.get("key", "")
        value = item.get("value", "")
        if not key or not value:
            return False, "text 必须含 key 和 value"
        return True, ""
    else:
        return False, f"未知 type: {itype}"


def validate_enrich_file(payload: dict) -> tuple[bool, list[str]]:
    """校验整个 enrich_file。返回 (ok, reasons)。"""
    reasons = []
    if not isinstance(payload, dict):
        return False, ["enrich_file 顶层非 dict"]
    items = payload.get("items", [])
    if not isinstance(items, list):
        return False, ["items 非列表"]
    for i, item in enumerate(items):
        ok, reason = validate_enrich_item(item)
        if not ok:
            reasons.append(f"item[{i}]: {reason}")
    return (len(reasons) == 0), reasons


# ── chart_data 契约 ──────────────────────────────────────────
# fig_* 键 → 值类型约束（扁平 dict 或复合 dict 兼容）
CHART_DATA_RULES = {
    "fig_revenue_trend": ("dict", "营收趋势: 年份→数值"),
    "fig_profitability": ("dict", "盈利能力: 年份→数值"),
    "fig_margin": ("dict", "毛利率: 年份→数值"),
    "fig_qlib_price": ("dict", "价格/净值: latest 或 年份→数值"),
    "fig_market_size_global": ("dict", "全球市场规模"),
    "fig_market_size_china": ("dict", "中国市场规模"),
    "fig_market_share": ("dict", "市占率"),
    "fig_peer_comparison": ("dict", "对标"),
    "fig_business_segments": ("dict", "业务分部"),
    "fig_capital_flow": ("dict", "资金面"),
    "company_intro": ("str", "公司简介文本"),
}


def validate_chart_data(chart_data: dict) -> tuple[bool, list[str]]:
    """校验 chart_data 结构。返回 (ok, problems)。"""
    if not isinstance(chart_data, dict):
        return False, ["chart_data 非 dict"]
    problems = []
    for key, (expected_type, desc) in CHART_DATA_RULES.items():
        if key not in chart_data:
            continue
        val = chart_data[key]
        if expected_type == "dict" and not isinstance(val, dict):
            problems.append(f"{key} 应为 dict（{desc}），实际 {type(val).__name__}")
        elif expected_type == "str" and not isinstance(val, str):
            problems.append(f"{key} 应为 str（{desc}），实际 {type(val).__name__}")
    return (len(problems) == 0), problems


def validate_enrich_file_merge(data: dict, enrich_file: str) -> tuple[bool, list[str]]:
    """enrich 合并后校验（enrich_node 调用）。"""
    problems = []
    # 1. enrich_file 本身合规
    try:
        import json
        from pathlib import Path

        payload = json.loads(Path(enrich_file).read_text(encoding="utf-8"))
        ok, reasons = validate_enrich_file(payload)
        if not ok:
            problems.extend(reasons)
    except Exception as e:
        problems.append(f"enrich_file 解析失败: {str(e)[:80]}")
    # 2. chart_data 结构
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    ok2, p2 = validate_chart_data(cd)
    if not ok2:
        problems.extend(p2)
    return (len(problems) == 0), problems


if __name__ == "__main__":
    # 自测
    good = {
        "asset": "x",
        "items": [{"type": "fig_data", "key": "fig_market_size_global", "data": {"2024": 46}, "source": "测试"}],
    }
    ok, reasons = validate_enrich_file(good)
    print("good enrich:", ok, reasons)
    bad = {"asset": "x", "items": [{"type": "fig_data", "key": "bad_key", "data": {}, "source": ""}]}
    ok2, reasons2 = validate_enrich_file(bad)
    print("bad enrich:", ok2, reasons2)


# ── financials.db 契约 ───────────────────────────────────────
# 表结构: financials(code, quarter, table_name, field, value, source)
# table_name ∈ {profit, balance, cashflow}
# 关键 field 按表约束

FINANCIALS_TABLES = {"profit", "balance", "cashflow"}

# 每表应有（未出现即视为覆盖缺口）的关键字段
# R78（2026-08-05）：cashflow 实际命名是 OCF/ICF/FCF/capex（非 netCashFlow），
# 契约按实际数据修正，避免误报。
FINANCIALS_REQUIRED_FIELDS = {
    "profit": ["MBRevenue", "netProfit", "epsTTM", "gpMargin", "roeAvg"],
    "balance": ["totalAssets", "totalLiab", "totalEquity"],
    "cashflow": ["OCF", "ICF", "FCF", "capex", "DA"],
}


def check_financials_coverage(db_path: str, code: str = "") -> dict:
    """检查 financials.db 对某标的的覆盖率。

    返回 {code, tables: {profit: {fields: [...], coverage: 0.x}}, total_coverage}
    """
    import sqlite3
    from pathlib import Path

    result = {"code": code, "tables": {}, "total_coverage": 0.0}
    if not Path(db_path).exists():
        return result
    try:
        conn = sqlite3.connect(db_path)
        where = "WHERE code=?" if code else ""
        params = (code,) if code else ()
        for table in FINANCIALS_TABLES:
            rows = conn.execute(
                f"SELECT DISTINCT field FROM financials WHERE table_name=? {where}",
                ((table,) + params) if params else (table,),
            ).fetchall()
            fields = {r[0] for r in rows}
            required = FINANCIALS_REQUIRED_FIELDS.get(table, [])
            present = [f for f in required if f in fields]
            result["tables"][table] = {
                "present_fields": present,
                "missing_fields": [f for f in required if f not in fields],
                "coverage": round(len(present) / max(len(required), 1), 2),
            }
        covs = [t["coverage"] for t in result["tables"].values()]
        result["total_coverage"] = round(sum(covs) / max(len(covs), 1), 2) if covs else 0.0
        conn.close()
    except Exception as e:
        result["error"] = str(e)[:80]
    return result


if __name__ == "__main__":
    # 自测 financials
    from pathlib import Path

    db = Path(__file__).resolve().parent.parent / "data" / "financials.db"
    r = check_financials_coverage(str(db))
    print("financials 全库:", {k: r["tables"][k]["coverage"] for k in r["tables"]})


# ── 信息来源分级（R80 Phase3 合规红线）────────────────────────
# 券商合规三原则：公开/半公开/敏感分级；敏感不入报告正文。
# enrich-file 的每个 item.source 应能映射到分级：
#   A_public  = 公开可查（公告/财报/招标平台/官方政策）
#   B_licensed = 付费/权威第三方（wind/行业协会，需授权）
#   C_sensitive = 未公开访谈/内幕（禁止入报告正文）
import re as _re

_SENSITIVE_PATTERNS = [
    r"(访谈|拜访|尽调|电话会|专家).{0,20}(未公开|内部|独家|非公开)",
    r"(某.{0,6}(客户|供应商|采购经理)|业内人士).{0,20}(反馈|透露|表示|称)",
    r"(招标量|订单|中标).{0,20}(下季度|内部|提前|未公布)",
]


def classify_source(source: str) -> str:
    """把来源字符串映射到分级 A/B/C。"""
    if not source:
        return "C_sensitive"  # 无来源默认敏感（保守）
    if any(_re.search(p, source) for p in _SENSITIVE_PATTERNS):
        return "C_sensitive"
    if _re.search(r"(访谈|调研|走访|专家)", source):
        return "C_sensitive"
    if _re.search(r"(wind|choice|付费|licensed|授权)", source, _re.I):
        return "B_licensed"
    return "A_public"


def validate_report_sources(items: list[dict]) -> tuple[bool, list[str]]:
    """校验 enrich items 无敏感来源入报告正文。

    C_sensitive 的 item 若标记 type=fig_data/text（会进正文）→ 违规。
    只允许 C_sensitive 影响判断方向（如 notes），不进正文。
    """
    violations = []
    for i, item in enumerate(items):
        src = item.get("source", "")
        grade = classify_source(src)
        if grade == "C_sensitive" and item.get("type") in ("fig_data", "text"):
            violations.append(f"item[{i}] 敏感来源({src[:30]})不能进报告正文")
    return (len(violations) == 0), violations
