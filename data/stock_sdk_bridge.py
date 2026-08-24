"""
2hao-analyst StockSDK Bridge ? stock-sdk CLI wrapper for Python

Uses stock-sdk (https://npm.im/stock-sdk) via subprocess to fetch:
- Real-time A/HK/US stock quotes
- Historical K-line data
- Technical indicators
- Sector/industry board data
- Capital flow, dragon-tiger, block trade data

Install: npm install -g stock-sdk
"""
import subprocess
import json as _json
import logging
from typing import Optional

logger = logging.getLogger("2hao.stock_sdk")


class StockSDKBridge:
    """Bridge to stock-sdk CLI for financial data."""

    def __init__(self):
        self._available = self._check()

    def _check(self) -> bool:
        try:
            result = subprocess.run(
                ["stock-sdk.cmd", "quote", "--help"],
                capture_output=True, text=True, encoding="utf-8", timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    @property
    def available(self) -> bool:
        return self._available

    def quote(self, code: str) -> Optional[dict]:
        """Get real-time quote for a stock code."""
        try:
            result = subprocess.run(
                ["npx.cmd", "-q", "stock-sdk.cmd", "quote", code, "--format", "json"],
                capture_output=True, text=True, encoding="utf-8", timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = _json.loads(result.stdout.strip())
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
            return None
        except Exception as e:
            logger.debug("StockSDK quote failed for %s: %s", code, e)
            return None

    def kline(self, code: str, period: str = "weekly", limit: int = 30) -> Optional[list]:
        """Get historical K-line data."""
        try:
            result = subprocess.run(
                ["npx.cmd", "-q", "stock-sdk.cmd", "kline", code, "--period", period,
                 "--limit", str(limit), "--format", "json"],
                capture_output=True, text=True, encoding="utf-8", timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return _json.loads(result.stdout.strip())
            return None
        except Exception as e:
            logger.debug("StockSDK kline failed for %s: %s", code, e)
            return None

    def indicators(self, code: str, ma: str = "5,10,20,60",
                   macd: bool = True, rsi: bool = True) -> Optional[dict]:
        """Get technical indicators."""
        try:
            args = ["npx.cmd", "-q", "stock-sdk.cmd", "indicators", code,
                    "--ma", ma, "--format", "json"]
            if macd:
                args.append("--macd")
            if rsi:
                args.append("--rsi")
            result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=15)
            if result.returncode == 0 and result.stdout.strip():
                return _json.loads(result.stdout.strip())
            return None
        except Exception as e:
            logger.debug("StockSDK indicators failed for %s: %s", code, e)
            return None

    def board_list(self, board_type: str = "industry") -> Optional[list]:
        """List sector/industry boards."""
        try:
            result = subprocess.run(
                ["npx.cmd", "-q", "stock-sdk.cmd", "board", board_type, "list", "--format", "json"],
                capture_output=True, text=True, encoding="utf-8", timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return _json.loads(result.stdout.strip())
            return None
        except Exception as e:
            logger.debug("StockSDK board list failed: %s", e)
            return None

    def fund_flow(self, code: str) -> Optional[dict]:
        """Get capital flow data for a stock."""
        try:
            result = subprocess.run(
                ["npx.cmd", "-q", "stock-sdk.cmd", "fundFlow", code, "--format", "json"],
                capture_output=True, text=True, encoding="utf-8", timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return _json.loads(result.stdout.strip())
            return None
        except Exception as e:
            logger.debug("StockSDK fund flow failed: %s", code, e)
            return None

    def search(self, keyword: str, limit: int = 10) -> Optional[list]:
        """Search for stocks by keyword."""
        try:
            result = subprocess.run(
                ["npx.cmd", "-q", "stock-sdk.cmd", "search", keyword,
                 "--limit", str(limit), "--format", "json"],
                capture_output=True, text=True, encoding="utf-8", timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return _json.loads(result.stdout.strip())
            return None
        except Exception as e:
            logger.debug("StockSDK search failed for %s: %s", keyword, e)
            return None


def test():
    """Quick test of StockSDKBridge."""
    bridge = StockSDKBridge()
    print(f"StockSDK available: {bridge.available}")
    if bridge.available:
        q = bridge.quote("600519")
        print(f"Quote: {_json.dumps(q, ensure_ascii=False, indent=2) if q else 'None'}")
        b = bridge.board_list("industry")
        print(f"Boards: {len(b) if b else 0} industries")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test()
