# -*- coding: utf-8 -*-
"""
run_reports.py — 多报告任务队列（R48 并发编排）

**功能**：多个报告并发跑，互不干扰。解决单报告串行的堵塞问题。

**用法**：
  python scripts/run_reports.py "柯力传感" "云迹科技" --type listed_company --workers 2 --mode perf
  python scripts/run_reports.py --list "标的清单.txt" --workers 2 --mode train
  python scripts/run_reports.py --resume batch_20260901  # 从上次 checkpoint 续跑

**模式**：
  --mode perf   性能模式（DeepSeek 高速，默认）
  --mode train  训练模式（Marvis 自迭代）

**并发控制**：
  --workers N   并发 worker 数（默认 2，防 SQLite/API 争抢）
  --priority    可选：高/中/低（队列优先级）
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# 模式 → LLM provider 映射（R48 双模式）
MODE_LLM = {
    "perf": "deepseek",  # 性能模式：DeepSeek 高速
    "train": "agent_provider",  # 训练模式：Marvis 自迭代
}

# S7-2: 批次状态目录
_BATCH_DIR = _ROOT / "data" / "batches"


def _save_batch_state(batch_id: str, state: dict) -> None:
    """保存批次状态。"""
    _BATCH_DIR.mkdir(parents=True, exist_ok=True)
    path = _BATCH_DIR / f"{batch_id}.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_batch_state(batch_id: str) -> dict | None:
    """加载批次状态。"""
    path = _BATCH_DIR / f"{batch_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_single_report(
    asset: str, report_type: str, style: str, output: str, mode: str, max_attempts: int = None, enrich_file: str = None
) -> dict:
    """运行单个报告（子进程隔离，互不干扰）。

    Args:
        asset: 标的名
        report_type: 报告类型
        style: 机构风格
        output: 输出目录
        mode: perf/train
        max_attempts: 迭代上限（train 模式可设高）
        enrich_file: 可选 enrich 文件

    Returns:
        {"asset", "ok", "returncode", "log"}
    """
    cmd = [
        sys.executable,
        str(_ROOT / "pipeline" / "scheduler.py"),
        asset,
        "--type",
        report_type,
        "--style",
        style,
        "--output",
        output,
    ]
    if enrich_file:
        cmd += ["--enrich-file", enrich_file]
    # R82（2026-08-06）：子进程加载 .env——父进程（Claude/终端）可能没加载 .env，
    # 直接继承 os.environ 会拿到空 DeepSeek key，导致反复要求 key。
    # 这里主动读项目 .env 补进子进程环境（不覆盖已存在的）。
    try:
        _env_path = _ROOT / ".env"
        if _env_path.exists():
            for _line in _env_path.read_text(encoding="utf-8-sig").splitlines():
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip('"').strip("'")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass
    # train 模式：通过环境变量传 max_attempts（scheduler 读它）
    env = dict(os.environ)
    # 2026-08-07：节点级混编路由——RUN_MODE 传给 route_policy 按节点选 provider。
    # 不设 LLM_PROVIDER（route_policy 已接管 write/merge/revise 路由）。
    env["RUN_MODE"] = mode
    if max_attempts:
        env["MAX_ATTEMPTS"] = str(max_attempts)

    log_path = _ROOT / "logs" / f"report_{asset}_{int(time.time())}.log"
    start = time.time()
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            r = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600, env=env
            )
            f.write(r.stdout)
            f.write(r.stderr)
        return {
            "asset": asset,
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "log": str(log_path),
            "elapsed_s": round(time.time() - start, 1),
        }
    except subprocess.TimeoutExpired:
        return {
            "asset": asset,
            "ok": False,
            "returncode": -1,
            "log": str(log_path),
            "elapsed_s": round(time.time() - start, 1),
            "error": "timeout",
        }
    except Exception as e:
        return {
            "asset": asset,
            "ok": False,
            "returncode": -1,
            "log": str(log_path),
            "elapsed_s": round(time.time() - start, 1),
            "error": str(e)[:100],
        }


def run_reports(
    assets: list,
    report_type: str,
    style: str,
    output: str,
    workers: int,
    mode: str,
    max_attempts: int = None,
    enrich_file: str = None,
    verbose: bool = True,
    batch_id: str | None = None,
    resume: bool = False,
) -> list:
    """并发运行多个报告。

    Returns:
        [{"asset", "ok", "returncode", "log", "elapsed_s", "error"}]
    """
    if not assets:
        print("[RUN] 无标的输入")
        return []

    # S7-2: 批次 ID 和状态恢复
    if not batch_id:
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    completed_assets = set()
    if resume:
        prev = _load_batch_state(batch_id)
        if prev:
            completed_assets = {r["asset"] for r in prev.get("results", []) if r.get("ok")}
            assets = [a for a in assets if a not in completed_assets]
            print(f"[RUN] 恢复批次 {batch_id}，已完成 {len(completed_assets)} 个，剩余 {len(assets)} 个")

    print(f"[RUN] 开始 {len(assets)} 个报告，mode={mode}, workers={workers}, batch={batch_id}")
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_single_report, a, report_type, style, output, mode, max_attempts, enrich_file): a
            for a in assets
        }
        for fut in as_completed(futures):
            asset = futures[fut]
            try:
                r = fut.result()
                results.append(r)
                status = "✓" if r["ok"] else "✗"
                print(
                    f"[RUN] {status} {asset} "
                    f"({r['elapsed_s']}s, code={r['returncode']})"
                    + (f" error={r.get('error', '')}" if not r["ok"] else "")
                )
            except Exception as e:
                results.append({"asset": asset, "ok": False, "error": str(e)[:100]})
                print(f"[RUN] ✗ {asset} error={str(e)[:80]}")

            # S7-2: 每个报告完成后保存批次状态（支持断点续跑）
            _save_batch_state(batch_id, {
                "batch_id": batch_id,
                "report_type": report_type,
                "style": style,
                "mode": mode,
                "results": results,
                "updated_at": datetime.now().isoformat(),
            })

    # 汇总
    ok = sum(1 for r in results if r.get("ok"))
    print(f"[RUN] 完成: {ok}/{len(results)} 成功 (batch={batch_id})")
    return results


def main():
    parser = argparse.ArgumentParser(description="2hao 多报告任务队列")
    parser.add_argument("assets", nargs="*", help="标的列表")
    parser.add_argument("--list", "-l", default=None, help="标的清单文件（每行一个）")
    parser.add_argument(
        "--type",
        "-t",
        default="listed_company",
        choices=["industry_deep", "listed_company", "unlisted_company", "earnings_notes"],
    )
    parser.add_argument("--style", "-s", default="cicc")
    parser.add_argument("--output", "-o", default="output")
    parser.add_argument("--workers", "-w", type=int, default=2, help="并发数")
    parser.add_argument(
        "--mode",
        "-m",
        default="perf",
        choices=["perf", "train"],
        help="perf=性能模式(DeepSeek) / train=训练模式(Marvis)",
    )
    parser.add_argument("--max-attempts", type=int, default=None, help="迭代上限（train 模式建议 5-10）")
    parser.add_argument("--enrich-file", "-e", default=None)
    parser.add_argument("--retry", "-r", type=int, default=0, help="失败后重试次数（默认 0；借助 checkpoint 续跑）")
    parser.add_argument("--batch-id", default=None, help="批次 ID（用于状态追踪）")
    parser.add_argument("--resume", action="store_true", help="从上次 checkpoint 续跑（需配合 --batch-id）")
    args = parser.parse_args()

    assets = list(args.assets)
    if args.list:
        p = Path(args.list)
        if p.exists():
            assets += [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            print(f"[ERR] 清单文件不存在: {args.list}")
            sys.exit(1)

    # R81 fix: run_reports 签名无 retry 参数，--retry 留作兼容选项
    results = run_reports(
        assets, args.type, args.style, args.output, args.workers, args.mode,
        args.max_attempts, args.enrich_file,
        batch_id=args.batch_id, resume=args.resume,
    )
    # 输出结果 JSON 供调用方分析
    out = _ROOT / "output" / "run_reports_result.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[RUN] 结果写入: {out}")

    # 有任何失败则非零退出
    if any(not r.get("ok") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
