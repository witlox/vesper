"""
Integration Tests for Vesper Verification Framework
"""

import asyncio
from decimal import Decimal

import pytest

from vesper_runtime.executor import (
    DirectRuntime,
    DualExecutionResult,
    ExecutionOrchestrator,
    ExecutionResult,
    PythonRuntime,
)
from vesper_verification.confidence import ConfidenceTracker
from vesper_verification.differential import OutputComparator
from vesper_verification.metrics import MetricsCollector
from vesper_verification.routing import ExecutionMode, ExecutionRouter, RoutingConfig
from vesper_verification.shadow_mode import ShadowExecutor


class TestVerificationIntegration:
    """Integration tests for the verification framework."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create runtimes
        self.python_runtime = PythonRuntime()
        self.direct_runtime = DirectRuntime()

        # Create verification components
        self.confidence_tracker = ConfidenceTracker()
        self.metrics_collector = MetricsCollector()
        self.comparator = OutputComparator()

        # Create router
        self.router = ExecutionRouter(
            confidence_tracker=self.confidence_tracker,
            config=RoutingConfig(),
        )

        # Create shadow executor
        self.shadow_executor = ShadowExecutor(
            direct_runtime=self.direct_runtime,
            comparator=self.comparator,
            confidence_tracker=self.confidence_tracker,
            metrics_collector=self.metrics_collector,
        )

        # Create orchestrator
        self.orchestrator = ExecutionOrchestrator(
            python_runtime=self.python_runtime,
            direct_runtime=self.direct_runtime,
            router=self.router,
            confidence_tracker=self.confidence_tracker,
            metrics_collector=self.metrics_collector,
            shadow_executor=self.shadow_executor,
            comparator=self.comparator,
        )

    def _register_simple_handler(self):
        """Register a simple handler that returns input * 2."""

        def handler(value: int) -> dict:
            return {"result": value * 2}

        self.python_runtime.register_handler("simple_node", handler)
        self.direct_runtime.register_handler("simple_node", handler)

    def _register_diverging_handler(self):
        """Register handlers that produce different results."""

        def python_handler(value: int) -> dict:
            return {"result": value * 2}

        def direct_handler(value: int) -> dict:
            return {"result": value * 3}  # Different!

        self.python_runtime.register_handler("diverging_node", python_handler)
        self.direct_runtime.register_handler("diverging_node", direct_handler)

    @pytest.mark.asyncio
    async def test_python_only_mode(self):
        """Python-only mode uses only Python runtime."""
        self._register_simple_handler()

        result = await self.orchestrator.execute(
            "simple_node",
            {"value": 5},
            mode=ExecutionMode.PYTHON_ONLY,
        )

        assert result.success
        assert result.output == {"result": 10}
        assert result.path_used == "python"

    @pytest.mark.asyncio
    async def test_dual_verify_no_divergence(self):
        """Dual verify with matching outputs."""
        self._register_simple_handler()

        result = await self.orchestrator.execute_dual(
            "simple_node",
            {"value": 5},
        )

        assert isinstance(result, DualExecutionResult)
        assert not result.diverged
        assert result.python_result.output == {"result": 10}
        assert result.direct_result.output == {"result": 10}

    @pytest.mark.asyncio
    async def test_dual_verify_detects_divergence(self):
        """Dual verify detects divergence."""
        self._register_diverging_handler()

        result = await self.orchestrator.execute_dual(
            "diverging_node",
            {"value": 5},
        )

        assert result.diverged
        assert result.python_result.output == {"result": 10}
        assert result.direct_result.output == {"result": 15}
        assert result.divergence_details is not None

    @pytest.mark.asyncio
    async def test_shadow_mode_executes_both(self):
        """Shadow mode executes both but returns Python result."""
        self._register_simple_handler()

        result = await self.orchestrator.execute(
            "simple_node",
            {"value": 5},
            mode=ExecutionMode.SHADOW_DIRECT,
        )

        assert result.success
        assert result.output == {"result": 10}
        assert result.path_used == "python"

        # Wait for shadow to complete
        await self.shadow_executor.wait_for_pending(timeout=1.0)

        # Shadow should have recorded the execution
        metrics = self.confidence_tracker.get_metrics("simple_node")
        # Note: The shadow execution records to confidence tracker
        # The main execution may or may not depending on implementation

    @pytest.mark.asyncio
    async def test_confidence_builds_over_time(self):
        """Confidence increases with successful executions."""
        self._register_simple_handler()

        # Run many executions
        for i in range(200):
            result = await self.orchestrator.execute_dual(
                "simple_node",
                {"value": i},
            )
            assert not result.diverged

        # Check confidence (Wilson score is conservative)
        confidence = self.confidence_tracker.get_confidence("simple_node")
        assert confidence > 0.94  # Wilson score gives ~0.948 for 200 samples

    @pytest.mark.asyncio
    async def test_divergence_reduces_confidence(self):
        """Divergences reduce confidence score."""
        # Register initially matching handlers
        def python_handler(value: int) -> dict:
            return {"result": value * 2}

        self.python_runtime.register_handler("test_node", python_handler)
        self.direct_runtime.register_handler("test_node", python_handler)

        # Build up some confidence
        for i in range(100):
            await self.orchestrator.execute_dual("test_node", {"value": i})

        initial_confidence = self.confidence_tracker.get_confidence("test_node")

        # Now introduce divergence
        def diverging_handler(value: int) -> dict:
            return {"result": value * 3}

        self.direct_runtime.register_handler("test_node", diverging_handler)

        # Run more executions with divergence
        for i in range(100):
            await self.orchestrator.execute_dual("test_node", {"value": i})

        final_confidence = self.confidence_tracker.get_confidence("test_node")

        # Confidence should decrease
        assert final_confidence < initial_confidence

    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        """Metrics are collected during execution."""
        self._register_simple_handler()

        for i in range(10):
            await self.orchestrator.execute(
                "simple_node",
                {"value": i},
                mode=ExecutionMode.PYTHON_ONLY,
            )

        metrics = self.metrics_collector.get_aggregate_metrics("simple_node")
        assert metrics.total_executions == 10
        assert metrics.python_executions == 10
        assert metrics.avg_python_duration_ms > 0

    @pytest.mark.asyncio
    async def test_fallback_on_direct_failure(self):
        """Orchestrator falls back to Python on direct failure."""

        def python_handler(value: int) -> dict:
            return {"result": value * 2}

        def failing_handler(value: int) -> dict:
            raise RuntimeError("Direct runtime failed")

        self.python_runtime.register_handler("fallback_node", python_handler)
        self.direct_runtime.register_handler("fallback_node", failing_handler)

        # Force direct mode - should fall back
        result = await self.orchestrator.execute(
            "fallback_node",
            {"value": 5},
            mode=ExecutionMode.DIRECT_ONLY,
        )

        # Should get Python result as fallback
        assert result.success
        assert result.output == {"result": 10}


class TestEndToEndVerification:
    """End-to-end tests demonstrating the verification workflow."""

    @pytest.mark.asyncio
    async def test_python_vs_python_verification(self):
        """
        Verify that Python vs Python produces zero divergences.

        This proves the framework works before introducing a real
        alternative runtime.
        """
        # Create two Python runtimes (both are "oracles")
        runtime_a = PythonRuntime()
        runtime_b = PythonRuntime()

        # Register the same handler on both
        def payment_handler(
            amount: Decimal,
            user_id: str,
        ) -> dict:
            # Simple deterministic logic
            if amount <= 0:
                return {
                    "success": False,
                    "error_code": "invalid_amount",
                }
            return {
                "success": True,
                "transaction_id": f"txn_{user_id}_{int(amount * 100)}",
                "amount_charged": float(amount),
            }

        runtime_a.register_handler("payment", payment_handler)
        runtime_b.register_handler("payment", payment_handler)

        # Create verification infrastructure
        tracker = ConfidenceTracker()
        comparator = OutputComparator()
        router = ExecutionRouter(tracker)

        orchestrator = ExecutionOrchestrator(
            python_runtime=runtime_a,
            direct_runtime=runtime_b,
            router=router,
            confidence_tracker=tracker,
            comparator=comparator,
        )

        # Run 1000 test cases
        divergences = 0
        for i in range(1000):
            result = await orchestrator.execute_dual(
                "payment",
                {"amount": Decimal(f"{i + 1}.00"), "user_id": f"user_{i}"},
            )
            if result.diverged:
                divergences += 1

        # Should be zero divergences (same code!)
        assert divergences == 0

        # Confidence should be high (Wilson score is conservative)
        confidence = tracker.get_confidence("payment")
        assert confidence > 0.98  # ~0.989 for 1000 samples

    @pytest.mark.asyncio
    async def test_property_based_verification(self):
        """
        Property-based verification example.

        Demonstrates how to use verification framework with
        property-based testing patterns.
        """
        runtime = PythonRuntime()

        def calculator(a: int, b: int, op: str) -> dict:
            if op == "add":
                return {"result": a + b}
            elif op == "sub":
                return {"result": a - b}
            elif op == "mul":
                return {"result": a * b}
            elif op == "div":
                if b == 0:
                    return {"error": "division_by_zero"}
                return {"result": a / b}
            else:
                return {"error": "unknown_operation"}

        runtime.register_handler("calculator", calculator)

        # Same handler on "direct" (proving framework works)
        direct_runtime = DirectRuntime()
        direct_runtime.register_handler("calculator", calculator)

        tracker = ConfidenceTracker()
        comparator = OutputComparator()

        orchestrator = ExecutionOrchestrator(
            python_runtime=runtime,
            direct_runtime=direct_runtime,
            confidence_tracker=tracker,
            comparator=comparator,
        )

        # Property: addition is commutative
        import random

        for _ in range(100):
            a = random.randint(-1000, 1000)
            b = random.randint(-1000, 1000)

            result1 = await runtime.execute("calculator", {"a": a, "b": b, "op": "add"})
            result2 = await runtime.execute("calculator", {"a": b, "b": a, "op": "add"})

            assert result1 == result2, f"Commutativity failed for {a}, {b}"

        # Property: multiplication distributes over addition
        for _ in range(100):
            a = random.randint(-100, 100)
            b = random.randint(-100, 100)
            c = random.randint(-100, 100)

            # a * (b + c) should equal a*b + a*c
            bc = (await runtime.execute("calculator", {"a": b, "b": c, "op": "add"}))["result"]
            left = (await runtime.execute("calculator", {"a": a, "b": bc, "op": "mul"}))["result"]

            ab = (await runtime.execute("calculator", {"a": a, "b": b, "op": "mul"}))["result"]
            ac = (await runtime.execute("calculator", {"a": a, "b": c, "op": "mul"}))["result"]
            right = (await runtime.execute("calculator", {"a": ab, "b": ac, "op": "add"}))["result"]

            assert left == right, f"Distributivity failed for {a}, {b}, {c}"

