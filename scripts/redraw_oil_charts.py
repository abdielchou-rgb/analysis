# -*- coding: utf-8 -*-
"""重画油位报告图表：图0a市场总览 + 图0b机会逻辑链 + 图12推导总桥
全幅大字（字号≥9pt），留白充足，解决"字体小/排版紧凑/看不清"。
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path

# 中文字体
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
OUT = Path("output/charts")
OUT.mkdir(parents=True, exist_ok=True)

# 配色
C_MAIN = "#1f4e79"      # 深蓝
C_ACCENT = "#c0504d"    # 红
C_GREEN = "#2e7d32"
C_GRAY = "#808080"
C_LIGHT = "#dbe5f1"


def fig0a_market_overview():
    """图0a 油位传感器市场总览——饼图+柱图，大字。"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor("white")

    # 左：全球+中国市场规模（柱）
    years = ["2024", "2025", "2030E"]
    global_v = [46, 50, 65]
    china_v = [166, 172, 195]
    x = range(len(years))
    ax1.bar([i - 0.2 for i in x], global_v, width=0.4, color=C_MAIN, label="全球(亿美元)")
    ax1.bar([i + 0.2 for i in x], china_v, width=0.4, color=C_ACCENT, label="中国(亿元)")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(years, fontsize=16)
    ax1.set_ylabel("市场规模", fontsize=16)
    ax1.set_title("全球与中国油位传感器市场规模", fontsize=20, fontweight="bold", pad=15)
    ax1.legend(fontsize=15, loc="upper left")
    ax1.grid(axis="y", alpha=0.3)
    for i, v in enumerate(global_v):
        ax1.text(i - 0.2, v + 1, f"{v}", ha="center", fontsize=16, fontweight="bold", color=C_MAIN)
    for i, v in enumerate(china_v):
        ax1.text(i + 0.2, v + 1, f"{v}", ha="center", fontsize=16, fontweight="bold", color=C_ACCENT)
    ax1.text(0.02, 0.95, "全球CAGR≈5%", transform=ax1.transAxes, fontsize=15,
             color=C_MAIN, fontweight="bold", va="top")

    # 右：细分结构（饼）
    seg = [15, 20, 65]
    labels = ["罐箱监测\n6-9亿美元\n增速10-15%", "其他中端\n(ATG/危化品)", "外资高端大项目"]
    colors = [C_GREEN, C_ACCENT, C_GRAY]
    ax2.pie(seg, labels=labels, colors=colors, autopct="%d%%",
            startangle=90, textprops={"fontsize": 15}, explode=(0.05, 0, 0))
    ax2.set_title("全球油位细分结构（约）", fontsize=20, fontweight="bold", pad=15)

    plt.tight_layout()
    out = OUT / "fig0a_market_overview.png"
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print("✅", out)


def fig0b_opportunity_chain():
    """图0b 承接久通机会逻辑链——横向箭头链，大字。"""
    fig, ax = plt.subplots(figsize=(16, 4.5))
    fig.patch.set_facecolor("white")
    ax.axis("off")

    steps = [
        ("久通\n80国渠道", C_MAIN),
        ("+我方\n制造/认证", C_GREEN),
        ("→ 油位\n市场入口", C_ACCENT),
        ("→ 罐箱\n一体化", C_GREEN),
        ("→ 物位\n大类延伸", C_MAIN),
    ]
    box_w, box_h = 0.18, 0.5
    y = 0.5
    for i, (label, color) in enumerate(steps):
        x0 = 0.03 + i * 0.19
        ax.add_patch(plt.Rectangle((x0, y - box_h / 2), box_w, box_h,
                                   facecolor=color, edgecolor="white", alpha=0.9))
        ax.text(x0 + box_w / 2, y, label, ha="center", va="center",
                fontsize=15, color="white", fontweight="bold")
        if i < len(steps) - 1:
            ax.annotate("", xy=(x0 + box_w + 0.01, y), xytext=(x0 + box_w - 0.005, y),
                        arrowprops=dict(arrowstyle="->", color="black", lw=2.5))

    ax.text(0.5, 0.06, "承接久通生产 = 以代工为起点，换取「制造+渠道」协同的战略入口",
            ha="center", fontsize=17, color=C_MAIN, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    plt.tight_layout()
    out = OUT / "fig0b_opportunity_chain.png"
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print("✅", out)


def fig12_bridge():
    """图12 推导总桥——7步桥：市场→可竞争→份额→收入→毛利→成本→NPV。"""
    fig, ax = plt.subplots(figsize=(16, 5.5))
    fig.patch.set_facecolor("white")
    ax.axis("off")

    steps = [
        ("① 全球市场\n46→65亿美元", C_MAIN),
        ("② 中国可竞争\n40-50亿元", C_ACCENT),
        ("③ 罐箱细分\n6-9亿美元(15%)", C_GREEN),
        ("④ 渠道可及\n久通80国", C_MAIN),
        ("⑤ 基准收入\n曲线", C_ACCENT),
        ("⑥ 毛利40-50%\n→净贡献", C_GREEN),
        ("⑦ NPV 3116万\nIRR 57%", "#7b1fa2"),
    ]
    n = len(steps)
    box_w, box_h = 0.115, 0.42
    y = 0.62
    for i, (label, color) in enumerate(steps):
        x0 = 0.02 + i * (0.96 - box_w) / (n - 1)
        ax.add_patch(plt.Rectangle((x0, y - box_h / 2), box_w, box_h,
                                   facecolor=color, edgecolor="white", alpha=0.92))
        ax.text(x0 + box_w / 2, y, label, ha="center", va="center",
                fontsize=12.5, color="white", fontweight="bold")
        if i < n - 1:
            ax.annotate("", xy=(x0 + box_w + 0.005, y), xytext=(x0 + box_w - 0.002, y),
                        arrowprops=dict(arrowstyle="->", color="black", lw=2))

    # 底部敏感性注记
    ax.text(0.5, 0.22, "关键变量敏感性：毛利率 + 罐箱渗透率 驱动项目价值约80%",
            ha="center", fontsize=16, color="#7b1fa2", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#f3e5f5", edgecolor="#7b1fa2"))
    ax.text(0.5, 0.08, "三情景加权NPV ≈ +3,200万元  |  最坏敞口 ≈ 2,100万元  |  止损线 2,450万元",
            ha="center", fontsize=13, color=C_GRAY)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    plt.tight_layout()
    out = OUT / "fig12_bridge.png"
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print("✅", out)


if __name__ == "__main__":
    fig0a_market_overview()
    fig0b_opportunity_chain()
    fig12_bridge()
    print("全部图表生成完成")
