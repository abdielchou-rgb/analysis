"""V51 Full Benchmark: V51 outputs vs real analyst reports.

5-dimension scoring (FinRpt framework) applied to both groups.
Outputs a side-by-side comparison report.
"""

from __future__ import annotations
import re, csv, json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScoreCard:
    clarity: float = 0.0
    depth: float = 0.0
    data: float = 0.0
    logic: float = 0.0
    objectivity: float = 0.0


def score_report(text: str) -> ScoreCard:
    """5-dimension scoring (1-5)."""
    sc = ScoreCard()
    lines = text.split('\n')
    chapters = [c for c in re.split(r'\n#+\s', text) if len(c) > 100]
    n_chapters = max(len(chapters), 1)

    # Clarity: judgment sentences in first 20% of lines
    first = lines[:max(len(lines)//5, 10)]
    jp = [r'我们[认为判断预计预期]', r'将[会带提升下降]', r'[有望可能]', r'意味着', r'关键[在于是]']
    jh = sum(1 for l in first if any(re.search(p, l) for p in jp))
    sc.clarity = min(5.0, 1.0 + jh * 0.5)

    # Depth: contrarian judgment density
    sk = ["而非", "不同于市场", "与市场分歧", "超预期", "低于预期", "颠覆", "拐点",
          "结构性变化", "误读", "未充分定价", "预期差", "认知差", "我们的判断有别于"]
    sc2 = sum(1 for c in chapters if any(k in c for k in sk))
    sc.depth = min(5.0, 1.0 + sc2 / n_chapters * 5)

    # Data: citations + concrete company-level numbers
    cits = text.count("来源") + text.count("数据来源") + text.count("年报") + text.count("报告")
    dps = len(re.findall(r'\d+[\.\d]*\s*[%亿元万元倍家个个点]', text))
    sc.data = min(5.0, 1.0 + min(cits/5, 2.0) + min(dps/20, 2.0))

    # Logic: counter-argument structure
    cl = ["风险", "证伪", "反方", "不及预期", "不利", "谨慎", "然而", "但是", "不足", "挑战", "反之"]
    cc = sum(1 for l in lines if l.startswith("##") and any(k in l for k in cl))
    sc.logic = min(5.0, 1.0 + cc * 0.8)

    # Objectivity: AI contamination
    ai = ["AIGC", "ContentProducer", "AI生成", "由AI", "AI辅助", "内容由AI生成", "仅供参考"]
    ah = sum(1 for a in ai if a in text)
    sc.objectivity = 5.0 if ah == 0 else max(1.0, 5.0 - ah * 2)

    return sc


def run_benchmark(v51_dir="outputs", bench_dir=None) -> dict:
    """Run full benchmark and return results dict."""
    v51_path = Path(v51_dir)
    if not v51_path.exists():
        return {"error": f"V51 directory not found: {v51_dir}"}

    # Find V51 reports
    v51_files = sorted(v51_path.glob("*贵州茅台*.md")) + \
                sorted(v51_path.glob("*宁德时代*.md")) + \
                sorted(v51_path.glob("*半导体*.md")) + \
                sorted(v51_path.glob("V_*.md"))
    v51_files = [f for f in v51_files if "benchmark" not in f.name.lower() and "pack_" not in f.name]
    v51_files = v51_files[:10]  # cap at 10

    # Find benchmark reports
    bench_files = []
    if bench_dir:
        bp = Path(bench_dir)
        if bp.exists():
            bench_files = sorted(bp.glob("*.txt")) + sorted(bp.glob("*.md"))
            bench_files = [f for f in bench_files if f.stat().st_size > 1000][:10]
    # Filter out image-PDF extracts (too short to be meaningful)
    import itertools
    bench_files = [f for f in bench_files if f.stat().st_size > 5000 or '年报' in f.name]

    # Score V51
    v51_scores = []
    for f in v51_files:
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
            sc = score_report(t)
            v51_scores.append({"name": f.stem, "scores": sc, "type": "v51"})
        except Exception as e:
            print(f"  Error reading {f.name}: {e}")

    # Score benchmark
    bench_scores = []
    for f in bench_files:
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
            sc = score_report(t)
            bench_scores.append({"name": f.stem, "scores": sc, "type": "benchmark"})
        except Exception as e:
            print(f"  Error reading {f.name}: {e}")

    # Averages
    def avg(scores_list, dim):
        vals = [getattr(s["scores"], dim) for s in scores_list]
        return sum(vals) / len(vals) if vals else 0

    dims = ["clarity", "depth", "data", "logic", "objectivity"]
    v51_avg = {d: avg(v51_scores, d) for d in dims}
    bench_avg = {d: avg(bench_scores, d) for d in dims}
    gap = {d: round(min(bench_avg[d],5.0) - min(v51_avg[d],5.0), 2) for d in dims}

    return {
        "v51_files": len(v51_files),
        "bench_files": len(bench_files),
        "v51_averages": v51_avg,
        "bench_averages": bench_avg,
        "gaps": gap,
        "v51_details": v51_scores,
        "bench_details": bench_scores,
    }


def print_report(r: dict):
    """Print benchmark report."""
    print()
    print("=" * 60)
    print("     V51 完整回测对标报告")
    print("=" * 60)
    print()
    print(f"  评分框架: FinRpt 5维 (1-5分制)")
    print(f"  V51产出: {r['v51_files']} 篇")
    print(f"  真实研报: {r['bench_files']} 篇")
    print()
    dim_cn = {"clarity": "Clarity (结构)", "depth": "Depth (锐度)", "data": "Data (数据)",
              "logic": "Logic (反方)", "objectivity": "Objectivity (去AI)"}

    print(f"  {'维度':20s}  {'V51':>8s}  {'真实研报':>10s}  {'差距':>8s}")
    print(f"  {'-'*20}  {'-'*8}  {'-'*10}  {'-'*8}")
    for d in ["clarity", "depth", "data", "logic", "objectivity"]:
        v = r["v51_averages"][d]
        b = r["bench_averages"][d]
        g = r["gaps"][d]
        if b > 0:
            print(f"  {dim_cn[d]:20s}  {min(v,5.0):>7.2f}  {min(b,5.0):>9.2f}  {g:>+7.2f}")
        else:
            print(f"  {dim_cn[d]:20s}  {v:>7.2f}  {'N/A':>10s}  {'N/A':>8s}")

    if r["bench_files"] > 0:
        print()
        print("-" * 60)
        print(f"  分析:")
        for d in ["clarity", "depth", "data", "logic", "objectivity"]:
            g = r["gaps"][d]
            if g > 0:
                tag = "落后" if abs(g) > 1 else "接近"
            else:
                tag = "领先" if abs(g) > 0.5 else "持平"
            print(f"    {dim_cn[d]}: V51 {tag}真实研报 {abs(g):.2f} 分")
        print()
        worst_dim = max(r["gaps"], key=lambda d: r["gaps"][d])
        best_dim = min(r["gaps"], key=lambda d: r["gaps"][d]) if r.get("bench_files", 0) > 0 else list(r["gaps"].keys())[0]
        print(f"  最大差距: {dim_cn[worst_dim]} ({r['gaps'][worst_dim]:+.2f})")
        if r["gaps"][best_dim] < 0:
            print(f"  唯一领先: {dim_cn[best_dim]} ({r['gaps'][best_dim]:+.2f})")
        print()
        print("  改进建议 (按影响排序):")
        print(f"    1. 激活 LLM 全文生成 (Clarity +2.0, Depth +1.5)")
        print(f"    2. V30 Compute Engine 接入财务数据 (Data +1.0)")
        print(f"    3. 强化反方论证模板 (Logic +1.5)")
    else:
        print()
        print("  [未检测到真实研报文本文件。请先执行 PDF 提取步骤]")

    # Save to file
    out_path = Path("outputs") / "V51_Benchmark_Report.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Reconstruct for file output
    lines = [
        "---\n", f"v51_reports: {r['v51_files']}\n",
        f"benchmark_reports: {r['bench_files']}\n",
        f"v51_averages: {json.dumps(r['v51_averages'])}\n",
        f"bench_averages: {json.dumps(r['bench_averages'])}\n",
        f"gaps: {json.dumps(r['gaps'])}\n", "---\n\n",
        "# V51 完整回测对标报告\n\n",
        f"## 概览\nV51产出: {r['v51_files']} 篇, 真实研报: {r['bench_files']} 篇\n\n",
        "## 评分对比\n", "| 维度 | V51 | 真实研报 | 差距 |\n",
        "|------|-----|---------|------|\n",
    ]
    for d in ["clarity", "depth", "data", "logic", "objectivity"]:
        v = r["v51_averages"][d]
        b = r["bench_averages"][d]
        g = r["gaps"][d]
        lines.append(f"| {dim_cn[d]} | {v:.2f} | {b:.2f} | {g:+.2f} |\n")

    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"\n  报告已保存: {out_path}")
    print("=" * 60)

    # Save CSV
    csv_path = Path("benchmark_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["维度", "V51产出", "真实研报", "差距"])
        for d in ["clarity", "depth", "data", "logic", "objectivity"]:
            w.writerow([dim_cn[d], round(r["v51_averages"][d], 2),
                       round(r["bench_averages"][d], 2) if r["bench_files"] > 0 else "N/A",
                       round(r["gaps"][d], 2) if r["bench_files"] > 0 else "N/A"])
    print(f"  CSV已保存: {csv_path}")

    return r


if __name__ == "__main__":
    import sys
    v51_dir = sys.argv[1] if len(sys.argv) > 1 else "outputs"
    bench_dir = sys.argv[2] if len(sys.argv) > 2 else None
    r = run_benchmark(v51_dir, bench_dir)
    if "error" in r:
        print(f"Error: {r['error']}")
        sys.exit(1)
    print_report(r)
    sys.exit(0)
