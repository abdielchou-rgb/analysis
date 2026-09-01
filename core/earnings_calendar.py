"""S2-2: 财报日历驱动

基于 akshare 获取财报披露日历，判断是否在财报窗口内。
接线：data_collector 采集时若命中财报窗口，写作 prompt 注入"注意最新财报"。
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("earnings_calendar")

CALENDAR_CACHE = _ROOT / "data" / "financial_calendar.json"


def _load_cache() -> dict:
    if CALENDAR_CACHE.exists():
        with open(CALENDAR_CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(data: dict):
    CALENDAR_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CALENDAR_CACHE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def refresh_calendar(codes: list[str] | None = None) -> dict:
    """从 akshare 刷新财报披露日历。

    Returns:
        {code: {"next_report_date": str, "report_type": str, ...}}
    """
    try:
        import akshare as ak
    except ImportError:
        logger.warning("akshare 未安装，跳过财报日历刷新")
        return {}

    result = {}
    try:
        # 获取 A 股财报预约披露时间
        df = ak.stock_financial_report_em()
        if df is None or df.empty:
            return {}

        for _, row in df.iterrows():
            code = str(row.get("股票代码", ""))
            if codes and code not in codes:
                continue

            report_date = str(row.get("预约披露时间", ""))
            report_type = str(row.get("报告类型", ""))

            if code and report_date:
                result[code] = {
                    "next_report_date": report_date,
                    "report_type": report_type,
                    "refreshed_at": datetime.now().isoformat(),
                }

        logger.info("刷新财报日历: %d 条", len(result))
    except Exception as e:
        logger.warning("刷新财报日历失败: %s", e)

    if result:
        cache = _load_cache()
        cache.update(result)
        _save_cache(cache)

    return result


def next_earnings_date(code: str) -> str | None:
    """获取指定标的的下次财报披露日期。

    Returns:
        YYYY-MM-DD 字符串，无数据返回 None
    """
    cache = _load_cache()
    entry = cache.get(code)
    if not entry:
        return None

    date_str = entry.get("next_report_date", "")
    if not date_str:
        return None

    # 解析日期（支持多种格式）
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(date_str[:10], fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str[:10] if date_str else None


def is_earnings_window(code: str, report_start: str, report_end: str | None = None) -> bool:
    """判断指定标的是否在财报窗口内（报告覆盖期内有财报发布）。

    Args:
        code: 股票代码
        report_start: 报告起始日期 YYYY-MM-DD
        report_end: 报告结束日期 YYYY-MM-DD（默认今天）
    Returns:
        True = 在窗口内（需注意最新财报）
    """
    next_date = next_earnings_date(code)
    if not next_date:
        return False

    try:
        dt = datetime.fromisoformat(next_date)
        start = datetime.fromisoformat(report_start)
        end = datetime.fromisoformat(report_end) if report_end else datetime.now()

        # 财报日在报告覆盖期内，或在未来 30 天内
        return start <= dt <= end or (start <= dt <= end + timedelta(days=30))
    except Exception:
        return False


def main():
    """刷新财报日历并输出摘要。"""
    logger.info("=== 财报日历刷新 ===")
    result = refresh_calendar()
    logger.info("刷新完成: %d 条", len(result))

    # 输出近期财报
    now = datetime.now()
    upcoming = []
    for code, info in result.items():
        next_date = info.get("next_report_date", "")
        if next_date:
            try:
                dt = datetime.strptime(next_date[:10], "%Y-%m-%d")
                if now <= dt <= now + timedelta(days=30):
                    upcoming.append((code, next_date, info.get("report_type", "")))
            except ValueError:
                pass

    if upcoming:
        logger.info("未来30天有财报披露: %d 家", len(upcoming))
        for code, date, rtype in upcoming[:10]:
            logger.info("  %s: %s (%s)", code, date, rtype)
    else:
        logger.info("未来30天无财报披露")


if __name__ == "__main__":
    main()
