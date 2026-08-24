"""
V53 假设对标数据库 — 从 data/assumption_distributions.json 动态加载行业假设分布。
保留硬编码 INDUSTRY_ASSUMPTIONS 作为 fallback，优先使用动态加载。

Conviction Matrix 设定 base/bull/bear 概率时，对照行业假设分布定位自己的百分位。
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("v51.benchmark.assumptions")

# ── 项目根目录 ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 默认分布 JSON 路径 ──
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "assumption_distributions.json"

# ═══════════════════════════════════════════════════════════════
# 硬编码行业假设分布（fallback，初始数据来自130家估值模型人工提取）
# ═══════════════════════════════════════════════════════════════
INDUSTRY_ASSUMPTIONS: dict[str, dict] = {
    "新能源车": {
        "revenue_cagr_3y": {"mean": 0.25, "p10": 0.12, "p25": 0.18, "p50": 0.22, "p75": 0.30, "p90": 0.40, "count": 8},
        "gross_margin": {"mean": 0.20, "p10": 0.12, "p25": 0.16, "p50": 0.20, "p75": 0.25, "p90": 0.30, "count": 10},
        "target_pe": {"mean": 25.0, "p10": 12.0, "p25": 18.0, "p50": 22.0, "p75": 30.0, "p90": 40.0, "count": 6},
        "beta": {"mean": 1.3, "p10": 0.9, "p25": 1.1, "p50": 1.3, "p75": 1.5, "p90": 1.7, "count": 5},
    },
    "半导体": {
        "revenue_cagr_3y": {"mean": 0.18, "p10": 0.08, "p25": 0.12, "p50": 0.16, "p75": 0.22, "p90": 0.30, "count": 12},
        "gross_margin": {"mean": 0.35, "p10": 0.20, "p25": 0.28, "p50": 0.35, "p75": 0.42, "p90": 0.50, "count": 12},
        "target_pe": {"mean": 30.0, "p10": 15.0, "p25": 22.0, "p50": 28.0, "p75": 35.0, "p90": 50.0, "count": 8},
        "beta": {"mean": 1.2, "p10": 0.8, "p25": 1.0, "p50": 1.2, "p75": 1.4, "p90": 1.6, "count": 6},
    },
    "互联网平台": {
        "revenue_cagr_3y": {"mean": 0.20, "p10": 0.10, "p25": 0.15, "p50": 0.18, "p75": 0.25, "p90": 0.35, "count": 15},
        "gross_margin": {"mean": 0.40, "p10": 0.22, "p25": 0.30, "p50": 0.38, "p75": 0.45, "p90": 0.55, "count": 15},
        "target_pe": {"mean": 22.0, "p10": 10.0, "p25": 15.0, "p50": 20.0, "p75": 28.0, "p90": 38.0, "count": 10},
        "beta": {"mean": 1.4, "p10": 1.0, "p25": 1.2, "p50": 1.35, "p75": 1.55, "p90": 1.8, "count": 8},
    },
    "医药": {
        "revenue_cagr_3y": {"mean": 0.15, "p10": 0.08, "p25": 0.10, "p50": 0.14, "p75": 0.18, "p90": 0.25, "count": 10},
        "gross_margin": {"mean": 0.55, "p10": 0.35, "p25": 0.45, "p50": 0.55, "p75": 0.65, "p90": 0.75, "count": 10},
        "target_pe": {"mean": 28.0, "p10": 15.0, "p25": 20.0, "p50": 25.0, "p75": 35.0, "p90": 45.0, "count": 8},
        "beta": {"mean": 1.0, "p10": 0.7, "p25": 0.85, "p50": 1.0, "p75": 1.15, "p90": 1.3, "count": 6},
    },
    "消费": {
        "revenue_cagr_3y": {"mean": 0.12, "p10": 0.05, "p25": 0.08, "p50": 0.12, "p75": 0.16, "p90": 0.22, "count": 12},
        "gross_margin": {"mean": 0.30, "p10": 0.15, "p25": 0.22, "p50": 0.28, "p75": 0.35, "p90": 0.45, "count": 12},
        "target_pe": {"mean": 20.0, "p10": 10.0, "p25": 15.0, "p50": 18.0, "p75": 24.0, "p90": 32.0, "count": 10},
        "beta": {"mean": 0.9, "p10": 0.6, "p25": 0.75, "p50": 0.9, "p75": 1.05, "p90": 1.2, "count": 8},
    },
    "金融": {
        "revenue_cagr_3y": {"mean": 0.08, "p10": 0.03, "p25": 0.05, "p50": 0.08, "p75": 0.10, "p90": 0.14, "count": 8},
        "roe": {"mean": 0.12, "p10": 0.07, "p25": 0.09, "p50": 0.12, "p75": 0.14, "p90": 0.18, "count": 8},
        "target_pb": {"mean": 1.2, "p10": 0.5, "p25": 0.8, "p50": 1.1, "p75": 1.5, "p90": 2.0, "count": 6},
        "beta": {"mean": 1.1, "p10": 0.8, "p25": 0.95, "p50": 1.1, "p75": 1.25, "p90": 1.4, "count": 6},
    },
}


@dataclass
class BenchmarkResult:
    """对标查询结果。"""
    industry: str = ""
    metric: str = ""
    our_value: float = 0.0
    percentile: float = 0.0
    distribution: dict = field(default_factory=dict)
    judgment: str = ""
    note: str = ""


class AssumptionBenchmark:
    """假设对标查询器。

    V53 新增: 支持从 data/assumption_distributions.json 动态加载行业分布，
    覆盖硬编码的 INDUSTRY_ASSUMPTIONS，且支持增量更新。

    用法:
        bm = AssumptionBenchmark()  # 自动加载动态数据，fallback 到硬编码
        result = bm.query("新能源车", "revenue_cagr_3y", 0.30)
    """

    def __init__(self, db: dict = None, db_path: str = None):
        """初始化对标查询器。

        Args:
            db: 手动传入的行业分布字典覆盖
            db_path: 动态加载 JSON 路径（默认 data/assumption_distributions.json）
        """
        if db is not None:
            self.db = db
        else:
            # 优先加载动态 DB，缺失行业回退到硬编码
            dynamic_db = self._load_dynamic_db(db_path) or {}
            merged = dict(INDUSTRY_ASSUMPTIONS)
            merged.update(dynamic_db)  # 动态 DB 中的行业覆盖硬编码
            self.db = merged
            if dynamic_db:
                added = set(dynamic_db.keys()) - set(INDUSTRY_ASSUMPTIONS.keys())
                if added:
                    logger.info(f"Dynamic DB added industries: {added}")

    @staticmethod
    def _load_dynamic_db(db_path: str = None) -> Optional[dict]:
        """从 JSON 文件动态加载行业分布。"""
        path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        if not path.exists():
            logger.warning(f"Dynamic DB not found: {path}, fallback to hardcoded")
            return None
        try:
            with open(str(path), "r", encoding="utf-8") as f:
                raw = json.load(f)
            # V53 格式: {industry: {metric: {mean, p25, p50, p75, ...}}}
            # 转换为兼容格式: {industry: {metric: {mean, p10, p25, p50, p75, p90, count}}}
            db = {}
            for ind, metrics in raw.items():
                db[ind] = {}
                for metric, dist in metrics.items():
                    if metric == "count":
                        continue
                    # 对齐字段名
                    entry = dict(dist)
                    # 确保字段完整
                    for field in ["mean", "p10", "p25", "p50", "p75", "p90", "count"]:
                        if field not in entry:
                            entry[field] = dist.get(field, 0)
                    db[ind][metric] = entry
            logger.info(f"Loaded {len(db)} industries from {path}")
            return db
        except Exception as e:
            logger.warning(f"Failed to load DB {path}: {e}, fallback to hardcoded")
            return None

    def load_from_db(self, db_path: str = None) -> bool:
        """重新加载行业分布数据库（运行时热加载）。"""
        db = self._load_dynamic_db(db_path)
        if db:
            self.db = db
            return True
        return False

    def refresh(self, db_path: str = None) -> bool:
        """别名：重载数据。"""
        return self.load_from_db(db_path)

    def get_distribution(self, industry: str, metric: str) -> Optional[dict]:
        """直接获取某行业某指标的分布数据。"""
        industry_key = self._match_industry(industry)
        if not industry_key:
            return None
        dist = self.db.get(industry_key, {}).get(metric)
        return dist

    def query(self, industry: str, metric: str, value: float) -> BenchmarkResult:
        """查询假设值在行业分布中的位置。"""
        result = BenchmarkResult(
            industry=industry, metric=metric, our_value=value
        )

        industry_key = self._match_industry(industry)
        if not industry_key:
            result.note = f"行业'{industry}'不在对标库中"
            result.judgment = "无法判断"
            return result

        dist = self.db.get(industry_key, {}).get(metric, {})
        if not dist or "count" not in dist or dist["count"] == 0:
            result.note = f"指标'{metric}'在行业'{industry}'中无数据"
            result.judgment = "无法判断"
            return result

        result.distribution = dist
        if "mean" not in dist:
            result.note = f"分布数据不完整（缺mean）"
            result.judgment = "无法判断"
            return result

        mean = dist.get("mean", 0)
        p10 = dist.get("p10", mean * 0.5)
        p25 = dist.get("p25", mean * 0.7)
        p50 = dist.get("p50", mean)
        p75 = dist.get("p75", mean * 1.3)
        p90 = dist.get("p90", mean * 1.5)

        # 计算百分位——用分段线性插值
        if value <= p10:
            result.percentile = max(0.05, (value - mean) / (p10 - mean) * 0.10 + 0.10 if p10 != mean else 0.10)
        elif value <= p25:
            result.percentile = 0.10 + (value - p10) / (p25 - p10) * 0.15 if p25 != p10 else 0.25
        elif value <= p50:
            result.percentile = 0.25 + (value - p25) / (p50 - p25) * 0.25 if p50 != p25 else 0.50
        elif value <= p75:
            result.percentile = 0.50 + (value - p50) / (p75 - p50) * 0.25 if p75 != p50 else 0.75
        elif value <= p90:
            result.percentile = 0.75 + (value - p75) / (p90 - p75) * 0.15 if p90 != p75 else 0.90
        else:
            result.percentile = min(0.99, 0.90 + (value - p90) / (p90) * 0.09 if p90 != 0 else 0.95)
        result.percentile = max(0.01, min(0.99, result.percentile))

        # 判断：偏离中位数超过 25 百分位范围认为是显著
        if result.percentile > 0.75:
            result.judgment = "偏乐观"
            result.note = f"该假设偏乐观（同类模型分布第{int(result.percentile * 100)}百分位）"
        elif result.percentile < 0.25:
            result.judgment = "偏保守"
            result.note = f"该假设偏保守（同类模型分布第{int(result.percentile * 100)}百分位）"
        else:
            result.judgment = "在正常范围"
            result.note = f"该假设在行业正常范围内（同类模型分布第{int(result.percentile * 100)}百分位）"

        return result

    def _match_industry(self, industry: str) -> Optional[str]:
        """模糊匹配行业名到数据库中的行业键。"""
        if not industry:
            return None
        # 直接匹配
        if industry in self.db:
            return industry
        # 模糊匹配
        mapping = {
            "新能源车": ["新能源车", "新能源汽车", "电动车", "汽车"],
            "半导体": ["半导体", "芯片", "集成电路", "电路"],
            "互联网平台": ["互联网", "电商", "外卖", "平台", "科技"],
            "医药": ["医药", "生物", "CXO", "医疗", "药"],
            "消费": ["消费", "食品", "白酒", "饮料", "乳业", "调味"],
            "金融": ["金融", "银行", "证券", "保险", "信托"],
            "地产": ["地产", "房地产", "物业"],
            "通信": ["通信", "通讯", "5G"],
            "军工": ["军工", "国防", "航天", "航空"],
            "化工": ["化工", "化学"],
            "机械": ["机械", "装备"],
            "食品饮料": ["食品", "饮料", "白酒", "乳业", "调味"],
            "电子": ["电子"],
            "煤炭": ["煤炭", "煤"],
            "公用事业": ["电力", "水务", "燃气", "公用"],
            "传媒": ["传媒", "广告", "影视"],
        }
        for key, keywords in mapping.items():
            for kw in keywords:
                if kw in industry:
                    # 如果这个 key 在 db 中
                    if key in self.db:
                        return key
                    # 也检查原 key 名匹配
                    for db_key in self.db:
                        if key in db_key or db_key in key:
                            return db_key
        # 尝试部分匹配 db 中的键
        for db_key in self.db:
            if any(kw in industry for kw in [db_key]) or db_key[:2] in industry:
                return db_key
        return None


# ═══════════════════════════════════════════════════════════════
# Conviction Matrix 概率校准
# ═══════════════════════════════════════════════════════════════

def calibrate_probabilities(
    industry: str,
    revenue_cagr: float = None,
    gross_margin: float = None,
    target_pe: float = None,
    base_prob: tuple = (0.55, 0.20, 0.25),
) -> dict:
    """用假设对标校准 Conviction Matrix 概率。"""
    bm = AssumptionBenchmark()
    base, bull, bear = base_prob
    calibration_log = []
    adjustments = {"base": 0.0, "bull": 0.0, "bear": 0.0}

    pairs = [
        (revenue_cagr, "revenue_cagr_3y", "营收CAGR"),
        (gross_margin, "gross_margin", "毛利率"),
        (target_pe, "target_pe", "目标PE"),
    ]

    for value, metric, name in pairs:
        if value is None:
            continue
        result = bm.query(industry, metric, value)
        if result.judgment == "偏乐观":
            adj = min(0.10, result.percentile - 0.50)
            adjustments["bear"] += adj
            adjustments["base"] -= adj / 2
            adjustments["bull"] -= adj / 2
            calibration_log.append(f"假设'{name}={value:.0%}'偏乐观（P{int(result.percentile*100)}），bear上调{adj:.1%}")
        elif result.judgment == "偏保守":
            adj = min(0.10, 0.50 - result.percentile)
            adjustments["bull"] += adj
            adjustments["base"] -= adj / 2
            adjustments["bear"] -= adj / 2
            calibration_log.append(f"假设'{name}={value:.0%}'偏保守（P{int(result.percentile*100)}），bull上调{adj:.1%}")
        else:
            calibration_log.append(f"假设'{name}={value:.0%}'在行业正常范围（P{int(result.percentile*100)})")

    adj_base = base + adjustments["base"]
    adj_bull = bull + adjustments["bull"]
    adj_bear = bear + adjustments["bear"]

    total = adj_base + adj_bull + adj_bear
    if total > 0:
        adj_base /= total
        adj_bull /= total
        adj_bear /= total

    return {
        "base": round(adj_base, 2),
        "bull": round(adj_bull, 2),
        "bear": round(adj_bear, 2),
        "calibration_log": calibration_log,
    }


def detect_growth_assumption_gap(
    industry: str,
    our_revenue_cagr: float,
) -> Optional[str]:
    """检测营收假设是否与行业对标数据存在显著偏差。"""
    bm = AssumptionBenchmark()
    dist = bm.get_distribution(industry, "revenue_cagr_3y")
    if not dist:
        return None
    mean = dist.get("mean", 0)
    p25 = dist.get("p25", mean * 0.7)
    p75 = dist.get("p75", mean * 1.3)
    iqr = p75 - p25
    if iqr == 0:
        return None
    deviation = (our_revenue_cagr - mean) / iqr
    if deviation > 1.5:
        return (f"营收假设 {our_revenue_cagr:.1%} 显著高于行业均值{mean:.1%} "
                f"（偏差{deviation:.1f}倍IQR），建议谨慎评估假设合理性")
    if deviation < -1.5:
        return (f"营收假设 {our_revenue_cagr:.1%} 显著低于行业均值{mean:.1%} "
                f"（偏差{abs(deviation):.1f}倍IQR），建议检查是否低估")
    return None
