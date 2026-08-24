# -*- coding: utf-8 -*-
"""R84：委托方实体锚定 + 决策引擎引用 Gate 回归测试

油位 v0.90 事故根因（2026-08-07）：
  1. 把"柯力进加油站/危化品油位市场"写成"某制造业上市公司进商用车车规油箱"——
     --client-questions 只注入了必答问题，没注入"委托方是谁/场景是什么/不能写成什么"
  2. DecisionEngine 产出确定性结论（3.94/5、投入1.5-2亿、最坏损失2亿），
     报告一个都没引用，自己编了量级差10倍的数值

本测试守护：
  - report_planner 支持 must_contain / forbidden_swap 注入
  - Gate _check_entity_anchoring：缺失关键实体/出现禁止场景 → FAIL
  - Gate _check_decision_engine_citation：缺卡位评分/最坏损失金额 → FAIL

可独立运行：python tests/test_r84_entity_anchoring.py
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

    # ── 1. report_planner 支持 must_contain/forbidden_swap ─────
    from core.report_planner import build_report_plan, serialize_plan
    cq = [
        {"q": "油位市场是否值得战略卡位？", "must_contain": ["华虹", "加油站", "危化品"], "forbidden_swap": ["商用车", "车规"]},
        {"q": "久通整合可行性？", "must_contain": ["久通", "转移定价"], "forbidden_swap": ["汽车油箱"]},
    ]
    plan = build_report_plan("decision_memo", client_questions=cq)
    mc = plan.get("must_contain", [])
    fb = plan.get("forbidden_swap", [])
    t("plan must_contain aggregated", "华虹" in mc and "加油站" in mc and "久通" in mc, str(mc))
    t("plan forbidden_swap aggregated", "商用车" in fb and "车规" in fb and "汽车油箱" in fb, str(fb))
    s = serialize_plan(plan, max_chars=3000)
    t("serialize has 必须出现的实体", "必须出现" in s and "华虹" in s)
    t("serialize has 禁止替换", "禁止替换" in s and "商用车" in s)

    # ── 2. Gate _check_entity_anchoring：缺实体 → FAIL ────────
    from pipeline.iron_gate import IronGate
    # 2a. 缺关键实体（华虹/加油站/危化品），出现禁止场景（商用车）→ FAIL
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp.write("""
# 决策备忘录

## 执行摘要
我们建议条件性进入商用车车规油位传感器市场。制造业上市公司具备车规级品控能力。

## 禀赋匹配
IATF16949认证已建立，客户渠道与整车厂高度重叠。
""")
    tmp.close()
    ig = IronGate(tmp.name, report_type="decision_memo", client_questions=cq)
    r = ig._check_entity_anchoring()
    t("entity_anchoring FAILs missing entities", not r.passed,
      f"passed={r.passed} det={r.details[:100]}")
    os.unlink(tmp.name)

    # 2b. 含关键实体、无禁止场景 → PASS
    tmp2 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp2.write("""
# 决策备忘录

## 执行摘要
我们建议柯力通过华虹进入加油站油位传感器市场，并整合久通渠道。危化品SIS改造是政策窗口。

## 路径决策
久通整合采用转移定价成本加成法。
""")
    tmp2.close()
    ig2 = IronGate(tmp2.name, report_type="decision_memo", client_questions=cq)
    r2 = ig2._check_entity_anchoring()
    t("entity_anchoring PASSes correct entities", r2.passed, r2.details[:80])
    os.unlink(tmp2.name)

    # 2c. 非 decision_memo 无注入 → 跳过（PASS）
    tmp3 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp3.write("行业报告。")
    tmp3.close()
    ig3 = IronGate(tmp3.name, report_type="industry_deep")
    r3 = ig3._check_entity_anchoring()
    t("entity_anchoring skips non-decision", r3.passed, r3.details[:60])
    os.unlink(tmp3.name)

    # ── 3. Gate _check_decision_engine_citation ──────────────
    # 3a. 缺卡位评分/最坏损失/投入金额 → FAIL
    tmp4 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp4.write("""
# 决策备忘录

## 执行摘要
建议条件性进入。市场空间真实但天花板清晰。该赛道适合作为传感器产品矩阵中的补充品类而非战略级新业务。

## 行业真相
全球油位传感器市场2024年46亿美元，中国166亿元。竞争格局分散，技术壁垒中等。

## 禀赋匹配度
委托方在制造工艺、客户渠道、品控体系三大维度高度匹配。技术原理存在差距但可弥补。

## 路径决策
三条路径对比：自制、外协、子公司承接。推荐子公司承接加母公司产线改造。

## 财务测算
三年投入1600-2500万。盈亏平衡期24-30个月。敏感性分析显示核心变量是锚点客户。

## 延伸产业
物位/液位大类全球规模是油位4-6倍。建议以油位为切入点逐步延伸。

## 执行路线图
Q1立项，Q2产品开发，Q3客户验证，Q4定点。18个月内验证市场可行性。
""")
    tmp4.close()
    ig4 = IronGate(tmp4.name, report_type="decision_memo")
    r4 = ig4._check_decision_engine_citation()
    t("decision_citation FAILs missing score/worst", not r4.passed,
      f"passed={r4.passed} det={r4.details[:100]}")
    os.unlink(tmp4.name)

    # 3b. 含卡位评分(X.X/5)+最坏损失金额+投入 → PASS
    tmp5 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp5.write("""
# 决策备忘录

## 执行摘要
卡位评分3.94/5，值得战略卡位。三年投入约1.5-2亿元。最坏损失约2亿元，占净利0.6倍。

## 财务测算
投入约1.5-2亿。最坏损失上限约2亿元。
""")
    tmp5.close()
    ig5 = IronGate(tmp5.name, report_type="decision_memo")
    r5 = ig5._check_decision_engine_citation()
    t("decision_citation PASSes with engine numbers", r5.passed, r5.details[:80])
    os.unlink(tmp5.name)

    # 3c. 非 decision_memo → 跳过
    tmp6 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp6.write("行业报告正文。")
    tmp6.close()
    ig6 = IronGate(tmp6.name, report_type="industry_deep")
    r6 = ig6._check_decision_engine_citation()
    t("decision_citation skips non-decision", r6.passed, r6.details[:60])
    os.unlink(tmp6.name)

    # ── 4. iron_gate.run_all 注册了新检查 ────────────────────
    try:
        import inspect
        src = inspect.getsource(IronGate.run_all)
        t("run_all registers entity_anchoring", "_check_entity_anchoring" in src)
        t("run_all registers decision_engine_citation", "_check_decision_engine_citation" in src)
    except Exception as e:
        t("run_all registers new checks", False, f"异常: {str(e)[:60]}")

    return n_pass, n_fail


if __name__ == "__main__":
    p, f = run()
    print(f"\nR84 实体锚定+决策引擎引用回归测试: {p} passed, {f} failed")
    sys.exit(1 if f else 0)

# ── P1-audit 2026-08-24 收编：原 run() 只 print 不 raise，pytest 看不见 ──
def test_orphan_suite():
    _p, _f = run()
    assert _f == 0, f"{_f} 个断言失败 / 共 {_p + _f} 条"