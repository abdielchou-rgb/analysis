# -*- coding: utf-8 -*-
"""
可比公司对标矩阵（Peer Matrix）— R30 模块9b：对标麦肯锡/咨询

**问题**：2hao 报告里有零散可比对比，但没有结构化对标矩阵（估值/增速/ROE/利润率逐项）。
对标咨询：指标 vs 行业基准，一眼看出高低。

**方案**：标的 vs 同行业可比公司（global_leaders + financials.db）→ 多指标矩阵。
"""
from __future__ import annotations
import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger("2hao.peer_matrix")

_ROOT = Path(__file__).resolve().parent.parent
LEADERS = _ROOT / "data" / "global_leaders.json"
FIN_DB = _ROOT / "data" / "financials.db"

# 指标 → 描述
METRICS = ["pe_ttm", "revenue", "net_profit", "market_cap", "roe"]


def _load_leaders() -> list[dict]:
    if not LEADERS.exists():
        return []
    try:
        d = json.loads(LEADERS.read_text(encoding="utf-8"))
        return d.get("leaders", []) if isinstance(d, dict) else d
    except Exception:
        return []


def _company_financials(code: str) -> dict:
    """从 financials.db 取标的最近财务。"""
    if not FIN_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(str(FIN_DB))
        row = conn.execute(
            "SELECT quarter, field, value FROM financials WHERE code=? "
            "ORDER BY quarter DESC LIMIT 200", (code,)).fetchall()
        conn.close()
        # 取最新季度
        latest_q = None
        fields = {}
        for q, f, v in row:
            if latest_q is None:
                latest_q = q
            if q == latest_q:
                fields[f] = v
        return fields
    except Exception:
        return {}


def build_peer_matrix(code: str, asset_name: str = "", industry: str = "") -> dict:
    """构建对标矩阵。

    Args:
        code: 标的代码（6位）
        asset_name: 标的名
        industry: 行业提示（用于匹配可比）
    """
    leaders = _load_leaders()
    if not leaders:
        return {"status": "no_data", "note": "global_leaders 无数据"}

    # 标的财务
    fin = _company_financials(code)
    target = {
        "name": asset_name or code,
        "code": code,
        "revenue": fin.get("MBRevenue", 0) / 1e8 if fin.get("MBRevenue") else None,
        "net_profit": fin.get("netProfit", 0) / 1e8 if fin.get("netProfit") else None,
        "roe": fin.get("roeAvg"),
    }

    # 匹配可比：同行业（industry 匹配或代码同段）
    peers = []
    if industry:
        for l in leaders:
            if industry in str(l.get("industry", "")):
                peers.append(l)
    # 若行业没匹配到，用全库 top 市值做参考
    if not peers:
        peers = sorted(leaders, key=lambda x: x.get("market_cap_b", 0), reverse=True)[:5]

    rows = []
    for p in peers[:8]:
        rows.append({
            "name": p.get("company", ""),
            "ticker": p.get("ticker", ""),
            "industry": p.get("industry", ""),
            "pe": p.get("pe_ttm"),
            "revenue_b": p.get("revenue_ttm_m", 0) / 1000 if p.get("revenue_ttm_m") else None,
            "net_profit_b": p.get("net_income_ttm_m", 0) / 1000 if p.get("net_income_ttm_m") else None,
            "market_cap_b": p.get("market_cap_b"),
        })

    # 计算目标 vs 可比均值偏离
    pe_list = [r["pe"] for r in rows if r.get("pe")]
    if pe_list:
        avg_pe = sum(pe_list) / len(pe_list)
    else:
        avg_pe = None

    return {
        "status": "ok",
        "target": target,
        "peers": rows,
        "peer_avg_pe": round(avg_pe, 1) if avg_pe else None,
        "industry": industry,
        "note": "对标 global_leaders 同行业可比；财务单位=亿元",
    }


def serialize_matrix(m: dict) -> str:
    """序列化注入 prompt。"""
    if not m or m.get("status") != "ok":
        return ""
    lines = ["=== 可比公司对标矩阵（对标咨询） ===",
             f"标的: {m['target'].get('name')} | 行业: {m.get('industry') or '未指定'}"]
    if m["target"].get("revenue"):
        lines.append(f"  {m['target']['name']}: 营收{m['target']['revenue']:.1f}亿 "
                     f"净利{m['target'].get('net_profit', 0):.1f}亿")
    lines.append("  可比公司:")
    for r in m["peers"]:
        pe = f"{r['pe']:.0f}x" if r.get("pe") else "N/A"
        lines.append(f"    {r['name']}({r['ticker']}): PE {pe}, "
                     f"市值{r.get('market_cap_b', 0):.0f}亿美元")
    if m.get("peer_avg_pe"):
        t_pe = "N/A"
        lines.append(f"  可比平均PE: {m['peer_avg_pe']}x")
    return "\n".join(lines)


if __name__ == "__main__":
    m = build_peer_matrix("603662", "柯力传感", "半导体")
    print(serialize_matrix(m))
