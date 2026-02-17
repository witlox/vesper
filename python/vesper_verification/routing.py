"""
Traffic Routing for Vesper Verification
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vesper_verification.confidence import ConfidenceTracker


class ExecutionMode(Enum):
    """Execution modes for dual-path runtime."""

    PYTHON_ONLY = "python_only"
    SHADOW_DIRECT = "shadow_direct"
    CANARY_DIRECT = "canary_direct"
    DUAL_VERIFY = "dual_verify"
    DIRECT_ONLY = "direct_only"


@dataclass
class RoutingDecision:
    """A decision about how to route execution."""

    mode: ExecutionMode
    use_python: bool
    use_direct: bool
    is_shadow: bool
    verify_outputs: bool
    reason: str

    @classmethod
    def python_only(cls, reason: str = "Default fallback") -> RoutingDecision:
        return cls(
            mode=ExecutionMode.PYTHON_ONLY,
            use_python=True,
            use_direct=False,
            is_shadow=False,
            verify_outputs=False,
            reason=reason,
        )

    @classmethod
    def shadow(cls, reason: str = "Shadow mode for data collection") -> RoutingDecision:
        return cls(
            mode=ExecutionMode.SHADOW_DIRECT,
            use_python=True,
            use_direct=True,
            is_shadow=True,
            verify_outputs=False,
            reason=reason,
        )

    @classmethod
    def dual_verify(cls, reason: str = "Dual verification") -> RoutingDecision:
        return cls(
            mode=ExecutionMode.DUAL_VERIFY,
            use_python=True,
            use_direct=True,
            is_shadow=False,
            verify_outputs=True,
            reason=reason,
        )

    @classmethod
    def direct_only(cls, reason: str = "High confidence direct") -> RoutingDecision:
        return cls(
            mode=ExecutionMode.DIRECT_ONLY,
            use_python=False,
            use_direct=True,
            is_shadow=False,
            verify_outputs=False,
            reason=reason,
        )


@dataclass
class RoutingConfig:
    """Configuration for routing decisions."""

    canary_threshold: float = 0.95
    dual_verify_threshold: float = 0.999
    direct_only_threshold: float = 0.9999
    canary_percentage: float = 0.05
    direct_only_sample_rate: float = 0.01
    shadow_mode_enabled: bool = True
    node_overrides: dict[str, ExecutionMode] = field(default_factory=dict)


class ExecutionRouter:
    """Determine how to route execution based on confidence and configuration."""

    def __init__(
        self,
        confidence_tracker: ConfidenceTracker,
        config: RoutingConfig | None = None,
    ) -> None:
        self.confidence_tracker = confidence_tracker
        self.config = config or RoutingConfig()

    def route(
        self,
        node_id: str,
        inputs: dict[str, Any],
        force_mode: ExecutionMode | None = None,
    ) -> RoutingDecision:
        """Determine routing for an execution."""
        if force_mode:
            return self._decision_for_mode(force_mode, "Forced by caller")

        if node_id in self.config.node_overrides:
            mode = self.config.node_overrides[node_id]
            return self._decision_for_mode(mode, f"Node override to {mode.value}")

        confidence = self.confidence_tracker.get_confidence(node_id)
        metrics = self.confidence_tracker.get_metrics(node_id)

        if (
            metrics is None
            or metrics.total_executions < self.confidence_tracker.MIN_SAMPLE_SIZE
        ):
            return RoutingDecision.python_only(
                reason=f"Insufficient data ({metrics.total_executions if metrics else 0} executions)"
            )

        if confidence < self.config.canary_threshold:
            return RoutingDecision.python_only(
                reason=f"Low confidence ({confidence:.4f} < {self.config.canary_threshold})"
            )
        elif confidence < self.config.dual_verify_threshold:
            return self._canary_decision(node_id, inputs, confidence)
        elif confidence < self.config.direct_only_threshold:
            return RoutingDecision.dual_verify(
                reason=f"High confidence ({confidence:.4f}), continuous verification"
            )
        else:
            return self._direct_only_decision(node_id, inputs, confidence)

    def _decision_for_mode(self, mode: ExecutionMode, reason: str) -> RoutingDecision:
        """Create a routing decision for a specific mode."""
        if mode == ExecutionMode.PYTHON_ONLY:
            return RoutingDecision.python_only(reason)
        elif mode == ExecutionMode.SHADOW_DIRECT:
            return RoutingDecision.shadow(reason)
        elif mode == ExecutionMode.CANARY_DIRECT:
            return RoutingDecision(
                mode=ExecutionMode.CANARY_DIRECT,
                use_python=False,
                use_direct=True,
                is_shadow=False,
                verify_outputs=False,
                reason=reason,
            )
        elif mode == ExecutionMode.DUAL_VERIFY:
            return RoutingDecision.dual_verify(reason)
        elif mode == ExecutionMode.DIRECT_ONLY:
            return RoutingDecision.direct_only(reason)
        else:
            return RoutingDecision.python_only(reason)

    def _canary_decision(
        self, node_id: str, inputs: dict[str, Any], confidence: float
    ) -> RoutingDecision:
        """Make a canary routing decision."""
        hash_input = f"{node_id}:{_stable_hash(inputs)}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        percentage = (hash_value % 10000) / 10000.0

        if percentage < self.config.canary_percentage:
            return RoutingDecision(
                mode=ExecutionMode.CANARY_DIRECT,
                use_python=False,
                use_direct=True,
                is_shadow=False,
                verify_outputs=False,
                reason=f"Canary ({self.config.canary_percentage:.0%} traffic to direct)",
            )
        else:
            return RoutingDecision(
                mode=ExecutionMode.CANARY_DIRECT,
                use_python=True,
                use_direct=False,
                is_shadow=False,
                verify_outputs=False,
                reason=f"Canary ({1 - self.config.canary_percentage:.0%} traffic to Python)",
            )

    def _direct_only_decision(
        self, node_id: str, inputs: dict[str, Any], confidence: float
    ) -> RoutingDecision:
        """Make a direct-only routing decision with sampling."""
        if random.random() < self.config.direct_only_sample_rate:
            return RoutingDecision(
                mode=ExecutionMode.DIRECT_ONLY,
                use_python=True,
                use_direct=True,
                is_shadow=False,
                verify_outputs=True,
                reason=f"Direct with sampling ({self.config.direct_only_sample_rate:.0%} verification)",
            )
        else:
            return RoutingDecision.direct_only(
                reason=f"Very high confidence ({confidence:.4f})"
            )

    def set_mode_override(self, node_id: str, mode: ExecutionMode) -> None:
        """Set a mode override for a specific node."""
        self.config.node_overrides[node_id] = mode

    def clear_mode_override(self, node_id: str) -> None:
        """Clear mode override for a node."""
        self.config.node_overrides.pop(node_id, None)


def _stable_hash(obj: Any) -> str:
    """Create a stable hash of an object for consistent routing."""
    serialized = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()
