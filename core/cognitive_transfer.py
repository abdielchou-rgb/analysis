"""
WIP — Work In Progress: This module depends on core.cognitive_baseline.CognitiveBaseline
which does not yet exist. All public methods are wrapped with try/except ImportError guards.
Not connected to the pipeline. Do not use in production.

跨标的认知迁移——超级分析师的网络效应能力。
基于业务模式/财务特征/竞争结构的相似性，将一只标的上验证的模式迁移到类似标的。

用例：
  - "五粮液2019年渠道改革的利润轨迹" → 迁移到"茅台当前渠道改革"分析
  - "宁德时代2023年产能过剩信号" → 迁移到"其他电池企业"监测
  - "白酒行业ROE驱动力分解" → 迁移到"啤酒行业"分析框架

相似性维度：
  - 行业分类（GICS三级）
  - 财务特征（ROE/毛利率/增速集群）
  - 竞争结构（集中度/进入壁垒类型）
  - 生命周期阶段（成长期/成熟期/衰退期）
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Optional  # noqa: F401  (dead-import debt)

logger = logging.getLogger("v51.cognitive_transfer")

TRANSFER_DB = Path(__file__).resolve().parent.parent / "data" / "cognitive_transfer.json"

# ── WIP guard: CognitiveBaseline does not exist yet ──────────
_has_baseline = False
_CognitiveBaseline = None
try:
    from core.cognitive_baseline import CognitiveBaseline as _CognitiveBaseline  # type: ignore

    _has_baseline = True
except ImportError:
    logger.warning("core.cognitive_baseline not available — CognitiveTransfer is WIP, all methods return empty lists")


def _require_baseline():
    """Raise if CognitiveBaseline is not available."""
    if not _has_baseline:
        raise ImportError("core.cognitive_baseline is required but not available — CognitiveTransfer is WIP")


# ── Industry similarity (pre-coded, can be extended) ─────────

INDUSTRY_CLUSTERS = {
    "白酒": ["白酒", "啤酒", "葡萄酒", "食品饮料"],
    "新能源": ["动力电池", "光伏", "风电", "储能"],
    "半导体": ["芯片设计", "芯片制造", "封测", "半导体设备"],
    "互联网": ["电商", "社交", "搜索", "云计算"],
    "金融": ["银行", "证券", "保险", "金融科技"],
    "医药": ["创新药", "医疗器械", "CXO", "中药"],
    "消费电子": ["手机", "面板", "可穿戴", "智能家居"],
}


# ── Similarity scoring ───────────────────────────────────────


def compute_similarity(code_a: str, code_b: str, baseline_a: dict, baseline_b: dict) -> float:
    """Compute similarity score (0.0-1.0) between two assets.

    Factors:
      - Industry cluster match: 0.2
      - Financial profile similarity: 0.4
      - Business model type match: 0.4
    """
    score = 0.0

    # 1. Industry cluster (0-0.2)
    industry_a = baseline_a.get("name", "")
    industry_b = baseline_b.get("name", "")
    for cluster, members in INDUSTRY_CLUSTERS.items():
        a_in = any(m in industry_a for m in members)
        b_in = any(m in industry_b for m in members)
        if a_in and b_in:
            score += 0.2
            break

    # 2. Financial profile (0-0.4) — from key_variables
    vars_a = set(baseline_a.get("key_variables", {}).keys())
    vars_b = set(baseline_b.get("key_variables", {}).keys())
    if vars_a and vars_b:
        overlap = len(vars_a & vars_b) / max(len(vars_a | vars_b), 1)
        score += overlap * 0.4

    # 3. Active hypotheses similarity (0-0.4)
    hyps_a = {h.get("statement", "") for h in baseline_a.get("active_hypotheses", [])}
    hyps_b = {h.get("statement", "") for h in baseline_b.get("active_hypotheses", [])}
    if hyps_a and hyps_b:
        # Simple word overlap on hypothesis statements
        words_a = set(" ".join(hyps_a).split())
        words_b = set(" ".join(hyps_b).split())
        if words_a and words_b:
            overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
            score += overlap * 0.4

    return round(min(score, 1.0), 3)


# ── Transfer DB ──────────────────────────────────────────────


def _load_transfers() -> dict:
    if TRANSFER_DB.exists():
        try:
            return json.loads(TRANSFER_DB.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"version": "V51.3", "transfer_map": {}, "similarity_scores": []}


def _save_transfers(data: dict):
    TRANSFER_DB.parent.mkdir(parents=True, exist_ok=True)
    TRANSFER_DB.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Core API ─────────────────────────────────────────────────


class CognitiveTransfer:
    """Cross-asset cognitive pattern transfer. (WIP — requires CognitiveBaseline)"""

    @staticmethod
    def find_similar(code: str, top_n: int = 5) -> list[dict]:
        """Find the most cognitively similar assets.

        Args:
            code: Source asset code
            top_n: Number of similar assets to return

        Returns:
            List of {"code": str, "name": str, "similarity": float}
        """
        try:
            _require_baseline()
        except ImportError:
            logger.warning("CognitiveTransfer.find_similar: baseline unavailable, returning []")
            return []
        source = _CognitiveBaseline.load(code)
        if not source.get("key_variables"):
            logger.warning(f"No baseline for {code}, cannot find similar")
            return []

        candidates = []
        for other_code in _CognitiveBaseline.list_all():
            if other_code == code:
                continue
            other = _CognitiveBaseline.load(other_code)
            if not other.get("key_variables"):
                continue
            sim = compute_similarity(code, other_code, source, other)
            if sim > 0.1:  # Minimum threshold
                candidates.append(
                    {
                        "code": other_code,
                        "name": other.get("name", other_code),
                        "similarity": sim,
                    }
                )

        # Sort and cache
        candidates.sort(key=lambda x: -x["similarity"])
        top = candidates[:top_n]

        # Cache in transfer DB
        db = _load_transfers()
        db["similarity_scores"].append(
            {
                "source": code,
                "timestamp": datetime.datetime.now().isoformat(),
                "results": top,
            }
        )
        db["similarity_scores"] = db["similarity_scores"][-100:]  # keep last 100
        _save_transfers(db)

        return top

    @staticmethod
    def transfer_pattern(pattern_id: str, source_code: str, target_code: str, pattern_data: dict) -> dict:
        """Transfer a verified pattern from source to target asset.

        Args:
            pattern_id: Pattern type (growth_inflection, margin_structure, etc.)
            source_code: Source asset where pattern was verified
            target_code: Target asset to apply pattern to
            pattern_data: Pattern result data

        Returns:
            Transfer record.
        """
        db = _load_transfers()
        transfer = {
            "pattern_id": pattern_id,
            "source": source_code,
            "target": target_code,
            "pattern_data": pattern_data,
            "created_at": datetime.datetime.now().isoformat(),
            "verified": False,
            "target_applied": False,
        }

        transfer_id = f"tfr_{source_code}_{target_code}_{pattern_id}"
        db.setdefault("transfer_map", {})[transfer_id] = transfer
        _save_transfers(db)
        logger.info(f"Pattern {pattern_id} transferred: {source_code} → {target_code}")
        return transfer

    @staticmethod
    def get_relevant_patterns(code: str, pattern_type: str = "") -> list[dict]:
        """Get patterns from similar assets that may apply to this code.

        Args:
            code: Target asset code
            pattern_type: Optional filter (growth_inflection, margin_structure, etc.)

        Returns:
            List of transfer candidates with similarity score.
        """
        try:
            _require_baseline()
        except ImportError:
            return []

        similar = CognitiveTransfer.find_similar(code, top_n=3)
        relevant = []

        for sim in similar:
            other_baseline = _CognitiveBaseline.load(sim["code"])
            patterns = other_baseline.get("known_patterns", [])
            for pattern in patterns:
                if pattern_type and pattern.get("type") != pattern_type:
                    continue
                relevant.append(
                    {
                        "source_code": sim["code"],
                        "source_name": sim.get("name", sim["code"]),
                        "similarity": sim["similarity"],
                        "pattern": pattern,
                    }
                )

        return relevant

    @staticmethod
    def recommend_hypothesis(code: str) -> list[dict]:
        """Suggest hypotheses based on patterns from similar assets.

        If a hypothesis was confirmed in a similar asset, suggest testing
        it in this asset.
        """
        try:
            _require_baseline()
        except ImportError:
            return []

        similar = CognitiveTransfer.find_similar(code, top_n=3)
        recommendations = []

        for sim in similar:
            other_baseline = _CognitiveBaseline.load(sim["code"])
            for hyp in other_baseline.get("active_hypotheses", []):
                if hyp.get("verified"):
                    recommendations.append(
                        {
                            "hypothesis": hyp.get("statement", ""),
                            "source_code": sim["code"],
                            "source_name": sim.get("name", sim["code"]),
                            "similarity": sim["similarity"],
                            "confidence_transfer": sim["similarity"] * 0.5,
                            "note": f"已在{sim.get('name', sim['code'])}上验证，可考虑在本标的上检验",
                        }
                    )

        return recommendations

    @staticmethod
    def stats() -> dict:
        """Get transfer statistics."""
        db = _load_transfers()
        transfers = db.get("transfer_map", {})
        scores = db.get("similarity_scores", [])
        return {
            "total_transfers": len(transfers),
            "total_similarity_runs": len(scores),
            "unique_patterns": len(set(t.get("pattern_id", "") for t in transfers.values())),
        }
