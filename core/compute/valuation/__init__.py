"""
1号分析师 V30 — 估值模型包

包含四个核心估值模块：
  - DCF 估值 (dcf.py): 基于麦肯锡估值第8版
  - 可比公司分析 (comparable.py): PE/PB/PS 多维度对标（中国同行）
  - 全球竞争对标 (global_benchmark.py): 全球龙头估值/业绩对标
  - 三情景分析 (scenario.py): 摩根士丹利 Risk-Reward 框架
"""

__all__ = [
    "DCFResult",
    "compute_dcf",
    "format_dcf_for_report",
    "ComparableResult",
    "compute_comparable",
    "compute_comparable_with_existing_data",
    "format_comparable_for_report",
    "GlobalPeerEntry",
    "GlobalBenchmarkResult",
    "compute_global_benchmark",
    "format_global_benchmark_for_report",
    "ScenarioDetail",
    "ScenarioResult",
    "compute_scenario",
    "make_base_scenario",
    "make_bull_scenario",
    "make_bear_scenario",
    "format_scenario_for_report",
    "SOTPSegmentInput",
    "SOTPResult",
    "compute_sotp",
    "format_sotp_for_report",
]


def __getattr__(name):
    import importlib

    module_map = {
        "DCFResult": ("core.compute.valuation.dcf", "DCFResult"),
        "compute_dcf": ("core.compute.valuation.dcf", "compute_dcf"),
        "format_dcf_for_report": ("core.compute.valuation.dcf", "format_dcf_for_report"),
        "ComparableResult": ("core.compute.valuation.comparable", "ComparableResult"),
        "compute_comparable": ("core.compute.valuation.comparable", "compute_comparable"),
        "compute_comparable_with_existing_data": (
            "core.compute.valuation.comparable",
            "compute_comparable_with_existing_data",
        ),
        "format_comparable_for_report": (
            "core.compute.valuation.comparable",
            "format_comparable_for_report",
        ),
        "GlobalPeerEntry": (
            "core.compute.valuation.global_benchmark",
            "GlobalPeerEntry",
        ),
        "GlobalBenchmarkResult": (
            "core.compute.valuation.global_benchmark",
            "GlobalBenchmarkResult",
        ),
        "compute_global_benchmark": (
            "core.compute.valuation.global_benchmark",
            "compute_global_benchmark",
        ),
        "format_global_benchmark_for_report": (
            "core.compute.valuation.global_benchmark",
            "format_global_benchmark_for_report",
        ),
        "ScenarioDetail": ("core.compute.valuation.scenario", "ScenarioDetail"),
        "ScenarioResult": ("core.compute.valuation.scenario", "ScenarioResult"),
        "compute_scenario": ("core.compute.valuation.scenario", "compute_scenario"),
        "make_base_scenario": ("core.compute.valuation.scenario", "make_base_scenario"),
        "make_bull_scenario": ("core.compute.valuation.scenario", "make_bull_scenario"),
        "make_bear_scenario": ("core.compute.valuation.scenario", "make_bear_scenario"),
        "format_scenario_for_report": (
            "core.compute.valuation.scenario",
            "format_scenario_for_report",
        ),
        "SOTPSegmentInput": (
            "core.compute.valuation.sotp",
            "SOTPSegmentInput",
        ),
        "SOTPResult": (
            "core.compute.valuation.sotp",
            "SOTPResult",
        ),
        "compute_sotp": (
            "core.compute.valuation.sotp",
            "compute_sotp",
        ),
        "format_sotp_for_report": (
            "core.compute.valuation.sotp",
            "format_sotp_for_report",
        ),
    }
    if name in module_map:
        mod_path, attr = module_map[name]
        mod = importlib.import_module(mod_path)
        return getattr(mod, attr)
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
