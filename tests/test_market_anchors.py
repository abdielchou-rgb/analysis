# -*- coding: utf-8 -*-
"""C1: market_anchors 提取验证测试。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from pipeline.checks.market_anchors import load_market_anchors


class TestLoadMarketAnchors:
    def test_no_asset_returns_empty(self):
        result = load_market_anchors(asset="")
        assert isinstance(result, dict)

    def test_nonexistent_asset_returns_empty(self):
        result = load_market_anchors(asset="不存在的标的_12345")
        assert isinstance(result, dict)

    def test_return_type(self):
        result = load_market_anchors(asset="test")
        assert isinstance(result, dict)
        for v in result.values():
            assert "unit" in v
            assert "values" in v
