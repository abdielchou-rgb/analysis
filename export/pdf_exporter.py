"""V56 PDFExporter — ReportLab 驱动的高质量 PDF 输出

用于生成符合 CICC/中金风格的机构级 PDF 报告。

依赖: pip install reportlab
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime

logger = logging.getLogger("v56.export.pdf")

try:
    from reportlab.lib.colors import Color, HexColor, black, white  # noqa: F401  (dead-import debt)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Image,
        KeepTogether,  # noqa: F401  (dead-import debt)
        ListFlowable,  # noqa: F401  (dead-import debt)
        ListItem,  # noqa: F401  (dead-import debt)
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False

try:
    from core.models import ReportType
except ImportError:
    from enum import Enum

    class ReportType(str, Enum):
        INDUSTRY_DEEP = "industry_deep"
        LISTED_COMPANY = "listed_company"
        UNLISTED_COMPANY = "unlisted_company"


class CICCStylePDFExporter:
    """CICC风格PDF报告生成器

    特点:
    - 中文字体支持（SimHei / SimSun fallback）
    - 专业配色（CICC蓝 #003D7A）
    - 机构级排版（页眉/页脚/页码/边距）
    - 图片嵌入（图表在正文对应位置）
    - 表格格式化
    """

    # CICC 品牌色
    CICC_BLUE = HexColor("#003D7A")
    CICC_LIGHT_BLUE = HexColor("#E8F0FE")
    CICC_GRAY = HexColor("#666666")
    CICC_LIGHT_GRAY = HexColor("#F5F5F5")

    def __init__(self, font_name: str = "SimHei"):
        self.font_name = font_name
        self._register_fonts()

    def _register_fonts(self):
        """注册中文字体"""
        if not _HAS_REPORTLAB:
            return
        try:
            # 尝试注册常见中文字体
            font_paths = [
                ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
                ("SimSun", "C:/Windows/Fonts/simsun.ttc"),
                ("MicrosoftYaHei", "C:/Windows/Fonts/msyh.ttc"),
            ]
            for name, path in font_paths:
                if os.path.exists(path):
                    try:
                        pdfmetrics.registerFont(TTFont(name, path))
                        logger.info(f"Registered font: {name}")
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Font registration failed: {e}")

    def _get_styles(self):
        """获取预定义样式"""
        styles = getSampleStyleSheet()

        # 主标题
        styles.add(
            ParagraphStyle(
                "CoverTitle",
                fontName=self.font_name,
                fontSize=24,
                leading=32,
                textColor=self.CICC_BLUE,
                spaceAfter=12,
                alignment=1,  # center
            )
        )
        # 副标题
        styles.add(
            ParagraphStyle(
                "CoverSubtitle",
                fontName=self.font_name,
                fontSize=14,
                leading=20,
                textColor=self.CICC_GRAY,
                spaceAfter=6,
                alignment=1,
            )
        )
        # 章节标题
        styles.add(
            ParagraphStyle(
                "SectionTitle",
                fontName=self.font_name,
                fontSize=16,
                leading=22,
                textColor=self.CICC_BLUE,
                spaceBefore=20,
                spaceAfter=10,
                borderWidth=0,
                borderPadding=0,
                borderColor=self.CICC_BLUE,
            )
        )
        # 正文
        styles.add(
            ParagraphStyle(
                "BodyTextCN",
                fontName=self.font_name,
                fontSize=10.5,
                leading=18,
                textColor=black,
                spaceAfter=6,
                firstLineIndent=21,  # 首行缩进2字符
            )
        )
        # 表头
        styles.add(
            ParagraphStyle(
                "TableHeader",
                fontName=self.font_name,
                fontSize=9,
                leading=14,
                textColor=white,
                alignment=1,
            )
        )
        # 表体
        styles.add(
            ParagraphStyle(
                "TableCell",
                fontName=self.font_name,
                fontSize=9,
                leading=14,
                textColor=black,
                alignment=1,
            )
        )
        # 页脚
        styles.add(
            ParagraphStyle(
                "Footer",
                fontName=self.font_name,
                fontSize=8,
                leading=10,
                textColor=self.CICC_GRAY,
                alignment=1,
            )
        )
        # 数据来源
        styles.add(
            ParagraphStyle(
                "SourceNote",
                fontName=self.font_name,
                fontSize=8,
                leading=12,
                textColor=self.CICC_GRAY,
                spaceBefore=4,
                spaceAfter=12,
            )
        )

        return styles

    def export(
        self,
        markdown_text: str,
        output_path: str,
        title: str = "研究报告",
        subtitle: str = "",
        author: str = "1号分析师",
        logo_path: str = "",
    ) -> str:
        """将 Markdown 文本生成为 PDF

        Args:
            markdown_text: 报告 Markdown 内容
            output_path: 输出 PDF 路径
            title: 报告标题
            subtitle: 报告副标题
            author: 作者

        Returns:
            str: 输出文件路径
        """
        if not _HAS_REPORTLAB:
            # P1-4（2026-08-07）：缺失依赖必须明确报错，禁止静默返回空路径。
            raise RuntimeError("PDF 导出失败（P1-4）: reportlab 未安装，无法生成 PDF。请执行: pip install reportlab")

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
            topMargin=2.0 * cm,
            bottomMargin=2.0 * cm,
        )

        styles = self._get_styles()
        story = []

        # ═══ 封面 ═══
        story.append(Spacer(1, 60 * mm))
        story.append(Paragraph(title, styles["CoverTitle"]))
        if subtitle:
            story.append(Paragraph(subtitle, styles["CoverSubtitle"]))
        story.append(Spacer(1, 20 * mm))
        story.append(Paragraph(f"作者: {author}", styles["CoverSubtitle"]))
        story.append(
            Paragraph(
                datetime.now().strftime("%Y年%m月%d日"),
                styles["CoverSubtitle"],
            )
        )
        story.append(PageBreak())

        # ═══ 正文 ═══
        self._parse_markdown_to_story(markdown_text, story, styles, output_path)

        # ═══ 生成 ═══
        try:
            doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
            logger.info(f"PDF generated: {output_path}")
            return output_path
        except Exception as e:
            # P1-4（2026-08-07）：build 失败必须明确报错，禁止静默返回空路径。
            raise RuntimeError(f"PDF 导出失败（P1-4）: PDF build 异常: {e}") from e

    def _parse_markdown_to_story(self, text: str, story: list, styles, output_path: str):
        """解析 Markdown 为 ReportLab Flowable 列表

        支持:
        - # 标题 → SectionTitle
        - ## 小节 → Heading2
        - 普通文本 → BodyTextCN
        - **加粗** → 加粗 Text
        - - 列表 → ListItem
        - ![alt](path) → Image（嵌入图片）
        - 表格 → Table
        """
        lines = text.split("\n")
        i = 0
        chart_counter = 0

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # 标题
            if line.startswith("# "):
                story.append(Paragraph(line[2:], styles["SectionTitle"]))
                story.append(Spacer(1, 4 * mm))

            elif line.startswith("## "):
                story.append(
                    Paragraph(
                        line[3:],
                        ParagraphStyle(
                            "SubSection",
                            fontName=self.font_name,
                            fontSize=13,
                            leading=18,
                            textColor=self.CICC_BLUE,
                            spaceBefore=12,
                            spaceAfter=6,
                        ),
                    )
                )

            elif line.startswith("### "):
                story.append(
                    Paragraph(
                        line[4:],
                        ParagraphStyle(
                            "SubSubSection",
                            fontName=self.font_name,
                            fontSize=11,
                            leading=16,
                            textColor=black,
                            spaceBefore=8,
                            spaceAfter=4,
                            borderWidth=0,
                            borderPadding=0,
                        ),
                    )
                )

            # 图片
            elif line.startswith("!["):
                chart_counter += 1
                # 提取图片路径
                img_match = re.match(r"!\[.*?\]\((.+?)\)", line)
                if img_match:
                    img_path = img_match.group(1)
                    if os.path.exists(img_path):
                        try:
                            img = Image(img_path, width=15 * cm, height=8 * cm)
                            story.append(img)
                            story.append(
                                Paragraph(
                                    f"图{chart_counter}：{line[2 : line.find(']')]}",
                                    styles["SourceNote"],
                                )
                            )
                        except Exception as e:
                            logger.debug(f"Image embed failed: {e}")
                            story.append(
                                Paragraph(
                                    f"[图表: {line[2 : line.find(']')]}]",
                                    styles["BodyTextCN"],
                                )
                            )

            # 表格（检测以 | 开始的行）
            elif line.startswith("|") and line.endswith("|"):
                table_data = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    row = [cell.strip() for cell in lines[i].strip().split("|")[1:-1]]
                    table_data.append(row)
                    i += 1

                if len(table_data) >= 2:
                    # 忽略分隔行（|---|）
                    table_data = [r for r in table_data if not r[0].startswith("---")]

                    if table_data:
                        tbl = Table(table_data, repeatRows=1)
                        tbl.setStyle(
                            TableStyle(
                                [
                                    ("BACKGROUND", (0, 0), (-1, 0), self.CICC_BLUE),
                                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                                    ("FONTNAME", (0, 0), (-1, -1), self.font_name),
                                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                    ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
                                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, self.CICC_LIGHT_GRAY]),
                                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                ]
                            )
                        )
                        story.append(tbl)
                        story.append(Spacer(1, 3 * mm))
                continue

            # 列表
            elif line.startswith("- ") or line.startswith("* "):
                items = []
                while i < len(lines) and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                    items.append(lines[i].strip()[2:])
                    i += 1
                for item in items[:10]:
                    story.append(
                        Paragraph(
                            f"• {item}",
                            styles["BodyTextCN"],
                        )
                    )
                continue

            # 普通段落
            else:
                # 处理加粗
                processed = self._process_bold(line, styles)
                story.append(Paragraph(processed, styles["BodyTextCN"]))

            i += 1

    def _process_bold(self, text: str, styles) -> str:
        """将 **text** 转为 ReportLab 的 <b>text</b>"""
        import re

        result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        return result

    def _header_footer(self, canvas, doc):
        """页眉页脚"""
        canvas.saveState()
        # 页眉：CICC 蓝线
        canvas.setStrokeColor(self.CICC_BLUE)
        canvas.setLineWidth(0.5)
        canvas.line(2.5 * cm, A4[1] - 1.5 * cm, A4[0] - 2.5 * cm, A4[1] - 1.5 * cm)
        # 页脚：页码
        canvas.setFont(self.font_name, 8)
        canvas.setFillColor(self.CICC_GRAY)
        canvas.drawCentredString(
            A4[0] / 2,
            1.5 * cm,
            f"— {doc.page} —",
        )
        canvas.restoreState()
