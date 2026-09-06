"""
eval/diff_runs.py — 两份评测集 run 对比（mini-GEPA 双版本质量回归）。

用法：
    python -m eval.diff_runs <run_a> <run_b>

run_a = 基线（旧 prompt/旧代码），run_b = 新版本。输出：
    1. 每标的 total 分差（回归检测）
    2. 每标的×每维分差
    3. 聚合最弱维度变化（回答"涨在哪个维度、最弱项是否改善"）

run 目录：eval/runs/<run_id>/（由 run_evalset.py 产出）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

RUNS_DIR = _ANALYST_ROOT / "eval" / "runs"
DIMS = [
    "factual_accuracy",
    "citation_completeness",
    "logical_depth",
    "industry_understanding",
    "falsifiability",
    "expression_quality",
]


def _load_run(run_id: str) -> dict:
    d = RUNS_DIR / run_id
    if not d.exists():
        raise FileNotFoundError(f"run 不存在: {d}（先跑 python -m eval.run_evalset --tag {run_id}）")
    out = {}
    for fp in sorted(d.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        data = json.loads(fp.read_text(encoding="utf-8"))
        asset = data.get("asset", fp.stem)
        out[asset] = data
    return out


def _dims(result: dict) -> dict:
    if result.get("dimensions"):
        return result["dimensions"]
    return {k: (v.get("value") if isinstance(v, dict) else v) for k, v in (result.get("scores") or {}).items()}


def diff_runs(run_a: str, run_b: str) -> dict:
    a, b = _load_run(run_a), _load_run(run_b)
    assets = sorted(set(a) & set(b))
    report = {
        "run_a": run_a,
        "run_b": run_b,
        "n_common": len(assets),
        "only_a": sorted(set(a) - set(b)),
        "only_b": sorted(set(b) - set(a)),
        "per_asset": {},
        "dim_agg": {},
    }
    if not assets:
        report["status"] = "no_common"
        return report

    # 每维全标的分差聚合（均值变化 → 回答"哪个维度整体变了"）
    for dim in DIMS:
        da = [(_dims(a[x]).get(dim, 0)) for x in assets]
        db = [(_dims(b[x]).get(dim, 0)) for x in assets]
        report["dim_agg"][dim] = {
            "mean_a": round(sum(da) / len(da), 2),
            "mean_b": round(sum(db) / len(db), 2),
            "delta": round((sum(db) - sum(da)) / len(db), 2),
        }

    for asset in assets:
        ra, rb = a[asset], b[asset]
        ta, tb = ra.get("total", 0), rb.get("total", 0)
        dim_delta = {d: _dims(rb).get(d, 0) - _dims(ra).get(d, 0) for d in DIMS}
        report["per_asset"][asset] = {
            "total_a": ta,
            "total_b": tb,
            "total_delta": round(tb - ta, 2),
            "dim_delta": dim_delta,
            "regression": tb < ta,
        }

    report["n_regressed"] = sum(1 for v in report["per_asset"].values() if v["regression"])
    report["mean_total_a"] = round(sum(v["total_a"] for v in report["per_asset"].values()) / len(assets), 2)
    report["mean_total_b"] = round(sum(v["total_b"] for v in report["per_asset"].values()) / len(assets), 2)
    report["status"] = "ok"
    return report


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_a", help="基线 run_id")
    parser.add_argument("run_b", help="新版本 run_id")
    args = parser.parse_args()
    print(json.dumps(diff_runs(args.run_a, args.run_b), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_cli()
