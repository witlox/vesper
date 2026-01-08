"""
Tests for Vesper Models
"""

import pytest
from datetime import datetime

from vesper.models import (
    VesperNode,
    NodeType,
    InputSpec,
    Outputs,
    Contracts,
    FlowStep,
    ValidationResult,
    ValidationError,
    Metadata,
)


class TestVesperNode:
    """Tests for the VesperNode model."""

    def test_create_minimal_node(self) -> None:
        """Test creating a minimal Vesper node."""
        node = VesperNode(
            node_id="test_v1",
            type=NodeType.FUNCTION,
            intent="test intent"
        )

        assert node.node_id == "test_v1"
        assert node.type == NodeType.FUNCTION
        assert node.intent == "test intent"

    def test_create_node_with_inputs(self) -> None:
        """Test creating a node with inputs."""
        node = VesperNode(
            node_id="input_test_v1",
            type=NodeType.FUNCTION,
            intent="test with inputs",
            inputs={
                "name": InputSpec(type="string", required=True),
                "age": InputSpec(type="integer", required=False, default=0),
            }
        )

        assert "name" in node.inputs
        assert "age" in node.inputs

    def test_get_input_spec(self) -> None:
        """Test getting input specification."""
        node = VesperNode(
            node_id="spec_test_v1",
            type=NodeType.FUNCTION,
            intent="test get_input_spec",
            inputs={
                "value": InputSpec(type="integer", required=True, description="A value"),
            }
        )

        spec = node.get_input_spec("value")
        assert spec.type == "integer"
        assert spec.required is True
        assert spec.description == "A value"

    def test_get_input_spec_missing(self) -> None:
        """Test getting non-existent input spec raises error."""
        node = VesperNode(
            node_id="missing_test_v1",
            type=NodeType.FUNCTION,
            intent="test missing input"
        )

        with pytest.raises(KeyError):
            node.get_input_spec("nonexistent")


class TestInputSpec:
    """Tests for the InputSpec model."""

    def test_create_required_input(self) -> None:
        """Test creating a required input."""
        spec = InputSpec(type="string", required=True)

        assert spec.type == "string"
        assert spec.required is True
        assert spec.default is None

    def test_create_optional_input_with_default(self) -> None:
        """Test creating an optional input with default."""
        spec = InputSpec(type="integer", required=False, default=42)

        assert spec.required is False
        assert spec.default == 42

    def test_input_with_constraints(self) -> None:
        """Test input with constraints."""
        spec = InputSpec(
            type="string",
            constraints=["non_empty", "max_length:100"]
        )

        assert len(spec.constraints) == 2
        assert "non_empty" in spec.constraints


class TestContracts:
    """Tests for the Contracts model."""

    def test_empty_contracts(self) -> None:
        """Test creating empty contracts."""
        contracts = Contracts()

        assert contracts.preconditions == []
        assert contracts.postconditions == []
        assert contracts.invariants == []

    def test_contracts_with_conditions(self) -> None:
        """Test contracts with conditions."""
        contracts = Contracts(
            preconditions=["amount > 0", "user.authenticated"],
            postconditions=["transaction.recorded"],
            invariants=["balance >= 0"]
        )

        assert len(contracts.preconditions) == 2
        assert len(contracts.postconditions) == 1
        assert len(contracts.invariants) == 1


class TestFlowStep:
    """Tests for the FlowStep model."""

    def test_minimal_step(self) -> None:
        """Test creating a minimal flow step."""
        step = FlowStep(step="test_step", operation="validation")

        assert step.step == "test_step"
        assert step.operation == "validation"

    def test_step_with_guards(self) -> None:
        """Test step with guards."""
        step = FlowStep(
            step="guarded_step",
            operation="validation",
            guards=["user.active", "amount > 0"]
        )

        assert len(step.guards) == 2

    def test_step_with_template(self) -> None:
        """Test step with string template."""
        step = FlowStep(
            step="template_step",
            operation="string_template",
            template="Hello, {name}!",
            output="greeting"
        )

        assert step.template == "Hello, {name}!"
        assert step.output == "greeting"


class TestValidationResult:
    """Tests for the ValidationResult model."""

    def test_valid_result(self) -> None:
        """Test creating a valid result."""
        result = ValidationResult(valid=True)

        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_add_error(self) -> None:
        """Test adding an error."""
        result = ValidationResult(valid=True)
        result.add_error("inputs.name", "Missing type")

        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].path == "inputs.name"
        assert result.errors[0].message == "Missing type"

    def test_add_warning(self) -> None:
        """Test adding a warning."""
        result = ValidationResult(valid=True)
        result.add_warning("flow[0]", "Unknown operation")

        # Warnings don't invalidate
        assert result.valid is True
        assert len(result.warnings) == 1


class TestMetadata:
    """Tests for the Metadata model."""

    def test_empty_metadata(self) -> None:
        """Test creating empty metadata."""
        metadata = Metadata()

        assert metadata.author is None
        assert metadata.tags == []

    def test_metadata_with_values(self) -> None:
        """Test metadata with values."""
        metadata = Metadata(
            author="test@example.com",
            version="1.0.0",
            tags=["example", "test"],
            description="A test node"
        )

        assert metadata.author == "test@example.com"
        assert metadata.version == "1.0.0"
        assert "example" in metadata.tags

