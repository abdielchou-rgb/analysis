# -*- coding: utf-8 -*-
"""Report Assembler - 报告组装器

核心原则：
- 从 Section 生成完整报告
- 嵌入 Knowledge Lineage 附录
- 生成 Pipeline Fingerprint
- 导出多格式：MD、DOCX、JSON
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from core.analysis_context import AnalysisContext
from core.finding_store import LineageTracker


@dataclass(frozen=True)
class ReportMetadata:
    """报告元数据"""

    asset: str
    report_type: str
    style: str
    generated_at: datetime
    pipeline_version: str
    gate_score: float
    gate_passed: bool
    attempt: int
    total_time_seconds: float
    llm_calls: int
    total_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class ReportArtifact:
    """报告产物"""

    markdown: str
    docx_path: Optional[str] = None
    json_path: Optional[str] = None
    metadata: Optional["ReportMetadata"] = None
    lineage: Optional[Dict] = None
    fingerprint: Optional[str] = None


@dataclass
class ReportAssembler:
    """报告组装器"""

    def __init__(self):
        self._templates: Dict[str, str] = {}
        self._load_templates()

    def _load_templates(self):
        """加载报告模板"""
        self._templates = {
            "header": """# {asset} {report_type_name}

**报告类型**: {report_type}
**风格**: {style}
**生成时间**: {generated_at}
**Pipeline 版本**: {pipeline_version}
**Gate 得分**: {gate_score:.2f} ({gate_status})
**尝试次数**: {attempt}
**耗时**: {total_time:.1f}s
**LLM 调用**: {llm_calls} 次
**Token 总量**: {total_tokens:,}
**预估成本**: ${cost_usd:.4f}

---
""",
            "toc": """## 目录

{toc_items}

---
""",
            "section": "## {section_id}\n\n{content}\n\n",
            "footer": """---

## 附录

### 知识谱系
{lineage_summary}

### 方法论谱系
{method_lineage_summary}

### 执行追踪
{execution_trace}

### Pipeline Fingerprint
{fingerprint}

---
*报告生成时间: {generated_at}*
*Pipeline 版本: {pipeline_version}*
*Gate 得分: {gate_score:.2f} ({gate_status})*
""",
            "cicc": """# {asset} 深度研究报告

**报告类型**: {report_type}
**风格**: 中金 (CICC)
**生成时间**: {generated_at}
**Pipeline 版本**: {pipeline_version}
**Gate 得分**: {gate_score:.2f} ({gate_status})

---

{sections}

---

## 附录

### 知识谱系
{lineage_summary}

### 方法论谱系
{method_lineage_summary}

### 执行追踪
{execution_trace}

### Pipeline Fingerprint
{fingerprint}

---
*报告生成时间: {generated_at}*
*Pipeline 版本: {pipeline_version}*
*Gate 得分: {gate_score:.2f} ({gate_status})*
""",
        }

    def assemble(
        self,
        context: "AnalysisContext",
        metadata: "ReportMetadata",
        lineage_tracker: "LineageTracker",
        style: str = "cicc",
    ) -> "ReportArtifact":
        """组装完整报告"""

        # 1. 生成目录
        toc = self._generate_toc(context)

        # 2. 组装正文
        sections_md = self._assemble_sections(context)

        # 3. 生成知识谱系附录
        lineage_md = self._generate_lineage_appendix(context, lineage_tracker)

        # 4. 生成方法论谱系
        method_lineage_md = self._generate_method_lineage(context)

        # 4. 生成执行追踪
        trace_md = self._generate_execution_trace(context)

        # 4. 生成 Fingerprint
        fingerprint = self._generate_fingerprint(context)

        # 5. 组装完整报告
        template = self._templates.get("cicc", self._templates.get("default", ""))

        markdown = template.format(
            asset=context.intent.asset,
            report_type=context.intent.report_type.value,
            report_type_name=self._get_report_type_name(context.intent.report_type),
            style="中金 (CICC)",
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            pipeline_version="2.0.0",
            gate_score=context.gate_results.score if context.gate_results else 0.0,
            gate_status="通过" if (context.gate_results and context.gate_results.passed) else "未通过",
            attempt=context.metadata.get("attempt", 1) if hasattr(context, "metadata") else 1,
            total_time=0.0,  # TODO
            llm_calls=0,  # TODO
            total_tokens=0,  # TODO
            cost_usd=0.0,  # TODO
            sections=sections_md,
            lineage_summary="知识谱系摘要",  # TODO
            method_lineage_summary="方法论谱系摘要",  # TODO
            execution_trace="执行追踪",  # TODO
            fingerprint="fingerprint_placeholder",  # TODO
        )

        # 生成 Fingerprint
        fingerprint = self._generate_fingerprint(context)

        # 构建产物
        artifact = ReportArtifact(
            markdown=markdown,
            metadata=ReportMetadata(
                asset=context.intent.asset,
                report_type=context.intent.report_type.value,
                style="cicc",
                generated_at=datetime.now(),
                pipeline_version="2.0.0",
                gate_score=context.gate_results.score if context.gate_results else 0.0,
                gate_passed=context.gate_results.passed if context.gate_results else False,
                attempt=context.metadata.get("attempt", 1) if hasattr(context, "metadata") else 1,
                total_time_seconds=0.0,
                llm_calls=0,
                total_tokens=0,
                cost_usd=0.0,
            ),
            lineage=lineage_tracker.export_lineage() if lineage_tracker else None,
            fingerprint=fingerprint,
        )

        return artifact

    def _generate_toc(self, context: "AnalysisContext") -> str:
        """生成目录"""
        items = []
        for i, section in enumerate(context.sections, 1):
            items.append(f"{i}. [{section.title}](#{section.section_id.lower().replace(' ', '-')})")
        return "\n".join(items)

    def _assemble_sections(self, context: "AnalysisContext") -> str:
        """组装正文章节"""
        parts = []
        for section in context.sections:
            content = section.content if hasattr(section, "content") else ""
            parts.append(f"## {section.title}\n\n{content}\n")
        return "\n\n".join(parts)

    def _generate_lineage_appendix(self, context: "AnalysisContext", lineage_tracker: "LineageTracker") -> str:
        """生成知识谱系附录"""
        if not lineage_tracker:
            return "知识谱系附录 (无谱系追踪器)"

        lineage_data = lineage_tracker.export_lineage()
        claims = lineage_data.get("claims", {})

        if not claims:
            return "知识谱系附录 (无 Claim 数据)"

        parts = ["## 知识谱系附录\n"]

        # 按 Section 分组
        section_claims = defaultdict(list)
        for claim_id, claim in claims.items():
            section = claim.get("section", "未知章节")
            section_claims[section].append(claim)

        for section, claims_list in sorted(section_claims.items()):
            parts.append(f"\n### {section}\n")
            for claim in claims_list:
                method = claim.get("method", "未知方法")
                mkb_refs = claim.get("mkb_refs", [])
                gate_status = "✅" if claim.get("gate_passed") else "❌"
                mkb_str = f" [MKB: {', '.join(mkb_refs)}]" if mkb_refs else ""
                parts.append(
                    f"- **{claim.get('claim_id', 'unknown')}** ({method}) {gate_status}{mkb_str}: {claim.get('text', '')[:100]}...\n"
                )

        return "\n".join(parts)

    def _generate_method_lineage(self, context: "AnalysisContext") -> str:
        """生成方法论谱系"""
        # TODO: 从 LineageTracker 获取方法论使用统计
        return "方法论谱系 (待实现)"

    def _generate_execution_trace(self, context: "AnalysisContext") -> str:
        """生成执行追踪"""
        parts = ["## 执行追踪\n"]

        # 性能指标
        if hasattr(context, "performance") and context.performance:
            parts.append("\n### 性能指标\n")
            for key, value in context.performance.items():
                parts.append(f"- {key}: {value}")

        # 节点执行历史
        if hasattr(context, "_node_executions") and context._node_executions:
            parts.append("\n### 节点执行历史\n")
            for node_exec in context._node_executions:
                parts.append(f"- {node_exec['node']}: {node_exec['status']} ({node_exec['duration_ms']}ms)")

        return "\n".join(parts)

    def _generate_fingerprint(self, context: "AnalysisContext") -> str:
        """生成 Pipeline Fingerprint"""
        content = f"{context.intent.asset}:{context.intent.report_type.value}:{context.gate_results.score if context.gate_results else 0}:{datetime.now().date()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_report_type_name(self, report_type: "IntentType") -> str:
        names = {
            "listed_company": "上市公司深度研究",
            "industry_deep": "行业深度研究",
            "unlisted_company": "非上市企业尽调",
            "earnings_notes": "业绩快评",
            "decision_memo": "决策备忘录",
        }
        return names.get(report_type.value, report_type.value)

    def export_formats(self, artifact: "ReportArtifact", output_dir: str) -> Dict[str, str]:
        """导出多格式"""
        import os

        os.makedirs(output_dir, exist_ok=True)

        paths = {}

        # MD
        md_path = os.path.join(
            output_dir,
            f"{artifact.metadata.asset}_{artifact.metadata.report_type}_{datetime.now().strftime('%Y%m%d')}.md",
        )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(artifact.markdown)
        paths["md"] = md_path

        # JSON
        json_path = os.path.join(
            output_dir,
            f"{artifact.metadata.asset}_{artifact.metadata.report_type}_{datetime.now().strftime('%Y%m%d')}.json",
        )
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metadata": artifact.metadata.__dict__ if artifact.metadata else {},
                    "lineage": artifact.lineage,
                    "fingerprint": artifact.fingerprint,
                    "content_preview": artifact.markdown[:1000],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        paths["json"] = json_path

        return paths
