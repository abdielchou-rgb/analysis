"""Prediction backtest dashboard. Wraps existing ForwardPicksDB + TemporalVerifier."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("v52.calibration")

try:
    from core.forward_picks import ForwardPick, ForwardPicksDB  # noqa: F401  (availability probe)

    _HAS_FP = True
except ImportError:
    _HAS_FP = False
    ForwardPicksDB = None

try:
    from core.temporal_verifier import TemporalVerifier

    _HAS_TV = True
except ImportError:
    _HAS_TV = False
    TemporalVerifier = None


@dataclass
class SectorAccuracy:
    sector: str = ""
    correct: int = 0
    total: int = 0
    accuracy: float = 0.0


@dataclass
class TimeframeAccuracy:
    timeframe: str = ""
    correct: int = 0
    total: int = 0
    accuracy: float = 0.0


@dataclass
class BiasReport:
    overall_bias_pct: float = 0.0  # positive = bullish bias
    sector_biases: dict[str, float] = field(default_factory=dict)
    warning_sectors: list[str] = field(default_factory=list)
    is_significant: bool = False


@dataclass
class ValuationBias:
    avg_deviation_pct: float = 0.0  # negative = overestimated
    median_deviation_pct: float = 0.0
    suggested_calibration: float = 1.0
    sample_size: int = 0


@dataclass
class CalibrationSuggestion:
    area: str = ""
    finding: str = ""
    suggestion: str = ""
    priority: str = "medium"  # high/medium/low


class CalibrationDashboard:
    """Prediction backtest and calibration dashboard."""

    def __init__(self):
        self.db = ForwardPicksDB() if _HAS_FP else None
        self.verifier = TemporalVerifier() if _HAS_TV else None

    def accuracy_by_sector(self) -> list[SectorAccuracy]:
        """Break down prediction accuracy by sector/industry."""
        if not self.db:
            return [SectorAccuracy("N/A", 0, 0, 0.0)]

        picks = self._get_matured_picks()
        sectors: dict[str, dict] = {}
        for p in picks:
            sector = getattr(p, "sector", getattr(p, "asset_sector", "unknown")) or "unknown"
            correct = getattr(p, "verified", None)
            if correct is None:
                continue
            if sector not in sectors:
                sectors[sector] = {"correct": 0, "total": 0}
            sectors[sector]["total"] += 1
            if correct:
                sectors[sector]["correct"] += 1

        results = []
        for sector, data in sorted(sectors.items()):
            results.append(
                SectorAccuracy(
                    sector=sector,
                    correct=data["correct"],
                    total=data["total"],
                    accuracy=round(data["correct"] / max(data["total"], 1), 3),
                )
            )
        return results

    def accuracy_by_timeframe(self) -> list[TimeframeAccuracy]:
        """Break down by 3m/6m/12m time windows."""
        if not self.db:
            return [TimeframeAccuracy("N/A", 0, 0, 0.0)]

        picks = self._get_matured_picks()
        tfs: dict[str, dict] = {
            "3m": {"correct": 0, "total": 0},
            "6m": {"correct": 0, "total": 0},
            "12m": {"correct": 0, "total": 0},
            "other": {"correct": 0, "total": 0},
        }

        for p in picks:
            tw = getattr(p, "time_window", "") or ""
            correct = getattr(p, "verified", None)
            if correct is None:
                continue
            key = "other"
            if "3" in tw or "3m" in tw or "quarter" in tw.lower():
                key = "3m"
            elif "6" in tw or "6m" in tw or "half" in tw.lower():
                key = "6m"
            elif "12" in tw or "12m" in tw or "year" in tw.lower():
                key = "12m"
            tfs[key]["total"] += 1
            if correct:
                tfs[key]["correct"] += 1

        return [
            TimeframeAccuracy(k, v["correct"], v["total"], round(v["correct"] / max(v["total"], 1), 3))
            for k, v in tfs.items()
        ]

    def systematic_bias(self) -> BiasReport:
        """Detect systematic bullish/bearish bias."""
        report = BiasReport()
        if not self.db:
            return report

        picks = self._get_matured_picks()
        sector_dirs: dict[str, list[float]] = {}
        for p in picks:
            direction = getattr(p, "direction", "") or ""
            correct = getattr(p, "verified", None)
            if correct is None:
                continue
            sector = getattr(p, "sector", "unknown") or "unknown"

            # direction as +1 (bull), -1 (bear), 0 (neutral)
            d_val = 0
            if direction in ("bull", "买入", "增持", "看多"):
                d_val = 1
            elif direction in ("bear", "卖出", "减持", "看空"):
                d_val = -1

            if sector not in sector_dirs:
                sector_dirs[sector] = []
            # If prediction was correct, direction was validated; if wrong, invert
            sector_dirs[sector].append(d_val if correct else -d_val)

        sector_biases = {}
        total_bias = 0.0
        total_count = 0
        for sector, vals in sector_dirs.items():
            avg_bias = sum(vals) / len(vals) if vals else 0.0
            sector_biases[sector] = round(avg_bias, 3)
            total_bias += sum(vals)
            total_count += len(vals)
            if abs(avg_bias) > 0.15:
                report.warning_sectors.append(sector)

        report.overall_bias_pct = round(total_bias / max(total_count, 1) * 100, 1)
        report.sector_biases = sector_biases
        report.is_significant = any(abs(v) > 0.15 for v in sector_biases.values())
        return report

    def valuation_bias(self) -> ValuationBias:
        """DCF target price vs actual price deviation analysis."""
        result = ValuationBias()
        if not self.db:
            return result

        picks = self._get_matured_picks()
        deviations = []
        for p in picks:
            target = getattr(p, "base_target", None) or getattr(p, "target_price", None)
            actual = getattr(p, "actual_price", None)
            if target and actual and target > 0:
                deviations.append((actual - target) / target)

        if not deviations:
            return result

        result.sample_size = len(deviations)
        result.avg_deviation_pct = round(sum(deviations) / len(deviations) * 100, 1)
        sorted_d = sorted(deviations)
        result.median_deviation_pct = round(sorted_d[len(sorted_d) // 2] * 100, 1) if sorted_d else 0.0

        # Suggested calibration: if avg_deviation is -8.7% (overestimate),
        # multiply future DCF by 1/(1-0.087) ≈ 1.095 to correct
        if result.avg_deviation_pct < 0:
            result.suggested_calibration = round(1 / (1 + result.avg_deviation_pct / 100), 3)
        elif result.avg_deviation_pct > 0:
            result.suggested_calibration = round(1 / (1 + result.avg_deviation_pct / 100), 3)
        else:
            result.suggested_calibration = 1.0

        return result

    def suggest_calibration(self) -> list[CalibrationSuggestion]:
        """Generate actionable calibration suggestions."""
        suggestions = []

        # 1. Overall accuracy
        sector_acc = self.accuracy_by_sector()
        all_picks = sum(s.total for s in sector_acc)
        all_correct = sum(s.correct for s in sector_acc)
        if all_picks > 0:
            overall = all_correct / all_picks
            if overall < 0.5:
                suggestions.append(
                    CalibrationSuggestion(
                        area="整体",
                        priority="high",
                        finding=f"总体准确率 {overall:.0%} 低于 50%",  # intentional: < 0.5
                        suggestion="检查方法论执行质量，重点排查 hypothesis 是否正确",
                    )
                )

        # 2. Sector bias
        bias = self.systematic_bias()
        for sector in bias.warning_sectors:
            b = bias.sector_biases.get(sector, 0)
            direction = "bullish" if b > 0 else "bearish"
            suggestions.append(
                CalibrationSuggestion(
                    area=sector,
                    priority="medium",
                    finding=f"对 {sector} 的 {direction} 倾向 {abs(b):.1%}",
                    suggestion=f"复盘 {sector} 的假设链条，看是否忽略了某个持续性变量",
                )
            )

        # 3. Valuation bias
        val_bias = self.valuation_bias()
        if val_bias.sample_size >= 5 and abs(val_bias.avg_deviation_pct) > 5:
            suggestions.append(
                CalibrationSuggestion(
                    area="估值",
                    priority="high" if abs(val_bias.avg_deviation_pct) > 10 else "medium",
                    finding=f"DCF 目标价 vs 实现价偏差 {val_bias.avg_deviation_pct:+.1f}% (样本 {val_bias.sample_size})",
                    suggestion=f"在 ComputeEngine DCF 输入层应用校准系数 {val_bias.suggested_calibration}x",
                )
            )

        return suggestions

    def full_report(self) -> str:
        """Generate the full calibration dashboard output."""
        lines = ["═" * 50, "  V52 预测校准仪表盘", "═" * 50, ""]

        # Overall
        sector_acc = self.accuracy_by_sector()
        total = sum(s.total for s in sector_acc)
        correct = sum(s.correct for s in sector_acc)
        overall = round(correct / max(total, 1), 3) if total > 0 else 0
        lines.append(f"  总体准确率: {overall:.1%} (基于 {total} 个已到期预测)")
        lines.append("")

        # By sector
        lines.append("  按行业:")
        for s in sector_acc:
            if s.total > 0:
                lines.append(f"    {s.sector:15s} {s.accuracy:.1%} ({s.correct}/{s.total})")
        lines.append("")

        # By timeframe
        tf_acc = self.accuracy_by_timeframe()
        lines.append("  按时间跨度:")
        for t in tf_acc:
            if t.total > 0:
                lines.append(f"    {t.timeframe:8s} {t.accuracy:.1%} ({t.correct}/{t.total})")
        lines.append("")

        # Bias
        bias = self.systematic_bias()
        lines.append(f"  系统偏差: {bias.overall_bias_pct:+.1f}%")
        for sector in sorted(bias.warning_sectors):
            b = bias.sector_biases.get(sector, 0)
            lines.append(f"    {sector} {b:+.1%} {'(需警惕)' if abs(b) > 0.2 else ''}")
        lines.append("")

        # Valuation
        val = self.valuation_bias()
        if val.sample_size > 0:
            lines.append("  估值校准:")
            lines.append(f"    DCF 目标价 vs 实现价平均偏差 {val.avg_deviation_pct:+.1f}%")
            if val.suggested_calibration != 1.0:
                lines.append(f"    建议校准系数: {val.suggested_calibration}x")
        lines.append("")

        # Suggestions
        suggestions = self.suggest_calibration()
        if suggestions:
            lines.append("  改进建议:")
            for s in suggestions:
                tag = "!!" if s.priority == "high" else "!" if s.priority == "medium" else "-"
                lines.append(f"    [{tag}] {s.area}: {s.finding}")
                lines.append(f"          {s.suggestion}")

        lines.append("═" * 50)
        return "\n".join(lines)

    # << IronGate Calibration >>

    def _get_calib_dir(self):
        p = Path("output/calibration")
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _load_runs(self, report_type):
        p = self._get_calib_dir() / (report_type + "_runs.json")
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save_runs(self, report_type, runs):
        p = self._get_calib_dir() / (report_type + "_runs.json")
        p.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")

    def log_run(self, report_type, asset, gate_score, failures, suggestions):
        """Record one IronGate evaluation run."""
        runs = self._load_runs(report_type)
        from datetime import datetime

        record = {
            "timestamp": datetime.now().isoformat(),
            "report_type": report_type,
            "asset": asset,
            "gate_score": round(gate_score, 4),
            "failures": [
                {"name": f.name, "score": f.score, "details": f.details}
                if hasattr(f, "name")
                else {"name": str(f), "score": 0.0, "details": ""}
                for f in (failures or [])
            ],
            "suggestions": suggestions or [],
        }
        runs.append(record)
        self._save_runs(report_type, runs)

    def get_trend(self, report_type, last_n=10):
        """Get gate score trend for last N runs."""
        runs = self._load_runs(report_type)
        return [{"timestamp": r["timestamp"], "gate_score": r["gate_score"]} for r in runs[-last_n:]]

    def get_frequent_failures(self, report_type, top_k=5):
        """Get most common failure check names."""
        runs = self._load_runs(report_type)
        from collections import Counter

        counter = Counter()
        for r in runs:
            for f in r.get("failures", []):
                counter[f.get("name", "unknown")] += 1
        return [{"name": name, "count": count} for name, count in counter.most_common(top_k)]

    def get_improvement_suggestions(self, report_type):
        """Get recurring suggestions from history."""
        runs = self._load_runs(report_type)
        if not runs:
            return []
        from collections import Counter

        counter = Counter()
        for r in runs:
            for s in r.get("suggestions", []):
                counter[s] += 1
        top = counter.most_common(3)
        return [s + " (appeared " + str(count) + "x)" for s, count in top]

    # ─── helpers ───

    def _get_matured_picks(self) -> list:
        """Get picks that have reached their maturity date."""
        if not self.db:
            return []
        try:
            all_picks = getattr(self.db, "load", lambda: [])()
            if not all_picks:
                return []
            now = datetime.now()
            matured = []
            for p in all_picks:
                deadline = getattr(p, "deadline", None) or getattr(p, "maturity_date", None)
                if deadline and isinstance(deadline, datetime) and deadline <= now:
                    matured.append(p)
            return matured
        except Exception as e:
            logger.warning(f"Failed to load matured picks: {e}")
            return []
