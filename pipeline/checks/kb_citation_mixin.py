"""P1-2 KB/MKB 引用覆盖检查（2026-09-07 收尾新增，验收报告 R4 修复项）。

文档计划（docs/MASTER_REVIEW_AND_KB_PLAN_20260907.md §10 P1-2）要求"消费端不变式"：
注入非空 → 正文 [KB#]/[MKB#]/方法名回指 ≥ 一定比例 → 否则告警/阻断。
此前 KB 注入成功后无门禁保证 LLM 真的在正文用了它——"注入成功 ≠ 消费成功"盲区。

本模块是**独立可测的纯函数**，不直接修改 IronGate 注册表（避免与并行改动纠缠），
由调用方（IronGate check 或 assemble 节点）传入注入计数与正文，返回 GateCheckResult。
"""

from __future__ import annotations

import re

from pipeline.checks.base import GateCheckResult

# KB 引用标记: 正文里应出现 [KB1]、[KB 宁德时代]、[方法论:xxx] 或方法名回指
_KB_MARK_RE = re.compile(r"\[KB\s*[:：#]?\s*\w*\]|\[KB\d+\]|\[MKB\d*\]|\[方法论[:：#]")
# P2（2026-09-07）：提取唯一 KB/MKB ID，防止同一标记在多段重复出现虚高覆盖率
_KB_ID_RE = re.compile(r"\[KB(\d+)\]")
_MKB_ID_RE = re.compile(r"\[MKB(\d+)\]")
# 常见方法论文档名关键词（allowlist 01/02/03/04/07/08/09 目录内容命中后应被正文回指）
_METHOD_TERMS = re.compile(
    r"生命周期|利润池|波特五力|竞争格局|护城河|DCF|折现|敏感性|三表|勾稽|"
    r"审计|核查|国际投行|宏观框架|产业链|景气度|SWOT|PEST|波士顿矩阵"
)


def check_kb_citation_coverage(
    report_text: str,
    injected_kb_count: int = 0,
    injected_mkb_count: int = 0,
    threshold: float = 0.5,
    mode: str = "warning",
) -> GateCheckResult:
    """检查注入的知识库/方法论是否在正文中被引用。

    Args:
        report_text: 报告正文（Gate 判定输入）
        injected_kb_count: 本轮注入的 KB 条数（来自注入审计日志，未知传 0 = 仅做弱检查）
        injected_mkb_count: 本轮注入的 MKB 条数
        threshold: 正文 KB 引用数 / 注入条数 的最低比例（默认 0.5，warning 起步）
        mode: "warning"（默认，不阻断）或 "error"（基线稳定后升级）

    Returns:
        GateCheckResult
    """
    if not report_text or len(report_text) < 300:
        return GateCheckResult("kb_citation_coverage", True, 1.0, "text too short, skipped", severity="warning")

    kb_marks_total = len(_KB_MARK_RE.findall(report_text))
    method_hits = len(_METHOD_TERMS.findall(report_text))

    # P2（2026-09-07）：cited = 唯一 KB/MKB ID 集合大小（同一 [KB1] 在 5 个
    # 段落出现只算 1 次引用），防止重复标记虚高覆盖率。方法论词仍按命中数
    # 算（多个不同方法论词说明正文确实引用了多种框架）。
    unique_kb_ids = set(_KB_ID_RE.findall(report_text))
    unique_mkb_ids = set(_MKB_ID_RE.findall(report_text))
    cited = len(unique_kb_ids) + len(unique_mkb_ids) + (1 if method_hits > 0 else 0)

    # 无注入计数信息 → 只做弱检查：正文至少出现 KB 标记或方法论关键词，否则告警
    if injected_kb_count + injected_mkb_count <= 0:
        if kb_marks_total == 0 and method_hits == 0:
            det = "未检测到 KB/MKB 引用或方法论关键词（注入计数未知，弱检查）"
            return GateCheckResult("kb_citation_coverage", False, 0.3, det, severity=mode)
        det = f"KB引用={kb_marks_total}, 方法论词命中={method_hits}（注入计数未知，弱检查通过）"
        return GateCheckResult("kb_citation_coverage", True, 0.8, det, severity="warning")

    # 有注入计数 → 强检查: 唯一引用数 ≥ 注入条数 × threshold
    injected = injected_kb_count + injected_mkb_count
    ratio = cited / injected if injected > 0 else 1.0
    passed = ratio >= threshold or len(unique_kb_ids) >= max(1, int(injected * threshold))

    det = (
        f"注入KB={injected_kb_count}, MKB={injected_mkb_count}, "
        f"唯一KB-ID={len(unique_kb_ids)}, 唯一MKB-ID={len(unique_mkb_ids)}, "
        f"方法论词={method_hits}, 覆盖率={ratio:.0%}≥{threshold:.0%}"
    )
    severity = "warning" if passed else mode
    return GateCheckResult("kb_citation_coverage", passed, min(1.0, ratio), det, severity=severity)


class KbCitationChecksMixin:
    """IronGate 接线层：把 KB/MKB 引用覆盖检查注册进 run_all。

    R61 全量守卫（test_run_all_covers_all_check_methods）要求 checks/ 下每个
    _check_* 方法都被 run_all 执行。弱检查（无注入计数）在正文完全无 KB/方法论
    痕迹时告警；e2e 主链路可通过 set_kb_injection_counts 传入写作期实际注入
    计数，把检查升级为"注入 N 条 → 正文至少消费 50%"的强不变式。
    """

    def _check_kb_citation_coverage(self) -> GateCheckResult:
        text = getattr(self, "report_text", "") or ""
        kb_n = int(getattr(self, "_kb_injected_count", 0) or 0)
        mkb_n = int(getattr(self, "_mkb_injected_count", 0) or 0)
        mkb_retrieved = int(getattr(self, "_mkb_retrieved_count", 0) or 0)
        kb_retrieved = int(getattr(self, "_kb_retrieved_count", 0) or 0)
        result = check_kb_citation_coverage(text, injected_kb_count=kb_n, injected_mkb_count=mkb_n)
        # P1: 附加 retrieved→injected 诊断（截断丢条目时预警）
        # 只在实际跑了强检查（非 early-return）且 retrieved > injected 时附加
        if result.name != "kb_citation_coverage" or "text too short" in result.details:
            return result
        truncations = []
        if kb_retrieved > 0 and kb_n > 0 and kb_retrieved > kb_n:
            truncations.append(f"KB: retrieved={kb_retrieved}>injected={kb_n} 截断丢{kb_retrieved - kb_n}条")
        if mkb_retrieved > 0 and mkb_n > 0 and mkb_retrieved > mkb_n:
            truncations.append(f"MKB: retrieved={mkb_retrieved}>injected={mkb_n} 截断丢{mkb_retrieved - mkb_n}条")
        if truncations:
            result = GateCheckResult(
                result.name,
                result.passed,
                result.score,
                result.details + " [" + "; ".join(truncations) + "]",
                severity=result.severity,
            )
        return result

    def set_kb_injection_counts(
        self,
        kb_count: int = 0,
        mkb_count: int = 0,
        retrieved_count: int = 0,
        kb_retrieved_count: int = 0,
    ) -> None:
        """供 e2e/写作器在 Gate 前注入本报告实际使用的 KB/MKB 条数。

        P1（2026-09-07）：retrieved_count = MKB 检索命中总数（截断前），
        kb_retrieved_count = KB 检索命中总数（截断前），
        供三段漏斗 retrieved→injected→cited 诊断。
        """
        self._kb_injected_count = int(kb_count or 0)
        self._mkb_injected_count = int(mkb_count or 0)
        self._mkb_retrieved_count = int(retrieved_count or 0)
        self._kb_retrieved_count = int(kb_retrieved_count or 0)
