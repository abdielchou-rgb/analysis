# -*- coding: utf-8 -*-
"""R85：叙事一致性 + 数据点引用 + self_audit 升级 回归测试

油位 v0.90 事故（2026-08-07）：委托方必答问题覆盖 PASS（四个问题都回答了），
但全在"商用车车规"语境下——答对了问题但答错了生意。

本测试守护：
  1. _check_narrative_consistency：叙事漂移（异质实体压倒关键实体）→ FAIL
  2. _check_data_point_citation：enrich 关键数据点缺失 → FAIL
  3. 正确生意文本 → 两条都 PASS（不误杀）
  4. self_audit 报告内容一致性检查生效

可独立运行：python tests/test_r85_narrative.py
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

    from pipeline.iron_gate import IronGate

    # ── 1. 叙事一致性：错误生意文本 → FAIL ─────────────────
    # 用 v0.90 真实开头（商用车车规主导），加长避免<300字跳过
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp.write("""
# 决策备忘录

## 执行摘要
建议条件性进入商用车车规油位传感器市场。制造业上市公司具备车规级品控能力。IATF16949认证已建立。

## 禀赋匹配
客户渠道与商用车整车厂高度重叠。国四排放法规驱动工程机械液位监测需求。苏奥传感是主要国产对手。商用车市场规模稳定，整车厂供应商切换成本高。

## 财务测算
三年投入1600-2500万。盈亏平衡期24-30个月。敏感性分析显示核心变量是锚点客户。工程机械液压油箱液位监测是增量市场，混合动力商用车双油箱增加复杂度。

## 延伸产业
雷达物位计毛利率50-60%。工业过程仪表国产化是政策鼓励方向。新能源商用车混动增加油箱复杂度。

## 执行路线图
Q1立项，Q2产品开发，Q3客户验证，Q4定点。工程机械挖掘机是重点目标市场。
""")
    tmp.close()
    ig = IronGate(tmp.name, report_type="decision_memo")
    r = ig._check_narrative_consistency()
    t("narrative FAILs wrong business", not r.passed,
      f"passed={r.passed} det={r.details[:100]}")
    os.unlink(tmp.name)

    # ── 2. 叙事一致性：正确生意文本 → PASS ─────────────────
    tmp2 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp2.write("""
# 决策备忘录：柯力油位整合可行性

## 执行摘要
卡位评分3.94/5，值得战略卡位。柯力通过华虹进入加油站油位市场，整合久通渠道。危化品SIS改造是政策窗口。三年投入约1.5-2亿元，最坏损失约2亿。

## 行业真相
全球46亿美元(2024)→65亿(2030)，中国166亿元。托肯恒山是中石化核心供应商，富仁高科主导国标。磁致伸缩丝被TDK垄断。防渗改造执行率62%，2026H2替换高峰。

## 路径决策
久通整合采用转移定价。华虹生产为主。加油站防渗改造与危化品储罐SIS是核心场景。
""")
    tmp2.close()
    ig2 = IronGate(tmp2.name, report_type="decision_memo")
    r2 = ig2._check_narrative_consistency()
    t("narrative PASSes correct business", r2.passed, r2.details[:80])
    os.unlink(tmp2.name)

    # ── 3. 数据点引用：错误生意缺 enrich 数据 → FAIL ────────
    tmp3 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp3.write("""
# 决策备忘录

## 执行摘要
建议条件性进入商用车车规油位传感器市场。制造业上市公司具备车规级品控能力。

## 禀赋匹配
IATF16949认证已建立，客户渠道与商用车整车厂高度重叠。国四法规驱动工程机械液位需求。车规认证周期12-18个月。

## 财务测算
三年投入1600-2500万。最坏损失1650万占净利润2-3%。盈亏平衡期24-30个月。敏感性分析显示核心变量是锚点客户是否落地。

## 延伸产业
雷达物位计毛利率50-60%。工业过程仪表国产化。新能源商用车混动增加油箱复杂度。

## 执行路线图
Q1立项，Q2产品开发，Q3客户验证，Q4定点。工程机械挖掘机是重点目标市场。苏奥传感是主要对手。
""")
    tmp3.close()
    ig3 = IronGate(tmp3.name, report_type="decision_memo")
    r3 = ig3._check_data_point_citation()
    t("data_point FAILs missing enrich data", not r3.passed,
      f"passed={r3.passed} det={r3.details[:100]}")
    os.unlink(tmp3.name)

    # ── 4. 数据点引用：正确生意 → PASS ─────────────────────
    tmp4 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp4.write("""
# 决策备忘录：柯力油位整合可行性

## 执行摘要
卡位评分3.94/5，值得战略卡位。柯力通过华虹进入加油站油位市场，整合久通渠道。危化品SIS改造是窗口。三年投入约1.5-2亿元，最坏损失约2亿。

## 行业真相
全球46亿美元(2024)→65亿(2030)，中国166亿元。托肯恒山是中石化核心供应商。磁致伸缩丝被TDK垄断。防渗改造执行率62%，2026H2替换高峰。

## 路径决策
久通整合采用转移定价。华虹生产为主。
""")
    tmp4.close()
    ig4 = IronGate(tmp4.name, report_type="decision_memo")
    r4 = ig4._check_data_point_citation()
    t("data_point PASSes correct business", r4.passed, r4.details[:80])
    os.unlink(tmp4.name)

    # ── 5. 非 decision_memo → 两条都跳过（PASS）─────────────
    tmp5 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp5.write("行业报告正文内容。油位传感器市场空间充足。")
    tmp5.close()
    ig5 = IronGate(tmp5.name, report_type="industry_deep")
    r5a = ig5._check_narrative_consistency()
    r5b = ig5._check_data_point_citation()
    t("narrative skips non-decision", r5a.passed, r5a.details[:60])
    t("data_point skips non-decision", r5b.passed, r5b.details[:60])
    os.unlink(tmp5.name)

    # ── 6. iron_gate.run_all 注册了新检查 ───────────────────
    try:
        import inspect
        src = inspect.getsource(IronGate.run_all)
        t("run_all registers narrative_consistency", "_check_narrative_consistency" in src)
        t("run_all registers data_point_citation", "_check_data_point_citation" in src)
    except Exception as e:
        t("run_all registers new checks", False, f"异常: {str(e)[:60]}")

    # ── 7. self_audit 报告内容一致性 ────────────────────────
    try:
        import subprocess, sys as _sys
        r = subprocess.run([_sys.executable, str(_ROOT / "_self_audit.py")],
                           capture_output=True, text=True, timeout=60)
        has_p104 = "P1-04" in r.stdout
        # 当前 v0.90 存在 → 内容一致性应 FAIL（Fail>=1）
        t("self_audit has P1-04 check", has_p104, r.stdout[:200])
    except Exception as e:
        t("self_audit has P1-04 check", False, f"异常: {str(e)[:60]}")

    return n_pass, n_fail


if __name__ == "__main__":
    p, f = run()
    print(f"\nR85 叙事一致性+数据点引用回归测试: {p} passed, {f} failed")
    sys.exit(1 if f else 0)
