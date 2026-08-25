# -*- coding: utf-8 -*-
"""导出柯力 v5 报告四件套：MD(已有) + DOCX + PDF + PPTX"""

import io
import os
import sys
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"D:\2hao-analyst")

out_log = r"D:\2hao-analyst\logs\export_v5_result.txt"
logf = open(out_log, "w", encoding="utf-8")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    logf.write(s + "\n")
    logf.flush()


try:
    from export.docx_exporter import markdown_to_docx
    from export.pdf_exporter import CICCStylePDFExporter
    from export.pptx_exporter import export_pptx

    md_path = r"D:\2hao-analyst\output\柯力传感深度分析报告_v5_20260804.md"
    text = open(md_path, encoding="utf-8").read()
    # 剥离 YAML front matter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]

    base = r"D:\2hao-analyst\output\柯力传感深度分析报告_v5_20260804"
    title = "柯力传感（603662.SH）深度研究报告"

    # 1. DOCX
    docx_out = base + ".docx"
    docx_path = markdown_to_docx(text, docx_out, title=title, subtitle="2号分析师 | CICC 风格", author="2hao Analyst")
    log(
        "DOCX:",
        docx_path,
        "exists:",
        os.path.exists(docx_path),
        "size:",
        os.path.getsize(docx_path) if os.path.exists(docx_path) else 0,
    )

    # 2. PDF
    pdf_out = base + ".pdf"
    exporter = CICCStylePDFExporter()
    pdf_path = exporter.export(text, pdf_out, title=title)
    log(
        "PDF:",
        pdf_path,
        "exists:",
        os.path.exists(pdf_path),
        "size:",
        os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0,
    )

    # 3. PPTX
    pptx_out = base + ".pptx"
    pptx_path = export_pptx(text, style_id="cicc", output_path=pptx_out)
    log(
        "PPTX:",
        pptx_path,
        "exists:",
        os.path.exists(pptx_path),
        "size:",
        os.path.getsize(pptx_path) if os.path.exists(pptx_path) else 0,
    )

    log("ALL DONE")
except Exception as e:
    log("ERROR:", repr(e))
    log(traceback.format_exc())
finally:
    logf.close()
