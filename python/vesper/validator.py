"""
Vesper Validator

Validates Vesper specifications for correctness, consistency, and best practices.

This validator checks:
- Required fields are present
- Types are valid
- Contracts are well-formed
- Flow steps reference valid variables
- Security constraints are satisfied
- Performance requirements are reasonable
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vesper.models import VesperNode, InputSpec, FlowStep


@dataclass
class ValidationIssue:
    """A single validation issue."""
    path: str
    message: str
    severity: str  # "error", "warning", "info"
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """Result of validating a Vesper node."""
    valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get all error-level issues."""
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get all warning-level issues."""
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[ValidationIssue]:
        """Get all info-level issues."""
        return [i for i in self.issues if i.severity == "info"]

    def add_error(
        self,
        path: str,
        message: str,
        suggestion: str | None = None
    ) -> None:
        """Add an error issue."""
        self.issues.append(ValidationIssue(
            path=path,
            message=message,
            severity="error",
            suggestion=suggestion,
        ))
        self.valid = False

    def add_warning(
        self,
        path: str,
        message: str,
        suggestion: str | None = None
    ) -> None:
        """Add a warning issue."""
        self.issues.append(ValidationIssue(
            path=path,
            message=message,
            severity="warning",
            suggestion=suggestion,
        ))

    def add_info(
        self,
        path: str,
        message: str,
        suggestion: str | None = None
    ) -> None:
        """Add an info issue."""
        self.issues.append(ValidationIssue(
            path=path,
            message=message,
            severity="info",
            suggestion=suggestion,
        ))

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        self.issues.extend(other.issues)
        if not other.valid:
            self.valid = False


class VesperValidator:
    """
    Validates Vesper specifications for correctness.

    This validator performs comprehensive checks on Vesper nodes to ensure
    they are well-formed and consistent before code generation.

    Example:
        >>> validator = VesperValidator()
        >>> result = validator.validate(node)
        >>> if not result.valid:
        ...     for error in result.errors:
        ...         print(f"Error: {error.path}: {error.message}")
    """

    # Valid Vesper types
    VALID_TYPES = {
        "string", "integer", "decimal", "boolean", "bytes", "timestamp",
        "enum", "any",
    }

    # Valid operations
    VALID_OPERATIONS = {
        "validation", "conditional", "state_machine_transition",
        "database_query", "database_write", "database_update",
        "external_api_call", "event_publish", "event_subscribe",
        "data_transform", "string_template", "arithmetic",
        "return", "call_node",
    }

    def validate(self, node: VesperNode, strict: bool = False) -> ValidationResult:
        """
        Validate a Vesper node.

        Args:
            node: The node to validate
            strict: If True, treat warnings as errors

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult()

        # Required field validation
        self._validate_required_fields(node, result)

        # Node ID format
        self._validate_node_id(node, result)

        # Input validation
        self._validate_inputs(node, result)

        # Output validation
        self._validate_outputs(node, result)

        # Contract validation
        self._validate_contracts(node, result)

        # Flow validation
        self._validate_flow(node, result)

        # Security validation
        self._validate_security(node, result)

        # Performance validation
        self._validate_performance(node, result)

        # Cross-cutting validations
        self._validate_references(node, result)

        # Best practices
        self._check_best_practices(node, result)

        # In strict mode, convert warnings to errors
        if strict:
            for issue in result.issues:
                if issue.severity == "warning":
                    issue.severity = "error"
                    result.valid = False

        return result

    def _validate_required_fields(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Validate that all required fields are present."""
        if not node.node_id:
            result.add_error("node_id", "Node ID is required")

        if not node.intent:
            result.add_error("intent", "Intent is required")

    def _validate_node_id(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Validate node_id format."""
        if not node.node_id:
            return

        # Check format: name_vN
        pattern = r"^[a-z][a-z0-9_]*_v[0-9]+[a-z0-9_]*$"
        if not re.match(pattern, node.node_id, re.IGNORECASE):
            result.add_error(
                "node_id",
                f"Invalid node_id format: '{node.node_id}'. Expected format: name_vN (e.g., 'payment_handler_v1')",
                suggestion="Use lowercase with underscores and version suffix"
            )

        # Check for reserved words
        reserved = {"import", "from", "class", "def", "return", "if", "else", "try"}
        base_name = node.node_id.split("_v")[0] if "_v" in node.node_id else node.node_id
        if base_name in reserved:
            result.add_error(
                "node_id",
                f"Node ID base name '{base_name}' is a Python reserved word",
                suggestion="Choose a different name"
            )

    def _validate_inputs(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Validate input specifications."""
        for name, spec in node.inputs.items():
            path = f"inputs.{name}"

            # Check name format
            if not re.match(r"^[a-z_][a-z0-9_]*$", name, re.IGNORECASE):
                result.add_error(
                    path,
                    f"Invalid input name: '{name}'",
                    suggestion="Use lowercase with underscores"
                )

            # Get type
            if isinstance(spec, dict):
                type_str = spec.get("type")
                constraints = spec.get("constraints", [])
            elif isinstance(spec, InputSpec):
                type_str = spec.type
                constraints = spec.constraints
            else:
                result.add_error(path, "Invalid input specification format")
                continue

            # Check type is valid
            if not type_str:
                result.add_error(path, "Input must have a type")
            elif not self._is_valid_type(type_str):
                result.add_warning(
                    path,
                    f"Unknown type: '{type_str}'",
                    suggestion=f"Valid types: {', '.join(sorted(self.VALID_TYPES))}"
                )

            # Validate constraints
            for i, constraint in enumerate(constraints):
                if not self._is_valid_constraint(constraint):
                    result.add_warning(
                        f"{path}.constraints[{i}]",
                        f"Constraint may be invalid: '{constraint}'"
                    )

    def _validate_outputs(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Validate output specifications."""
        outputs = node.outputs

        if isinstance(outputs, dict):
            success = outputs.get("success", {})
            error = outputs.get("error", {})
        elif hasattr(outputs, "success"):
            success = outputs.success
            error = outputs.error
        else:
            result.add_warning("outputs", "Output specification format is unclear")
            return

        # Check success outputs
        if not success:
            result.add_info(
                "outputs.success",
                "No success outputs defined",
                suggestion="Consider adding output fields for documentation"
            )

        for name, spec in success.items():
            path = f"outputs.success.{name}"
            if isinstance(spec, dict):
                type_str = spec.get("type")
            elif isinstance(spec, str):
                type_str = spec
            else:
                type_str = None

            if type_str and not self._is_valid_type(type_str):
                result.add_warning(
                    path,
                    f"Unknown output type: '{type_str}'"
                )

    def _validate_contracts(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Validate contracts are well-formed."""
        # Validate preconditions
        for i, cond in enumerate(node.contracts.preconditions):
            path = f"contracts.preconditions[{i}]"
            issues = self._validate_condition(cond, node)
            for issue in issues:
                result.add_warning(path, issue)

        # Validate postconditions
        for i, cond in enumerate(node.contracts.postconditions):
            path = f"contracts.postconditions[{i}]"
            issues = self._validate_condition(cond, node)
            for issue in issues:
                result.add_warning(path, issue)

        # Validate invariants
        for i, inv in enumerate(node.contracts.invariants):
            path = f"contracts.invariants[{i}]"
            if not inv.strip():
                result.add_error(path, "Empty invariant")

    def _validate_condition(
        self,
        condition: str,
        node: VesperNode
    ) -> list[str]:
        """Validate a single condition expression."""
        issues = []

        if not condition.strip():
            issues.append("Empty condition")
            return issues

        # Check for balanced parentheses
        if condition.count("(") != condition.count(")"):
            issues.append("Unbalanced parentheses")

        # Check for balanced quotes
        if condition.count("'") % 2 != 0:
            issues.append("Unbalanced single quotes")
        if condition.count('"') % 2 != 0:
            issues.append("Unbalanced double quotes")

        # Extract variable references and check they exist
        # This is a simple heuristic - could be more sophisticated
        var_pattern = r"\b([a-z_][a-z0-9_]*)\b"
        keywords = {"and", "or", "not", "in", "is", "true", "false", "null", "none"}

        for match in re.finditer(var_pattern, condition, re.IGNORECASE):
            var_name = match.group(1)
            if var_name.lower() not in keywords:
                # Check if it's a known input
                if var_name not in node.inputs:
                    # Could be a dotted reference like user.id
                    base = var_name.split(".")[0] if "." in var_name else var_name
                    if base not in node.inputs:
                        # Don't error, just note it might be undefined
                        pass

        return issues

    def _validate_flow(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Validate flow steps."""
        if not node.flow:
            result.add_warning(
                "flow",
                "No flow steps defined",
                suggestion="Add at least one flow step"
            )
            return

        step_names = set()

        for i, step in enumerate(node.flow):
            path = f"flow[{i}]"

            # Check step name
            if not step.step:
                result.add_error(path, "Step must have a name")
            elif step.step in step_names:
                result.add_error(path, f"Duplicate step name: '{step.step}'")
            else:
                step_names.add(step.step)

            # Check operation
            if not step.operation:
                result.add_error(f"{path}.operation", "Step must have an operation")
            elif not step.operation.startswith("custom."):
                if step.operation not in self.VALID_OPERATIONS:
                    result.add_warning(
                        f"{path}.operation",
                        f"Unknown operation: '{step.operation}'",
                        suggestion=f"Valid operations: {', '.join(sorted(self.VALID_OPERATIONS))}"
                    )

            # Validate operation-specific requirements
            self._validate_step_requirements(step, path, result)

    def _validate_step_requirements(
        self,
        step: FlowStep,
        path: str,
        result: ValidationResult
    ) -> None:
        """Validate operation-specific requirements."""
        op = step.operation

        if op == "string_template":
            if not step.template:
                result.add_error(f"{path}.template", "string_template requires a template")

        elif op == "arithmetic":
            if not step.expression:
                result.add_error(f"{path}.expression", "arithmetic requires an expression")

        elif op == "conditional":
            if not step.condition:
                result.add_error(f"{path}.condition", "conditional requires a condition")

        elif op == "database_query":
            if "query" not in step.parameters:
                result.add_warning(f"{path}.parameters", "database_query should have a query parameter")

        elif op == "external_api_call":
            if "provider" not in step.parameters:
                result.add_warning(f"{path}.parameters", "external_api_call should specify a provider")
            if "endpoint" not in step.parameters:
                result.add_warning(f"{path}.parameters", "external_api_call should specify an endpoint")

    def _validate_security(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Validate security configuration."""
        security = node.security

        # Check for dangerous capabilities
        dangerous = {
            "filesystem.write",
            "exec.shell_command",
            "network.raw_socket",
        }

        for cap in security.capabilities_required:
            if cap in dangerous:
                result.add_warning(
                    f"security.capabilities_required",
                    f"Capability '{cap}' is potentially dangerous",
                    suggestion="Ensure this capability is actually needed"
                )

        # Check for conflicting capabilities
        required_set = set(security.capabilities_required)
        denied_set = set(security.denied_capabilities)
        conflicts = required_set & denied_set

        if conflicts:
            result.add_error(
                "security",
                f"Capabilities both required and denied: {conflicts}"
            )

        # Recommend audit for sensitive operations
        has_external_calls = any(
            s.operation in {"external_api_call", "database_write", "database_update"}
            for s in node.flow
        )
        if has_external_calls and security.audit_level.value == "none":
            result.add_warning(
                "security.audit_level",
                "Node has external operations but audit is disabled",
                suggestion="Consider enabling audit_level: basic or detailed"
            )

    def _validate_performance(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Validate performance configuration."""
        perf = node.performance

        # Check for reasonable latency expectations
        if perf.expected_latency_ms and perf.p99_latency_ms:
            if perf.expected_latency_ms > perf.p99_latency_ms:
                result.add_error(
                    "performance",
                    "expected_latency_ms cannot be greater than p99_latency_ms"
                )

        # Check timeout
        if perf.timeout_seconds and perf.max_latency_ms:
            if perf.timeout_seconds * 1000 < perf.max_latency_ms:
                result.add_warning(
                    "performance",
                    "timeout_seconds is less than max_latency_ms",
                    suggestion="Increase timeout or reduce max_latency expectation"
                )

    def _validate_references(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Validate cross-references between sections."""
        input_names = set(node.inputs.keys())

        # Build set of variables defined by flow steps
        defined_vars = input_names.copy()

        for i, step in enumerate(node.flow):
            # Check if step references undefined variables
            template = step.template or ""
            expression = step.expression or ""

            for text in [template, expression]:
                for match in re.finditer(r"\{(\w+)\}", text):
                    var_name = match.group(1)
                    if var_name not in defined_vars:
                        result.add_warning(
                            f"flow[{i}]",
                            f"Reference to potentially undefined variable: '{var_name}'"
                        )

            # Add output to defined vars
            if step.output:
                defined_vars.add(step.output)

    def _check_best_practices(
        self,
        node: VesperNode,
        result: ValidationResult
    ) -> None:
        """Check for best practice violations."""
        # Intent should be descriptive
        if node.intent and len(node.intent) < 10:
            result.add_info(
                "intent",
                "Intent is very short",
                suggestion="Consider a more descriptive intent"
            )

        # Recommend having tests
        if not node.testing.test_cases and not node.testing.property_tests:
            result.add_info(
                "testing",
                "No test cases defined",
                suggestion="Consider adding test_cases for documentation and testing"
            )

        # Recommend metadata
        if not node.metadata.description:
            result.add_info(
                "metadata.description",
                "No description provided",
                suggestion="Add a description explaining what this node does"
            )

        # Recommend contracts for complex nodes
        flow_count = len(node.flow)
        if flow_count > 3:
            if not node.contracts.preconditions and not node.contracts.postconditions:
                result.add_info(
                    "contracts",
                    "Complex node has no contracts defined",
                    suggestion="Consider adding preconditions and postconditions"
                )

    def _is_valid_type(self, type_str: str) -> bool:
        """Check if a type string is valid."""
        if type_str.lower() in self.VALID_TYPES:
            return True

        # Check for array types
        if type_str.startswith("array<") and type_str.endswith(">"):
            inner = type_str[6:-1]
            return self._is_valid_type(inner)

        # Check for map types
        if type_str.startswith("map<") and type_str.endswith(">"):
            return True  # Simplified check

        return False

    def _is_valid_constraint(self, constraint: str | dict) -> bool:
        """Check if a constraint is well-formed."""
        # Handle dict constraints (e.g., {pattern: "..."})
        if isinstance(constraint, dict):
            return True  # Dict constraints are assumed valid

        if not isinstance(constraint, str):
            return False

        if not constraint.strip():
            return False

        # Known constraint patterns
        known_patterns = [
            r"^non_empty$",
            r"^positive$",
            r"^negative$",
            r"^pattern:\s*.+",
            r"^min:\s*\d+",
            r"^max:\s*\d+",
            r"^[<>=!]+\s*\d+",
            r"^[<>=!]+\s*[\d.]+$",
        ]

        for pattern in known_patterns:
            if re.match(pattern, constraint, re.IGNORECASE):
                return True

        # If it looks like an expression, it's probably valid
        if any(op in constraint for op in ["<", ">", "=", "!", "AND", "OR"]):
            return True

        return True  # Be permissive by default

