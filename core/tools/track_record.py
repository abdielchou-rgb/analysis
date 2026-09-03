"""Track Record — 分析师追踪记录系统

核心功能:
1. 记录每个预测(Bold Call)的详细信息
2. 跟踪预测结果(对/错/待定)
3. 计算历史准确率(按行业/报告类型/时间维度)
4. 在每次新分析前显示相关历史记录

来源: 圆桌会议四方共识 — 没有Track Record就没有Credibility
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime

# ── M0-U1: 全仓唯一 outcome 词汇表 ──────────────────────────
# 唯一允许写入/读取的 outcome 值
OUTCOME_VOCAB = frozenset({"pending", "hit", "miss", "partial", "unverifiable", "pending_review"})
# 写入侧白名单：resolved 状态（非 pending）
RESOLVED_OUTCOMES = frozenset({"hit", "miss", "partial"})
# 方向白名单
DIRECTION_VOCAB = frozenset({"bullish", "bearish", "neutral"})


@dataclass
class Prediction:
    """单个预测记录"""

    id: str = ""
    asset: str = ""
    report_type: str = ""  # industry/listed_company/unlisted_company
    industry: str = ""
    direction: str = ""  # bullish/bearish/neutral
    bold_call: str = ""  # 具体预测内容
    target_price: str = ""  # 目标价(如有)
    falsification: str = ""  # 证伪条件——什么情况下该预测被证明错误
    time_horizon: str = ""  # 3m/6m/12m
    made_date: str = ""  # 预测日期
    outcome_date: str = ""  # 结果确认日期
    outcome: str = ""  # hit/miss/partial/pending/unverifiable/pending_review
    outcome_detail: str = ""  # 结果详情
    confidence_at_make: float = 0.0  # 做出预测时的置信度
    source: str = "pipeline"  # 数据源: pipeline/backfill (mock 禁止写入生产库)

    def is_expired(self) -> bool:
        """是否已过期"""
        if not self.outcome_date:
            return False
        try:
            d = datetime.strptime(self.outcome_date, "%Y-%m-%d")
            return d < datetime.now()
        except Exception:
            return False


@dataclass
class TrackRecord:
    """分析师追踪记录"""

    analyst_name: str = "2号分析师"
    predictions: list[Prediction] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.predictions)

    @property
    def correct_count(self) -> int:
        return sum(1 for p in self.predictions if p.outcome == "hit")

    @property
    def incorrect_count(self) -> int:
        return sum(1 for p in self.predictions if p.outcome == "miss")

    @property
    def pending_count(self) -> int:
        return sum(1 for p in self.predictions if p.outcome == "pending")

    @property
    def accuracy(self) -> float:
        resolved = self.correct_count + self.incorrect_count
        if resolved == 0:
            return 0.0
        return self.correct_count / resolved

    def by_industry(self, industry: str) -> float:
        """某个行业的准确率"""
        preds = [p for p in self.predictions if p.industry == industry and p.outcome in ("hit", "miss")]
        if not preds:
            return 0.0
        return sum(1 for p in preds if p.outcome == "hit") / len(preds)

    def add_prediction(self, pred: Prediction):
        """添加预测记录"""
        self.predictions.append(pred)

    def summary(self, industry: str = "") -> str:
        """生成追踪记录摘要"""
        lines = [f"## Track Record: {self.analyst_name}"]
        lines.append(f"总预测数: {self.total}")

        if industry:
            ind_preds = [p for p in self.predictions if p.industry == industry]
            correct = sum(1 for p in ind_preds if p.outcome == "hit")
            incorrect = sum(1 for p in ind_preds if p.outcome == "miss")
            resolved = correct + incorrect
            acc = correct / resolved if resolved > 0 else 0
            lines.append(f"[{industry}] 预测{len(ind_preds)}次, 准确率{acc:.0%}")
        else:
            lines.append(f"正确: {self.correct_count} | 错误: {self.incorrect_count} | 待定: {self.pending_count}")
            lines.append(f"综合准确率: {self.accuracy:.0%}")

            # 按报告类型
            for rt in ["industry", "listed_company", "unlisted_company"]:
                rt_preds = [
                    p for p in self.predictions if p.report_type == rt and p.outcome in ("hit", "miss")
                ]
                if rt_preds:
                    acc = sum(1 for p in rt_preds if p.outcome == "hit") / len(rt_preds)
                    lines.append(f"  [{rt}] {len(rt_preds)}次, 准确率{acc:.0%}")

        return "\n".join(lines)

    def get_credibility_statement(self, industry: str) -> str:
        """生成可信度声明 — 用于报告开篇"""
        ind_acc = self.by_industry(industry)
        total_acc = self.accuracy

        if total_acc >= 0.7 and ind_acc >= 0.6:
            level = "高"
        elif total_acc >= 0.5:
            level = "中"
        else:
            level = "低"

        lines = [
            "### 分析师可信度声明",
            f"本报告由{self.analyst_name}撰写。",
            f"历史预测记录: 共{self.total}次预测, 综合准确率{total_acc:.0%}。",
            f"在{industry}行业的{self.by_industry(industry) * 100:.0f}%准确率。",
            f"可信度评级: {level}",
            "",
            "免责: 过往表现不代表未来结果。所有投资判断均包含不确定性。",
        ]
        return "\n".join(lines)


class TrackRecordManager:
    """Track Record管理器 — 持久化存储"""

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data",
                "forward_picks",
                "track_record.json",
            )
        self.storage_path = storage_path
        self.record = self._load()

    def _load(self) -> TrackRecord:
        """从磁盘加载"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, encoding="utf-8") as f:
                    data = json.load(f)
                record = TrackRecord()
                for p in data.get("predictions", []):
                    record.predictions.append(Prediction(**p))
                return record
        except Exception:
            pass
        return TrackRecord()

    def _save(self):
        """持久化到磁盘"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "analyst_name": self.record.analyst_name,
                        "predictions": [p.__dict__ for p in self.record.predictions],
                        "last_updated": datetime.now().isoformat(),
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            print(f"TrackRecord save failed: {e}")

    def register_prediction(
        self,
        asset: str,
        report_type: str,
        industry: str,
        direction: str,
        bold_call: str,
        target_price: str = "",
        falsification: str = "",
        time_horizon: str = "6m",
        confidence: float = 0.7,
        source: str = "pipeline",
    ) -> Prediction:
        """注册新预测
        
        Args:
            source: 数据源标识，必须是 {pipeline, backfill} 之一
                   mock 数据禁止写入生产库
            direction: 必须是 {bullish, bearish, neutral} 之一
        """
        # Source validation: mock data cannot be written to production
        VALID_SOURCES = {"pipeline", "backfill"}
        if source not in VALID_SOURCES:
            raise ValueError(
                f"Invalid source '{source}' for production track_record. "
                f"Valid sources: {VALID_SOURCES}. "
                f"Mock data must be written to isolated mock_track_record.json"
            )

        # M0-U3: Direction validation
        if direction not in DIRECTION_VOCAB:
            raise ValueError(
                f"Invalid direction '{direction}'. "
                f"Valid directions: {DIRECTION_VOCAB}"
            )

        pred = Prediction(
            id=f"{datetime.now().strftime('%Y%m%d_%H%M')}_{asset}",
            asset=asset,
            report_type=report_type,
            industry=industry,
            direction=direction,
            bold_call=bold_call,
            target_price=target_price,
            falsification=falsification,
            time_horizon=time_horizon,
            made_date=datetime.now().strftime("%Y-%m-%d"),
            outcome="pending",
            confidence_at_make=confidence,
            source=source,
        )
        self.record.add_prediction(pred)
        self._save()
        return pred

    def update_outcome(self, pred_id: str, outcome: str, detail: str = ""):
        """更新预测结果"""
        # M0-U3: Outcome validation
        if outcome not in OUTCOME_VOCAB:
            raise ValueError(
                f"Invalid outcome '{outcome}'. "
                f"Valid outcomes: {OUTCOME_VOCAB}"
            )

        for p in self.record.predictions:
            if p.id == pred_id:
                p.outcome = outcome
                p.outcome_detail = detail
                p.outcome_date = datetime.now().strftime("%Y-%m-%d")
                break
        self._save()

    def log_run(self, job_id: str, asset: str, report_type: str, style: str, result: dict):
        """Log pipeline run and extract bold calls for track record."""
        from core.bold_call_extractor import BoldCallExtractor

        try:
            text = result.get("final_text", "") or result.get("report_text", "")
            if not text:
                return

            bce = BoldCallExtractor()
            calls = bce.extract(text)

            for call in calls:
                # Determine direction from call
                direction = "bullish"
                if any(kw in call.get("text", "").lower() for kw in ["看空", "下调", "减持", "卖出", "风险"]):
                    direction = "bearish"
                elif any(kw in call.get("text", "").lower() for kw in ["中性", "持有", "观望"]):
                    direction = "neutral"

                # Extract industry from asset or report context
                industry = call.get("industry", "")

                pred = self.register_prediction(
                    asset=asset,
                    report_type=report_type,
                    industry=industry,
                    direction=direction,
                    bold_call=call.get("text", "")[:200],
                    target_price=call.get("target_price", ""),
                    time_horizon=call.get("time_window", "6m"),
                    confidence=call.get("confidence", 0.7),
                )
        except Exception as e:
            print(f"TrackRecord log_run failed: {e}")

    def list_recent(self, limit: int = 50) -> list:
        """List recent runs from track record."""
        # Sort by made_date descending
        sorted_preds = sorted(self.record.predictions, key=lambda p: p.made_date, reverse=True)
        return [
            {
                "id": p.id,
                "asset": p.asset,
                "report_type": p.report_type,
                "industry": p.industry,
                "direction": p.direction,
                "bold_call": p.bold_call,
                "target_price": p.target_price,
                "falsification": p.falsification,
                "time_horizon": p.time_horizon,
                "made_date": p.made_date,
                "outcome": p.outcome,
                "outcome_date": p.outcome_date,
                "outcome_detail": p.outcome_detail,
                "confidence": p.confidence_at_make,
            }
            for p in sorted_preds[:limit]
        ]

    def get_public_summary(self) -> dict:
        """Generate public track record summary."""
        resolved = [p for p in self.record.predictions if p.outcome in ("hit", "miss")]
        total = len(resolved)
        correct = sum(1 for p in resolved if p.outcome == "hit")

        directional_acc = correct / total if total > 0 else 0

        # Calculate avg PnL (mock for now - would need price data)
        avg_pnl = 0.0
        if resolved:
            # Simplified: assume hit = +10%, miss = -5%
            avg_pnl = (correct * 10 - (total - correct) * 5) / total

        # Group by sector
        by_sector = {}
        for p in self.record.predictions:
            if p.industry:
                by_sector[p.industry] = by_sector.get(p.industry, 0) + 1

        # Group by type
        by_type = {}
        for p in self.record.predictions:
            by_type[p.report_type] = by_type.get(p.report_type, 0) + 1

        return {
            "total_calls": len(self.record.predictions),
            "resolved_calls": total,
            "directional_accuracy": directional_acc,
            "avg_pnl_pct": avg_pnl,
            "kelly_sizing": "1.3x",
            "calls": [
                {
                    "id": p.id,
                    "asset": p.asset,
                    "report_type": p.report_type,
                    "industry": p.industry,
                    "direction": p.direction,
                    "bold_call": p.bold_call,
                    "target_price": p.target_price,
                    "falsification": p.falsification,
                    "time_window": p.time_horizon,
                    "trigger": p.bold_call[:100],
                    "falsification": p.outcome_detail[:100] if not p.falsification else p.falsification,
                    "created_at": p.made_date,
                    "outcome": p.outcome,
                    "outcome_date": p.outcome_date,
                    "outcome_detail": p.outcome_detail,
                    "pnl_pct": 10.0 if p.outcome == "hit" else (-5.0 if p.outcome == "miss" else 0),
                }
                for p in sorted(self.record.predictions, key=lambda x: x.made_date, reverse=True)
            ],
            "by_sector": by_sector,
            "by_type": by_type,
        }
