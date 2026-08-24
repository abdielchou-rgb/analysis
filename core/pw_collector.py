# Playwright Deep Data Collector
# 处理BS4无法处理的JS渲染页面 + 定时监控任务

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("2hao.playwright_collector")

try:
    from playwright.sync_api import sync_playwright

    _HAS_PW = True
except ImportError:
    _HAS_PW = False


@dataclass
class PageContent:
    url: str = ""
    title: str = ""
    text: str = ""
    html_snippet: str = ""
    status_code: int = 0
    load_time_ms: float = 0.0
    error: str = ""


def launch_browser():
    """启动Playwright浏览器"""
    if not _HAS_PW:
        return None
    try:
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)
        return (p, browser)
    except Exception as e:
        logger.warning("PW launch: %s", e)
        return None


def close_browser(handle):
    """关闭浏览器"""
    if handle:
        try:
            p, browser = handle
            browser.close()
            p.stop()
        except Exception:
            pass


def fetch_page(url: str, timeout_ms: int = 15000) -> PageContent:
    """用Playwright抓取JS渲染页面"""
    result = PageContent(url=url)
    if not _HAS_PW:
        result.error = "Playwright not available"
        return result
    handle = launch_browser()
    if not handle:
        result.error = "Browser launch failed"
        return result
    p, browser = handle
    try:
        page = browser.new_page()
        t0 = time.time()
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        result.load_time_ms = (time.time() - t0) * 1000
        result.title = page.title()
        result.text = page.inner_text("body")[:8000]
        result.status_code = 200
        logger.info("PW fetch %s: %.0fms", url[:40], result.load_time_ms)
    except Exception as e:
        result.error = str(e)[:100]
        logger.debug("PW fetch %s: %s", url[:40], e)
    finally:
        close_browser(handle)
    return result


# ── 目标网站 ──────────────────────────────────────

TARGET_PAGES = {
    "xueqiu_stock": {
        "name": "雪球个股页",
        "url_template": "https://xueqiu.com/S/{code}",
        "description": "雪球讨论/热度/估值数据",
        "type": "investor_community",
    },
    "xueqiu_search": {
        "name": "雪球搜索",
        "url_template": "https://xueqiu.com/query?query={asset}",
        "description": "雪球相关讨论",
        "type": "investor_community",
    },
    "cls_telegraph": {
        "name": "财联社电报",
        "url_template": "https://www.cls.cn/telegraph",
        "description": "实时财经快讯",
        "type": "news",
    },
    "eastmoney_news": {
        "name": "东方财富个股新闻",
        "url_template": "https://so.eastmoney.com/news/s?keyword={asset}",
        "description": "个股新闻聚合",
        "type": "news",
    },
}


def collect_from_sites(asset: str = "", asset_code: str = "") -> dict:
    """从多个目标网站收集数据"""
    results = {}
    for site_id, config in TARGET_PAGES.items():
        url = config["url_template"]
        if "{code}" in url and asset_code:
            url = url.replace("{code}", asset_code[:6])
        elif "{asset}" in url and asset:
            url = url.replace("{asset}", asset)
        else:
            continue
        content = fetch_page(url)
        results[site_id] = {
            "url": url,
            "title": content.title,
            "text_preview": content.text[:500] if content.text else "",
            "error": content.error,
            "load_time_ms": content.load_time_ms,
        }
    return results


def extract_xueqiu_sentiment(text: str) -> dict:
    """从雪球文本提取情绪信号"""
    if not text:
        return {}
    sentiment = {"positive": 0, "negative": 0, "neutral": 0, "signals": []}
    pos_words = ["看好", "买入", "加仓", "低估", "成长", "突破", "利好", "反转"]
    neg_words = ["看空", "卖出", "减仓", "高估", "风险", "破位", "利空", "崩盘"]
    for word in pos_words:
        count = text.count(word)
        sentiment["positive"] += count
        if count > 0:
            sentiment["signals"].append(f"积极:{word}x{count}")
    for word in neg_words:
        count = text.count(word)
        sentiment["negative"] += count
        if count > 0:
            sentiment["signals"].append(f"消极:{word}x{count}")
    total = sentiment["positive"] + sentiment["negative"]
    if total > 0:
        sentiment["net_sentiment"] = round((sentiment["positive"] - sentiment["negative"]) / total, 2)
    return sentiment


# ── 批量报告解析 ──────────────────────────────────


def batch_extract_reports(max_files: int = 30) -> list[dict]:
    """批量从assets/reports/提取报告元数据"""
    from core.data_feeds import extract_report_metadata

    results = []
    root = Path(__file__).resolve().parent.parent
    report_dir = root / "assets" / "reports"
    if not report_dir.exists():
        return results
    for f in sorted(report_dir.rglob("*.pdf"))[:max_files]:
        meta = extract_report_metadata(f)
        if meta:
            results.append(meta)
    logger.info("Batch extract: %d/%d reports", len(results), max_files)
    return results
