"""
Differential Testing for Vesper Verification

Implements comparison logic and divergence detection between
Python (oracle) and direct runtime implementations.
"""

from __future__ import annotations

import asyncio
import logging
import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class Divergence:
    """Details about a divergence between two execution paths."""

    node_id: str
    inputs: dict[str, Any]
    python_output: dict[str, Any]
    direct_output: dict[str, Any]
    diff: dict[str, Any]
    timestamp: str
    trace_id: str

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "node_id": self.node_id,
            "inputs": self.inputs,
            "python_output": self.python_output,
            "direct_output": self.direct_output,
            "diff": self.diff,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
        }


class OutputComparator:
    """
    Compare outputs from different runtimes.

    Handles:
    - Deep equality checks
    - Type coercion (Decimal vs float)
    - Timestamp tolerance
    - Floating point epsilon
    - NaN handling
    - Nested structures
    """

    def __init__(
        self,
        epsilon: float = 1e-9,
        timestamp_tolerance_ms: int = 1000,
    ) -> None:
        self.epsilon = epsilon
        self.timestamp_tolerance_ms = timestamp_tolerance_ms

    def compare(
        self,
        python_output: dict[str, Any],
        direct_output: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Compare two outputs for equality.

        Returns None if equal, dict describing differences if diverged.
        """
        differences = self._compare_recursive(python_output, direct_output, path="root")

        if differences:
            return {"differences": differences, "count": len(differences)}
        return None

    def _compare_recursive(self, v1: Any, v2: Any, path: str) -> list[dict[str, Any]]:
        """Recursively compare two values."""
        differences: list[dict[str, Any]] = []

        if v1 is None and v2 is None:
            return differences
        if v1 is None or v2 is None:
            differences.append(
                {
                    "path": path,
                    "type": "null_mismatch",
                    "python_value": v1,
                    "direct_value": v2,
                }
            )
            return differences

        if not self._types_compatible(v1, v2):
            differences.append(
                {
                    "path": path,
                    "type": "type_mismatch",
                    "python_type": type(v1).__name__,
                    "direct_type": type(v2).__name__,
                    "python_value": repr(v1),
                    "direct_value": repr(v2),
                }
            )
            return differences

        if isinstance(v1, dict):
            differences.extend(self._compare_dicts(v1, v2, path))
        elif isinstance(v1, (list, tuple)):
            differences.extend(self._compare_lists(v1, v2, path))
        elif isinstance(v1, (float, Decimal)) or isinstance(v2, (float, Decimal)):
            diff = self._compare_numbers(v1, v2, path)
            if diff:
                differences.append(diff)
        elif isinstance(v1, str) and self._looks_like_timestamp(v1):
            diff = self._compare_timestamps(v1, v2, path)
            if diff:
                differences.append(diff)
        else:
            if v1 != v2:
                differences.append(
                    {
                        "path": path,
                        "type": "value_mismatch",
                        "python_value": v1,
                        "direct_value": v2,
                    }
                )

        return differences

    def _types_compatible(self, v1: Any, v2: Any) -> bool:
        """Check if two types are compatible for comparison."""
        if type(v1) is type(v2):
            return True
        numeric_types = (int, float, Decimal)
        if isinstance(v1, numeric_types) and isinstance(v2, numeric_types):
            return True
        if isinstance(v1, (list, tuple)) and isinstance(v2, (list, tuple)):
            return True
        return False

    def _compare_dicts(self, d1: dict, d2: dict, path: str) -> list[dict[str, Any]]:
        """Compare two dictionaries."""
        differences: list[dict[str, Any]] = []
        all_keys = set(d1.keys()) | set(d2.keys())

        for key in all_keys:
            key_path = f"{path}.{key}"
            if key not in d1:
                differences.append(
                    {
                        "path": key_path,
                        "type": "missing_in_python",
                        "direct_value": d2[key],
                    }
                )
            elif key not in d2:
                differences.append(
                    {
                        "path": key_path,
                        "type": "missing_in_direct",
                        "python_value": d1[key],
                    }
                )
            else:
                differences.extend(self._compare_recursive(d1[key], d2[key], key_path))
        return differences

    def _compare_lists(
        self, l1: list | tuple, l2: list | tuple, path: str
    ) -> list[dict[str, Any]]:
        """Compare two lists/tuples."""
        differences: list[dict[str, Any]] = []

        if len(l1) != len(l2):
            differences.append(
                {
                    "path": path,
                    "type": "length_mismatch",
                    "python_length": len(l1),
                    "direct_length": len(l2),
                }
            )

        for i in range(min(len(l1), len(l2))):
            differences.extend(self._compare_recursive(l1[i], l2[i], f"{path}[{i}]"))
        return differences

    def _compare_numbers(
        self, n1: int | float | Decimal, n2: int | float | Decimal, path: str
    ) -> dict[str, Any] | None:
        """Compare two numbers with epsilon tolerance."""
        f1 = float(n1)
        f2 = float(n2)

        if math.isnan(f1) and math.isnan(f2):
            return None
        if math.isnan(f1) or math.isnan(f2):
            return {
                "path": path,
                "type": "nan_mismatch",
                "python_value": n1,
                "direct_value": n2,
            }

        if math.isinf(f1) and math.isinf(f2):
            if (f1 > 0) == (f2 > 0):
                return None
            return {
                "path": path,
                "type": "infinity_sign_mismatch",
                "python_value": n1,
                "direct_value": n2,
            }

        if abs(f1 - f2) <= self.epsilon:
            return None

        if abs(f1) > 1.0 or abs(f2) > 1.0:
            relative_diff = abs(f1 - f2) / max(abs(f1), abs(f2))
            if relative_diff <= self.epsilon:
                return None

        return {
            "path": path,
            "type": "numeric_mismatch",
            "python_value": n1,
            "direct_value": n2,
            "difference": abs(f1 - f2),
        }

    def _looks_like_timestamp(self, s: str) -> bool:
        """Check if a string looks like a timestamp."""
        if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
            return True
        return False

    def _compare_timestamps(self, t1: str, t2: str, path: str) -> dict[str, Any] | None:
        """Compare two timestamps with tolerance."""
        try:
            dt1 = datetime.fromisoformat(t1.replace("Z", "+00:00"))
            dt2 = datetime.fromisoformat(t2.replace("Z", "+00:00"))
            diff_ms = abs((dt1 - dt2).total_seconds() * 1000)

            if diff_ms <= self.timestamp_tolerance_ms:
                return None

            return {
                "path": path,
                "type": "timestamp_mismatch",
                "python_value": t1,
                "direct_value": t2,
                "difference_ms": diff_ms,
            }
        except (ValueError, TypeError):
            if t1 != t2:
                return {
                    "path": path,
                    "type": "value_mismatch",
                    "python_value": t1,
                    "direct_value": t2,
                }
            return None


class RuntimeProtocol(Protocol):
    """Protocol for runtime implementations."""

    async def execute(self, node_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute a node with the given inputs."""
        ...


@dataclass
class DiffTestResult:
    """Result of a differential test."""

    node_id: str
    total_tests: int
    passed: int
    failed: int
    divergences: list[Divergence] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        """Proportion of tests that passed."""
        if self.total_tests == 0:
            return 0.0
        return self.passed / self.total_tests


class DifferentialTester:
    """
    Run differential tests between Python and direct runtimes.

    Generates random inputs based on node specification,
    executes both paths, and detects divergences.
    """

    def __init__(
        self,
        python_runtime: RuntimeProtocol,
        direct_runtime: RuntimeProtocol,
        comparator: OutputComparator | None = None,
    ) -> None:
        self.python_runtime = python_runtime
        self.direct_runtime = direct_runtime
        self.comparator = comparator or OutputComparator()

    async def test_node(
        self,
        node_id: str,
        test_inputs: list[dict[str, Any]],
        on_divergence: Callable[[Divergence], None] | None = None,
    ) -> DiffTestResult:
        """Run differential tests on a node with provided inputs."""
        import time

        start_time = time.perf_counter()

        result = DiffTestResult(
            node_id=node_id,
            total_tests=len(test_inputs),
            passed=0,
            failed=0,
        )

        for inputs in test_inputs:
            try:
                python_output, direct_output = await asyncio.gather(
                    self.python_runtime.execute(node_id, inputs),
                    self.direct_runtime.execute(node_id, inputs),
                )

                diff = self.comparator.compare(python_output, direct_output)

                if diff is None:
                    result.passed += 1
                else:
                    result.failed += 1
                    divergence = Divergence(
                        node_id=node_id,
                        inputs=inputs,
                        python_output=python_output,
                        direct_output=direct_output,
                        diff=diff,
                        timestamp=datetime.now(UTC).isoformat(),
                        trace_id=str(uuid.uuid4()),
                    )
                    result.divergences.append(divergence)
                    if on_divergence:
                        on_divergence(divergence)

            except Exception as e:
                result.failed += 1
                result.errors.append(
                    {
                        "inputs": inputs,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )
                logger.warning(f"Error during differential test for {node_id}: {e}")

        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return result

    async def test_with_random_inputs(
        self,
        node_id: str,
        input_generator: Callable[[], dict[str, Any]],
        num_tests: int = 1000,
        on_divergence: Callable[[Divergence], None] | None = None,
    ) -> DiffTestResult:
        """Run differential tests with randomly generated inputs."""
        test_inputs = [input_generator() for _ in range(num_tests)]
        return await self.test_node(node_id, test_inputs, on_divergence)
