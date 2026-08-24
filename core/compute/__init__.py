"""核心计算模块统一导出接口"""

from __future__ import annotations

from .financial.dupont import DupontAnalysis
from .financial.factor_decomp import AttributionResult, RevenueAttribution
from .multi_debate import DebateResult, MultiModelDebate
from .signal_chain import SignalChainEngine, SignalResult
from .valuation.comparable import ComparableResult
from .valuation.dcf import DCFResult, compute_dcf
from .valuation.eva import AltmanZScore, EVAModel, EVAResult
from .valuation.lbo import LBOModel, LBOResult
from .valuation.monte_carlo import MCResult, MonteCarloValuation
from .valuation.peg import PEGResult, PEGValuation
from .valuation.real_option import RealOption, RealOptionResult
from .valuation.reverse_dcf import ReverseDCF, ReverseDCFResult

__all__ = [
    "compute_dcf",
    "DCFResult",
    "ReverseDCF",
    "ReverseDCFResult",
    "ComparableResult",
    "MonteCarloValuation",
    "MCResult",
    "RealOption",
    "RealOptionResult",
    "EVAModel",
    "AltmanZScore",
    "EVAResult",
    "PEGValuation",
    "PEGResult",
    "LBOModel",
    "LBOResult",
    "DupontAnalysis",
    "RevenueAttribution",
    "AttributionResult",
    "SignalChainEngine",
    "SignalResult",
    "MultiModelDebate",
    "DebateResult",
]

__version__ = "2.0.0"
