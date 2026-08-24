"""吸收2: Decision Hub — mathematical signal fusion with confidence evolution.

从 Multi-Agent Investment (flash131307) 吸收的 Decision Hub 设计哲学：
  "No LLM in the critical path" — 所有信号融合是数学的、确定性的。

三个核心机制:
  1. 历史胜率追踪 — 每个信号ID记录 wins/losses/total
  2. 权重衰减 — 时间越久的信号权重越低 (decay = e^(-λt))
  3. 概率分布输出 — Bull/Bear/Neutral 的概率 + 整体置信度

与现有系统的关系:
  - Phase B (Pattern Library) 产生原始信号 → 输入到 DecisionHub
  - Phase D (PredictionLoop) 提供信号的历史验证数据 → DecisionHub 读取
  - Phase C (Watchdog) 消费 DecisionHub 的输出 → 简报 + 告警级别
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("v51.decision_hub")

HISTORY_DB = Path(__file__).resolve().parent.parent / "data" / "signal_history.json"


# ── Data model ───────────────────────────────────────────────

@dataclass
class Signal:
    """单个信号。"""
    id: str = ""
    name: str = ""
    direction: str = "neutral"  # bull | bear | neutral
    strength: float = 0.5       # 0.0-1.0
    source: str = ""            # pattern / prediction / data
    created_at: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Decision:
    """融合后的决策输出。"""
    bull_prob: float = 0.0      # 0.0-1.0
    bear_prob: float = 0.0
    neutral_prob: float = 0.0
    conviction: float = 0.0      # 0.0-1.0 (overall confidence)
    dominant_signal: str = ""    # 最强信号的ID
    n_signals: int = 0
    n_active_signals: int = 0
    reasoning: list[str] = field(default_factory=list)


# ── History DB ───────────────────────────────────────────────

def _load_history() -> dict:
    if HISTORY_DB.exists():
        try:
            return json.loads(HISTORY_DB.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"version": "V51.3", "signals": {}}


def _save_history(data: dict):
    HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_DB.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Decision Hub ─────────────────────────────────────────────

class DecisionHub:
    """数学化信号融合引擎。"""

    # 权重衰减参数：半衰期90天
    HALF_LIFE_DAYS = 90
    DECAY_CONSTANT = math.log(2) / HALF_LIFE_DAYS

    # 最小有效信号数
    MIN_SIGNALS = 2

    # 历史胜率学习率（new = old * (1-lr) + observed * lr）
    LEARNING_RATE = 0.3

    @classmethod
    def fuse(cls, signals: list[Signal]) -> Decision:
        """融合多个信号为单一决策。

        Each signal contributes:
          weighted_strength = strength × historical_winrate × time_decay
        """
        if not signals:
            return Decision(conviction=0.0, reasoning=["无信号输入"])

        history = _load_history()
        now = datetime.now()

        bull_weight = 0.0
        bear_weight = 0.0
        total_weight = 0.0
        strongest_signal = ""
        strongest_strength = 0.0
        active_count = 0

        for sig in signals:
            # 1. 历史胜率
            signal_history = history.get("signals", {}).get(sig.id, {})
            historical_winrate = cls._get_winrate(signal_history)

            # 2. 时间衰减
            time_decay = 1.0
            if sig.created_at:
                try:
                    created = datetime.fromisoformat(sig.created_at)
                    days_old = (now - created).days
                    time_decay = math.exp(-cls.DECAY_CONSTANT * max(days_old, 0))
                except (ValueError, TypeError):
                    pass

            # 3. 综合权重
            weight = sig.strength * historical_winrate * time_decay
            total_weight += weight

            if sig.direction == "bull":
                bull_weight += weight
            elif sig.direction == "bear":
                bear_weight += weight
            else:
                # Neutral signals contribute to total but not to bull/bear
                pass

            if sig.strength > strongest_strength:
                strongest_strength = sig.strength
                strongest_signal = sig.id

            if time_decay > 0.1:  # > 10% weight remaining
                active_count += 1

        # 4. 概率分布
        decision = Decision()
        decision.n_signals = len(signals)
        decision.n_active_signals = active_count

        if total_weight > 0 and active_count >= cls.MIN_SIGNALS:
            decision.bull_prob = round(bull_weight / total_weight, 3)
            decision.bear_prob = round(bear_weight / total_weight, 3)
            decision.neutral_prob = round(
                max(0, 1 - decision.bull_prob - decision.bear_prob), 3
            )

            # Conviction: how decisive is the signal
            net = abs(decision.bull_prob - decision.bear_prob)
            coverage = min(1.0, active_count / max(cls.MIN_SIGNALS, 1))
            decision.conviction = round(net * coverage, 3)

        decision.dominant_signal = strongest_signal
        decision.reasoning = cls._generate_reasoning(signals, decision, history)

        return decision

    @classmethod
    def _get_winrate(cls, signal_history: dict) -> float:
        """Compute win rate from signal history.

        Starts at 0.5 (neutral) when no history available.
        """
        wins = signal_history.get("wins", 0)
        total = signal_history.get("total", 0)
        if total == 0:
            return 0.5
        return wins / total

    @classmethod
    def _generate_reasoning(cls, signals: list[Signal],
                             decision: Decision,
                             history: dict) -> list[str]:
        """Generate human-readable reasoning for the decision."""
        reasons = []

        if decision.conviction > 0.6:
            direction = "看多" if decision.bull_prob > decision.bear_prob else "看空"
            reasons.append(f"信号一致{direction}（置信度{decision.conviction:.0%})")
        elif decision.conviction > 0.3:
            reasons.append(f"信号倾向{'看多' if decision.bull_prob > decision.bear_prob else '看空'}（置信度{decision.conviction:.0%})")
        else:
            reasons.append(f"信号分歧（看多{decision.bull_prob:.0%} / 看空{decision.bear_prob:.0%}），置信度不足")

        # Top signals
        sorted_signals = sorted(
            signals, key=lambda s: s.strength, reverse=True
        )[:3]
        for sig in sorted_signals:
            hist = history.get("signals", {}).get(sig.id, {})
            wr = cls._get_winrate(hist)
            reasons.append(
                f"  [{sig.direction}] {sig.name}（强度{sig.strength:.1f}，历史胜率{wr:.0%})"
            )

        return reasons

    # ── History recording ────────────────────────────────────

    @classmethod
    def record_outcome(cls, signal_id: str, correct: bool):
        """Record whether a signal's prediction was correct.

        Called by PredictionLoop when a prediction is verified.
        """
        db = _load_history()
        if signal_id not in db["signals"]:
            db["signals"][signal_id] = {"wins": 0, "total": 0, "history": []}

        db["signals"][signal_id]["total"] += 1
        if correct:
            db["signals"][signal_id]["wins"] += 1

        # Exponential moving average of recent accuracy
        recent = db["signals"][signal_id].get("history", [])
        recent.append({"correct": correct, "timestamp": datetime.now().isoformat()})
        db["signals"][signal_id]["history"] = recent[-50:]  # keep last 50

        _save_history(db)
        wr = db["signals"][signal_id]["wins"] / db["signals"][signal_id]["total"]
        logger.info(f"Signal {signal_id}: {'correct' if correct else 'incorrect'} "
                    f"(win rate now {wr:.0%})")

    @classmethod
    def get_stats(cls) -> dict:
        """Get decision hub statistics."""
        db = _load_history()
        signals = db.get("signals", {})
        total_signals = len(signals)
        total_events = sum(s.get("total", 0) for s in signals.values())
        total_wins = sum(s.get("wins", 0) for s in signals.values())

        return {
            "tracked_signals": total_signals,
            "total_events": total_events,
            "overall_winrate": round(total_wins / total_events, 3) if total_events > 0 else 0,
            "learned_signals": sum(
                1 for s in signals.values() if s.get("total", 0) >= 5
            ),
        }

    @classmethod
    def get_signal_performance(cls, signal_id: str = "") -> list[dict]:
        """Get performance breakdown by signal."""
        db = _load_history()
        result = []
        for sid, hist in db.get("signals", {}).items():
            if signal_id and sid != signal_id:
                continue
            total = hist.get("total", 0)
            wins = hist.get("wins", 0)
            result.append({
                "signal_id": sid,
                "total": total,
                "wins": wins,
                "winrate": round(wins / total, 3) if total > 0 else 0,
            })
        return sorted(result, key=lambda x: -x["total"])


# ── Convenience: Signal factory ─────────────────────────────

def make_signal(signal_id: str, name: str, direction: str,
                 strength: float, source: str = "pattern",
                 created_at: str = "") -> Signal:
    """Factory for creating signal instances."""
    if not created_at:
        created_at = datetime.now().isoformat()
    return Signal(
        id=signal_id,
        name=name,
        direction=direction,
        strength=min(max(strength, 0.0), 1.0),
        source=source,
        created_at=created_at,
    )


def from_pattern_results(pattern_results: dict,
                          created_at: str = "") -> list[Signal]:
    """Convert Phase B pattern detection results to signals.

    Each PatternResult with non-neutral signal becomes one Signal.
    """
    signals = []
    for pid, pr in pattern_results.items():
        if pr.signal == "neutral":
            continue
        signals.append(make_signal(
            signal_id=pid,
            name=pr.pattern_name,
            direction=pr.signal,
            strength=pr.confidence,
            source="pattern",
            created_at=created_at,
        ))
    return signals


def from_phase_d_predictions(predictions: list[dict]) -> list[Signal]:
    """Convert Phase D active predictions to signals."""
    signals = []
    for pred in predictions:
        if pred.get("status") != "pending":
            continue
        direction = "bull"  # default; could be refined from statement text
        signals.append(make_signal(
            signal_id=pred.get("id", ""),
            name=pred.get("statement", "")[:40],
            direction=direction,
            strength=pred.get("current_confidence", 0.5),
            source="prediction",
            created_at=pred.get("created_at", ""),
        ))
    return signals
