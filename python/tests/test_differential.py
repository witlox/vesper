"""
Tests for Differential Testing
"""

from decimal import Decimal

import pytest
from vesper_verification.differential import (
    DifferentialTester,
    Divergence,
    OutputComparator,
)


class TestOutputComparator:
    """Tests for OutputComparator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.comparator = OutputComparator()

    def test_equal_dicts(self):
        """Equal dicts return None (no diff)."""
        result = self.comparator.compare(
            {"a": 1, "b": "hello"},
            {"a": 1, "b": "hello"},
        )
        assert result is None

    def test_different_values(self):
        """Different values are detected."""
        result = self.comparator.compare(
            {"a": 1},
            {"a": 2},
        )
        assert result is not None
        assert result["count"] == 1
        assert result["differences"][0]["path"] == "root.a"

    def test_missing_key_in_direct(self):
        """Missing key in direct is detected."""
        result = self.comparator.compare(
            {"a": 1, "b": 2},
            {"a": 1},
        )
        assert result is not None
        assert any(d["type"] == "missing_in_direct" for d in result["differences"])

    def test_missing_key_in_python(self):
        """Extra key in direct is detected."""
        result = self.comparator.compare(
            {"a": 1},
            {"a": 1, "b": 2},
        )
        assert result is not None
        assert any(d["type"] == "missing_in_python" for d in result["differences"])

    def test_nested_dicts(self):
        """Nested differences are detected with paths."""
        result = self.comparator.compare(
            {"outer": {"inner": 1}},
            {"outer": {"inner": 2}},
        )
        assert result is not None
        assert result["differences"][0]["path"] == "root.outer.inner"

    def test_list_comparison(self):
        """Lists are compared element by element."""
        result = self.comparator.compare(
            {"items": [1, 2, 3]},
            {"items": [1, 2, 3]},
        )
        assert result is None

    def test_list_different_values(self):
        """List element differences are detected."""
        result = self.comparator.compare(
            {"items": [1, 2, 3]},
            {"items": [1, 99, 3]},
        )
        assert result is not None
        assert result["differences"][0]["path"] == "root.items[1]"

    def test_list_different_lengths(self):
        """List length differences are detected."""
        result = self.comparator.compare(
            {"items": [1, 2, 3]},
            {"items": [1, 2]},
        )
        assert result is not None
        assert any(d["type"] == "length_mismatch" for d in result["differences"])

    def test_float_epsilon_tolerance(self):
        """Floats within epsilon are considered equal."""
        comparator = OutputComparator(epsilon=1e-6)
        result = comparator.compare(
            {"value": 1.0000001},
            {"value": 1.0000002},
        )
        assert result is None

    def test_float_beyond_epsilon(self):
        """Floats beyond epsilon are detected."""
        comparator = OutputComparator(epsilon=1e-9)
        result = comparator.compare(
            {"value": 1.0},
            {"value": 1.001},
        )
        assert result is not None

    def test_decimal_vs_float(self):
        """Decimal and float are compared numerically."""
        result = self.comparator.compare(
            {"amount": Decimal("10.50")},
            {"amount": 10.50},
        )
        assert result is None

    def test_nan_handling(self):
        """NaN values are handled."""
        result = self.comparator.compare(
            {"value": float("nan")},
            {"value": float("nan")},
        )
        assert result is None  # Both NaN is equal

    def test_nan_vs_number(self):
        """NaN vs number is a divergence."""
        result = self.comparator.compare(
            {"value": float("nan")},
            {"value": 1.0},
        )
        assert result is not None

    def test_infinity_handling(self):
        """Infinity values are compared correctly."""
        result = self.comparator.compare(
            {"value": float("inf")},
            {"value": float("inf")},
        )
        assert result is None

    def test_timestamp_tolerance(self):
        """Timestamps within tolerance are equal."""
        comparator = OutputComparator(timestamp_tolerance_ms=5000)
        result = comparator.compare(
            {"time": "2025-01-01T10:00:00Z"},
            {"time": "2025-01-01T10:00:02Z"},
        )
        assert result is None

    def test_timestamp_beyond_tolerance(self):
        """Timestamps beyond tolerance are different."""
        comparator = OutputComparator(timestamp_tolerance_ms=1000)
        result = comparator.compare(
            {"time": "2025-01-01T10:00:00Z"},
            {"time": "2025-01-01T10:01:00Z"},
        )
        assert result is not None

    def test_none_values(self):
        """None values are handled."""
        result = self.comparator.compare(
            {"value": None},
            {"value": None},
        )
        assert result is None

    def test_none_vs_value(self):
        """None vs value is a divergence."""
        result = self.comparator.compare(
            {"value": None},
            {"value": 1},
        )
        assert result is not None

    def test_type_mismatch(self):
        """Type mismatches are detected."""
        result = self.comparator.compare(
            {"value": "123"},
            {"value": 123},
        )
        assert result is not None
        assert result["differences"][0]["type"] == "type_mismatch"

    def test_relative_epsilon_for_large_numbers(self):
        """Large numbers use relative epsilon."""
        result = self.comparator.compare(
            {"value": 1000000.0},
            {"value": 1000000.0000001},
        )
        assert result is None


class MockRuntime:
    """Mock runtime for testing."""

    def __init__(self, responses: dict = None):
        self.responses = responses or {}
        self.calls = []

    async def execute(self, node_id: str, inputs: dict) -> dict:
        self.calls.append({"node_id": node_id, "inputs": inputs})
        if node_id in self.responses:
            response = self.responses[node_id]
            if callable(response):
                return response(inputs)
            return response
        return {"result": "default"}


class TestDifferentialTester:
    """Tests for DifferentialTester."""

    @pytest.mark.asyncio
    async def test_no_divergence(self):
        """Test passes when outputs match."""
        python_runtime = MockRuntime({"test_node": {"result": 42}})
        direct_runtime = MockRuntime({"test_node": {"result": 42}})

        tester = DifferentialTester(python_runtime, direct_runtime)
        result = await tester.test_node(
            "test_node",
            [{"input": 1}, {"input": 2}, {"input": 3}],
        )

        assert result.total_tests == 3
        assert result.passed == 3
        assert result.failed == 0
        assert len(result.divergences) == 0

    @pytest.mark.asyncio
    async def test_divergence_detected(self):
        """Test detects divergence."""
        python_runtime = MockRuntime({"test_node": {"result": 42}})
        direct_runtime = MockRuntime({"test_node": {"result": 99}})

        tester = DifferentialTester(python_runtime, direct_runtime)
        result = await tester.test_node(
            "test_node",
            [{"input": 1}],
        )

        assert result.total_tests == 1
        assert result.passed == 0
        assert result.failed == 1
        assert len(result.divergences) == 1

    @pytest.mark.asyncio
    async def test_divergence_callback(self):
        """Divergence callback is called."""
        python_runtime = MockRuntime({"test_node": {"result": 42}})
        direct_runtime = MockRuntime({"test_node": {"result": 99}})

        divergences_received = []

        def on_divergence(div: Divergence):
            divergences_received.append(div)

        tester = DifferentialTester(python_runtime, direct_runtime)
        await tester.test_node(
            "test_node",
            [{"input": 1}],
            on_divergence=on_divergence,
        )

        assert len(divergences_received) == 1
        assert divergences_received[0].node_id == "test_node"

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Errors in execution are handled gracefully."""

        class FailingRuntime:
            async def execute(self, node_id: str, inputs: dict) -> dict:
                raise RuntimeError("Simulated failure")

        python_runtime = MockRuntime({"test_node": {"result": 42}})
        failing_runtime = FailingRuntime()

        tester = DifferentialTester(python_runtime, failing_runtime)
        result = await tester.test_node(
            "test_node",
            [{"input": 1}],
        )

        assert result.total_tests == 1
        assert result.failed == 1
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_success_rate(self):
        """Success rate is calculated correctly."""

        def python_response(inputs):
            return {"result": inputs.get("value", 0) * 2}

        def direct_response(inputs):
            # Diverges for value > 5
            value = inputs.get("value", 0)
            if value > 5:
                return {"result": value * 3}  # Wrong
            return {"result": value * 2}

        python_runtime = MockRuntime({"test_node": python_response})
        direct_runtime = MockRuntime({"test_node": direct_response})

        tester = DifferentialTester(python_runtime, direct_runtime)
        result = await tester.test_node(
            "test_node",
            [{"value": i} for i in range(10)],  # 0-9
        )

        # Values 0-5 pass (6 tests), 6-9 fail (4 tests)
        assert result.passed == 6
        assert result.failed == 4
        assert result.success_rate == 0.6

    @pytest.mark.asyncio
    async def test_with_random_inputs(self):
        """Test with random input generator."""
        import random

        python_runtime = MockRuntime({"test_node": {"result": 42}})
        direct_runtime = MockRuntime({"test_node": {"result": 42}})

        def generate_input() -> dict:
            return {"value": random.randint(0, 100)}

        tester = DifferentialTester(python_runtime, direct_runtime)
        result = await tester.test_with_random_inputs(
            "test_node",
            generate_input,
            num_tests=50,
        )

        assert result.total_tests == 50
        assert result.passed == 50

    @pytest.mark.asyncio
    async def test_duration_tracked(self):
        """Execution duration is tracked."""
        python_runtime = MockRuntime({"test_node": {"result": 42}})
        direct_runtime = MockRuntime({"test_node": {"result": 42}})

        tester = DifferentialTester(python_runtime, direct_runtime)
        result = await tester.test_node(
            "test_node",
            [{"input": i} for i in range(10)],
        )

        assert result.duration_ms > 0


class TestDivergence:
    """Tests for Divergence dataclass."""

    def test_to_dict(self):
        """Divergence serializes to dict."""
        div = Divergence(
            node_id="test_node",
            inputs={"x": 1},
            python_output={"result": 2},
            direct_output={"result": 3},
            diff={"differences": [{"path": "result", "type": "value_mismatch"}]},
            timestamp="2025-01-08T10:00:00Z",
            trace_id="abc-123",
        )

        d = div.to_dict()
        assert d["node_id"] == "test_node"
        assert d["inputs"] == {"x": 1}
        assert d["python_output"] == {"result": 2}
        assert d["direct_output"] == {"result": 3}
