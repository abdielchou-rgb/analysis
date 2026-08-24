"""R65 (2026-08-04) 回归测试 — FP8 元认知选择层

覆盖：
1. analyst_planner 框架选择（按报告类型/数据充足度）
2. 维度聚焦（数据不足时聚焦核心，充足时全量）
3. 降级策略声明（FP2a 诚实标注）
4. method_reflection 回写 registry（FP5 演化）
5. scheduler 接入方案规划（语法/import 兼容）
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_REG = _ROOT / "data" / "framework_registry.json"


def test_planner_selects_frameworks():
    """数据充足时应选多框架组合。"""
    from core.analyst_planner import AnalystPlanner

    p = AnalystPlanner()
    plan = p.plan("气体传感器", "industry_deep", {"sufficient": True}, "传感器")
    assert plan["frameworks"], "数据充足应选到框架"
    assert plan["fp8_compliant"]["no_gate_exemption"], "FP8 不得豁免 Gate"
    assert plan["method_rationale"], "方法选择须可解释"


def test_planner_poor_data_focuses_core():
    """数据不足时聚焦核心维度 + 声明降级。"""
    from core.analyst_planner import AnalystPlanner

    p = AnalystPlanner()
    plan = p.plan(
        "某标的", "listed_company", {"sufficient": False, "semantic_gap": ["渗透率"], "missing_partial": ["行情"]}, ""
    )
    assert plan["degradation"], "数据不足应声明降级策略"
    # 降级策略应含诚实标注
    assert any("confidence" in str(d) or "不可得" in str(d) or "不硬凑" in str(d) for d in plan["degradation"]), (
        "降级须诚实标注（FP2a）"
    )


def test_planner_focus_rationale():
    """维度裁剪须有理由（FP8-3 数据驱动）。"""
    from core.analyst_planner import AnalystPlanner

    p = AnalystPlanner()
    plan = p.plan("测试", "industry_deep", {"sufficient": False, "semantic_gap": ["x"]}, "")
    assert plan["sac_focus"]["rationale"], "维度裁剪须有理由"
    assert "数据" in plan["sac_focus"]["rationale"], "裁剪理由须数据驱动"


def test_registry_schema():
    """framework_registry.json 结构合法。"""
    reg = json.loads(_REG.read_text(encoding="utf-8"))
    assert "frameworks" in reg, "registry 须有 frameworks"
    assert len(reg["frameworks"]) >= 5, "至少 5 个子框架"
    for fw in reg["frameworks"]:
        assert fw["id"], "框架须有 id"
        assert fw.get("适用条件"), "框架须有适用条件"
        assert fw.get("映射SAC"), "框架须映射 SAC 维度"
        assert fw.get("效果", {}).get("平均Gate分", 0) > 0, "框架须有效果基线"


def test_method_reflection_updates_registry():
    """method_reflection 应回写 registry 效果字段（FP5 演化）。"""
    import json as _json

    from core.method_reflection import record_reflection

    # 备份原值
    reg = _json.loads(_REG.read_text(encoding="utf-8"))
    orig = {}
    for fw in reg["frameworks"]:
        if fw["id"] == "bottleneck_engine":
            orig = dict(fw["效果"])
    try:
        ok = record_reflection(
            "回归测试", "industry_deep", ["bottleneck_engine"], 0.99, {"sufficient": True}, "r65 回归测试"
        )
        assert ok, "反思记录应成功"
        reg2 = _json.loads(_REG.read_text(encoding="utf-8"))
        for fw in reg2["frameworks"]:
            if fw["id"] == "bottleneck_engine":
                # R77(2026-08-05 P0-3)：估算基线首次被实测覆盖时重置次数为 1，
                # 之后才滑动累计。orig 可能是估算基线（3）或已实测值（N）。
                if orig.get("数据来源", "").startswith("估算"):
                    assert fw["效果"]["已用次数"] == 1, "估算基线首次实测应重置为1"
                else:
                    assert fw["效果"]["已用次数"] == orig["已用次数"] + 1, "已用次数应+1"
                break
    finally:
        # 恢复原值 + 清理日志
        reg3 = _json.loads(_REG.read_text(encoding="utf-8"))
        for fw in reg3["frameworks"]:
            if fw["id"] == "bottleneck_engine":
                fw["效果"] = orig
                break
        _REG.write_text(_json.dumps(reg3, ensure_ascii=False, indent=2), encoding="utf-8")
        log_path = _ROOT / "data" / "method_reflection_log.json"
        if log_path.exists():
            log = _json.loads(log_path.read_text(encoding="utf-8"))
            log["entries"] = [e for e in log["entries"] if e.get("asset") != "回归测试"]
            log_path.write_text(_json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def test_scheduler_imports_planner():
    """scheduler.py 应能 import（含 FP8 方案规划接入）。"""
    import ast

    src = (_ROOT / "pipeline" / "scheduler.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert "analyst_planner" in src, "scheduler 应引用 analyst_planner"
    assert "build_analysis_plan" in src, "scheduler 应调用 build_analysis_plan"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
