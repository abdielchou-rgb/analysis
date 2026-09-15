"""R78 (2026-08-05) — 数据契约校验回归测试。

2026-09-14 审计重写：本文件原先 import 模块级 `validate_chart_data` /
`validate_enrich_item`，但 `core/data_contract.py` 的实现是 **类** 形态
（`DataContract().validate_chart_data(...)` 返回 self，违规记在 `.violations`），
且从未存在 `validate_enrich_item`。

后果：该 import 在 **收集期** 抛 ImportError → `pytest tests/` 退出码非零 → CI 红。
（手挑文件跑的验证协议测不到未挑中文件的收集错误，故长期未被发现。）

本版改为对齐真实 API：normalize_cn_number / parse_period_key / DataContract。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_contract import DataContract, normalize_cn_number, parse_period_key

# ── 单位归一（CN_UNIT_MULT） ──────────────────────────────────────────


def test_normalize_cn_unit_yi():
    val, raw = normalize_cn_number("29.12亿")
    assert abs(val - 2.912e9) < 1e-3, f"29.12亿 应为 2.912e9，实得 {val}"
    assert raw == "29.12亿", "原始串应保留"


def test_normalize_cn_unit_wanyi():
    val, _ = normalize_cn_number("1.5万亿")
    assert abs(val - 1.5e12) < 1e-3, f"1.5万亿 应为 1.5e12，实得 {val}"


def test_normalize_plain_number_and_commas():
    assert normalize_cn_number(50)[0] == 50.0
    assert normalize_cn_number("1,234.5")[0] == 1234.5


def test_normalize_empty_and_null():
    assert normalize_cn_number(None) == (0.0, "")
    assert normalize_cn_number("--")[0] == 0.0
    assert normalize_cn_number("")[0] == 0.0


# ── 年报/季报口径键解析（P0-5） ────────────────────────────────────────


def test_parse_period_key_annual():
    assert parse_period_key("2024") == ("2024", "annual")


def test_parse_period_key_forecast():
    assert parse_period_key("2025E") == ("2025", "forecast")


def test_parse_period_key_quarter():
    assert parse_period_key("2026Q3") == ("2026", "quarter")


def test_parse_period_key_invalid():
    assert parse_period_key("abc") is None
    assert parse_period_key(None) is None


# ── DataContract 契约校验 ────────────────────────────────────────────


def test_non_dict_chart_data_rejected():
    c = DataContract().validate_chart_data("not_a_dict")
    assert len(c.violations) == 1, "非 dict 应记一条 value_invalid"
    assert c.violations[0].issue == "value_invalid"


def test_fig_valuation_missing_source():
    c = DataContract().validate_chart_data({"fig_valuation": {"period": "2024"}})
    issues = [v.issue for v in c.violations]
    assert "missing_metadata" in issues, "fig_valuation 无 source 应记 missing_metadata"


def test_period_conflict_detected():
    c = DataContract().validate_chart_data(
        {
            "fig_revenue_trend": {"2024": {"revenue": 50}},
            "fig_valuation": {"source": "akshare", "period": "2026Q3"},
        }
    )
    issues = [v.issue for v in c.violations]
    assert "period_conflict" in issues, f"valuation 2026Q3 vs 最新年报 2024 应记 period_conflict，实得 {issues}"


def test_clean_chart_data_has_no_violations():
    c = DataContract().validate_chart_data(
        {
            "fig_revenue_trend": {"2024": {"revenue": 50, "net_profit": 5}},
            "fig_valuation": {"source": "akshare", "period": "2024"},
        }
    )
    assert c.violations == [], f"干净输入不应有违规，实得 {[v.issue for v in c.violations]}"


def test_revenue_fields_registered_with_unit_normalized():
    c = DataContract().validate_chart_data({"fig_revenue_trend": {"2024": {"revenue": "29.12亿"}}})
    fc = c.get("revenue.2024")
    assert fc is not None, "revenue.2024 应被注册"
    assert abs(fc.value - 2.912e9) < 1e-3, f"单位应归一为元，实得 {fc.value}"
    assert fc.canonical_unit == "yuan"
    assert fc.period == "2024"


def test_forecast_period_suffix_preserved():
    c = DataContract().validate_chart_data({"fig_revenue_trend": {"2025E": {"revenue": 60}}})
    fc = c.get("revenue.2025E")
    assert fc is not None and fc.period == "2025E", "预测年份应保留 E 后缀"


def test_validate_returns_self_for_chaining():
    c = DataContract()
    assert c.validate_chart_data({}) is c, "应返回 self 以支持链式调用"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  OK {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
