"""
Tests for Confidence Calculation
"""

import pytest
from vesper_verification.confidence import ConfidenceTracker, RuntimeMetrics


class TestRuntimeMetrics:
    """Tests for RuntimeMetrics dataclass."""

    def test_success_rate_no_executions(self):
        """Success rate is 0 with no executions."""
        metrics = RuntimeMetrics(node_id="test_node")
        assert metrics.success_rate == 0.0

    def test_success_rate_all_success(self):
        """Success rate is 1.0 with no divergences."""
        metrics = RuntimeMetrics(
            node_id="test_node",
            total_executions=100,
            divergences=0,
        )
        assert metrics.success_rate == 1.0

    def test_success_rate_partial(self):
        """Success rate reflects divergence proportion."""
        metrics = RuntimeMetrics(
            node_id="test_node",
            total_executions=100,
            divergences=10,
        )
        assert metrics.success_rate == 0.9

    def test_divergence_rate(self):
        """Divergence rate is calculated correctly."""
        metrics = RuntimeMetrics(
            node_id="test_node",
            total_executions=100,
            divergences=5,
        )
        assert metrics.divergence_rate == 0.05


class TestConfidenceTracker:
    """Tests for ConfidenceTracker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ConfidenceTracker()

    def test_no_data_returns_zero_confidence(self):
        """No data means zero confidence."""
        confidence = self.tracker.get_confidence("unknown_node")
        assert confidence == 0.0

    def test_insufficient_data_returns_zero(self):
        """Fewer than MIN_SAMPLE_SIZE executions returns zero."""
        for _ in range(50):  # Less than MIN_SAMPLE_SIZE (100)
            self.tracker.record_execution("test_node", diverged=False)

        confidence = self.tracker.get_confidence("test_node")
        assert confidence == 0.0

    def test_perfect_record_high_confidence(self):
        """Perfect record gives high confidence."""
        for _ in range(1000):
            self.tracker.record_execution("test_node", diverged=False)

        confidence = self.tracker.get_confidence("test_node")
        # Wilson score with z=3.29 gives conservative bounds
        # With 1000 perfect executions, expect ~0.989
        assert confidence > 0.98

    def test_all_divergences_low_confidence(self):
        """All divergences gives low confidence."""
        for _ in range(1000):
            self.tracker.record_execution("test_node", diverged=True)

        confidence = self.tracker.get_confidence("test_node")
        assert confidence < 0.01

    def test_mixed_record_intermediate_confidence(self):
        """Mixed record gives intermediate confidence."""
        # 5% divergence rate
        for i in range(1000):
            self.tracker.record_execution(
                "test_node",
                diverged=(i % 20 == 0),  # 5% divergence
            )

        confidence = self.tracker.get_confidence("test_node")
        # Should be around 0.93-0.97 with 5% divergence
        assert 0.90 < confidence < 0.98

    def test_wilson_score_conservative(self):
        """Wilson score gives conservative estimate for small samples."""
        for _ in range(100):
            self.tracker.record_execution("small_sample", diverged=False)

        for _ in range(1000):
            self.tracker.record_execution("large_sample", diverged=False)

        small_confidence = self.tracker.get_confidence("small_sample")
        large_confidence = self.tracker.get_confidence("large_sample")

        # Larger sample should have higher confidence
        assert large_confidence > small_confidence

    def test_record_errors(self):
        """Errors are tracked separately."""
        self.tracker.record_execution(
            "test_node",
            diverged=False,
            python_error=True,
        )
        self.tracker.record_execution(
            "test_node",
            diverged=False,
            direct_error=True,
        )

        metrics = self.tracker.get_metrics("test_node")
        assert metrics is not None
        assert metrics.python_errors == 1
        assert metrics.direct_errors == 1

    def test_get_metrics_returns_none_for_unknown(self):
        """get_metrics returns None for unknown nodes."""
        metrics = self.tracker.get_metrics("unknown_node")
        assert metrics is None

    def test_get_all_metrics(self):
        """get_all_metrics returns all tracked nodes."""
        self.tracker.record_execution("node_a", diverged=False)
        self.tracker.record_execution("node_b", diverged=False)

        all_metrics = self.tracker.get_all_metrics()
        assert "node_a" in all_metrics
        assert "node_b" in all_metrics

    def test_reset_metrics(self):
        """reset_metrics clears metrics for a node."""
        self.tracker.record_execution("test_node", diverged=False)
        assert self.tracker.get_metrics("test_node") is not None

        self.tracker.reset_metrics("test_node")
        assert self.tracker.get_metrics("test_node") is None

    def test_recommended_mode_low_confidence(self):
        """Low confidence recommends python_only."""
        for _ in range(100):
            self.tracker.record_execution("test_node", diverged=True)

        mode = self.tracker.get_recommended_mode("test_node")
        assert mode == "python_only"

    def test_recommended_mode_high_confidence(self):
        """High confidence recommends direct modes."""
        # Need many more executions for very high confidence
        for _ in range(100000):
            self.tracker.record_execution("test_node", diverged=False)

        mode = self.tracker.get_recommended_mode("test_node")
        # With 100k perfect executions, should be dual_verify or direct_only
        assert mode in ("canary_direct", "dual_verify", "direct_only")

    def test_serialize_deserialize(self):
        """Serialization and deserialization preserve state."""
        for _ in range(200):
            self.tracker.record_execution("test_node", diverged=False)

        for _ in range(10):
            self.tracker.record_execution("test_node", diverged=True)

        serialized = self.tracker.serialize()
        restored = ConfidenceTracker.deserialize(serialized)

        original_metrics = self.tracker.get_metrics("test_node")
        restored_metrics = restored.get_metrics("test_node")

        assert original_metrics is not None
        assert restored_metrics is not None
        assert original_metrics.total_executions == restored_metrics.total_executions
        assert original_metrics.divergences == restored_metrics.divergences


class TestConfidenceThresholds:
    """Tests for confidence threshold logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tracker = ConfidenceTracker()

    def test_threshold_boundaries(self):
        """Test confidence at various threshold boundaries."""
        # Create metrics with known divergence rates

        # 0% divergence - should be very high confidence
        for _ in range(1000):
            self.tracker.record_execution("perfect", diverged=False)

        # 1% divergence - should be around 0.98
        for i in range(1000):
            self.tracker.record_execution("one_percent", diverged=(i < 10))

        # 10% divergence - should be around 0.88
        for i in range(1000):
            self.tracker.record_execution("ten_percent", diverged=(i < 100))

        perfect = self.tracker.get_confidence("perfect")
        one_percent = self.tracker.get_confidence("one_percent")
        ten_percent = self.tracker.get_confidence("ten_percent")

        # Verify ordering
        assert perfect > one_percent > ten_percent

        # Verify approximate values (Wilson score is conservative)
        assert perfect > 0.98  # With z=3.29 and 1000 samples, ~0.989
        assert 0.95 < one_percent < 0.995
        assert 0.85 < ten_percent < 0.92

    def test_sample_size_effect(self):
        """Larger sample sizes give tighter confidence bounds."""
        # Same 1% divergence rate, different sample sizes
        for i in range(100):
            self.tracker.record_execution("small", diverged=(i < 1))

        for i in range(1000):
            self.tracker.record_execution("medium", diverged=(i < 10))

        for i in range(10000):
            self.tracker.record_execution("large", diverged=(i < 100))

        small = self.tracker.get_confidence("small")
        medium = self.tracker.get_confidence("medium")
        large = self.tracker.get_confidence("large")

        # Larger samples should have higher (tighter) confidence bounds
        assert large >= medium >= small

