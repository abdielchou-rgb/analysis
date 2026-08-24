"""
OCR 引擎集成模块
---------------
统一 OCR 接口，支持多后端自动降级：
- UnlimitedOCR (baidu/Unlimited-OCR via transformers) —— 需 CUDA torch
- WebFallback —— 通过东方财富网搜索研报标题获取文字版

自动降级链：UnlimitedOCR → WebFallback

使用示例:
    from utils.ocr_engine import OCREngine

    engine = OCREngine(backend="auto")
    text = engine.extract_text("path/to/report.pdf")
"""

import base64
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 环境配置（由 ocr_engine_config.py 统一管理）
try:
    from utils.ocr_engine_config import (
        HAS_CUDA_TORCH,
        UNLIMITED_OCR_API_URL,
        UNLIMITED_OCR_DEVICE,
        UNLIMITED_OCR_MODEL_NAME,
    )
except ImportError:
    HAS_CUDA_TORCH = False
    UNLIMITED_OCR_API_URL = None
    UNLIMITED_OCR_MODEL_NAME = "baidu/Unlimited-OCR"
    UNLIMITED_OCR_DEVICE = "cuda"


class OCREngine:
    """统一的 OCR 引擎，支持多后端自动降级。

    Parameters
    ----------
    backend : str
        - "auto": 自动尝试 UnlimitedOCR，不可用时降级到 WebFallback
        - "unlimited-ocr": 强制使用 UnlimitedOCR
        - "web-fallback": 强制使用 WebFallback
    """

    def __init__(self, backend: str = "auto"):
        self.backend = backend
        self._pipeline = None  # transformers pipeline 懒加载
        logger.info(f"OCREngine initialized with backend={backend}")

    # ── 主入口 ──────────────────────────────────────────────

    def extract_text(self, pdf_path: str) -> str:
        """从 PDF 提取文字，根据 backend 策略自动降级。

        Parameters
        ----------
        pdf_path : str
            PDF 文件的绝对路径。

        Returns
        -------
        str
            提取的文字内容。如果所有后端均失败，返回空字符串。
        """
        pdf_path = str(Path(pdf_path).resolve())

        if not os.path.exists(pdf_path):
            logger.error(f"PDF 文件不存在: {pdf_path}")
            return ""

        if self.backend == "unlimited-ocr":
            result = self._try_unlimited_ocr(pdf_path)
            return result if result is not None else ""

        if self.backend == "web-fallback":
            result = self._try_web_fallback(pdf_path)
            return result if result is not None else ""

        # auto: 降级链
        logger.info("Auto mode: trying UnlimitedOCR → WebFallback")

        result = self._try_unlimited_ocr(pdf_path)
        if result:
            logger.info("UnlimitedOCR 成功")
            return result

        logger.info("UnlimitedOCR 不可用，降级到 WebFallback")
        result = self._try_web_fallback(pdf_path)
        if result:
            logger.info("WebFallback 成功")
            return result

        logger.warning(f"所有 OCR 后端均失败: {pdf_path}")
        return ""

    # ── 后端 1: UnlimitedOCR ─────────────────────────────────

    def _try_unlimited_ocr(self, pdf_path: str) -> str | None:
        """尝试使用 baidu/Unlimited-OCR via transformers。

        需要 CUDA torch。如果环境不满足，返回 None。

        支持两种模式：
        1. API 模式：设置 UNLIMITED_OCR_API_URL 时通过 HTTP API 调用远程服务
        2. 本地模式：直接加载 transformers pipeline（需 CUDA）
        """
        # 检查 API 模式
        if UNLIMITED_OCR_API_URL:
            return self._unlimited_ocr_api(pdf_path)

        # 本地模式：需要 CUDA torch
        if not HAS_CUDA_TORCH:
            logger.info(
                "UnlimitedOCR 本地模式需要 CUDA torch，当前环境不可用。可设置 UNLIMITED_OCR_API_URL 指向远程服务。"
            )
            return None

        try:
            import torch
            from PIL import Image  # noqa: F401  (dead-import debt)
            from transformers import pipeline

            if self._pipeline is None:
                logger.info(f"加载 UnlimitedOCR 模型: {UNLIMITED_OCR_MODEL_NAME}")
                self._pipeline = pipeline(
                    "image-to-text",
                    model=UNLIMITED_OCR_MODEL_NAME,
                    device=UNLIMITED_OCR_DEVICE if torch.cuda.is_available() else -1,
                )

            # PDF → 图片 → OCR
            images = self._pdf_to_images(pdf_path)
            if not images:
                logger.warning(f"无法将 PDF 转为图片: {pdf_path}")
                return None

            texts = []
            for i, img in enumerate(images):
                result = self._pipeline(img)
                if result and isinstance(result, list):
                    texts.append(result[0].get("generated_text", ""))
                logger.debug(f"OCR 完成第 {i + 1}/{len(images)} 页")

            return "\n\n".join(texts)

        except ImportError as e:
            logger.warning(f"UnlimitedOCR 依赖缺失: {e}")
            return None
        except Exception as e:
            logger.error(f"UnlimitedOCR 执行失败: {e}")
            return None

    def _unlimited_ocr_api(self, file_path: str) -> str | None:
        """通过 HTTP API 调用远程 UnlimitedOCR 服务（OpenAI Vision API 兼容格式）。

        自动识别文件类型：
        - 图片（PNG/JPG/JPEG/BMP/WEBP 等）：直接 base64 编码发送
        - PDF：先用 pdf2image 将第一页转为 PNG，再 base64 编码发送
        """
        try:
            import requests

            ext = Path(file_path).suffix.lower()

            # 判断是否为图片文件
            image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tiff", ".tif"}
            if ext in image_exts:
                mime_type = "image/png" if ext == ".png" else "image/jpeg"
                with open(file_path, "rb") as f:
                    file_content = f.read()
                b64_string = base64.b64encode(file_content).decode("utf-8")
            else:
                # PDF 或其他格式：通过 PyMuPDF 转为 PNG
                import fitz

                doc = fitz.open(file_path)
                page = doc[0]
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                doc.close()
                b64_string = base64.b64encode(img_bytes).decode("utf-8")
                mime_type = "image/png"

            body = {
                "model": UNLIMITED_OCR_MODEL_NAME,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{b64_string}"},
                            },
                            {
                                "type": "text",
                                "text": "请提取图中的所有文字内容",
                            },
                        ],
                    }
                ],
            }

            resp = requests.post(UNLIMITED_OCR_API_URL, json=body, timeout=300)

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
            else:
                logger.error(f"OCR API 返回 {resp.status_code}: {resp.text[:200]}")
                return None
        except ImportError as e:
            logger.warning(f"OCR API 依赖缺失: {e}")
            return None
        except Exception as e:
            logger.error(f"OCR API 调用失败: {e}")
            return None

    # ── 后端 2: WebFallback ──────────────────────────────────

    def _try_web_fallback(self, pdf_path: str) -> str | None:
        """通过 Web 搜索东方财富网获取研报文字版。

        基于 PDF 文件名（去掉后缀）构造搜索标题，
        尝试从东方财富网搜索结果中抓取研报文字。
        """
        filename = Path(pdf_path).stem  # 去掉 .pdf 后缀
        logger.info(f"WebFallback: 搜索 '{filename}'")

        # 策略 1: 本地缓存检查
        cached = self._check_local_cache(filename)
        if cached is not None:
            return cached

        # 策略 2: 东方财富网搜索
        result = self._search_eastmoney(filename)
        if result:
            return result

        # 策略 3: 通用搜索（返回 None 表示本次调用无法完成，由上层处理）
        logger.info(f"WebFallback 未找到: {filename}")
        return None

    def _check_local_cache(self, filename: str) -> str | None:
        """检查 text 目录下是否已有同名 txt 缓存。"""
        # 从 pdf_path 推断 text 目录
        # 约定：PDF 在 eastmoney/ 下，txt 在 text/ 下
        candidate_paths = [
            Path.cwd() / "data" / "cache" / f"{filename}.txt",
        ]

        for p in candidate_paths:
            if p.exists():
                logger.info(f"命中本地缓存: {p}")
                return p.read_text(encoding="utf-8")
        return None

    def _search_eastmoney(self, title: str) -> str | None:
        """搜索东方财富网研报页面并提取文字。

        返回提取的文字内容，失败返回 None。
        """
        try:
            import urllib.parse
            import urllib.request

            # 构造东方财富研报搜索 URL
            encoded = urllib.parse.quote(title)
            search_url = (
                f"https://search.eastmoney.com/search?"
                f"input={encoded}&type=8192"
                f"&filter=(report_type%3D%E4%B8%AA%E8%82%A1%E7%A0%94%E6%8A%A5)"
            )

            req = urllib.request.Request(
                search_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # 尝试从搜索结果页提取研报链接
            report_url = self._extract_report_url(html, title)
            if not report_url:
                logger.info("未从搜索结果中提取到研报链接")
                return None

            # 抓取研报详情页
            text = self._fetch_report_page(report_url)
            if text:
                return text

            return None

        except Exception as e:
            logger.warning(f"东方财富搜索失败: {e}")
            return None

    def _extract_report_url(self, html: str, title: str) -> str | None:
        """从东方财富搜索结果 HTML 中提取研报详情页 URL。"""
        # 匹配 data-link 或 href 中的研报链接
        patterns = [
            r'data-link="(/report/[^"]+)"',
            r'href="(/report/[^"]+)"',
            r'href="(/jiangu/report/[^"]*)"',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html)
            for m in matches:
                if "eastmoney.com" not in m:
                    m = f"https://data.eastmoney.com{m}"
                return m

        # 回退：匹配 data.eastmoney.com 域名的任意研报链接
        fallback = re.findall(r'https?://data\.eastmoney\.com/report/[^"\s]+', html)
        if fallback:
            return fallback[0]

        return None

    def _fetch_report_page(self, url: str) -> str | None:
        """抓取研报详情页并提取文字内容。"""
        try:
            import urllib.request

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # 提取正文：去除 HTML 标签，保留中文文本
            # 移除 script/style 块
            html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)

            # 移除 HTML 标签
            text = re.sub(r"<[^>]+>", "", html)

            # 清理空白
            text = re.sub(r"\n\s*\n", "\n\n", text)
            text = re.sub(r"[ \t]+", " ", text)
            text = text.strip()

            # 只保留有意义的中文段落（至少含 20 个中文字符）
            lines = text.split("\n")
            meaningful = [line.strip() for line in lines if len(re.findall(r"[\u4e00-\u9fff]", line)) >= 20]

            if meaningful:
                return "\n\n".join(meaningful)

            return None

        except Exception as e:
            logger.warning(f"抓取研报页面失败: {url} - {e}")
            return None

    # ── 辅助方法 ─────────────────────────────────────────────

    def _pdf_to_images(self, pdf_path: str) -> list:
        """将 PDF 每页转换为 PIL Image 列表。

        需要 pdf2image + poppler。
        """
        try:
            from pdf2image import convert_from_path

            return convert_from_path(pdf_path, dpi=200)
        except ImportError:
            logger.warning("pdf2image 未安装，尝试使用 PyMuPDF")
            return self._pdf_to_images_pymupdf(pdf_path)
        except Exception as e:
            logger.error(f"PDF 转图片失败: {e}")
            return []

    def _pdf_to_images_pymupdf(self, pdf_path: str) -> list:
        """使用 PyMuPDF 将 PDF 转图片（兜底方案）。"""
        try:
            import io

            import fitz  # PyMuPDF
            from PIL import Image

            doc = fitz.open(pdf_path)
            images = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                images.append(img)
            doc.close()
            return images
        except ImportError:
            logger.warning("PyMuPDF (fitz) 未安装")
            return []
        except Exception as e:
            logger.error(f"PyMuPDF 转图片失败: {e}")
            return []

    def _load_local_cache(self, txt_path: str) -> str | None:
        """显式从本地 txt 文件加载缓存（供外部调用）。"""
        p = Path(txt_path)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return None

    def save_result(self, text: str, output_path: str) -> bool:
        """将提取的文字保存到文件。"""
        try:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            logger.info(f"文字已保存: {output_path}")
            return True
        except Exception as e:
            logger.error(f"保存失败: {e}")
            return False
