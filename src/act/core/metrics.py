"""Metrics collection for AgentCommandTool.

Tracks:
- Tasks by final state
- Average verification attempts
- REPLAN frequency
- Scout query latency
- Verifier execution time
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any


@dataclass
class LatencyStats:
    """Statistics for latency measurements."""

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    values: list[float] = field(default_factory=list)

    def record(self, duration_ms: float) -> None:
        """Record a latency measurement.

        Args:
            duration_ms: Duration in milliseconds
        """
        self.count += 1
        self.total_ms += duration_ms
        self.min_ms = min(self.min_ms, duration_ms)
        self.max_ms = max(self.max_ms, duration_ms)
        self.values.append(duration_ms)

    @property
    def avg_ms(self) -> float:
        """Average latency in milliseconds."""
        return self.total_ms / self.count if self.count > 0 else 0.0

    @property
    def p50_ms(self) -> float:
        """50th percentile (median) latency."""
        if not self.values:
            return 0.0
        sorted_values = sorted(self.values)
        idx = len(sorted_values) // 2
        return sorted_values[idx]

    @property
    def p95_ms(self) -> float:
        """95th percentile latency."""
        if not self.values:
            return 0.0
        sorted_values = sorted(self.values)
        idx = int(len(sorted_values) * 0.95)
        return sorted_values[min(idx, len(sorted_values) - 1)]

    @property
    def p99_ms(self) -> float:
        """99th percentile latency."""
        if not self.values:
            return 0.0
        sorted_values = sorted(self.values)
        idx = int(len(sorted_values) * 0.99)
        return sorted_values[min(idx, len(sorted_values) - 1)]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "count": self.count,
            "total_ms": round(self.total_ms, 2),
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.min_ms != float("inf") else 0.0,
            "max_ms": round(self.max_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self.count = 0
        self.total_ms = 0.0
        self.min_ms = float("inf")
        self.max_ms = 0.0
        self.values.clear()


@dataclass
class TaskMetrics:
    """Metrics for a single task."""

    task_id: str
    started_at: datetime
    completed_at: datetime | None = None
    final_state: str | None = None
    verification_attempts: int = 0
    replan_count: int = 0
    scout_query_count: int = 0
    total_scout_latency_ms: float = 0.0
    total_verifier_latency_ms: float = 0.0

    @property
    def duration_ms(self) -> float | None:
        """Task duration in milliseconds."""
        if self.completed_at is None:
            return None
        delta = self.completed_at - self.started_at
        return delta.total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        completed = (
            self.completed_at.isoformat() if self.completed_at else None
        )
        return {
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": completed,
            "final_state": self.final_state,
            "verification_attempts": self.verification_attempts,
            "replan_count": self.replan_count,
            "scout_query_count": self.scout_query_count,
            "total_scout_latency_ms": round(self.total_scout_latency_ms, 2),
            "total_verifier_latency_ms": round(self.total_verifier_latency_ms, 2),
            "duration_ms": round(self.duration_ms, 2) if self.duration_ms else None,
        }


class MetricsCollector:
    """Collects and aggregates metrics.

    Thread-safe implementation for concurrent access.
    """

    # Default task states to track
    DEFAULT_STATES = (
        "QUEUED", "RUNNING", "SUCCESS", "CANCELLED", "STUCK", "INFRA_ERROR"
    )

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self._lock = Lock()

        # Task state counts
        self._tasks_by_state: dict[str, int] = dict.fromkeys(self.DEFAULT_STATES, 0)

        # Verification attempts
        self._verification_attempts: list[int] = []

        # REPLAN frequency
        self._replan_counts: list[int] = []

        # Latency stats
        self._scout_a_latency = LatencyStats()
        self._scout_b_latency = LatencyStats()
        self._verifier_latency = LatencyStats()

        # Current tasks
        self._current_tasks: dict[str, TaskMetrics] = {}

        # Completed tasks history (limited)
        self._completed_tasks: list[TaskMetrics] = []
        self._max_completed_history = 100

    def start_task(self, task_id: str) -> None:
        """Record task start.

        Args:
            task_id: Task identifier
        """
        with self._lock:
            self._current_tasks[task_id] = TaskMetrics(
                task_id=task_id,
                started_at=datetime.now(UTC),
            )

    def end_task(self, task_id: str, final_state: str) -> None:
        """Record task completion.

        Args:
            task_id: Task identifier
            final_state: Final task state
        """
        with self._lock:
            if task_id in self._current_tasks:
                metrics = self._current_tasks[task_id]
                metrics.completed_at = datetime.now(UTC)
                metrics.final_state = final_state

                # Update aggregates
                if final_state in self._tasks_by_state:
                    self._tasks_by_state[final_state] += 1

                self._verification_attempts.append(metrics.verification_attempts)
                self._replan_counts.append(metrics.replan_count)

                # Add to completed history
                self._completed_tasks.append(metrics)
                if len(self._completed_tasks) > self._max_completed_history:
                    self._completed_tasks.pop(0)

                del self._current_tasks[task_id]

    def record_verification_attempt(self, task_id: str) -> None:
        """Record a verification attempt.

        Args:
            task_id: Task identifier
        """
        with self._lock:
            if task_id in self._current_tasks:
                self._current_tasks[task_id].verification_attempts += 1

    def record_replan(self, task_id: str) -> None:
        """Record a REPLAN event.

        Args:
            task_id: Task identifier
        """
        with self._lock:
            if task_id in self._current_tasks:
                self._current_tasks[task_id].replan_count += 1

    def record_scout_query(
        self,
        scout_name: str,
        duration_ms: float,
        task_id: str | None = None,
    ) -> None:
        """Record Scout query latency.

        Args:
            scout_name: Name of scout (scout_a or scout_b)
            duration_ms: Query duration in milliseconds
            task_id: Optional task identifier
        """
        with self._lock:
            if scout_name == "scout_a":
                self._scout_a_latency.record(duration_ms)
            elif scout_name == "scout_b":
                self._scout_b_latency.record(duration_ms)

            if task_id and task_id in self._current_tasks:
                self._current_tasks[task_id].scout_query_count += 1
                self._current_tasks[task_id].total_scout_latency_ms += duration_ms

    def record_verifier_execution(
        self,
        duration_ms: float,
        task_id: str | None = None,
    ) -> None:
        """Record Verifier execution time.

        Args:
            duration_ms: Execution duration in milliseconds
            task_id: Optional task identifier
        """
        with self._lock:
            self._verifier_latency.record(duration_ms)

            if task_id and task_id in self._current_tasks:
                self._current_tasks[task_id].total_verifier_latency_ms += duration_ms

    def get_task_metrics(self, task_id: str) -> TaskMetrics | None:
        """Get metrics for a specific task.

        Args:
            task_id: Task identifier

        Returns:
            TaskMetrics if found, None otherwise
        """
        with self._lock:
            return self._current_tasks.get(task_id)

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary.

        Returns:
            Dictionary with aggregated metrics
        """
        with self._lock:
            total_tasks = sum(self._tasks_by_state.values())

            return {
                "tasks": {
                    "total": total_tasks,
                    "by_state": dict(self._tasks_by_state),
                    "success_rate": (
                        round(self._tasks_by_state.get("SUCCESS", 0) / total_tasks, 4)
                        if total_tasks > 0
                        else 0.0
                    ),
                    "current_running": len(self._current_tasks),
                },
                "verification": {
                    "total_attempts": sum(self._verification_attempts),
                    "average_attempts": (
                        round(statistics.mean(self._verification_attempts), 2)
                        if self._verification_attempts
                        else 0.0
                    ),
                    "max_attempts": (
                        max(self._verification_attempts)
                        if self._verification_attempts
                        else 0
                    ),
                },
                "replan": {
                    "total_count": sum(self._replan_counts),
                    "average_per_task": (
                        round(statistics.mean(self._replan_counts), 2)
                        if self._replan_counts
                        else 0.0
                    ),
                    "frequency": (
                        round(
                            sum(1 for c in self._replan_counts if c > 0)
                            / len(self._replan_counts),
                            4,
                        )
                        if self._replan_counts
                        else 0.0
                    ),
                },
                "latency": {
                    "scout_a": self._scout_a_latency.to_dict(),
                    "scout_b": self._scout_b_latency.to_dict(),
                    "verifier": self._verifier_latency.to_dict(),
                },
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._tasks_by_state = dict.fromkeys(self.DEFAULT_STATES, 0)
            self._verification_attempts.clear()
            self._replan_counts.clear()
            self._scout_a_latency.reset()
            self._scout_b_latency.reset()
            self._verifier_latency.reset()
            self._current_tasks.clear()
            self._completed_tasks.clear()


# Global metrics collector
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector.

    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics_collector() -> None:
    """Reset the global metrics collector. Useful for testing."""
    global _metrics_collector
    if _metrics_collector is not None:
        _metrics_collector.reset()
    _metrics_collector = None


class Timer:
    """Context manager for timing operations.

    Example:
        with Timer() as timer:
            # Do something
            pass
        print(f"Duration: {timer.duration_ms}ms")
    """

    def __init__(self) -> None:
        """Initialize timer."""
        self.start_time: float = 0
        self.end_time: float = 0

    def __enter__(self) -> Timer:
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        """Stop timing."""
        self.end_time = time.perf_counter()

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self.end_time - self.start_time
