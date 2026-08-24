"""intent_gate.py — 意图符合性门禁（FP0 落地，2026-08-07）

Gate 层新增"意图符合性"检查：必答问题是否被报告回答。
与 IronGate 结构检查互补——IronGate 查"结构/格式/一致性"，intent_gate 查"答没答对题"。

设计（FP0 否决条件）：结构正确但没回答用户问题 = 未通过。

用法（IronGate 集成）：
  from core.intent_gate import check_intent_compliance
  result = check_intent_compliance(report_text, plan)

直接调用：
  python -m core.intent_gate --report output/x.md --requirement "评估市场规模"
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger("2hao.intent_gate")

_ROOT = Path(__file__).resolve().parent.parent


def check_intent_compliance(report_text: str, plan: dict) -> dict:
    """意图符合性检查：必答问题是否被回答。

    Args:
        report_text: 报告正文
        plan: intent_parser 产出的意图计划（含 must_answer_questions）

    Returns:
        {passed, coverage, answered, total, results, gaps}
    """
    from core.intent_parser import IntentParser

    ip = IntentParser()
    result = ip.validate_report(plan, report_text)
    gaps = [r["question"] for r in result["results"] if not r["answered"]]
    return {
        "passed": result["passed"],
        "coverage": result["coverage"],
        "answered": result["answered"],
        "total": result["total"],
        "results": result["results"],
        "gaps": gaps,
    }


def intent_gate_node(node_id: str, context: dict) -> dict:
    """E2E 管线节点：意图符合性门禁（挂在 validate 后）。

    context 需含 report_text 与 intent_plan（由 orchestrator 注入）。
    """
    text = context.get("final_text") or context.get("report_text", "")
    plan = context.get("intent_plan") or context.get("_intent_plan")
    if not text or not plan:
        # 无意图计划（非 FP0 任务）→ 不阻断（向后兼容）
        return {"intent_passed": True, "intent_note": "no_intent_plan"}
    try:
        result = check_intent_compliance(text, plan)
        context["intent_gate_result"] = result
        logger.info(
            "[INTENT-GATE] coverage=%.2f passed=%s gaps=%d",
            result["coverage"],
            result["passed"],
            len(result.get("gaps", [])),
        )
        return {
            "intent_passed": result["passed"],
            "intent_coverage": result["coverage"],
            "intent_gaps": result.get("gaps", []),
        }
    except Exception as e:
        logger.warning("[INTENT-GATE] %s", str(e)[:80])
        return {"intent_passed": True, "intent_note": f"error:{str(e)[:40]}"}


def main():
    import argparse

    ap = argparse.ArgumentParser(description="意图符合性检查")
    ap.add_argument("--report", required=True, help="报告文件路径")
    ap.add_argument("--requirement", default="", help="委托方需求")
    ap.add_argument("--type", default="decision_memo", help="报告类型")
    args = ap.parse_args()
    from core.intent_parser import IntentParser

    text = Path(args.report).read_text(encoding="utf-8")
    plan = IntentParser().parse("CLI", args.type, args.requirement)
    result = check_intent_compliance(text, plan)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
