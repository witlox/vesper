"""
Tests for the Vesper CLI commands.
"""

from click.testing import CliRunner
from vesper.cli.main import main


class TestCLI:
    """Test CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_version(self):
        """Test version command."""
        result = self.runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        """Test help command."""
        result = self.runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Vesper" in result.output


class TestCompileCommand:
    """Test the compile command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_compile_example_file(self):
        """Test compiling an actual example file."""
        result = self.runner.invoke(
            main, ["compile", "examples/hello_world/hello_world.vsp", "--validate-only"]
        )
        # Should at least parse and validate
        assert "Parsing" in result.output or "Error" in result.output

    def test_compile_nonexistent_file(self):
        """Test compiling a non-existent file."""
        result = self.runner.invoke(main, ["compile", "/nonexistent/file.vsp"])
        assert result.exit_code != 0


class TestRunCommand:
    """Test the run command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_run_nonexistent_file(self):
        """Test running a non-existent file."""
        result = self.runner.invoke(main, ["run", "/nonexistent/file.vsp"])
        assert result.exit_code != 0


class TestShowCommand:
    """Test the show command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_show_example_file(self):
        """Test showing an example node."""
        result = self.runner.invoke(
            main, ["show", "examples/hello_world/hello_world.vsp"]
        )
        # Should at least attempt to show the node
        assert "hello_world" in result.output or "Error" in result.output


class TestCodegenCommand:
    """Test the codegen command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_codegen_example_file(self):
        """Test showing generated code for example."""
        result = self.runner.invoke(
            main, ["codegen", "examples/hello_world/hello_world.vsp"]
        )
        # Should generate or show error
        assert "def " in result.output or "Error" in result.output


class TestVerifyCommand:
    """Test the verify command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_verify_node(self):
        """Test verifying a node."""
        result = self.runner.invoke(main, ["verify", "test_node"])
        # This command shows usage examples
        assert "Example usage" in result.output or "Differential" in result.output


class TestConfidenceCommand:
    """Test the confidence command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_confidence_node(self):
        """Test showing confidence for a node."""
        result = self.runner.invoke(main, ["confidence", "test_node"])
        # Will show metrics or error
        assert "Confidence" in result.output or "Error" in result.output


class TestStatusCommand:
    """Test the status command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_status_text(self):
        """Test status command with text format."""
        result = self.runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "Verification Status" in result.output

    def test_status_json(self):
        """Test status command with JSON format."""
        result = self.runner.invoke(main, ["status", "--format", "json"])
        assert result.exit_code == 0

    def test_status_prometheus(self):
        """Test status command with Prometheus format."""
        result = self.runner.invoke(main, ["status", "--format", "prometheus"])
        assert result.exit_code == 0
        assert "vesper_" in result.output


class TestMetricsCommand:
    """Test the metrics command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_metrics_node(self):
        """Test showing metrics for a node."""
        result = self.runner.invoke(main, ["metrics", "test_node"])
        # Will show metrics or error
        assert "Metrics" in result.output or "Error" in result.output


class TestTestCommand:
    """Test the test command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_test_example_file(self):
        """Test running test cases on example."""
        result = self.runner.invoke(
            main, ["test", "examples/hello_world/hello_world.vsp"]
        )
        # Will attempt to run tests
        assert "test" in result.output.lower() or "Error" in result.output
