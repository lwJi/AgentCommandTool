"""Unit tests for act.core.metrics module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Thread

import pytest

from act.core.metrics import (
    LatencyStats,
    MetricsCollector,
    TaskMetrics,
    Timer,
    get_metrics_collector,
    reset_metrics_collector,
)


class TestLatencyStats:
    """Tests for LatencyStats dataclass."""

    def test_initial_state(self) -> None:
        """LatencyStats has correct initial state."""
        stats = LatencyStats()
        assert stats.count == 0
        assert stats.total_ms == 0.0
        assert stats.min_ms == float("inf")
        assert stats.max_ms == 0.0
        assert stats.values == []

    def test_record_single_value(self) -> None:
        """record() updates statistics for single value."""
        stats = LatencyStats()
        stats.record(100.0)
        assert stats.count == 1
        assert stats.total_ms == 100.0
        assert stats.min_ms == 100.0
        assert stats.max_ms == 100.0
        assert stats.values == [100.0]

    def test_record_multiple_values(self) -> None:
        """record() correctly accumulates multiple values."""
        stats = LatencyStats()
        stats.record(100.0)
        stats.record(200.0)
        stats.record(300.0)
        assert stats.count == 3
        assert stats.total_ms == 600.0
        assert stats.min_ms == 100.0
        assert stats.max_ms == 300.0

    def test_avg_ms_with_no_values(self) -> None:
        """avg_ms returns 0.0 when no values recorded."""
        stats = LatencyStats()
        assert stats.avg_ms == 0.0

    def test_avg_ms_with_values(self) -> None:
        """avg_ms calculates correct average."""
        stats = LatencyStats()
        stats.record(100.0)
        stats.record(200.0)
        stats.record(300.0)
        assert stats.avg_ms == 200.0

    def test_p50_ms_with_no_values(self) -> None:
        """p50_ms returns 0.0 when no values recorded."""
        stats = LatencyStats()
        assert stats.p50_ms == 0.0

    def test_p50_ms_with_values(self) -> None:
        """p50_ms returns median value."""
        stats = LatencyStats()
        for v in [10, 20, 30, 40, 50]:
            stats.record(v)
        assert stats.p50_ms == 30

    def test_p95_ms_with_values(self) -> None:
        """p95_ms returns 95th percentile."""
        stats = LatencyStats()
        for v in range(1, 101):
            stats.record(float(v))
        # Index int(100 * 0.95) = 95, value at index 95 is 96.0
        assert stats.p95_ms == 96.0

    def test_p99_ms_with_values(self) -> None:
        """p99_ms returns 99th percentile."""
        stats = LatencyStats()
        for v in range(1, 101):
            stats.record(float(v))
        # Index int(100 * 0.99) = 99, value at index 99 is 100.0
        assert stats.p99_ms == 100.0

    def test_to_dict(self) -> None:
        """to_dict() returns correct structure."""
        stats = LatencyStats()
        stats.record(100.0)
        stats.record(200.0)
        data = stats.to_dict()
        assert data["count"] == 2
        assert data["total_ms"] == 300.0
        assert data["avg_ms"] == 150.0
        assert data["min_ms"] == 100.0
        assert data["max_ms"] == 200.0
        assert "p50_ms" in data
        assert "p95_ms" in data
        assert "p99_ms" in data

    def test_to_dict_handles_no_values(self) -> None:
        """to_dict() handles empty stats gracefully."""
        stats = LatencyStats()
        data = stats.to_dict()
        assert data["count"] == 0
        assert data["min_ms"] == 0.0  # Not inf

    def test_reset(self) -> None:
        """reset() clears all statistics."""
        stats = LatencyStats()
        stats.record(100.0)
        stats.record(200.0)
        stats.reset()
        assert stats.count == 0
        assert stats.total_ms == 0.0
        assert stats.values == []


class TestTaskMetrics:
    """Tests for TaskMetrics dataclass."""

    def test_initial_state(self) -> None:
        """TaskMetrics has correct initial state."""
        now = datetime.now(UTC)
        metrics = TaskMetrics(task_id="task_001", started_at=now)
        assert metrics.task_id == "task_001"
        assert metrics.started_at == now
        assert metrics.completed_at is None
        assert metrics.final_state is None
        assert metrics.verification_attempts == 0

    def test_duration_ms_returns_none_when_incomplete(self) -> None:
        """duration_ms returns None when task not completed."""
        metrics = TaskMetrics(task_id="task_001", started_at=datetime.now(UTC))
        assert metrics.duration_ms is None

    def test_duration_ms_calculates_correctly(self) -> None:
        """duration_ms calculates correct duration."""
        start = datetime.now(UTC)
        end = start + timedelta(seconds=5)
        metrics = TaskMetrics(task_id="task_001", started_at=start, completed_at=end)
        assert metrics.duration_ms == 5000.0

    def test_to_dict(self) -> None:
        """to_dict() returns correct structure."""
        now = datetime.now(UTC)
        metrics = TaskMetrics(
            task_id="task_001",
            started_at=now,
            verification_attempts=3,
            replan_count=1,
        )
        data = metrics.to_dict()
        assert data["task_id"] == "task_001"
        assert data["verification_attempts"] == 3
        assert data["replan_count"] == 1
        assert data["completed_at"] is None


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def test_initial_state(self) -> None:
        """MetricsCollector has correct initial state."""
        collector = MetricsCollector()
        summary = collector.get_summary()
        assert summary["tasks"]["total"] == 0
        assert summary["tasks"]["current_running"] == 0

    def test_start_task(self) -> None:
        """start_task() creates task metrics."""
        collector = MetricsCollector()
        collector.start_task("task_001")
        summary = collector.get_summary()
        assert summary["tasks"]["current_running"] == 1

    def test_end_task_updates_counts(self) -> None:
        """end_task() updates state counts."""
        collector = MetricsCollector()
        collector.start_task("task_001")
        collector.end_task("task_001", "SUCCESS")
        summary = collector.get_summary()
        assert summary["tasks"]["total"] == 1
        assert summary["tasks"]["by_state"]["SUCCESS"] == 1
        assert summary["tasks"]["current_running"] == 0

    def test_end_task_unknown_state(self) -> None:
        """end_task() handles unknown states gracefully."""
        collector = MetricsCollector()
        collector.start_task("task_001")
        collector.end_task("task_001", "UNKNOWN_STATE")
        summary = collector.get_summary()
        assert summary["tasks"]["total"] == 0  # Not counted

    def test_record_verification_attempt(self) -> None:
        """record_verification_attempt() increments count."""
        collector = MetricsCollector()
        collector.start_task("task_001")
        collector.record_verification_attempt("task_001")
        collector.record_verification_attempt("task_001")
        collector.end_task("task_001", "SUCCESS")
        summary = collector.get_summary()
        assert summary["verification"]["total_attempts"] == 2

    def test_record_replan(self) -> None:
        """record_replan() increments count."""
        collector = MetricsCollector()
        collector.start_task("task_001")
        collector.record_replan("task_001")
        collector.end_task("task_001", "SUCCESS")
        summary = collector.get_summary()
        assert summary["replan"]["total_count"] == 1

    def test_record_scout_query(self) -> None:
        """record_scout_query() updates latency stats."""
        collector = MetricsCollector()
        collector.record_scout_query("scout_a", 100.0)
        collector.record_scout_query("scout_b", 150.0)
        summary = collector.get_summary()
        assert summary["latency"]["scout_a"]["count"] == 1
        assert summary["latency"]["scout_b"]["count"] == 1

    def test_record_scout_query_with_task(self) -> None:
        """record_scout_query() updates task metrics."""
        collector = MetricsCollector()
        collector.start_task("task_001")
        collector.record_scout_query("scout_a", 100.0, task_id="task_001")
        metrics = collector.get_task_metrics("task_001")
        assert metrics is not None
        assert metrics.scout_query_count == 1
        assert metrics.total_scout_latency_ms == 100.0

    def test_record_verifier_execution(self) -> None:
        """record_verifier_execution() updates latency stats."""
        collector = MetricsCollector()
        collector.record_verifier_execution(5000.0)
        summary = collector.get_summary()
        assert summary["latency"]["verifier"]["count"] == 1
        assert summary["latency"]["verifier"]["total_ms"] == 5000.0

    def test_get_task_metrics_returns_none_for_unknown(self) -> None:
        """get_task_metrics() returns None for unknown task."""
        collector = MetricsCollector()
        assert collector.get_task_metrics("unknown") is None

    def test_get_summary_calculates_success_rate(self) -> None:
        """get_summary() calculates correct success rate."""
        collector = MetricsCollector()
        for i in range(3):
            collector.start_task(f"success_{i}")
            collector.end_task(f"success_{i}", "SUCCESS")
        collector.start_task("fail_0")
        collector.end_task("fail_0", "STUCK")
        summary = collector.get_summary()
        assert summary["tasks"]["success_rate"] == 0.75

    def test_get_summary_calculates_average_attempts(self) -> None:
        """get_summary() calculates average verification attempts."""
        collector = MetricsCollector()
        collector.start_task("task_001")
        collector.record_verification_attempt("task_001")
        collector.record_verification_attempt("task_001")
        collector.end_task("task_001", "SUCCESS")
        collector.start_task("task_002")
        collector.record_verification_attempt("task_002")
        collector.end_task("task_002", "SUCCESS")
        summary = collector.get_summary()
        assert summary["verification"]["average_attempts"] == 1.5

    def test_get_summary_calculates_replan_frequency(self) -> None:
        """get_summary() calculates REPLAN frequency."""
        collector = MetricsCollector()
        # Task with REPLAN
        collector.start_task("task_001")
        collector.record_replan("task_001")
        collector.end_task("task_001", "SUCCESS")
        # Task without REPLAN
        collector.start_task("task_002")
        collector.end_task("task_002", "SUCCESS")
        summary = collector.get_summary()
        assert summary["replan"]["frequency"] == 0.5

    def test_reset(self) -> None:
        """reset() clears all metrics."""
        collector = MetricsCollector()
        collector.start_task("task_001")
        collector.record_scout_query("scout_a", 100.0)
        collector.reset()
        summary = collector.get_summary()
        assert summary["tasks"]["total"] == 0
        assert summary["latency"]["scout_a"]["count"] == 0

    def test_thread_safety(self) -> None:
        """MetricsCollector is thread-safe."""
        collector = MetricsCollector()
        errors: list[Exception] = []

        def worker(task_id: str) -> None:
            try:
                collector.start_task(task_id)
                collector.record_verification_attempt(task_id)
                collector.record_scout_query("scout_a", 100.0, task_id)
                collector.end_task(task_id, "SUCCESS")
            except Exception as e:
                errors.append(e)

        threads = [Thread(target=worker, args=(f"task_{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        summary = collector.get_summary()
        assert summary["tasks"]["total"] == 10


class TestMetricsCollectorSingleton:
    """Tests for metrics collector singleton functions."""

    def test_get_metrics_collector_returns_singleton(self) -> None:
        """get_metrics_collector() returns same instance."""
        reset_metrics_collector()
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        assert collector1 is collector2

    def test_reset_metrics_collector(self) -> None:
        """reset_metrics_collector() clears singleton."""
        reset_metrics_collector()
        collector1 = get_metrics_collector()
        collector1.start_task("task_001")
        reset_metrics_collector()
        collector2 = get_metrics_collector()
        assert collector1 is not collector2
        assert collector2.get_summary()["tasks"]["current_running"] == 0


class TestTimer:
    """Tests for Timer context manager."""

    def test_timer_measures_duration(self) -> None:
        """Timer measures operation duration."""
        with Timer() as timer:
            # Quick operation
            _ = sum(range(1000))
        assert timer.duration_ms >= 0
        assert timer.duration_seconds >= 0

    def test_timer_duration_ms(self) -> None:
        """duration_ms returns milliseconds."""
        timer = Timer()
        timer.start_time = 0.0
        timer.end_time = 1.5
        assert timer.duration_ms == 1500.0

    def test_timer_duration_seconds(self) -> None:
        """duration_seconds returns seconds."""
        timer = Timer()
        timer.start_time = 0.0
        timer.end_time = 1.5
        assert timer.duration_seconds == 1.5
