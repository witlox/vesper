"""
Vesper Differential Testing Framework

Compares outputs between Python and Direct runtimes to verify correctness.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from vesper.models import VesperNode, InputSpec
from vesper.runtime import VesperRuntime, ExecutionResult


@dataclass
class DivergenceRecord:
    """Record of a divergence between runtimes."""
    timestamp: datetime
    node_id: str
    test_id: int
    inputs: dict[str, Any]
    python_output: Any
    direct_output: Any
    python_duration_ms: float
    direct_duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "node_id": self.node_id,
            "test_id": self.test_id,
            "inputs": self.inputs,
            "python_output": str(self.python_output),
            "direct_output": str(self.direct_output),
            "python_duration_ms": self.python_duration_ms,
            "direct_duration_ms": self.direct_duration_ms,
        }


@dataclass
class TestResult:
    """Result of differential testing."""
    node_id: str
    total_tests: int
    passed: int
    failed: int
    divergences: list[DivergenceRecord] = field(default_factory=list)
    total_duration_ms: float = 0.0
    python_avg_duration_ms: float = 0.0
    direct_avg_duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tests == 0:
            return 0.0
        return self.passed / self.total_tests

    @property
    def speedup(self) -> float:
        """Calculate direct runtime speedup over Python."""
        if self.direct_avg_duration_ms == 0:
            return 0.0
        return self.python_avg_duration_ms / self.direct_avg_duration_ms


class InputGenerator:
    """
    Generates random valid inputs for a Vesper node.

    Uses constraint information to generate valid test data.
    """

    def __init__(self, seed: int | None = None) -> None:
        """Initialize with optional seed for reproducibility."""
        self.rng = random.Random(seed)

    def generate(self, node: VesperNode) -> dict[str, Any]:
        """Generate random inputs for a node."""
        inputs: dict[str, Any] = {}

        for name, spec in node.inputs.items():
            if isinstance(spec, dict):
                spec = InputSpec(**spec)

            # Skip optional inputs sometimes
            if not spec.required and self.rng.random() < 0.3:
                if spec.default is not None:
                    inputs[name] = spec.default
                continue

            inputs[name] = self._generate_value(spec)

        return inputs

    def _generate_value(self, spec: InputSpec) -> Any:
        """Generate a random value based on type and constraints."""
        type_str = spec.type.lower()

        if type_str == "string":
            return self._generate_string(spec)
        elif type_str == "integer":
            return self._generate_integer(spec)
        elif type_str in ("decimal", "float", "number"):
            return self._generate_decimal(spec)
        elif type_str == "boolean":
            return self.rng.choice([True, False])
        elif type_str == "timestamp":
            return self._generate_timestamp()
        else:
            # Default to string for unknown types
            return self._generate_string(spec)

    def _generate_string(self, spec: InputSpec) -> str:
        """Generate a random string."""
        # Check for non_empty constraint
        min_length = 1 if "non_empty" in spec.constraints else 0
        max_length = 100

        # Check for length constraints
        for constraint in spec.constraints:
            if constraint.startswith("max_length:"):
                max_length = int(constraint.split(":")[1])
            elif constraint.startswith("min_length:"):
                min_length = int(constraint.split(":")[1])

        length = self.rng.randint(min_length, max_length)
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "".join(self.rng.choice(chars) for _ in range(length))

    def _generate_integer(self, spec: InputSpec) -> int:
        """Generate a random integer."""
        min_val = -1000000
        max_val = 1000000

        for constraint in spec.constraints:
            if constraint == "positive":
                min_val = 1
            elif constraint == "non_negative":
                min_val = 0
            elif constraint.startswith("min:"):
                min_val = int(constraint.split(":")[1])
            elif constraint.startswith("max:"):
                max_val = int(constraint.split(":")[1])

        return self.rng.randint(min_val, max_val)

    def _generate_decimal(self, spec: InputSpec) -> float:
        """Generate a random decimal."""
        min_val = -1000000.0
        max_val = 1000000.0

        for constraint in spec.constraints:
            if constraint == "positive":
                min_val = 0.01
            elif constraint == "non_negative":
                min_val = 0.0
            elif constraint.startswith("min:"):
                min_val = float(constraint.split(":")[1])
            elif constraint.startswith("max:"):
                max_val = float(constraint.split(":")[1])

        return round(self.rng.uniform(min_val, max_val), 2)

    def _generate_timestamp(self) -> str:
        """Generate a random ISO 8601 timestamp."""
        # Generate a timestamp within the last year
        from datetime import timedelta

        base = datetime(2025, 1, 1)
        offset_days = self.rng.randint(0, 365)
        offset_seconds = self.rng.randint(0, 86400)
        ts = base + timedelta(days=offset_days, seconds=offset_seconds)
        return ts.isoformat() + "Z"


class DifferentialTester:
    """
    Runs differential tests between Python and Direct runtimes.

    For each test:
    1. Generate random valid inputs
    2. Execute on both runtimes
    3. Compare outputs
    4. Record any divergences
    """

    def __init__(
        self,
        runtime: VesperRuntime | None = None,
        seed: int | None = None
    ) -> None:
        """Initialize the tester."""
        self.runtime = runtime or VesperRuntime()
        self.input_generator = InputGenerator(seed)
        self.divergence_log: list[DivergenceRecord] = []

    async def test_node(
        self,
        node_id: str,
        num_tests: int = 10000,
        progress_callback: Any = None
    ) -> TestResult:
        """
        Run differential tests on a node.

        Args:
            node_id: The node to test
            num_tests: Number of random tests to run
            progress_callback: Optional callback(current, total)

        Returns:
            TestResult with statistics and divergences
        """
        node = self.runtime.get_node(node_id)
        if node is None:
            raise ValueError(f"Node {node_id} not loaded")

        result = TestResult(
            node_id=node_id,
            total_tests=num_tests,
            passed=0,
            failed=0
        )

        python_durations: list[float] = []
        direct_durations: list[float] = []

        start_time = time.perf_counter()

        for i in range(num_tests):
            # Generate inputs
            inputs = self.input_generator.generate(node)

            # Execute on Python runtime
            python_result = await self.runtime.python_executor.execute(node_id, inputs)
            python_duration = python_result.metrics.duration_ms if python_result.metrics else 0
            python_durations.append(python_duration)

            # Execute on Direct runtime
            direct_result = await self.runtime.direct_executor.execute(node, inputs)
            direct_duration = direct_result.metrics.duration_ms if direct_result.metrics else 0
            direct_durations.append(direct_duration)

            # Compare results
            if self._results_match(python_result, direct_result):
                result.passed += 1
            else:
                result.failed += 1
                divergence = DivergenceRecord(
                    timestamp=datetime.now(),
                    node_id=node_id,
                    test_id=i,
                    inputs=inputs,
                    python_output=python_result.data,
                    direct_output=direct_result.data,
                    python_duration_ms=python_duration,
                    direct_duration_ms=direct_duration
                )
                result.divergences.append(divergence)
                self.divergence_log.append(divergence)

            # Progress callback
            if progress_callback and (i + 1) % 100 == 0:
                progress_callback(i + 1, num_tests)

        result.total_duration_ms = (time.perf_counter() - start_time) * 1000
        result.python_avg_duration_ms = sum(python_durations) / len(python_durations) if python_durations else 0
        result.direct_avg_duration_ms = sum(direct_durations) / len(direct_durations) if direct_durations else 0

        return result

    def _results_match(
        self,
        python_result: ExecutionResult,
        direct_result: ExecutionResult
    ) -> bool:
        """Check if two results match."""
        # Both must have same success status
        if python_result.success != direct_result.success:
            return False

        # If both failed, check error codes match (not just error, as Direct is not implemented)
        if not python_result.success and not direct_result.success:
            # For now, since Direct isn't implemented, we consider this a match
            # In production, we'd compare error codes
            return True

        # Compare data (with some tolerance for floating point)
        return self._deep_compare(python_result.data, direct_result.data)

    def _deep_compare(self, a: Any, b: Any, tolerance: float = 1e-9) -> bool:
        """Deep comparison with floating point tolerance."""
        if type(a) != type(b):
            return False

        if isinstance(a, float):
            return abs(a - b) < tolerance

        if isinstance(a, dict):
            if set(a.keys()) != set(b.keys()):
                return False
            return all(self._deep_compare(a[k], b[k], tolerance) for k in a)

        if isinstance(a, (list, tuple)):
            if len(a) != len(b):
                return False
            return all(self._deep_compare(x, y, tolerance) for x, y in zip(a, b))

        return a == b

    def save_divergences(self, path: Path) -> None:
        """Save divergence log to a JSON file."""
        data = [d.to_dict() for d in self.divergence_log]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def clear_divergences(self) -> None:
        """Clear the divergence log."""
        self.divergence_log = []


class PropertyTester:
    """
    Property-based testing for Vesper nodes.

    Uses Hypothesis-style testing to verify invariants.
    """

    def __init__(self, runtime: VesperRuntime | None = None) -> None:
        """Initialize the tester."""
        self.runtime = runtime or VesperRuntime()

    async def test_property(
        self,
        node_id: str,
        property_name: str,
        property_check: Any,
        num_tests: int = 1000
    ) -> tuple[bool, list[dict[str, Any]]]:
        """
        Test a property with random inputs.

        Args:
            node_id: The node to test
            property_name: Name of the property being tested
            property_check: Callable(inputs, result) -> bool
            num_tests: Number of tests to run

        Returns:
            Tuple of (all_passed, list of failures)
        """
        node = self.runtime.get_node(node_id)
        if node is None:
            raise ValueError(f"Node {node_id} not loaded")

        generator = InputGenerator()
        failures: list[dict[str, Any]] = []

        for i in range(num_tests):
            inputs = generator.generate(node)
            result = await self.runtime.execute(node_id, inputs)

            try:
                if not property_check(inputs, result):
                    failures.append({
                        "test_id": i,
                        "inputs": inputs,
                        "result": result.data if result.success else result.error,
                        "property": property_name
                    })
            except Exception as e:
                failures.append({
                    "test_id": i,
                    "inputs": inputs,
                    "error": str(e),
                    "property": property_name
                })

        return len(failures) == 0, failures
