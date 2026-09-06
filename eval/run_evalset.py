"""
eval/run_evalset.py — 对固定评测集全量跑 rubric（mini-GEPA 双版本对照）。

用法：
    python -m eval.run_evalset [--tag <标签>] [--report <相对路径或子串>]

行为：
    1. 读 eval/evalset.json 的固定报告清单
    2. 逐份跑 score_report（LLM-as-judge，走 opencode_go→deepseek 链）
    3. 单份结果落 eval/runs/<run_id>/<asset>.json
    4. 汇总落 eval/runs/<run_id>/_summary.json
    run_id = YYYYMMDD_HHMMSS 或 <tag>

副作用：无（结果只写入 eval/runs/）。评分失败不中断（单份降级记录）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.eval.runset")

RUNS_DIR = _ANALYST_ROOT / "eval" / "runs"


def _load_evalset() -> list[dict]:
    p = _ANALYST_ROOT / "eval" / "evalset.json"
    if not p.exists():
        raise FileNotFoundError(f"评测集缺失: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("reports", [])


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def run_evalset(tag: str | None = None, report_filter: str | None = None) -> dict:
    from eval.rubric_score import _git_commit, score_report

    reports = _load_evalset()
    if report_filter:
        reports = [r for r in reports if report_filter in r.get("file", "") or report_filter in r.get("asset", "")]
    if not reports:
        return {"status": "no_reports", "run_id": "", "n": 0}

    run_id = tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = RUNS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    per_asset = {}
    summary_scores = {}
    failures = []
    for r in reports:
        fp = _ANALYST_ROOT / r["file"]
        asset = r.get("asset", fp.stem)
        if not fp.exists():
            failures.append({"asset": asset, "error": "file missing"})
            continue
        text = fp.read_text(encoding="utf-8")
        try:
            result = score_report(text, r.get("report_type", "listed_company"))
        except Exception as e:  # 单份失败不中断评测集
            failures.append({"asset": asset, "error": str(e)[:120]})
            logger.warning("[RUNSET] %s 评分失败: %s", asset, str(e)[:100])
            continue
        result["asset"] = asset
        result["report"] = r["file"]
        result["report_sha8"] = _sha(text)
        result["run_id"] = run_id
        result["commit"] = _git_commit()
        per_asset[asset] = result
        summary_scores[asset] = result.get("total", 0)
        (out_dir / f"{asset}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "status": "ok",
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "n_reports": len(reports),
        "n_scored": len(per_asset),
        "per_asset_total": summary_scores,
        "mean_total": round(sum(summary_scores.values()) / len(summary_scores), 2) if summary_scores else None,
        "failures": failures,
    }
    (out_dir / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=None, help="run_id 标签（默认时间戳）")
    parser.add_argument("--report", default=None, help="只跑指定标的（file/asset 子串）")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    s = run_evalset(tag=args.tag, report_filter=args.report)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_cli()
