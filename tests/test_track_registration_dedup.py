"""2026-09-07 T3 regression tests: 幂等注册 / 唯一 id / 保守去重 / 到期链容错.

- 同一报告经 orchestrator 与 web log_run 双路径注册 → register_prediction 幂等。
- 分钟级旧 id 撞车 → 新 id 秒级 + 内容摘要；历史撞 id 由 dedup uniquify_ids 修复。
- check_expired 对 unknown/区间/坏日期显式 warning，不静默吞掉。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json

from core.tools.track_record import TrackRecordManager, _make_prediction_id


def _manager(tmp_path, payload=None):
    path = tmp_path / "track_record.json"
    if payload is None:
        payload = {"analyst_name": "t", "predictions": [], "last_updated": ""}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return TrackRecordManager(storage_path=str(path))


# ── id 唯一性 ─────────────────────────────────────────────────
def test_prediction_id_differs_by_content_same_second(monkeypatch):
    """同一秒内不同 bold_call 也必须得到不同 id（内容摘要兜底）。"""
    import core.tools.track_record as tr

    class _FakeDT:
        @classmethod
        def now(cls):
            return cls()

        def strftime(self, fmt):
            return "20260907_000000"

    monkeypatch.setattr(tr, "datetime", _FakeDT)
    id_a = _make_prediction_id("000001", "目标价 40 元", set())
    id_b = _make_prediction_id("000001", "目标价 25 元", set())
    assert id_a != id_b


def test_prediction_id_ordinal_fallback_on_collision():
    id_1 = _make_prediction_id("000001", "same call", {"x"})
    # 与已有 id 相同则追加序号
    collided = _make_prediction_id("000001", "same call", {id_1})
    assert collided != id_1
    assert collided.endswith("_1")


# ── 幂等注册 ─────────────────────────────────────────────────
def test_register_prediction_is_idempotent(tmp_path):
    mgr = _manager(tmp_path)
    kwargs = dict(
        asset="300750",
        report_type="listed_company",
        industry="新能源",
        direction="bullish",
        bold_call="  未来12个月看多，目标价翻倍。  ",
        time_horizon="12m",
    )
    first = mgr.register_prediction(**kwargs)
    # 同一内容、同日、同方向/期限/目标价 → 返回已有记录，不新增
    second = mgr.register_prediction(**kwargs)
    assert first.id == second.id
    assert mgr.record.total == 1

    # 重新加载后依然只有一条（幂等跨实例生效）
    mgr2 = TrackRecordManager(storage_path=mgr.storage_path)
    assert mgr2.record.total == 1


def test_register_distinct_calls_both_kept(tmp_path):
    mgr = _manager(tmp_path)
    base = dict(
        asset="600519",
        report_type="listed_company",
        industry="白酒",
        direction="bullish",
        time_horizon="12m",
    )
    a = mgr.register_prediction(bold_call="第一观点：批价上行。", **base)
    b = mgr.register_prediction(bold_call="第二观点：扩产落地。", **base)
    assert mgr.record.total == 2
    assert a.id != b.id


# ── apply_resolved 重复 id 保护 ──────────────────────────────
def test_apply_resolved_duplicate_id_only_updates_first(tmp_path):
    rows = [
        {
            "id": "dup1",
            "asset": "000001",
            "direction": "bullish",
            "outcome": "pending",
            "made_date": "2026-01-01",
            "time_horizon": "6m",
            "bold_call": "call A",
        },
        {
            "id": "dup1",
            "asset": "000001",
            "direction": "bullish",
            "outcome": "pending",
            "made_date": "2026-01-01",
            "time_horizon": "6m",
            "bold_call": "call B",
        },
    ]
    mgr = _manager(tmp_path, {"analyst_name": "t", "predictions": rows})
    n = mgr.apply_resolved(
        [
            {
                "id": "dup1",
                "outcome": "hit",
                "price_at_expiry": 12.0,
                "judge_ver": "v2",
                "expiry_date": "2026-07-01",
                "price_at_make": 10.0,
            }
        ]
    )
    assert n == 1
    settled = [p for p in mgr.record.predictions if p.outcome == "hit"]
    pending = [p for p in mgr.record.predictions if p.outcome == "pending"]
    assert len(settled) == 1 and len(pending) == 1  # 撞 id 只更新首条，遗留 pending


# ── parse_horizon / check_expired ────────────────────────────
def test_parse_horizon_cases():
    from scripts.update_outcomes import parse_horizon

    assert parse_horizon("6m") == 180
    assert parse_horizon("12m") == 360
    assert parse_horizon("1y") == 365
    assert parse_horizon("5y") == 1825
    assert parse_horizon("6-12m") == 360  # 取上界，不提前结算
    assert parse_horizon("unknown") is None
    assert parse_horizon("") is None
    assert parse_horizon("banana") is None


def test_check_expired_warns_not_silent():
    from scripts.update_outcomes import check_expired

    preds = [
        {"id": "1", "asset": "a", "outcome": "pending", "made_date": "2025-01-01", "time_horizon": "12m"},
        {"id": "2", "asset": "b", "outcome": "pending", "made_date": "2025-01-01", "time_horizon": "unknown"},
        {"id": "3", "asset": "c", "outcome": "pending", "made_date": "not-a-date", "time_horizon": "6m"},
        {"id": "4", "asset": "d", "outcome": "pending", "made_date": "2025-01-01", "time_horizon": "6-12m"},
    ]
    expired, warnings = check_expired(preds, as_of_date="2026-09-07")
    assert len(expired) == 2  # id=1(12m) + id=4(区间上界12m) 到期
    assert len(warnings) == 2  # unknown + 坏日期各一条，不再静默吞
    text = "\n".join(warnings)
    assert "unknown" in text and "not-a-date" in text


def test_check_expired_future_not_expired():
    from scripts.update_outcomes import check_expired

    preds = [{"id": "1", "asset": "a", "outcome": "pending", "made_date": "2026-08-01", "time_horizon": "12m"}]
    expired, warnings = check_expired(preds, as_of_date="2026-09-07")
    assert expired == []
    assert warnings == []


# ── 保守去重脚本核心 ─────────────────────────────────────────
def test_dedup_keeps_distinct_calls_merges_real_dups():
    from scripts.dedup_track_record import dedup

    base = {
        "asset": "000001",
        "made_date": "2026-08-01",
        "direction": "bullish",
        "time_horizon": "6m",
        "target_price": "",
    }
    # 真重复：同字段、文本完全一致
    exact_dup = dict(base, id="a", bold_call="看多逻辑全文。")
    exact_dup2 = dict(base, id="a", bold_call="看多逻辑全文。")
    # 双路径截断差异：共享 60+ 前缀，但文本不同长
    long_txt = (
        "未来一年公司盈利将显著改善，产能爬坡带动毛利率与净利率同步上行，"
        "叠加费用率优化与产品结构升级，目标价上修至行业均值之上，"
        "给予强烈推荐评级并建议重点关注左侧布局机会与催化剂兑现节奏。A"
    )
    assert len(long_txt) - 12 >= 60
    trunc = long_txt[:-12]
    truncated_dup = dict(base, id="b", bold_call=trunc)
    long_call = dict(base, id="c", bold_call=long_txt)
    # 独立观点：同 asset/date 但不同方向 → 必须保留
    independent = dict(base, id="d", direction="bearish", bold_call="看空逻辑完全不一样。")
    rows = [exact_dup, exact_dup2, truncated_dup, long_call, independent]
    kept, removed = dedup(rows)
    assert removed == 2  # exact_dup2 + truncated_dup
    assert len(kept) == 3
    assert any(p["id"] == "d" for p in kept)  # 独立看空观点被保留


def test_uniquify_ids_makes_ids_unique():
    from scripts.dedup_track_record import uniquify_ids

    rows = [
        {"id": "20260801_0100_000001", "asset": "000001", "bold_call": "观点甲", "made_date": "2026-08-01"},
        {"id": "20260801_0100_000001", "asset": "000001", "bold_call": "观点乙", "made_date": "2026-08-01"},
        {"id": "20260801_0100_000002", "asset": "000002", "bold_call": "观点丙", "made_date": "2026-08-01"},
    ]
    changed = uniquify_ids(rows)
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == 3
    assert changed == 2  # 共享 id 的两条被重建，单条 id 不动
    assert rows[2]["id"] == "20260801_0100_000002"
