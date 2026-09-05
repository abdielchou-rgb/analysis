"""
Cell-level Provenance Tracker — 每个计算值的来源追踪。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CellProvenanceRecord:
    """单个单元格的溯源记录"""

    cell_id: str
    value: Any
    formula: str = ""
    inputs: dict[str, str] = field(default_factory=dict)
    source_file: str = ""
    source_doc: str = ""
    timestamp: str = ""


class ProvenanceTracker:
    """全局溯源追踪器 — 记录所有计算值的来源链"""

    def __init__(self):
        self._cells: dict[str, CellProvenanceRecord] = {}

    def record(
        self,
        cell_id: str,
        value: Any,
        formula: str = "",
        inputs: Optional[dict[str, str]] = None,
        source_file: str = "",
        source_doc: str = "",
    ) -> None:
        self._cells[cell_id] = CellProvenanceRecord(
            cell_id=cell_id,
            value=value,
            formula=formula,
            inputs=inputs or {},
            source_file=source_file,
            source_doc=source_doc,
        )

    def get(self, cell_id: str) -> Optional[CellProvenanceRecord]:
        return self._cells.get(cell_id)

    def get_trace(self, cell_id: str) -> list[CellProvenanceRecord]:
        """获取完整的依赖链"""
        trace = []
        visited = set()
        self._trace_recursive(cell_id, trace, visited)
        return trace

    def _trace_recursive(self, cell_id: str, trace: list, visited: set) -> None:
        if cell_id in visited:
            return
        visited.add(cell_id)
        record = self._cells.get(cell_id)
        if record:
            trace.append(record)
            for input_id in record.inputs.values():
                self._trace_recursive(input_id, trace, visited)

    def to_audit_report(self) -> str:
        """生成人类可读的审计报告"""
        lines = ["=== Provenance Audit Report ==="]
        for cell_id, record in sorted(self._cells.items()):
            lines.append(f"  {cell_id} = {record.value}")
            if record.formula:
                lines.append(f"    formula: {record.formula}")
            if record.inputs:
                lines.append(f"    inputs: {record.inputs}")
            if record.source_file:
                lines.append(f"    source: {record.source_file}")
        lines.append(f"  Total cells tracked: {len(self._cells)}")
        return "\n".join(lines)

    def summary(self) -> dict:
        return {
            "total_cells": len(self._cells),
            "with_formula": sum(1 for r in self._cells.values() if r.formula),
            "with_source": sum(1 for r in self._cells.values() if r.source_file),
        }
