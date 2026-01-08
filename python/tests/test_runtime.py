"""
Tests for the Vesper Runtime
"""

import pytest
from vesper.runtime import (
    ExecutionMode,
    MigrationController,
    RuntimeMetrics,
    VesperRuntime,
)


class TestVesperRuntime:
    """Tests for the VesperRuntime class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runtime = VesperRuntime()

    def test_load_simple_node(self) -> None:
        """Test loading a simple Vesper node."""
        yaml_content = """
node_id: runtime_test_v1
type: function
intent: runtime_test

inputs:
  x:
    type: integer

outputs:
  success:
    result: integer

flow:
  - step: double
    operation: arithmetic
    expression: "x * 2"
    output: result

  - step: return_result
    operation: return
    return_success:
      result: "{result}"
"""
        node = self.runtime.load_node(yaml_content)

        assert node.node_id == "runtime_test_v1"
        assert self.runtime.get_node("runtime_test_v1") is not None

    @pytest.mark.asyncio
    async def test_execute_simple_node(self) -> None:
        """Test executing a simple node."""
        yaml_content = """
node_id: execute_test_v1
type: function
intent: add_numbers

inputs:
  a:
    type: integer
  b:
    type: integer

outputs:
  success:
    result: integer

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
        self.runtime.load_node(yaml_content)
        result = await self.runtime.execute("execute_test_v1", {"a": 5, "b": 3})

        assert result.success
        assert result.data is not None

    def test_execute_sync(self) -> None:
        """Test synchronous execution."""
        yaml_content = """
node_id: sync_test_v1
type: function
intent: sync_test

inputs:
  value:
    type: integer

outputs:
  success:
    doubled: integer

flow:
  - step: double
    operation: arithmetic
    expression: "value * 2"
    output: doubled

  - step: return_result
    operation: return
    return_success:
      doubled: "{doubled}"
"""
        self.runtime.load_node(yaml_content)
        result = self.runtime.execute_sync("sync_test_v1", {"value": 7})

        assert result.success

    def test_execute_unloaded_node(self) -> None:
        """Test executing a node that hasn't been loaded."""
        result = self.runtime.execute_sync("nonexistent_v1", {})

        assert not result.success
        assert "not loaded" in result.error.lower()

    def test_set_execution_mode(self) -> None:
        """Test setting execution mode."""
        self.runtime.set_mode("test_node_v1", ExecutionMode.DUAL_VERIFY)

        mode = self.runtime.migration_controller.get_execution_mode("test_node_v1")
        assert mode == ExecutionMode.DUAL_VERIFY


class TestMigrationController:
    """Tests for the MigrationController class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.controller = MigrationController()

    def test_default_mode_is_python_only(self) -> None:
        """Test that default execution mode is Python-only."""
        mode = self.controller.get_execution_mode("any_node_v1")
        assert mode == ExecutionMode.PYTHON_ONLY

    def test_set_and_get_mode(self) -> None:
        """Test setting and getting execution mode."""
        self.controller.set_execution_mode("test_v1", ExecutionMode.CANARY_DIRECT)
        mode = self.controller.get_execution_mode("test_v1")

        assert mode == ExecutionMode.CANARY_DIRECT

    def test_metrics_initialized_empty(self) -> None:
        """Test that metrics are initialized with zeros."""
        metrics = self.controller.get_metrics("new_node_v1")

        assert metrics.total_executions == 0
        assert metrics.divergences == 0
        assert metrics.errors == 0

    def test_confidence_zero_for_few_samples(self) -> None:
        """Test that confidence is zero when samples are insufficient."""
        confidence = self.controller.calculate_confidence("new_node_v1")
        assert confidence == 0.0

    def test_record_execution(self) -> None:
        """Test recording execution metrics."""
        from vesper.runtime import ExecutionMetrics

        metrics = ExecutionMetrics(
            node_id="record_test_v1", duration_ms=50.0, path_used="python", success=True
        )

        self.controller.record_execution(metrics)

        node_metrics = self.controller.get_metrics("record_test_v1")
        assert node_metrics.total_executions == 1
        assert node_metrics.python_executions == 1
        assert node_metrics.total_duration_ms == 50.0


class TestRuntimeMetrics:
    """Tests for RuntimeMetrics calculations."""

    def test_avg_duration_empty(self) -> None:
        """Test average duration with no executions."""
        metrics = RuntimeMetrics(node_id="test_v1")
        assert metrics.avg_duration_ms == 0.0

    def test_avg_duration_calculated(self) -> None:
        """Test average duration calculation."""
        metrics = RuntimeMetrics(
            node_id="test_v1", total_executions=4, total_duration_ms=100.0
        )
        assert metrics.avg_duration_ms == 25.0

    def test_error_rate_calculated(self) -> None:
        """Test error rate calculation."""
        metrics = RuntimeMetrics(node_id="test_v1", total_executions=100, errors=5)
        assert metrics.error_rate == 0.05

    def test_divergence_rate_calculated(self) -> None:
        """Test divergence rate calculation."""
        metrics = RuntimeMetrics(
            node_id="test_v1", total_executions=1000, divergences=10
        )
        assert metrics.divergence_rate == 0.01
