"""
Vesper Runtime

Executes Vesper specifications with dual-path support.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from vesper.models import VesperNode
from vesper.compiler import VesperCompiler


class ExecutionMode(Enum):
    """Execution mode for dual-path routing."""
    PYTHON_ONLY = "python_only"
    SHADOW_DIRECT = "shadow_direct"
    CANARY_DIRECT = "canary_direct"
    DUAL_VERIFY = "dual_verify"
    DIRECT_ONLY = "direct_only"


@dataclass
class ExecutionMetrics:
    """Metrics for a single execution."""
    node_id: str
    duration_ms: float
    path_used: str
    success: bool
    error_type: str | None = None
    divergence: bool = False


@dataclass
class RuntimeMetrics:
    """Accumulated metrics for a node."""
    node_id: str
    total_executions: int = 0
    python_executions: int = 0
    direct_executions: int = 0
    divergences: int = 0
    errors: int = 0
    total_duration_ms: float = 0.0

    @property
    def avg_duration_ms(self) -> float:
        """Average execution duration."""
        if self.total_executions == 0:
            return 0.0
        return self.total_duration_ms / self.total_executions

    @property
    def error_rate(self) -> float:
        """Error rate as a fraction."""
        if self.total_executions == 0:
            return 0.0
        return self.errors / self.total_executions

    @property
    def divergence_rate(self) -> float:
        """Divergence rate as a fraction."""
        if self.total_executions == 0:
            return 0.0
        return self.divergences / self.total_executions


@dataclass
class ExecutionResult:
    """Result of executing a Vesper node."""
    success: bool
    data: Any = None
    error: str | None = None
    metrics: ExecutionMetrics | None = None


class MigrationController:
    """
    Controls the execution mode for each node based on confidence scores.
    """

    MIN_SAMPLE_SIZE = 1000

    def __init__(self) -> None:
        self._node_modes: dict[str, ExecutionMode] = {}
        self._metrics: dict[str, RuntimeMetrics] = {}

    def get_execution_mode(self, node_id: str) -> ExecutionMode:
        """Get the current execution mode for a node."""
        return self._node_modes.get(node_id, ExecutionMode.PYTHON_ONLY)

    def set_execution_mode(self, node_id: str, mode: ExecutionMode) -> None:
        """Set the execution mode for a node."""
        self._node_modes[node_id] = mode

    def get_metrics(self, node_id: str) -> RuntimeMetrics:
        """Get metrics for a node."""
        if node_id not in self._metrics:
            self._metrics[node_id] = RuntimeMetrics(node_id=node_id)
        return self._metrics[node_id]

    def record_execution(self, metrics: ExecutionMetrics) -> None:
        """Record execution metrics."""
        node_metrics = self.get_metrics(metrics.node_id)
        node_metrics.total_executions += 1
        node_metrics.total_duration_ms += metrics.duration_ms

        if metrics.path_used == "python":
            node_metrics.python_executions += 1
        else:
            node_metrics.direct_executions += 1

        if not metrics.success:
            node_metrics.errors += 1

        if metrics.divergence:
            node_metrics.divergences += 1

    def calculate_confidence(self, node_id: str) -> float:
        """
        Calculate confidence that direct runtime is correct.

        Uses Wilson score confidence interval for statistical rigor.
        """
        metrics = self.get_metrics(node_id)

        if metrics.total_executions < self.MIN_SAMPLE_SIZE:
            return 0.0

        successes = metrics.total_executions - metrics.divergences

        # Wilson score with 99.9% confidence
        z = 3.29  # z-score for 99.9% confidence
        n = metrics.total_executions
        p = successes / n

        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator

        import math
        margin = z * math.sqrt(
            (p * (1-p) / n + z**2 / (4 * n**2))
        ) / denominator

        return max(0, center - margin)  # Lower bound


class PythonExecutor:
    """
    Executes Vesper nodes using generated Python code.
    """

    def __init__(self, compiler: VesperCompiler) -> None:
        self.compiler = compiler
        self._compiled_modules: dict[str, Any] = {}
        self._compiled_functions: dict[str, Callable[..., Any]] = {}

    def load_node(self, node: VesperNode, code: str) -> None:
        """Load a compiled node into the executor."""
        import sys

        # Create a module from the code
        spec = importlib.util.spec_from_loader(node.node_id, loader=None)
        if spec is None:
            raise RuntimeError(f"Failed to create module spec for {node.node_id}")

        module = importlib.util.module_from_spec(spec)

        # Register the module in sys.modules before exec (required for Python 3.14+ dataclasses)
        sys.modules[node.node_id] = module

        try:
            exec(code, module.__dict__)
        except Exception:
            # Clean up on failure
            sys.modules.pop(node.node_id, None)
            raise

        self._compiled_modules[node.node_id] = module

        # Extract the main function
        func_name = self.compiler._to_function_name(node.node_id)
        if hasattr(module, func_name):
            self._compiled_functions[node.node_id] = getattr(module, func_name)
        elif hasattr(module, f"{func_name}_verified"):
            self._compiled_functions[node.node_id] = getattr(module, f"{func_name}_verified")

    async def execute(
        self,
        node_id: str,
        inputs: dict[str, Any]
    ) -> ExecutionResult:
        """Execute a node with the given inputs."""
        if node_id not in self._compiled_functions:
            return ExecutionResult(
                success=False,
                error=f"Node {node_id} not loaded"
            )

        func = self._compiled_functions[node_id]

        start_time = time.perf_counter()
        try:
            result = func(**inputs)
            duration_ms = (time.perf_counter() - start_time) * 1000

            return ExecutionResult(
                success=True,
                data=result,
                metrics=ExecutionMetrics(
                    node_id=node_id,
                    duration_ms=duration_ms,
                    path_used="python",
                    success=True
                )
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                success=False,
                error=str(e),
                metrics=ExecutionMetrics(
                    node_id=node_id,
                    duration_ms=duration_ms,
                    path_used="python",
                    success=False,
                    error_type=type(e).__name__
                )
            )


class DirectExecutor:
    """
    Placeholder for the direct (Rust) runtime executor.

    In the future, this will interface with the Rust-based
    semantic interpreter and JIT compiler.
    """

    async def execute(
        self,
        node: VesperNode,
        inputs: dict[str, Any]
    ) -> ExecutionResult:
        """Execute a node directly (placeholder)."""
        # TODO: Implement actual direct execution
        # For now, return a not-implemented error
        return ExecutionResult(
            success=False,
            error="Direct runtime not yet implemented",
            metrics=ExecutionMetrics(
                node_id=node.node_id,
                duration_ms=0.0,
                path_used="direct",
                success=False,
                error_type="NotImplemented"
            )
        )


class VesperRuntime:
    """
    Main runtime for executing Vesper specifications.

    Supports dual-path execution with confidence-based routing.
    """

    def __init__(self) -> None:
        self.compiler = VesperCompiler()
        self.python_executor = PythonExecutor(self.compiler)
        self.direct_executor = DirectExecutor()
        self.migration_controller = MigrationController()

        self._loaded_nodes: dict[str, VesperNode] = {}

    def load_node(self, source: str | Path) -> VesperNode:
        """
        Load and compile a Vesper node.

        Args:
            source: Path to .vsp file or YAML string

        Returns:
            The loaded VesperNode
        """
        node = self.compiler.parse(source)
        validation = self.compiler.validate(node)

        if not validation.valid:
            error_msgs = [f"{e.path}: {e.message}" for e in validation.errors]
            raise ValueError(f"Validation failed: {'; '.join(error_msgs)}")

        # Compile to Python
        code = self.compiler.compile(node)

        # Load into executor
        self.python_executor.load_node(node, code)

        self._loaded_nodes[node.node_id] = node

        return node

    def get_node(self, node_id: str) -> VesperNode | None:
        """Get a loaded node by ID."""
        return self._loaded_nodes.get(node_id)

    async def execute(
        self,
        node_id: str,
        inputs: dict[str, Any]
    ) -> ExecutionResult:
        """
        Execute a node with the appropriate runtime path.

        The execution path is determined by the migration controller
        based on the node's execution mode and confidence score.
        """
        node = self._loaded_nodes.get(node_id)
        if node is None:
            return ExecutionResult(
                success=False,
                error=f"Node {node_id} not loaded"
            )

        mode = self.migration_controller.get_execution_mode(node_id)

        if mode == ExecutionMode.PYTHON_ONLY:
            result = await self.python_executor.execute(node_id, inputs)
            if result.metrics:
                self.migration_controller.record_execution(result.metrics)
            return result

        elif mode == ExecutionMode.SHADOW_DIRECT:
            # Python runs in foreground
            python_result = await self.python_executor.execute(node_id, inputs)

            # Direct runs in background (async, fire-and-forget)
            asyncio.create_task(
                self._shadow_direct_execute(node, inputs, python_result)
            )

            if python_result.metrics:
                self.migration_controller.record_execution(python_result.metrics)
            return python_result

        elif mode == ExecutionMode.CANARY_DIRECT:
            # Route 5% to direct, 95% to Python
            input_hash = int(hashlib.md5(str(inputs).encode()).hexdigest(), 16)
            if input_hash % 100 < 5:
                try:
                    direct_result = await self.direct_executor.execute(node, inputs)
                    if direct_result.success:
                        if direct_result.metrics:
                            self.migration_controller.record_execution(direct_result.metrics)
                        return direct_result
                except Exception:
                    pass
                # Fallback to Python on failure

            result = await self.python_executor.execute(node_id, inputs)
            if result.metrics:
                self.migration_controller.record_execution(result.metrics)
            return result

        elif mode == ExecutionMode.DUAL_VERIFY:
            # Execute both, compare, return Python
            python_result, direct_result = await asyncio.gather(
                self.python_executor.execute(node_id, inputs),
                self.direct_executor.execute(node, inputs)
            )

            # Check for divergence
            divergence = self._check_divergence(python_result, direct_result)

            if python_result.metrics:
                python_result.metrics.divergence = divergence
                self.migration_controller.record_execution(python_result.metrics)

            if divergence:
                # Log divergence for analysis
                self._log_divergence(node_id, inputs, python_result, direct_result)

            return python_result

        elif mode == ExecutionMode.DIRECT_ONLY:
            # Direct runtime with 1% sampling for verification
            if random.random() < 0.01:
                # Sample verification
                python_result, direct_result = await asyncio.gather(
                    self.python_executor.execute(node_id, inputs),
                    self.direct_executor.execute(node, inputs)
                )
                divergence = self._check_divergence(python_result, direct_result)
                if direct_result.metrics:
                    direct_result.metrics.divergence = divergence
                    self.migration_controller.record_execution(direct_result.metrics)
                return direct_result
            else:
                result = await self.direct_executor.execute(node, inputs)
                if result.metrics:
                    self.migration_controller.record_execution(result.metrics)
                return result

        # Default fallback
        return await self.python_executor.execute(node_id, inputs)

    async def _shadow_direct_execute(
        self,
        node: VesperNode,
        inputs: dict[str, Any],
        python_result: ExecutionResult
    ) -> None:
        """Execute direct runtime in shadow mode and record divergence."""
        try:
            direct_result = await self.direct_executor.execute(node, inputs)
            divergence = self._check_divergence(python_result, direct_result)

            if divergence:
                self._log_divergence(node.node_id, inputs, python_result, direct_result)
        except Exception as e:
            # Log but don't fail - this is shadow mode
            pass

    def _check_divergence(
        self,
        python_result: ExecutionResult,
        direct_result: ExecutionResult
    ) -> bool:
        """Check if the two results diverge."""
        # Simple comparison for now
        if python_result.success != direct_result.success:
            return True

        if python_result.data != direct_result.data:
            return True

        return False

    def _log_divergence(
        self,
        node_id: str,
        inputs: dict[str, Any],
        python_result: ExecutionResult,
        direct_result: ExecutionResult
    ) -> None:
        """Log a divergence for later analysis."""
        # TODO: Implement proper divergence logging
        print(f"DIVERGENCE detected in {node_id}")
        print(f"  Inputs: {inputs}")
        print(f"  Python: {python_result.data}")
        print(f"  Direct: {direct_result.data}")

    def execute_sync(
        self,
        node_id: str,
        inputs: dict[str, Any]
    ) -> ExecutionResult:
        """Synchronous wrapper for execute."""
        return asyncio.run(self.execute(node_id, inputs))

    def get_metrics(self, node_id: str) -> RuntimeMetrics:
        """Get execution metrics for a node."""
        return self.migration_controller.get_metrics(node_id)

    def get_confidence(self, node_id: str) -> float:
        """Get confidence score for a node."""
        return self.migration_controller.calculate_confidence(node_id)

    def set_mode(self, node_id: str, mode: ExecutionMode) -> None:
        """Set the execution mode for a node."""
        self.migration_controller.set_execution_mode(node_id, mode)

