"""
Confidence Calculation for Vesper Verification

Implements Wilson score confidence intervals for statistical confidence
in runtime equivalence. Uses a conservative lower bound to ensure
safe migration decisions.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


@dataclass
class RuntimeMetrics:
    """Metrics for a node's execution history."""

    node_id: str
    total_executions: int = 0
    divergences: int = 0
    python_errors: int = 0
    direct_errors: int = 0
    last_updated: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        """Rate of non-divergent executions."""
        if self.total_executions == 0:
            return 0.0
        return (self.total_executions - self.divergences) / self.total_executions

    @property
    def divergence_rate(self) -> float:
        """Rate of divergent executions."""
        if self.total_executions == 0:
            return 0.0
        return self.divergences / self.total_executions


class ConfidenceTracker:
    """
    Track execution metrics and calculate confidence scores.

    Uses Wilson score confidence interval:
    - Conservative lower bound of binomial proportion
    - Accounts for sample size
    - 99.9% confidence level (z=3.29)

    Confidence thresholds:
    - < 0.95: PYTHON_ONLY (not ready for migration)
    - 0.95 - 0.999: CANARY_DIRECT (5% traffic)
    - 0.999 - 0.9999: DUAL_VERIFY (continuous verification)
    - > 0.9999: DIRECT_ONLY (high confidence)
    """

    MIN_SAMPLE_SIZE = 100
    Z_SCORE = 3.29

    def __init__(self) -> None:
        self.metrics: dict[str, RuntimeMetrics] = {}

    def record_execution(
        self,
        node_id: str,
        diverged: bool,
        python_error: bool = False,
        direct_error: bool = False,
    ) -> None:
        """Record an execution result."""
        if node_id not in self.metrics:
            self.metrics[node_id] = RuntimeMetrics(node_id=node_id)

        m = self.metrics[node_id]
        m.total_executions += 1
        if diverged:
            m.divergences += 1
        if python_error:
            m.python_errors += 1
        if direct_error:
            m.direct_errors += 1
        m.last_updated = time.time()

    def get_confidence(self, node_id: str) -> float:
        """
        Calculate confidence that direct runtime is correct.

        Returns value between 0.0 and 1.0.
        Uses Wilson score confidence interval.
        """
        if node_id not in self.metrics:
            return 0.0

        m = self.metrics[node_id]

        if m.total_executions < self.MIN_SAMPLE_SIZE:
            return 0.0

        z = self.Z_SCORE
        n = m.total_executions
        successes = n - m.divergences
        p = successes / n

        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator
        margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator

        return max(0.0, center - margin)

    def get_metrics(self, node_id: str) -> RuntimeMetrics | None:
        """Get raw metrics for a node."""
        return self.metrics.get(node_id)

    def get_all_metrics(self) -> dict[str, RuntimeMetrics]:
        """Get metrics for all tracked nodes."""
        return dict(self.metrics)

    def reset_metrics(self, node_id: str) -> None:
        """Reset metrics for a node."""
        if node_id in self.metrics:
            del self.metrics[node_id]

    def get_recommended_mode(self, node_id: str) -> str:
        """Get recommended execution mode based on confidence."""
        confidence = self.get_confidence(node_id)

        if confidence < 0.95:
            return "python_only"
        elif confidence < 0.999:
            return "canary_direct"
        elif confidence < 0.9999:
            return "dual_verify"
        else:
            return "direct_only"

    def serialize(self) -> dict:
        """Serialize tracker state for persistence."""
        return {
            node_id: {
                "total_executions": m.total_executions,
                "divergences": m.divergences,
                "python_errors": m.python_errors,
                "direct_errors": m.direct_errors,
                "last_updated": m.last_updated,
            }
            for node_id, m in self.metrics.items()
        }

    @classmethod
    def deserialize(cls, data: dict) -> ConfidenceTracker:
        """Deserialize tracker state from persistence."""
        tracker = cls()
        for node_id, values in data.items():
            tracker.metrics[node_id] = RuntimeMetrics(
                node_id=node_id,
                total_executions=values["total_executions"],
                divergences=values["divergences"],
                python_errors=values["python_errors"],
                direct_errors=values["direct_errors"],
                last_updated=values["last_updated"],
            )
        return tracker
