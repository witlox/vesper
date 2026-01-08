"""
Vesper Runtime

Core execution infrastructure for dual-path runtime with verification support.
"""

from vesper_runtime.backends import Backend, InMemoryBackend
from vesper_runtime.contracts import (
    ContractChecker,
    ContractViolation,
    PostconditionViolation,
    PreconditionViolation,
)
from vesper_runtime.executor import (
    DualExecutionResult,
    ExecutionOrchestrator,
    ExecutionResult,
    PythonRuntime,
    DirectRuntime,
)
from vesper_runtime.tracing import ExecutionSpan, ExecutionTracer, TraceContext

__all__ = [
    # Executor
    "ExecutionOrchestrator",
    "ExecutionResult",
    "DualExecutionResult",
    "PythonRuntime",
    "DirectRuntime",
    # Tracing
    "ExecutionTracer",
    "ExecutionSpan",
    "TraceContext",
    # Backends
    "Backend",
    "InMemoryBackend",
    # Contracts
    "ContractChecker",
    "ContractViolation",
    "PreconditionViolation",
    "PostconditionViolation",
]

