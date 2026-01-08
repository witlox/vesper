"""
Vesper Python Code Generator

Generates idiomatic, production-ready Python code from Vesper specifications
using Jinja2 templates.

This generator is designed to produce code that:
- Is more readable than hand-written code
- Has comprehensive type hints and docstrings
- Includes contract verification (pre/post conditions)
- Handles errors gracefully with clear messages
- Is easily debuggable with proper logging
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

from vesper.models import VesperNode, InputSpec, FlowStep


class FieldSpec(NamedTuple):
    """Specification for a generated field."""
    type_hint: str
    description: str | None
    default: str | None
    required: bool


class Condition(NamedTuple):
    """A translated condition."""
    original: str
    python: str


class FlowStepCode(NamedTuple):
    """Generated code for a flow step."""
    name: str
    operation: str
    description: str | None
    code_lines: list[str]
    guard: str | None


class VesperGenerator:
    """
    Generates Python code from Vesper specifications.

    This generator uses Jinja2 templates to produce clean, idiomatic Python
    code that implements the behavior specified in a Vesper node.

    Example:
        >>> generator = VesperGenerator()
        >>> node = VesperNode(...)
        >>> code = generator.generate(node)
        >>> print(code)
    """

    # Mapping from Vesper types to Python type hints
    TYPE_MAPPING = {
        "string": "str",
        "integer": "int",
        "decimal": "Decimal",
        "boolean": "bool",
        "bytes": "bytes",
        "timestamp": "datetime",
        "enum": "str",
        "any": "Any",
    }

    # Operations that involve async I/O
    ASYNC_OPERATIONS = {
        "external_api_call",
        "database_query",
        "database_write",
        "database_update",
        "http_request",
    }

    def __init__(self, template_dir: Path | None = None) -> None:
        """
        Initialize the generator.

        Args:
            template_dir: Optional custom template directory.
                          Defaults to the bundled templates.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

        # Add custom filters
        self.env.filters["python_type"] = self._to_python_type
        self.env.filters["indent"] = self._indent

    def generate(
        self,
        node: VesperNode,
        source_file: str | None = None
    ) -> str:
        """
        Generate Python code from a Vesper node.

        Args:
            node: The parsed Vesper node
            source_file: Optional source file path for documentation

        Returns:
            Generated Python code as a string
        """
        template = self.env.get_template("function.py.jinja2")

        # Prepare template context
        context = self._build_context(node, source_file)

        # Render the template
        code = template.render(**context)

        return code

    def generate_to_file(
        self,
        node: VesperNode,
        output_path: Path,
        source_file: str | None = None
    ) -> Path:
        """
        Generate Python code and write to a file.

        Args:
            node: The parsed Vesper node
            output_path: Path to write the generated code
            source_file: Optional source file path for documentation

        Returns:
            Path to the generated file
        """
        code = self.generate(node, source_file)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code)

        return output_path

    def _build_context(
        self,
        node: VesperNode,
        source_file: str | None = None
    ) -> dict[str, Any]:
        """Build the template context from a Vesper node."""

        # Extract input information
        input_names = list(node.inputs.keys())
        input_types = {}
        input_specs = {}
        input_signature = {}

        for name, spec in node.inputs.items():
            if isinstance(spec, dict):
                type_str = spec.get("type", "any")
                required = spec.get("required", True)
                default = spec.get("default")
                description = spec.get("description")
                constraints = spec.get("constraints", [])
            elif isinstance(spec, InputSpec):
                type_str = spec.type
                required = spec.required
                default = spec.default
                description = spec.description
                constraints = spec.constraints
            else:
                type_str = "any"
                required = True
                default = None
                description = None
                constraints = []

            py_type = self._to_python_type(type_str)
            input_types[name] = py_type
            input_specs[name] = {
                "type": type_str,
                "type_hint": py_type,
                "required": required,
                "default": default,
                "description": description,
                "constraints": constraints,
            }

            if required:
                input_signature[name] = py_type
            else:
                default_str = repr(default) if default is not None else "None"
                input_signature[name] = f"{py_type} = {default_str}"

        # Extract output information
        success_fields = self._extract_success_fields(node)
        error_fields = self._extract_error_fields(node)
        error_codes = self._extract_error_codes(node)

        # Process contracts
        preconditions = [
            Condition(original=cond, python=self._translate_condition(cond))
            for cond in node.contracts.preconditions
        ]
        postconditions = [
            Condition(original=cond, python=self._translate_condition(cond))
            for cond in node.contracts.postconditions
        ]

        # Process flow steps
        flow_steps = [
            self._process_flow_step(step, input_names)
            for step in node.flow
        ]

        # Check for async/special operations
        has_async = any(
            step.operation in self.ASYNC_OPERATIONS
            for step in node.flow
        )
        has_http = any(
            step.operation in {"external_api_call", "http_request"}
            for step in node.flow
        )
        has_db = any(
            step.operation in {"database_query", "database_write", "database_update"}
            for step in node.flow
        )

        return {
            "node": node,
            "source_file": source_file,
            "timestamp": datetime.now().isoformat(),
            "function_name": self._to_function_name(node.node_id),

            # Input information
            "input_names": input_names,
            "input_types": input_types,
            "input_specs": input_specs,
            "input_signature": input_signature,

            # Output information
            "success_fields": success_fields,
            "error_fields": error_fields,
            "error_codes": error_codes,

            # Contracts
            "preconditions": preconditions,
            "postconditions": postconditions,

            # Flow
            "flow_steps": flow_steps,

            # Flags
            "has_async_operations": has_async,
            "has_http_operations": has_http,
            "has_db_operations": has_db,
        }

    def _to_python_type(self, vesper_type: str) -> str:
        """Convert a Vesper type to a Python type hint."""
        if isinstance(vesper_type, dict):
            vesper_type = vesper_type.get("type", "any")

        # Handle array types
        if vesper_type.startswith("array<") and vesper_type.endswith(">"):
            inner = vesper_type[6:-1]
            inner_py = self._to_python_type(inner)
            return f"list[{inner_py}]"

        # Handle map types
        if vesper_type.startswith("map<") and vesper_type.endswith(">"):
            inner = vesper_type[4:-1]
            if "," in inner:
                key, value = inner.split(",", 1)
                key_py = self._to_python_type(key.strip())
                value_py = self._to_python_type(value.strip())
                return f"dict[{key_py}, {value_py}]"
            return f"dict[str, {self._to_python_type(inner)}]"

        return self.TYPE_MAPPING.get(vesper_type.lower(), "Any")

    def _to_function_name(self, node_id: str) -> str:
        """Convert a node_id to a valid Python function name."""
        # Replace non-alphanumeric characters with underscores
        name = re.sub(r"[^a-zA-Z0-9_]", "_", node_id)

        # Ensure it doesn't start with a digit
        if name and name[0].isdigit():
            name = f"node_{name}"

        return name.lower()

    def _translate_condition(self, condition: str) -> str:
        """Translate a Vesper condition to Python."""
        result = condition

        # Replace logical operators
        result = re.sub(r'\bAND\b', 'and', result, flags=re.IGNORECASE)
        result = re.sub(r'\bOR\b', 'or', result, flags=re.IGNORECASE)
        result = re.sub(r'\bNOT\b', 'not', result, flags=re.IGNORECASE)

        # Replace comparison operators
        result = re.sub(r'\bIN\b', 'in', result, flags=re.IGNORECASE)
        result = re.sub(r'\bIS NOT NULL\b', 'is not None', result, flags=re.IGNORECASE)
        result = re.sub(r'\bIS NULL\b', 'is None', result, flags=re.IGNORECASE)

        # Replace string literals
        result = result.replace("''", '""')

        return result

    def _replace_vars_with_context(self, expression: str) -> str:
        """Replace variable references with context lookups."""
        def replace_var(match: re.Match[str]) -> str:
            var = match.group(1)
            # Don't replace Python keywords, operators, or numeric literals
            keywords = {
                'and', 'or', 'not', 'True', 'False', 'None', 'in', 'is',
                'if', 'else', 'for', 'while', 'return', 'context',
            }
            if var in keywords:
                return var
            return f'context["{var}"]'

        return re.sub(r"\b([a-zA-Z_]\w*)\b", replace_var, expression)

    def _extract_success_fields(self, node: VesperNode) -> dict[str, FieldSpec]:
        """Extract success output fields from the node."""
        outputs = node.outputs

        if isinstance(outputs, dict):
            success = outputs.get("success", outputs)
        elif hasattr(outputs, "success"):
            success = outputs.success
        else:
            success = {}

        fields = {}
        for name, spec in success.items():
            if isinstance(spec, str):
                fields[name] = FieldSpec(
                    type_hint=self._to_python_type(spec),
                    description=None,
                    default=None,
                    required=True,
                )
            elif isinstance(spec, dict):
                fields[name] = FieldSpec(
                    type_hint=self._to_python_type(spec.get("type", "any")),
                    description=spec.get("description"),
                    default=spec.get("default"),
                    required=spec.get("required", True),
                )

        return fields

    def _extract_error_fields(self, node: VesperNode) -> dict[str, FieldSpec]:
        """Extract error output fields from the node."""
        outputs = node.outputs

        if isinstance(outputs, dict):
            error = outputs.get("error", {})
        elif hasattr(outputs, "error"):
            error = outputs.error
        else:
            error = {}

        fields = {}
        for name, spec in error.items():
            if isinstance(spec, str):
                fields[name] = FieldSpec(
                    type_hint=self._to_python_type(spec),
                    description=None,
                    default=None,
                    required=True,
                )
            elif isinstance(spec, dict):
                fields[name] = FieldSpec(
                    type_hint=self._to_python_type(spec.get("type", "any")),
                    description=spec.get("description"),
                    default=spec.get("default"),
                    required=spec.get("required", True),
                )

        return fields

    def _extract_error_codes(self, node: VesperNode) -> list[str]:
        """Extract possible error codes from the node."""
        codes = set()

        # From error handling config
        if node.error_handling:
            codes.update(node.error_handling.keys())

        # From flow steps
        for step in node.flow:
            if step.on_failure and "return_error" in step.on_failure:
                error_spec = step.on_failure["return_error"]
                if "error_code" in error_spec:
                    codes.add(error_spec["error_code"])

            if step.return_error:
                if "error_code" in step.return_error:
                    codes.add(step.return_error["error_code"])

        # From output spec
        outputs = node.outputs
        if isinstance(outputs, dict):
            error = outputs.get("error", {})
        elif hasattr(outputs, "error"):
            error = outputs.error
        else:
            error = {}

        if "error_code" in error:
            error_spec = error["error_code"]
            if isinstance(error_spec, dict) and "values" in error_spec:
                codes.update(error_spec["values"])

        return sorted(codes)

    def _process_flow_step(
        self,
        step: FlowStep,
        input_names: list[str]
    ) -> FlowStepCode:
        """Process a flow step into generated code."""
        code_lines: list[str] = []
        guard: str | None = None

        # Process guards
        if step.guards:
            guard_conditions = [
                self._translate_condition(g) for g in step.guards
            ]
            guard = " and ".join(f"({g})" for g in guard_conditions)

        # Generate code based on operation type
        if step.operation == "validation":
            code_lines = self._generate_validation_code(step)
        elif step.operation == "string_template":
            code_lines = self._generate_template_code(step)
        elif step.operation == "arithmetic":
            code_lines = self._generate_arithmetic_code(step)
        elif step.operation == "conditional":
            code_lines = self._generate_conditional_code(step, input_names)
        elif step.operation == "return":
            code_lines = self._generate_return_code(step)
        elif step.operation == "database_query":
            code_lines = self._generate_db_query_code(step)
        elif step.operation in {"database_write", "database_update"}:
            code_lines = self._generate_db_write_code(step)
        elif step.operation == "external_api_call":
            code_lines = self._generate_api_call_code(step)
        elif step.operation == "event_publish":
            code_lines = self._generate_event_publish_code(step)
        elif step.operation == "data_transform":
            code_lines = self._generate_transform_code(step)
        else:
            code_lines = [
                f'# TODO: Implement operation "{step.operation}"',
                "pass",
            ]

        return FlowStepCode(
            name=step.step.replace("-", "_").replace(" ", "_"),
            operation=step.operation,
            description=step.description,
            code_lines=code_lines,
            guard=guard,
        )

    def _generate_validation_code(self, step: FlowStep) -> list[str]:
        """Generate code for validation steps."""
        lines = []

        for guard in step.guards:
            py_guard = self._translate_condition(guard)
            # Replace variable references with context lookups
            py_guard = self._replace_vars_with_context(py_guard)
            lines.append(f"if not ({py_guard}):")

            if step.on_failure and "return_error" in step.on_failure:
                error = step.on_failure["return_error"]
                error_code = error.get("error_code", "validation_failed")
                message = error.get("message", f"Validation failed: {guard}")
                lines.append(f'    context["_error"] = ErrorResult(')
                lines.append(f'        error_code="{error_code}",')
                lines.append(f'        message="{message}"')
                lines.append("    )")
                lines.append("    return context")
            else:
                lines.append(f'    raise ValueError("Validation failed: {guard}")')

        return lines or ["pass"]

    def _generate_template_code(self, step: FlowStep) -> list[str]:
        """Generate code for string template steps."""
        template = step.template or ""
        output_var = step.output or "result"

        # Convert {var} to Python f-string format
        py_template = re.sub(r"\{(\w+)\}", r'{context["\1"]}', template)

        return [
            f'context["{output_var}"] = f"{py_template}"',
        ]

    def _generate_arithmetic_code(self, step: FlowStep) -> list[str]:
        """Generate code for arithmetic steps."""
        expression = step.expression or "0"
        output_var = step.output or "result"

        # Replace variable references with context lookups
        # Match word boundaries for variable names, excluding operators and numbers
        def replace_var(match: re.Match[str]) -> str:
            var = match.group(1)
            # Don't replace Python keywords or numeric literals
            if var in {'and', 'or', 'not', 'True', 'False', 'None', 'in', 'is'}:
                return var
            return f'context["{var}"]'

        py_expr = re.sub(r"\b([a-zA-Z_]\w*)\b", replace_var, expression)

        return [
            f'context["{output_var}"] = {py_expr}',
        ]

    def _generate_conditional_code(
        self,
        step: FlowStep,
        input_names: list[str]
    ) -> list[str]:
        """Generate code for conditional steps."""
        lines = []

        condition = step.condition or "True"
        py_condition = self._translate_condition(condition)
        # Replace variable references with context lookups
        py_condition = self._replace_vars_with_context(py_condition)

        lines.append(f"if {py_condition}:")

        if step.then:
            for sub_step in step.then:
                if isinstance(sub_step, dict):
                    sub = FlowStep(**sub_step)
                    sub_code = self._process_flow_step(sub, input_names)
                    for line in sub_code.code_lines:
                        lines.append(f"    {line}")
        else:
            lines.append("    pass")

        if step.else_:
            lines.append("else:")
            for sub_step in step.else_:
                if isinstance(sub_step, dict):
                    sub = FlowStep(**sub_step)
                    sub_code = self._process_flow_step(sub, input_names)
                    for line in sub_code.code_lines:
                        lines.append(f"    {line}")

        return lines

    def _generate_return_code(self, step: FlowStep) -> list[str]:
        """Generate code for return steps."""
        lines = []

        if step.return_success:
            lines.append("# Return success result")
            for key, value in step.return_success.items():
                if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                    var_name = value[1:-1]
                    lines.append(f'context["{key}"] = context.get("{var_name}")')
                else:
                    lines.append(f'context["{key}"] = {repr(value)}')
        elif step.return_error:
            error_code = step.return_error.get("error_code", "unknown")
            message = step.return_error.get("message", "An error occurred")
            lines.append('context["_error"] = ErrorResult(')
            lines.append(f'    error_code="{error_code}",')
            lines.append(f'    message="{message}"')
            lines.append(")")

        return lines or ["pass"]

    def _generate_db_query_code(self, step: FlowStep) -> list[str]:
        """Generate code for database query steps."""
        query = step.parameters.get("query", "SELECT 1")

        return [
            f'# Database query: {query}',
            '# TODO: Inject database client via dependency injection',
            'context["query_result"] = None  # Placeholder',
        ]

    def _generate_db_write_code(self, step: FlowStep) -> list[str]:
        """Generate code for database write steps."""
        table = step.parameters.get("table", "unknown")

        return [
            f'# Database write to table: {table}',
            '# TODO: Inject database client via dependency injection',
            'pass  # Placeholder',
        ]

    def _generate_api_call_code(self, step: FlowStep) -> list[str]:
        """Generate code for external API call steps."""
        provider = step.parameters.get("provider", "unknown")
        endpoint = step.parameters.get("endpoint", "/")
        method = step.parameters.get("method", "GET")

        return [
            f'# External API call to {provider}: {method} {endpoint}',
            '# TODO: Inject HTTP client via dependency injection',
            'context["api_response"] = None  # Placeholder',
        ]

    def _generate_event_publish_code(self, step: FlowStep) -> list[str]:
        """Generate code for event publish steps."""
        event_type = step.parameters.get("event_type", "unknown")

        return [
            f'# Publish event: {event_type}',
            '# TODO: Inject event bus via dependency injection',
            'pass  # Placeholder',
        ]

    def _generate_transform_code(self, step: FlowStep) -> list[str]:
        """Generate code for data transform steps."""
        return [
            "# Data transformation",
            '# TODO: Implement transformation logic',
            'pass  # Placeholder',
        ]

    @staticmethod
    def _indent(text: str, amount: int = 4) -> str:
        """Indent text by the specified amount."""
        prefix = " " * amount
        return "\n".join(prefix + line for line in text.split("\n"))

