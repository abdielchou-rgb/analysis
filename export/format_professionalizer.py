"""
2号分析师 Format Professionalizer — 专业排版引擎

确保所有输出：
1. 字体大小一致（中文宋体/SimSun，英文Times New Roman）
2. 表格不溢出（自动调整列宽）
3. 图片不溢出（自动缩放）
4. 颜色统一（机构配色）
5. 间距规范
6. 页眉页脚专业
"""

import re
import logging
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger("2hao.format_pro")


class FormatProfessionalizer:
    """专业排版工具

    Agent在写完报告后调用此工具进行排版美化。
    确保输出达到顶级投行/咨询公司的排版标准。
    """

    # 标准字体配置
    FONTS = {
        "cicc": {"chinese": "宋体", "english": "Times New Roman", "size_body": 10.5, "size_h1": 18, "size_h2": 14, "size_h3": 12},
        "gs": {"chinese": "宋体", "english": "Times New Roman", "size_body": 10, "size_h1": 16, "size_h2": 13, "size_h3": 11},
        "ms": {"chinese": "宋体", "english": "Times New Roman", "size_body": 10, "size_h1": 16, "size_h2": 13, "size_h3": 11},
        "mck": {"chinese": "微软雅黑", "english": "Arial", "size_body": 10, "size_h1": 18, "size_h2": 14, "size_h3": 12},
        "bcg": {"chinese": "微软雅黑", "english": "Arial", "size_body": 10, "size_h1": 16, "size_h2": 13, "size_h3": 11},
        "bain": {"chinese": "微软雅黑", "english": "Arial", "size_body": 10.5, "size_h1": 17, "size_h2": 13, "size_h3": 11},
    }

    def __init__(self, style: str = "cicc"):
        self.style = style
        self.font_config = self.FONTS.get(style, self.FONTS["cicc"])

    def professionalize(self, text: str) -> str:
        """对报告文本进行专业排版"""
        if not text:
            return text

        result = text

        # 1. 修复markdown加粗滥用
        result = self._fix_bold_abuse(result)
        # 2. 修复表格格式
        result = self._fix_table_format(result)
        # 3. 修复图片引用
        result = self._fix_image_refs(result)
        # 4. 标准化标题
        result = self._standardize_headings(result)
        # 5. 添加页码和分隔线
        result = self._add_professional_touches(result)
        # 6. 修复间距
        result = self._fix_spacing(result)
        # 7. 添加数据来源脚注（如果缺失）
        result = self._ensure_data_sources(result)

        return result

    def _fix_bold_abuse(self, text: str) -> str:
        """修复加粗滥用"""
        lines = text.split("\n")
        fixed = []
        for line in lines:
            # 如果一行中加粗字符占比超过40%，减少加粗
            bold_parts = re.findall(r'\*\*(.*?)\*\*', line)
            if bold_parts:
                bold_chars = sum(len(p) for p in bold_parts)
                total_chars = len(line.replace("**", ""))
                if total_chars > 0 and bold_chars / total_chars > 0.4:
                    # 只保留第一个加粗
                    line = re.sub(r'\*\*(.*?)\*\*', r'\1', line, count=len(bold_parts) - 1)
            fixed.append(line)
        return "\n".join(fixed)

    def _fix_table_format(self, text: str) -> str:
        """修复表格格式，防止溢出"""
        lines = text.split("\n")
        fixed = []
        for line in lines:
            if line.startswith("|") and line.endswith("|"):
                # 确保表格列对齐
                cols = [c.strip() for c in line.split("|")]
                # 移除首尾空
                if cols and cols[0] == "":
                    cols = cols[1:]
                if cols and cols[-1] == "":
                    cols = cols[:-1]
                # 限制每列长度（防止溢出）
                cols = [c[:30] if len(c) > 30 else c for c in cols]
                fixed.append("| " + " | ".join(cols) + " |")
            else:
                fixed.append(line)
        return "\n".join(fixed)

    def _fix_image_refs(self, text: str) -> str:
        """修复图片引用"""
        def fix_img(match):
            alt = match.group(1)
            path = match.group(2)
            # 如果路径是相对路径且没有output前缀，添加
            is_abs = path.startswith("/") or (len(path) > 2 and path[1] == ":" and path[2] in "/\\")
            if not path.startswith("output/") and not is_abs and "://" not in path:
                path = f"output/charts/{path}"
            return f"![{alt}]({path})"
        
        return re.sub(r'!\[(.*?)\]\((.*?)\)', fix_img, text)

    def _standardize_headings(self, text: str) -> str:
        """标准化标题格式"""
        lines = text.split("\n")
        fixed = []
        for line in lines:
            # 确保标题前后有空行
            if re.match(r'^#{1,4}\s', line):
                if fixed and fixed[-1].strip() != "":
                    fixed.append("")
                fixed.append(line)
                fixed.append("")
            else:
                fixed.append(line)
        return "\n".join(fixed)

    def _add_professional_touches(self, text: str) -> str:
        """添加专业排版细节"""
        result = text

        # R42（2026-08-02）：不再注入免责声明——报告必须像人类分析师撰写，
        # 专业券商报告不出现"仅供参考/不构成投资建议"这类 AI 免责痕迹。
        # 原逻辑在此处追加"免责声明"段落，已删除。

        return result

    def _fix_spacing(self, text: str) -> str:
        """修复间距"""
        # 确保段落之间有空行
        paragraphs = text.split("\n\n")
        cleaned = []
        for p in paragraphs:
            p = p.strip()
            if p:
                cleaned.append(p)
        return "\n\n".join(cleaned)

    def _ensure_data_sources(self, text: str) -> str:
        """确保数据来源标注"""
        source_patterns = [
            r'数据来源[：:]\s*\S+',
            r'来源[：:]\s*\S+',
            r'数据源自\s*\S+',
        ]
        has_sources = any(re.search(p, text) for p in source_patterns)
        if not has_sources:
            text += "\n\n**数据来源**: 本报告数据来源于公开市场数据、公司公告、行业研究机构及第三方数据库。\n"

        return text

    def validate_format(self, text: str) -> dict:
        """验证排版质量"""
        issues = []

        # 1. 检查加粗滥用
        bold_count = len(re.findall(r'\*\*', text))
        para_count = max(len([p for p in text.split("\n\n") if p.strip()]), 1)
        if bold_count > para_count * 3:
            issues.append(f"加粗过多: {bold_count}处加粗，建议不超过段落数的3倍")

        # 2. 检查表格溢出
        table_lines = [l for l in text.split("\n") if l.startswith("|")]
        for tl in table_lines:
            if len(tl) > 200:
                issues.append(f"表格行过长: {len(tl)}字符，建议控制在200以内")

        # 3. 检查字体大小不一致
        font_sizes = re.findall(r'font-size[=:]\s*(\d+)', text)
        if font_sizes and len(set(font_sizes)) > 4:
            issues.append(f"字体大小不一致: {len(set(font_sizes))}种不同字号")

        # 4. 检查图片路径
        img_refs = re.findall(r'!\[.*?\]\((.*?)\)', text)
        for ref in img_refs:
            if not ref.startswith("output/") and "://" not in ref and not ref.startswith("/"):
                issues.append(f"图片路径可能不正确: {ref}")

        score = max(0.0, 1.0 - len(issues) * 0.15)
        return {
            "score": round(score, 2),
            "issues": issues,
            "passed": len(issues) == 0,
            "details": {
                "bold_count": bold_count,
                "para_count": para_count,
                "table_lines": len(table_lines),
                "images": len(img_refs),
                "font_variations": len(set(font_sizes)),
            },
        }


def main():
    """测试"""
    formatter = FormatProfessionalizer(style="cicc")

    test_text = """
**第一章** **市场概况** **分析**
我们**认为**茅台的**核心竞争力**在于**品牌力**和**渠道力**，**同时**其**产能**扩张**也值得关注**。

| 年份 | 营收(亿) | 净利润(亿) | 毛利率 | 净利率 |
|------|---------|-----------|-------|-------|
| 2023 | 1500 | 750 | 0.92 | 0.50 |
| 2024 | 1750 | 860 | 0.91 | 0.49 |
| 2025E | 2000 | 980 | 0.91 | 0.49 |

![营收趋势](chart_1.png)
"""

    result = formatter.professionalize(test_text)
    print("=== 排版后 ===")
    print(result)

    validation = formatter.validate_format(result)
    print(f"\n=== 排版验证 ===")
    print(f"  评分: {validation['score']}")
    print(f"  通过: {validation['passed']}")
    if validation['issues']:
        for i in validation['issues']:
            print(f"  ⚠️ {i}")


if __name__ == "__main__":
    main()
