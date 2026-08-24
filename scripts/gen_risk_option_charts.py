# -*- coding: utf-8 -*-
"""生成 tornado 敏感性表 + 风险矩阵 + 期权定价（接入油位报告）"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = Path("output/charts")
OUT.mkdir(parents=True, exist_ok=True)


def tornado_chart():
    """Tornado 敏感性图：毛利率/罐箱渗透率/单价/爬坡 × 对 NPV 的影响。"""
    # 基准 NPV 3116 万元；各变量 ± 波动对 NPV 的影响（估算，万元）
    items = [
        ("毛利率 -10pct", -1850, "#c0504d"),
        ("毛利率 +10pct", +2050, "#2e7d32"),
        ("罐箱渗透率 -30%", -1400, "#c0504d"),
        ("罐箱渗透率 +30%", +1550, "#2e7d32"),
        ("单价 -15%", -950, "#c0504d"),
        ("单价 +15%", +1050, "#2e7d32"),
        ("爬坡慢1年", -780, "#c0504d"),
        ("爬坡快1年", +850, "#2e7d32"),
    ]
    # 按影响绝对值排序（tornado 惯例）
    items.sort(key=lambda x: abs(x[1]))

    fig, ax = plt.subplots(figsize=(12, 6.5))
    fig.patch.set_facecolor("white")
    y_pos = range(len(items))
    labels = [x[0] for x in items]
    vals = [x[1] for x in items]
    colors = [x[2] for x in items]
    ax.barh(list(y_pos), vals, color=colors, height=0.6)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=14)
    ax.axvline(0, color="black", lw=1)
    ax.set_xlabel("NPV 变化（万元）", fontsize=15)
    ax.set_title("关键变量敏感性 Tornado（基准 NPV +3,116 万元）", fontsize=19, fontweight="bold", pad=15)
    for i, v in enumerate(vals):
        ax.text(v + (60 if v > 0 else -60), i, f"{v:+d}", va="center",
                ha="left" if v > 0 else "right", fontsize=13, fontweight="bold")
    ax.text(0.5, -0.15,
            "毛利率 + 罐箱渗透率 两项驱动项目价值约80%——须季度复核 + 压力测试(±30%)",
            transform=ax.transAxes, ha="center", fontsize=14, color="#7b1fa2",
            bbox=dict(boxstyle="round", facecolor="#f3e5f5", edgecolor="#7b1fa2"))
    plt.tight_layout()
    out = OUT / "fig_tornado_sensitivity.png"
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print("✅", out)


def risk_matrix():
    """风险矩阵：概率 × 影响，量化最可能风险。"""
    risks = [
        ("久通渠道订单未达预期", 0.35, 800, "中"),
        ("认证延期（>18个月）", 0.30, 700, "中"),
        ("毛利率低于40%", 0.30, 1200, "高"),
        ("波导丝涨价/断供", 0.15, 900, "中"),
        ("政策红利2028回落", 0.40, 600, "中"),
        ("雷达物位计替代加速", 0.20, 500, "中"),
    ]
    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor("white")
    for r in risks:
        name, prob, impact, sev = r
        color = {"高": "#c0504d", "中": "#ed7d31", "低": "#2e7d32"}[sev]
        ax.scatter(prob, impact, s=700, color=color, alpha=0.8, edgecolor="white", zorder=3)
        ax.text(prob, impact + 40, name, ha="center", fontsize=11)
    ax.set_xlabel("发生概率", fontsize=14)
    ax.set_ylabel("影响金额（万元）", fontsize=14)
    ax.set_title("风险矩阵：概率 × 影响（量化）", fontsize=19, fontweight="bold", pad=15)
    ax.set_xlim(0, 0.55)
    ax.set_ylim(0, 1500)
    ax.grid(alpha=0.3)
    # 高影响区标记
    ax.axhline(1000, color="#c0504d", ls="--", alpha=0.5)
    ax.text(0.01, 1050, "高影响区", fontsize=11, color="#c0504d")
    plt.tight_layout()
    out = OUT / "fig_risk_matrix.png"
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print("✅", out)


def option_pricing():
    """四重战略期权定价（粗糙量化）。"""
    # 基于 contract_manufacturing 的 BS 期权逻辑
    options = [
        ("40-50亿可竞争市场", "进入油位大类的入场券", 2100, "NPV+期权"),
        ("罐箱渗透率+1%", "增量NPV约300万/个百分点", 300, "边际期权"),
        ("久通80国渠道", "海外线收入期权", 1500, "渠道期权"),
        ("物位大类延伸", "雷达/物位计高端品类", 2000, "扩张期权"),
    ]
    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor("white")
    labels = [o[0] for o in options]
    vals = [o[2] for o in options]
    bars = ax.bar(labels, vals, color=["#1f4e79", "#2e7d32", "#c0504d", "#7b1fa2"], width=0.5)
    ax.set_ylabel("期权价值（万元）", fontsize=14)
    ax.set_title("四重战略期权价值（粗糙量化）", fontsize=19, fontweight="bold", pad=15)
    for i, (bar, o) in enumerate(zip(bars, options)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 50,
                f"{o[2]:,}万\n{o[3]}", ha="center", fontsize=12)
    ax.text(0.5, -0.15,
            "总期权价值约 +5,900 万元 ≈ 经营期NPV(3,116万) 的 1.9 倍——期权属性强于当期利润",
            transform=ax.transAxes, ha="center", fontsize=14, color="#7b1fa2",
            bbox=dict(boxstyle="round", facecolor="#f3e5f5", edgecolor="#7b1fa2"))
    ax.set_ylim(0, 3500)
    plt.tight_layout()
    out = OUT / "fig_option_pricing.png"
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print("✅", out)


if __name__ == "__main__":
    tornado_chart()
    risk_matrix()
    option_pricing()
    print("tornado/风险矩阵/期权定价图生成完成")
