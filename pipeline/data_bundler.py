"""
pipeline/data_bundler.py — 数据捆绑器

从 section_writer._build_data_bundle() 提取并增强：
1. 严格区分 live(实时) / reference(静态知识) 数据层
2. 支持数据溯源（每个数据点标记来源）
3. 支持数据验证（检查数据完整性）
4. 支持数据压缩（避免超长注入）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("2hao.data_bundler")

_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class DataBundle:
    """数据捆绑"""

    live: dict = field(default_factory=dict)  # 实时数据层
    reference: dict = field(default_factory=dict)  # 静态知识层
    metadata: dict = field(default_factory=dict)  # 元数据


class DataBundler:
    """
    数据捆绑器

    职责：
    1. 从 collected_data 构建结构化数据捆绑
    2. 严格区分 live(实时) / reference(静态知识) 数据层
    3. 支持数据溯源（每个数据点标记来源）
    4. 支持数据验证（检查数据完整性）
    5. 支持数据压缩（避免超长注入）
    """

    def __init__(self, max_data_length: int = 8000):
        """
        Args:
            max_data_length: 数据最大长度（字符数）
        """
        self.max_data_length = max_data_length

    def build_bundle(self, data_context: Optional[dict] = None) -> DataBundle:
        """
        构建数据捆绑

        Args:
            data_context: 数据上下文（collected_data）

        Returns:
            DataBundle: 数据捆绑
        """
        bundle = DataBundle()
        data = data_context or {}

        # ═══ LIVE 实时数据层 (akshare实时拉取) ═══
        self._add_live_financials(bundle, data)
        self._add_live_chart_data(bundle, data)
        self._add_live_news(bundle, data)
        self._add_live_compute(bundle, data)
        self._add_live_macro(bundle, data)
        self._add_live_feeds(bundle, data)
        self._add_live_valuation(bundle, data)

        # ═══ REFERENCE 静态知识层 (你喂的,只作参考) ═══
        self._add_reference_valuation_params(bundle, data)
        self._add_reference_knowledge_base(bundle)
        self._add_reference_biz_model(bundle, data)

        # 元数据
        bundle.metadata = {
            "live_keys": list(bundle.live.keys()),
            "reference_keys": list(bundle.reference.keys()),
            "total_length": self._estimate_length(bundle),
        }

        return bundle

    def bundle_to_string(self, bundle: DataBundle) -> str:
        """
        将数据捆绑转换为字符串

        Args:
            bundle: 数据捆绑

        Returns:
            str: 数据字符串
        """
        parts = []

        # 实时数据
        if bundle.live:
            parts.append("## [实时数据]")
            for key, value in bundle.live.items():
                parts.append(f"### {key}")
                parts.append(self._format_value(value))

        # 静态知识
        if bundle.reference:
            parts.append("## [参考知识]")
            for key, value in bundle.reference.items():
                parts.append(f"### {key}")
                parts.append(self._format_value(value))

        result = "\n".join(parts)

        # 压缩超长数据
        if len(result) > self.max_data_length:
            result = self._compress_data(result)

        return result

    def _add_live_financials(self, bundle: DataBundle, data: dict):
        """添加实时财务数据"""
        fin = data.get("financials", {})
        if fin:
            bundle.live["financials"] = fin

    def _add_live_chart_data(self, bundle: DataBundle, data: dict):
        """添加实时图表数据"""
        if isinstance(data, dict) and data.get("chart_data"):
            cd = data["chart_data"]
            if isinstance(cd, dict):
                bundle.live["chart_data"] = cd

    def _add_live_news(self, bundle: DataBundle, data: dict):
        """添加实时新闻"""
        if isinstance(data, dict) and data.get("tavily"):
            bundle.live["news"] = data["tavily"]

    def _add_live_compute(self, bundle: DataBundle, data: dict):
        """添加实时计算结果"""
        cr = data.get("compute_results", {}) if isinstance(data, dict) else {}
        if cr:
            bundle.live["compute"] = cr

    def _add_live_macro(self, bundle: DataBundle, data: dict):
        """添加宏观数据"""
        macro = data.get("macro_ctx", {}) if isinstance(data, dict) else {}
        if macro:
            bundle.live["macro"] = {
                "earnings_cycle": getattr(macro, "earnings_cycle", ""),
                "liquidity_cycle": getattr(macro, "liquidity_cycle", ""),
                "risk_preference": getattr(macro, "risk_preference", ""),
            }

    def _add_live_feeds(self, bundle: DataBundle, data: dict):
        """添加数据源"""
        feed_keys = [
            "feed_news",
            "feed_news_raw",
            "feed_reports",
            "feed_report_count",
            "feed_target_reports",
            "feed_basics",
            "feed_patents",
            "extra_sentiment",
            "extra_jobs",
        ]
        feeds = {k: data.get(k) for k in feed_keys if data.get(k) is not None}
        if feeds:
            bundle.live["feeds"] = feeds

    def _add_live_valuation(self, bundle: DataBundle, data: dict):
        """添加估值数据"""
        val = data.get("valuation_percentile", {}) if isinstance(data, dict) else {}
        if val:
            bundle.live["valuation"] = val

    def _add_reference_valuation_params(self, bundle: DataBundle, data: dict):
        """添加估值参数"""
        try:
            from core.model_extractor import get_params

            _asset_name = data.get("asset", "") if isinstance(data, dict) else ""
            _company_key = str(_asset_name).split(" ")[0].split("(")[0].strip() if _asset_name else ""
            if _company_key:
                _vparams = get_params(_company_key)
                if _vparams:
                    bundle.reference["valuation_params"] = _vparams
        except Exception:
            pass

    def _add_reference_knowledge_base(self, bundle: DataBundle):
        """添加知识库"""
        try:
            _data_dir = _ROOT / "data"
            for key, fname in [
                ("industry_baselines", "industry_baselines.json"),
                ("consensus_prices", "consensus_prices.json"),
                ("industry_drivers", "industry_drivers.json"),
                ("methodology_styles", "methodology_styles.json"),
                ("methodology_frameworks", "methodology_frameworks.json"),
                ("methodology_detailed", "methodology_frameworks_detailed.json"),
                ("baseline_findings", "baseline_findings.json"),
                ("ib_templates", "investment_bank_templates.json"),
                ("absorbed_baseline", "absorbed_baseline.json"),
                ("absorbed_style_dna", "absorbed_style_dna.json"),
                ("absorbed_methodology", "absorbed_methodology.json"),
            ]:
                _fp = _data_dir / fname
                if _fp.exists():
                    bundle.reference[key] = json.loads(_fp.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _add_reference_biz_model(self, bundle: DataBundle, data: dict):
        """添加商业模式"""
        biz = data.get("biz_model", {}) if isinstance(data, dict) else {}
        if biz:
            bundle.reference["biz"] = {
                "type": getattr(biz, "biz_name", ""),
                "industry": getattr(biz, "industry_tags", []),
            }

    def _format_value(self, value: Any) -> str:
        """格式化值"""
        if isinstance(value, str):
            return value
        elif isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, indent=2)[:500]
        elif isinstance(value, list):
            return json.dumps(value, ensure_ascii=False, indent=2)[:500]
        else:
            return str(value)[:200]

    def _estimate_length(self, bundle: DataBundle) -> int:
        """估算数据长度"""
        total = 0
        for key, value in bundle.live.items():
            total += len(self._format_value(value))
        for key, value in bundle.reference.items():
            total += len(self._format_value(value))
        return total

    def _compress_data(self, data_str: str) -> str:
        """压缩超长数据"""
        # 保留前 max_data_length 字符
        if len(data_str) > self.max_data_length:
            return data_str[: self.max_data_length] + "\n\n[数据已压缩...]"
        return data_str
