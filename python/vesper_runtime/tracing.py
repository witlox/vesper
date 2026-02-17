"""
Execution Tracing for Vesper Runtime
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceContext:
    """Context for distributed tracing."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    baggage: dict[str, str] = field(default_factory=dict)

    @classmethod
    def new_trace(cls) -> TraceContext:
        return cls(trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()))

    def child_context(self) -> TraceContext:
        return TraceContext(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=self.span_id,
            baggage=dict(self.baggage),
        )


@dataclass
class ExecutionSpan:
    """A span representing a unit of work in the execution trace."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    start_time_ns: int
    end_time_ns: int | None = None
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @property
    def duration_ms(self) -> float:
        if self.end_time_ns is None:
            return 0.0
        return (self.end_time_ns - self.start_time_ns) / 1_000_000

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append(
            {
                "name": name,
                "timestamp_ns": time.time_ns(),
                "attributes": attributes or {},
            }
        )

    def set_error(self, error: Exception) -> None:
        self.status = "error"
        self.error = str(error)
        self.add_event(
            "exception", {"type": type(error).__name__, "message": str(error)}
        )

    def finish(self) -> None:
        self.end_time_ns = time.time_ns()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time_ns": self.start_time_ns,
            "end_time_ns": self.end_time_ns,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
            "error": self.error,
        }


class ExecutionTracer:
    """Tracer for execution spans."""

    def __init__(self, service_name: str = "vesper") -> None:
        self.service_name = service_name
        self._spans: list[ExecutionSpan] = []
        self._active_contexts: list[TraceContext] = []

    @contextmanager
    def start_span(
        self,
        name: str,
        context: TraceContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[ExecutionSpan, None, None]:
        if context is None:
            if self._active_contexts:
                context = self._active_contexts[-1].child_context()
            else:
                context = TraceContext.new_trace()

        span = ExecutionSpan(
            name=name,
            trace_id=context.trace_id,
            span_id=context.span_id,
            parent_span_id=context.parent_span_id,
            start_time_ns=time.time_ns(),
            attributes=attributes or {},
        )
        span.set_attribute("service.name", self.service_name)
        self._active_contexts.append(context)

        try:
            yield span
        except Exception as e:
            span.set_error(e)
            raise
        finally:
            span.finish()
            self._spans.append(span)
            self._active_contexts.pop()

    def get_current_context(self) -> TraceContext | None:
        if self._active_contexts:
            return self._active_contexts[-1]
        return None

    def get_spans(self) -> list[ExecutionSpan]:
        return list(self._spans)

    def get_trace(self, trace_id: str) -> list[ExecutionSpan]:
        return [s for s in self._spans if s.trace_id == trace_id]

    def clear(self) -> None:
        self._spans.clear()

    def export_spans(self, format: str = "json") -> Any:
        if format == "json":
            return [s.to_dict() for s in self._spans]
        elif format == "otlp":
            return {
                "resourceSpans": [
                    {
                        "resource": {
                            "attributes": [
                                {
                                    "key": "service.name",
                                    "value": {"stringValue": self.service_name},
                                }
                            ]
                        },
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": s.trace_id,
                                        "spanId": s.span_id,
                                        "parentSpanId": s.parent_span_id,
                                        "name": s.name,
                                        "startTimeUnixNano": s.start_time_ns,
                                        "endTimeUnixNano": s.end_time_ns,
                                        "status": {
                                            "code": 1 if s.status == "ok" else 2
                                        },
                                    }
                                    for s in self._spans
                                ]
                            }
                        ],
                    }
                ]
            }
        else:
            raise ValueError(f"Unknown format: {format}")
