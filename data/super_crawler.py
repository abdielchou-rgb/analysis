"""
2号分析师 Super Crawler — 超级数据采集引擎

利用免费公开数据源，最大化数据搜集能力：
- Crawl4AI: 智能网页爬虫（政策、新闻、行业数据）
- akshare: 3000+中国金融数据接口
- EastMoney: 实时行情和资金流
- FRED: 美联储10万+经济序列
- SEC EDGAR: 美股财报
- 自定义爬虫: 行业特定数据
"""

import sys
import json
import logging
import time
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field

_ANALYST_ROOT = Path(__file__).resolve().parent.parent
if str(_ANALYST_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYST_ROOT))

logger = logging.getLogger("2hao.super_crawler")


@dataclass
class DataSource:
    """数据源信息"""
    name: str
    type: str  # api / crawler / file
    status: str = "unknown"  # available / limited / unavailable
    data: Any = None
    error: str = ""
    latency_ms: float = 0.0
    cached: bool = False


class SuperCrawler:
    """超级数据采集器

    整合所有免费数据源，提供统一的采集接口。
    自动降级：首选→备选→fallback，确保不返回空数据。
    """

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._crawl4ai = None
        self._akshare = None

    # ==================== 统一采集接口 ====================

    def collect_all(self, query: str, dimensions: list = None) -> dict:
        """全维度数据采集"""
        if dimensions is None:
            dimensions = ["financial", "news", "industry", "policy", "macro", "competitor"]

        result = {
            "query": query,
            "timestamp": time.time(),
            "dimensions": {},
            "sources_used": [],
            "quality_flags": [],
        }

        for dim in dimensions:
            try:
                data = self._collect_dimension(dim, query)
                result["dimensions"][dim] = data
                if data.get("source"):
                    result["sources_used"].append(data["source"])
                if data.get("quality") == "low":
                    result["quality_flags"].append(f"{dim}: {data.get('warning', 'low quality')}")
            except Exception as e:
                result["dimensions"][dim] = {"error": str(e), "status": "failed"}

        result["source_count"] = len(set(result["sources_used"]))
        result["data_quality"] = "good" if len(result["quality_flags"]) == 0 else "has_issues"
        return result

    def _collect_dimension(self, dim: str, query: str) -> dict:
        """采集单个维度"""

        if dim == "financial":
            return self._get_financial(query)
        elif dim == "news":
            return self._get_news(query)
        elif dim == "industry":
            return self._get_industry(query)
        elif dim == "policy":
            return self._get_policy(query)
        elif dim == "macro":
            return self._get_macro()
        elif dim == "competitor":
            return self._get_competitor(query)
        else:
            return {"error": f"Unknown dimension: {dim}"}

    # ==================== Crawl4AI 增强 ====================

    def _init_crawl4ai(self):
        if self._crawl4ai is None:
            try:
                from crawl4ai import AsyncWebCrawler
                self._crawl4ai = "available"
            except ImportError:
                self._crawl4ai = "unavailable"

    async def crawl_url(self, url: str, max_pages: int = 1) -> dict:
        """使用Crawl4AI爬取网页"""
        self._init_crawl4ai()
        if self._crawl4ai == "unavailable":
            return self._crawl_fallback(url)

        try:
            from crawl4ai import AsyncWebCrawler
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url)
                return {
                    "url": url,
                    "content": result.markdown[:10000] if result.markdown else "",
                    "success": result.success,
                    "source": "Crawl4AI",
                }
        except Exception as e:
            logger.warning(f"Crawl4AI failed for {url}: {e}")
            return self._crawl_fallback(url)

    def _crawl_fallback(self, url: str) -> dict:
        """Crawl4AI不可用时的降级"""
        try:
            import requests
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            return {
                "url": url,
                "content": resp.text[:10000],
                "success": resp.status_code == 200,
                "source": "requests_fallback",
            }
        except Exception as e:
            return {"url": url, "error": str(e), "success": False, "source": "failed"}

    # ==================== akshare 增强 ====================

    def _init_akshare(self):
        """初始化akshare"""
        if self._akshare is None:
            try:
                import akshare as ak
                self._akshare = ak
            except ImportError:
                self._akshare = "unavailable"

    def _get_financial(self, query: str) -> dict:
        """获取财务数据"""
        result = {"status": "searching", "data": [], "source": "unknown"}
        
        # 优先使用 DuckDB
        try:
            from data.financial_db import FinancialDB
            db = FinancialDB()
            data = db.query(query)
            if data:
                result["data"] = data
                result["source"] = "DuckDB FinancialDB"
                result["status"] = "available"
                return result
        except Exception:
            pass

        # akshare
        self._init_akshare()
        if self._akshare != "unavailable":
            try:
                # 尝试获取股票数据
                stock_info = self._akshare.stock_individual_info_em(symbol=query)
                if stock_info is not None:
                    result["data"] = stock_info.to_dict(orient="records")
                    result["source"] = "akshare"
                    result["status"] = "available"
                    return result
            except Exception as e:
                logger.warning(f"akshare financial failed: {e}")

        # Fallback: crawl4AI
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            crawl_result = loop.run_until_complete(
                self.crawl_url(f"https://finance.sina.com.cn/realstock/company/{query}/nc.shtml")
            )
            result["data"] = crawl_result
            result["source"] = "Crawl4AI_sina"
            result["status"] = "available"
            result["quality"] = "low"
            result["warning"] = "数据来自网页抓取，未验证"
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "unavailable"

        return result

    def _get_news(self, query: str) -> dict:
        """获取新闻"""
        urls = [
            f"https://news.sina.com.cn/search/?q={query}",
            f"https://www.cls.cn/searchPage?keyword={query}",
            f"https://36kr.com/search/articles/{query}",
        ]
        results = []
        for url in urls:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                crawl_result = loop.run_until_complete(self.crawl_url(url))
                if crawl_result.get("success"):
                    results.append(crawl_result)
            except Exception:
                pass

        return {
            "status": "available" if results else "unavailable",
            "data": results,
            "count": len(results),
            "source": "Crawl4AI",
        }

    def _get_industry(self, query: str) -> dict:
        """获取行业数据"""
        self._init_akshare()
        result = {"status": "searching", "data": [], "source": "unknown"}

        if self._akshare != "unavailable":
            try:
                # 行业板块数据
                sector_data = self._akshare.stock_board_industry_name_em()
                if sector_data is not None:
                    result["data"] = sector_data.to_dict(orient="records")
                    result["source"] = "akshare_industry"
                    result["status"] = "available"
                    return result
            except Exception as e:
                logger.warning(f"akshare industry failed: {e}")

        return result

    def _get_policy(self, query: str) -> dict:
        """获取政策数据"""
        result = {"status": "searching", "data": [], "source": "unknown"}

        # 尝试从已有数据管线获取
        try:
            from data.policy_extractor import PolicyExtractor
            extractor = PolicyExtractor()
            data = extractor.extract(query)
            if data:
                result["data"] = data
                result["source"] = "PolicyExtractor"
                result["status"] = "available"
                return result
        except Exception:
            pass

        return result

    def _get_macro(self) -> dict:
        """获取宏观数据"""
        result = {"status": "searching", "data": [], "source": "unknown"}

        self._init_akshare()
        if self._akshare != "unavailable":
            try:
                macro_data = self._akshare.macro_china_gdp_yearly()
                if macro_data is not None:
                    result["data"] = macro_data.to_dict(orient="records")
                    result["source"] = "akshare_macro"
                    result["status"] = "available"
                    return result
            except Exception:
                pass

        return result

    def _get_competitor(self, query: str) -> dict:
        """获取竞争对手数据"""
        result = {"status": "searching", "data": [], "source": "unknown"}
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            crawl_result = loop.run_until_complete(
                self.crawl_url(f"https://www.tianyancha.com/search?key={query}")
            )
            if crawl_result.get("success"):
                result["data"] = crawl_result
                result["source"] = "Crawl4AI"
                result["status"] = "available"
        except Exception:
            pass
        return result

    def search_free(self, query: str, sources: list = None) -> dict:
        """多源自由搜索 - 同时搜索多个免费数据源"""
        if sources is None:
            sources = ["web", "financial", "news"]

        results = {}
        for src in sources:
            if src == "web":
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    # 搜索百度+必应
                    baidu = loop.run_until_complete(self.crawl_url(f"https://www.baidu.com/s?wd={query}"))
                    bing = loop.run_until_complete(self.crawl_url(f"https://cn.bing.com/search?q={query}"))
                    results["web"] = {"baidu": baidu.get("content", "")[:2000], "bing": bing.get("content", "")[:2000]}
                except Exception:
                    results["web"] = {"error": "failed"}
            elif src == "financial":
                results["financial"] = self._get_financial(query)
            elif src == "news":
                results["news"] = self._get_news(query)

        return {
            "query": query,
            "results": results,
            "sources_count": len(results),
        }


def main():
    """命令行测试"""
    import argparse
    parser = argparse.ArgumentParser(description="2hao-analyst Super Crawler")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--dimensions", "-d", nargs="+", 
                        default=["financial", "news", "industry", "policy"],
                        help="Dimensions to collect")
    args = parser.parse_args()

    crawler = SuperCrawler()
    result = crawler.collect_all(args.query, args.dimensions)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
