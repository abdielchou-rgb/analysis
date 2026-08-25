#!/usr/bin/env python3
"""2hao-analyst 三份深度报告一键运行（Python 版，跨平台）

标的: 中芯国际 / 宁德时代 / 汇川技术
类型: listed_company | 风格: cicc

用法:
    python scripts/run_3_reports.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
REPORTS = [
    ("中芯国际", "listed_company"),
    ("宁德时代", "listed_company"),
    ("汇川技术", "listed_company"),
]
STYLE = "cicc"


def main():
    print("=" * 60)
    print("  2hao-analyst — 三份深度报告批量运行")
    print("=" * 60)

    # 1. 环境准备
    if not (_ROOT / ".env").exists():
        print("[!!] 缺少 .env 文件！请创建并填入 DEEPSEEK_API_KEY / TAVILY_API_KEY")
        return 1
    print("[1/4] .env 存在 ✓")

    # 2. 依赖检查
    try:
        import akshare, tavily, openai, pdfplumber  # noqa

        print("[2/4] 依赖完整 ✓")
    except ImportError as e:
        print(f"[2/4] 缺依赖: {e}，尝试安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=_ROOT)
        print("  安装完成，请重试。")
        return 1

    # 3. 逐份跑报告
    print(f"[3/4] 生成 {len(REPORTS)} 份报告（每份约 5-15 分钟）...")
    # 继承当前环境变量 + 只追加 ENFORCE_GATE（不能替换，否则 Windows 下
    # 丢失 SystemRoot 等关键变量导致 _overlapped.pyd 加载失败 WinError 10106）
    env = dict(os.environ)
    env["ENFORCE_GATE"] = "true"
    env["PYTHONUNBUFFERED"] = "1"
    results = []
    for i, (asset, rtype) in enumerate(REPORTS, 1):
        print(f"\n  --- 第{i}份: {asset} ---")
        t0 = time.time()
        cmd = [sys.executable, "pipeline/scheduler.py", asset, "--type", rtype, "--style", STYLE, "--output", "output"]
        r = subprocess.run(cmd, cwd=_ROOT, env=env)
        dt = time.time() - t0
        ok = r.returncode == 0
        print(f"  {'✓' if ok else '✗'} {asset} 退出码={r.returncode} 耗时={dt / 60:.1f}分钟")
        results.append((asset, ok))

    # 4. 汇总
    print("\n[4/4] 完成！")
    print("=" * 60)
    for asset, ok in results:
        print(f"  {'✓' if ok else '✗'} {asset}")
    print("=" * 60)
    print("报告输出在 output/ 目录")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
