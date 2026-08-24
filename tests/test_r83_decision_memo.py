# -*- coding: utf-8 -*-
"""R83：决策备忘录（decision_memo）报告类型回归测试

油位 v0.89 事故根因（2026-08-07）：管线产出"二级市场投资评级报告"，
委托方要"董事长决策备忘录"。本测试守护：
  1. SACLoader 能加载 sac_decision_memo.yaml（维度/图表/章节结构）
  2. report_planner 生成委托方必答问题清单（client_questions）
  3. scheduler/orchestrator 支持 decision_memo + client_questions 注入
  4. IronGate 委托方问题覆盖率检查：缺答 FAIL、完整 PASS
  5. analyst_planner 路由 decision_memo 到正确框架

可独立运行：python tests/test_r83_decision_memo.py
"""

from __future__ import annotations
import sys, os, tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def run(report=None) -> tuple:
    n_pass, n_fail = 0, 0

    def t(name, ok, detail=""):
        nonlocal n_pass, n_fail
        if ok:
            n_pass += 1
        else:
            n_fail += 1
            msg = f"  FAIL: {name} {detail}"
            print(msg)
            if report:
                report(name, ok, detail)

    # ── 1. SACLoader 加载 decision_memo ─────────────────────
    from core.sacs import SACLoader
    sac = SACLoader("decision_memo")
    dims = sac.get_dimension_ids()
    t("decision_memo SAC dims >= 8", len(dims) >= 8, f"dims={len(dims)}")
    t("decision_memo has exec_summary", "exec_summary" in dims)
    t("decision_memo has worst_case_loss", "worst_case_loss" in dims)
    t("decision_memo has roadmap", "roadmap" in dims)
    cc = sac.get_chart_config()
    t("decision_memo chart min_charts>=4", int(cc.get("min_charts", 0)) >= 4)
    t("decision_memo section has 执行摘要",
      "执行摘要" in sac.get_section_structure())
    # 报告用途标签：board
    t("decision_memo purpose=board", sac.get_report_purpose() == "board")
    t("industry_deep purpose=investor", SACLoader("industry_deep").get_report_purpose() == "investor")

    # ── 2. report_planner 委托方问题清单 ─────────────────────
    from core.report_planner import build_report_plan, serialize_plan
    p = build_report_plan("decision_memo")
    cq = p.get("client_questions", [])
    t("decision_memo client_questions >= 6", len(cq) >= 6, f"count={len(cq)}")
    t("client_questions includes 执行摘要",
      any("执行摘要" in q for q in cq))
    t("client_questions includes 最坏损失",
      any("最坏损失" in q for q in cq))
    s = serialize_plan(p, max_chars=2000)
    t("serialize_plan has 委托方必答", "委托方必答" in s)

    # 外部注入 client_questions
    p2 = build_report_plan("decision_memo",
                           client_questions=["油位传感器市场是否值得战略卡位？",
                                             "柯力进入能否快速放量？"])
    t("external client_questions merged",
      len(p2.get("client_questions", [])) > len(cq))
    t("external question appears", any("卡位" in q for q in p2.get("client_questions", [])))

    # ── 3. analyst_planner 路由 decision_memo ─────────────────
    from core.analyst_planner import build_analysis_plan
    ap = build_analysis_plan("油位传感器", "decision_memo",
                             data_sufficiency={"sufficient": True})
    fw = [f["id"] for f in ap.get("frameworks", [])]
    t("planner routes to decision_memo framework", "decision_memo" in fw, str(fw))

    # ── 4. IronGate 委托方问题覆盖率 ────────────────────────
    from pipeline.iron_gate import IronGate
    # 缺答报告 → FAIL
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp.write("# 油位传感器行业报告\n\n## 核心判断\n成熟期前段。\n\n## 市场规模\n全球46亿美元。")
    tmp.close()
    ig = IronGate(tmp.name, report_type="decision_memo")
    r_fail = ig._check_client_questions_coverage()
    t("gate FAILs unanswered decision_memo", not r_fail.passed, r_fail.details[:80])
    os.unlink(tmp.name)
    # 完整报告 → PASS
    tmp2 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp2.write("""
# 决策备忘录：整合可行性

## 执行摘要
结论：值得战略卡位，条件性进入。投入1.7亿，最坏损失半年利润。

## 行业真相
全球46亿美元，卡脖子在磁致伸缩丝。竞争托肯恒山第一。

## 禀赋匹配度
华虹具备承接能力。

## 路径决策
建议华虹生产为主，转移定价公允。

## 财务测算
收入三浪，投入1.7亿。

## 最坏损失
最坏损失1.7亿。

## 执行路线图
Q1签协议，第一步订单承诺。
""")
    tmp2.close()
    ig2 = IronGate(tmp2.name, report_type="decision_memo")
    r_pass = ig2._check_client_questions_coverage()
    t("gate PASSes complete decision_memo", r_pass.passed, r_pass.details[:80])
    os.unlink(tmp2.name)
    # 非 decision_memo 无注入问题 → 跳过（PASS warning）
    tmp3 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp3.write("行业报告正文内容。")
    tmp3.close()
    ig3 = IronGate(tmp3.name, report_type="industry_deep")
    r_skip = ig3._check_client_questions_coverage()
    t("gate skips non-decision_memo", r_skip.passed, r_skip.details[:80])
    os.unlink(tmp3.name)

    # ── 5. scheduler 支持 decision_memo + client_questions ──
    import inspect
    from pipeline import scheduler
    sig = inspect.signature(scheduler.schedule)
    t("schedule() accepts client_questions", "client_questions" in sig.parameters)
    # CLI argparse choices
    t("scheduler CLI accepts decision_memo", "decision_memo" in inspect.getsource(scheduler.main))

    return n_pass, n_fail


if __name__ == "__main__":
    p, f = run()
    print(f"\nR83 decision_memo 回归测试: {p} passed, {f} failed")
    sys.exit(1 if f else 0)
