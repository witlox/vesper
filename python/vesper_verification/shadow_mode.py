"""
Shadow Mode Execution for Vesper Verification
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional, Protocol

if TYPE_CHECKING:
    from vesper_verification.confidence import ConfidenceTracker
    from vesper_verification.differential import OutputComparator
    from vesper_verification.divergence import DivergenceDatabase
    from vesper_verification.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class RuntimeProtocol(Protocol):
    """Protocol for runtime implementations."""

    async def execute(self, node_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute a node with the given inputs."""
        ...


@dataclass
class ExecutionResult:
    """Result from executing a semantic node."""

    output: dict[str, Any]
    execution_time_ms: float
    path_used: str
    trace_id: str
    success: bool
    error: Optional[Exception] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "output": self.output,
            "execution_time_ms": self.execution_time_ms,
            "path_used": self.path_used,
            "trace_id": self.trace_id,
            "success": self.success,
            "error": str(self.error) if self.error else None,
        }


class ShadowExecutor:
    """
    Execute direct runtime in shadow mode.

    Shadow mode means:
    - Python runtime runs in foreground (user sees this)
    - Direct runtime runs in background (async, doesn't block)
    - Divergences are logged but don't affect response
    - Collects data for confidence building
    """

    def __init__(
        self,
        direct_runtime: RuntimeProtocol,
        comparator: "OutputComparator",
        confidence_tracker: "ConfidenceTracker",
        metrics_collector: Optional["MetricsCollector"] = None,
        divergence_database: Optional["DivergenceDatabase"] = None,
    ) -> None:
        self.direct_runtime = direct_runtime
        self.comparator = comparator
        self.confidence_tracker = confidence_tracker
        self.metrics_collector = metrics_collector
        self.divergence_database = divergence_database
        self._pending_tasks: set[asyncio.Task] = set()

    def execute_shadow(
        self,
        node_id: str,
        inputs: dict[str, Any],
        python_result: ExecutionResult,
    ) -> None:
        """Launch shadow execution (non-blocking)."""
        task = asyncio.create_task(
            self._shadow_execution_task(node_id, inputs, python_result)
        )
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _shadow_execution_task(
        self,
        node_id: str,
        inputs: dict[str, Any],
        python_result: ExecutionResult,
    ) -> None:
        """Background task for shadow execution."""
        import time

        trace_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        try:
            direct_output = await self.direct_runtime.execute(node_id, inputs)
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            direct_result = ExecutionResult(
                output=direct_output,
                execution_time_ms=execution_time_ms,
                path_used="direct",
                trace_id=trace_id,
                success=True,
            )

            diff = self.comparator.compare(python_result.output, direct_result.output)
            diverged = diff is not None

            self.confidence_tracker.record_execution(
                node_id=node_id,
                diverged=diverged,
                python_error=not python_result.success,
                direct_error=False,
            )

            if self.metrics_collector:
                self.metrics_collector.record_execution(
                    node_id=node_id,
                    path="direct",
                    duration_ms=execution_time_ms,
                    success=True,
                    diverged=diverged,
                )

            if diverged:
                logger.warning(
                    f"Shadow divergence detected for {node_id}: {diff.get('count', 0)} differences"
                )
                if self.divergence_database:
                    await self._record_divergence(
                        node_id, inputs, python_result.output, direct_output, diff, trace_id
                    )

        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Shadow execution failed for {node_id}: {e}")

            self.confidence_tracker.record_execution(
                node_id=node_id,
                diverged=True,
                python_error=not python_result.success,
                direct_error=True,
            )

            if self.metrics_collector:
                self.metrics_collector.record_execution(
                    node_id=node_id,
                    path="direct",
                    duration_ms=execution_time_ms,
                    success=False,
                    diverged=True,
                    error=e,
                )

    async def _record_divergence(
        self,
        node_id: str,
        inputs: dict[str, Any],
        python_output: dict[str, Any],
        direct_output: dict[str, Any],
        diff: dict[str, Any],
        trace_id: str,
    ) -> None:
        """Record a divergence to the database."""
        if self.divergence_database:
            from vesper_verification.divergence import DivergenceRecord

            record = DivergenceRecord(
                id=trace_id,
                node_id=node_id,
                inputs=inputs,
                python_output=python_output,
                direct_output=direct_output,
                diff=diff,
                timestamp=datetime.now(timezone.utc).isoformat(),
                mode="shadow",
            )
            await self.divergence_database.store(record)

    async def wait_for_pending(self, timeout: Optional[float] = None) -> int:
        """Wait for all pending shadow executions to complete."""
        if not self._pending_tasks:
            return 0

        pending_count = len(self._pending_tasks)

        try:
            await asyncio.wait_for(
                asyncio.gather(*self._pending_tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for {len(self._pending_tasks)} shadow tasks")

        return pending_count

    @property
    def pending_count(self) -> int:
        """Number of pending shadow executions."""
        return len(self._pending_tasks)

