#!/usr/bin/env python3
"""MinerU 文档解析封装 — 统一 PDF/DOCX/PPTX/图片 → Markdown/JSON

两种模式（按可用性自动降级）：
  local : 本地 mineru 包（离线，首次需下载模型 ~3GB，适合本地/敏感文档）
  cloud : mineru-open-sdk（flash 免 token ≤20页/10MB；precision 需 MINERU_API_TOKEN）

与 pdfplumber 的关系：
  现有 baseline_pdf_extractor / methodology_pdf_extractor 用 pdfplumber（仅文本层）。
  MinerU 增强：扫描版 PDF、复杂版面、表格、公式 → 高质量 Markdown。
  该模块作为可选增强层：装了 mineru 走 MinerU，没装则回退 pdfplumber。

用法：
  from core.mineru_parser import MinerUClient
  client = MinerUClient(mode="auto")           # auto: local→cloud→None 探测
  md = client.extract_markdown("report.pdf")    # → str
  data = client.extract_json("report.pdf")      # → dict (若支持)
  client.supports("pdf")                        # → bool

CLI 直用（不开 Python）：
  mineru -p report.pdf -o ./out                 # 本地版
  mineru-open-api flash-extract report.pdf      # 云 flash
  mineru-open-api extract report.pdf -o ./out   # 云 precision（需 auth）
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SUPPORTED_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


class MinerUClient:
    """MinerU 统一客户端：local / cloud / auto 三模式。

    mode="auto" 时优先本地（无网络依赖），本地不可用则降级云 flash。
    云 flash 免 token；若设置了 MINERU_API_TOKEN 且文件超限/需 precision，可用 mode="cloud"。
    """

    def __init__(self, mode: str = "auto", token: Optional[str] = None, timeout: int = 600):
        self.mode = mode
        self.token = token
        self.timeout = timeout
        self._local_ok = None    # 探测缓存
        self._cloud_ok = None

    # ---------- 探测 ----------
    # 注意：本地引擎 mineru 与云 SDK mineru-open-sdk 都注册模块名 `mineru`，
    # 同环境不可共存。用接口差异区分：
    #   local : from mineru import process      (本地 3.x 提供)
    #   cloud : from mineru import MinerU        (SDK 0.2.x 提供)
    def _check_local(self) -> bool:
        if self._local_ok is None:
            try:
                from mineru import process  # noqa: F401
                self._local_ok = True
            except (ImportError, AttributeError):
                self._local_ok = False
        return self._local_ok

    def _check_cloud(self) -> bool:
        if self._cloud_ok is None:
            try:
                from mineru import MinerU  # noqa: F401  (SDK 包名同为 mineru)
                self._cloud_ok = True
            except (ImportError, AttributeError):
                self._cloud_ok = False
        return self._cloud_ok

    def supports(self, suffix: str) -> bool:
        return suffix.lower() in _SUPPORTED_EXTS

    # ---------- 主入口 ----------
    def extract_markdown(self, path: str, **kw) -> str:
        """提取文档 → Markdown 字符串。失败抛异常（不静默）。"""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"MinerU: 文件不存在 {p}")
        if not self.supports(p.suffix):
            raise ValueError(f"MinerU: 不支持的格式 {p.suffix}")

        # 1) local（auto 或显式 local）
        if self.mode in ("auto", "local") and self._check_local():
            try:
                return self._extract_local(p, **kw)
            except Exception as e:
                logger.warning("MinerU local 失败: %s，尝试 cloud", e)
                if self.mode == "local":
                    raise
        # 2) cloud（auto 或显式 cloud）
        if self.mode in ("auto", "cloud") and self._check_cloud():
            return self._extract_cloud(p, **kw)
        raise RuntimeError(
            "MinerU 不可用：请 pip install mineru（本地）或 pip install mineru-open-sdk（云）。"
        )

    # ---------- 本地模式 ----------
    def _extract_local(self, path: Path, **kw) -> str:
        import mineru
        if hasattr(mineru, "process"):
            # mineru>=3.x 提供 mineru.process(input, output_dir)
            out_dir = Path(kw.pop("output_dir", path.parent / "mineru_out"))
            mineru.process(str(path), str(out_dir))
            # 输出通常为 out_dir/<name>/<name>.md
            md_file = self._find_md(out_dir, path.stem)
            if md_file:
                return md_file.read_text(encoding="utf-8", errors="ignore")
        # 兜底：命令行 mineru -p
        if shutil.which("mineru"):
            out_dir = Path(kw.pop("output_dir", path.parent / "mineru_out"))
            cmd = [shutil.which("mineru"), "-p", str(path), "-o", str(out_dir)]
            subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout, check=True)
            md_file = self._find_md(out_dir, path.stem)
            if md_file:
                return md_file.read_text(encoding="utf-8", errors="ignore")
        raise RuntimeError("MinerU local: 无 mineru.process 且无 mineru CLI")

    @staticmethod
    def _find_md(out_dir: Path, stem: str) -> Optional[Path]:
        candidates = [out_dir / stem / f"{stem}.md", out_dir / f"{stem}.md"]
        for c in candidates:
            if c.exists():
                return c
        # 递归找第一个 .md
        for md in out_dir.rglob("*.md"):
            return md
        return None

    # ---------- 云模式 ----------
    def _extract_cloud(self, path: Path, **kw) -> str:
        from mineru import MinerU
        pages = kw.get("pages")          # 如 "1-20"（precision）
        page_range = kw.get("page_range")  # 如 "1-20"（flash）
        if self.token:
            client = MinerU(self.token)
            result = client.extract(str(path), pages=pages)
        else:
            client = MinerU()
            result = client.flash_extract(str(path), page_range=page_range)
        # flash 20页超限会 state=failed + err_code=-30003，不静默
        if result.markdown is None:
            raise RuntimeError(
                f"MinerU cloud 失败: state={getattr(result, 'state', None)} "
                f"err={getattr(result, 'error', '未知错误')}"
            )
        return result.markdown


def extract_markdown(path: str, mode: str = "auto", **kw) -> str:
    """便捷单函数入口。"""
    return MinerUClient(mode=mode).extract_markdown(path, **kw)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    md = extract_markdown(sys.argv[1])
    print(md[:2000] if md else "(空)")
