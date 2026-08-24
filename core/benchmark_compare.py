"""
预测 vs 基准检验（Benchmark Compare）— R30 模块9a：对标学术研究

**问题**：2hao 的预测跑赢"均值回归"基准吗？从未测过。
对标学术：模型预测必须跑赢朴素基准（沿用去年增速/均值回归）才算有价值。

**方案**：对已验证的预测，对比 2hao 预测误差 vs 基准误差。
  基准 = 均值回归（实际收益→0 收敛）
  - 若 2hao 预测方向正确且误差 < 基准误差 → 有超额价值
  - 否则 → 预测无增量信息，需校准
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

logger = logging.getLogger("2hao.benchmark_compare")

_ROOT = Path(__file__).resolve().parent.parent
FP_DIR = _ROOT / "data" / "forward_picks"


def _load_verified_picks() -> list[dict]:
    """加载已验证的预测。"""
    path = FP_DIR / "forward_picks.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r.get("verification_status") in ("hit", "miss")]


def compare_vs_benchmark() -> dict:
    """对比 2hao 预测 vs 均值回归基准。

    逻辑：
      - 2hao 预测：direction 方向（bull/bear）+ actual_return
      - 基准（均值回归）：预测收益 = 0（回归均值），误差 = |actual_return|
      - 2hao 误差：direction 正确时误差小，错误时误差大
      - 超额 = 基准误差 - 2hao 误差（>0 说明预测有价值）

    简化实现：2hao 命中率 vs 随机基准（50%）
    """
    picks = _load_verified_picks()
    if not picks:
        return {"total": 0, "hit_rate": 0, "benchmark_hit_rate": 0.5, "excess": 0, "note": "暂无已验证预测"}

    total = len(picks)
    hit = sum(1 for p in picks if p.get("verification_status") == "hit")
    hit_rate = hit / total if total else 0

    # 基准 = 随机（50%）
    benchmark_hit_rate = 0.5
    # 超额：2hao 命中率 - 基准命中率（正=有增量价值）
    excess = hit_rate - benchmark_hit_rate

    # 结论
    if excess > 0.1:
        conclusion = "2hao 预测显著跑赢随机基准（有增量价值）"
    elif excess > 0:
        conclusion = "2hao 预测略优于随机基准"
    elif excess > -0.1:
        conclusion = "2hao 预测接近随机水平（需校准）"
    else:
        conclusion = "2hao 预测劣于随机（可能系统偏差，需大改）"

    return {
        "total": total,
        "hit": hit,
        "hit_rate": round(hit_rate, 3),
        "benchmark_hit_rate": benchmark_hit_rate,
        "excess": round(excess, 3),
        "conclusion": conclusion,
        "note": "基准=随机50%（简化）。后续可升级为'均值回归'基准（预测收益=0）。",
    }


def serialize_benchmark(b: dict) -> str:
    """序列化注入。"""
    if not b:
        return ""
    lines = [
        "=== 预测 vs 基准检验（对标学术研究） ===",
        f"已验证预测: {b.get('total', 0)} | 命中率: {b.get('hit_rate', 0):.0%}",
        f"基准命中率: {b.get('benchmark_hit_rate', 0):.0%} | 超额: {b.get('excess', 0):+.0%}",
        f"结论: {b.get('conclusion', '')}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    b = compare_vs_benchmark()
    print(serialize_benchmark(b))
