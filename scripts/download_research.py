#!/usr/bin/env python
"""
Free Research Aggregator Scrapers — 免费研报平台批量下载

支持平台：
- 东方财富
- 同花顺
- 财联社
- 研报精选

注意：仅供个人学习/研究使用，请遵守各平台 robots.txt 和使用条款
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class EastmoneyScraper:
    """东方财富研报爬虫"""

    BASE_URL = "https://reportapi.eastmoney.com"
    LIST_API = "/report/list"
    DETAIL_API = "/report/detail"

    def __init__(self, session: aiohttp.ClientSession, output_dir: Path):
        self.session = session
        self.output_dir = output_dir / "eastmoney"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def search_reports(
        self, keyword: str = "", org_code: str = "", rating: str = "", page: int = 1, page_size: int = 50
    ) -> List[dict]:
        """搜索研报列表"""
        params = {
            "cb": "callback",
            "industryCode": "*",
            "rating": rating or "*",
            "ratingChange": "*",
            "beginTime": (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d"),
            "endTime": datetime.now().strftime("%Y-%m-%d"),
            "pageSize": str(page_size),
            "pageNo": str(page),
            "qType": "1",
        }
        if org_code:
            params["orgCode"] = org_code
        if keyword:
            params["keyword"] = keyword

        url = f"{self.BASE_URL}{self.LIST_API}?{urlencode(params)}"

        try:
            headers = {
                "Referer": "https://data.eastmoney.com/report/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            async with self.session.get(url, headers=headers) as resp:
                text = await resp.text()
                # 东财返回 JSONP
                match = re.search(r"callback\((.*)\)", text)
                if match:
                    data = json.loads(match.group(1))
                    return data.get("data", [])
        except Exception as e:
            print(f"  [Eastmoney] Search error: {e}")
        return []

    async def get_report_detail(self, info_code: str) -> Optional[dict]:
        """获取研报详情（含 PDF 链接）"""
        url = f"{self.BASE_URL}{self.DETAIL_API}?infoCode={info_code}&cb=callback"
        try:
            headers = {"Referer": "https://data.eastmoney.com/report/"}
            async with self.session.get(url, headers=headers) as resp:
                text = await resp.text()
                match = re.search(r"callback\((.*)\)", text)
                if match:
                    data = json.loads(match.group(1))
                    return data.get("data", {})
        except Exception as e:
            print(f"  [Eastmoney] Detail error for {info_code}: {e}")
        return None

    async def download_pdf(self, pdf_url: str, filename: str) -> Optional[Path]:
        """下载 PDF"""
        filepath = self.output_dir / filename
        if filepath.exists():
            return filepath

        try:
            headers = {"Referer": "https://data.eastmoney.com/"}
            async with self.session.get(pdf_url, headers=headers) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    filepath.write_bytes(content)
                    print(f"    ✓ {filename}")
                    return filepath
        except Exception as e:
            print(f"    ✗ {filename}: {e}")
        return None


class TonghuashunScraper:
    """同花顺研报爬虫"""

    BASE_URL = "https://stock.10jqka.com.cn"

    def __init__(self, session: aiohttp.ClientSession, output_dir: Path):
        self.session = session
        self.output_dir = output_dir / "tonghuashun"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def get_stock_reports(self, ticker: str, page: int = 1) -> List[dict]:
        """获取个股研报列表"""
        url = f"{self.BASE_URL}/api/stock_report/stock_report_list/"
        params = {"code": ticker, "page": page, "limit": 20}
        try:
            headers = {"Referer": f"https://stock.10jqka.com.cn/{ticker}/"}
            async with self.session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                return data.get("data", [])
        except Exception as e:
            print(f"  [10jqka] Error for {ticker}: {e}")
        return []


class ClsScraper:
    """财联社深度/研报爬虫"""

    BASE_URL = "https://www.cls.cn"
    SEARCH_API = "/api/search/v3/deep"

    def __init__(self, session: aiohttp.ClientSession, output_dir: Path):
        self.session = session
        self.output_dir = output_dir / "cls"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def search_deep(self, keyword: str, page: int = 1, size: int = 20) -> List[dict]:
        """搜索深度报告"""
        params = {
            "keyword": keyword,
            "page": page,
            "size": size,
            "type": "deep",
        }
        url = f"{self.BASE_URL}{self.SEARCH_API}?{urlencode(params)}"
        try:
            headers = {"Referer": "https://www.cls.cn/depth/"}
            async with self.session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                return data.get("data", {}).get("list", [])
        except Exception as e:
            print(f"  [CLS] Search error: {e}")
        return []


class YanbaojxScraper:
    """研报精选爬虫"""

    BASE_URL = "https://yanbaojx.com"

    def __init__(self, session: aiohttp.ClientSession, output_dir: Path):
        self.session = session
        self.output_dir = output_dir / "yanbaojx"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def search(self, keyword: str, page: int = 1) -> List[dict]:
        url = f"{self.BASE_URL}/search"
        params = {"q": keyword, "page": page}
        try:
            headers = {"Referer": "https://yanbaojx.com/"}
            async with self.session.get(url, params=params, headers=headers) as resp:
                html = await resp.text()
                return self._parse_html(html)
        except Exception as e:
            print(f"  [Yanbaojx] Error: {e}")
        return []

    def _parse_html(self, html: str) -> List[dict]:
        """解析 HTML 列表"""
        # 简化版，实际需要更完整的解析
        results = []
        # 使用正则或 BeautifulSoup 解析
        return results


async def download_research(keywords: List[str], output_dir: Path, max_pages: int = 3):
    """统一下载入口"""
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=3)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        eastmoney = EastmoneyScraper(session, output_dir)
        ths = TonghuashunScraper(session, output_dir)
        cls = ClsScraper(session, output_dir)
        ybj = YanbaojxScraper(session, output_dir)

        for keyword in keywords:
            print(f"\n🔍 Searching: {keyword}")

            # 东方财富
            print("  [Eastmoney]...")
            for page in range(1, max_pages + 1):
                reports = await eastmoney.search_reports(keyword=keyword, page=page)
                if not reports:
                    break
                print(f"    Page {page}: {len(reports)} reports")

                for r in reports:
                    info_code = r.get("infoCode")
                    title = r.get("title", "untitled").replace("/", "_")[:80]
                    org = r.get("orgSName", "unknown")
                    date = r.get("publishDate", "")[:10]

                    # 获取详情拿 PDF 链接
                    detail = await eastmoney.get_report_detail(info_code)
                    if detail:
                        pdf_url = detail.get("pdfUrl") or detail.get("pdfUrlNew")
                        if pdf_url:
                            filename = f"{date}_{org}_{title}.pdf"
                            await eastmoney.download_pdf(pdf_url, filename)

                    await asyncio.sleep(0.2)

            # 财联社
            print("  [CLS]...")
            for page in range(1, max_pages + 1):
                reports = await cls.search_deep(keyword, page)
                if not reports:
                    break
                print(f"    Page {page}: {len(reports)} reports")

                for r in reports:
                    # CLS 通常提供网页版，PDF 需要进一步处理
                    title = r.get("title", "").replace("/", "_")[:80]
                    date = r.get("ctime", "")[:10]
                    print(f"      {date} - {title}")

                await asyncio.sleep(0.5)

            # 同花顺 - 需要股票代码
            if re.match(r"^\d{6}$", keyword):
                print("  [10jqka]...")
                reports = await ths.get_stock_reports(keyword)
                for r in reports:
                    print(f"      {r.get('title', '')}")


def main():
    parser = argparse.ArgumentParser(description="Download free research reports")
    parser.add_argument("--keywords", "-k", required=True, help="Comma-separated keywords/tickers")
    parser.add_argument("--output-dir", "-o", default="benchmark/golden_raw/research", help="Output directory")
    parser.add_argument("--max-pages", "-p", type=int, default=3, help="Max pages per source")
    parser.add_argument("--sources", "-s", default="eastmoney,cls,10jqka", help="Sources to use")

    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",")]
    output_dir = Path(args.output_dir)

    asyncio.run(download_research(keywords, output_dir, args.max_pages))

    print(f"\n✓ Research download complete. Check: {output_dir}")


if __name__ == "__main__":
    main()
