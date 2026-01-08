"""
Tests for the Vesper Python Code Generator

These tests verify that:
1. The generator produces valid Python code
2. Generated code is idiomatic and readable
3. Contracts are properly implemented
4. All flow operations are handled correctly
"""

import pytest
from vesper.compiler import VesperCompiler
from vesper.generator import VesperGenerator


class TestVesperGenerator:
    """Tests for the VesperGenerator class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.compiler = VesperCompiler()
        self.generator = VesperGenerator()

    def test_generate_simple_function(self) -> None:
        """Test generating a simple function."""
        yaml_content = """
node_id: greet_user_v1
type: function
intent: Generate a greeting for a user

inputs:
  name:
    type: string
    required: true
    description: The user's name

outputs:
  success:
    message:
      type: string
      description: The greeting message

flow:
  - step: generate_greeting
    operation: string_template
    template: "Hello, {name}!"
    output: message
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        # Check basic structure
        assert "AUTO-GENERATED" in code
        assert "def greet_user_v1(" in code
        assert "name: str" in code
        assert "ExecutionResult" in code
        assert "SuccessResult" in code
        assert "ErrorResult" in code

        # Verify it's valid Python by compiling
        compile(code, "<generated>", "exec")

    def test_generate_with_contracts(self) -> None:
        """Test generating code with preconditions and postconditions."""
        yaml_content = """
node_id: add_numbers_v1
type: function
intent: Add two positive numbers

inputs:
  a:
    type: integer
    required: true
  b:
    type: integer
    required: true

outputs:
  success:
    result:
      type: integer

contracts:
  preconditions:
    - "a > 0"
    - "b > 0"
  postconditions:
    - "result == a + b"

flow:
  - step: compute
    operation: arithmetic
    expression: "a + b"
    output: result
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        # Check contracts are included
        assert "preconditions" in code.lower()
        assert "postconditions" in code.lower()
        assert "ContractViolation" in code
        assert "a > 0" in code
        assert "b > 0" in code

        compile(code, "<generated>", "exec")

    def test_generate_with_validation_step(self) -> None:
        """Test generating code with validation steps."""
        yaml_content = """
node_id: validate_input_v1
type: function
intent: Validate user input

inputs:
  email:
    type: string
    required: true

outputs:
  success:
    valid: boolean
  error:
    error_code: string
    message: string

flow:
  - step: check_email
    operation: validation
    guards:
      - "email != ''"
    on_failure:
      return_error:
        error_code: invalid_email
        message: "Email cannot be empty"

  - step: return_valid
    operation: return
    return_success:
      valid: true
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        assert "validation" in code.lower()
        assert "invalid_email" in code
        compile(code, "<generated>", "exec")

    def test_generate_with_conditional(self) -> None:
        """Test generating code with conditional steps."""
        yaml_content = """
node_id: classify_number_v1
type: function
intent: Classify a number as positive or negative

inputs:
  value:
    type: integer

outputs:
  success:
    classification:
      type: string

flow:
  - step: classify
    operation: conditional
    condition: "value > 0"
    then:
      - step: positive
        operation: string_template
        template: "positive"
        output: classification
    else:
      - step: negative
        operation: string_template
        template: "non-positive"
        output: classification
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        assert "if" in code
        compile(code, "<generated>", "exec")

    def test_generate_with_optional_inputs(self) -> None:
        """Test generating code with optional inputs."""
        yaml_content = """
node_id: optional_input_v1
type: function
intent: Test optional inputs

inputs:
  required_field:
    type: string
    required: true
  optional_field:
    type: string
    required: false
    default: "default_value"

outputs:
  success:
    result: string

flow:
  - step: combine
    operation: string_template
    template: "{required_field}"
    output: result
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        # Optional field should have default value
        assert "required_field: str" in code
        assert "optional_field" in code
        assert "default_value" in code

        compile(code, "<generated>", "exec")

    def test_generate_has_docstrings(self) -> None:
        """Test that generated code has proper docstrings."""
        yaml_content = """
node_id: documented_v1
type: function
intent: A well-documented function

metadata:
  description: |
    This is a detailed description of what this function does.
    It spans multiple lines.

inputs:
  param:
    type: string
    description: A parameter with description

outputs:
  success:
    result: string

flow:
  - step: noop
    operation: return
    return_success:
      result: "done"
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        # Check for docstrings
        assert '"""' in code
        assert "A well-documented function" in code
        assert "A parameter with description" in code

        compile(code, "<generated>", "exec")

    def test_generate_has_type_hints(self) -> None:
        """Test that generated code has comprehensive type hints."""
        yaml_content = """
node_id: typed_function_v1
type: function
intent: Function with all types

inputs:
  str_param:
    type: string
  int_param:
    type: integer
  dec_param:
    type: decimal
  bool_param:
    type: boolean

outputs:
  success:
    result: string

flow:
  - step: noop
    operation: return
    return_success:
      result: "ok"
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        assert "str_param: str" in code
        assert "int_param: int" in code
        assert "dec_param: Decimal" in code
        assert "bool_param: bool" in code
        assert "-> ExecutionResult:" in code

        compile(code, "<generated>", "exec")

    def test_generate_includes_logging(self) -> None:
        """Test that generated code includes logging."""
        yaml_content = """
node_id: logged_v1
type: function
intent: Function with logging

inputs:
  x:
    type: integer

outputs:
  success:
    result: integer

flow:
  - step: compute
    operation: arithmetic
    expression: "x * 2"
    output: result
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        assert "import logging" in code
        assert "logger" in code
        assert "logger.debug" in code or "logger.info" in code

        compile(code, "<generated>", "exec")

    def test_generate_verified_wrapper(self) -> None:
        """Test that a verified wrapper function is generated."""
        yaml_content = """
node_id: verified_v1
type: function
intent: Function with verified wrapper

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
        code = self.generator.generate(node)

        assert "def verified_v1(" in code
        assert "def verified_v1_verified(" in code

        compile(code, "<generated>", "exec")


class TestGeneratedCodeExecution:
    """Tests that verify generated code actually executes correctly."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.compiler = VesperCompiler()
        self.generator = VesperGenerator()

    def test_execute_simple_template(self) -> None:
        """Test executing generated code for a simple template."""
        yaml_content = """
node_id: hello_v1
type: function
intent: Say hello

inputs:
  name:
    type: string

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
        code = self.generator.generate(node)

        # Execute the code
        namespace = {}
        exec(code, namespace)

        # Get and call the function
        func = namespace["hello_v1"]
        result = func(name="World")

        assert result.is_success
        assert result.success.message == "Hello, World!"

    def test_execute_arithmetic(self) -> None:
        """Test executing generated code with arithmetic."""
        yaml_content = """
node_id: multiply_v1
type: function
intent: Multiply numbers

inputs:
  x:
    type: integer
  y:
    type: integer

outputs:
  success:
    result:
      type: integer

flow:
  - step: multiply
    operation: arithmetic
    expression: "x * y"
    output: result
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        namespace = {}
        exec(code, namespace)

        func = namespace["multiply_v1"]
        result = func(x=6, y=7)

        assert result.is_success
        assert result.success.result == 42

    def test_execute_with_precondition_violation(self) -> None:
        """Test that precondition violations raise exceptions."""
        yaml_content = """
node_id: positive_only_v1
type: function
intent: Accept only positive numbers

inputs:
  x:
    type: integer

outputs:
  success:
    result: integer

contracts:
  preconditions:
    - "x > 0"

flow:
  - step: passthrough
    operation: arithmetic
    expression: "x"
    output: result
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        namespace = {}
        exec(code, namespace)

        func = namespace["positive_only_v1"]

        # Positive value should work
        result = func(x=5)
        assert result.is_success

        # Negative value should raise ContractViolation
        contract_violation = namespace["ContractViolation"]
        with pytest.raises(contract_violation):
            func(x=-1)


class TestGeneratorEdgeCases:
    """Tests for edge cases and error handling in the generator."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.compiler = VesperCompiler()
        self.generator = VesperGenerator()

    def test_empty_flow(self) -> None:
        """Test generating code with no flow steps."""
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
        code = self.generator.generate(node)

        compile(code, "<generated>", "exec")

    def test_special_characters_in_template(self) -> None:
        """Test templates with special characters."""
        yaml_content = """
node_id: special_chars_v1
type: function
intent: Handle special characters

inputs:
  name:
    type: string

outputs:
  success:
    message:
      type: string

flow:
  - step: format
    operation: string_template
    template: "Hello, {name}! Welcome to 'Vesper'."
    output: message
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        namespace = {}
        exec(code, namespace)

        func = namespace["special_chars_v1"]
        result = func(name="User")
        assert result.is_success
        assert "Welcome to 'Vesper'" in result.success.message

    def test_unknown_operation_type(self) -> None:
        """Test handling of unknown operation types."""
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
    operation: custom.my_operation
    parameters:
      key: value
"""
        node = self.compiler.parse(yaml_content)
        code = self.generator.generate(node)

        # Should still compile
        assert "TODO" in code
        compile(code, "<generated>", "exec")
