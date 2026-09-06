"""SSOT single-writer + round-trip invariant tests (2026-09-07 T1/T2).

- T1: update_outcomes resolve 结果必须经 TrackRecordManager.apply_resolved 写回，
      不裸 json.dump track_record；alpha/bench/return_pct/resolved_at 落盘后保留。
- T2: Prediction serialize→deserialize 全字段恒等(round-trip invariant)。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import tempfile

import pytest

from core.tools.track_record import Prediction, TrackRecordManager


def _write_temp(payload: dict) -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return path


def _base_payload(**over):
    return {
        "analyst_name": "t",
        "predictions": [
            {
                "id": "x1",
                "asset": "300750",
                "direction": "bullish",
                "outcome": "pending",
                "made_date": "2026-01-01",
                "time_horizon": "3m",
                **over,
            }
        ],
        "last_updated": "",
    }


# ── T1: single writer ────────────────────────────────────────
def test_apply_resolved_persists_resolve_fields():
    """apply_resolved 写回后 alpha/bench/return_pct/resolved_at 必须落盘保留。"""
    path = _write_temp(_base_payload())
    try:
        mgr = TrackRecordManager(storage_path=path)
        n = mgr.apply_resolved(
            [
                {
                    "id": "x1",
                    "outcome": "hit",
                    "judge_ver": "v2",
                    "alpha": 0.03,
                    "bench": "hs300",
                    "return_pct": 8.0,
                    "price_at_make": 10.0,
                    "price_at_expiry": 10.8,
                    "resolved_at": "2026-09-07T00:00:00+00:00",
                    "expiry_date": "2026-04-01",  # 非 dataclass 派生键 → 忽略不落盘
                }
            ]
        )
        assert n == 1
        raw = json.load(open(path, encoding="utf-8"))
        row = raw["predictions"][0]
        assert row["outcome"] == "hit"
        assert row["alpha"] == 0.03
        assert row["bench"] == "hs300"
        assert row["return_pct"] == 8.0
        assert row["resolved_at"]
        assert row["expiry_date"] == "2026-04-01"  # 合法 dataclass 字段, 落盘保留
    finally:
        os.remove(path)


def test_apply_resolved_rejects_bad_outcome():
    path = _write_temp(_base_payload())
    try:
        mgr = TrackRecordManager(storage_path=path)
        n = mgr.apply_resolved([{"id": "x1", "outcome": "correct"}])  # 不在词表
        assert n == 0
        raw = json.load(open(path, encoding="utf-8"))
        assert raw["predictions"][0]["outcome"] == "pending"  # 未污染
    finally:
        os.remove(path)


def test_run_outcome_update_uses_ssot_path(tmp_path, monkeypatch):
    """resolve 经 SSOT 门面写回：模拟到期+取价 → 落盘保留真实价与 alpha。"""
    # 3m from 2026-01-01 → expiry ~2026-04-01 < today(2026-09) → expired
    path = _write_temp(_base_payload())
    try:
        from scripts.update_outcomes import run_outcome_update

        # 避免 import 网络: 注入假取价函数
        def fake_price(asset, date):
            return {"make": 10.0, "expiry": 11.0}.get("make" if "01-01" in date else "expiry")

        stats = run_outcome_update(track_record_path=path, get_price_func=fake_price, dry_run=False)
        raw = json.load(open(path, encoding="utf-8"))
        row = raw["predictions"][0]
        assert row["outcome"] == "hit"
        assert row["return_pct"] is not None
        assert row["price_at_expiry"] == 11.0
    finally:
        os.remove(path)


# ── T2: round-trip invariant ─────────────────────────────────
@pytest.mark.parametrize(
    "fields",
    [
        {},  # 全默认
        {
            "id": "a",
            "asset": "600519",
            "direction": "bearish",
            "outcome": "miss",
            "price_at_make": 1500.0,
            "price_at_expiry": 1400.0,
            "alpha": -0.05,
            "bench": "hs300",
            "return_pct": -6.67,
            "resolved_at": "2026-09-07T00:00:00+00:00",
        },
        {
            "id": "b",
            "asset": "X",
            "direction": "neutral",
            "outcome": "unverifiable",
            "outcome_reason": "data_unavailable",
            "judge_ver": "v2",
        },
        {
            "id": "c",
            "asset": "Y",
            "direction": "bullish",
            "outcome": "pending",
            "bold_call": "12m目标{{tp_primary}}元",
            "falsification": "毛利率跌破34%",
        },
    ],
)
def test_roundtrip_invariant(fields):
    """Prediction → dict → Prediction 全字段恒等(round-trip)。"""
    p = Prediction(**fields)
    d = p.__dict__
    p2 = Prediction(**{k: v for k, v in d.items() if k in Prediction.__dataclass_fields__})
    assert p2 == p


def test_load_save_roundtrip_preserves_all_fields():
    """经真实文件 _load→_save→_load, 全 dataclass 字段无损。"""
    path = _write_temp(
        {
            "analyst_name": "t",
            "predictions": [
                {
                    "id": "rt1",
                    "asset": "300750",
                    "report_type": "listed_company",
                    "industry": "电池",
                    "direction": "bullish",
                    "bold_call": "看多",
                    "target_price": "260",
                    "falsification": "跌破200",
                    "time_horizon": "12m",
                    "made_date": "2026-01-15",
                    "outcome_date": "",
                    "outcome": "pending",
                    "outcome_detail": "",
                    "confidence_at_make": 0.8,
                    "source": "pipeline",
                    "price_at_make": None,
                    "price_at_expiry": None,
                    "outcome_reason": "",
                    "judge_ver": "",
                    "alpha": None,
                    "bench": "none",
                    "return_pct": None,
                    "resolved_at": "",
                }
            ],
            "last_updated": "",
        }
    )
    try:
        m1 = TrackRecordManager(storage_path=path)
        m1._save()  # round-trip through dataclass serialization
        m2 = TrackRecordManager(storage_path=path)
        assert m2.record.predictions[0] == m1.record.predictions[0]
        assert m2.record.predictions[0].confidence_at_make == 0.8
        assert m2.record.predictions[0].source == "pipeline"
    finally:
        os.remove(path)


# ── T3: run_all=门, v2=advisor(2026-09-07 门禁分层) ─────────
def test_v2_checks_never_error_severity():
    """iron_gate._run_irongate_v2_checks append 的 v2_* 必须恒为 warning(advisor 非 gate)。

    直接构造门禁实例成本高(依赖重)；用源码级守卫锁"禁止把 v2 升为 error"这条回归。
    """
    from pathlib import Path

    src = Path("pipeline/iron_gate.py").read_text(encoding="utf-8")
    # v2 layer append 段: 禁止 conditional error (score<0.5 → error) 或 v2 名 + error
    assert 'severity="error" if layer_result.score < 0.5' not in src, "v2 曾按分数升 error, 已降级为 advisor"
    # 取 v2 段检查: 名字以 v2_ 开头的 check 不出现 severity="error"
    import re

    start = src.index("def _run_irongate_v2_checks")
    # 截到下一个顶层 def/@ 之前, 仅覆盖 v2 方法体
    rest = src[start:]
    nxt = re.search(r"\n    (?:def |@|async def )", rest)
    v2_block = rest if not nxt else rest[: nxt.start()]
    # 所有 v2 append 的 severity 均应等于 warning 字面量
    assert 'severity="warning"' in v2_block
    assert 'severity="error"' not in v2_block, "v2 段(含 unavailable/error 兜底)不得出现 error severity"


# ── T4 (2026-09-07): 死函数清除 + resolved 不变量 ──────────
def test_no_save_track_record_function():
    """save_track_record 裸写函数已删除——唯一写路径是 TrackRecordManager。"""
    from pathlib import Path

    src = Path("scripts/update_outcomes.py").read_text(encoding="utf-8")
    assert "def save_track_record" not in src, "裸写函数必须删除(SSOT 唯一写路径)"


def test_resolved_outcome_requires_price_and_judge():
    """hit/miss/partial 必须带 price_at_expiry + judge_ver, 否则 apply_resolved 拒绝(illegal state)。"""
    path = _write_temp(_base_payload())
    try:
        mgr = TrackRecordManager(storage_path=path)
        # 缺 price_at_expiry → 拒绝
        n1 = mgr.apply_resolved([{"id": "x1", "outcome": "hit", "judge_ver": "v2"}])
        assert n1 == 0
        raw = json.load(open(path, encoding="utf-8"))
        assert raw["predictions"][0]["outcome"] == "pending"  # 未污染
        # 缺 judge_ver → 拒绝
        n2 = mgr.apply_resolved([{"id": "x1", "outcome": "hit", "price_at_expiry": 11.0}])
        assert n2 == 0
        # 齐备 → 通过
        n3 = mgr.apply_resolved(
            [
                {
                    "id": "x1",
                    "outcome": "hit",
                    "price_at_expiry": 11.0,
                    "price_at_make": 10.0,
                    "judge_ver": "v2",
                    "return_pct": 10.0,
                }
            ]
        )
        assert n3 == 1
        raw = json.load(open(path, encoding="utf-8"))
        assert raw["predictions"][0]["outcome"] == "hit"
    finally:
        os.remove(path)
