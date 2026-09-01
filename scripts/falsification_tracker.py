"""S3-4: 证伪追踪

提取报告 Bold Call 的 falsification conditions（已结构化）：
- 到期检查关键变量（如"毛利率跌破34%"→ 拉最新毛利率）
- 输出 output/falsification_check_<date>.md：每条件 满足/未满足/待查
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("falsification_tracker")

OUTPUT_DIR = _ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _load_forward_picks_with_falsification() -> list[dict]:
    """加载有证伪条件的 ForwardPick。"""
    from core.forward_picks import ForwardPicksDB

    db = ForwardPicksDB()
    picks = db.load_all()

    results = []
    for p in picks:
        if p.falsification and p.falsification.strip():
            results.append({
                "pick_id": p.pick_id,
                "asset": p.asset_code,
                "direction": p.direction,
                "falsification": p.falsification,
                "key_variable": p.key_variable,
                "core_thesis": p.core_thesis,
                "verification_status": p.verification_status,
                "created_at": p.created_at,
            })

    return results


def _parse_falsification_conditions(falsification_text: str) -> list[dict]:
    """解析证伪条件文本，提取可检查的条件。

    支持格式：
    - "毛利率跌破34%"
    - "营收连续2季下滑"
    - "管理层变动"
    - "净利润亏损"
    """
    conditions = []

    # 数值阈值条件
    patterns = [
        (r"(\w+?)(?:跌|降|低于|低于)(?:破|到)?(\d+\.?\d*)%", "threshold_below"),
        (r"(\w+?)(?:涨|升|高于|超过)(?:破|到)?(\d+\.?\d*)%", "threshold_above"),
        (r"(\w+?)(?:连续)(\d+)(?:季|年)(?:下滑|下降|亏损)", "consecutive_decline"),
        (r"(\w+?)(?:亏损|为负)", "negative_value"),
    ]

    for pattern, cond_type in patterns:
        matches = re.finditer(pattern, falsification_text)
        for m in matches:
            groups = m.groups()
            conditions.append({
                "raw": m.group(0),
                "type": cond_type,
                "variable": groups[0] if groups else "",
                "threshold": groups[1] if len(groups) > 1 else "",
                "status": "pending",
            })

    if not conditions:
        # 无法解析的条件，标记为待人工检查
        conditions.append({
            "raw": falsification_text[:100],
            "type": "unparsed",
            "variable": "",
            "threshold": "",
            "status": "pending",
        })

    return conditions


def check_falsification(conditions: list[dict], asset_code: str) -> list[dict]:
    """检查证伪条件是否触发。"""
    for cond in conditions:
        if cond["status"] != "pending":
            continue

        if cond["type"] == "unparsed":
            cond["status"] = "needs_manual_review"
            cond["note"] = "无法自动解析，需人工检查"
            continue

        # 尝试获取最新财务数据
        try:
            from core.data_backends import get_financial_data
            fin_data = get_financial_data(asset_code)
            if not fin_data:
                cond["status"] = "unavailable"
                cond["note"] = "无法获取最新财务数据"
                continue

            variable = cond["variable"]
            threshold = float(cond["threshold"]) if cond["threshold"] else 0

            # 简单匹配变量名
            latest_value = None
            for key, val in fin_data.items():
                if variable in key and isinstance(val, (int, float)):
                    latest_value = val
                    break

            if latest_value is None:
                cond["status"] = "unavailable"
                cond["note"] = f"未找到变量「{variable}」"
                continue

            if cond["type"] == "threshold_below":
                if latest_value < threshold:
                    cond["status"] = "triggered"
                    cond["note"] = f"{variable}={latest_value:.1f} < {threshold}%"
                else:
                    cond["status"] = "not_triggered"
                    cond["note"] = f"{variable}={latest_value:.1f} >= {threshold}%"

            elif cond["type"] == "threshold_above":
                if latest_value > threshold:
                    cond["status"] = "triggered"
                    cond["note"] = f"{variable}={latest_value:.1f} > {threshold}%"
                else:
                    cond["status"] = "not_triggered"
                    cond["note"] = f"{variable}={latest_value:.1f} <= {threshold}%"

        except Exception as e:
            cond["status"] = "error"
            cond["note"] = str(e)

    return conditions


def generate_falsification_report() -> str:
    """生成证伪追踪报告。"""
    picks = _load_forward_picks_with_falsification()

    if not picks:
        return f"# 证伪追踪报告 {datetime.now().strftime('%Y-%m-%d')}\n\n无带证伪条件的预测。"

    lines = [
        f"# 证伪追踪报告 {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"总计 {len(picks)} 条带证伪条件的预测",
        "",
    ]

    triggered_count = 0
    pending_count = 0

    for pick in picks:
        conditions = _parse_falsification_conditions(pick["falsification"])
        conditions = check_falsification(conditions, pick["asset"])

        lines.append(f"## {pick['asset']} ({pick['direction']})")
        lines.append(f"- 状态: {pick['verification_status']}")
        lines.append(f"- 核心论点: {pick['core_thesis'][:80]}")
        lines.append(f"- 证伪条件:")

        for cond in conditions:
            status_mark = {
                "triggered": "❌ 已触发",
                "not_triggered": "✅ 未触发",
                "pending": "⏳ 待查",
                "unavailable": "❓ 数据不可用",
                "needs_manual_review": "🔍 需人工",
                "error": "⚠️ 检查失败",
            }.get(cond["status"], cond["status"])

            lines.append(f"  - {status_mark}: {cond['raw']}")
            if cond.get("note"):
                lines.append(f"    {cond['note']}")

            if cond["status"] == "triggered":
                triggered_count += 1
            elif cond["status"] == "pending":
                pending_count += 1

        lines.append("")

    lines.extend([
        "## 汇总",
        f"- 已触发: {triggered_count}",
        f"- 待查: {pending_count}",
    ])

    return "\n".join(lines)


def main():
    logger.info("=== 证伪追踪 ===")
    report = generate_falsification_report()
    report_file = OUTPUT_DIR / f"falsification_check_{datetime.now().strftime('%Y%m%d')}.md"
    report_file.write_text(report, encoding="utf-8")
    logger.info("证伪报告: %s", report_file)
    print(report)


if __name__ == "__main__":
    main()
