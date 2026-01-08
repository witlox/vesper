"""
Tests for the Vesper Compiler
"""

from vesper.compiler import VesperCompiler
from vesper.models import NodeType


class TestVesperCompiler:
    """Tests for the VesperCompiler class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.compiler = VesperCompiler()

    def test_parse_simple_node(self) -> None:
        """Test parsing a simple Vesper node."""
        yaml_content = """
node_id: test_node_v1
type: function
intent: test_function

inputs:
  name:
    type: string

outputs:
  success:
    message: string

flow:
  - step: greet
    operation: string_template
    template: "Hello, {name}!"
    output: message
"""
        node = self.compiler.parse(yaml_content)

        assert node.node_id == "test_node_v1"
        assert node.type == NodeType.FUNCTION
        assert node.intent == "test_function"
        assert "name" in node.inputs

    def test_parse_with_contracts(self) -> None:
        """Test parsing a node with contracts."""
        yaml_content = """
node_id: contract_node_v1
type: function
intent: test_contracts

inputs:
  amount:
    type: integer

outputs:
  success:
    doubled: integer

contracts:
  preconditions:
    - "amount > 0"
  postconditions:
    - "doubled == amount * 2"

flow:
  - step: double
    operation: arithmetic
    expression: "amount * 2"
    output: doubled
"""
        node = self.compiler.parse(yaml_content)

        assert len(node.contracts.preconditions) == 1
        assert "amount > 0" in node.contracts.preconditions
        assert len(node.contracts.postconditions) == 1

    def test_validate_valid_node(self) -> None:
        """Test validation of a valid node."""
        yaml_content = """
node_id: valid_node_v1
type: function
intent: valid_function

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
"""
        node = self.compiler.parse(yaml_content)
        result = self.compiler.validate(node)

        assert result.valid
        assert len(result.errors) == 0

    def test_validate_invalid_node_id(self) -> None:
        """Test validation rejects invalid node_id format."""
        yaml_content = """
node_id: InvalidNodeId
type: function
intent: invalid

inputs:
  x:
    type: integer

outputs:
  success:
    result: integer

flow:
  - step: noop
    operation: return
"""
        node = self.compiler.parse(yaml_content)
        result = self.compiler.validate(node)

        assert not result.valid
        assert any("node_id" in e.path for e in result.errors)

    def test_compile_generates_python(self) -> None:
        """Test that compile generates valid Python code."""
        yaml_content = """
node_id: compile_test_v1
type: function
intent: compile_test

inputs:
  a:
    type: integer
  b:
    type: integer

outputs:
  success:
    result: integer

contracts:
  preconditions:
    - "a > 0"
    - "b > 0"

flow:
  - step: add
    operation: arithmetic
    expression: "a + b"
    output: result

  - step: return_result
    operation: return
    return_success:
      result: "{result}"
"""
        node = self.compiler.parse(yaml_content)
        code = self.compiler.compile(node)

        # Check code contains expected elements
        assert "AUTO-GENERATED" in code
        assert "def compile_test(" in code
        assert "a: int" in code
        assert "b: int" in code
        assert "result = a + b" in code

        # Verify it's valid Python by executing it
        exec(code)

    def test_compile_with_validation_step(self) -> None:
        """Test compilation of validation steps."""
        yaml_content = """
node_id: validation_test_v1
type: function
intent: validation_test

inputs:
  name:
    type: string

outputs:
  success:
    greeting: string
  error:
    error_code: enum
    message: string

flow:
  - step: validate_name
    operation: validation
    guards:
      - "name != ''"
    on_failure:
      return_error:
        error_code: invalid_name
        message: "Name cannot be empty"

  - step: greet
    operation: string_template
    template: "Hello, {name}!"
    output: greeting
"""
        node = self.compiler.parse(yaml_content)
        code = self.compiler.compile(node)

        assert 'if not (name != "")' in code
        assert "invalid_name" in code

    def test_translate_condition(self) -> None:
        """Test condition translation."""
        assert self.compiler._translate_condition("a AND b") == "a and b"
        assert self.compiler._translate_condition("NOT x") == "not x"
        assert self.compiler._translate_condition("x IN list") == "x in list"


class TestCodeGeneration:
    """Tests for code generation quality."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.compiler = VesperCompiler()

    def test_generated_code_has_docstring(self) -> None:
        """Test that generated code has proper docstrings."""
        yaml_content = """
node_id: docstring_test_v1
type: function
intent: generate_greeting

inputs:
  name:
    type: string

outputs:
  success:
    message: string

flow:
  - step: greet
    operation: string_template
    template: "Hello!"
    output: message
"""
        node = self.compiler.parse(yaml_content)
        code = self.compiler.compile(node)

        assert '"""' in code
        assert "generate_greeting" in code

    def test_generated_code_has_type_hints(self) -> None:
        """Test that generated code has type hints."""
        yaml_content = """
node_id: typehints_test_v1
type: function
intent: typed_function

inputs:
  count:
    type: integer
  ratio:
    type: decimal
  active:
    type: boolean

outputs:
  success:
    result: integer

flow:
  - step: compute
    operation: arithmetic
    expression: "count"
    output: result
"""
        node = self.compiler.parse(yaml_content)
        code = self.compiler.compile(node)

        assert "count: int" in code
        assert "ratio: float" in code
        assert "active: bool" in code
        assert "-> Result" in code
