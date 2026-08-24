"""agent_graph 输出契约回归测试

背景（2026-08-01 审计）：
  agent_graph._run_node 曾用 `result.validation_issues = issues` 覆盖契约违例，
  导致 error 级契约（data 缺 collected_data、write 缺 report_text）从不失败节点，
  契约机制形同虚设。

本测试锁定修复后的行为：
  1. error 级契约违例 → 节点 FAILED
  2. warning 级契约违例 → 节点 PASSED（只记录，不阻断）
  3. validator issues 与契约违例合并，不互相覆盖
  4. 依赖失败的节点被 SKIPPED，不影响已通过节点
  5. 环检测仍然有效
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.agent_graph import NODE_FAILED, NODE_PASSED, NODE_SKIPPED, AgentGraph


# ── 1. error 级契约违例 → 节点 FAILED ────────────────────────────
def test_error_contract_blocks_node():
    g = AgentGraph("test_error_contract")
    g.add_node(
        "data",
        lambda nid, ctx: {"something_else": 1},  # 不产出 collected_data
        deps=[],
        output_contract={"collected_data": {"type": dict, "required": True, "severity": "error"}},
    )
    r = g.run({})
    assert r.nodes["data"].status == NODE_FAILED, f"error 级契约违例必须阻断节点, got {r.nodes['data'].status}"
    assert r.nodes["data"].validation_issues, "应记录契约违例"
    assert any("contract error" in i for i in r.nodes["data"].validation_issues)
    assert r.passed is False


# ── 2. warning 级契约违例 → 节点 PASSED ───────────────────────────
def test_warning_contract_does_not_block():
    g = AgentGraph("test_warning_contract")
    g.add_node(
        "data",
        lambda nid, ctx: {"collected_data": {}},  # 产出存在但空 dict
        deps=[],
        output_contract={"collected_data": {"type": dict, "required": True, "severity": "warning"}},
    )
    r = g.run({})
    assert r.nodes["data"].status == NODE_PASSED, f"warning 级契约不应阻断, got {r.nodes['data'].status}"
    assert r.passed is True


# ── 3. 契约违例与 validator issues 合并，不互相覆盖 ────────────────
def test_contract_and_validator_issues_merge():
    def bad_validator(nid, output):
        return ["validator issue"]

    g = AgentGraph("test_merge")
    g.add_node(
        "data",
        lambda nid, ctx: {"something_else": 1},
        deps=[],
        validators=[bad_validator],
        output_contract={"collected_data": {"type": dict, "required": True, "severity": "error"}},
    )
    r = g.run({})
    issues = r.nodes["data"].validation_issues
    assert any("contract error" in i for i in issues), "契约违例必须保留"
    assert any("validator issue" in i for i in issues), "validator issue 必须保留"


# ── 4. 依赖失败的节点被 SKIPPED，不影响其他节点 ───────────────────
def test_dependency_failure_skips_downstream():
    g = AgentGraph("test_dep_skip")
    g.add_node(
        "a",
        lambda nid, ctx: {"x": 1},
        deps=[],
        output_contract={"must_exist": {"type": str, "required": True, "severity": "error"}},
    )
    g.add_node("b", lambda nid, ctx: {"y": 2}, deps=["a"])
    g.add_node("c", lambda nid, ctx: {"z": 3}, deps=[])
    r = g.run({})
    assert r.nodes["a"].status == NODE_FAILED, "a 应失败（契约违例）"
    assert r.nodes["b"].status == NODE_SKIPPED, "b 依赖 a，应被跳过"
    assert r.nodes["c"].status == NODE_PASSED, "c 独立，应通过"


# ── 5. 环检测仍然有效 ────────────────────────────────────────────
def test_cycle_detection():
    g = AgentGraph("test_cycle")
    g.add_node("a", lambda nid, ctx: {}, deps=["b"])
    g.add_node("b", lambda nid, ctx: {}, deps=["a"])
    try:
        g.run({})
        assert False, "环应被检测并抛异常"
    except RuntimeError as e:
        assert "cycle" in str(e).lower()


# ── 6. 正常节点输出 merge 进 context 供下游使用 ───────────────────
def test_dict_output_merges_into_context():
    g = AgentGraph("test_merge_ctx")
    g.add_node("a", lambda nid, ctx: {"fig_revenue_trend": {2024: 1.0}}, deps=[])
    captured = {}

    def consumer(nid, ctx):
        captured["rev"] = ctx.get("fig_revenue_trend")
        return {}

    g.add_node("b", consumer, deps=["a"])
    r = g.run({})
    assert r.passed is True
    assert captured.get("rev") == {2024: 1.0}, "上游 dict 输出应自动 merge 进 context"


# ── 7. 子字段契约校验（dict 的 keys 检查）────────────────────────
def test_subkey_contract_check():
    g = AgentGraph("test_subkey")
    g.add_node(
        "data",
        lambda nid, ctx: {"collected_data": {"chart_data": {}}},  # 缺 fig_revenue_trend
        deps=[],
        output_contract={
            "collected_data": {
                "type": dict,
                "required": True,
                "severity": "error",
                "keys": ["chart_data"],
            }
        },
    )
    r = g.run({})
    # 顶层 key 存在 → 通过（子键只记录 warning）
    assert r.nodes["data"].status == NODE_PASSED


if __name__ == "__main__":
    import traceback

    passed = 0
    failed = 0
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
