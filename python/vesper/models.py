"""
Vesper Models

Pydantic models for Vesper specification parsing and validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeType(str, Enum):
    """Types of semantic nodes."""
    FUNCTION = "function"
    HTTP_HANDLER = "http_handler"
    EVENT_HANDLER = "event_handler"
    DATA_TRANSFORM = "data_transform"
    STATE_MACHINE = "state_machine"
    AGGREGATION = "aggregation"
    SCHEDULED_JOB = "scheduled_job"


class AuditLevel(str, Enum):
    """Audit logging levels."""
    NONE = "none"
    BASIC = "basic"
    DETAILED = "detailed"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(str, Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ChangelogEntry(BaseModel):
    """A single changelog entry."""
    version: str
    date: str
    changes: str


class Metadata(BaseModel):
    """Node metadata."""
    author: str | None = None
    created: datetime | None = None
    version: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    changelog: list[ChangelogEntry] = Field(default_factory=list)


class InputSpec(BaseModel):
    """Specification for a single input parameter."""
    type: str
    required: bool = True
    constraints: list[str] = Field(default_factory=list)
    default: Any = None
    description: str | None = None


class OutputField(BaseModel):
    """Specification for an output field."""
    type: str
    description: str | None = None
    values: list[str] | None = None  # For enum types
    required: bool = True


class Outputs(BaseModel):
    """Output specification with success and error cases."""
    success: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)


class CustomType(BaseModel):
    """Custom type definition."""
    base: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)


class Contracts(BaseModel):
    """Formal contracts for verification."""
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)


class RetryPolicy(BaseModel):
    """Retry policy for operations."""
    max_attempts: int = 3
    backoff: str = "exponential"
    backoff_base: int = 2
    initial_delay: str = "1s"


class FlowStep(BaseModel):
    """A single step in the execution flow."""
    model_config = ConfigDict(populate_by_name=True)

    step: str
    operation: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    guards: list[str] = Field(default_factory=list)
    condition: str | None = None
    then: list[dict[str, Any]] | None = None
    else_: list[dict[str, Any]] | None = Field(default=None, alias="else")
    on_success: dict[str, Any] | None = None
    on_error: dict[str, Any] | list[dict[str, Any]] | None = None
    on_failure: dict[str, Any] | None = None
    on_result: dict[str, Any] | None = None
    template: str | None = None
    expression: str | None = None
    output: str | None = None
    timeout: str | None = None
    retry_policy: RetryPolicy | None = None
    return_success: dict[str, Any] | None = None
    return_error: dict[str, Any] | None = None



class ErrorHandler(BaseModel):
    """Error handling configuration."""
    action: str
    max_retries: int | None = None
    notify: str | list[str] | None = None
    log_level: LogLevel = LogLevel.ERROR
    threshold: int | None = None
    timeout: str | None = None


class RateLimit(BaseModel):
    """Rate limiting configuration."""
    model_config = ConfigDict(populate_by_name=True)

    per_user: str | None = None
    global_: str | None = Field(default=None, alias="global")



class Performance(BaseModel):
    """Performance requirements."""
    expected_latency_ms: int | None = None
    p99_latency_ms: int | None = None
    max_latency_ms: int | None = None
    memory_limit_mb: int | None = None
    cpu_limit_cores: float | None = None
    timeout_seconds: int | None = None
    rate_limit: RateLimit | None = None


class Security(BaseModel):
    """Security configuration."""
    capabilities_required: list[str] = Field(default_factory=list)
    denied_capabilities: list[str] = Field(default_factory=list)
    sensitive_data: list[str] = Field(default_factory=list)
    audit_level: AuditLevel = AuditLevel.BASIC
    compliance: list[str] = Field(default_factory=list)


class Metric(BaseModel):
    """Metric definition."""
    name: str
    type: MetricType
    labels: list[str] = Field(default_factory=list)
    buckets: list[float] | None = None


class Alert(BaseModel):
    """Alert definition."""
    condition: str
    severity: AlertSeverity
    notify: list[str] = Field(default_factory=list)


class Tracing(BaseModel):
    """Tracing configuration."""
    enabled: bool = False
    sample_rate: float = 0.1


class Logging(BaseModel):
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    structured: bool = True
    include_request_id: bool = True


class Observability(BaseModel):
    """Observability configuration."""
    metrics: list[Metric] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    tracing: Tracing = Field(default_factory=Tracing)
    logging: Logging = Field(default_factory=Logging)


class PropertyTest(BaseModel):
    """Property-based test definition."""
    property: str
    description: str | None = None
    strategy: str = "hypothesis"
    invariant: str | None = None
    verify: str | None = None


class TestCase(BaseModel):
    """Test case definition."""
    name: str
    description: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_output: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] | None = None


class DifferentialTests(BaseModel):
    """Differential testing configuration."""
    enabled: bool = True
    sample_size: int = 10000


class Testing(BaseModel):
    """Testing configuration."""
    property_tests: list[PropertyTest] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    differential_tests: DifferentialTests = Field(default_factory=DifferentialTests)


class Example(BaseModel):
    """Documentation example."""
    title: str
    code: str


class Documentation(BaseModel):
    """Documentation configuration."""
    examples: list[Example] = Field(default_factory=list)
    related_nodes: list[str] = Field(default_factory=list)
    migration_notes: str | None = None


class VesperNode(BaseModel):
    """Complete Vesper semantic node."""
    node_id: str
    type: NodeType
    intent: str

    # Optional fields
    metadata: Metadata = Field(default_factory=Metadata)
    inputs: dict[str, InputSpec | dict[str, Any]] = Field(default_factory=dict)
    outputs: Outputs | dict[str, Any] = Field(default_factory=Outputs)
    types: dict[str, CustomType] = Field(default_factory=dict)
    contracts: Contracts = Field(default_factory=Contracts)
    flow: list[FlowStep] = Field(default_factory=list)
    error_handling: dict[str, ErrorHandler] = Field(default_factory=dict)
    performance: Performance = Field(default_factory=Performance)
    security: Security = Field(default_factory=Security)
    observability: Observability = Field(default_factory=Observability)
    testing: Testing = Field(default_factory=Testing)
    documentation: Documentation = Field(default_factory=Documentation)

    def get_input_spec(self, name: str) -> InputSpec:
        """Get the input specification for a parameter."""
        spec = self.inputs.get(name)
        if spec is None:
            raise KeyError(f"Input '{name}' not found")
        if isinstance(spec, dict):
            return InputSpec(**spec)
        return spec


class ValidationError(BaseModel):
    """A single validation error."""
    path: str
    message: str
    severity: str = "error"


class ValidationResult(BaseModel):
    """Result of validating a Vesper node."""
    valid: bool
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)

    def add_error(self, path: str, message: str) -> None:
        """Add an error to the validation result."""
        self.errors.append(ValidationError(path=path, message=message))
        self.valid = False

    def add_warning(self, path: str, message: str) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(ValidationError(path=path, message=message, severity="warning"))

