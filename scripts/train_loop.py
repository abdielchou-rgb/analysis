# -*- coding: utf-8 -*-
"""
train_loop.py — 训练模式自迭代闭环（R52 三期）

**功能**：训练模式（Marvis）下，自动执行 写→审→改→记 循环直到满意，
并把改报告过程记录下来，最终汇成综合分析。

**流程**：
  1. 跑管线生成报告（LLM_PROVIDER=agent_provider，MAX_ATTEMPTS 高）
  2. 对报告做 Gate 校验 + 审计（圆桌式检查）
  3. 若未通过，记录问题，带 feedback 重跑（局部修订）
  4. 直到 Gate 全过 + 无 P0，记录最终报告
  5. 汇总各轮修改历史 → 综合分析

**用法**：
  python scripts/train_loop.py "柯力传感" --max-attempts 5
  python scripts/train_loop.py "云迹科技" --max-attempts 8 --style gs --type unlisted_company
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def run_pipeline(
    asset: str, report_type: str, style: str, max_attempts: int, attempt: int, enrich_file: str = None
) -> dict:
    """跑一次管线，返回 {ok, gate_score, failures, report_path}"""
    env = dict(os.environ)
    env["LLM_PROVIDER"] = "agent_provider"  # 训练模式：Marvis
    env["MAX_ATTEMPTS"] = str(max_attempts)

    cmd = [sys.executable, str(_ROOT / "pipeline" / "scheduler.py"), asset, "--type", report_type, "--style", style]
    if enrich_file:
        cmd += ["--enrich-file", enrich_file]
    log = _ROOT / "logs" / f"train_{asset}_a{attempt}.log"
    report_path = _ROOT / "output" / "_gate_prev.md"  # 2026-08-03: 未过Gate时管线产出
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600, env=env, encoding="utf-8", errors="replace"
        )
        log.write_text(r.stdout + r.stderr, encoding="utf-8")
        # 从输出解析 Gate 结果
        gate_score = None
        failures = []
        for line in (r.stdout or "").splitlines():
            if "score=" in line and "Gate" in line:
                try:
                    gate_score = float(line.split("score=")[1].split()[0])
                except (ValueError, IndexError):
                    pass
            if "FAIL" in line and "Gate" in line:
                failures.append(line.strip()[:80])
        # 尝试从失败摘要提取报告路径（e2e 输出 "最终报告(未过Gate)在 <path>"）
        import re as _re

        m = _re.search(r"未过Gate\)在\s+(\S+\.md)", r.stdout or "")
        if m:
            report_path = _ROOT / m.group(1)
        return {
            "ok": r.returncode == 0,
            "gate_score": gate_score,
            "failures": failures,
            "log": str(log),
            "returncode": r.returncode,
            "report_path": str(report_path) if report_path.exists() else "",
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "gate_score": None,
            "failures": ["timeout"],
            "log": str(log),
            "returncode": -1,
            "report_path": str(report_path) if report_path.exists() else "",
        }


def audit_report(asset: str, report_type: str, style: str = "cicc", report_path: str = None) -> dict:
    """对报告做 Gate 复评（训练模式审计环节）。

    2026-08-03 修复：此前 `glob(f"output/{asset}*.md")` 取第一个文件，
    而管线未过 Gate 时实际产出在 output/_gate_prev.md（共享锚点文件）。
    → 训练模式审计的一直是旧文件（如 Jul-26 的 气体传感器…_cicc.md），
    导致 3 轮审计分数卡死不变（0.7212）。
    修复：优先审计本轮产出（report_path 参数），否则取 mtime 最新的候选，
    并把 _gate_prev.md 纳入候选。
    """
    try:
        from pathlib import Path as _P

        from pipeline.iron_gate import IronGate

        # 1) 显式报告路径（run_pipeline 返回）
        if report_path and _P(report_path).exists():
            md_path = _P(report_path)
        else:
            # 2) mtime 最新候选：资产文件 + _gate_prev.md（未过Gate时管线产出）
            candidates = list(_ROOT.glob(f"output/{asset}*.md"))
            gate_prev = _ROOT / "output" / "_gate_prev.md"
            if gate_prev.exists():
                candidates.append(gate_prev)
            if not candidates:
                return {"passed": False, "failures": ["报告文件未找到"]}
            md_path = max(candidates, key=lambda p: p.stat().st_mtime)
        gate = IronGate(str(md_path), report_type, style, asset=asset)
        report = gate.run_all()
        failures = [c.name for c in report.checks if not c.passed]
        return {
            "passed": report.passed,
            "score": round(report.overall_score, 4),
            "failures": failures[:5],
            "report_path": str(md_path),
        }
    except Exception as e:
        return {"passed": False, "failures": [str(e)[:80]]}


def record_iteration(asset: str, iteration: int, result: dict) -> None:
    """记录一轮改报告过程（结构化入库）。"""
    record = {
        "asset": asset,
        "iteration": iteration,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "gate_score": result.get("gate_score"),
        "ok": result.get("ok"),
        "failures": result.get("failures", []),
        "audit": result.get("audit", {}),
    }
    out = _ROOT / "output" / f"train_{asset}_iterations.json"
    history = []
    if out.exists():
        try:
            history = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history.append(record)
    out.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
    return


def synthesize(asset: str) -> str:
    """汇成综合分析（读取迭代历史，生成总结）。"""
    out = _ROOT / "output" / f"train_{asset}_iterations.json"
    if not out.exists():
        return ""
    try:
        history = json.loads(out.read_text(encoding="utf-8"))
    except Exception:
        return ""
    lines = [f"# {asset} 训练模式综合分析", f"共 {len(history)} 轮迭代", ""]
    for h in history:
        lines.append(f"## 第 {h['iteration']} 轮")
        lines.append(f"- Gate 分数: {h.get('gate_score')}")
        lines.append(f"- 状态: {'通过' if h.get('ok') else '未通过'}")
        if h.get("failures"):
            lines.append(f"- 问题: {'; '.join(h['failures'][:3])}")
        if h.get("audit", {}).get("failures"):
            lines.append(f"- 审计: {'; '.join(h['audit']['failures'][:3])}")
        lines.append("")
    summary = _ROOT / "output" / f"train_{asset}_综合分析.md"
    summary.write_text("\n".join(lines), encoding="utf-8")
    return str(summary)


CONVERGE_STREAK = 3  # 连续 3 轮
CONVERGE_EPS = 0.01  # 分数变化 < 0.01 视为平稳


def is_converged(score_history: list, streak: int = CONVERGE_STREAK, eps: float = CONVERGE_EPS) -> bool:
    """R54（2026-08-03 P2-8）：分数平稳=收敛判定。

    连续 streak 轮分数变化 < eps → 收敛（系统已达当前数据/策略极限）。
    返回是否收敛。
    """
    if len(score_history) < streak:
        return False
    recent = score_history[-streak:]
    return (max(recent) - min(recent)) < eps


def train_one(asset: str, report_type: str, style: str, max_attempts: int, min_score: float, enrich_file: str) -> dict:
    """训练单只标的（可被多线程并行调用）。

    Returns:
        {"asset", "ok", "score", "attempts", "summary"}
    """
    print(f"[TRAIN:{asset}] 开始训练模式 (max_attempts={max_attempts}, min_score={min_score})")

    prev_failures = None  # 上轮失败项（用于变化检测，防空转）
    fixed_notes = []  # 已修项记录（跨迭代传递，对标 stevegrocott prior findings）
    # R54（2026-08-03 P2-8）：分数平稳=收敛判定——连续 N 轮分数变化<阈值且未达标
    # 说明系统已达到当前数据/策略下的极限，继续重跑只会浪费，应停止并明确标注。
    score_history = []
    CONVERGE_STREAK = 3  # 连续 3 轮
    CONVERGE_EPS = 0.01  # 分数变化 < 0.01 视为平稳

    for attempt in range(1, max_attempts + 1):
        print(f"\n[TRAIN:{asset}] === 第 {attempt}/{max_attempts} 轮 ===")
        result = run_pipeline(asset, report_type, style, max_attempts, attempt, enrich_file)
        result["audit"] = audit_report(asset, report_type, style, report_path=result.get("report_path"))
        record_iteration(asset, attempt, result)

        score = result.get("audit", {}).get("score", 0)
        passed = result.get("audit", {}).get("passed", False)
        cur_failures = set(result.get("audit", {}).get("failures", []) or result.get("failures", []) or [])
        print(
            f"[TRAIN:{asset}] 第 {attempt} 轮: Gate score={score}, passed={passed}, failures={sorted(cur_failures)[:3]}"
        )

        if passed and score >= min_score:
            print(f"[TRAIN:{asset}] ✅ 达标（score={score} >= {min_score}）")
            break

        # P0-2：失败项变化检测（防空转）
        # 上轮失败 == 本轮失败 且 非首轮 → 无效重跑，提前终止并记录残留问题
        if prev_failures is not None and cur_failures and cur_failures == prev_failures:
            print(
                f"[TRAIN:{asset}] ⚠️ 失败项连续{attempt - 1}轮未变化 {sorted(cur_failures)[:3]} → 提前终止（防无效重跑）"
            )
            result["stalled"] = True
            break

        # R54（2026-08-03 P2-8）：分数平稳收敛判定
        # 分数已录入 ≥CONVERGE_STREAK 轮且全部平稳（变化<EPS）→ 收敛，停止。
        # 区别于失败项检测：失败项可能在变（每次修一个），但分数上不去 → 同样该停。
        score_history.append(score)
        if is_converged(score_history):
            _recent = score_history[-CONVERGE_STREAK:]
            print(
                f"[TRAIN:{asset}] ⚠️ 分数连续{CONVERGE_STREAK}轮平稳"
                f"（{_recent}）但未达标 → 判定收敛（当前数据/策略已达极限），停止"
            )
            result["converged"] = True
            result["score_history"] = score_history
            break

        # P0-3：记录已修项（跨迭代传递）
        if prev_failures is not None:
            newly_fixed = prev_failures - cur_failures
            for f in sorted(newly_fixed):
                fixed_notes.append(f"第{attempt - 1}轮已修复: {f}")
                print(f"[TRAIN:{asset}] ✅ 已修复: {f}")
        prev_failures = cur_failures

        if attempt < max_attempts:
            # 把已修项传给下一轮（state_anchor 升级）
            result["fixed_notes"] = fixed_notes
            print(f"[TRAIN:{asset}] 未达标，下一轮带反馈重跑...")

    # 记录残留问题（终止后明确标注，不假装完成）
    if not result.get("audit", {}).get("passed", False):
        remaining = sorted(prev_failures or [])
        if remaining:
            print(f"[TRAIN:{asset}] 残留问题: {remaining}（未达标，需人工/补数据）")
            result["remaining_failures"] = remaining

    summary = synthesize(asset)
    print(f"\n[TRAIN:{asset}] 综合分析: {summary}")
    return {
        "asset": asset,
        "ok": bool(result.get("ok")),
        "score": result.get("audit", {}).get("score"),
        "attempts": attempt,
        "summary": summary,
        "remaining_failures": result.get("remaining_failures", []),
        "converged": result.get("converged", False),
        "score_history": result.get("score_history", score_history),
    }


def main():
    parser = argparse.ArgumentParser(description="训练模式自迭代闭环（支持多标的并行）")
    parser.add_argument("assets", nargs="*", help="标的列表")
    parser.add_argument("--list", "-l", default=None, help="标的清单文件（每行一个）")
    parser.add_argument("--type", "-t", default="listed_company")
    parser.add_argument("--style", "-s", default="cicc")
    parser.add_argument("--max-attempts", "-m", type=int, default=5, help="最多迭代轮数")
    parser.add_argument("--min-score", type=float, default=0.90, help="满意 Gate 分数")
    parser.add_argument("--workers", "-w", type=int, default=1, help="并发 worker 数（多标的并行训练）")
    parser.add_argument(
        "--enrich-file", "-e", default=None, help="agent 补充数据 JSON（见 pipeline/data_enrichment.py schema）"
    )
    args = parser.parse_args()

    assets = list(args.assets)
    if args.list:
        p = Path(args.list)
        if p.exists():
            assets += [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            print(f"[ERR] 清单文件不存在: {args.list}")
            sys.exit(1)

    if not assets:
        print("[TRAIN] 无标的输入")
        sys.exit(1)

    print(f"[TRAIN] 训练 {len(assets)} 个标的，workers={args.workers}，max_attempts={args.max_attempts}")

    # 多标的并行（train 模式，Marvis 多实例可同时响应多个 agent_provider 请求）
    results = []
    if args.workers > 1 and len(assets) > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(train_one, a, args.type, args.style, args.max_attempts, args.min_score, args.enrich_file): a
                for a in assets
            }
            for fut in as_completed(futures):
                a = futures[fut]
                try:
                    r = fut.result()
                    results.append(r)
                    status = "✓" if r.get("ok") else "✗"
                    print(f"[TRAIN] {status} {a} score={r.get('score')} attempts={r.get('attempts')}")
                except Exception as e:
                    results.append({"asset": a, "ok": False, "error": str(e)[:80]})
                    print(f"[TRAIN] ✗ {a} error={str(e)[:60]}")
    else:
        for a in assets:
            r = train_one(a, args.type, args.style, args.max_attempts, args.min_score, args.enrich_file)
            results.append(r)

    # 汇总
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n[TRAIN] 完成: {ok}/{len(results)} 达标")
    for r in results:
        print(f"  {'✓' if r.get('ok') else '✗'} {r['asset']} score={r.get('score')} attempts={r.get('attempts')}")

    if any(not r.get("ok") for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
