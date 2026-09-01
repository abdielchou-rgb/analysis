# -*- coding: utf-8 -*-
"""C3: to_yfinance_ticker 中央化测试——A股/港股/美股通用后缀映射。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from core.data_backends import _to_yfinance_ticker


class TestToYfinanceTicker:
    def test_shanghai_a_share(self):
        assert _to_yfinance_ticker("600519") == "600519.SS"

    def test_shanghai_9x(self):
        assert _to_yfinance_ticker("900901") == "900901.SS"

    def test_shenzhen_0x(self):
        assert _to_yfinance_ticker("000858") == "000858.SZ"

    def test_shenzhen_3x(self):
        assert _to_yfinance_ticker("300750") == "300750.SZ"

    def test_shenzhen_2x(self):
        assert _to_yfinance_ticker("200001") == "200001.SZ"

    def test_hk_5digit(self):
        assert _to_yfinance_ticker("00700") == "00700.HK"

    def test_hk_with_suffix(self):
        assert _to_yfinance_ticker("00700.HK") == "00700.HK"

    def test_us_ticker(self):
        assert _to_yfinance_ticker("AAPL") == "AAPL"

    def test_us_ticker_lowercase(self):
        assert _to_yfinance_ticker("msft") == "MSFT"

    def test_with_suffix_sh(self):
        assert _to_yfinance_ticker("600519.SH") == "600519.SS"

    def test_unknown_returns_none(self):
        assert _to_yfinance_ticker("") is None

    def test_whitespace_handled(self):
        assert _to_yfinance_ticker(" 600519 ") == "600519.SS"
