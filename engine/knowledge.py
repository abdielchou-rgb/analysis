"""
Damodaran RAG + Per-Ticker 机构记忆 + Deep-Merge 场景引擎。
参考 valuation-project (RAG + memory) + dashboard-package (deep-merge scenarios)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Damodaran RAG ──────────────────────────────────────────────────────────


@dataclass
class DamodaranEntry:
    """Damodaran 语料库条目"""

    id: str
    source: str  # blog / pdf / spreadsheet / video
    topic: str  # dcf / com估值 / 相对估值 / 风险 / 资本成本 / ...
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DamodaranRAGQuery:
    """RAG 查询"""

    query: str
    topic_filter: Optional[str] = None
    top_k: int = 5


@dataclass
class DamodaranRAGResult:
    """RAG 查询结果"""

    entries: List[DamodaranEntry] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    summary: str = ""


class DamodaranRAG:
    """Damodaran 知识库 RAG 引擎"""

    def __init__(self, corpus_path: Optional[str] = None):
        self.corpus: List[DamodaranEntry] = []
        if corpus_path and Path(corpus_path).exists():
            self._load_corpus(corpus_path)

    def _load_corpus(self, path: str) -> None:
        """加载语料库"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    self.corpus.append(DamodaranEntry(**item))
        except Exception:
            pass

    def query(self, q: DamodaranRAGQuery) -> DamodaranRAGResult:
        """简单关键词匹配 RAG（生产环境用向量数据库）"""
        result = DamodaranRAGResult()
        query_lower = q.query.lower()

        scored = []
        for entry in self.corpus:
            if q.topic_filter and entry.topic != q.topic_filter:
                continue
            # 简单 TF 匹配
            score = sum(1 for word in query_lower.split() if word in entry.content.lower())
            if score > 0:
                scored.append((entry, score))

        scored.sort(key=lambda x: -x[1])
        for entry, score in scored[: q.top_k]:
            result.entries.append(entry)
            result.scores.append(score)

        return result

    def add_entry(self, entry: DamodaranEntry) -> None:
        self.corpus.append(entry)


# ─── Per-Ticker Memory ──────────────────────────────────────────────────────


@dataclass
class TickerMemory:
    """Per-Ticker 机构记忆"""

    ticker: str
    investment_thesis: str = ""
    calibration: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class TickerMemoryStore:
    """Ticker 记忆存储"""

    def __init__(self, store_path: Optional[str] = None):
        self.memories: Dict[str, TickerMemory] = {}
        self.store_path = store_path
        if store_path and Path(store_path).exists():
            self._load()

    def _load(self) -> None:
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for ticker, mem_data in data.items():
                    self.memories[ticker] = TickerMemory(**mem_data)
        except Exception:
            pass

    def save(self) -> None:
        if self.store_path:
            Path(self.store_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(
                    {k: vars(v) for k, v in self.memories.items()},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

    def get(self, ticker: str) -> TickerMemory:
        if ticker not in self.memories:
            self.memories[ticker] = TickerMemory(ticker=ticker)
        return self.memories[ticker]

    def update_calibration(self, ticker: str, key: str, value: Any) -> None:
        mem = self.get(ticker)
        mem.calibration[key] = value

    def add_history(self, ticker: str, entry: Dict[str, Any]) -> None:
        mem = self.get(ticker)
        mem.history.append(entry)
        # 只保留最近 20 条
        if len(mem.history) > 20:
            mem.history = mem.history[-20:]

    def add_warning(self, ticker: str, warning: str) -> None:
        mem = self.get(ticker)
        mem.warnings.append(warning)


# ─── Deep-Merge Scenario Engine ─────────────────────────────────────────────


def deep_merge(base: Dict, override: Dict) -> Dict:
    """深度合并两个字典，override 覆盖 base，不修改原始对象"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class ScenarioTemplate:
    """场景模板"""

    name: str
    adjustments: Dict[str, Any] = field(default_factory=dict)
    probability: float = 0.33


@dataclass
class DeepMergeScenarioAssumptions:
    """深度合并场景假设"""

    base_assumptions: Dict[str, Any] = field(default_factory=dict)
    scenarios: List[ScenarioTemplate] = field(default_factory=list)


class DeepMergeScenarioEngine:
    """深度合并场景引擎 — base assumptions never mutated"""

    def __init__(self, assumptions: DeepMergeScenarioAssumptions):
        self.a = assumptions

    def run(self) -> List[Dict[str, Any]]:
        """生成多个场景的完整假设"""
        results = []
        for scenario in self.a.scenarios:
            merged = deep_merge(self.a.base_assumptions, scenario.adjustments)
            merged["_scenario_name"] = scenario.name
            merged["_probability"] = scenario.probability
            results.append(merged)
        return results


# ─── Tornado Chart ──────────────────────────────────────────────────────────


@dataclass
class TornadoInput:
    """Tornado 图输入"""

    base_value: float
    drivers: Dict[str, Tuple[float, float]]  # driver_name → (low_value, high_value)
    driver_values: Dict[str, float]  # driver_name → base_driver_value


@dataclass
class TornadoBar:
    """Tornado 图单条"""

    driver: str
    low_result: float
    high_result: float
    swing: float  # |high - low|
    base_value: float


@dataclass
class TornadoResult:
    """Tornado 图结果"""

    bars: List[TornadoBar] = field(default_factory=list)
    base_value: float = 0.0

    def sorted_by_swing(self) -> List[TornadoBar]:
        return sorted(self.bars, key=lambda b: -b.swing)


class TornadoEngine:
    """Tornado Chart 引擎 — ±20% driver swing analysis"""

    def __init__(self, compute_fn):
        """
        Args:
            compute_fn: callable(params_dict) → float (fair value)
        """
        self.compute_fn = compute_fn

    def run(self, inputs: TornadoInput) -> TornadoResult:
        result = TornadoResult(base_value=inputs.base_value)

        for driver, (low_val, high_val) in inputs.drivers.items():
            # Low scenario
            params_low = {k: v for k, v in inputs.driver_values.items()}
            params_low[driver] = low_val
            low_result = self.compute_fn(params_low)

            # High scenario
            params_high = {k: v for k, v in inputs.driver_values.items()}
            params_high[driver] = high_val
            high_result = self.compute_fn(params_high)

            swing = abs(high_result - low_result)
            result.bars.append(
                TornadoBar(
                    driver=driver,
                    low_result=low_result,
                    high_result=high_result,
                    swing=swing,
                    base_value=inputs.base_value,
                )
            )

        return result
