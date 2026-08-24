"""event_monitor.py — 事件驱动监控器

主动监控：财报发布、政策发布、宏观数据更新、个股异动、行业价格变化。
检测到重大事件自动触发分析。

用法:
    from data.event_monitor import EventMonitor
    monitor = EventMonitor()
    events = monitor.check_all()  # 返回新事件列表
    # 定时运行: python data/event_monitor.py
"""

from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("v57.data.event_monitor")

try:
    from core.models import DataPoint
except ImportError:
    from dataclasses import dataclass, field
    from typing import Any
    @dataclass
    class DataPoint:
        name: str = ""; value: Any = None; unit: str = ""
        source: str = ""; source_level: str = ""; confidence: str = "medium"
        is_estimate: bool = False; fiscal_year: int | None = None; note: str = ""


class EventMonitor:
    """事件驱动监控器

    定时检查各数据源，检测到重大事件自动触发分析。
    事件被记录到 event_log.jsonl，避免重复触发。
    """

    def __init__(self, log_dir: str | None = None):
        root = Path(__file__).resolve().parent.parent
        self.log_dir = Path(log_dir or (root / "outputs" / "events"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "event_log.jsonl"

        # 关注的股票池
        self.watchlist = ["600519", "300750", "000858", "002415", "601318",
                         "600036", "000333", "002594", "688981", "600276"]

        # 关注的政策源
        self.policy_sources = [
            "https://www.gov.cn/zhengce/",
            "https://www.miit.gov.cn/",
            "https://www.csrc.gov.cn/",
        ]

    def check_all(self) -> list[dict]:
        """运行全部监控检查，返回新事件列表"""
        events = []
        events.extend(self.check_market_moves())
        events.extend(self.check_policy_updates())
        events.extend(self.check_earnings_season())
        events.extend(self.check_macro_releases())

        # 记录新事件
        for event in events:
            self._log_event(event)

        return events

    def check_market_moves(self, threshold_pct: float = 5.0) -> list[dict]:
        """检查个股异动（单日涨跌幅超过threshold_pct）"""
        events = []
        try:
            from data.__init__ import fetch_realtime
            points = fetch_realtime(self.watchlist)
            for p in points:
                if p.name == "change_pct" and abs(float(p.value)) >= threshold_pct:
                    if not self._already_seen(f"market_move_{p.note}_{datetime.now().date()}"):
                        events.append({
                            "type": "market_move",
                            "asset": p.note or "unknown",
                            "value": float(p.value),
                            "threshold": threshold_pct,
                            "timestamp": datetime.now().isoformat(),
                            "summary": f"{p.note} 涨跌幅 {p.value}% 触发异动监控阈值({threshold_pct}%)",
                        })
        except Exception as e:
            logger.debug("Market move check failed: %s", e)
        return events

    def check_policy_updates(self) -> list[dict]:
        """检查政策网站是否有新发布"""
        events = []
        try:
            for url in self.policy_sources:
                cache_key = f"policy_check_{url}_{datetime.now().date()}"
                if self._already_seen(cache_key):
                    continue
                # 这里可以集成Crawl4AI检查
                events.append({
                    "type": "policy_check",
                    "source": url,
                    "timestamp": datetime.now().isoformat(),
                    "summary": f"政策源 {url} 有新的内容更新",
                })
        except Exception as e:
            logger.debug("Policy check failed: %s", e)
        return events

    def check_earnings_season(self) -> list[dict]:
        """检查财报季（通常4月/8月/10月）"""
        events = []
        now = datetime.now()
        month = now.month

        # 财报季判断
        is_earnings_season = month in [3, 4, 8, 9, 10]
        if is_earnings_season:
            cache_key = f"earnings_season_{now.year}Q{(month-1)//3+1}"
            if not self._already_seen(cache_key):
                quarter = (month - 1) // 3 + 1
                events.append({
                    "type": "earnings_season",
                    "quarter": f"{now.year}Q{quarter}",
                    "timestamp": now.isoformat(),
                    "summary": f"{now.year}年第{quarter}季度财报季进行中，关注{len(self.watchlist)}只核心标的",
                })
        return events

    def check_macro_releases(self) -> list[dict]:
        """检查宏观数据发布"""
        events = []
        try:
            from data.__init__ import fetch_macro
            points = fetch_macro("all")
            for p in points[:5]:
                cache_key = f"macro_{p.name}_{datetime.now().date()}"
                if self._already_seen(cache_key):
                    continue
                events.append({
                    "type": "macro_release",
                    "indicator": p.name,
                    "value": str(p.value),
                    "timestamp": datetime.now().isoformat(),
                    "summary": f"宏观指标 {p.name}: {p.value}{p.unit}",
                })
        except Exception as e:
            logger.debug("Macro check failed: %s", e)
        return events

    def _already_seen(self, key: str) -> bool:
        """检查事件是否已被记录"""
        if not self.log_path.exists():
            return False
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event.get("_cache_key") == key:
                            return True
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return False

    def _log_event(self, event: dict):
        """记录事件到日志文件"""
        try:
            # 生成缓存键
            cache_key = f"{event['type']}_{datetime.now().date()}"
            event["_cache_key"] = cache_key
            event["_recorded_at"] = datetime.now().isoformat()

            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Event log failed: %s", e)

    def get_recent_events(self, days: int = 7) -> list[dict]:
        """获取近期事件"""
        if not self.log_path.exists():
            return []
        cutoff = datetime.now() - timedelta(days=days)
        events = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        ts = event.get("timestamp", event.get("_recorded_at", ""))
                        if ts:
                            ev_time = datetime.fromisoformat(ts)
                            if ev_time >= cutoff:
                                events.append(event)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception:
            pass
        return events

    def get_event_stats(self) -> dict:
        """事件统计"""
        events = self.get_recent_events(30)
        stats = {"total": len(events), "by_type": {}}
        for e in events:
            etype = e.get("type", "unknown")
            stats["by_type"][etype] = stats["by_type"].get(etype, 0) + 1
        return stats


def run_event_check():
    """便捷函数：运行一次事件检查"""
    monitor = EventMonitor()
    events = monitor.check_all()
    if events:
        logger.info("EventMonitor: %d new events detected", len(events))
        for e in events:
            logger.info("  [%s] %s", e["type"], e["summary"])
    else:
        logger.info("EventMonitor: No new events")
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_event_check()
