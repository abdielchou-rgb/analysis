# -*- coding: utf-8 -*-
"""A-10 假设敏感性表模块。"""

from __future__ import annotations


def sensitivity_table(
    eps: float,
    pe_base: float,
    growth_rate: float,
    asset: str = "",
) -> str:
    """生成目标价假设敏感性矩阵（Markdown 表格）。

    对 EPS 和 PE 各 ±10%/±20% 变化，计算目标价的联动变化。
    帮助读者理解哪些假设对结论影响最大。
    """
    if eps <= 0 or pe_base <= 0:
        return ""
    base_tp = round(eps * pe_base, 2)

    pe_deltas = [-20, -10, 0, 10, 20]
    eps_deltas = [-20, -10, 0, 10, 20]

    lines = [
        "### 目标价敏感性分析",
        "",
        f"基准假设：EPS {eps}元 × PE {pe_base}x = 目标价 {base_tp} 元",
        f"（隐含增长率 {growth_rate}%，请关注哪个假设对结果影响最大）",
        "",
        f"| | PE {-20}%={pe_base * 0.8:.0f}x | PE {-10}%={pe_base * 0.9:.0f}x | PE 基准={pe_base:.0f}x | PE +10%={pe_base * 1.1:.0f}x | PE +20%={pe_base * 1.2:.0f}x |",
        "|---|---|---|---|---|---|",
    ]
    for ed in eps_deltas:
        e_adj = eps * (1 + ed / 100)
        row = f"| EPS {'-' if ed < 0 else '+'}{abs(ed)}%={e_adj:.2f}元 |"
        for pd in pe_deltas:
            p_adj = pe_base * (1 + pd / 100)
            tp = round(e_adj * p_adj, 1)
            deviation = (tp / base_tp - 1) * 100
            sign = "+" if deviation >= 0 else ""
            row += f" {tp}{sign}{deviation:.0f}% |"
        lines.append(row)

    lines += [
        "",
        f"> 敏感性说明：EPS ±10% 对目标价影响 {abs(eps * 1.1 * pe_base - base_tp) / base_tp * 100:.0f}%；"
        f"PE ±10% 影响约 10%。当前估值的核心风险在于 EPS 预测的准确度。",
    ]
    return "\n".join(lines)
