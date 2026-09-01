#!/usr/bin/env python
"""
Company Filings Downloader — 交易所公开文件批量下载

支持：
- 上交所 (SSE): 年报/季报/公告
- 深交所 (SZSE): 年报/季报/公告
- 港交所 (HKEX): 年报/季报/公告
- 美 SEC (EDGAR): 10-K/10-Q/8-K

用法:
    python scripts/download_filings.py --tickers "600519,300750,002594" --exchange SSE --years 5
    python scripts/download_filings.py --ticker 600519 --exchange SSE --output-dir benchmark/golden_raw/listed_company
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

try:
    from core.asset_resolver import resolve_asset
except ImportError:
    resolve_asset = None


class SSEDownloader:
    """上交所公告下载"""

    BASE_URL = "https://query.sse.com.cn"
    ANNOUNCEMENT_API = "/security/stock/queryCompanyBulletin.do"

    CATEGORIES = {"annual": "年报", "quarterly": "季报", "semi_annual": "半年报", "all": "全部"}

    def __init__(self, session: aiohttp.ClientSession, output_dir: Path):
        self.session = session
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def get_announcements(
        self, ticker: str, start_date: str, end_date: str, category: str = "all", page_size: int = 100
    ) -> List[dict]:
        """获取公告列表"""
        params = {
            "jsonCallBack": "jsonpCallback",
            "isPagination": "true",
            "pageHelp.pageSize": str(page_size),
            "pageHelp.pageNo": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": "5",
            "securityCode": ticker,
            "categoryId": category,
            "startDate": start_date,
            "endDate": end_date,
        }

        url = f"{self.BASE_URL}{self.ANNOUNCEMENT_API}?{urlencode(params)}"

        try:
            async with self.session.get(url, headers={"Referer": "https://www.sse.com.cn/"}) as resp:
                text = await resp.text()
                # SSE 返回 JSONP，需要提取 JSON
                match = re.search(r"jsonpCallback\((.*)\)", text)
                if match:
                    data = json.loads(match.group(1))
                    return data.get("result", [])
        except Exception as e:
            print(f"  [SSE] Error fetching {ticker}: {e}")
        return []

    async def download_pdf(self, announcement: dict) -> Optional[Path]:
        """下载单个公告 PDF"""
        pdf_url = announcement.get("URL") or announcement.get("attachPath")
        if not pdf_url:
            return None

        # 补全 URL
        if pdf_url.startswith("//"):
            pdf_url = "https:" + pdf_url
        elif pdf_url.startswith("/"):
            pdf_url = "https://static.sse.com.cn" + pdf_url

        title = announcement.get("TITLE", "untitled").replace("/", "_").replace("\\", "_")[:100]
        date_str = announcement.get("SSEDATE", "")[:10].replace("-", "")
        filename = f"{date_str}_{title}.pdf"
        filepath = self.output_dir / filename

        if filepath.exists():
            return filepath

        try:
            async with self.session.get(pdf_url) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    filepath.write_bytes(content)
                    print(f"    ✓ Downloaded: {filename}")
                    return filepath
        except Exception as e:
            print(f"    ✗ Failed: {filename} - {e}")
        return None


class SZSEDownloader:
    """深交所公告下载"""

    BASE_URL = "https://www.szse.cn"
    ANNOUNCEMENT_API = "/api/disc/announcement/annList"

    def __init__(self, session: aiohttp.ClientSession, output_dir: Path):
        self.session = session
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def get_announcements(
        self, ticker: str, start_date: str, end_date: str, category: str = "010301", page_size: int = 50
    ) -> List[dict]:
        """category: 010301=年报, 010302=半年报, 010303=季报"""
        params = {
            "random": "0.123456",
            "pageSize": str(page_size),
            "pageNum": "1",
            "stock": [ticker],
            "category": [category],
            "startTime": start_date,
            "endTime": end_date,
            "seDate": f"{start_date}~{end_date}",
        }

        url = f"{self.BASE_URL}{self.ANNOUNCEMENT_API}"

        try:
            async with self.session.post(
                url, json=params, headers={"Content-Type": "application/json", "Referer": "https://www.szse.cn/"}
            ) as resp:
                data = await resp.json()
                return data.get("data", [])
        except Exception as e:
            print(f"  [SZSE] Error fetching {ticker}: {e}")
        return []

    async def download_pdf(self, announcement: dict) -> Optional[Path]:
        """下载深交所公告 PDF"""
        attach_path = announcement.get("attachPath")
        if not attach_path:
            return None

        pdf_url = f"{self.BASE_URL}{attach_path}"
        title = announcement.get("title", "untitled").replace("/", "_").replace("\\", "_")[:100]
        date_str = announcement.get("publishTime", "")[:10].replace("-", "")
        filename = f"{date_str}_{title}.pdf"
        filepath = self.output_dir / filename

        if filepath.exists():
            return filepath

        try:
            async with self.session.get(pdf_url) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    filepath.write_bytes(content)
                    print(f"    ✓ Downloaded: {filename}")
                    return filepath
        except Exception as e:
            print(f"    ✗ Failed: {filename} - {e}")
        return None


class HKEXDownloader:
    """港交所公告下载"""

    BASE_URL = "https://www.hkexnews.hk"
    SEARCH_URL = "/listedco/listconews/advancedsearch/active_main_c.aspx"

    def __init__(self, session: aiohttp.ClientSession, output_dir: Path):
        self.session = session
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def get_announcements(self, ticker: str, start_date: str, end_date: str, doc_type: str = "-1") -> List[dict]:
        """搜索公告 - 需要解析 HTML 表单"""
        # 港交所比较复杂，建议使用 Playwright 或直接下载已知 URL 模式
        # 这里提供基础框架
        return []


class SECDownloader:
    """美国 SEC EDGAR 下载"""

    BASE_URL = "https://www.sec.gov"
    SEARCH_URL = "/cgi-bin/browse-edgar"
    SUBMISSIONS_URL = "/Archives/edgar/data"

    def __init__(self, session: aiohttp.ClientSession, output_dir: Path):
        self.session = session
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def get_company_cik(self, ticker: str) -> Optional[str]:
        """通过 ticker 查找 CIK"""
        # SEC 公司搜索
        url = f"{self.BASE_URL}/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=&dateb=&owner=include&count=10"
        try:
            async with self.session.get(url, headers={"User-Agent": "2hao-analyst/1.0"}) as resp:
                html = await resp.text()
                # 解析 CIK
                match = re.search(r"CIK=(\d{10})", html)
                if match:
                    return match.group(1).lstrip("0")
        except Exception:
            pass
        return None

    async def get_filings(
        self, cik: str, form_types: List[str] = None, start_date: str = None, count: int = 100
    ) -> List[dict]:
        """获取公司文件列表"""
        if form_types is None:
            form_types = ["10-K", "10-Q", "8-K", "20-F", "40-F"]

        url = f"{self.BASE_URL}/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "CIK": cik.zfill(10),
            "type": "",
            "dateb": "",
            "owner": "include",
            "count": str(count),
        }

        try:
            async with self.session.get(url, params=params, headers={"User-Agent": "2hao-analyst/1.0"}) as resp:
                html = await resp.text()
                # 解析表格
                return self._parse_filings_table(html, form_types)
        except Exception as e:
            print(f"  [SEC] Error fetching CIK {cik}: {e}")
        return []

    def _parse_filings_table(self, html: str, form_types: List[str]) -> List[dict]:
        """解析 SEC 文件表格"""
        # 简化版：实际建议使用 sec-api 或 edgar-python 库
        filings = []
        # ... HTML 解析逻辑
        return filings


async def download_all(tickers: List[str], exchange: str, years: int, output_dir: Path):
    """统一下载入口"""
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")

        if exchange.upper() == "SSE":
            downloader = SSEDownloader(session, output_dir)
            get_anns = downloader.get_announcements
            dl_pdf = downloader.download_pdf
        elif exchange.upper() == "SZSE":
            downloader = SZSEDownloader(session, output_dir)
            get_anns = downloader.get_announcements
            dl_pdf = downloader.download_pdf
        elif exchange.upper() == "HKEX":
            downloader = HKEXDownloader(session, output_dir)
            get_anns = downloader.get_announcements
            dl_pdf = downloader.download_pdf
        elif exchange.upper() == "SEC":
            downloader = SECDownloader(session, output_dir)
            # SEC 用不同流程
            for ticker in tickers:
                cik = await downloader.get_company_cik(ticker)
                if cik:
                    filings = await downloader.get_filings(cik)
                    for f in filings:
                        await downloader.download_filing(f, ticker)
            return
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

        for ticker in tickers:
            print(f"\n[{exchange}] Processing {ticker}...")
            try:
                announcements = await get_anns(ticker, start_date, end_date)
                print(f"  Found {len(announcements)} announcements")

                for ann in announcements:
                    await dl_pdf(ann)
                    await asyncio.sleep(0.1)  # 限流
            except Exception as e:
                print(f"  Error processing {ticker}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Download company filings from exchanges")
    parser.add_argument("--tickers", "-t", required=True, help="Comma-separated tickers (e.g., 600519,300750)")
    parser.add_argument("--exchange", "-e", required=True, choices=["SSE", "SZSE", "HKEX", "SEC"], help="Exchange")
    parser.add_argument("--years", "-y", type=int, default=5, help="Years of history")
    parser.add_argument("--output-dir", "-o", default="benchmark/golden_raw", help="Output directory")
    parser.add_argument("--category", "-c", default="all", help="Announcement category (SSE/SZSE)")

    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")]
    output_dir = Path(args.output_dir) / args.exchange.lower()

    asyncio.run(download_all(tickers, args.exchange, args.years, output_dir))

    print(f"\n✓ Download complete. Files in: {output_dir}")


if __name__ == "__main__":
    main()
