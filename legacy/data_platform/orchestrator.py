"""
V53 KnowledgeOrchestrator — 数据管线升级版

V53 变更:
1. _load_data() 现在调用 consensus_connector 获取一致预期数据
2. _load_data() 调用 akshare_connector 获取实时行情
3. 新增 _enrich_with_consensus() 和 _enrich_with_realtime() 方法
4. 数据缺口检测现在基于真实数据状态
"""

from __future__ import annotations
import logging
import json
from pathlib import Path
from typing import Optional
import yaml
from core.models import (
    WritingBrief,
    KnowledgePackage,
    DataPoint,
    FinancialSummary,
    SACEntry,
    StyleProfile,
    EvidenceItem,
    EvidenceLevel,
    ReportType,
)

V50_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger("v51.data.orchestrator")

# Layer 4: 尝试导入实时数据连接器
_HAS_CONSENSUS = False
_HAS_AKSHARE = False
_HAS_SINA = False
try:
    from legacy.data_platform.consensus_connector import fetch_consensus

    _HAS_CONSENSUS = True
except ImportError:
    logger.warning("consensus_connector not available")

try:
    from legacy.data_platform.akshare_connector import fetch_financials as _fetch_financials

    _HAS_AKSHARE = True
except ImportError:
    logger.warning("akshare_connector not available")

try:
    from legacy.data_platform.sina_connector import get_sina_connector

    _HAS_SINA = True
except ImportError:
    logger.warning("sina_connector not available")


class SACLoader:
    def __init__(self, sac_dir: Optional[Path] = None):
        self.sac_dir = sac_dir or V50_ROOT / "core" / "sacs"

    def load(self, report_type: ReportType) -> Optional[SACEntry]:
        mapping = {
            ReportType.INDUSTRY_DEEP: "sac_industry_deep",
            ReportType.LISTED_COMPANY: "sac_listed_company",
            ReportType.UNLISTED_COMPANY: "sac_unlisted_company",
            ReportType.EARNINGS_NOTES: "sac_listed_company",
        }
        sac_id = mapping.get(report_type)
        return self._load_file(sac_id) if sac_id else None

    def _load_file(self, sac_id: str) -> Optional[SACEntry]:
        for ext in [".yaml", ".yml"]:
            path = self.sac_dir / f"{sac_id}{ext}"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return SACEntry(
                    sac_id=data.get("id", sac_id),
                    name=data.get("name", ""),
                    applies_to=data.get("applies_to", []),
                    required_dimensions=data.get("required_dimensions", data.get("required_questions", [])),
                    evidence_requirements=data.get("evidence_requirements", {}),
                    forbidden_patterns=data.get("forbidden_patterns", []),
                    pre_workflow=data.get("pre_workflow", []),
                    verification_rules=data.get("verification"),
                    logic_chain=data.get("logic_chain", []),
                )
        return None


class StyleLoader:
    def __init__(self, style_dir: Optional[Path] = None):
        self.style_dir = style_dir or V50_ROOT / "core" / "styles"

    def load(self, style_id: str) -> Optional[StyleProfile]:
        path = self.style_dir / f"{style_id}.yaml"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return StyleProfile(
            style_id=style_id,
            name=data.get("name", style_id),
            colors=data.get("colors", {}),
            typography=data.get("typography", {}),
            charts=data.get("charts", {}),
            writing=data.get("writing", {}),
            expression_dna=data.get("expression_dna"),
        )


class KnowledgeOrchestrator:
    """V53: 知识编排器，集成一致预期 + akshare 实时数据"""

    def __init__(self):
        self.sac_loader = SACLoader()
        self.style_loader = StyleLoader()
        self._evidence_counter = 0

    @staticmethod
    def _resolve_asset_code(brief: WritingBrief) -> str:
        """解析资产代码：优先 asset_code，fallback 到 asset 去掉后缀"""
        code = (brief.asset_code or "").strip()
        if code:
            return code.split(".")[0]
        asset = (brief.asset or "").strip()
        if asset:
            return asset.split(".")[0]
        return ""

    def build(self, brief: WritingBrief) -> KnowledgePackage:
        pkg = KnowledgePackage(brief=brief)
        pkg.sac = self.sac_loader.load(brief.report_type)
        pkg.style = self.style_loader.load(brief.style_profile)

        # V53 Layer 4: 组装多源数据
        all_data = self._load_data(brief)
        consensus_data = self._load_consensus(brief)
        realtime_data = self._load_realtime(brief)
        pkg.data_points = all_data + consensus_data + realtime_data

        pkg.financials = self._compute(brief, pkg.data_points)
        pkg.evidence_items = self._build_evidence_items(pkg)
        pkg.data_gaps = self._detect_gaps(pkg)
        return pkg

    def _load_data(self, brief: WritingBrief) -> list[DataPoint]:
        """加载财报基础数据（akshare EastMoney → Sina fallback）。"""
        pts: list[DataPoint] = []
        asset_code = self._resolve_asset_code(brief)

        # 优先尝试 akshare EastMoney
        if _HAS_AKSHARE:
            try:
                pts = _fetch_financials(asset_code)
                if pts and len(pts) > 1 and pts[0].name != "no_data":
                    return pts
            except Exception as e:
                logger.warning("_load_data(%s) EastMoney failed: %s", asset_code, e)

        # Sina fallback
        if _HAS_SINA:
            try:
                conn = get_sina_connector()
                sina_pts = conn.fetch_financials(asset_code)
                if sina_pts:
                    logger.info("_load_data(%s) Sina fallback: %d points", asset_code, len(sina_pts))
                    return sina_pts
            except Exception as e:
                logger.warning("_load_data(%s) Sina fallback failed: %s", asset_code, e)

        return pts

    def _load_consensus(self, brief: WritingBrief) -> list[DataPoint]:
        """V53 Layer 4: 加载一致预期数据。"""
        if not _HAS_CONSENSUS:
            logger.debug("consensus not available")
            return []
        try:
            asset_code = self._resolve_asset_code(brief)
            return fetch_consensus(asset_code)
        except Exception as e:
            logger.debug("consensus fetch failed: %s", e)
            return []

    def _load_realtime(self, brief: WritingBrief) -> list[DataPoint]:
        """V53 Layer 4: 加载实时行情（Sina fallback）。"""
        asset_code = self._resolve_asset_code(brief)

        # Sina connector
        if _HAS_SINA:
            try:
                conn = get_sina_connector()
                return conn.fetch_realtime(asset_code)
            except Exception as e:
                logger.debug("Sina realtime unavailable for %s: %s", asset_code, e)

        # 原 EastMoney fallback
        if _HAS_AKSHARE:
            try:
                import akshare as ak

                pts = []
                try:
                    quote = ak.stock_zh_a_spot_em()
                    if quote is not None and not quote.empty:
                        match = quote[quote["代码"] == brief.asset_code]
                        if not match.empty:
                            price = match.iloc[0].get("最新价", 0)
                            change_pct = match.iloc[0].get("涨跌幅", 0)
                            if price:
                                pts.append(
                                    DataPoint(
                                        name="realtime_price",
                                        value=float(price),
                                        unit="元",
                                        source="akshare_realtime",
                                        source_level="L2_provider",
                                        confidence="high",
                                    )
                                )
                            if change_pct is not None:
                                pts.append(
                                    DataPoint(
                                        name="realtime_change_pct",
                                        value=float(change_pct),
                                        unit="%",
                                        source="akshare_realtime",
                                        source_level="L2_provider",
                                        confidence="high",
                                    )
                                )
                except Exception as e:
                    logger.debug("realtime price unavailable for %s: %s", brief.asset_code, e)
                return pts
            except Exception:
                return []
        return []

    def _build_evidence_items(self, pkg: KnowledgePackage) -> list[EvidenceItem]:
        items = []
        for dp in pkg.data_points:
            self._evidence_counter += 1
            items.append(
                EvidenceItem(
                    content=f"{dp.name}: {dp.value} {dp.unit}",
                    source=dp.source or "data_engine",
                    level=self._map_confidence(dp.confidence),
                    support_direction="neutral",
                    relevance_score=0.7,
                )
            )
        fin = pkg.financials
        if fin:
            for field_name in ["revenue_bridge", "margin_bridge", "roe_decomposition"]:
                data = getattr(fin, field_name, None)
                if data:
                    self._evidence_counter += 1
                    items.append(
                        EvidenceItem(
                            content=f"{field_name}: computed",
                            source="compute_engine",
                            level=EvidenceLevel.FILING,
                            support_direction="neutral",
                            relevance_score=0.8,
                        )
                    )
        return items

    @staticmethod
    def _map_confidence(c: str) -> EvidenceLevel:
        return {"high": EvidenceLevel.FILING, "medium": EvidenceLevel.ESTIMATE, "low": EvidenceLevel.INFERENCE}.get(
            c, EvidenceLevel.ESTIMATE
        )

    def _compute(self, brief: WritingBrief, data: list[DataPoint]) -> Optional[FinancialSummary]:
        try:
            from compute.pipeline import run_compute

            return run_compute(brief, data)
        except Exception:
            return None

    @staticmethod
    def _detect_gaps(pkg: KnowledgePackage) -> list[str]:
        gaps = []
        if not pkg.financials:
            gaps.append("财务数据未获取")
        if not pkg.evidence_items:
            gaps.append("无结构化证据可用")
        if pkg.sac and not pkg.data_points:
            gaps.append("SAC 要求数据覆盖但不满足")
        # V53: 检查是否缺少一致预期和实时行情
        has_consensus = any(dp.name.startswith("consensus") for dp in pkg.data_points)
        has_realtime = any(dp.name in ("realtime_price", "current_price") for dp in pkg.data_points)
        if not has_consensus:
            gaps.append("一致预期数据未获取（可选）")
        if not has_realtime:
            gaps.append("实时行情未获取（可选）")
        return gaps
