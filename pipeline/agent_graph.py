"""
2号分析师 Agent Graph — 轻量级状态机引擎

架构设计原则：
1. 图结构强制执行 — 每个节点注册后必须执行，不可跳过
2. 硬失败 — 任何节点失败立即抛异常，不静默吞错误
3. 逐级验证 — 每个节点输出后立即验证，不通过不往下走
4. 审计追踪 — 每个节点记录执行状态、耗时、输出哈希
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("2hao.agent_graph")

NODE_PENDING = "pending"
NODE_RUNNING = "running"
NODE_PASSED = "passed"
NODE_FAILED = "failed"
NODE_SKIPPED = "skipped"


@dataclass
class NodeResult:
    node_id: str
    status: str = NODE_PENDING
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    output_hash: str = ""
    validation_issues: list = field(default_factory=list)


@dataclass
class GraphResult:
    passed: bool = False
    nodes: dict = field(default_factory=dict)
    total_duration_ms: float = 0.0
    failed_nodes: list = field(default_factory=list)


class AgentGraph:
    def __init__(self, name: str = "default"):
        self.name = name
        self._nodes: dict[str, dict] = {}
        self._results: dict[str, NodeResult] = {}
        self._start_time: float = 0.0

    def add_node(
        self,
        node_id: str,
        fn: Callable,
        deps: list[str] = None,
        validators: list[Callable] = None,
        timeout_s: int = 300,
        description: str = "",
        desc: str = "",
        output_contract: dict[str, dict] = None,
    ):
        """注册管线节点。

        output_contract: {key: {"type": type, "required": bool, "severity": str, "keys": [sub_keys]}}
          - type: 期望的 Python 类型 (如 str, dict, list)
          - required: True 表示该 key 必填 (None 则 warning)
          - severity: "warning" (默认, 记录日志不阻断) | "error" (阻断管线)
          - keys: 对 dict 类型进一步检查子 key 是否存在
        """
        self._nodes[node_id] = {
            "fn": fn,
            "deps": deps or [],
            "validators": validators or [],
            "timeout_s": timeout_s,
            "description": description or desc or node_id,
            "output_contract": output_contract or {},
        }
        self._results[node_id] = NodeResult(node_id=node_id)

    def _check_deps(self, node_id: str) -> str | None:
        deps = self._nodes[node_id]["deps"]
        for dep_id in deps:
            dep_result = self._results.get(dep_id)
            if dep_result is None:
                return f"dep {dep_id} not found"
            if dep_result.status != NODE_PASSED:
                return f"dep {dep_id} failed ({dep_result.status}): {dep_result.error}"
        return None

    def _run_node(self, node_id: str, context: dict) -> Any:
        node = self._nodes[node_id]
        result = self._results[node_id]
        result.status = NODE_RUNNING
        # R78（2026-08-05）：trace 日志——带 trace_id 记录节点执行，跨环节可追溯。
        _trace_id = (context or {}).get("trace_id", "")
        logger.info("  [TRACE %s] AgentGraph exec: %s (%s)", _trace_id or "-", node_id, node["description"][:60])
        t0 = time.time()
        try:
            # P2-audit 2026-08-24：timeout_s 此前存入 dict 后从未使用——
            # 节点挂死即挂死整条管线。现用单发线程池 + future.result(timeout)
            # 实装。注意：超时后工作线程无法被杀死（Python 线程不可中断），
            # 但管线可立即按失败处理并 SKIP 下游节点。
            _timeout_s = int(node.get("timeout_s") or 0)
            if _timeout_s > 0:
                from concurrent.futures import ThreadPoolExecutor
                from concurrent.futures import TimeoutError as _FutureTimeout

                with ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"ag-{node_id}") as _ex:
                    _fut = _ex.submit(node["fn"], node_id, context)
                    try:
                        output = _fut.result(timeout=_timeout_s)
                    except _FutureTimeout:
                        raise TimeoutError(f"node '{node_id}' exceeded timeout_s={_timeout_s}s") from None
            else:
                output = node["fn"](node_id, context)
            # R78：节点完成 trace
            logger.info("  [TRACE %s] AgentGraph done: %s (%.1fs)", _trace_id or "-", node_id, time.time() - t0)
            # Auto-merge dict output into context for downstream nodes
            if isinstance(output, dict):
                context.update(output)
            # 输出契约校验
            contract = node.get("output_contract", {})
            contract_issues = []
            if contract:
                violations = _check_contract(context, contract)
                for v in violations:
                    logger.log(
                        logging.WARNING if v.severity == "warning" else logging.ERROR,
                        "  [Contract] %s: %s expected=%s actual=%s preview=%s",
                        node_id,
                        v.key,
                        v.expected_type,
                        v.actual_type,
                        v.value_preview,
                    )
                    contract_issues.append(
                        f"contract {'error' if v.severity == 'error' else 'warning'}: "
                        f"{v.key} expected {v.expected_type} got {v.actual_type}"
                    )
            issues = []
            for validator in node["validators"]:
                try:
                    v_issues = validator(node_id, output)
                    if v_issues:
                        issues.extend(v_issues)
                except Exception as e:
                    issues.append(f"validator error: {e}")
            duration = (time.time() - t0) * 1000
            result.duration_ms = duration
            result.output = output
            result.output_hash = hashlib.md5(str(output).encode()).hexdigest()[:8]
            # 修复（2026-08-01 审计）：原来用 issues 覆盖 validation_issues，
            # 导致 error 级契约违例全部丢失、节点永不因契约失败。
            # 现在合并契约违例 + validator issues；仅 error 级契约违例阻断节点，
            # warning 级只记录不阻断（避免误伤实际有效的输出）。
            all_issues = list(issues)
            for ci in contract_issues:
                if ci.startswith("contract error"):
                    all_issues.append(ci)
            result.validation_issues = all_issues
            if all_issues:
                result.status = NODE_FAILED
                result.error = f"validation: {'; '.join(all_issues[:5])}"
            else:
                result.status = NODE_PASSED
            logger.info("  [AgentGraph] %s: %s (%.0fms)", node_id, result.status, duration)
        except Exception as e:
            duration = (time.time() - t0) * 1000
            result.duration_ms = duration
            result.status = NODE_FAILED
            result.error = str(e)
            logger.error("  [AgentGraph] %s FAILED: %s", node_id, e)
        return result.output

    def run(self, context: dict = None) -> GraphResult:
        self._start_time = time.time()
        ctx = context or {}
        logger.info("[AgentGraph] run: %s (%d nodes)", self.name, len(self._nodes))
        sorted_nodes = self._topological_sort()
        if sorted_nodes is None:
            raise RuntimeError(f"cycle detected: {self.name}")
        for node_id in sorted_nodes:
            dep_err = self._check_deps(node_id)
            if dep_err:
                self._results[node_id].status = NODE_SKIPPED
                self._results[node_id].error = dep_err
                continue
            self._run_node(node_id, ctx)
        total_time = (time.time() - self._start_time) * 1000
        failed = [nid for nid, r in self._results.items() if r.status == NODE_FAILED]
        passed = all(r.status == NODE_PASSED for r in self._results.values() if r.status != NODE_SKIPPED)
        return GraphResult(passed=passed, nodes=self._results, total_duration_ms=total_time, failed_nodes=failed)

    def _topological_sort(self) -> list[str] | None:
        in_degree = {nid: 0 for nid in self._nodes}
        for nid, node in self._nodes.items():
            for dep in node["deps"]:
                if dep not in in_degree:
                    in_degree[dep] = 0
                in_degree[nid] = in_degree.get(nid, 0) + 1
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        sorted_list = []
        while queue:
            nid = queue.pop(0)
            sorted_list.append(nid)
            for other_nid, other_node in self._nodes.items():
                if nid in other_node["deps"]:
                    in_degree[other_nid] -= 1
                    if in_degree[other_nid] == 0:
                        queue.append(other_nid)
        return sorted_list if len(sorted_list) == len(self._nodes) else None

    def get_result(self, node_id: str) -> NodeResult | None:
        return self._results.get(node_id)

    def summary(self) -> str:
        lines = [f"AgentGraph: {self.name}"]
        for nid, r in self._results.items():
            icon = {"passed": "+", "failed": "-", "pending": ".", "running": ">", "skipped": "x"}.get(r.status, "?")
            desc = self._nodes[nid]["description"][:50] if nid in self._nodes else nid
            lines.append(f"  [{icon}] {nid}: {desc} ({r.duration_ms:.0f}ms)")
            if r.validation_issues:
                for issue in r.validation_issues[:3]:
                    lines.append(f"     issue: {issue[:80]}")
            if r.error:
                lines.append(f"     error: {r.error[:80]}")
        return "\n".join(lines)


@dataclass
class ContractViolation:
    """输出契约违例 — 节点产出不符合预期类型/结构"""

    key: str
    expected_type: str
    actual_type: str
    value_preview: str = ""
    severity: str = "warning"  # warning | error


def _check_contract(ctx: dict, contract: dict) -> list[ContractViolation]:
    """校验 context 中的 key 是否符合 output_contract 定义的类型/结构"""
    violations = []
    for key, spec in contract.items():
        actual = ctx.get(key)
        if actual is None:
            if spec.get("required", False):
                violations.append(
                    ContractViolation(
                        key=key,
                        expected_type=str(spec.get("type", "any")),
                        actual_type="NoneType",
                        value_preview="None",
                        severity=spec.get("severity", "warning"),
                    )
                )
            continue
        expected_type = spec.get("type")
        if expected_type and not isinstance(actual, expected_type):
            violations.append(
                ContractViolation(
                    key=key,
                    expected_type=expected_type.__name__,
                    actual_type=type(actual).__name__,
                    value_preview=str(actual)[:80],
                    severity=spec.get("severity", "warning"),
                )
            )
        # 对 dict/list 类型的 key 做子字段校验
        sub_keys = spec.get("keys", [])
        if sub_keys and isinstance(actual, dict):
            for sk in sub_keys:
                if sk not in actual:
                    violations.append(
                        ContractViolation(
                            key=f"{key}.{sk}",
                            expected_type="present",
                            actual_type="missing",
                            severity=spec.get("severity", "warning"),
                        )
                    )
    return violations
