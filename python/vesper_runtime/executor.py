"""
Execution Orchestrator for Vesper Runtime
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Protocol

if TYPE_CHECKING:
    from vesper_verification.confidence import ConfidenceTracker
    from vesper_verification.differential import OutputComparator
    from vesper_verification.metrics import MetricsCollector
    from vesper_verification.routing import ExecutionRouter
    from vesper_verification.shadow_mode import ShadowExecutor

from vesper_verification.routing import ExecutionMode, RoutingDecision

logger = logging.getLogger(__name__)


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
        return {
            "output": self.output,
            "execution_time_ms": self.execution_time_ms,
            "path_used": self.path_used,
            "trace_id": self.trace_id,
            "success": self.success,
            "error": str(self.error) if self.error else None,
        }


@dataclass
class DualExecutionResult:
    """Result from executing both paths."""

    python_result: ExecutionResult
    direct_result: Optional[ExecutionResult]
    diverged: bool
    divergence_details: Optional[dict[str, Any]] = None

    @property
    def primary_result(self) -> ExecutionResult:
        return self.python_result


class RuntimeProtocol(Protocol):
    """Protocol for runtime implementations."""

    async def execute(self, node_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        ...


class PythonRuntime:
    """Python-based reference runtime."""

    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}

    def register_handler(self, node_id: str, handler: Any) -> None:
        self._handlers[node_id] = handler

    async def execute(self, node_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        if node_id not in self._handlers:
            raise RuntimeError(f"No handler registered for node: {node_id}")

        handler = self._handlers[node_id]

        if inspect.iscoroutinefunction(handler):
            result = await handler(**inputs)
        else:
            result = handler(**inputs)

        if isinstance(result, dict):
            return result
        else:
            return {"result": result}


class DirectRuntime:
    """Placeholder for the direct (optimized) runtime."""

    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}

    def register_handler(self, node_id: str, handler: Any) -> None:
        self._handlers[node_id] = handler

    async def execute(self, node_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        if node_id not in self._handlers:
            raise RuntimeError(f"No handler registered for node: {node_id}")

        handler = self._handlers[node_id]

        if inspect.iscoroutinefunction(handler):
            result = await handler(**inputs)
        else:
            result = handler(**inputs)

        if isinstance(result, dict):
            return result
        else:
            return {"result": result}


class ExecutionOrchestrator:
    """Orchestrates execution across Python and direct runtimes."""

    def __init__(
        self,
        python_runtime: RuntimeProtocol,
        direct_runtime: Optional[RuntimeProtocol] = None,
        router: Optional["ExecutionRouter"] = None,
        confidence_tracker: Optional["ConfidenceTracker"] = None,
        metrics_collector: Optional["MetricsCollector"] = None,
        shadow_executor: Optional["ShadowExecutor"] = None,
        comparator: Optional["OutputComparator"] = None,
    ) -> None:
        self.python_runtime = python_runtime
        self.direct_runtime = direct_runtime
        self.router = router
        self.confidence_tracker = confidence_tracker
        self.metrics_collector = metrics_collector
        self.shadow_executor = shadow_executor
        self.comparator = comparator

    async def execute(
        self,
        node_id: str,
        inputs: dict[str, Any],
        mode: Optional[ExecutionMode] = None,
    ) -> ExecutionResult:
        """Execute a semantic node in the appropriate mode."""
        trace_id = str(uuid.uuid4())

        if mode is not None:
            decision = self._adjust_decision_for_mode(mode)
        elif self.router:
            decision = self.router.route(node_id, inputs)
        else:
            decision = RoutingDecision.python_only("No router configured")

        logger.info(f"Executing {node_id} in mode {decision.mode.value}: {decision.reason}")

        try:
            if decision.mode == ExecutionMode.PYTHON_ONLY:
                return await self._execute_python_only(node_id, inputs, trace_id)
            elif decision.mode == ExecutionMode.SHADOW_DIRECT:
                return await self._execute_shadow_mode(node_id, inputs, trace_id)
            elif decision.mode == ExecutionMode.CANARY_DIRECT:
                return await self._execute_canary_mode(node_id, inputs, trace_id, decision)
            elif decision.mode == ExecutionMode.DUAL_VERIFY:
                dual_result = await self._execute_dual_verify(node_id, inputs, trace_id)
                return dual_result.python_result
            elif decision.mode == ExecutionMode.DIRECT_ONLY:
                return await self._execute_direct_only(node_id, inputs, trace_id, decision)
            else:
                return await self._execute_python_only(node_id, inputs, trace_id)
        except Exception as e:
            logger.error(f"Execution failed for {node_id}: {e}")
            try:
                return await self._execute_python_only(node_id, inputs, trace_id)
            except Exception as python_error:
                return ExecutionResult(
                    output={},
                    execution_time_ms=0.0,
                    path_used="python",
                    trace_id=trace_id,
                    success=False,
                    error=python_error,
                )

    def _adjust_decision_for_mode(self, mode: ExecutionMode) -> RoutingDecision:
        if mode == ExecutionMode.PYTHON_ONLY:
            return RoutingDecision.python_only("Forced mode")
        elif mode == ExecutionMode.SHADOW_DIRECT:
            return RoutingDecision.shadow("Forced mode")
        elif mode == ExecutionMode.CANARY_DIRECT:
            return RoutingDecision(
                mode=mode,
                use_python=False,
                use_direct=True,
                is_shadow=False,
                verify_outputs=False,
                reason="Forced canary mode",
            )
        elif mode == ExecutionMode.DUAL_VERIFY:
            return RoutingDecision.dual_verify("Forced mode")
        elif mode == ExecutionMode.DIRECT_ONLY:
            return RoutingDecision.direct_only("Forced mode")
        else:
            return RoutingDecision.python_only("Unknown mode")

    async def _execute_python_only(
        self, node_id: str, inputs: dict[str, Any], trace_id: str
    ) -> ExecutionResult:
        start_time = time.perf_counter()
        try:
            output = await self.python_runtime.execute(node_id, inputs)
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            result = ExecutionResult(
                output=output,
                execution_time_ms=execution_time_ms,
                path_used="python",
                trace_id=trace_id,
                success=True,
            )
            self._record_metrics(node_id, "python", execution_time_ms, True)
            return result
        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            self._record_metrics(node_id, "python", execution_time_ms, False, error=e)
            raise

    async def _execute_shadow_mode(
        self, node_id: str, inputs: dict[str, Any], trace_id: str
    ) -> ExecutionResult:
        python_result = await self._execute_python_only(node_id, inputs, trace_id)
        if self.shadow_executor and self.direct_runtime:
            from vesper_verification.shadow_mode import ExecutionResult as ShadowResult
            shadow_result = ShadowResult(
                output=python_result.output,
                execution_time_ms=python_result.execution_time_ms,
                path_used=python_result.path_used,
                trace_id=python_result.trace_id,
                success=python_result.success,
            )
            self.shadow_executor.execute_shadow(node_id, inputs, shadow_result)
        return python_result

    async def _execute_canary_mode(
        self, node_id: str, inputs: dict[str, Any], trace_id: str, decision: RoutingDecision
    ) -> ExecutionResult:
        if decision.use_direct and self.direct_runtime:
            try:
                return await self._execute_direct(node_id, inputs, trace_id)
            except Exception as e:
                logger.warning(f"Canary direct failed for {node_id}, falling back: {e}")
                return await self._execute_python_only(node_id, inputs, trace_id)
        else:
            return await self._execute_python_only(node_id, inputs, trace_id)

    async def _execute_dual_verify(
        self, node_id: str, inputs: dict[str, Any], trace_id: str
    ) -> DualExecutionResult:
        if not self.direct_runtime:
            python_result = await self._execute_python_only(node_id, inputs, trace_id)
            return DualExecutionResult(
                python_result=python_result,
                direct_result=None,
                diverged=False,
            )

        start_time = time.perf_counter()
        try:
            python_output, direct_output = await asyncio.gather(
                self.python_runtime.execute(node_id, inputs),
                self.direct_runtime.execute(node_id, inputs),
            )
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            python_result = ExecutionResult(
                output=python_output,
                execution_time_ms=execution_time_ms,
                path_used="python",
                trace_id=trace_id,
                success=True,
            )
            direct_result = ExecutionResult(
                output=direct_output,
                execution_time_ms=execution_time_ms,
                path_used="direct",
                trace_id=trace_id,
                success=True,
            )

            diverged = False
            divergence_details = None

            if self.comparator:
                divergence_details = self.comparator.compare(python_output, direct_output)
                diverged = divergence_details is not None
            else:
                diverged = python_output != direct_output
                if diverged:
                    divergence_details = {"python": python_output, "direct": direct_output}

            if self.confidence_tracker:
                self.confidence_tracker.record_execution(node_id=node_id, diverged=diverged)

            self._record_metrics(node_id, "python", execution_time_ms, True, diverged=diverged)
            self._record_metrics(node_id, "direct", execution_time_ms, True, diverged=diverged)

            if diverged:
                logger.warning(f"Divergence in dual verify for {node_id}: {divergence_details}")

            return DualExecutionResult(
                python_result=python_result,
                direct_result=direct_result,
                diverged=diverged,
                divergence_details=divergence_details,
            )
        except Exception as e:
            logger.error(f"Dual execution failed for {node_id}: {e}")
            python_result = await self._execute_python_only(node_id, inputs, trace_id)
            return DualExecutionResult(
                python_result=python_result,
                direct_result=None,
                diverged=True,
                divergence_details={"error": str(e)},
            )

    async def _execute_direct_only(
        self, node_id: str, inputs: dict[str, Any], trace_id: str, decision: RoutingDecision
    ) -> ExecutionResult:
        if not self.direct_runtime:
            return await self._execute_python_only(node_id, inputs, trace_id)

        if decision.verify_outputs:
            dual_result = await self._execute_dual_verify(node_id, inputs, trace_id)
            if dual_result.direct_result:
                return dual_result.direct_result
            return dual_result.python_result
        else:
            return await self._execute_direct(node_id, inputs, trace_id)

    async def _execute_direct(
        self, node_id: str, inputs: dict[str, Any], trace_id: str
    ) -> ExecutionResult:
        if not self.direct_runtime:
            raise RuntimeError("Direct runtime not configured")

        start_time = time.perf_counter()
        try:
            output = await self.direct_runtime.execute(node_id, inputs)
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            result = ExecutionResult(
                output=output,
                execution_time_ms=execution_time_ms,
                path_used="direct",
                trace_id=trace_id,
                success=True,
            )
            self._record_metrics(node_id, "direct", execution_time_ms, True)
            return result
        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            self._record_metrics(node_id, "direct", execution_time_ms, False, error=e)
            raise

    def _record_metrics(
        self,
        node_id: str,
        path: str,
        duration_ms: float,
        success: bool,
        diverged: bool = False,
        error: Optional[Exception] = None,
    ) -> None:
        if self.metrics_collector:
            self.metrics_collector.record_execution(
                node_id=node_id,
                path=path,
                duration_ms=duration_ms,
                success=success,
                diverged=diverged,
                error=error,
            )

    async def execute_dual(
        self, node_id: str, inputs: dict[str, Any]
    ) -> DualExecutionResult:
        """Explicitly execute dual verification."""
        trace_id = str(uuid.uuid4())
        return await self._execute_dual_verify(node_id, inputs, trace_id)

