"""1hao analyst V52 - core module."""

from __future__ import annotations

from core.ai_fingerprints import AIScanner, HumanSenseReport
from core.argument import ArgumentEngine
from core.calibration import BiasReport, CalibrationDashboard, CalibrationSuggestion
from core.enforcer import EnforcementResult, Enforcer, EnforcerConfig
from core.forward_picks import ForwardPick, ForwardPicksDB
from core.hypothesis_verifier import HypothesisVerdict
from core.hypothesis_verifier import HypothesisVerifier as NewHypothesisVerifier
from core.input import V51Input
from core.metrics import ValidateHistory

# V51 core
from core.models import DataPoint, Deliverable, KnowledgePackage, SACEntry, WritingBrief

# V52 core
from core.quality_scorer import DimensionScore, QualityScore, QualityScorer
from core.scarcity_signals import ScarcitySignalChecker
from core.style import CompiledText, StyleCompiler
from core.temporal_verifier import PredictionRecorder, TemporalVerifier
from core.verify import T3Orchestrator

__all__ = [
    # V51
    "WritingBrief",
    "KnowledgePackage",
    "Deliverable",
    "SACEntry",
    "DataPoint",
    "ValidateHistory",
    "V51Input",
    "ArgumentEngine",
    "StyleCompiler",
    "CompiledText",
    "T3Orchestrator",
    "NewHypothesisVerifier",
    "HypothesisVerdict",
    "ScarcitySignalChecker",
    "AIScanner",
    "HumanSenseReport",
    "TemporalVerifier",
    "PredictionRecorder",
    "ForwardPicksDB",
    "ForwardPick",
    # V52
    "QualityScorer",
    "QualityScore",
    "DimensionScore",
    "Enforcer",
    "EnforcerConfig",
    "EnforcementResult",
    "CalibrationDashboard",
    "BiasReport",
    "CalibrationSuggestion",
]
