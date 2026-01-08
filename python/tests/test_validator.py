"""
Tests for the Vesper Validator

These tests verify that:
1. Required fields are validated
2. Invalid formats are rejected
3. Contract syntax is checked
4. Security issues are flagged
5. Best practices are suggested
"""

from vesper.compiler import VesperCompiler
from vesper.validator import VesperValidator


class TestVesperValidator:
    """Tests for the VesperValidator class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.compiler = VesperCompiler()
        self.validator = VesperValidator()

    def test_validate_valid_node(self) -> None:
        """Test that a valid node passes validation."""
        yaml_content = """
node_id: valid_node_v1
type: function
intent: A valid function node

inputs:
  name:
    type: string
    required: true

outputs:
  success:
    message:
      type: string

flow:
  - step: greet
    operation: string_template
    template: "Hello, {name}!"
    output: message
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert result.valid
        assert len(result.errors) == 0

    def test_validate_invalid_node_id_format(self) -> None:
        """Test that invalid node_id format is rejected."""
        yaml_content = """
node_id: InvalidNodeIdWithoutVersion
type: function
intent: Invalid ID format

inputs: {}
flow: []
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert not result.valid
        assert any("node_id" in e.path for e in result.errors)
        assert any("format" in e.message.lower() for e in result.errors)

    def test_validate_missing_input_type(self) -> None:
        """Test that missing input types are flagged."""
        yaml_content = """
node_id: missing_type_v1
type: function
intent: Missing input type

inputs:
  name: {}

outputs:
  success:
    result: string

flow:
  - step: noop
    operation: return
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        # This should generate an error or warning about missing type
        has_type_issue = any("type" in issue.message.lower() for issue in result.issues)
        assert has_type_issue

    def test_validate_unknown_type(self) -> None:
        """Test that unknown types are warned about."""
        yaml_content = """
node_id: unknown_type_v1
type: function
intent: Unknown type

inputs:
  data:
    type: custom_unknown_type

outputs:
  success:
    result: string

flow:
  - step: noop
    operation: return
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any(
            "unknown" in w.message.lower() and "type" in w.message.lower()
            for w in result.warnings
        )

    def test_validate_duplicate_step_names(self) -> None:
        """Test that duplicate step names are rejected."""
        yaml_content = """
node_id: duplicate_steps_v1
type: function
intent: Duplicate step names

inputs:
  x:
    type: integer

outputs:
  success:
    result: integer

flow:
  - step: compute
    operation: arithmetic
    expression: "x + 1"
    output: result

  - step: compute
    operation: arithmetic
    expression: "result + 1"
    output: result
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any("duplicate" in e.message.lower() for e in result.errors)

    def test_validate_unknown_operation(self) -> None:
        """Test that unknown operations are warned about."""
        yaml_content = """
node_id: unknown_op_v1
type: function
intent: Unknown operation

inputs:
  x:
    type: string

outputs:
  success:
    result: string

flow:
  - step: unknown
    operation: teleport_to_mars
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any(
            "unknown" in w.message.lower() and "operation" in w.message.lower()
            for w in result.warnings
        )

    def test_validate_empty_flow_warning(self) -> None:
        """Test that empty flow generates a warning."""
        yaml_content = """
node_id: empty_flow_v1
type: function
intent: Empty flow

inputs:
  x:
    type: string

outputs:
  success:
    result: string

flow: []
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any(
            "flow" in w.path and "no flow" in w.message.lower() for w in result.warnings
        )

    def test_validate_missing_template(self) -> None:
        """Test that string_template without template is an error."""
        yaml_content = """
node_id: missing_template_v1
type: function
intent: Missing template

inputs:
  x:
    type: string

outputs:
  success:
    result: string

flow:
  - step: format
    operation: string_template
    output: result
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any(
            "template" in e.path.lower() and "requires" in e.message.lower()
            for e in result.errors
        )

    def test_validate_missing_expression(self) -> None:
        """Test that arithmetic without expression is an error."""
        yaml_content = """
node_id: missing_expr_v1
type: function
intent: Missing expression

inputs:
  x:
    type: integer

outputs:
  success:
    result: integer

flow:
  - step: compute
    operation: arithmetic
    output: result
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any(
            "expression" in e.path.lower() and "requires" in e.message.lower()
            for e in result.errors
        )

    def test_validate_conflicting_capabilities(self) -> None:
        """Test that conflicting security capabilities are rejected."""
        yaml_content = """
node_id: conflict_cap_v1
type: function
intent: Conflicting capabilities

inputs:
  x:
    type: string

outputs:
  success:
    result: string

security:
  capabilities_required:
    - filesystem.write
  denied_capabilities:
    - filesystem.write

flow:
  - step: noop
    operation: return
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any(
            "conflict" in e.message.lower()
            or "both required and denied" in e.message.lower()
            for e in result.errors
        )

    def test_validate_dangerous_capabilities_warning(self) -> None:
        """Test that dangerous capabilities generate warnings."""
        yaml_content = """
node_id: dangerous_cap_v1
type: function
intent: Dangerous capabilities

inputs:
  x:
    type: string

outputs:
  success:
    result: string

security:
  capabilities_required:
    - exec.shell_command

flow:
  - step: noop
    operation: return
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any(
            "dangerous" in w.message.lower() or "shell_command" in w.message.lower()
            for w in result.warnings
        )

    def test_validate_unbalanced_parentheses(self) -> None:
        """Test that unbalanced parentheses in conditions are caught."""
        yaml_content = """
node_id: unbalanced_v1
type: function
intent: Unbalanced parentheses

inputs:
  x:
    type: integer

outputs:
  success:
    result: integer

contracts:
  preconditions:
    - "(x > 0"

flow:
  - step: noop
    operation: return
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any(
            "parentheses" in w.message.lower() or "unbalanced" in w.message.lower()
            for w in result.warnings
        )


class TestValidatorBestPractices:
    """Tests for best practice suggestions."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.compiler = VesperCompiler()
        self.validator = VesperValidator()

    def test_suggest_description(self) -> None:
        """Test that missing description generates a suggestion."""
        yaml_content = """
node_id: no_description_v1
type: function
intent: No description

inputs:
  x:
    type: string

outputs:
  success:
    result: string

flow:
  - step: noop
    operation: return
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any("description" in i.path.lower() for i in result.infos)

    def test_suggest_tests(self) -> None:
        """Test that missing tests generate a suggestion."""
        yaml_content = """
node_id: no_tests_v1
type: function
intent: No tests defined

inputs:
  x:
    type: string

outputs:
  success:
    result: string

flow:
  - step: noop
    operation: return
"""
        node = self.compiler.parse(yaml_content)
        result = self.validator.validate(node)

        assert any(
            "test" in i.path.lower() or "test" in i.message.lower()
            for i in result.infos
        )


class TestValidatorStrictMode:
    """Tests for strict validation mode."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.compiler = VesperCompiler()
        self.validator = VesperValidator()

    def test_strict_mode_converts_warnings_to_errors(self) -> None:
        """Test that strict mode treats warnings as errors."""
        yaml_content = """
node_id: warning_node_v1
type: function
intent: Has warnings

inputs:
  x:
    type: unknown_type_xyz

outputs:
  success:
    result: string

flow:
  - step: noop
    operation: return
"""
        node = self.compiler.parse(yaml_content)

        # Normal mode - should be valid (only warnings)
        normal_result = self.validator.validate(node, strict=False)

        # Strict mode - warnings become errors
        strict_result = self.validator.validate(node, strict=True)

        assert len(strict_result.errors) >= len(normal_result.warnings)
