"""Unit tests for task runner module."""

import pytest
from io import StringIO
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock
import time

from rich.console import Console

from act.task.state import Task, TaskState, create_task
from act.task.queue import TaskQueue
from act.task.display import StatusDisplay, Milestone
from act.task.runner import (
    TaskRunner,
    TaskRunnerError,
    TaskCancelledError,
    TaskResult,
    create_task_runner,
)


@pytest.fixture
def console() -> Console:
    """Create a console that captures output."""
    return Console(file=StringIO(), force_terminal=True, width=120)


@pytest.fixture
def queue() -> TaskQueue:
    """Create a fresh task queue."""
    return TaskQueue()


@pytest.fixture
def display(console: Console) -> StatusDisplay:
    """Create a status display with test console."""
    return StatusDisplay(console=console, verbose=False)


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    """Create a temporary repo path."""
    return tmp_path


@pytest.fixture
def config() -> Mock:
    """Create a mock config."""
    return Mock()


@pytest.fixture
def runner(queue: TaskQueue, display: StatusDisplay, repo_path: Path, config: Mock) -> TaskRunner:
    """Create a task runner."""
    return TaskRunner(
        queue=queue,
        display=display,
        repo_path=repo_path,
        config=config,
    )


class TestTaskRunnerExceptions:
    """Tests for runner exception classes."""

    def test_task_cancelled_error(self) -> None:
        """TaskCancelledError has task_id."""
        error = TaskCancelledError("task_123")
        assert error.task_id == "task_123"
        assert "task_123" in str(error)


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_success_result(self) -> None:
        """Create success result."""
        task = create_task("Test")
        task.state = TaskState.SUCCESS

        result = TaskResult(
            task=task,
            success=True,
            summary="Task completed",
        )

        assert result.success is True
        assert result.summary == "Task completed"
        assert result.error_message is None

    def test_failure_result(self) -> None:
        """Create failure result."""
        task = create_task("Test")
        task.state = TaskState.STUCK

        result = TaskResult(
            task=task,
            success=False,
            stuck_report_path="agent/stuck_report.md",
        )

        assert result.success is False
        assert result.stuck_report_path == "agent/stuck_report.md"

    def test_error_result(self) -> None:
        """Create error result."""
        task = create_task("Test")
        task.state = TaskState.INFRA_ERROR

        result = TaskResult(
            task=task,
            success=False,
            error_message="Docker unavailable",
        )

        assert result.success is False
        assert result.error_message == "Docker unavailable"


class TestTaskRunnerSubmit:
    """Tests for task submission."""

    def test_submit_starts_immediately_when_idle(self, runner: TaskRunner) -> None:
        """Task starts immediately when no task running."""
        task = create_task("Test task")
        position = runner.submit(task)

        # Position 0 means started immediately (or position > 0 if queued)
        # Actually, after submit, task should be set as current
        runner.wait_for_completion(timeout=5.0)

        assert task.state in [TaskState.SUCCESS, TaskState.CANCELLED, TaskState.INFRA_ERROR]

    def test_submit_queues_when_busy(self, runner: TaskRunner, queue: TaskQueue) -> None:
        """Task is queued when another task running."""
        # Set a current task manually
        running_task = create_task("Running")
        running_task.state = TaskState.RUNNING
        queue.set_current(running_task)

        new_task = create_task("New task")
        position = runner.submit(new_task)

        assert position > 0
        assert queue.size() > 0


class TestTaskRunnerStateTransitions:
    """Tests for state transitions."""

    def test_task_transitions_to_running(self, runner: TaskRunner) -> None:
        """Task transitions from QUEUED to RUNNING."""
        task = create_task("Test")
        assert task.state == TaskState.QUEUED

        runner.submit(task)
        # Give it a moment to start
        time.sleep(0.1)

        # Should be running or already completed
        assert task.state in [TaskState.RUNNING, TaskState.SUCCESS]

    def test_task_sets_started_at(self, runner: TaskRunner) -> None:
        """Task gets started_at timestamp."""
        task = create_task("Test")
        assert task.started_at is None

        runner.submit(task)
        runner.wait_for_completion(timeout=5.0)

        assert task.started_at is not None

    def test_task_sets_completed_at(self, runner: TaskRunner) -> None:
        """Task gets completed_at timestamp."""
        task = create_task("Test")

        runner.submit(task)
        runner.wait_for_completion(timeout=5.0)

        assert task.completed_at is not None


class TestTaskRunnerDryRun:
    """Tests for dry-run mode."""

    def test_dry_run_skips_verification(self, runner: TaskRunner) -> None:
        """Dry-run skips verification and succeeds."""
        task = create_task("Test", dry_run=True)

        runner.submit(task)
        runner.wait_for_completion(timeout=5.0)

        assert task.state == TaskState.SUCCESS


class TestTaskRunnerCancellation:
    """Tests for task cancellation."""

    def test_cancel_current_returns_false_when_idle(self, runner: TaskRunner) -> None:
        """Cancel returns False when no task running."""
        assert runner.cancel_current() is False

    def test_cancel_queued_by_position(self, runner: TaskRunner, queue: TaskQueue) -> None:
        """Can cancel queued task by position."""
        # Set a current task to make queue work
        running_task = create_task("Running")
        running_task.state = TaskState.RUNNING
        queue.set_current(running_task)

        # Add tasks to queue
        task1 = create_task("Task 1")
        task2 = create_task("Task 2")
        queue.add(task1)
        queue.add(task2)

        # Cancel position 1
        cancelled = runner.cancel_queued(1)

        assert cancelled == task1
        assert cancelled.state == TaskState.CANCELLED
        assert queue.size() == 1

    def test_cancel_queued_invalid_position(self, runner: TaskRunner, queue: TaskQueue) -> None:
        """Cancel invalid position returns None."""
        cancelled = runner.cancel_queued(999)
        assert cancelled is None

    def test_cancel_by_id_queued(self, runner: TaskRunner, queue: TaskQueue) -> None:
        """Can cancel queued task by ID."""
        # Set a current task
        running_task = create_task("Running")
        running_task.state = TaskState.RUNNING
        queue.set_current(running_task)

        # Add task to queue
        task = create_task("To cancel")
        queue.add(task)

        # Cancel by ID
        result = runner.cancel_by_id(task.id)

        assert result is True
        assert task.state == TaskState.CANCELLED

    def test_cancel_by_id_not_found(self, runner: TaskRunner) -> None:
        """Cancel unknown ID returns False."""
        result = runner.cancel_by_id("nonexistent_id")
        assert result is False


class TestTaskRunnerStatus:
    """Tests for status retrieval."""

    def test_get_status_idle(self, runner: TaskRunner) -> None:
        """Get status when idle."""
        status = runner.get_status()

        assert status["current"] is None
        assert status["queue_size"] == 0
        assert status["queued_tasks"] == []

    def test_get_status_with_current(self, runner: TaskRunner, queue: TaskQueue) -> None:
        """Get status with current task."""
        task = create_task("Running task")
        task.state = TaskState.RUNNING
        queue.set_current(task)

        status = runner.get_status()

        assert status["current"] is not None
        assert status["current"]["id"] == task.id

    def test_get_status_with_queue(self, runner: TaskRunner, queue: TaskQueue) -> None:
        """Get status with queued tasks."""
        # Set current
        current = create_task("Current")
        current.state = TaskState.RUNNING
        queue.set_current(current)

        # Add to queue
        queued = create_task("Queued")
        queue.add(queued)

        status = runner.get_status()

        assert status["queue_size"] == 1
        assert len(status["queued_tasks"]) == 1
        assert status["queued_tasks"][0]["position"] == 1


class TestTaskRunnerCallbacks:
    """Tests for completion callbacks."""

    def test_add_completion_callback(self, runner: TaskRunner) -> None:
        """Can add completion callback."""
        results: list[TaskResult] = []

        def callback(result: TaskResult) -> None:
            results.append(result)

        runner.add_completion_callback(callback)
        task = create_task("Test")
        runner.submit(task)
        runner.wait_for_completion(timeout=5.0)

        assert len(results) == 1
        assert results[0].task == task

    def test_callback_error_doesnt_break_execution(self, runner: TaskRunner) -> None:
        """Callback errors don't break execution."""

        def bad_callback(result: TaskResult) -> None:
            raise ValueError("Callback error")

        runner.add_completion_callback(bad_callback)
        task = create_task("Test")
        runner.submit(task)

        # Should not raise
        runner.wait_for_completion(timeout=5.0)


class TestTaskRunnerWait:
    """Tests for wait functionality."""

    def test_wait_returns_true_when_no_task(self, runner: TaskRunner) -> None:
        """Wait returns True when no task running."""
        assert runner.wait_for_completion() is True

    def test_wait_for_completion_success(self, runner: TaskRunner) -> None:
        """Wait returns True when task completes."""
        task = create_task("Test")
        runner.submit(task)

        result = runner.wait_for_completion(timeout=5.0)

        assert result is True
        assert task.is_terminal()


class TestCreateTaskRunner:
    """Tests for factory function."""

    def test_create_task_runner_minimal(self, repo_path: Path, config: Mock) -> None:
        """Create runner with minimal args."""
        runner = create_task_runner(repo_path=repo_path, config=config)

        assert isinstance(runner, TaskRunner)
        assert runner.repo_path == repo_path
        assert runner.config == config

    def test_create_task_runner_with_queue(
        self, repo_path: Path, config: Mock, queue: TaskQueue
    ) -> None:
        """Create runner with custom queue."""
        runner = create_task_runner(
            repo_path=repo_path,
            config=config,
            queue=queue,
        )

        assert runner.queue is queue

    def test_create_task_runner_verbose(self, repo_path: Path, config: Mock) -> None:
        """Create runner with verbose flag."""
        runner = create_task_runner(
            repo_path=repo_path,
            config=config,
            verbose=True,
        )

        assert runner.display.verbose is True
