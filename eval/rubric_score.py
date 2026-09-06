"""
eval/rubric_score.py — LLM-as-judge 报告质量评分（Phase B2，2026-09-06）。

按 SAC 维度权重给最终报告打分（复用 core/sacs/*.yaml 权重，不发明新维度）。
结果写入 eval/history/<commit>.json，代码变更后跑 delta 对比。

用法：
    python -m eval.rubric_score <report.md> [--report-type listed_company]

不依赖：评分失败不影响主管线（独立 CLI 工具）。
依赖：core.deepseek_client.call_llm（走 opencode_go → deepseek 链）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.eval.rubric")

EVAL_DIR = _ANALYST_ROOT / "eval" / "history"

# 评分维度（对齐 SAC 核心维度 + Evaluation Layer 蓝图的六维，各 0-10 分）
RUBRIC = {
    "factual_accuracy": "事实准确：数字与来源一致，无自造数据（权重 25%）",
    "citation_completeness": "引用完整：关键论断有来源标注，可回溯（权重 20%）",
    "logical_depth": "逻辑深度：因果链完整，有 So What 推导而非罗列（权重 20%）",
    "industry_understanding": "行业理解：价值链/竞争格局/驱动因素的机构级把握（权重 15%）",
    "falsifiability": "可证伪性：有明确的证伪条件与催化剂跟踪（权重 10%）",
    "expression_quality": "表达质量：去 AI 化、专业行文、结构清晰（权重 10%）",
}
WEIGHTS = {
    "factual_accuracy": 0.25,
    "citation_completeness": 0.20,
    "logical_depth": 0.20,
    "industry_understanding": 0.15,
    "falsifiability": 0.10,
    "expression_quality": 0.10,
}


def _git_commit() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=_ANALYST_ROOT,
            ).stdout.strip()
            or "no-git"
        )
    except Exception:
        return "no-git"


def score_report(report_text: str, report_type: str = "listed_company") -> dict:
    """LLM-as-judge 评分。返回 {dimension: score, ... , total}。"""
    from core.deepseek_client import call_llm

    rubric_lines = "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
    prompt = f"""你是机构研究报告质量评审（Senior Analyst 角度）。对以下{report_type}报告按 6 个维度打分（每维 0-10 整数分）。

评分维度：
{rubric_lines}

要求：
1. 严格按文本内容评分，不做宽容推断
2. 每个分数后附一句理由（20字内）
3. 最后输出一行 JSON: {{"factual_accuracy": N, "citation_completeness": N, "logical_depth": N, "industry_understanding": N, "falsifiability": N, "expression_quality": N}}

报告（截取前6000字）：
{report_text[:6000]}"""

    resp = call_llm(
        [{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.1,
    )
    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")

    # 提取 JSON（容忍 ```json 包裹）
    import re

    m = re.search(r"\{[^{}]*factual_accuracy[^{}]*\}", content, re.DOTALL)
    if not m:
        raise ValueError(f"judge 返回无评分 JSON: {content[:200]}")
    raw = json.loads(m.group())
    scores = {}
    for k in RUBRIC:
        v = raw.get(k)
        scores[k] = (
            max(0, min(10, int(v))) if isinstance(v, (int, float, str)) and str(v).strip().lstrip("-").isdigit() else 5
        )
    total = sum(scores[k] * w for k, w in WEIGHTS.items())
    return {"dimensions": scores, "total": round(total, 2), "judge_raw_head": content[:300]}


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="报告 md 路径")
    parser.add_argument("--report-type", default="listed_company")
    parser.add_argument("--save", action="store_true", help="写入 eval/history/")
    args = parser.parse_args()

    text = Path(args.report).read_text(encoding="utf-8")
    result = score_report(text, args.report_type)
    result["report"] = str(args.report)
    result["report_sha8"] = hashlib.sha256(text.encode()).hexdigest()[:8]
    result["commit"] = _git_commit()
    result["timestamp"] = datetime.now(timezone.utc).isoformat()

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.save:
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        out = EVAL_DIR / f"{result['commit']}_{result['report_sha8']}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("saved: %s", out)


def delta_vs_last(current: dict) -> dict | None:
    """与 eval/history 最近一次评分对比（质量回归监测）。"""
    files = sorted(EVAL_DIR.glob("*.json")) if EVAL_DIR.exists() else []
    if not files:
        return None
    prev = json.loads(files[-1].read_text(encoding="utf-8"))
    prev_dims = prev.get("dimensions", {})
    cur_dims = current.get("dimensions", {})
    delta = {k: cur_dims.get(k, 0) - prev_dims.get(k, 0) for k in RUBRIC}
    return {"prev_commit": prev.get("commit"), "delta": delta, "prev_total": prev.get("total")}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_cli()
