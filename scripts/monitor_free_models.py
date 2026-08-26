#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenRouter 免费模型监控 + 自动重跑管线
每 30 分钟检测一次免费模型可用性，恢复 ≥4 个时自动重跑管线
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "output" / "free_model_monitor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("free_model_monitor")


# 读取 OpenRouter API Key
def load_or_key():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in open(env_path, encoding="utf-8-sig"):
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return os.environ.get("OPENROUTER_API_KEY", "")


OR_KEY = load_or_key()
if not OR_KEY:
    log.error("OPENROUTER_API_KEY 未配置，退出")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {OR_KEY}"}
MIN_FREE_MODELS = 4  # 至少恢复这么多个免费模型才启动
CHECK_INTERVAL = 30 * 60  # 30 分钟

PIPELINE_CMD = [
    sys.executable,
    "-u",
    "pipeline/scheduler.py",
    "浙江觉纤光电",
    "--type",
    "unlisted_company",
    "--style",
    "gs",
    "--enrich-file",
    "output/浙江觉纤光电_enrich.json",
]

ENV_BASE = {
    "DEEPSEEK_API_KEY": "sk-disabled-by-user-openrouter-only",
    "PYTHONIOENCODING": "utf-8",
    "LLM_PROVIDER": "openrouter",
    "NODE_PROVIDER_WRITE": "openrouter",
    "NODE_PROVIDER_SKELETON": "openrouter",
    "NODE_PROVIDER_MERGE": "openrouter",
    "NODE_PROVIDER_REVISE": "openrouter",
    "NODE_PROVIDER_EXTRACT": "openrouter",
    "NODE_PROVIDER_ROUNDTABLE": "openrouter",
    "HAS_AGENT": "0",
    "RUN_MODE": "perf",
    "SKELETON_MODE": "0",
    "SEG_MAX_TOKENS": "12000",
    "LLM_HTTP_TIMEOUT": "600",
    "DIM_PARALLEL": "0",
    "SEG_PARALLEL": "0",
    "SEG_WRITE_DELAY_S": "30",
    "AGENT_GRAPH_NODE_TIMEOUT_S": "7200",
    "WRITE_NODE_TIMEOUT_S": "7200",
    "MAX_ATTEMPTS": "3",
    "RESEARCH_PLANNER_LLM": "0",
    "GATE_LLM_MAX_TOKENS": "2500",
    "CUSTOM_REQUIREMENT": (
        "委托方必答：浙江觉纤光电投资概要，必须突出 "
        "1) 市场前景：华为全光网络/6G+运营商集采+军工量子三大引擎 "
        "2) 技术实力：马普所专利族+量产工艺唯一性+华为联合实验室验证闭环 "
        "3) 投资价值：估值洼地+里程碑清晰+战略绑定确定性+双赛道协同 "
        "4) 两轮融资估值锚点(7亿/2000万→10亿/1亿) "
        "5) 风险催化剂与行业配置建议"
    ),
    "PYTHONIOENCODING": "utf-8",
}


def check_free_models():
    """返回当前可用的免费模型列表"""
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        free_models = []
        for m in data.get("data", []):
            pricing = m.get("pricing", {})
            prompt_price = str(pricing.get("prompt", "")).strip()
            completion_price = str(pricing.get("completion", "")).strip()
            if prompt_price == "0" and completion_price == "0":
                free_models.append(m["id"])
        return free_models
    except Exception as e:
        log.warning(f"检测免费模型失败: {e}")
        return []


def build_openrouter_models(free_list):
    """按优先级排序免费模型（大模型优先）"""
    priority_order = [
        "qwen/qwen3-235b-a22b:free",
        "meta-llama/llama-3.1-405b:free",
        "google/gemini-flash-1.5:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-2-27b-it:free",
        "mistralai/mistral-nemo:free",
        "microsoft/phi-3-medium-128k:free",
        "deepseek/deepseek-v3:free",
        "google/gemini-flash-1.5:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
        "nousresearch/nous-hermes-2-mixtral-8x7b-dpo:free",
        "gryphe/mythomax-l2-13b:free",
        "undi95/toppy-m-7b:free",
        "cognitivecomputations/dolphin-2.9.2-mixtral-8x7b:free",
    ]
    available = [m for m in priority_order if m in free_list]
    # 补充检测到但不在优先级列表里的免费模型
    for m in free_list:
        if m not in available:
            available.append(m)
    return ",".join(available) if available else ""


def run_pipeline(free_models_str):
    """启动管线子进程"""
    env = os.environ.copy()
    env.update({"OPENROUTER_MODELS": free_models_str, **{k: v for k, v in ENV_BASE.items()}})
    # 清理旧日志
    for f in ["output/juexian_run_out.log", "output/juexian_run_err.log"]:
        try:
            os.remove(ROOT / f)
        except FileNotFoundError:
            pass
    # 清理 checkpoint
    try:
        from pipeline.write_checkpoint import clear_checkpoint

        clear_checkpoint("浙江觉纤光电")
    except Exception:
        pass

    log.info(f"启动管线，使用模型: {free_models_str}")
    # 确保输出目录存在
    (ROOT / "output").mkdir(exist_ok=True)
    log.info(f"启动管线，使用模型: {free_models_str}")
    # 确保输出目录存在
    (ROOT / "output").mkdir(exist_ok=True)
    out_log = ROOT / "output" / "juexian_run_out.log"
    err_log = ROOT / "output" / "juexian_run_err.log"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "pipeline/scheduler.py",
            "浙江觉纤光电",
            "--type",
            "unlisted_company",
            "--style",
            "gs",
            "--enrich-file",
            "output/浙江觉纤光电_enrich.json",
        ],
        cwd=str(ROOT),
        env={
            **os.environ,
            **{
                "DEEPSEEK_API_KEY": "sk-disabled-by-user-openrouter-only",
                "PYTHONIOENCODING": "utf-8",
                "LLM_PROVIDER": "openrouter",
                "OPENROUTER_MODELS": free_models_str,
                "NODE_PROVIDER_WRITE": "openrouter",
                "NODE_PROVIDER_SKELETON": "openrouter",
                "NODE_PROVIDER_MERGE": "openrouter",
                "NODE_PROVIDER_REVISE": "openrouter",
                "NODE_PROVIDER_EXTRACT": "openrouter",
                "NODE_PROVIDER_ROUNDTABLE": "openrouter",
                "HAS_AGENT": "0",
                "RUN_MODE": "perf",
                "SKELETON_MODE": "0",
                "SEG_MAX_TOKENS": "12000",
                "LLM_HTTP_TIMEOUT": "600",
                "DIM_PARALLEL": "0",
                "SEG_PARALLEL": "0",
                "SEG_WRITE_DELAY_S": "30",
                "AGENT_GRAPH_NODE_TIMEOUT_S": "7200",
                "WRITE_NODE_TIMEOUT_S": "7200",
                "MAX_ATTEMPTS": "3",
                "RESEARCH_PLANNER_LLM": "0",
                "GATE_LLM_MAX_TOKENS": "2500",
                "CUSTOM_REQUIREMENT": (
                    "委托方必答：浙江觉纤光电投资概要，必须突出 "
                    "1) 市场前景：华为全光网络/6G+运营商集采+军工量子三大引擎 "
                    "2) 技术实力：马普所专利族+量产工艺唯一性+华为联合实验室验证闭环 "
                    "3) 投资价值：估值洼地+里程碑清晰+战略绑定确定性+双赛道协同 "
                    "4) 两轮融资估值锚点(7亿/2000万→10亿/1亿) "
                    "5) 风险催化剂与行业配置建议"
                ),
                "PYTHONIOENCODING": "utf-8",
            },
        },
        stdout=open(out_log, "w", encoding="utf-8"),
        stderr=open(err_log, "w", encoding="utf-8"),
    )
    return proc


def main():
    log.info("=" * 60)
    log.info("OpenRouter 免费模型监控启动 | 检测间隔 30 分钟 | 阈值 ≥4 个免费模型")
    log.info("=" * 60)

    last_check = 0
    pipeline_proc = None

    while True:
        now = time.time()
        if now - last_check >= CHECK_INTERVAL:
            last_check = now
            free_models = check_free_models()
            log.info(f"检测到 {len(free_models)} 个免费模型: {', '.join(free_models)[:200]}")

            if len(free_models) >= MIN_FREE_MODELS:
                free_str = build_openrouter_models(free_models)
                log.info(f"[OK] 达标 ({len(free_models)} >= {MIN_FREE_MODELS})，启动管线")
                log.info(f"使用模型: {free_str}")

                # 杀掉旧进程（如果有）
                # 这里简单处理：新进程会覆盖日志文件
                proc = run_pipeline(free_str)
                log.info(f"管线已启动 (PID: {proc.pid})，等待完成...")

                # 等待管线结束
                return_code = proc.wait()
                if return_code == 0:
                    log.info("[OK] 管线正常结束，IronGate 通过，任务完成")
                    break
                else:
                    log.warning(f"管线异常退出 (code={return_code})，继续监控等待下一轮")
            else:
                log.info(f"未达标 ({len(free_models)} < {MIN_FREE_MODELS})，继续等待...")

        time.sleep(10)  # 短睡眠避免忙等


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("手动停止监控")
    except Exception as e:
        log.exception(f"监控异常退出: {e}")
        sys.exit(1)
