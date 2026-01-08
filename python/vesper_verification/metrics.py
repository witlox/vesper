"""
Metrics Collection for Vesper Verification
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExecutionMetrics:
    """Metrics for a single execution."""

    node_id: str
    timestamp: float
    path: str
    duration_ms: float
    success: bool
    diverged: Optional[bool] = None
    error_type: Optional[str] = None


@dataclass
class AggregateMetrics:
    """Aggregated metrics for a node."""

    node_id: str
    total_executions: int = 0
    python_executions: int = 0
    direct_executions: int = 0
    divergences: int = 0
    errors: int = 0
    avg_python_duration_ms: float = 0.0
    avg_direct_duration_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    @property
    def error_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return (self.errors / self.total_executions) * 100

    @property
    def divergence_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return (self.divergences / self.total_executions) * 100


class MetricsCollector:
    """Collect and aggregate execution metrics."""

    MAX_EXECUTIONS_PER_NODE = 10000

    def __init__(self) -> None:
        self._executions: dict[str, list[ExecutionMetrics]] = defaultdict(list)
        self._aggregates: dict[str, AggregateMetrics] = {}

    def record_execution(
        self,
        node_id: str,
        path: str,
        duration_ms: float,
        success: bool,
        diverged: Optional[bool] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Record a single execution."""
        metrics = ExecutionMetrics(
            node_id=node_id,
            timestamp=time.time(),
            path=path,
            duration_ms=duration_ms,
            success=success,
            diverged=diverged,
            error_type=type(error).__name__ if error else None,
        )

        executions = self._executions[node_id]
        executions.append(metrics)

        if len(executions) > self.MAX_EXECUTIONS_PER_NODE:
            self._executions[node_id] = executions[-self.MAX_EXECUTIONS_PER_NODE:]

        self._update_aggregate(node_id, metrics)

    def _update_aggregate(self, node_id: str, metrics: ExecutionMetrics) -> None:
        """Update aggregate metrics with new execution."""
        if node_id not in self._aggregates:
            self._aggregates[node_id] = AggregateMetrics(node_id=node_id)

        agg = self._aggregates[node_id]
        agg.total_executions += 1

        if metrics.path == "python":
            agg.python_executions += 1
        else:
            agg.direct_executions += 1

        if metrics.diverged:
            agg.divergences += 1

        if not metrics.success:
            agg.errors += 1

    def get_aggregate_metrics(self, node_id: str) -> AggregateMetrics:
        """Get aggregated metrics for a node."""
        if node_id not in self._aggregates:
            return AggregateMetrics(node_id=node_id)

        agg = self._aggregates[node_id]
        executions = self._executions.get(node_id, [])

        if executions:
            python_durations = [e.duration_ms for e in executions if e.path == "python"]
            direct_durations = [e.duration_ms for e in executions if e.path == "direct"]
            all_durations = [e.duration_ms for e in executions]

            if python_durations:
                agg.avg_python_duration_ms = statistics.mean(python_durations)
            if direct_durations:
                agg.avg_direct_duration_ms = statistics.mean(direct_durations)
            if all_durations:
                sorted_durations = sorted(all_durations)
                n = len(sorted_durations)
                agg.p50_latency_ms = sorted_durations[int(n * 0.5)]
                agg.p95_latency_ms = sorted_durations[int(n * 0.95)]
                agg.p99_latency_ms = sorted_durations[min(int(n * 0.99), n - 1)]

        return agg

    def get_all_aggregates(self) -> dict[str, AggregateMetrics]:
        """Get aggregate metrics for all nodes."""
        return {node_id: self.get_aggregate_metrics(node_id) for node_id in self._aggregates}

    def get_recent_executions(self, node_id: str, limit: int = 100) -> list[ExecutionMetrics]:
        """Get recent executions for a node."""
        executions = self._executions.get(node_id, [])
        return list(reversed(executions[-limit:]))

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        lines: list[str] = []

        lines.append("# HELP vesper_executions_total Total number of executions")
        lines.append("# TYPE vesper_executions_total counter")

        for node_id, agg in self._aggregates.items():
            lines.append(f'vesper_executions_total{{node_id="{node_id}",path="python"}} {agg.python_executions}')
            lines.append(f'vesper_executions_total{{node_id="{node_id}",path="direct"}} {agg.direct_executions}')

        lines.append("")
        lines.append("# HELP vesper_errors_total Total number of errors")
        lines.append("# TYPE vesper_errors_total counter")

        for node_id, agg in self._aggregates.items():
            lines.append(f'vesper_errors_total{{node_id="{node_id}"}} {agg.errors}')

        lines.append("")
        lines.append("# HELP vesper_divergences_total Total number of divergences")
        lines.append("# TYPE vesper_divergences_total counter")

        for node_id, agg in self._aggregates.items():
            lines.append(f'vesper_divergences_total{{node_id="{node_id}"}} {agg.divergences}')

        return "\n".join(lines)

    def export_json(self) -> dict[str, Any]:
        """Export metrics as JSON-serializable dict."""
        return {
            "nodes": {
                node_id: {
                    "total_executions": agg.total_executions,
                    "python_executions": agg.python_executions,
                    "direct_executions": agg.direct_executions,
                    "divergences": agg.divergences,
                    "errors": agg.errors,
                    "error_rate": agg.error_rate,
                    "divergence_rate": agg.divergence_rate,
                    "avg_python_duration_ms": agg.avg_python_duration_ms,
                    "avg_direct_duration_ms": agg.avg_direct_duration_ms,
                    "p50_latency_ms": agg.p50_latency_ms,
                    "p95_latency_ms": agg.p95_latency_ms,
                    "p99_latency_ms": agg.p99_latency_ms,
                }
                for node_id, agg in ((nid, self.get_aggregate_metrics(nid)) for nid in self._aggregates)
            },
            "timestamp": time.time(),
        }

    def reset(self, node_id: Optional[str] = None) -> None:
        """Reset metrics."""
        if node_id:
            self._executions.pop(node_id, None)
            self._aggregates.pop(node_id, None)
        else:
            self._executions.clear()
            self._aggregates.clear()

