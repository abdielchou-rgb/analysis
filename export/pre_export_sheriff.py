"""
PreExportSheriff — 统一MD预处理
在所有导出器之前运行，确保输入干净
"""
import re

def sanitize(markdown_text: str) -> str:
    """一站式清理MD文本"""
    text = markdown_text
    text = re.sub(r"好的，[^。]*。", "", text)  # 个人叙事
    text = text.replace("**", "")                   # bold标记
    text = re.sub(r"\|?\s*:[-:]+\s*\|\s*(?::[-:]+\s*\|\s*)*\|?", "", text)  # 表格分隔
    text = re.sub(r"^\|[\s|]*\|$", "", text, flags=re.MULTILINE)             # 空表
    text = re.sub(r"\n---\n", "\n\n", text)         # 孤立分隔线
    text = text.lstrip("\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.rstrip()
    return text

def validate_sanitized(text: str) -> list:
    """检查清理后是否还有残留问题"""
    issues = []
    if "**" in text:
        issues.append("仍有 ** 标记残留")
    if re.search(r"\|?\s*:[-:]+\s*\|", text):
        issues.append("仍有 :--- 表格分隔符残留")
    if re.search(r"^好的，", text):
        issues.append("仍有个人叙事开头残留")
    return issues
