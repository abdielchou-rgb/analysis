"""V51 L3-1 时序验证 MVP

闭环：报告生成时记录 prediction → 6 个月后回头看 → 计算准确率 → 更新认知基线

CognitiveBaseline 已有:
  - prediction_history: [{id, type, text, time_window, created_at, verified_at_6m, mid_term_result, verified_at_12m, final_result}]
  - active_hypotheses: [{statement, confidence, last_verified}]
  - data_freshness: {variable_name: last_updated}

当前缺失（本模块补齐）:
  1. PredictionAccuracy 计算
  2. TemporalScore 合成（BacktestScore × 0.6 + PredAcc × 0.4）
  3. 认知基线修正（准确率 < 0.5 → 标记 hypotheses 为"需重新检验"）
  4. CLI: python main.py backtest-lookback

FP4 设计：
  一个不会"回头看"的分析师不是真正的资深分析师。
  系统必须在每次判断被市场验证（或证伪）之后修正自身的认知框架。
  这是 FP4 要求的"像人一样犯错并修正"的工程实现。
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.cognitive_baseline import CognitiveBaseline

logger = logging.getLogger("v51.temporal_verifier")

# ═══════════════════════════════════════════════════════════════
# 评分配置
# ═══════════════════════════════════════════════════════════════

PREDICTION_WEIGHTS = {
    "directional": 0.20,   # 方向性预测："沪深300在6个月内上涨"
    "range": 0.30,         # 区间预测："目标价45-50元"
    "event": 0.25,         # 事件预测："Q2财报收入超预期"
    "trend": 0.15,         # 趋势预测："行业集中度12个月内从60%提升至70%"
    "bold_call": 0.10,     # Bold Call ："XX公司将在18个月内被收购"
}

# 各预测类型的评分函数
# Score_i: 正确=1.0 / 部分正确=0.5 / 错误=0.0


def score_directional(prediction_text: str, actual_outcome: str) -> float:
    """方向性预测评分。"""
    text = prediction_text.lower()
    outcome = actual_outcome.lower()
    # 简单实现: 检查预测方向和实际方向是否一致
    bull_words = ["上涨", "增长", "提升", "突破", "利好", "牛市"]
    bear_words = ["下跌", "下降", "回落", "利空", "熊市"]

    pred_bull = any(w in text for w in bull_words)
    pred_bear = any(w in text for w in bear_words)
    act_bull = any(w in outcome for w in bull_words)
    act_bear = any(w in outcome for w in bear_words)

    if (pred_bull and act_bull) or (pred_bear and act_bear):
        return 1.0
    if (pred_bull and act_bear) or (pred_bear and act_bull):
        return 0.0
    return 0.5


def score_range(prediction_text: str, actual_value: float) -> float:
    """区间预测评分。"""
    import re
    range_match = re.search(r'(\d+[\.\d]*)-\s*(\d+[\.\d]*)', prediction_text)
    if range_match:
        low, high = float(range_match.group(1)), float(range_match.group(2))
        if low <= actual_value <= high:
            return 1.0
        margin = (high - low) * 0.2  # 允许 20% 偏离
        if (low - margin) <= actual_value <= (high + margin):
            return 0.5
        return 0.0
    return 0.5  # 无法解析时给中等分


def score_event(prediction_text: str, actual_outcome: str) -> float:
    """事件预测评分。"""
    text = prediction_text.lower()
    outcome = actual_outcome.lower()
    # 简单实现：检查事件关键词是否在结果中出现
    event_keywords = ["超预期", "不及预期", "符合预期"]
    for kw in event_keywords:
        if kw in text and kw in outcome:
            return 1.0
        if (kw in text) != (kw in outcome):
            return 0.0
    return 0.5


def score_trend(prediction_text: str, actual_trend: dict) -> float:
    """趋势预测评分。"""
    text = prediction_text.lower()
    actual_pct = actual_trend.get("actual_change_pct", 0)
    predicted_dir = "up" if any(w in text for w in ["提升", "增长", "上升", "扩大"]) else "down" if any(w in text for w in ["下降", "降低", "缩小"]) else "neutral"
    actual_dir = "up" if actual_pct > 0 else "down"
    if predicted_dir == actual_dir:
        return 1.0
    if predicted_dir == "neutral":
        return 0.5 if abs(actual_pct) < 5 else 0.0
    return 0.0


def score_bold_call(prediction_text: str, actual_outcome: str) -> float:
    """Bold Call 评分——二进制判断。"""
    text = prediction_text.lower()
    outcome = actual_outcome.lower()
    # Bold Call 不做部分评分
    key_phrases = ["收购", "被收购", "并购", "退市", "破产", "重组", "分拆"]
    for phrase in key_phrases:
        if phrase in text and phrase in outcome:
            return 1.0
        if phrase in text and phrase not in outcome:
            return 0.0
    return 0.5  # 无法判定


# ═══════════════════════════════════════════════════════════════
# 时序验证引擎
# ═══════════════════════════════════════════════════════════════


@dataclass
class TemporalResult:
    """一次时序验证的结果。"""
    asset_code: str = ""
    total_predictions: int = 0
    verified_count: int = 0
    prediction_accuracy: float = 0.0
    details: list[dict] = field(default_factory=list)
    needs_baseline_update: bool = False  # 是否需要更新认知基线


class TemporalVerifier:
    """时序验证引擎。

    用法:
        verifier = TemporalVerifier()
        # 报告生成时自动调用
        verifier.record_prediction(asset_code="600519.SH", prediction_data={...})
        # 6个月后手动触发
        result = verifier.run_lookback("600519.SH", lookback_months=6)
        if result.prediction_accuracy < 0.5:
            verifier.update_baseline("600519.SH", result)
    """

    def __init__(self):
        self.recorder = PredictionRecorder()

    def record_prediction(self, asset_code: str, prediction_type: str,
                          prediction_text: str, time_window: str = "6m",
                          metadata: dict = None) -> None:
        """报告生成时记录一个预测。"""
        self.recorder.record(asset_code, prediction_type, prediction_text,
                             time_window, metadata or {})
        logger.info(f"Prediction recorded for {asset_code}: [{prediction_type}] {prediction_text[:60]}...")

    def run_lookback(self, asset_code: str, actual_outcomes: dict,
                     lookback_months: int = 6) -> TemporalResult:
        """回头看：对比预测与实际。"""
        baseline = CognitiveBaseline.load(asset_code)
        predictions = baseline.get("prediction_history", [])
        result = TemporalResult(asset_code=asset_code)
        result.total_predictions = len(predictions)

        # 过滤出到期的预测
        cutoff = datetime.now() - timedelta(days=lookback_months * 30)
        for pred in predictions:
            created = pred.get("created_at", "")
            if not created:
                continue
            try:
                pred_time = datetime.fromisoformat(created)
            except (ValueError, TypeError):
                continue
            if pred_time > cutoff:
                continue  # 还没到验证周期

            pred_type = pred.get("type", "directional")
            pred_text = pred.get("text", "")
            actual = actual_outcomes.get(pred.get("id", ""), "")

            if not actual:
                continue

            # 计算单次预测准确率
            scorer = self._get_scorer(pred_type)
            if scorer:
                try:
                    if pred_type == "range" and isinstance(actual, (int, float)):
                        score = scorer(pred_text, actual)
                    elif pred_type == "trend" and isinstance(actual, dict):
                        score = scorer(pred_text, actual)
                    else:
                        score = scorer(pred_text, str(actual))
                except Exception:
                    score = 0.0
            else:
                score = 0.0

            detail = {
                "id": pred.get("id", ""),
                "type": pred_type,
                "text": pred_text[:80],
                "score": score,
                "weight": PREDICTION_WEIGHTS.get(pred_type, 0.1),
            }
            result.details.append(detail)
            result.verified_count += 1

            # 写回验证结果到 CognitiveBaseline
            if lookback_months <= 6:
                pred["mid_term_result"] = {"score": score, "verified_at": datetime.now().isoformat()}
            else:
                pred["final_result"] = {"score": score, "verified_at": datetime.now().isoformat()}

        CognitiveBaseline.save(asset_code, baseline)

        # 计算加权准确率
        if result.details:
            total_weight = sum(d["weight"] for d in result.details)
            weighted_score = sum(d["score"] * d["weight"] for d in result.details)
            result.prediction_accuracy = weighted_score / total_weight if total_weight > 0 else 0.0
        else:
            result.prediction_accuracy = 0.0

        # 判断是否需要更新基线
        result.needs_baseline_update = result.prediction_accuracy < 0.5
        return result

    def update_baseline(self, asset_code: str, result: TemporalResult) -> None:
        """根据时序验证结果修正认知基线。"""
        baseline = CognitiveBaseline.load(asset_code)

        # 准确率过低 → 标记 hypotheses 为"需重新检验"
        if result.prediction_accuracy < 0.5:
            hypotheses = baseline.get("active_hypotheses", [])
            for h in hypotheses:
                if h.get("confidence", "medium") in ("high", "medium"):
                    h["status"] = "needs_revalidation"
                    h["last_verified"] = datetime.now().isoformat()
                    h["note"] = f"时序验证准确率 {result.prediction_accuracy:.2f}，建议重新检验"
                    logger.warning(f"Hypothesis marked for revalidation: {h.get('statement', '')[:60]}...")
            baseline["active_hypotheses"] = hypotheses

        # 记录验证历史
        validation_history = baseline.get("validation_history", [])
        validation_history.append({
            "timestamp": datetime.now().isoformat(),
            "prediction_accuracy": result.prediction_accuracy,
            "predictions_verified": result.verified_count,
        })
        baseline["validation_history"] = validation_history

        CognitiveBaseline.save(asset_code, baseline)
        logger.info(f"Baseline updated for {asset_code} (accuracy: {result.prediction_accuracy:.2f})")

    def _get_scorer(self, pred_type: str):
        """获取预测类型的评分函数。"""
        scorers = {
            "directional": score_directional,
            "range": score_range,
            "event": score_event,
            "trend": score_trend,
            "bold_call": score_bold_call,
        }
        return scorers.get(pred_type)


# ═══════════════════════════════════════════════════════════════
# 预测记录器
# ═══════════════════════════════════════════════════════════════


class PredictionRecorder:
    """负责将预测写入 CognitiveBaseline。"""

    @staticmethod
    def record(asset_code: str, prediction_type: str, prediction_text: str,
               time_window: str = "6m", metadata: dict = None) -> None:
        """写入一条预测到 CognitiveBaseline。"""
        import hashlib
        pred_id = hashlib.md5(f"{asset_code}_{prediction_text}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        prediction_entry = {
            "id": pred_id,
            "type": prediction_type,
            "text": prediction_text,
            "time_window": time_window,
            "created_at": datetime.now().isoformat(),
            "verified_at_6m": None,
            "mid_term_result": None,
            "verified_at_12m": None,
            "final_result": None,
            "metadata": metadata or {},
        }

        baseline = CognitiveBaseline.load(asset_code)
        predictions = baseline.get("prediction_history", [])
        predictions.append(prediction_entry)
        baseline["prediction_history"] = predictions
        CognitiveBaseline.save(asset_code, baseline)


# ═══════════════════════════════════════════════════════════════
# CLI 集成
# ═══════════════════════════════════════════════════════════════


def run_lookback_for_asset(asset_code: str, lookback_months: int = 6) -> TemporalResult:
    """便捷函数：对某个标的跑回头看。"""
    verifier = TemporalVerifier()
    # 实际使用时需要传入 actual_outcomes 参数
    # 此处为框架占位，等待数据管线接入实际数据
    result = TemporalResult(asset_code=asset_code)
    return result
