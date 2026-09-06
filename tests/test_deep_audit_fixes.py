"""Regression tests for 2026-09-06 deep-audit fixes.

Covers:
- P0-1: core/calibration.py dead module removed; metrics reachable via package; no shadowing.
- P1-1: core/attribution.generate_attribution_report executes the datetime branch (was NameError).
- P0-2: get_public_summary is fail-closed (no fake avg_pnl/kelly/pnl_pct).
- 附加: track_record._load tolerant of unknown JSON keys (schema evolution won't silently wipe).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import tempfile


# ── P0-1: calibration dead module ─────────────────────────────
def test_calibration_is_package_not_file():
    """core.calibration must resolve to the package (no shadowing .py dead module)."""
    import core.calibration

    assert hasattr(core.calibration, "__path__"), "core.calibration should be a package"


def test_calibration_metrics_reachable_via_package():
    """ECE/Brier metric functions (migrated out of dead module) are importable."""
    from core.calibration import compute_brier, compute_ece

    ece = compute_ece([0.8, 0.6, 0.5], [1, 0, 1])
    assert isinstance(ece, float)
    brier = compute_brier([0.8, 0.6], [1, 0])
    assert brier >= 0.0


def test_load_and_recalibrate_executes_branch():
    """load_and_recalibrate must run its recalibrate loop (was F821: recal_confidence undefined)."""
    import core.calibration.metrics as m

    # insufficient-data branch: <20 resolved
    out = m.load_and_recalibrate.__wrapped__ if hasattr(m.load_and_recalibrate, "__wrapped__") else None
    # build a small temp track record with >=20 hit/miss to force fit path
    preds = []
    for i in range(22):
        preds.append(
            {
                "id": f"t{i}",
                "asset": "X",
                "outcome": "hit" if i % 2 == 0 else "miss",
                "confidence_at_make": 0.6 + (i % 5) * 0.05,
            }
        )
    payload = {"analyst_name": "t", "predictions": preds, "last_updated": ""}
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    try:
        updated = m.load_and_recalibrate(path)
        assert len(updated) == 22
        assert all("calibrated_confidence" in p for p in updated)
    finally:
        os.remove(path)


# ── P1-1: attribution datetime NameError ──────────────────────
def test_generate_attribution_report_runs_datetime_branch():
    from core.attribution import generate_attribution_report

    preds = [
        {
            "asset": "A",
            "direction": "bullish",
            "outcome": "hit",
            "dimensions_used": ["moat"],
            "frameworks_used": ["quality"],
        },
        {
            "asset": "B",
            "direction": "bearish",
            "outcome": "miss",
            "dimensions_used": ["moat"],
            "frameworks_used": ["quality"],
        },
        {
            "asset": "C",
            "direction": "bullish",
            "outcome": "hit",
            "dimensions_used": ["valuation"],
            "frameworks_used": ["value"],
        },
    ]
    report = generate_attribution_report(preds)
    assert report["generated_at"], "generated_at must be populated (was NameError before fix)"


# ── P0-2: track_record fail-closed summary ────────────────────
def _make_prediction(**over):
    from core.tools.track_record import Prediction

    base = dict(id="p1", asset="300750", direction="bullish", outcome="pending")
    base.update(over)
    return Prediction(**base)


def test_public_summary_no_fake_pnl():
    from core.tools.track_record import TrackRecord, TrackRecordManager

    tr = TrackRecord(
        predictions=[
            _make_prediction(id="h1", outcome="hit", price_at_make=10.0, price_at_expiry=12.0),
            _make_prediction(id="m1", outcome="miss", price_at_make=10.0, price_at_expiry=9.0),
            _make_prediction(id="pd1", outcome="pending"),
        ]
    )
    mgr = TrackRecordManager.__new__(TrackRecordManager)
    mgr.storage_path = "unused"
    mgr.record = tr

    s = mgr.get_public_summary()
    # 2 resolved with real prices → avg_pnl = mean(+20%, -10%) = +5%
    assert s["resolved_calls"] == 2
    assert s["avg_pnl_pct"] == 5.0
    assert s["kelly_sizing"] is None, "fake kelly 1.3x must be gone"
    rows = {c["id"]: c for c in s["calls"]}
    assert rows["h1"]["pnl_pct"] == 20.0
    assert rows["m1"]["pnl_pct"] == -10.0
    # pending & no-price rows → pnl None, never 0/10/-5 fabricated
    assert rows["pd1"]["pnl_pct"] is None


def test_public_summary_no_price_no_avg():
    from core.tools.track_record import TrackRecord, TrackRecordManager

    tr = TrackRecord(
        predictions=[
            _make_prediction(outcome="hit"),  # resolved but NO real price
        ]
    )
    mgr = TrackRecordManager.__new__(TrackRecordManager)
    mgr.record = tr
    s = mgr.get_public_summary()
    assert s["avg_pnl_pct"] is None  # no fabricated +10%


def test_load_tolerant_unknown_keys():
    """_load must not silently wipe record when JSON has keys not on the dataclass."""
    from core.tools.track_record import TrackRecordManager

    payload = {
        "analyst_name": "t",
        "predictions": [
            {
                "id": "a",
                "asset": "X",
                "direction": "bullish",
                "outcome": "pending",
                "future_schema_key": 123,
            },  # unknown key (schema evolution)
        ],
        "last_updated": "",
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    try:
        mgr = TrackRecordManager(storage_path=path)
        assert mgr.record.total == 1, "record must survive unknown-key load"
    finally:
        os.remove(path)


# ── R1 (2026-09-07): resolve 字段 load→save→再读 往返不丢失 ──
def test_resolve_fields_survive_round_trip():
    """alpha/bench/return_pct/resolved_at 必须经 _load→_save→_load 往返保留."""
    from core.tools.track_record import TrackRecordManager

    payload = {
        "analyst_name": "t",
        "predictions": [
            {
                "id": "r1",
                "asset": "300750",
                "direction": "bullish",
                "outcome": "hit",
                "judge_ver": "v3",
                "price_at_make": 10.0,
                "price_at_expiry": 11.0,
                "alpha": 0.03,
                "bench": "hs300",
                "return_pct": 10.0,
                "resolved_at": "2026-09-07T00:00:00+00:00",
            }
        ],
        "last_updated": "",
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    try:
        mgr = TrackRecordManager(storage_path=path)
        p = mgr.record.predictions[0]
        assert p.alpha == 0.03
        assert p.bench == "hs300"
        assert p.return_pct == 10.0
        assert p.resolved_at  # 字段在 dataclass 上(不再是白名单外的孤儿 key)

        # _save → 再读
        mgr._save()
        mgr2 = TrackRecordManager(storage_path=path)
        p2 = mgr2.record.predictions[0]
        assert p2.alpha == 0.03, "alpha 经 _save 往返被剥离 → 触发点确实会丢数据"
        assert p2.bench == "hs300"
        assert p2.return_pct == 10.0
        assert p2.resolved_at
    finally:
        os.remove(path)


def test_resolve_write_keys_are_on_dataclass():
    """update_outcomes.resolve_outcome 写入的每个 key 都必须是 Prediction dataclass 字段."""
    import re
    from pathlib import Path

    from core.tools.track_record import Prediction

    src = Path("scripts/update_outcomes.py").read_text(encoding="utf-8")
    written = set(re.findall(r'prediction\["([a-z_]+)"\]\s*=', src))
    dataclass_fields = set(Prediction.__dataclass_fields__)
    # 允许的写键 = dataclass 字段 + 非 schema 控制键(如 outcome 读取用键)
    missing = written - dataclass_fields
    assert not missing, f"resolve 写入键不在 Prediction dataclass 上, _save 会剥离: {missing}"


# ── R2 (2026-09-07): partial 语义定死 ──
def test_partial_counts_in_resolved_and_credit():
    from core.tools.track_record import OUTCOME_CREDIT, TrackRecord, TrackRecordManager

    tr = TrackRecord(
        predictions=[
            _make_prediction(id="h", outcome="hit"),
            _make_prediction(id="p", outcome="partial"),
            _make_prediction(id="m", outcome="miss"),
        ]
    )
    assert tr.resolved_count == 3, "partial 必须计入已结算"
    assert tr.accuracy == 0.5, f"信用加权 (1+0.5+0)/3=0.5, got {tr.accuracy}"
    assert OUTCOME_CREDIT["partial"] == 0.5

    mgr = TrackRecordManager.__new__(TrackRecordManager)
    mgr.storage_path = "unused"
    mgr.record = tr
    s = mgr.get_public_summary()
    assert s["resolved_calls"] == 3, "summary 的 resolved_calls 必须包含 partial"


# ── R3 (2026-09-07): 非正价格 fail-closed ──
def test_non_positive_expiry_price_returns_none():
    from core.tools.track_record import TrackRecordManager

    mgr = TrackRecordManager.__new__(TrackRecordManager)
    mgr.storage_path = "unused"
    # expiry=0(退市归零) 不得除零, 返回 None
    p = _make_prediction(id="z", outcome="miss", price_at_make=10.0, price_at_expiry=0.0)
    assert mgr._real_pnl_pct(p) is None
    p2 = _make_prediction(id="z2", outcome="hit", price_at_make=-1.0, price_at_expiry=10.0)
    assert mgr._real_pnl_pct(p2) is None


# ── R4 (2026-09-07): IronGate 阈值单一事实源 ──
def test_docs_threshold_equals_runtime():
    """PIPELINE_FACTS 文档阈值必须等于 iron_gate.PASS_THRESHOLD(单一事实源)。"""
    import re
    from pathlib import Path

    ig_src = Path("pipeline/iron_gate.py").read_text(encoding="utf-8")
    m = re.search(r"^PASS_THRESHOLD\s*=\s*([\d.]+)", ig_src, re.M)
    assert m, "iron_gate.py 必须定义 PASS_THRESHOLD"
    runtime_threshold = float(m.group(1))

    facts = Path("docs/PIPELINE_FACTS.md").read_text(encoding="utf-8")
    fm = re.search(r"PASS_THRESHOLD（iron_gate.py 单一事实源）：([\d.]+)", facts)
    assert fm, "PIPELINE_FACTS.md 必须含单一事实源阈值行(由 generate_docs 生成)"
    assert float(fm.group(1)) == runtime_threshold, "文档阈值与运行时漂移——需重跑 generate_docs"

    # harness 历史快照字段与运行时一致(只读参考)
    from harness.pipeline_contract import IRON_GATE_CONTRACT

    assert IRON_GATE_CONTRACT["min_score"] == runtime_threshold


def test_generate_docs_single_source_helpers():
    """generate_docs 的 _gate_pass_threshold/_gate_judge_version 读 iron_gate.py 源码。"""
    from harness.generate_docs import _gate_judge_version, _gate_pass_threshold

    assert _gate_pass_threshold() == 0.78
    assert "error-mean" in _gate_judge_version()
