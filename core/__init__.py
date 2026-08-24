"""1hao analyst V52 - core module."""

from __future__ import annotations

# V51 core
from core.models import WritingBrief, KnowledgePackage, Deliverable, SACEntry, DataPoint
from core.metrics import ValidateHistory
from core.input import V51Input
from core.argument import ArgumentEngine
from core.style import StyleCompiler, CompiledText
from core.verify import T3Orchestrator
from core.hypothesis_verifier import HypothesisVerifier as NewHypothesisVerifier, HypothesisVerdict
from core.scarcity_signals import ScarcitySignalChecker
from core.ai_fingerprints import AIScanner, HumanSenseReport
from core.temporal_verifier import TemporalVerifier, PredictionRecorder
from core.forward_picks import ForwardPicksDB, ForwardPick

# V52 core
from core.quality_scorer import QualityScorer, QualityScore, DimensionScore
from core.enforcer import Enforcer, EnforcerConfig, EnforcementResult
from core.calibration import CalibrationDashboard, BiasReport, CalibrationSuggestion

__all__ = [
    # V51
    "WritingBrief", "KnowledgePackage", "Deliverable", "SACEntry", "DataPoint",
    "ValidateHistory", "V51Input", "ArgumentEngine", "StyleCompiler", "CompiledText",
    "T3Orchestrator", "NewHypothesisVerifier", "HypothesisVerdict", "ScarcitySignalChecker",
    "AIScanner", "HumanSenseReport", "TemporalVerifier", "PredictionRecorder",
    "ForwardPicksDB", "ForwardPick",
    # V52
    "QualityScorer", "QualityScore", "DimensionScore",
    "Enforcer", "EnforcerConfig", "EnforcementResult",
    "CalibrationDashboard", "BiasReport", "CalibrationSuggestion",
]
