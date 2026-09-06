"""Track Record — 分析师追踪记录系统

核心功能:
1. 记录每个预测(Bold Call)的详细信息
2. 跟踪预测结果(对/错/待定)
3. 计算历史准确率(按行业/报告类型/时间维度)
4. 在每次新分析前显示相关历史记录

来源: 圆桌会议四方共识 — 没有Track Record就没有Credibility
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("2hao.track_record")


def _normalize_call(text: str) -> str:
    """归一化 bold_call 用于幂等/去重判断：折叠空白即可，不做语义改写。"""
    return " ".join((text or "").split())


def _make_prediction_id(asset: str, bold_call: str, taken: set) -> str:
    """生成唯一预测 id：秒级时间戳 + 资产 + 内容摘要。

    旧实现只到分钟精度，同一报告内多个 Bold Call 会撞 id；撞 id 的记录在
    apply_resolved 里只更新第一个匹配，其余永远无法独立结算。摘要保证
    同一秒内不同 call 也唯一；极端撞车再用序号兜底。
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    digest = hashlib.sha1(f"{asset}\x1f{_normalize_call(bold_call)}".encode("utf-8")).hexdigest()[:6]
    candidate = f"{stamp}_{asset}_{digest}"
    n = 1
    while candidate in taken:
        candidate = f"{stamp}_{asset}_{digest}_{n}"
        n += 1
    return candidate


# ── M0-U1: 全仓唯一 outcome 词汇表 ──────────────────────────
# 唯一允许写入/读取的 outcome 值
OUTCOME_VOCAB = frozenset({"pending", "hit", "miss", "partial", "unverifiable", "pending_review"})
# 写入侧白名单：resolved 状态（非 pending）
RESOLVED_OUTCOMES = frozenset({"hit", "miss", "partial"})
# 2026-09-07 R2: partial 语义定死——信用分(供准确率/统计统一取用，消除词表与口径漂移)
OUTCOME_CREDIT = {"hit": 1.0, "partial": 0.5, "miss": 0.0}
# 方向白名单
DIRECTION_VOCAB = frozenset({"bullish", "bearish", "neutral"})


def resolved_outcome_list():
    """供统计统一过滤: 命中/部分/错误(即 RESOLVED_OUTCOMES)。"""
    return sorted(RESOLVED_OUTCOMES)


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
    # P0-2 修复: resolve 写入的真实价格/判据字段——必须落在 dataclass 上，
    # 否则 _load 的 Prediction(**p) 对未知键抛 TypeError 且被 except 吞掉 → 静默清空记录。
    expiry_date: str = ""  # 到期日(2026-09-06 审计补: resolve 依赖)
    price_at_make: float | None = None  # 做出预测时的真实价(无=未取到)
    price_at_expiry: float | None = None  # 到期真实价(无=未取到)
    outcome_reason: str = ""  # unverifiable/错误原因
    judge_ver: str = ""  # 判据版本(alpha/方向/目标价)
    # 2026-09-07 R1: resolve_outcome 写回键补进 dataclass，避免 _load→_save 往返被白名单剥离
    alpha: float | None = None  # 超额收益(相对基准)
    bench: str = "none"  # 基准来源 none/hs300/zz500/...
    return_pct: float | None = None  # 实际收益(%)
    resolved_at: str = ""  # resolve 时间(ISO)

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
    def partial_count(self) -> int:
        return sum(1 for p in self.predictions if p.outcome == "partial")

    @property
    def pending_count(self) -> int:
        return sum(1 for p in self.predictions if p.outcome == "pending")

    @property
    def resolved_count(self) -> int:
        """已结算数 = hit + miss + partial(R2: 词表 RESOLVED_OUTCOMES 一致)。"""
        return sum(1 for p in self.predictions if p.outcome in RESOLVED_OUTCOMES)

    @property
    def accuracy(self) -> float:
        """信用加权准确率: hit=1, partial=0.5, miss=0 (R2: partial 不再游离)。"""
        resolved = [p for p in self.predictions if p.outcome in RESOLVED_OUTCOMES]
        if not resolved:
            return 0.0
        return sum(OUTCOME_CREDIT.get(p.outcome, 0.0) for p in resolved) / len(resolved)

    def by_industry(self, industry: str) -> float:
        """某个行业的准确率(信用加权)"""
        preds = [p for p in self.predictions if p.industry == industry and p.outcome in RESOLVED_OUTCOMES]
        if not preds:
            return 0.0
        return sum(OUTCOME_CREDIT.get(p.outcome, 0.0) for p in preds) / len(preds)

    def add_prediction(self, pred: Prediction):
        """添加预测记录"""
        self.predictions.append(pred)

    def summary(self, industry: str = "") -> str:
        """生成追踪记录摘要"""
        lines = [f"## Track Record: {self.analyst_name}"]
        lines.append(f"总预测数: {self.total}")

        if industry:
            ind_preds = [p for p in self.predictions if p.industry == industry and p.outcome in RESOLVED_OUTCOMES]
            acc = sum(OUTCOME_CREDIT.get(p.outcome, 0.0) for p in ind_preds) / len(ind_preds) if ind_preds else 0
            lines.append(f"[{industry}] 预测{len(ind_preds)}次(已结算), 准确率{acc:.0%}")
        else:
            lines.append(
                f"正确: {self.correct_count} | 部分: {self.partial_count} | "
                f"错误: {self.incorrect_count} | 待定: {self.pending_count}"
            )
            lines.append(f"综合准确率(信用加权): {self.accuracy:.0%}")

            # 按报告类型
            for rt in ["industry", "listed_company", "unlisted_company"]:
                rt_preds = [p for p in self.predictions if p.report_type == rt and p.outcome in RESOLVED_OUTCOMES]
                if rt_preds:
                    acc = sum(OUTCOME_CREDIT.get(p.outcome, 0.0) for p in rt_preds) / len(rt_preds)
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
                valid_fields = set(Prediction.__dataclass_fields__.keys())
                for p in data.get("predictions", []):
                    # 只取 dataclass 已知字段，未知键(未来 schema 演进)不抛错、不静默清空
                    p = {k: v for k, v in p.items() if k in valid_fields}
                    record.predictions.append(Prediction(**p))
                return record
        except Exception as e:
            logger.warning("TrackRecord load failed (%s) — returning empty; data NOT wiped on disk", e)
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

    def apply_resolved(self, resolved: list[dict]) -> int:
        """SSOT 单写门面(2026-09-07 T1): 把 resolve 结果写回 dataclass 并落盘。

        - 只允许写 dataclass 已知字段(store of record = Prediction);未知键丢弃并告警,
          与 _load 的容错一致(不会静默丢数据, 而是把"该补 schema"暴露为 warning)。
        - outcome 必须 ∈ OUTCOME_VOCAB, 否则拒绝该条。
        - 本方法是唯一允许的外部批量写入路径; 调用方不再直接 json.dump track_record。
        """
        if not resolved:
            return 0
        valid_fields = set(Prediction.__dataclass_fields__.keys())
        updated = 0
        for item in resolved:
            pred_id = item.get("id")
            if not pred_id:
                continue
            outcome = item.get("outcome")
            if outcome is not None and outcome not in OUTCOME_VOCAB:
                logger.warning("[SSOT] apply_resolved rejected id=%s outcome=%r (not in vocab)", pred_id, outcome)
                continue
            # 2026-09-07 T2 (make illegal states unrepresentable):
            # 已结算(hit/miss/partial)必须携带真实到期价与判据版本——无价即不构成"已结算"。
            if outcome in RESOLVED_OUTCOMES:
                if item.get("price_at_expiry") is None or not item.get("judge_ver"):
                    logger.warning(
                        "[SSOT] apply_resolved rejected id=%s outcome=%r "
                        "(resolved 必须带 price_at_expiry+judge_ver, 否则标 unverifiable)",
                        pred_id,
                        outcome,
                    )
                    continue
            matches = [p for p in self.record.predictions if p.id == pred_id]
            if len(matches) > 1:
                logger.warning(
                    "[SSOT] duplicate id=%s has %d rows — apply only updates first; "
                    "run scripts/dedup_track_record.py --apply 修复历史数据",
                    pred_id,
                    len(matches),
                )
            if not matches:
                continue
            target = matches[0]
            unknown = set(item) - valid_fields - {"expiry_date"}
            if unknown:
                logger.warning("[SSOT] apply_resolved dropped unknown keys for %s: %s", pred_id, sorted(unknown))
            for k, v in item.items():
                if k in valid_fields:
                    setattr(target, k, v)
            updated += 1
        if updated:
            self._save()
        return updated

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
            raise ValueError(f"Invalid direction '{direction}'. Valid directions: {DIRECTION_VOCAB}")

        # 2026-09-07 T3: 幂等注册——同一 (asset, 归一化 bold_call, made_date,
        # direction, time_horizon, target_price) 已存在则直接返回现有记录。
        # 根因: orchestrator(extract_and_register) 与 web log_run 对同一报告
        # 走两条注册路径，同日内重复产生整条重复记录，污染准确率分母。
        made_date = datetime.now().strftime("%Y-%m-%d")
        norm_call = _normalize_call(bold_call)
        existing = next(
            (
                p
                for p in self.record.predictions
                if p.asset == asset
                and p.made_date == made_date
                and p.direction == direction
                and p.time_horizon == time_horizon
                and p.target_price == (target_price or "")
                and _normalize_call(p.bold_call) == norm_call
            ),
            None,
        )
        if existing is not None:
            logger.info(
                "[TRACK] duplicate registration suppressed asset=%s date=%s id=%s",
                asset,
                made_date,
                existing.id,
            )
            return existing

        taken = {p.id for p in self.record.predictions}
        pred = Prediction(
            id=_make_prediction_id(asset, bold_call, taken),
            asset=asset,
            report_type=report_type,
            industry=industry,
            direction=direction,
            bold_call=bold_call,
            target_price=target_price,
            falsification=falsification,
            time_horizon=time_horizon,
            made_date=made_date,
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
            raise ValueError(f"Invalid outcome '{outcome}'. Valid outcomes: {OUTCOME_VOCAB}")

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

    def _real_pnl_pct(self, p: Prediction) -> float | None:
        """由真实价格计算单条持有期收益率(%); 缺真实价或价非正返回 None(fail-closed, 不编造)。"""
        if p.price_at_make is None or p.price_at_expiry is None:
            return None
        if p.price_at_make <= 0 or p.price_at_expiry <= 0:
            # R3(2026-09-07): expiry<=0(退市/归零)同样 fail-closed, 否则除零/误导
            return None
        return round((p.price_at_expiry - p.price_at_make) / p.price_at_make * 100.0, 2)

    def get_public_summary(self) -> dict:
        """Generate public track record summary.

        P0-2 (2026-09-06 audit) 修复:
        - avg_pnl / pnl_pct 只从 price_at_make/price_at_expiry 真实价计算;
          无真实价一律 None(不返回 0/假 ±10%), 对外面标记需真价结算。
        - 移除伪造字面量 kelly_sizing。
        """
        # R2(2026-09-07): resolved 统一按 RESOLVED_OUTCOMES(hit/miss/partial),
        # 准确率用 OUTCOME_CREDIT 信用加权(partial=0.5), 消除词表与统计口径漂移。
        resolved = [p for p in self.record.predictions if p.outcome in RESOLVED_OUTCOMES]
        total = len(resolved)
        directional_acc = sum(OUTCOME_CREDIT.get(p.outcome, 0.0) for p in resolved) / total if total > 0 else 0

        # 真实 PnL: 只有带真实价的已结算预测参与
        pnl_vals = [v for v in (self._real_pnl_pct(p) for p in resolved) if v is not None]
        avg_pnl = round(sum(pnl_vals) / len(pnl_vals), 2) if pnl_vals else None

        # Group by sector
        by_sector = {}
        for p in self.record.predictions:
            if p.industry:
                by_sector[p.industry] = by_sector.get(p.industry, 0) + 1

        # Group by type
        by_type = {}
        for p in self.record.predictions:
            by_type[p.report_type] = by_type.get(p.report_type, 0) + 1

        def _call_row(p: Prediction) -> dict:
            falsification = p.falsification if p.falsification else (p.outcome_detail[:100] if p.outcome_detail else "")
            return {
                "id": p.id,
                "asset": p.asset,
                "report_type": p.report_type,
                "industry": p.industry,
                "direction": p.direction,
                "bold_call": p.bold_call,
                "target_price": p.target_price,
                "falsification": falsification,  # 单键——修复原 dict 重复 key 被静默覆盖
                "time_window": p.time_horizon,
                "trigger": p.bold_call[:100],
                "created_at": p.made_date,
                "outcome": p.outcome,
                "outcome_date": p.outcome_date,
                "outcome_detail": p.outcome_detail,
                "pnl_pct": self._real_pnl_pct(p),  # None=无真实价, 绝不假造 ±10/-5
                "price_at_make": p.price_at_make,
                "price_at_expiry": p.price_at_expiry,
            }

        return {
            "total_calls": len(self.record.predictions),
            "resolved_calls": total,
            "directional_accuracy": directional_acc,
            "avg_pnl_pct": avg_pnl,
            "pnl_basis_note": "avg_pnl 仅统计带真实价格(price_at_make/expiry)的已结算预测；无真价记录不参与、显示 None。",
            "kelly_sizing": None,  # 移除假字面量 1.3x；待真实 PnL 序列后由仓位模型计算
            "calls": [_call_row(p) for p in sorted(self.record.predictions, key=lambda x: x.made_date, reverse=True)],
            "by_sector": by_sector,
            "by_type": by_type,
        }
