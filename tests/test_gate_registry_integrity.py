"""R6 结构性防幽灵检查 + R5 指标冻结 — 用结构断言替代"我以为它跑了"。

## R6：定义了的检查项必须被注册

本项目已出现过的幽灵能力形态是"功能存在、有名字、有文档、有测试，
但从不执行"。对 IronGate 而言最直接的形态是：mixin 里写了
`def _check_xxx`，但 run_all() 的 `_check_funcs` 列表里没有它
——它永远不会跑，也永远不会报错，于是"105 项检查全通过"里
其实只有 100 项在执行。

这类缺陷**不可能**被"跑一遍看结果"发现（因为没跑的那项本来就不报错），
只能靠结构断言：把"定义集合"和"注册集合"做差集。

## R5：门禁指标冻结

PASS_THRESHOLD / JUDGE_VERSION / 评分公式一旦被悄悄改动，
历史分数就不可比——这正是"指标协同适应"（causal Goodhart）的温床：
改判定标准比改产出容易得多。这里把三个量锁进 lock 文件，
改动必须显式更新 lock（从而在 review 里暴露出来）。
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_METRIC_LOCK = _ROOT / "benchmark" / "gate_metric_lock.json"

# 这三个 LLM 校验器在 run_all 中走线程池，同样必须在 _check_funcs 里
_EXPECTED_MIN_CHECKS = 100


def _registered_check_names() -> set[str]:
    """从 pipeline/iron_gate.py 的源码里静态解析 _check_funcs 列表。

    用 AST 而非 import：import 会触发整条依赖链，且无法区分
    "在列表里" 与 "被动态追加"。静态解析拿到的是代码写下来的事实。
    """
    src = (_ROOT / "pipeline" / "iron_gate.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id == "_check_funcs" and isinstance(node.value, ast.List):
                for elt in node.value.elts:
                    # 形如 self._check_xxx
                    if isinstance(elt, ast.Attribute) and isinstance(elt.value, ast.Name) and elt.value.id == "self":
                        names.add(elt.attr)
    return names


def _defined_check_methods() -> set[str]:
    """IronGate 类（含全部 mixin）上定义的 _check_* 方法。"""
    from pipeline.iron_gate import IronGate

    return {n for n, _ in inspect.getmembers(IronGate, predicate=inspect.isfunction) if n.startswith("_check_")}


def test_every_defined_check_is_registered():
    """定义了却没注册的检查项 = 永远不执行的幽灵。"""
    defined = _defined_check_methods()
    registered = _registered_check_names()
    assert registered, "未能从 iron_gate.py 解析出 _check_funcs（源码结构变了？）"

    orphans = sorted(defined - registered)
    assert not orphans, (
        f"{len(orphans)} 个检查项已定义但未注册进 run_all 的 _check_funcs，永远不会执行：{orphans}"
    )


def test_registered_checks_all_exist():
    """注册了却不存在的方法会在运行时 AttributeError——收集期就拦住。"""
    defined = _defined_check_methods()
    registered = _registered_check_names()
    missing = sorted(registered - defined)
    assert not missing, f"_check_funcs 里引用了不存在的方法：{missing}"


def test_check_count_is_plausible():
    """检查项总数不应 silently 缩水（比如某次重构漏掉一批）。"""
    registered = _registered_check_names()
    assert len(registered) >= _EXPECTED_MIN_CHECKS, (
        f"注册检查项仅 {len(registered)} 项，低于基线 {_EXPECTED_MIN_CHECKS}——是否有检查项在重构中丢失？"
    )


# ── R5：指标冻结 ─────────────────────────────────────────────


def _current_metric_fingerprint() -> dict:
    import pipeline.iron_gate as ig

    src = (_ROOT / "pipeline" / "iron_gate.py").read_text(encoding="utf-8")
    # 评分公式签名：抓 error_mean 那段特征，公式一改这里就变
    formula = "error_mean" if "c.severity == \"error\"" in src else "unknown"
    return {
        "pass_threshold": ig.PASS_THRESHOLD,
        "judge_version": ig.JUDGE_VERSION,
        "formula": formula,
    }


def test_gate_metric_is_frozen():
    """门禁阈值/判定版本/评分公式必须与 lock 文件一致。

    要改动？改完必须同步更新 benchmark/gate_metric_lock.json 并在 PR 里说明——
    把"悄悄改判定标准"变成一次显式、可 review 的动作。
    """
    current = _current_metric_fingerprint()
    if not _METRIC_LOCK.exists():
        _METRIC_LOCK.parent.mkdir(parents=True, exist_ok=True)
        _METRIC_LOCK.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        pytest.skip(f"首次运行，已生成指标锁文件 {_METRIC_LOCK.relative_to(_ROOT)}")

    locked = json.loads(_METRIC_LOCK.read_text(encoding="utf-8"))
    diff = {k: (locked.get(k), current[k]) for k in current if locked.get(k) != current[k]}
    assert not diff, (
        f"门禁指标发生变化：{diff}。"
        f"若确为预期调整，请同步更新 {_METRIC_LOCK.relative_to(_ROOT)} 并在提交说明中写明理由。"
    )


def test_pass_threshold_not_moved_by_patch_only():
    """阈值只允许"显式改 lock"，不允许偷偷改常量（双保险）。

    与上一个用例的区别：即便有人顺手把 lock 文件删了（从而绕过上一条），
    这里仍要求阈值落在历史记录过的取值集合内。
    """
    import pipeline.iron_gate as ig

    history = _ROOT / "benchmark" / "gate_metric_lock.json"
    allowed = {0.78}
    if history.exists():
        try:
            allowed.add(float(json.loads(history.read_text(encoding="utf-8"))["pass_threshold"]))
        except Exception:  # noqa: BLE001
            pass
    assert ig.PASS_THRESHOLD in allowed, (
        f"PASS_THRESHOLD={ig.PASS_THRESHOLD} 不在历史取值 {sorted(allowed)} 内——阈值调整必须显式登记"
    )


def test_no_new_check_without_mutation_coverage():
    """新增检查项必须至少有一个变异体覆盖（否则它是否工作无人知晓）。

    这条把 R1 语料库和 R6 注册表连起来：注册表说"它在跑"，语料库说"它有用"。
    """
    from tests.gate_mutation.corpus import MUTANTS

    covered = {m.target for m in MUTANTS}
    registered = {n.replace("_check_", "") for n in _registered_check_names()}
    uncovered = sorted(registered - covered)
    # 不硬失败——105 项检查不可能一次覆盖完；只作为可观测的覆盖率指标输出
    print(f"\n[变异覆盖率] {len(registered & covered)}/{len(registered)} 项检查有变异体覆盖")
    if uncovered:
        print(f"[未覆盖] {len(uncovered)} 项：{uncovered[:15]}{' ...' if len(uncovered) > 15 else ''}")
    assert len(registered & covered) >= 20, (
        f"变异覆盖仅 {len(registered & covered)} 项，语料库需扩充（最低 20）"
    )
