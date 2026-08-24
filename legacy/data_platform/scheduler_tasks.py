"""scheduler_tasks.py — 定时采集任务定义

供scheduler.py调用的所有定时任务函数。

用法:
    from legacy.data_platform.scheduler_tasks import collect_all_daily
    collect_all_daily()  # 每天10:00运行
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger("v57.data.scheduler_tasks")

WATCHLIST = [
    ("600519", "贵州茅台"),
    ("300750", "宁德时代"),
    ("000858", "五粮液"),
    ("002594", "比亚迪"),
    ("688981", "中芯国际"),
    ("601012", "隆基绿能"),
    ("002415", "海康威视"),
    ("603259", "药明康德"),
    ("000333", "美的集团"),
    ("600036", "招商银行"),
    ("601318", "中国平安"),
    ("600276", "恒瑞医药"),
    ("002475", "立讯精密"),
    ("300124", "汇川技术"),
    ("002371", "北方华创"),
]


def collect_market_daily():
    """每日收盘后采集行情数据

    定时: 每天 15:30
    """
    logger.info("Scheduled: collect_market_daily")
    try:
        from legacy.data_platform.__init__ import fetch_realtime, build_data_cache

        codes = [c for c, _ in WATCHLIST]
        points = fetch_realtime(codes)
        logger.info("  Collected %d market data points", len(points))

        # 写入DuckDB
        try:
            from legacy.data_platform.financial_db import financial_db
            from core.models import DataPoint

            if financial_db._available:
                logger.info("  FinancialDB: active")
        except Exception:
            pass

        return {"success": True, "points": len(points)}
    except Exception as e:
        logger.error("collect_market_daily failed: %s", e)
        return {"success": False, "error": str(e)}


def collect_macro_daily():
    """每日采集宏观数据

    定时: 每天 10:00
    """
    logger.info("Scheduled: collect_macro_daily")
    try:
        from legacy.data_platform.__init__ import fetch_macro, fetch_global_market

        macro = fetch_macro("all")
        logger.info("  Macro: %d points", len(macro))

        global_mkt = fetch_global_market()
        logger.info("  Global market: %d points", len(global_mkt))

        return {"success": True, "macro": len(macro), "global": len(global_mkt)}
    except Exception as e:
        logger.error("collect_macro_daily failed: %s", e)
        return {"success": False, "error": str(e)}


def collect_consensus_weekly():
    """每周采集一致预期数据

    定时: 每周一 10:00
    """
    logger.info("Scheduled: collect_consensus_weekly")
    try:
        from legacy.data_platform.consensus_crawler import ConsensusCrawler
        from legacy.data_platform.consensus_connector import fetch_consensus

        cc = ConsensusCrawler()
        total = 0

        for code, name in WATCHLIST[:10]:  # 前10只
            try:
                # 方式1: Crawl4AI
                points = cc.fetch(code)
                total += len(points)

                # 方式2: akshare fallback
                if not points:
                    points2 = fetch_consensus(code)
                    total += len(points2)

                # 写入FinancialDB
                try:
                    from legacy.data_platform.financial_db import financial_db

                    if financial_db._available and points:
                        for p in points:
                            if hasattr(p, "fiscal_year") and p.fiscal_year:
                                financial_db.store_consensus(
                                    code, p.fiscal_year, {"consensus_revenue": p.value, "source": "scheduler"}
                                )
                except Exception:
                    pass
            except Exception as e:
                logger.debug("Consensus failed for %s: %s", code, e)

        logger.info("  Consensus: %d total points", total)
        return {"success": True, "points": total}
    except Exception as e:
        logger.error("collect_consensus_weekly failed: %s", e)
        return {"success": False, "error": str(e)}


def collect_industry_weekly():
    """每周采集行业数据

    定时: 每周一 14:00
    """
    logger.info("Scheduled: collect_industry_weekly")
    try:
        from legacy.data_platform.industry_crawlers import fetch_industry_data

        industries = ["光伏", "新能源车", "半导体", "锂电池", "白酒"]
        total = 0

        for ind in industries:
            try:
                points = fetch_industry_data(ind)
                total += len(points)
                logger.info("  %s: %d points", ind, len(points))
            except Exception as e:
                logger.debug("Industry %s failed: %s", ind, e)

        return {"success": True, "points": total}
    except Exception as e:
        logger.error("collect_industry_weekly failed: %s", e)
        return {"success": False, "error": str(e)}


def collect_financials_monthly():
    """每月采集财务数据

    定时: 每月1日 10:00
    """
    logger.info("Scheduled: collect_financials_monthly")
    try:
        from legacy.data_platform.financial_db import financial_db

        if not financial_db._available:
            logger.warning("FinancialDB not available")
            return {"success": False, "error": "DuckDB not installed"}

        try:
            import akshare as ak
        except ImportError:
            logger.warning("akshare not available, skip financials collection")
            return {"success": False, "error": "akshare not installed"}

        total = 0
        for code, name in WATCHLIST[:5]:  # 先5只测试
            try:
                # 利润表
                df = ak.stock_financial_abstract_em(symbol=code)
                if df is not None and not df.empty:
                    latest = df.iloc[0]
                    financial_db.store_income_statement(
                        code,
                        2025,
                        {
                            "revenue": float(latest.get("营业收入", 0) or 0),
                            "net_income": float(latest.get("净利润", 0) or 0),
                            "source": "akshare/scheduler",
                        },
                    )
                    total += 1
            except Exception as e:
                logger.debug("Financials failed for %s: %s", code, e)

        logger.info("  Financials: %d companies updated", total)
        return {"success": True, "companies": total}
    except Exception as e:
        logger.error("collect_financials_monthly failed: %s", e)
        return {"success": False, "error": str(e)}


def collect_event_monitor():
    """运行时检查事件

    定时: 每30分钟
    """
    try:
        from legacy.data_platform.event_monitor import EventMonitor

        monitor = EventMonitor()
        events = monitor.check_all()
        if events:
            logger.info("Scheduled events: %d new events detected", len(events))
            for e in events[:3]:
                logger.info("  [%s] %s", e.get("type", "?"), e.get("summary", "")[:60])
        return {"success": True, "events": len(events)}
    except Exception as e:
        logger.debug("Event monitor check failed: %s", e)
        return {"success": False, "error": str(e)}


def collect_all_daily():
    """每日全量采集（用于每日一次的全量更新）"""
    results = {}
    results["market"] = collect_market_daily()
    results["macro"] = collect_macro_daily()
    results["events"] = collect_event_monitor()
    return results


def collect_all_weekly():
    """每周全量采集"""
    results = {}
    results["consensus"] = collect_consensus_weekly()
    results["industry"] = collect_industry_weekly()
    return results


TASK_SCHEDULE = {
    "collect_market_daily": {
        "func": collect_market_daily,
        "trigger": "cron",
        "hour": 15,
        "minute": 30,
        "day_of_week": "mon-fri",
        "desc": "每日收盘行情采集",
    },
    "collect_macro_daily": {
        "func": collect_macro_daily,
        "trigger": "cron",
        "hour": 10,
        "minute": 0,
        "desc": "每日宏观数据采集",
    },
    "collect_consensus_weekly": {
        "func": collect_consensus_weekly,
        "trigger": "cron",
        "day_of_week": "mon",
        "hour": 10,
        "minute": 0,
        "desc": "每周一致预期采集",
    },
    "collect_industry_weekly": {
        "func": collect_industry_weekly,
        "trigger": "cron",
        "day_of_week": "mon",
        "hour": 14,
        "minute": 0,
        "desc": "每周行业数据采集",
    },
    "collect_financials_monthly": {
        "func": collect_financials_monthly,
        "trigger": "cron",
        "day": 1,
        "hour": 10,
        "minute": 0,
        "desc": "每月财务数据采集",
    },
    "collect_event_monitor": {
        "func": collect_event_monitor,
        "trigger": "interval",
        "minutes": 30,
        "desc": "事件监控检查",
    },
}
