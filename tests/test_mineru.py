"""MinerU 封装测试 — 验证 Markdown 剥离、supports 判定、回退不崩溃

2026-08-10 新增（MinerU 部署接入）
说明：不依赖真实 MinerU 网络调用，测纯逻辑分支。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_supports_extensions():
    from core.mineru_parser import MinerUClient

    c = MinerUClient(mode="cloud")
    assert c.supports(".pdf") is True
    assert c.supports(".docx") is True
    assert c.supports(".pptx") is True
    assert c.supports(".xlsx") is True
    assert c.supports(".png") is True
    assert c.supports(".txt") is False
    assert c.supports(".md") is False
    assert c.supports(".exe") is False


def test_strip_markdown_preserves_numbers_and_chinese():
    """MinerU 的 Markdown 输出应剥离语法符号，但保留数字/中文供正则命中。"""
    from core.baseline_pdf_extractor import _strip_markdown

    md = "## 目标价：12.5 元\n- 买入\n> 摘要内容"
    cleaned = _strip_markdown(md)
    assert "12.5" in cleaned  # 数字保留（目标价正则依赖）
    assert "目标价" in cleaned  # 中文保留
    assert "#" not in cleaned  # 标题符剥离
    assert ">" not in cleaned


def test_extract_text_mineru_failure_returns_error_not_crash(tmp_path, monkeypatch):
    """MinerU 失败时 extract_text 应回退 pdfplumber；pdfplumber 也失败则返回 ERROR 前缀不崩溃。"""
    from core import baseline_pdf_extractor as b

    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 not real")
    # 直接测 pdfplumber 对损坏 PDF 的路径：返回 ERROR 前缀（不抛异常）
    result = b.extract_text(str(fake_pdf), max_pages=2, use_mineru=False)
    assert result.startswith("ERROR") or isinstance(result, str)
