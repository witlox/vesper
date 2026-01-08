"""
Vesper Compiler

Parses Vesper specification files and generates Python code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from vesper.models import (
    VesperNode,
    ValidationResult,
    FlowStep,
    InputSpec,
    NodeType,
)


class VesperCompiler:
    """
    Compiles Vesper specification files (.vsp) to Python code.

    The compiler performs the following steps:
    1. Parse the YAML specification
    2. Validate against the schema
    3. Generate Python code with contracts
    4. Emit to .py file
    """

    def __init__(self, schema_path: Path | None = None) -> None:
        """
        Initialize the compiler.

        Args:
            schema_path: Optional path to JSON schema for validation
        """
        self.schema_path = schema_path
        self._schema: dict[str, Any] | None = None

    @property
    def schema(self) -> dict[str, Any] | None:
        """Load and cache the JSON schema."""
        if self._schema is None and self.schema_path:
            with open(self.schema_path) as f:
                self._schema = json.load(f)
        return self._schema

    def parse(self, source: str | Path) -> VesperNode:
        """
        Parse a Vesper specification from a file or string.

        Args:
            source: Either a file path or YAML string

        Returns:
            Parsed VesperNode

        Raises:
            ValueError: If parsing fails
        """
        if isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
            path = Path(source)
            with open(path) as f:
                content = f.read()
        else:
            content = source

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML: {e}") from e

        # Normalize inputs to InputSpec objects
        if "inputs" in data:
            normalized_inputs = {}
            for name, spec in data["inputs"].items():
                if isinstance(spec, dict):
                    normalized_inputs[name] = spec
                else:
                    normalized_inputs[name] = {"type": str(spec)}
            data["inputs"] = normalized_inputs

        # Handle outputs format
        if "outputs" in data:
            outputs = data["outputs"]
            # If outputs is not in success/error format, wrap it
            if "success" not in outputs and "error" not in outputs:
                # Assume it's all success outputs
                data["outputs"] = {"success": outputs, "error": {}}

        return VesperNode(**data)

    def validate(self, node: VesperNode) -> ValidationResult:
        """
        Validate a parsed Vesper node.

        Args:
            node: The node to validate

        Returns:
            ValidationResult with any errors/warnings
        """
        result = ValidationResult(valid=True)

        # Validate node_id format
        if not re.match(r"^[a-z_]+_v[0-9]+", node.node_id):
            result.add_error(
                "node_id",
                f"Invalid node_id format: {node.node_id}. Expected: name_vN"
            )

        # Validate inputs have types
        for name, spec in node.inputs.items():
            if isinstance(spec, dict):
                if "type" not in spec:
                    result.add_error(f"inputs.{name}", "Missing 'type' field")
            elif isinstance(spec, InputSpec):
                if not spec.type:
                    result.add_error(f"inputs.{name}", "Missing 'type' field")

        # Validate flow has at least one step for non-empty nodes
        if not node.flow:
            result.add_warning("flow", "No flow steps defined")

        # Validate flow step operations
        valid_operations = {
            "validation", "conditional", "state_machine_transition",
            "database_query", "database_write", "database_update",
            "external_api_call", "event_publish", "event_subscribe",
            "data_transform", "string_template", "arithmetic",
            "return", "call_node"
        }
        for i, step in enumerate(node.flow):
            # Allow custom operations (prefixed with "custom.")
            if not step.operation.startswith("custom.") and step.operation not in valid_operations:
                result.add_warning(
                    f"flow[{i}].operation",
                    f"Unknown operation: {step.operation}"
                )

        # Validate contracts syntax (basic check)
        for i, condition in enumerate(node.contracts.preconditions):
            if not self._validate_condition_syntax(condition):
                result.add_warning(
                    f"contracts.preconditions[{i}]",
                    f"Potentially invalid condition syntax: {condition}"
                )

        return result

    def _validate_condition_syntax(self, condition: str) -> bool:
        """Basic validation of condition syntax."""
        # For now, just check it's not empty and has some structure
        if not condition.strip():
            return False
        # Could add more sophisticated validation here
        return True

    def compile(self, node: VesperNode) -> str:
        """
        Compile a Vesper node to Python code.

        Args:
            node: The validated node to compile

        Returns:
            Generated Python code as a string
        """
        lines: list[str] = []

        # Header
        lines.append('"""')
        lines.append(f"AUTO-GENERATED by Vesper Compiler - DO NOT EDIT")
        lines.append(f"")
        lines.append(f"Node: {node.node_id}")
        lines.append(f"Intent: {node.intent}")
        if node.metadata.description:
            lines.append(f"")
            lines.append(f"Description: {node.metadata.description}")
        lines.append('"""')
        lines.append("")
        lines.append("from __future__ import annotations")
        lines.append("")
        lines.append("from dataclasses import dataclass")
        lines.append("from typing import Any")
        lines.append("")
        lines.append("")

        # Generate result types
        lines.append("@dataclass")
        lines.append("class Success:")
        lines.append('    """Success result."""')
        success_outputs = node.outputs.success if isinstance(node.outputs, dict) else (
            node.outputs.success if hasattr(node.outputs, 'success') else {}
        )
        if success_outputs:
            for field_name, field_spec in success_outputs.items():
                field_type = self._get_python_type(field_spec)
                lines.append(f"    {field_name}: {field_type}")
        else:
            lines.append("    pass")
        lines.append("")
        lines.append("")

        lines.append("@dataclass")
        lines.append("class Error:")
        lines.append('    """Error result."""')
        error_outputs = node.outputs.error if isinstance(node.outputs, dict) else (
            node.outputs.error if hasattr(node.outputs, 'error') else {}
        )
        if error_outputs:
            lines.append("    error_code: str")
            lines.append("    message: str")
        else:
            lines.append("    error_code: str = ''")
            lines.append("    message: str = ''")
        lines.append("")
        lines.append("")

        lines.append("@dataclass")
        lines.append("class Result:")
        lines.append('    """Execution result wrapper."""')
        lines.append("    success: Success | None = None")
        lines.append("    error: Error | None = None")
        lines.append("")
        lines.append("    @property")
        lines.append("    def is_success(self) -> bool:")
        lines.append("        return self.success is not None")
        lines.append("")
        lines.append("")

        # Generate the main function
        func_name = self._to_function_name(node.node_id)
        params = self._generate_parameters(node)

        lines.append(f"def {func_name}({params}) -> Result:")
        lines.append(f'    """')
        lines.append(f"    {node.intent}")
        lines.append(f"    ")
        lines.append(f"    Node ID: {node.node_id}")
        lines.append(f'    """')

        # Generate precondition checks
        if node.contracts.preconditions:
            lines.append("    # Precondition checks")
            for condition in node.contracts.preconditions:
                py_condition = self._translate_condition(condition)
                lines.append(f"    if not ({py_condition}):")
                lines.append(f'        return Result(error=Error(error_code="precondition_failed", message="{condition}"))')
            lines.append("")

        # Generate flow implementation
        lines.append("    # Flow implementation")
        context_vars: set[str] = set()

        for step in node.flow:
            lines.extend(self._generate_step(step, context_vars, indent=1))

        # Default return if no explicit return in flow
        if not any(s.operation == "return" for s in node.flow):
            lines.append("")
            lines.append("    # Default return")
            lines.append("    return Result(success=Success())")

        lines.append("")

        # Generate postcondition verification wrapper
        lines.append(f"def {func_name}_verified({params}) -> Result:")
        lines.append(f'    """Wrapper with postcondition verification."""')

        # Store old values for postconditions
        lines.append("    # Execute main function")
        call_args = ", ".join(
            name for name in node.inputs.keys()
        )
        lines.append(f"    result = {func_name}({call_args})")
        lines.append("")

        # Check postconditions
        if node.contracts.postconditions:
            lines.append("    # Postcondition checks")
            for condition in node.contracts.postconditions:
                lines.append(f"    # TODO: Verify postcondition: {condition}")

        lines.append("")
        lines.append("    return result")
        lines.append("")

        return "\n".join(lines)

    def _get_python_type(self, spec: Any) -> str:
        """Convert Vesper type to Python type."""
        if isinstance(spec, str):
            type_str = spec
        elif isinstance(spec, dict):
            type_str = spec.get("type", "Any")
        else:
            return "Any"

        type_mapping = {
            "string": "str",
            "integer": "int",
            "decimal": "float",
            "boolean": "bool",
            "bytes": "bytes",
            "timestamp": "str",  # Could use datetime
            "enum": "str",
        }

        return type_mapping.get(type_str, "Any")

    def _to_function_name(self, node_id: str) -> str:
        """Convert node_id to a Python function name."""
        # Remove version suffix for cleaner name
        name = re.sub(r"_v\d+.*$", "", node_id)
        return name

    def _generate_parameters(self, node: VesperNode) -> str:
        """Generate function parameter list."""
        params: list[str] = []

        for name, spec in node.inputs.items():
            if isinstance(spec, dict):
                py_type = self._get_python_type(spec)
                required = spec.get("required", True)
                default = spec.get("default")
            elif isinstance(spec, InputSpec):
                py_type = self._get_python_type(spec.type)
                required = spec.required
                default = spec.default
            else:
                py_type = "Any"
                required = True
                default = None

            if required:
                params.append(f"{name}: {py_type}")
            else:
                default_str = repr(default) if default is not None else "None"
                params.append(f"{name}: {py_type} = {default_str}")

        return ", ".join(params)

    def _translate_condition(self, condition: str) -> str:
        """Translate Vesper condition to Python."""
        import re as regex
        # Basic translations
        result = condition
        result = regex.sub(r'\bAND\b', 'and', result)
        result = regex.sub(r'\bOR\b', 'or', result)
        result = regex.sub(r'\bNOT\b', 'not', result)
        result = regex.sub(r'\bIN\b', 'in', result)
        result = regex.sub(r'\bCONTAINS\b', 'in', result)
        result = result.replace("''", '""')
        return result

    def _generate_step(
        self,
        step: FlowStep,
        context_vars: set[str],
        indent: int = 1
    ) -> list[str]:
        """Generate Python code for a flow step."""
        lines: list[str] = []
        prefix = "    " * indent

        lines.append(f"{prefix}# Step: {step.step}")

        if step.operation == "validation":
            lines.extend(self._generate_validation_step(step, prefix))
        elif step.operation == "string_template":
            lines.extend(self._generate_template_step(step, prefix, context_vars))
        elif step.operation == "arithmetic":
            lines.extend(self._generate_arithmetic_step(step, prefix, context_vars))
        elif step.operation == "return":
            lines.extend(self._generate_return_step(step, prefix))
        elif step.operation == "conditional":
            lines.extend(self._generate_conditional_step(step, prefix, context_vars))
        elif step.operation == "database_query":
            lines.extend(self._generate_db_query_step(step, prefix, context_vars))
        elif step.operation == "external_api_call":
            lines.extend(self._generate_api_call_step(step, prefix, context_vars))
        else:
            lines.append(f"{prefix}# TODO: Implement operation '{step.operation}'")
            lines.append(f"{prefix}pass")

        lines.append("")
        return lines

    def _generate_validation_step(self, step: FlowStep, prefix: str) -> list[str]:
        """Generate validation step code."""
        lines: list[str] = []

        for guard in step.guards:
            py_guard = self._translate_condition(guard)
            lines.append(f"{prefix}if not ({py_guard}):")

            if step.on_failure and "return_error" in step.on_failure:
                error_spec = step.on_failure["return_error"]
                error_code = error_spec.get("error_code", "validation_failed")
                message = error_spec.get("message", "Validation failed")
                lines.append(f'{prefix}    return Result(error=Error(error_code="{error_code}", message="{message}"))')
            else:
                lines.append(f'{prefix}    return Result(error=Error(error_code="validation_failed", message="Guard failed: {guard}"))')

        return lines

    def _generate_template_step(
        self,
        step: FlowStep,
        prefix: str,
        context_vars: set[str]
    ) -> list[str]:
        """Generate string template step code."""
        lines: list[str] = []

        template = step.template or ""
        output_var = step.output or "result"

        # Convert {var} to Python f-string format
        py_template = template.replace("{", "{").replace("}", "}")

        lines.append(f'{prefix}{output_var} = f"{py_template}"')
        context_vars.add(output_var)

        return lines

    def _generate_arithmetic_step(
        self,
        step: FlowStep,
        prefix: str,
        context_vars: set[str]
    ) -> list[str]:
        """Generate arithmetic step code."""
        lines: list[str] = []

        expression = step.expression or "0"
        output_var = step.output or "result"

        lines.append(f"{prefix}{output_var} = {expression}")
        context_vars.add(output_var)

        return lines

    def _generate_return_step(self, step: FlowStep, prefix: str) -> list[str]:
        """Generate return step code."""
        lines: list[str] = []

        if step.return_success:
            # Build success return
            fields: list[str] = []
            for key, value in step.return_success.items():
                if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                    var_name = value[1:-1]
                    fields.append(f"{key}={var_name}")
                else:
                    fields.append(f"{key}={repr(value)}")

            fields_str = ", ".join(fields)
            lines.append(f"{prefix}return Result(success=Success({fields_str}))")
        elif step.return_error:
            error_code = step.return_error.get("error_code", "unknown")
            message = step.return_error.get("message", "An error occurred")
            lines.append(f'{prefix}return Result(error=Error(error_code="{error_code}", message="{message}"))')
        else:
            lines.append(f"{prefix}return Result(success=Success())")

        return lines

    def _generate_conditional_step(
        self,
        step: FlowStep,
        prefix: str,
        context_vars: set[str]
    ) -> list[str]:
        """Generate conditional step code."""
        lines: list[str] = []

        condition = step.condition or "True"
        py_condition = self._translate_condition(condition)

        lines.append(f"{prefix}if {py_condition}:")

        if step.then:
            for sub_step_data in step.then:
                sub_step = FlowStep(**sub_step_data) if isinstance(sub_step_data, dict) else sub_step_data
                lines.extend(self._generate_step(sub_step, context_vars, indent=2))
        else:
            lines.append(f"{prefix}    pass")

        if step.else_:
            lines.append(f"{prefix}else:")
            for sub_step_data in step.else_:
                sub_step = FlowStep(**sub_step_data) if isinstance(sub_step_data, dict) else sub_step_data
                lines.extend(self._generate_step(sub_step, context_vars, indent=2))

        return lines

    def _generate_db_query_step(
        self,
        step: FlowStep,
        prefix: str,
        context_vars: set[str]
    ) -> list[str]:
        """Generate database query step code (placeholder)."""
        lines: list[str] = []
        query = step.parameters.get("query", "SELECT 1")

        lines.append(f"{prefix}# Database query: {query}")
        lines.append(f"{prefix}query_result = None  # TODO: Execute actual query")
        context_vars.add("query_result")

        return lines

    def _generate_api_call_step(
        self,
        step: FlowStep,
        prefix: str,
        context_vars: set[str]
    ) -> list[str]:
        """Generate external API call step code (placeholder)."""
        lines: list[str] = []

        provider = step.parameters.get("provider", "unknown")
        endpoint = step.parameters.get("endpoint", "/")

        lines.append(f"{prefix}# API call to {provider}: {endpoint}")
        lines.append(f"{prefix}api_response = None  # TODO: Execute actual API call")
        context_vars.add("api_response")

        return lines

    def compile_to_file(
        self,
        source: str | Path,
        output_path: Path | None = None
    ) -> Path:
        """
        Compile a Vesper file to a Python file.

        Args:
            source: Path to .vsp file
            output_path: Optional output path (defaults to same location with .py extension)

        Returns:
            Path to generated Python file
        """
        source_path = Path(source)

        if output_path is None:
            output_path = source_path.with_suffix(".py")

        node = self.parse(source_path)
        validation = self.validate(node)

        if not validation.valid:
            error_msgs = [f"  - {e.path}: {e.message}" for e in validation.errors]
            raise ValueError(f"Validation failed:\n" + "\n".join(error_msgs))

        code = self.compile(node)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(code)

        return output_path

