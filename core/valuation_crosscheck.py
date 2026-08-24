"""
估值锚交叉验证器（Valuation Crosscheck）— R30 模块8：对标投行三表→估值

**问题**：柯力报告 PE 65x vs 79.79x 矛盾、PE法40-48 vs DCF 51.6-57 取 48 无交代。
对标投行：多方法（DCF/可比/SOTP）交叉验证，单一结论，不并列矛盾。

**方案**：给定多估值锚，检查差异 >20% 时强制声明取值逻辑；差异小取中值。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("2hao.valuation_crosscheck")

_ROOT = Path(__file__).resolve().parent.parent

# 估值方法阈值：差异 >20% 需声明
GAP_THRESHOLD = 0.20


def crosscheck(valuations: dict) -> dict:
    """交叉验证多个估值锚。

    Args:
        valuations: {"DCF": 52.0, "PE": 45.0, "SOTP": 50.0, "可比": 48.0}

    Returns:
        {methods, values, gap_pct, passed, final, note}
    """
    # 过滤有效值
    valid = {k: float(v) for k, v in (valuations or {}).items() if v is not None and float(v) > 0}
    if len(valid) < 2:
        return {
            "methods": list((valuations or {}).keys()),
            "values": valuations or {},
            "gap_pct": 0,
            "passed": True,
            "final": list(valid.values())[0] if valid else 0,
            "note": "估值方法不足2个，无法交叉验证",
        }

    vmax = max(valid.values())
    vmin = min(valid.values())
    gap = (vmax - vmin) / vmin if vmin > 0 else 0
    passed = gap <= GAP_THRESHOLD

    if passed:
        final = sum(valid.values()) / len(valid)
        note = f"各估值锚差异{gap:.0%}，取均值 {final:.1f}"
    else:
        # 差异大：取中间值 + 声明
        sorted_v = sorted(valid.values())
        final = sorted_v[len(sorted_v) // 2]
        note = (
            f"估值锚差异{gap:.0%} > {GAP_THRESHOLD:.0%}，"
            f"正文必须声明取值逻辑。本验证取中值 {final:.1f}，"
            f"建议报告明确'采用X法因...'"
        )

    return {
        "methods": list(valid.keys()),
        "values": valid,
        "gap_pct": round(gap, 3),
        "passed": passed,
        "final": round(final, 1),
        "note": note,
    }


def serialize_crosscheck(cc: dict) -> str:
    """序列化注入 prompt。"""
    if not cc:
        return ""
    lines = ["=== 估值锚交叉验证（多方法一致性） ==="]
    for k, v in (cc.get("values") or {}).items():
        lines.append(f"  {k}: {v:.1f} 元")
    lines.append(f"差异: {cc.get('gap_pct', 0):.0%} → {'✅一致' if cc.get('passed') else '⚠️需声明取值逻辑'}")
    if cc.get("final"):
        lines.append(f"综合取值: {cc['final']} 元")
    lines.append(f"说明: {cc.get('note', '')}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 柯力场景：PE法 40-48 vs DCF 51.6-57
    cc = crosscheck({"DCF": 54.0, "PE": 44.0, "可比": 48.0})
    print(serialize_crosscheck(cc))
    print()
    # 一致场景
    cc2 = crosscheck({"DCF": 48.0, "PE": 46.0})
    print(serialize_crosscheck(cc2))
