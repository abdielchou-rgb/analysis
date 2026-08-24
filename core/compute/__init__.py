"""核心计算模块统一导出接口"""
from __future__ import annotations

from .valuation.dcf import compute_dcf, DCFResult
from .valuation.reverse_dcf import ReverseDCF, ReverseDCFResult
from .valuation.comparable import ComparableResult
from .valuation.monte_carlo import MonteCarloValuation, MCResult
from .valuation.real_option import RealOption, RealOptionResult
from .valuation.eva import EVAModel, AltmanZScore, EVAResult
from .valuation.peg import PEGValuation, PEGResult
from .valuation.lbo import LBOModel, LBOResult

from .financial.dupont import DupontAnalysis
from .financial.factor_decomp import RevenueAttribution, AttributionResult

from .signal_chain import SignalChainEngine, SignalResult
from .multi_debate import MultiModelDebate, DebateResult

__all__ = [
    "compute_dcf", "DCFResult", "ReverseDCF", "ReverseDCFResult",
    "ComparableResult", "MonteCarloValuation", "MCResult",
    "RealOption", "RealOptionResult",
    "EVAModel", "AltmanZScore", "EVAResult",
    "PEGValuation", "PEGResult", "LBOModel", "LBOResult",
    "DupontAnalysis", "RevenueAttribution", "AttributionResult",
    "SignalChainEngine", "SignalResult",
    "MultiModelDebate", "DebateResult",
]

__version__ = "2.0.0"
