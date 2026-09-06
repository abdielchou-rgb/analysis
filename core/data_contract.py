"""
Data Contract Layer（Phase C，2026-09-06）。

采集边界的数据契约：单位/口径/时间戳元数据 + 归一化校验。
P0-4/P0-5 的教训固化：口径打架（年报 vs 季报、亿 vs 元）在边界拦截，
不给下游打补丁的机会。

设计：
- ContractViolation → 调用方决定降级路径（degradation），不 raise 崩管线
- 与 compute_engine._clean_num 语义兼容（本层做源头校验，_clean_num 保留为下游兜底）
- 纯标准库，零依赖
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# ── 单位乘数（与 compute_engine._clean_num 同源表） ──────────────────────

CN_UNIT_MULT = {
    "万亿": 1e12,
    "千亿": 1e11,
    "百亿": 1e10,
    "十亿": 1e9,
    "亿": 1e8,
    "千万": 1e7,
    "百万": 1e6,
    "万": 1e4,
}


@dataclass
class ContractViolation:
    key: str
    issue: str  # unit_mismatch / period_conflict / missing_metadata / value_invalid
    detail: str = ""


@dataclass
class FieldContract:
    """单字段契约：归一值 + 元数据。"""

    key: str
    value: float = 0.0
    canonical_unit: str = "yuan"  # yuan / percent / ratio / shares / price
    source: str = ""  # akshare:xxx / tavily / yfinance
    period: str = ""  # "2024年报" / "2026Q3" / ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat()[:19])
    issues: list[ContractViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def normalize_cn_number(raw) -> tuple[float, str]:
    """'29.12亿' → (2912000000.0, 'yuan-raw:29.12亿')；返回 (值, 原始串)。"""
    if raw is None:
        return 0.0, ""
    if isinstance(raw, (int, float)):
        return float(raw), str(raw)
    s = str(raw).strip().replace(",", "").replace("，", "").replace(" ", "")
    if not s or s in ("--", "-", "nan", "None", ""):
        return 0.0, s
    mult = 1.0
    for unit, m in CN_UNIT_MULT.items():
        if unit in s:
            mult = m
            s = s.replace(unit, "")
            break
    s = s.replace("%", "").replace("元", "").strip()
    try:
        return float(s) * mult, str(raw)
    except ValueError:
        return 0.0, str(raw)


# ── 年报/季报键解析（P0-5 口径契约） ───────────────────────────────────────


def parse_period_key(yr_key) -> tuple[str, str] | None:
    """'2024' → ('2024', 'annual'); '2025E' → ('2025', 'forecast');
    '2026Q3' → ('2026', 'quarter'); 非年份 → None。"""
    if yr_key is None:
        return None
    s = str(yr_key).strip()
    if len(s) >= 4 and s[:4].isdigit():
        year = s[:4]
        rest = s[4:].upper()
        if rest == "":
            return year, "annual"
        if rest == "E":
            return year, "forecast"
        if rest.startswith("Q") and rest[1:].isdigit():
            return year, "quarter"
    return None


class DataContract:
    """chart_data 契约校验器。

    用法（data_collector 出口 / compute 入口）：
        contract = DataContract().validate_chart_data(chart_data)
        if contract.violations:
            → 降级路径（标记 data_quality，写作 prompt 注入 warning）
    """

    # 允许的 chart_data 键族
    KNOWN_KEYS = {
        "fig_revenue_trend",
        "fig_profitability",
        "fig_valuation",
        "fig_segments",
        "fig_business_segments",
        "fig_industry_board",
        "fig_capital_flow",
    }

    def __init__(self):
        self.fields: dict[str, FieldContract] = {}
        self.violations: list[ContractViolation] = []

    def validate_chart_data(self, chart_data: dict) -> "DataContract":
        """主入口：校验 + 归一。返回 self（链式）。"""
        if not isinstance(chart_data, dict):
            self.violations.append(ContractViolation("chart_data", "value_invalid", f"非 dict: {type(chart_data)}"))
            return self

        # 1. fig_valuation 元数据存在性（P0-5 契约）
        fv = chart_data.get("fig_valuation")
        if isinstance(fv, dict) and "source" not in fv:
            self.violations.append(
                ContractViolation(
                    "fig_valuation.source", "missing_metadata", "fig_valuation 无 source 标注（P0-5 契约）"
                )
            )

        # 2. 年报口径一致性（P0-4）：revenue_trend 内年报键与 valuation.period 不打架
        rt = chart_data.get("fig_revenue_trend")
        if isinstance(rt, dict) and isinstance(fv, dict):
            annual_years = {y for k in rt if (pp := parse_period_key(k)) and pp[1] == "annual" for y in [pp[0]]}
            v_period = str(fv.get("period", ""))
            v_year = v_period[:4] if v_period[:4].isdigit() else ""
            latest_annual = max(annual_years) if annual_years else ""
            if v_year and latest_annual and v_year != latest_annual:
                # valuation 是季报口径而 revenue_trend 有更新年报 → 提示（不硬拦，走 latest_annual 键）
                self.violations.append(
                    ContractViolation(
                        "fig_valuation.period",
                        "period_conflict",
                        f"valuation 口径 {v_year} 与 revenue_trend 最新年报 {latest_annual} 不同（检查 latest_annual 键）",
                    )
                )

        # 3. 单位归一注册（为下游提供带元数据的读数）
        if isinstance(rt, dict):
            for k, info in rt.items():
                pp = parse_period_key(k)
                if not pp:
                    continue
                if isinstance(info, dict):
                    val, raw = normalize_cn_number(info.get("revenue", info.get("营收", 0)))
                    self.fields[f"revenue.{k}"] = FieldContract(
                        key=f"revenue.{k}",
                        value=val,
                        canonical_unit="yuan",
                        source=str(info.get("source", "akshare")),
                        period=f"{pp[0]}{'E' if pp[1] == 'forecast' else ''}",
                    )
                    np_val, _ = normalize_cn_number(info.get("net_profit", info.get("净利润", 0)))
                    if np_val < 0 and "profit" in str(info.get("net_profit", "")):
                        # 负净利合法（亏损公司），不违规——只记录
                        pass

        return self

    def get(self, dotted_key: str) -> FieldContract | None:
        return self.fields.get(dotted_key)

    def summary(self) -> dict:
        return {
            "n_fields": len(self.fields),
            "n_violations": len(self.violations),
            "violations": [{"key": v.key, "issue": v.issue, "detail": v.detail} for v in self.violations],
        }
