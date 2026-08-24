# Data Feeds Pipeline Node — 将RSS/PDF/专利/推断 接入管线

from __future__ import annotations
import logging, json
from pathlib import Path
from core.data_feeds import (
    _feeds, collect_industry_news, scan_local_reports,
    search_patents, infer_company_basics,
)
from core.pw_collector import batch_extract_reports, extract_xueqiu_sentiment
from core.extra_collectors import collect_all_extra

logger = logging.getLogger("2hao.data_feeds_node")


def run_all_feeds(asset: str = "", industry: str = "",
                  asset_code: str = "") -> dict:
    """运行所有数据Feed，返回聚合结果"""
    context = {}

    # 1. 行业新闻 RSS/Web
    news = collect_industry_news(industry) if industry else []
    if news:
        context["feed_news"] = [n["title"] for n in news[:10]]
        context["feed_news_raw"] = news[:10]
        logger.info("Feed news: %d items", len(news))

    # 2. 本地报告扫描
    reports = batch_extract_reports(max_files=20)
    if reports:
        context["feed_reports"] = reports[:20]
        context["feed_report_count"] = len(reports)
        # 提取最近报告
        target_reports = [r for r in reports if r.get("company_guess", "").lower() in asset.lower()]
        if target_reports:
            context["feed_target_reports"] = target_reports[:5]
            logger.info("Feed reports: %d relevant to %s", len(target_reports), asset)

    # 3. 公司基本面推断
    basics = infer_company_basics(asset, industry)
    if basics:
        context["feed_basics"] = basics
        logger.info("Feed basics: %s %s", basics.get("ownership","?"), basics.get("board","?"))

    # 4. 专利搜索
    patents = search_patents(asset[:10])
    if patents and patents.get("patent_count", 0) > 0:
        context["feed_patents"] = patents
        logger.info("Feed patents: %d for %s", patents["patent_count"], asset[:10])


    # 5. Extra collectors (Xueqiu + job signals)
    extra = collect_all_extra(asset, asset_code, industry)
    if extra:
        context["extra_sentiment"] = extra.get("xueqiu", {})
        context["extra_jobs"] = extra.get("job_signals", {})
        logger.info("Extra: xueqiu=%s jobs=%s",
                    "Y" if extra.get("xueqiu") else "N",
                    "Y" if extra.get("job_signals") else "N")

    return context


def data_feeds_node(node_id: str, context: dict) -> dict:
    """E2E Pipeline Node — 在数据采集后运行，产出 merge 进 collected_data

    修复（2026-08-01 审计）：原实现把 feed_* 只写 context 顶层，而下游
    section_writer._build_data_bundle 只消费 collected_data → feeds 数据断线。
    现改为写入 collected_data["feed_*"]，供 bundle live 层消费。
    """
    asset = context.get("asset", "")
    industry = ""
    biz = context.get("biz_model")
    if biz and hasattr(biz, "industry_tags") and biz.industry_tags:
        industry = biz.industry_tags[0]
    elif asset:
        # 从行业分类器推断
        from core.tools.business_model_classifier import classify_by_text
        biz = classify_by_text(asset, "?")
        if biz.industry_tags:
            industry = biz.industry_tags[0]

    # 提取股票代码
    import re
    code_match = re.search(r"(\d{6})", asset)
    asset_code = code_match.group(1) if code_match else ""

    ctx = run_all_feeds(asset, industry, asset_code)
    context.update(ctx)
    context["feeds_loaded"] = True

    # 修复：把 feed 产出合并进 collected_data，让下游 bundle 能消费
    collected = context.get("collected_data")
    if not isinstance(collected, dict):
        collected = {}
    for k in ("feed_news", "feed_news_raw", "feed_reports", "feed_report_count",
              "feed_target_reports", "feed_basics", "feed_patents",
              "extra_sentiment", "extra_jobs"):
        if k in ctx:
            collected[k] = ctx[k]
    context["collected_data"] = collected

    logger.info("DataFeeds node: asset=%s industry=%s feeds=%d merged=%d",
                asset, industry, len(ctx), len([k for k in ctx if k.startswith("feed_") or k.startswith("extra_")]))
    return ctx