"""V51 — forward_picks 跟踪系统

抄自 Mrjie7205/serenity-bottleneck-hunter 的 score_tracker.py + forward_picks.csv。

核心改动：
  1. forward_picks.csv 持久化——记录每次输出的判断/目标价/评级
  2. score_tracker — 回测每笔判断的 Alpha（V51 判断 vs 实际市场表现）
  3. 接入 CognitiveBaseline——预测历史从"只写不读"变为"写→读→评分→更新基线"

Mrjie7205 原文：
  "forward_picks.csv 记录每次判定（包括 invalidation 列），
   score_tracker.py 计算 Alpha =（标的实际收益 - 主题 ETF 收益），
   剔除历史种子行防循环论证"

V51 适配:
  追踪的不是"个股买卖建议"，是 Conviction Matrix 的三情景目标价
"""

from __future__ import annotations
import csv
import json
import logging
import os
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.cognitive_baseline import CognitiveBaseline

logger = logging.getLogger("v51.forward_picks")

FORWARD_PICKS_DIR = Path(__file__).resolve().parent.parent / "data" / "forward_picks"


def _ensure_dir():
    FORWARD_PICKS_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════

@dataclass
class ForwardPick:
    """一次判断/预测的记录。对应 Mrjie7205 forward_picks.csv 的一行。"""
    pick_id: str = ""
    asset_code: str = ""
    asset_name: str = ""
    report_type: str = ""            # industry_deep / listed_company / unlisted
    created_at: str = ""

    # 判断内容
    direction: str = ""              # bull / bear / neutral
    base_target: float = 0.0
    bull_target: float = 0.0
    bear_target: float = 0.0
    current_price: float = 0.0       # 判断时的真实股价（元），需真实数据源，不强填
    anchor_nav: float = 0.0          # R64：预测日 qlib 收益率指数净值（验证用锚点）
    conviction: str = ""             # high / medium / low

    # 核心分歧
    core_thesis: str = ""
    key_variable: str = ""
    falsification: str = ""          # 证伪条件

    # 回测结果（score_tracker 写入）
    verified_at: Optional[str] = None
    actual_price: Optional[float] = None      # 验证时的股价
    actual_return: Optional[float] = None     # 判断以来实际收益率
    benchmark_return: Optional[float] = None   # 同期对标收益率
    alpha: Optional[float] = None             # actual_return - benchmark_return
    verification_status: str = "pending"      # pending / hit / miss / partial

    # 失效条件（Mrjie7205 的 invalidation 列）
    invalidation: str = ""
    notes: str = ""


# ═══════════════════════════════════════════════════════════════
# 持久化
# ═══════════════════════════════════════════════════════════════

class ForwardPicksDB:
    """forward_picks.csv 读写器。

    CSV 结构（对标 Mrjie7205）：
      pick_id, asset_code, asset_name, report_type, created_at,
      direction, base_target, conviction, core_thesis,
      falsification, verification_status, actual_return, alpha, invalidation
    """

    HEADERS = [
        "pick_id", "asset_code", "asset_name", "report_type", "created_at",
        "direction", "base_target", "bull_target", "bear_target", "current_price",
        "anchor_nav", "conviction", "core_thesis", "key_variable", "falsification",
        "verified_at", "actual_price", "actual_return", "benchmark_return", "alpha",
        "verification_status", "invalidation", "notes",
    ]

    def __init__(self):
        _ensure_dir()
        self.path = FORWARD_PICKS_DIR / "forward_picks.csv"

    def append(self, pick: ForwardPick) -> bool:
        """追加一条记录。

        R30（2026-08-02 完备计划模块1）：质量门槛——137 条垃圾预测(全neutral/0目标价)
        暴露记录环节不校验。现在：direction≠neutral、base_target>0、conviction 非空
        才允许入库；不合格返回 False 并记录原因。
        """
        # ── R63（2026-08-04）：pick_id 自动生成 + 记录完整度不变量 ──
        # Marvis 审计发现：pick_id 全空、bull/bear_target 全 0 → 无法唯一标识预测、
        # 无法算 alpha，预测闭环"记录有、回测无"。
        # 完整度不变量：缺 pick_id / 缺方向 / 缺目标价 / 缺锚点价 的预测不允许入库。
        if not pick.pick_id:
            # 确定性可读 ID：资产代码-方向-日期-短uuid，保证唯一且可追溯
            pick.pick_id = f"{pick.asset_code or pick.asset_name or 'asset'}-{pick.direction}-{(pick.created_at or 'nodate')[:10]}-{uuid.uuid4().hex[:6]}"

        # ── 质量门槛：防垃圾预测入库 ──
        issues = []
        if pick.direction in ("", "neutral"):
            issues.append("direction 不能为空/neutral")
        if not pick.base_target or float(pick.base_target) <= 0:
            issues.append("base_target 必须>0")
        if pick.conviction not in ("high", "medium", "low"):
            issues.append("conviction 必须为 high/medium/low")
        if not pick.asset_code and not pick.asset_name:
            issues.append("必须有标的代码或名称")
        # R64（2026-08-04 审计修复 P1-008）：bull/bear_target 改为**可选三情景**字段。
        # 旧 R63 强制 bull_target>0 导致 import 造 bull_target=base_target 复制值（审计批评）。
        # 诚实边界（FP2）：单目标价预测不编造独立 bull 档；若提供则须>0。
        if pick.direction == "bull" and pick.bull_target and float(pick.bull_target) <= 0:
            issues.append("bull_target 若提供必须>0")
        if pick.direction == "bear" and pick.bear_target and float(pick.bear_target) <= 0:
            issues.append("bear_target 若提供必须>0")
        # R64（2026-08-04 审计修复）：必须有**净值锚点**（anchor_nav，qlib close 收益率净值）。
        # 旧 R63 强制 current_price（股价语义）导致塞入复权价冒充股价（审计 P0-008）。
        # 净值锚点用于验证收益计算（latest_nav/anchor_nav-1），与股价字段解耦。
        if not pick.anchor_nav or float(pick.anchor_nav) <= 0:
            issues.append("必须提供 anchor_nav 净值锚点（qlib close 收益率净值）")
        if issues:
            logger.warning(f"[FORWARD-PICK-REJECT] {pick.pick_id} 质量不达标: "
                           f"{'; '.join(issues)}")
            return False

        exists = Path(self.path).exists()
        try:
            with open(self.path, "a", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=self.HEADERS)
                if not exists:
                    w.writeheader()
                w.writerow({
                    "pick_id": pick.pick_id,
                    "asset_code": pick.asset_code,
                    "asset_name": pick.asset_name,
                    "report_type": pick.report_type,
                    "created_at": pick.created_at,
                    "direction": pick.direction,
                    "base_target": pick.base_target,
                    "bull_target": pick.bull_target,
                    "bear_target": pick.bear_target,
                    "current_price": pick.current_price,
                    "anchor_nav": pick.anchor_nav,
                    "conviction": pick.conviction,
                    "core_thesis": pick.core_thesis[:100] if pick.core_thesis else "",
                    "key_variable": pick.key_variable[:100] if pick.key_variable else "",
                    "falsification": pick.falsification[:200] if pick.falsification else "",
                    "verified_at": pick.verified_at or "",
                    "actual_price": pick.actual_price or "",
                    "actual_return": pick.actual_return or "",
                    "benchmark_return": pick.benchmark_return or "",
                    "alpha": pick.alpha or "",
                    "verification_status": pick.verification_status,
                    "invalidation": pick.invalidation,
                    "notes": pick.notes,
                })
            logger.info(f"Forward pick saved: {pick.pick_id} ({pick.asset_code})")
            return True
        except Exception as e:
            logger.error(f"Failed to save forward pick: {e}")
            return False

    def purge_low_quality(self) -> int:
        """清理低质量记录（R30：neutral/无目标价/无conviction）。

        返回清理条数。存量 137 条垃圾预测由此清除，避免污染统计。
        """
        picks = self.load_all()
        kept = []
        purged = 0
        for p in picks:
            if (p.direction in ("", "neutral") or p.base_target <= 0
                    or p.conviction not in ("high", "medium", "low")):
                purged += 1
                continue
            kept.append(p)
        if purged:
            self._rewrite_all(kept)
            logger.info(f"[FORWARD-PICK-PURGE] 清理 {purged} 条低质量记录，保留 {len(kept)} 条")
        return purged

    def load_all(self) -> list[ForwardPick]:
        """加载全部记录。"""
        path = Path(self.path)
        if not path.exists():
            return []
        picks = []
        with open(self.path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                picks.append(ForwardPick(
                    pick_id=row.get("pick_id", ""),
                    asset_code=row.get("asset_code", ""),
                    asset_name=row.get("asset_name", ""),
                    report_type=row.get("report_type", ""),
                    created_at=row.get("created_at", ""),
                    direction=row.get("direction", ""),
                    base_target=float(row["base_target"]) if row.get("base_target") else 0.0,
                    bull_target=float(row["bull_target"]) if row.get("bull_target") else 0.0,
                    bear_target=float(row["bear_target"]) if row.get("bear_target") else 0.0,
                    current_price=float(row["current_price"]) if row.get("current_price") else 0.0,
                    anchor_nav=float(row["anchor_nav"]) if row.get("anchor_nav") else 0.0,
                    conviction=row.get("conviction", ""),
                    core_thesis=row.get("core_thesis", ""),
                    key_variable=row.get("key_variable", ""),
                    falsification=row.get("falsification", ""),
                    verified_at=row.get("verified_at") or None,
                    actual_price=float(row["actual_price"]) if row.get("actual_price") else None,
                    actual_return=float(row["actual_return"]) if row.get("actual_return") else None,
                    benchmark_return=float(row["benchmark_return"]) if row.get("benchmark_return") else None,
                    alpha=float(row["alpha"]) if row.get("alpha") else None,
                    verification_status=row.get("verification_status", "pending"),
                    invalidation=row.get("invalidation", ""),
                    notes=row.get("notes", ""),
                ))
        return picks

    def get_pending(self) -> list[ForwardPick]:
        """获取待验证的记录。"""
        return [p for p in self.load_all() if p.verification_status == "pending"]

    def update_verification(self, pick_id: str,
                            actual_price: float, benchmark_return: float) -> bool:
        """更新一条记录的验证结果。

        R64（2026-08-04 审计修复）：废弃 current_price 当股价的口径（审计 P0-008：
        复权价冒充股价致 actual_return 失真）。actual_price 入参语义统一为
        **qlib 收益率指数净值**（与 validate_forward_picks_csv 一致），
        收益用 latest_nav/anchor_nav-1 计算。仅当 actual_price 为净值口径时调用。
        """
        picks = self.load_all()
        updated = False
        for p in picks:
            if p.pick_id == pick_id and p.verification_status == "pending":
                p.actual_price = actual_price
                # 净值口径：anchor_nav 是预测日净值，actual_price 是到期净值
                if p.anchor_nav > 0:
                    p.actual_return = (actual_price - p.anchor_nav) / p.anchor_nav
                p.benchmark_return = benchmark_return
                p.alpha = (p.actual_return or 0) - benchmark_return
                p.verified_at = datetime.now().isoformat()

                # 判定 hit/miss
                if p.direction == "bull" and (p.actual_return or 0) > 0:
                    p.verification_status = "hit"
                elif p.direction == "bear" and (p.actual_return or 0) < 0:
                    p.verification_status = "hit"
                elif p.direction == "bull" and (p.actual_return or 0) < -0.1:
                    p.verification_status = "miss"
                elif p.direction == "bear" and (p.actual_return or 0) > 0.1:
                    p.verification_status = "miss"
                else:
                    p.verification_status = "partial"

                updated = True
                break

        if updated:
            self._rewrite_all(picks)
            # 同步写入 CognitiveBaseline
            self._sync_to_baseline(pick_id)
        return updated

    def _rewrite_all(self, picks: list[ForwardPick]):
        """全量重写 CSV。"""
        with open(self.path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=self.HEADERS)
            w.writeheader()
            for p in picks:
                w.writerow({
                    "pick_id": p.pick_id, "asset_code": p.asset_code,
                    "asset_name": p.asset_name, "report_type": p.report_type,
                    "created_at": p.created_at, "direction": p.direction,
                    "base_target": p.base_target, "bull_target": p.bull_target,
                    "bear_target": p.bear_target, "current_price": p.current_price,
                    "anchor_nav": p.anchor_nav,
                    "conviction": p.conviction, "core_thesis": p.core_thesis[:100],
                    "key_variable": p.key_variable[:100],
                    "falsification": p.falsification[:200],
                    "verified_at": p.verified_at or "",
                    "actual_price": p.actual_price or "",
                    "actual_return": p.actual_return or "",
                    "benchmark_return": p.benchmark_return or "",
                    "alpha": p.alpha or "",
                    "verification_status": p.verification_status,
                    "invalidation": p.invalidation, "notes": p.notes,
                })

    def _sync_to_baseline(self, pick_id: str):
        """将验证结果同步到 CognitiveBaseline。"""
        picks = self.load_all()
        for p in picks:
            if p.pick_id == pick_id and p.asset_code:
                baseline = CognitiveBaseline.load(p.asset_code)
                preds = baseline.get("prediction_history", [])
                for pred in preds:
                    if pred.get("id", "")[:12] == pick_id[:12]:
                        pred["verified_at_6m"] = p.verified_at
                        pred["mid_term_result"] = {
                            "score": 1.0 if p.verification_status == "hit" else 0.0,
                            "alpha": p.alpha,
                        }
                        break
                CognitiveBaseline.save(p.asset_code, baseline)
                break


# ═══════════════════════════════════════════════════════════════
# Score Tracker（Alpha 计算 + 统计）
# ═══════════════════════════════════════════════════════════════

@dataclass
class ScoreCard:
    """整体跟踪评分卡。"""
    total_picks: int = 0
    verified_count: int = 0
    hit_count: int = 0
    miss_count: int = 0
    partial_count: int = 0
    hit_rate: float = 0.0
    avg_alpha: float = 0.0
    best_pick: str = ""
    worst_pick: str = ""


class ScoreTracker:
    """跟踪评分器（对标 Mrjie7205 score_tracker.py）。"""

    def __init__(self):
        self.db = ForwardPicksDB()

    def compute_scorecard(self) -> ScoreCard:
        """计算整体评分卡。"""
        picks = self.db.load_all()
        verified = [p for p in picks if p.verification_status != "pending"]

        card = ScoreCard(
            total_picks=len(picks),
            verified_count=len(verified),
            hit_count=sum(1 for p in verified if p.verification_status == "hit"),
            miss_count=sum(1 for p in verified if p.verification_status == "miss"),
            partial_count=sum(1 for p in verified if p.verification_status == "partial"),
        )

        if card.verified_count > 0:
            card.hit_rate = round(card.hit_count / card.verified_count, 2)

        alphas = [p.alpha for p in verified if p.alpha is not None]
        if alphas:
            card.avg_alpha = round(sum(alphas) / len(alphas), 3)

        if verified:
            best = max(verified, key=lambda p: p.alpha or -999)
            worst = min(verified, key=lambda p: p.alpha or 999)
            card.best_pick = f"{best.asset_code} ({best.alpha:.1%})"
            card.worst_pick = f"{worst.asset_code} ({worst.alpha:.1%})"

        return card

    def report(self) -> str:
        """生成可读的跟踪报告。"""
        card = self.compute_scorecard()
        lines = [
            f"=== Forward Picks 评分卡 ===",
            f"总判断: {card.total_picks}",
            f"已验证: {card.verified_count}",
            f"命中: {card.hit_count}  |  未命中: {card.miss_count}  |  部分: {card.partial_count}",
            f"命中率: {card.hit_rate:.0%}" if card.hit_rate else "命中率: N/A",
            f"平均 Alpha: {card.avg_alpha:+.1%}" if card.avg_alpha else "平均 Alpha: N/A",
        ]
        if card.best_pick:
            lines.append(f"最佳: {card.best_pick}")
        if card.worst_pick:
            lines.append(f"最差: {card.worst_pick}")
        return "\n".join(lines)
