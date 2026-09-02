"""
bold_call_extractor.py - LLM-assisted bold call extraction from report text.
Replaces regex-based extraction - significantly higher coverage.
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("2hao.bold_call")

_ROOT = Path(__file__).resolve().parent.parent


class BoldCallExtractor:
    """Extract bold calls from report text using DeepSeek"""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from core.deepseek_client import DeepSeekClient

                self._client = DeepSeekClient()
            except Exception as e:
                logger.warning("DeepSeek client unavailable: %s", e)
                return None
        return self._client

    def extract(self, report_text: str, asset: str = "", report_type: str = "industry_deep") -> list[dict]:
        """Extract bold calls from report text using LLM"""
        client = self._get_client()
        if not client:
            return self._extract_regex_fallback(report_text)

        prompt = f"""从以下{report_type}报告中，提取所有的核心判断（Bold Call）。

Bold Call定义：
- 与市场共识不同的独特观点
- 对未来价格/业绩的明确预测
- 对行业格局变化的判断
- 对估值重估的预期
- 对催化剂事件的判断

输出JSON格式（数组）:
[
  {{
    "direction": "bullish/bearish/neutral",
    "bold_call": "具体判断内容（30-80字）",
    "confidence": 0.0-1.0,
    "time_horizon": "3m/6m/12m/unknown",
    "evidence": "支撑该判断的主要论据（20-50字）",
    "target_price": "明确的目标价数字（元），若报告给出了目标价则填数字；否则空字符串",
    "falsification": "证伪条件——什么指标/事件触发时该判断被证明错误（如'毛利率跌破34%'、'订单低于X亿'）；20-50字"
  }}
]

可证伪性铁律（FP2b）：每个 bullish/bearish 判断必须能回答"什么情况下我错了"。
若报告含目标价，target_price 必填；若无明确目标价则留空字符串（诚实标注，不编造）。
falsification 从报告的"证伪条件/风险提示"章节提取，无则根据 bold_call 推理一个可观察的证伪阈值。

报告标题: {asset}
报告内容:
{report_text[:6000]}
"""

        try:
            response = client.chat(prompt, temperature=0.2)
            if response:
                # Try JSON parse
                json_match = re.search(r"\[.*?\]", response, re.DOTALL)
                if json_match:
                    calls = json.loads(json_match.group())
                    if isinstance(calls, list):
                        # P0-2 数据契约加固：确保每个 call 带 target_price/falsification 键
                        for c in calls:
                            c.setdefault("target_price", "")
                            c.setdefault("falsification", "")
                        logger.info("LLM extracted %d bold calls", len(calls))
                        return calls
                # Fallback: parse line by line
                return self._parse_line_by_line(response)
        except Exception as e:
            logger.debug("LLM bold call extraction failed: %s", e)

        return self._extract_regex_fallback(report_text)

    def _parse_line_by_line(self, text: str) -> list[dict]:
        """Fallback: parse LLM response line by line"""
        calls = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            for direction in ["bullish", "bearish", "neutral"]:
                if direction in line.lower():
                    calls.append(
                        {
                            "direction": direction,
                            "bold_call": line[:100],
                            "confidence": 0.5,
                            "time_horizon": "unknown",
                            "evidence": "",
                        }
                    )
                    break
        return calls

    def _extract_regex_fallback(self, report_text: str) -> list[dict]:
        """Legacy regex-based extraction (fallback)"""
        calls = []
        patterns = [
            (r"我们(预测|预计|认为|判断)[^。]*?(增长|下降|突破|达到|超过|低于)[^。]*。", "bullish"),
            (r"我们(担忧|警惕|关注)[^。]*?(风险|挑战|下降|低于预期)[^。]*。", "bearish"),
            (r"(目标价|合理估值|公允价值)[为是约]?\s*\d+\.?\d*", "bullish"),
            (r"我们维持[^。]*?(买入|增持|推荐|优于大市)[^。]*。", "bullish"),
            (r"(催化剂|拐点|转折)[^。]*?(来临|出现|确认|临近)[^。]*。", "bullish"),
            (r"我们(下调|降低|调降)[^。]*?(评级|预期|目标价)[^。]*。", "bearish"),
        ]
        for pattern, direction in patterns:
            matches = re.findall(pattern, report_text)
            for m in matches[:3]:
                text = m if isinstance(m, str) else m[0]
                calls.append(
                    {
                        "direction": direction,
                        "bold_call": text[:100],
                        "confidence": 0.4,
                        "time_horizon": "unknown",
                        "evidence": "",
                    }
                )
        return calls

    def extract_and_register(
        self, report_text: str, asset: str, report_type: str, industry: str = "",
        tm=None, collected_data: dict = None,
    ) -> list[dict]:
        """Extract bold calls and register with TrackRecordManager"""
        calls = self.extract(report_text, asset, report_type)

        # W1.1: 从 collected_data 获取 primary_target_price 作为 fallback
        _fallback_tp = ""
        if collected_data and isinstance(collected_data, dict):
            _tp = collected_data.get("target_price")
            if _tp and isinstance(_tp, (int, float)) and _tp > 0:
                _fallback_tp = str(_tp)

        if tm and calls:
            for c in calls:
                try:
                    # P0-2 方向白名单：bullish/bearish/neutral 之外的非法方向值 → neutral + 记为逻辑
                    direction = c.get("direction", "neutral")
                    if direction not in ("bullish", "bearish", "neutral"):
                        direction = "neutral"
                    # target_price 提取数字（容忍 "38.5元"/38.5/"目标价38.5"）
                    tp_raw = str(c.get("target_price", "") or "").strip()
                    tp_num = re.sub(r"[^\d.]", "", tp_raw)
                    try:
                        tp_val = float(tp_num) if tp_num and 0.5 < float(tp_num) < 100_000 else ""
                    except ValueError:
                        tp_val = ""
                    # W1.1: LLM 未提取到 target_price 时，使用管线计算值
                    if not tp_val and _fallback_tp:
                        tp_val = _fallback_tp
                    tm.register_prediction(
                        asset=asset,
                        report_type=report_type,
                        industry=industry or asset,
                        direction=direction,
                        bold_call=c["bold_call"][:200],
                        target_price=str(tp_val) if tp_val else "",
                        falsification=str(c.get("falsification", ""))[:200],
                        time_horizon=c.get("time_horizon", "6m"),
                        confidence=c.get("confidence", 0.5),
                    )
                except Exception as e:
                    logger.debug("Failed to register bold call: %s", e)
            logger.info("Registered %d bold calls with TrackRecord", len(calls))

        return calls


__all__ = ["BoldCallExtractor"]
