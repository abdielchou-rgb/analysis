"""pipe_dashboard.py — 数据管道可观测性仪表盘

实时监控每个数据源的健康状态、延迟、成功率。
输出格式化的CLI报告，也可作为Grafana的数据源。

用法:
    from data.pipe_dashboard import PipelineDashboard
    dashboard = PipelineDashboard()
    dashboard.show()  # CLI输出
    dashboard.report()  # 返回结构化数据
"""

from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread
from typing import Any, Optional

logger = logging.getLogger("v57.data.dashboard")

try:
    from data.acquisition.framework import orchestrator
    _HAS_ACQUISITION = True
except ImportError:
    _HAS_ACQUISITION = False

try:
    from data.cache_manager import persistent_cache
    _HAS_CACHE = True
except ImportError:
    _HAS_CACHE = False


class PipelineDashboard:
    """数据管道仪表盘"""

    def __init__(self, log_path: str | None = None):
        if log_path is None:
            root = Path(__file__).resolve().parent.parent
            log_path = str(root / "data" / "pipeline_stats.jsonl")
        self.log_path = log_path

    def collect_stats(self) -> dict:
        """采集当前管道统计"""
        stats = {
            "timestamp": datetime.now().isoformat(),
            "sources": {},
            "cache": {},
            "summary": {},
        }

        # 数据源健康
        if _HAS_ACQUISITION:
            stats["sources"] = orchestrator.health_report()

        # 缓存统计
        if _HAS_CACHE:
            try:
                cache_stats = persistent_cache.stats()
                stats["cache"] = {
                    "total_entries": cache_stats.get("total_entries", 0),
                    "active_entries": cache_stats.get("active_entries", 0),
                    "by_type": cache_stats.get("by_type", {}),
                }
            except Exception:
                stats["cache"] = {"error": "unavailable"}

        # 汇总
        sources = stats["sources"]
        total = len(sources)
        healthy = sum(1 for s in sources.values() if s.get("status") == "healthy")
        degraded = sum(1 for s in sources.values() if s.get("status") == "degraded")
        down = sum(1 for s in sources.values() if s.get("status") == "down")
        
        stats["summary"] = {
            "total_sources": total,
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "health_score": round(healthy / max(total, 1) * 100, 1),
        }

        return stats

    def log_stats(self):
        """记录统计数据到日志文件"""
        stats = self.collect_stats()
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(stats, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Dashboard log failed: %s", e)
        return stats

    def get_history(self, hours: int = 24) -> list[dict]:
        """获取历史统计数据"""
        if not os.path.exists(self.log_path):
            return []
        cutoff = datetime.now() - timedelta(hours=hours)
        history = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp", "")
                        if ts:
                            et = datetime.fromisoformat(ts)
                            if et >= cutoff:
                                history.append(entry)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass
        return history

    def show(self):
        """CLI输出仪表盘"""
        stats = self.log_stats()
        
        print()
        print("=" * 60)
        print("  1号分析师 数据管道健康度")
        print(f"  {stats['timestamp']}")
        print("=" * 60)
        
        # 摘要
        s = stats["summary"]
        score_color = "🟢" if s["health_score"] >= 80 else ("🟡" if s["health_score"] >= 50 else "🔴")
        print(f"  健康总分: {score_color} {s['health_score']}%")
        print(f"  数据源: {s['total_sources']}总 / {s['healthy']}健康 / {s['degraded']}降级 / {s['down']}宕机")
        print()
        
        # 各源状态
        print("  ── 源健康详情 ──")
        for name, health in sorted(stats["sources"].items()):
            status = health.get("status", "unknown")
            icon = {"healthy": "🟢", "degraded": "🟡", "down": "🔴", "unknown": "⚪"}.get(status, "⚪")
            failures = health.get("consecutive_failures", 0)
            latency = health.get("avg_latency_ms", 0)
            cb = health.get("circuit_breaker", "closed")
            cb_icon = "🔓" if cb == "open" else "🔒"
            print(f"  {icon} {name:20s} | 失败{failures:2d}次 | {latency:6.1f}ms | {cb_icon}")
        
        print()
        
        # 缓存状态
        if stats.get("cache"):
            c = stats["cache"]
            if "error" not in c:
                by_type = c.get("by_type", {})
                type_str = ", ".join(f"{k}:{v}" for k, v in sorted(by_type.items())[:5])
                print(f"  ── 缓存状态 ──")
                print(f"  活跃条目: {c['active_entries']} / 总条目: {c['total_entries']}")
                if type_str:
                    print(f"  按类型: {type_str}")
        
        print()
        print("=" * 60)

    def report(self) -> dict:
        """返回结构化报告"""
        return self.collect_stats()


def show_dashboard():
    dashboard = PipelineDashboard()
    dashboard.show()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    show_dashboard()
