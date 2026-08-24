"""V51.6 集成导出器 — md/docx/pptx 一站式输出。

所有图表统一编号、统一风格、统一嵌入。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from core.chart_engine import ChartEngine

logger = logging.getLogger("v51.export")


@dataclass
class ExportResult:
    md_path: str = ""
    docx_path: str = ""
    pptx_path: str = ""
    charts: dict = field(default_factory=dict)
    embedded_md: str = ""
    layout_warnings: str = ""  # R40：渲染层目检结果（空=通过）


def preflight_export_checks(
    chart_paths: dict, need_pptx: bool = True, need_pdf: bool = False, md_refs: str = ""
) -> list:
    """P1-4（2026-08-07）：导出前预检。

    1) 图表存在性：chart_paths 中每个文件必须真实存在；
    2) MD 正文引用图（![](...)）存在性：缺失即列入错误；
    3) 环境依赖：python-pptx（PPTX 必需）、reportlab（PDF 兜底必需）。

    Returns:
        errors: 错误列表（空=全部通过）。调用方发现非空必须明确报错，
        禁止静默跳过导出。
    """
    import re as _re
    from pathlib import Path as _Path

    errors = []

    # 1. chart_paths 图表文件存在性
    if chart_paths:
        for chart_type, path in chart_paths.items():
            p = _Path(path)
            if not p.exists():
                errors.append(f"图表文件缺失: {chart_type} -> {path}")

    # 2. MD 正文图表引用存在性
    if md_refs:
        refs = _re.findall(r"!\[.*?\]\((.+?)\)", md_refs)
        for ref in refs:
            if ref.startswith("http") or ref.startswith("chart:"):
                continue
            p = _Path(ref)
            if not p.exists() and not p.is_absolute():
                # 相对路径：尝试以项目根/output 为基准
                cands = [
                    _Path(__file__).resolve().parent.parent / ref,
                    _Path(__file__).resolve().parent.parent / "output" / ref,
                ]
                if not any(c.exists() for c in cands):
                    errors.append(f"MD 引用图缺失: {ref}")
            elif not p.exists():
                errors.append(f"MD 引用图缺失: {ref}")

    # 3. 环境依赖
    if need_pptx:
        try:
            import pptx  # noqa: F401
        except ImportError:
            errors.append("python-pptx 未安装，无法生成 PPTX。请执行: pip install python-pptx")
    if need_pdf:
        try:
            import reportlab  # noqa: F401
        except ImportError:
            errors.append(
                "reportlab 未安装，无法生成 PDF（LibreOffice 亦不可用时的兜底）。请执行: pip install reportlab"
            )
        # LibreOffice 探测（PDF 首选转换器）
        import shutil as _shutil

        if not (_shutil.which("libreoffice") or _shutil.which("soffice")):
            import os as _os

            _lo_cands = [
                _os.path.expandvars(r"%ProgramFiles%\LibreOffice\program\soffice.exe"),
                _os.path.expandvars(r"%ProgramFiles(x86)%\LibreOffice\program\soffice.exe"),
                "/usr/bin/soffice",
                "/opt/libreoffice/program/soffice",
            ]
            if not any(_os.path.isfile(c) for c in _lo_cands):
                errors.append(
                    "LibreOffice 未安装（PDF 首选转换器缺失），将降级 reportlab；若 reportlab 缺失则 PDF 无法导出"
                )

    return errors


class IntegratedExporter:
    """一体化导出器：md + docx + pptx + charts 统一管线。"""

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chart_engine = ChartEngine(output_dir=str(self.output_dir / "charts"))

    def export_all(
        self,
        report_text: str,
        style_id: str = "cicc",
        data: dict = None,
        title: str = "",
        sensitivity_matrix: dict = None,
        forward_picks: dict = None,
        chart_paths: dict = None,
    ) -> ExportResult:
        """全量导出。

        Args:
            report_text: markdown 正文
            style_id: 机构风格
            data: 图表数据 {指标名: 值}
            title: 报告标题前缀
            sensitivity_matrix: {"matrix": [[...]], "rows": [...], "cols": [...]}
            forward_picks: {"asset": "xxx", "direction": "bull", ...}

        Returns:
            ExportResult: 所有导出路径
        """
        result = ExportResult()

        # P1-4（2026-08-07）：导出前预检图表存在性与环境依赖，缺失即明确报错。
        preflight_errors = preflight_export_checks(
            chart_paths=chart_paths or {},
            need_pptx=True,
            need_pdf=False,
            md_refs=report_text or "",
        )
        if preflight_errors:
            raise RuntimeError("导出前预检失败（P1-4）：\n  - " + "\n  - ".join(preflight_errors))

        # 1. 生成图表（优先用传入的 chart_paths，否则从 data/report_text 生成）
        self.chart_engine.set_style(style_id)
        if chart_paths is None:
            chart_paths = {}
            if data and len(data) >= 2:
                chart_paths = self.chart_engine.generate_all(data, title, style_id)
            else:
                chart_paths = self.chart_engine.generate_all({}, title, style_id, report_text)

        if sensitivity_matrix:
            sm = sensitivity_matrix
            self.chart_engine.set_style(style_id)
            hm = self.chart_engine.sensitivity_heatmap(sm.get("matrix", []), sm.get("rows", []), sm.get("cols", []))
            if hm:
                chart_paths["sensitivity"] = hm

        result.charts = chart_paths

        # 2. 增强 markdown：注入图表引用
        embedded = report_text
        if chart_paths:
            chart_lines = ["\n\n---\n"]
            i = 0
            for chart_type, path in sorted(chart_paths.items()):
                rel = Path(path).name
                i += 1
                desc = {
                    "bar": "核心指标",
                    "pie": "构成分析",
                    "line": "趋势",
                    "pareto": "帕累托分析",
                    "sensitivity": "敏感性分析",
                }.get(chart_type, chart_type)
                chart_lines.append(f"![图{i}：{desc}]({rel})")
                chart_lines.append(f"*图{i}：{desc}*\n")

            # 在"估值"章节前插入
            val_pos = embedded.find("## 估值")
            if val_pos > 0:
                embedded = embedded[:val_pos] + "\n".join(chart_lines) + "\n" + embedded[val_pos:]
            else:
                embedded += "\n".join(chart_lines)

            # 注入 forward_picks 摘要
            if forward_picks:
                fp = forward_picks
                fp_block = f"""
---
**判断跟踪**：对 {fp.get("asset", "")} 的 {fp.get("direction", "")} 判断已记录至 forward_picks。
验证周期: {fp.get("time_window", "6m")}。证伪条件: {fp.get("falsification", "见正文")}。
"""
                embedded += fp_block

        result.embedded_md = embedded

        # 3. 写 md 文件（scrub AIGC artifacts）
        from export.docx_exporter import _scrub_aigc_artifacts

        clean_md = _scrub_aigc_artifacts(embedded)
        md_path = self.output_dir / f"{title[:20]}_{style_id}.md"
        md_path.write_text(clean_md, encoding="utf-8")
        result.md_path = str(md_path)

        # 4. 导出 docx（含所有表格 + 图表嵌入）
        try:
            import re

            from export.docx_exporter import pandoc_to_docx

            docx_path = str(self.output_dir / f"{title[:20]}_{style_id}.docx")
            # 从 report_text 提取 H1 标题作为 docx 封面标题
            docx_title = title
            h1_match = re.search(r"^# (.+)$", report_text, re.MULTILINE)
            if h1_match:
                docx_title = h1_match.group(1).strip()
            # 优先尝试Pandoc（失败时自动回退markdown_to_docx）
            docx_result = pandoc_to_docx(
                markdown_path=str(md_path),
                output_path=docx_path,
                style=style_id,
            )
            # 对已生成的 docx 追加丰富表格和图表
            if docx_result and Path(docx_path).exists():
                try:
                    from docx import Document as DocxDoc

                    doc = DocxDoc(docx_path)
                    from export.docx_tables import enhance_tables_in_docx

                    enhance_tables_in_docx(doc, embedded, result.charts, style_id)
                    doc.save(docx_path)
                    result.docx_path = docx_path
                except Exception as e:
                    result.docx_path = docx_path  # 至少原始 docx 存在
                    logger.warning(f"表格增强失败（原始docx保留）: {e}")
            elif docx_result:
                result.docx_path = docx_result
            # R31（2026-08-02 排版根治）：清洗空段落（治空白页老问题）
            # 之前 clean_empty_paragraphs 定义了但从未接进导出链路 → 56空段一直存在
            if result.docx_path:
                try:
                    from export.docx_exporter import clean_empty_paragraphs

                    _removed = clean_empty_paragraphs(result.docx_path)
                    if _removed:
                        logger.info(f"[DOCX-CLEAN] 清洗 {_removed} 个空段落 → {result.docx_path}")
                except Exception as _e:
                    logger.warning(f"[DOCX-CLEAN] 清洗失败: {_e}")
                # R42（2026-08-02）：插入静态目录（从 markdown 标题生成，无需 Word 刷新）。
                # 根治"DOCX 目录为空"历史问题。
                try:
                    from export.docx_exporter import add_static_toc

                    _n = add_static_toc(result.docx_path, clean_md)
                    if _n:
                        logger.info(f"[DOCX-TOC] 插入静态目录 {_n} 条目 → {result.docx_path}")
                except Exception as _e:
                    logger.warning(f"[DOCX-TOC] 目录插入失败: {_e}")
            # P1-4（2026-08-07）：docx 环节最终必须产出真实文件，否则明确报错。
            if not result.docx_path:
                raise RuntimeError("DOCX 导出失败（P1-4）: 未产出 docx 文件")
            if not Path(result.docx_path).exists():
                raise RuntimeError(f"DOCX 导出失败（P1-4）: 产物路径不存在 {result.docx_path}")
        except Exception as e:
            # P1-4（2026-08-07）：DOCX 导出失败不再静默跳过，必须明确报错。
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"DOCX 导出失败（P1-4，不再静默）: {e}") from e

        # 5. 导出 pptx（传入 chart_paths 用于嵌入图表）
        # P1-4（2026-08-07）：不再静默失败——python-pptx 缺失或导出异常必须
        # 明确抛错，禁止调用方以为 PPTX 已产出。
        try:
            from export.pptx_exporter import export_pptx

            pptx_path = export_pptx(
                report_md=embedded,
                style_id=style_id,
                chart_paths=chart_paths,
                output_path=str(self.output_dir / f"{title[:20]}_{style_id}.pptx"),
            )
            if not pptx_path:
                raise RuntimeError("export_pptx 返回空路径，PPTX 导出未产出")
            result.pptx_path = pptx_path
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"PPTX 导出失败（P1-4，不再静默）: {e}") from e

        # R40（2026-08-02 渲染层闭环）：导出完成后对 docx 做渲染层目检，
        # 失败即记录阻断信号（Marvis 审计：检查只做 MD 层，docx 版式病灶长期漏网）。
        # 检测器已建（IronGate._check_layout_quality），此处直接调用同一套逻辑。
        if result.docx_path:
            try:
                import os as _os

                if _os.path.exists(result.docx_path):
                    from pipeline.iron_gate import IronGate

                    _ig = IronGate.__new__(IronGate)
                    _ig.report_text = clean_md
                    _ig.report_path = str(md_path)
                    _ig._allow_placeholder_degradation = False
                    _lr = _ig._check_layout_quality()
                    if not _lr.passed:
                        result.layout_warnings = _lr.details
                        logger.warning(f"[RENDER-AUDIT] 渲染层目检未通过: {_lr.details[:200]}")
                    else:
                        logger.info("[RENDER-AUDIT] 渲染层目检通过（无空段/分页/图表分布问题）")
            except Exception as _e:
                logger.debug(f"[RENDER-AUDIT] 目检失败（不阻断）: {_e}")

        return result
