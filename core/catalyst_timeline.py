# -*- coding: utf-8 -*-
"""
催化剂日历（Catalyst Timeline）— R23 王牌方法：把投资逻辑变成可验证的时间轴

**核心**：投行深度报告和普通报告的区别，是把"我认为这家公司会涨"翻译成
"在未来哪些时间点，什么事件会验证/证伪我的判断"。催化剂日历就是这张时间轴。

**两种模式**：
  - listed_company / industry_deep：财报季 + 政策节点 + 行业技术节点 + 生命周期事件
  - unlisted_company：融资轮 + 里程碑 + IPO 申报 + 客户验证节点

**数据源**：
  - 公司事件（data_basement.load_company_events）：分红/股本变动
  - 政策库（data_basement.load_policy）：按行业匹配政策日期/方向
  - 产业链结构（industry_chain）：行业技术节点
  - 生命周期（渗透率）：行业阶段事件

所有日期标记为 (E)/(A) 来源标注，无来源的事件标注为假设。
"""
from __future__ import annotations
import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

logger = logging.getLogger("2hao.catalyst")

_ROOT = Path(__file__).resolve().parent.parent


def _q_of(month: int) -> int:
    return (month - 1) // 3 + 1


def _quarter_label(q: int, year: int) -> str:
    return f"{year}Q{q}"


def next_earnings_window(now: date | None = None) -> str:
    """下一个财报披露窗口（A股：年报4月底前、一季报4月底、中报8月底、三季报10月底）。"""
    now = now or date.today()
    m = now.month
    if m <= 4:
        return f"{now.year}年4月底（{now.year}年报 + 一季报）"
    if m <= 8:
        return f"{now.year}年8月底（{now.year}中报）"
    if m <= 10:
        return f"{now.year}年10月底（{now.year}三季报）"
    return f"{now.year+1}年4月底（{now.year}年报）"


def build_catalyst_timeline(data: dict, report_type: str = "listed_company") -> dict:
    """构建催化剂日历（季度时间轴）。

    返回 dict：{status, timeline:[{quarter, events:[{type, desc, source}]}],
               next_catalyst, key_dates}
    """
    cd = data.get("chart_data", {}) if isinstance(data, dict) else {}
    if not isinstance(cd, dict):
        cd = {}
    asset = data.get("asset", "") if isinstance(data, dict) else ""
    asset_name = asset.split()[0] if asset else ""
    now = date.today()

    events_by_q = {}  # (year, q) -> list of events

    def _add(year, q, etype, desc, source):
        key = (year, q)
        events_by_q.setdefault(key, []).append(
            {"type": etype, "desc": desc, "source": source})

    # ── 1. 常规财报催化（所有类型）──
    y, m = now.year, now.month
    q = _q_of(m)
    _add(y, q, "财报", f"当季财报/业绩披露窗口（{_quarter_label(q, y)}）", "A/日历")
    # 未来 4 个季度
    for offset in range(1, 5):
        _y, _q = y, q
        for _ in range(offset):
            _q += 1
            if _q > 4:
                _q = 1
                _y += 1
        _add(_y, _q, "财报", f"季度财报/业绩披露窗口", "A/日历")

    # ── 2. 公司事件（个股）──
    try:
        from core.data_basement import load_company_events
        code = ""
        if asset:
            import re
            _m = re.search(r"(\d{6})", asset)
            code = _m.group(1) if _m else ""
        if code:
            ev = load_company_events(code) or {}
            if ev.get("dividend_count"):
                _add(y, _q_of(m) + 1 if _q_of(m) < 4 else 1,
                     "分红", f"分红除权日（近{ev['dividend_count']}次分红历史）", "A/公司公告")
            if ev.get("share_change_count"):
                _add(y, _q_of(m), "股本", "限售解禁/股本变动窗口", "A/公司公告")
    except Exception as _e:
        logger.debug("[CATALYST] company_events failed: %s", _e)

    # ── 3. 政策催化（行业匹配）──
    try:
        from core.data_basement import load_policy
        pol = load_policy(asset_name) if asset_name else None
        if pol:
            for p in pol[:6]:
                dstr = str(p.get("date", ""))[:10]
                try:
                    pd = datetime.strptime(dstr, "%Y-%m-%d").date()
                except Exception:
                    continue
                _add(pd.year, _q_of(pd.month), "政策",
                     f"政策节点：{str(p.get('title',''))[:40]}（方向{'利好' if p.get('direction',0)>0 else '中性/待评估'}）",
                     "A/政策库")
    except Exception as _e:
        logger.debug("[CATALYST] policy failed: %s", _e)

    # ── 4. 行业技术节点（行业生命周期）──
    try:
        from core.data_basement import load_penetration, load_industry_chain
        pen = load_penetration(asset_name) if asset_name else None
        lc = pen.get("life_cycle", "") if pen else ""
        # 生命周期 → 下一关键节点
        if lc in ("导入期", "导入期早期"):
            _add(y, _q_of(m) + 1, "技术", "技术路线验证节点：关键产品认证/客户导入结果", "E/假设")
        elif lc in ("成长期", "成长期早期"):
            _add(y, _q_of(m) + 1, "供给", "产能爬坡/扩产进度披露", "E/假设")
        elif lc == "成熟期":
            _add(y, _q_of(m) + 1, "格局", "行业整合/价格战结果披露", "E/假设")
    except Exception as _e:
        logger.debug("[CATALYST] lifecycle failed: %s", _e)

    # ── 5. 非上市专属：融资/里程碑/IPO ──
    if report_type == "unlisted_company":
        try:
            from core.bottleneck_engine import load_prospectus_data
            ps = load_prospectus_data(asset_name) or {}
            if ps.get("file"):
                _add(y, _q_of(m) + 1, "退出", "IPO 申报/注册推进（已见招股书）", "A/招股书")
            _add(y, _q_of(m) + 1, "融资", "下一轮融资窗口（估值抬升验证）", "E/假设")
            _add(y, _q_of(m) + 1, "里程碑", "产品/客户里程碑节点", "E/假设")
        except Exception as _e:
            logger.debug("[CATALYST] unlisted failed: %s", _e)

    # ── 排序输出 ──
    if not events_by_q:
        return {"status": "no_data", "timeline": [],
                "next_catalyst": "", "note": "无可用催化数据。"}

    timeline = []
    for key in sorted(events_by_q.keys()):
        year, q = key
        timeline.append({
            "quarter": _quarter_label(q, year),
            "events": events_by_q[key],
        })

    # 下一催化剂：最早的未来事件
    first_future = None
    for tl in timeline:
        yq, evs = tl["quarter"], tl["events"]
        try:
            yy = int(yq[:4])
            qq = int(yq[-1])
            if (yy, qq) >= (y, q):
                first_future = (yq, evs[0])
                break
        except Exception:
            pass

    return {
        "status": "ok",
        "timeline": timeline[:8],  # 未来 8 个季度
        "next_catalyst": first_future[0] if first_future else "",
        "next_catalyst_desc": first_future[1]["desc"] if first_future else "",
        "next_earnings": next_earnings_window(now),
        "key_dates": [t["quarter"] for t in timeline[:4]],
    }


def serialize_catalyst(ct: dict, max_chars: int = 1200) -> str:
    """序列化为 prompt 注入文本。"""
    if not ct or ct.get("status") != "ok":
        return ""
    lines = ["=== 催化剂日历（把判断变成可验证的时间轴） ===",
             f"下一催化剂: **{ct.get('next_catalyst')}** — {ct.get('next_catalyst_desc','')[:50]}",
             f"财报窗口: {ct.get('next_earnings')}"]
    for tl in ct.get("timeline", [])[:6]:
        evs = tl["events"]
        lines.append(f"\n{tl['quarter']}:")
        for e in evs[:3]:
            src = e.get("source", "")
            lines.append(f"- [{src}] {e.get('desc','')[:55]}")
    return "\n".join(lines)[:max_chars]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    sample = {"asset": "柯力传感(603662.SH)",
              "chart_data": {}}
    for rt in ["listed_company", "industry_deep", "unlisted_company"]:
        ct = build_catalyst_timeline(sample, rt)
        print(f"\n=== {rt} ===")
        print(serialize_catalyst(ct))
