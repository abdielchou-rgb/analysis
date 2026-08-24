#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench_baseline.py — P0-4 基线测量（2026-08-07）

跑一篇标准 listed_company 报告，记录各阶段耗时 / LLM 调用数 / token 估算 /
Gate 轮次 / 重写次数，输出 benchmark/baseline_*.json 作为后续 P0/P1/P2 验收对照。

用法：
  python scripts/bench_baseline.py --asset "柯力传感" --type listed_company
  python scripts/bench_baseline.py --asset "思必驰" --type unlisted_company
"""
from __future__ import annotations
import os, sys, json, time, argparse, logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("bench_baseline")


def main():
    ap = argparse.ArgumentParser(description="2hao 基线测量")
    ap.add_argument("--asset", required=True, help="标的名称")
    ap.add_argument("--type", default="listed_company",
                    choices=["listed_company", "unlisted_company", "industry_deep", "decision_memo"])
    ap.add_argument("--outdir", default="benchmark", help="基线输出目录")
    args = ap.parse_args()

    t0 = time.time()
    from pipeline.e2e_orchestrator import E2EOrchestratorV2

    orch = E2EOrchestratorV2(
        report_type=args.type,
        style="cicc",
        output_dir="output",
    )
    result = orch.run(asset=args.asset)
    elapsed = time.time() - t0

    # 从 orchestrator 汇总基线条目
    base = {
        "asset": args.asset,
        "report_type": args.type,
        "date": time.strftime("%Y-%m-%d"),
        "elapsed_s": round(elapsed, 1),
        "passed": result.get("passed", False),
        "attempt": result.get("attempt", orch.MAX_ATTEMPTS if hasattr(orch, "MAX_ATTEMPTS") else 0),
        "gate_score": (result.get("gate_result") or {}).get("overall_score", None),
        "gate_rounds": result.get("attempt", 0),
        "token_budget": result.get("token_budget", 0),
        "needs_agent": result.get("needs_agent", False),
        "data_enriched": result.get("data_enriched", False),
        "node_executions": result.get("_node_executions", []),
        "llm_calls": len(result.get("_node_executions", []) or []),
        "env": {
            "LLM_PROVIDER": os.environ.get("LLM_PROVIDER", "deepseek"),
            "MAX_ATTEMPTS": os.environ.get("MAX_ATTEMPTS", "3"),
        },
    }

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / f"baseline_{args.asset}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Baseline written: %s", out_path)
    logger.info("elapsed=%.1fs passed=%s attempt=%s gate_score=%s",
                elapsed, base["passed"], base["attempt"], base["gate_score"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
