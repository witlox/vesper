"""
Tests for Shadow Mode Execution
"""

import asyncio

import pytest

from vesper_verification.confidence import ConfidenceTracker
from vesper_verification.differential import OutputComparator
from vesper_verification.shadow_mode import ExecutionResult, ShadowExecutor


class MockDirectRuntime:
    """Mock direct runtime for testing."""

    def __init__(self, response: dict = None, delay: float = 0.0, fail: bool = False):
        self.response = response or {"result": "direct"}
        self.delay = delay
        self.fail = fail
        self.calls = []

    async def execute(self, node_id: str, inputs: dict) -> dict:
        self.calls.append({"node_id": node_id, "inputs": inputs})
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("Simulated direct failure")
        return self.response


class TestShadowExecutor:
    """Tests for ShadowExecutor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.confidence_tracker = ConfidenceTracker()
        self.comparator = OutputComparator()

    @pytest.mark.asyncio
    async def test_shadow_execution_non_blocking(self):
        """Shadow execution doesn't block the caller."""
        direct_runtime = MockDirectRuntime(delay=0.1)

        executor = ShadowExecutor(
            direct_runtime=direct_runtime,
            comparator=self.comparator,
            confidence_tracker=self.confidence_tracker,
        )

        python_result = ExecutionResult(
            output={"result": "python"},
            execution_time_ms=10.0,
            path_used="python",
            trace_id="test-trace",
            success=True,
        )

        import time
        start = time.perf_counter()

        # This should return immediately
        executor.execute_shadow("test_node", {"input": 1}, python_result)

        elapsed = time.perf_counter() - start
        # Should be much less than the 0.1s delay
        assert elapsed < 0.05

        # Wait for shadow to complete
        await executor.wait_for_pending(timeout=1.0)
        assert len(direct_runtime.calls) == 1

    @pytest.mark.asyncio
    async def test_no_divergence_records_success(self):
        """No divergence records success in confidence tracker."""
        direct_runtime = MockDirectRuntime(response={"result": "same"})

        executor = ShadowExecutor(
            direct_runtime=direct_runtime,
            comparator=self.comparator,
            confidence_tracker=self.confidence_tracker,
        )

        python_result = ExecutionResult(
            output={"result": "same"},
            execution_time_ms=10.0,
            path_used="python",
            trace_id="test-trace",
            success=True,
        )

        executor.execute_shadow("test_node", {"input": 1}, python_result)
        await executor.wait_for_pending(timeout=1.0)

        metrics = self.confidence_tracker.get_metrics("test_node")
        assert metrics is not None
        assert metrics.total_executions == 1
        assert metrics.divergences == 0

    @pytest.mark.asyncio
    async def test_divergence_records_failure(self):
        """Divergence records failure in confidence tracker."""
        direct_runtime = MockDirectRuntime(response={"result": "different"})

        executor = ShadowExecutor(
            direct_runtime=direct_runtime,
            comparator=self.comparator,
            confidence_tracker=self.confidence_tracker,
        )

        python_result = ExecutionResult(
            output={"result": "python"},
            execution_time_ms=10.0,
            path_used="python",
            trace_id="test-trace",
            success=True,
        )

        executor.execute_shadow("test_node", {"input": 1}, python_result)
        await executor.wait_for_pending(timeout=1.0)

        metrics = self.confidence_tracker.get_metrics("test_node")
        assert metrics is not None
        assert metrics.total_executions == 1
        assert metrics.divergences == 1

    @pytest.mark.asyncio
    async def test_direct_error_counts_as_divergence(self):
        """Direct runtime error counts as divergence."""
        direct_runtime = MockDirectRuntime(fail=True)

        executor = ShadowExecutor(
            direct_runtime=direct_runtime,
            comparator=self.comparator,
            confidence_tracker=self.confidence_tracker,
        )

        python_result = ExecutionResult(
            output={"result": "python"},
            execution_time_ms=10.0,
            path_used="python",
            trace_id="test-trace",
            success=True,
        )

        executor.execute_shadow("test_node", {"input": 1}, python_result)
        await executor.wait_for_pending(timeout=1.0)

        metrics = self.confidence_tracker.get_metrics("test_node")
        assert metrics is not None
        assert metrics.divergences == 1
        assert metrics.direct_errors == 1

    @pytest.mark.asyncio
    async def test_pending_count(self):
        """Pending count tracks active shadow executions."""
        direct_runtime = MockDirectRuntime(delay=0.1)

        executor = ShadowExecutor(
            direct_runtime=direct_runtime,
            comparator=self.comparator,
            confidence_tracker=self.confidence_tracker,
        )

        python_result = ExecutionResult(
            output={"result": "python"},
            execution_time_ms=10.0,
            path_used="python",
            trace_id="test-trace",
            success=True,
        )

        # Launch multiple shadow executions
        for i in range(5):
            executor.execute_shadow("test_node", {"input": i}, python_result)

        assert executor.pending_count == 5

        await executor.wait_for_pending(timeout=1.0)
        assert executor.pending_count == 0

    @pytest.mark.asyncio
    async def test_wait_for_pending_timeout(self):
        """Wait for pending handles timeout."""
        direct_runtime = MockDirectRuntime(delay=1.0)  # Long delay

        executor = ShadowExecutor(
            direct_runtime=direct_runtime,
            comparator=self.comparator,
            confidence_tracker=self.confidence_tracker,
        )

        python_result = ExecutionResult(
            output={"result": "python"},
            execution_time_ms=10.0,
            path_used="python",
            trace_id="test-trace",
            success=True,
        )

        executor.execute_shadow("test_node", {"input": 1}, python_result)

        # This should timeout
        count = await executor.wait_for_pending(timeout=0.1)
        assert count == 1  # One was pending

    @pytest.mark.asyncio
    async def test_multiple_nodes(self):
        """Shadow execution works for multiple nodes."""
        direct_runtime = MockDirectRuntime(response={"result": "same"})

        executor = ShadowExecutor(
            direct_runtime=direct_runtime,
            comparator=self.comparator,
            confidence_tracker=self.confidence_tracker,
        )

        python_result = ExecutionResult(
            output={"result": "same"},
            execution_time_ms=10.0,
            path_used="python",
            trace_id="test-trace",
            success=True,
        )

        executor.execute_shadow("node_a", {"input": 1}, python_result)
        executor.execute_shadow("node_b", {"input": 2}, python_result)
        executor.execute_shadow("node_a", {"input": 3}, python_result)

        await executor.wait_for_pending(timeout=1.0)

        assert self.confidence_tracker.get_metrics("node_a").total_executions == 2
        assert self.confidence_tracker.get_metrics("node_b").total_executions == 1


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_to_dict(self):
        """ExecutionResult serializes to dict."""
        result = ExecutionResult(
            output={"result": 42},
            execution_time_ms=10.5,
            path_used="python",
            trace_id="abc-123",
            success=True,
        )

        d = result.to_dict()
        assert d["output"] == {"result": 42}
        assert d["execution_time_ms"] == 10.5
        assert d["path_used"] == "python"
        assert d["trace_id"] == "abc-123"
        assert d["success"] is True

    def test_to_dict_with_error(self):
        """ExecutionResult with error serializes correctly."""
        result = ExecutionResult(
            output={},
            execution_time_ms=0.0,
            path_used="direct",
            trace_id="abc-123",
            success=False,
            error=RuntimeError("test error"),
        )

        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "test error"

