"""
OCR 引擎环境配置文件
--------------------
集中管理 OCR 引擎的运行环境参数。
修改此文件即可切换 UnlimitedOCR 的本地/远程模式。
"""

# ── 环境检测 ────────────────────────────────────────────────

# 当前 torch 为 CPU 版本（torch 2.10.0+cpu），CUDA 不可用
# UnlimitedOCR 本地模式需要 CUDA torch，因此在当前环境不可用
HAS_CUDA_TORCH = True

# ── UnlimitedOCR 配置 ───────────────────────────────────────

# 远程 API 地址（若部署 SGLang / vLLM Docker 后设置）
# 示例: "http://10.0.0.5:8000/ocr"
# 设为 None 表示使用本地 transformers pipeline
UNLIMITED_OCR_API_URL = "http://127.0.0.1:8000/v1/chat/completions"

# 模型名称（本地 pipeline 模式使用）
UNLIMITED_OCR_MODEL_NAME = "baidu/Unlimited-OCR"

# 设备设置："cuda" 或 "cpu"（本地 pipeline 模式使用）
UNLIMITED_OCR_DEVICE = "cuda"

# ── WebFallback 配置 ────────────────────────────────────────

# 本地缓存目录：已提取文字缓存的 txt 文件目录
WEBFALLBACK_CACHE_DIR = "D:/Claude/projects/analysis/benchmark_reports/text"

# 东方财富研报搜索基地址
EASTMONEY_SEARCH_URL = "https://search.eastmoney.com/search"

# ── Docker 部署参考 ─────────────────────────────────────────
#
# Unlimited-OCR 独立 GPU 环境部署命令（SGLang 示例）:
#
#   docker run --gpus all -p 8000:8000 \
#     lmsysorg/sglang:latest \
#     python -m sglang.launch_server \
#       --model-path baidu/Unlimited-OCR \
#       --host 0.0.0.0 --port 8000
#
# 部署后修改本文件:
#   UNLIMITED_OCR_API_URL = "http://<GPU_SERVER_IP>:8000/v1/chat/completions"
