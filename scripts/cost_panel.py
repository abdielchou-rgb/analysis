"""S7-3: 成本面板

聚合 ObservabilityDB.cost_audit：
- 每报告 token/成本/耗时
- 按模块/通道分布
- 输出 output/cost_panel_<date>.md + 成本超支告警
"""

from __future__ import annotations

import json
import logging
import sqlite3
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
logger = logging.getLogger("cost_panel")

OUTPUT_DIR = _ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 成本告警阈值
COST_ALERT_THRESHOLDS = {
    "max_tokens_per_report": 100000,
    "max_cost_per_report": 5.0,  # USD
    "max_latency_per_report": 300,  # seconds
}


def _query_observability_db(query: str, params: tuple = ()) -> list[dict]:
    """查询 ObservabilityDB。"""
    db_path = _ROOT / "core" / "data" / "observability.db"
    if not db_path.exists():
        db_path = _ROOT / "data" / "observability.db"
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.debug("查询 ObservabilityDB 失败: %s", e)
        return []


def get_cost_summary() -> dict:
    """获取成本汇总。"""
    # LLM 调用统计
    llm_stats = _query_observability_db("""
        SELECT
            COUNT(*) as total_calls,
            SUM(prompt_tokens) as total_prompt_tokens,
            SUM(completion_tokens) as total_completion_tokens,
            AVG(prompt_tokens + completion_tokens) as avg_tokens_per_call,
            AVG(latency_ms) as avg_latency_ms,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count
        FROM llm_call_log
    """)

    # 按模块分布
    by_module = _query_observability_db("""
        SELECT
            module,
            COUNT(*) as calls,
            SUM(prompt_tokens + completion_tokens) as total_tokens,
            AVG(latency_ms) as avg_latency
        FROM llm_call_log
        GROUP BY module
        ORDER BY total_tokens DESC
    """)

    # 按通道分布
    by_provider = _query_observability_db("""
        SELECT
            provider,
            COUNT(*) as calls,
            SUM(prompt_tokens + completion_tokens) as total_tokens,
            AVG(latency_ms) as avg_latency
        FROM llm_call_log
        GROUP BY provider
    """)

    return {
        "llm": llm_stats[0] if llm_stats else {},
        "by_module": by_module,
        "by_provider": by_provider,
    }


def check_cost_alerts(summary: dict) -> list[dict]:
    """检查成本超支告警。"""
    alerts = []
    llm = summary.get("llm", {})

    total_tokens = (llm.get("total_prompt_tokens") or 0) + (llm.get("total_completion_tokens") or 0)
    total_calls = llm.get("total_calls") or 0
    avg_tokens = llm.get("avg_tokens_per_call") or 0
    error_count = llm.get("error_count") or 0

    if avg_tokens > COST_ALERT_THRESHOLDS["max_tokens_per_report"]:
        alerts.append({
            "type": "high_tokens",
            "message": f"平均 token 数 {avg_tokens:.0f} 超过阈值 {COST_ALERT_THRESHOLDS['max_tokens_per_report']}",
            "severity": "warning",
        })

    if total_calls > 0 and error_count / total_calls > 0.1:
        alerts.append({
            "type": "high_error_rate",
            "message": f"LLM 错误率 {error_count/total_calls:.1%} 超过 10%",
            "severity": "critical",
        })

    for mod in summary.get("by_module", []):
        if mod.get("avg_latency", 0) > COST_ALERT_THRESHOLDS["max_latency_per_report"] * 1000:
            alerts.append({
                "type": "high_latency",
                "message": f"模块 {mod['module']} 平均延迟 {mod['avg_latency']:.0f}ms 过高",
                "severity": "warning",
            })

    return alerts


def generate_cost_panel_report() -> str:
    """生成成本面板报告。"""
    summary = get_cost_summary()
    alerts = check_cost_alerts(summary)

    llm = summary.get("llm", {})
    total_tokens = (llm.get("total_prompt_tokens") or 0) + (llm.get("total_completion_tokens") or 0)

    lines = [
        f"# 成本面板 {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## LLM 调用汇总",
        f"- 总调用次数: {llm.get('total_calls', 0)}",
        f"- 总 token 数: {total_tokens:,}",
        f"- 平均 token/次: {llm.get('avg_tokens_per_call', 0):,.0f}",
        f"- 平均延迟: {llm.get('avg_latency_ms', 0):,.0f}ms",
        f"- 错误次数: {llm.get('error_count', 0)}",
        "",
    ]

    if alerts:
        lines.append("## ⚠️ 告警")
        for a in alerts:
            lines.append(f"- [{a['severity']}] {a['message']}")
        lines.append("")

    if summary.get("by_module"):
        lines.append("## 按模块分布")
        lines.append("| 模块 | 调用次数 | 总 token | 平均延迟 |")
        lines.append("|------|---------|---------|---------|")
        for m in summary["by_module"]:
            lines.append(f"| {m.get('module', '')} | {m.get('calls', 0)} | {m.get('total_tokens', 0):,} | {m.get('avg_latency', 0):.0f}ms |")
        lines.append("")

    if summary.get("by_provider"):
        lines.append("## 按通道分布")
        lines.append("| 通道 | 调用次数 | 总 token | 平均延迟 |")
        lines.append("|------|---------|---------|---------|")
        for p in summary["by_provider"]:
            lines.append(f"| {p.get('provider', '')} | {p.get('calls', 0)} | {p.get('total_tokens', 0):,} | {p.get('avg_latency', 0):.0f}ms |")

    return "\n".join(lines)


def main():
    logger.info("=== 成本面板 ===")
    report = generate_cost_panel_report()
    report_file = OUTPUT_DIR / f"cost_panel_{datetime.now().strftime('%Y%m%d')}.md"
    report_file.write_text(report, encoding="utf-8")
    logger.info("成本面板: %s", report_file)
    print(report)


if __name__ == "__main__":
    main()
