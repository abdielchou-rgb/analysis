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
    """LLM-as-judge 评分。返回 score 对象（每维 score + reason，按 Langfuse score model）。

    返回结构（对齐顶级 eval 平台的 score-as-object 数据模型）：
    {
      "scores": {dim: {"value": 0-10, "reason": str, "type": "numeric"}},
      "dimensions": {dim: value},            # 兼容旧字段
      "total": float,                          # 权重总分 0-10
      "judge_raw_head": str,                  # 原始回复片段（审计）
    }
    """
    from core.deepseek_client import call_llm

    rubric_lines = "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
    prompt = f"""你是机构研究报告质量评审（Senior Analyst 角度）。对以下{report_type}报告按 6 个维度打分（每维 0-10 整数分）。

评分维度：
{rubric_lines}

要求：
1. 严格按文本内容评分，不做宽容推断
2. 每维给整数分 + 一句理由（30 字内，指出具体证据/缺陷，禁空话）
3. 最后输出一行 JSON（不要 ```json 包裹，只要裸 JSON）:
{{"factual_accuracy": {{"score": N, "reason": "..."}}, "citation_completeness": {{"score": N, "reason": "..."}}, "logical_depth": {{"score": N, "reason": "..."}}, "industry_understanding": {{"score": N, "reason": "..."}}, "falsifiability": {{"score": N, "reason": "..."}}, "expression_quality": {{"score": N, "reason": "..."}}}}

报告（截取前6000字）：
{report_text[:6000]}"""

    resp = call_llm(
        [{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.1,
    )
    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")

    # 提取 JSON（兼容嵌套对象 {"dim": {"score":N,"reason":"..."}} 与扁平 {dim:int}）

    # 定位 factual_accuracy 起始，向外找到包裹它的完整 JSON 对象
    start = content.find("factual_accuracy")
    if start < 0:
        raise ValueError(f"judge 返回无评分 JSON: {content[:200]}")
    open_brace = content.rfind("{", 0, start)
    # 从 open_brace 起做括号配对，取到闭合的完整对象
    depth = 0
    end = open_brace
    for i in range(open_brace, len(content)):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    raw = json.loads(content[open_brace:end])

    scores: dict = {}
    dims: dict = {}
    for k in RUBRIC:
        v = raw.get(k)
        reason = ""
        # 形态 1: {"score": N, "reason": "..."}
        if isinstance(v, dict):
            _val, _reason = v.get("score"), v.get("reason")
            if isinstance(_reason, str):
                reason = _reason[:120]
        else:
            _val = v
        _num = _val if isinstance(_val, (int, float)) else None
        if _num is None and isinstance(_val, str) and _val.strip().lstrip("-").isdigit():
            _num = float(_val)
        dims[k] = int(max(0, min(10, _num))) if _num is not None else 5
        # score 对象（Langfuse score model 对齐）
        scores[k] = {"value": dims[k], "reason": reason, "type": "numeric"}

    total = sum(dims[k] * w for k, w in WEIGHTS.items())
    return {
        "scores": scores,
        "dimensions": dims,
        "total": round(total, 2),
        "judge_raw_head": content[:600],
    }


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


def _dims_of(result: dict) -> dict:
    """兼容两种评分形态取 dimensions：新 {scores:{dim:{value,reason}}} 或旧 {dimensions:{dim:int}}。"""
    if result.get("dimensions"):
        return result["dimensions"]
    scores = result.get("scores") or {}
    return {
        k: (v.get("value") if isinstance(v, dict) else v)
        for k, v in scores.items()
        if isinstance(v, (dict, int, float))
    }


def delta_vs_last(current: dict) -> dict | None:
    """与 eval/history 最近一次评分对比（质量回归监测）。"""
    files = sorted(EVAL_DIR.glob("*.json")) if EVAL_DIR.exists() else []
    if not files:
        return None
    prev = json.loads(files[-1].read_text(encoding="utf-8"))
    prev_dims = _dims_of(prev)
    cur_dims = _dims_of(current)
    delta = {k: cur_dims.get(k, 0) - prev_dims.get(k, 0) for k in RUBRIC}
    return {"prev_commit": prev.get("commit"), "delta": delta, "prev_total": prev.get("total")}


def weakest_feedback(result: dict) -> dict:
    """提取评分最低维度的理由（mini-GEPA 反馈闭环的输入）。

    Langfuse score model 的 TEXT 型用途：把 judge 的定性理由抽出来，供下一轮
    写作 prompt 注入"上期评审反馈修正"指令（score → feedback → reflection）。
    返回 {dim, score, reason, actionable}；无 reason 时 actionable=False。
    """
    scores = result.get("scores") or {}
    dims = _dims_of(result)
    if not dims:
        return {"dim": None, "score": None, "reason": "", "actionable": False}
    worst = min(dims, key=lambda k: dims.get(k, 0))
    reason = ""
    s = scores.get(worst)
    if isinstance(s, dict):
        reason = str(s.get("reason") or "").strip()
    return {
        "dim": worst,
        "score": dims.get(worst),
        "reason": reason,
        "actionable": bool(reason and len(reason) >= 8),  # 理由够具体才可作为修正指令
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_cli()
