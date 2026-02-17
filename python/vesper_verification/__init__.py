"""
Vesper Verification Framework

Provides differential testing, shadow mode execution, and confidence-based
migration infrastructure for verifying runtime implementations.
"""

from vesper_verification.confidence import ConfidenceTracker, RuntimeMetrics
from vesper_verification.differential import (
    DifferentialTester,
    Divergence,
    OutputComparator,
)
from vesper_verification.divergence import DivergenceDatabase, DivergenceRecord
from vesper_verification.metrics import (
    AggregateMetrics,
    ExecutionMetrics,
    MetricsCollector,
)
from vesper_verification.routing import ExecutionRouter, RoutingDecision
from vesper_verification.shadow_mode import ShadowExecutor

__all__ = [
    # Confidence
    "ConfidenceTracker",
    "RuntimeMetrics",
    # Differential
    "DifferentialTester",
    "Divergence",
    "OutputComparator",
    # Divergence
    "DivergenceDatabase",
    "DivergenceRecord",
    # Metrics
    "AggregateMetrics",
    "ExecutionMetrics",
    "MetricsCollector",
    # Routing
    "ExecutionRouter",
    "RoutingDecision",
    # Shadow Mode
    "ShadowExecutor",
]
