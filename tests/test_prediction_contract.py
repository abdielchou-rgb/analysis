# -*- coding: utf-8 -*-
"""P0-2 (2026-09-02): 预测契约修复测试——目标价/证伪条件提取 + 方向清洗。

圆桌 P0-2 缺陷：2018 条预测 0 带目标价、0 带证伪条件。
根因：bold_call_extractor 的 LLM prompt 不要求输出 target_price/falsification。
本测试守护：
1. extract() 返回的每条 call 带 target_price/falsification 键
2. extract_and_register 能把 target_price 数值提取、direction 白名单清洗后入库
3. Prediction 数据结构含 falsification 字段
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from core.tools.track_record import Prediction, TrackRecordManager

_SAMPLE_REPORT = """
我们判断公司拐点临近，12个月目标价 38.50 元，给予买入评级。
核心逻辑：毛利率有望从 34.5% 提升至 38%，需求端放量。
风险提示：若毛利率跌破 30% 或订单低于 5 亿元，则拐点判断不成立。
"""


class TestCallContract:
    def test_extract_calls_have_keys(self):
        """extract 返回的每条 call 必须带 target_price/falsification 键（即使为空）。"""
        from core.bold_call_extractor import BoldCallExtractor

        # mock client 返回带完整字段的 JSON
        class FakeClient:
            def chat(self, prompt, temperature=0.2):
                return json.dumps(
                    [
                        {
                            "direction": "bullish",
                            "bold_call": "公司拐点临近，12个月目标价38.50元",
                            "confidence": 0.7,
                            "time_horizon": "12m",
                            "evidence": "毛利率提升+需求放量",
                            "target_price": "38.50",
                            "falsification": "毛利率跌破30%或订单低于5亿",
                        }
                    ],
                    ensure_ascii=False,
                )

        e = BoldCallExtractor()
        e._get_client = lambda: FakeClient()
        calls = e.extract(_SAMPLE_REPORT, "测试公司", "listed_company")
        assert len(calls) == 1
        assert "target_price" in calls[0]
        assert "falsification" in calls[0]
        assert calls[0]["target_price"] == "38.50"
        assert "毛利率" in calls[0]["falsification"]

    def test_setdefault_guards_missing_keys(self):
        """LLM 若漏输出 target_price/falsification，extract 也要补默认空值。"""
        from core.bold_call_extractor import BoldCallExtractor

        class FakeClient:
            def chat(self, prompt, temperature=0.2):
                return json.dumps(
                    [{"direction": "bullish", "bold_call": "判断", "confidence": 0.6, "time_horizon": "12m"}],
                    ensure_ascii=False,
                )

        e = BoldCallExtractor()
        e._get_client = lambda: FakeClient()
        calls = e.extract(_SAMPLE_REPORT, "测试公司", "listed_company")
        assert "target_price" in calls[0]
        assert "falsification" in calls[0]
        assert calls[0]["target_price"] == ""


class TestDirectionWhitelist:
    def test_illegal_direction_normalized(self):
        """非 bullish/bearish/neutral 的方向值应清洗为 neutral。"""
        from core.bold_call_extractor import BoldCallExtractor

        e = BoldCallExtractor()
        # 直接测内部清洗逻辑——用 monkeypatch 替换 extract 返回非法值
        e.extract = lambda *a, **kw: [
            {"direction": "长期看多", "bold_call": "x", "confidence": 0.5, "time_horizon": "12m"}
        ]
        tm = TrackRecordManager()
        calls = e.extract_and_register("报告", "测试", "listed_company", "测试", tm=tm)
        # 验证入库的 prediction direction 是 neutral（白名单内）
        last = tm.record.predictions[-1]
        assert last.direction == "neutral"


class TestPredictionDataContract:
    def test_prediction_has_falsification_field(self):
        """Prediction 数据结构含 falsification 字段。"""
        p = Prediction()
        assert hasattr(p, "falsification")
        assert p.falsification == ""

    def test_register_carries_falsification(self):
        """register_prediction 能携带 falsification 入库。"""
        tm = TrackRecordManager()
        n0 = len(tm.record.predictions)
        tm.register_prediction(
            asset="测试",
            report_type="listed_company",
            industry="测试",
            direction="bullish",
            bold_call="判断",
            target_price="38.5",
            falsification="毛利率跌破30%",
            time_horizon="12m",
        )
        assert len(tm.record.predictions) == n0 + 1
        last = tm.record.predictions[-1]
        assert last.target_price == "38.5"
        assert last.falsification == "毛利率跌破30%"
