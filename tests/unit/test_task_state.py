"""Unit tests for task state module."""

import pytest
from datetime import datetime, timezone

from act.task.state import (
    TaskState,
    Task,
    TERMINAL_STATES,
    is_terminal_state,
    generate_task_id,
    create_task,
)


class TestTaskState:
    """Tests for TaskState enum."""

    def test_all_states_defined(self) -> None:
        """All expected states are defined."""
        assert TaskState.QUEUED.value == "QUEUED"
        assert TaskState.RUNNING.value == "RUNNING"
        assert TaskState.SUCCESS.value == "SUCCESS"
        assert TaskState.CANCELLED.value == "CANCELLED"
        assert TaskState.STUCK.value == "STUCK"
        assert TaskState.INFRA_ERROR.value == "INFRA_ERROR"

    def test_state_count(self) -> None:
        """Exactly 6 states defined."""
        assert len(TaskState) == 6


class TestTerminalStates:
    """Tests for terminal state handling."""

    def test_terminal_states_frozenset(self) -> None:
        """Terminal states is a frozen set."""
        assert isinstance(TERMINAL_STATES, frozenset)

    def test_terminal_states_contents(self) -> None:
        """Correct states are terminal."""
        assert TaskState.SUCCESS in TERMINAL_STATES
        assert TaskState.CANCELLED in TERMINAL_STATES
        assert TaskState.STUCK in TERMINAL_STATES
        assert TaskState.INFRA_ERROR in TERMINAL_STATES

    def test_non_terminal_states(self) -> None:
        """QUEUED and RUNNING are not terminal."""
        assert TaskState.QUEUED not in TERMINAL_STATES
        assert TaskState.RUNNING not in TERMINAL_STATES

    def test_is_terminal_state_function(self) -> None:
        """is_terminal_state returns correct values."""
        assert is_terminal_state(TaskState.SUCCESS) is True
        assert is_terminal_state(TaskState.CANCELLED) is True
        assert is_terminal_state(TaskState.STUCK) is True
        assert is_terminal_state(TaskState.INFRA_ERROR) is True
        assert is_terminal_state(TaskState.QUEUED) is False
        assert is_terminal_state(TaskState.RUNNING) is False


class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation_minimal(self) -> None:
        """Create task with minimal arguments."""
        task = Task(id="test_123", description="Test task")
        assert task.id == "test_123"
        assert task.description == "Test task"
        assert task.state == TaskState.QUEUED
        assert task.dry_run is False
        assert task.verbose is False

    def test_task_creation_full(self) -> None:
        """Create task with all arguments."""
        now = datetime.now(timezone.utc)
        task = Task(
            id="test_456",
            description="Full task",
            state=TaskState.RUNNING,
            created_at=now,
            started_at=now,
            dry_run=True,
            verbose=True,
            run_ids=["run_1", "run_2"],
            current_attempt=5,
        )
        assert task.state == TaskState.RUNNING
        assert task.dry_run is True
        assert task.verbose is True
        assert task.run_ids == ["run_1", "run_2"]
        assert task.current_attempt == 5

    def test_task_is_terminal(self) -> None:
        """is_terminal method works correctly."""
        queued_task = Task(id="t1", description="test", state=TaskState.QUEUED)
        running_task = Task(id="t2", description="test", state=TaskState.RUNNING)
        success_task = Task(id="t3", description="test", state=TaskState.SUCCESS)
        stuck_task = Task(id="t4", description="test", state=TaskState.STUCK)

        assert queued_task.is_terminal() is False
        assert running_task.is_terminal() is False
        assert success_task.is_terminal() is True
        assert stuck_task.is_terminal() is True

    def test_task_can_cancel_queued(self) -> None:
        """QUEUED tasks can be cancelled."""
        task = Task(id="t1", description="test", state=TaskState.QUEUED)
        assert task.can_cancel() is True

    def test_task_can_cancel_running(self) -> None:
        """RUNNING tasks can be cancelled."""
        task = Task(id="t1", description="test", state=TaskState.RUNNING)
        assert task.can_cancel() is True

    def test_task_cannot_cancel_terminal(self) -> None:
        """Terminal tasks cannot be cancelled."""
        for state in TERMINAL_STATES:
            task = Task(id="t1", description="test", state=state)
            assert task.can_cancel() is False

    def test_task_to_dict(self) -> None:
        """to_dict returns correct dictionary."""
        now = datetime.now(timezone.utc)
        task = Task(
            id="test_789",
            description="Dict test",
            state=TaskState.RUNNING,
            created_at=now,
            dry_run=True,
            current_attempt=3,
        )
        d = task.to_dict()

        assert d["id"] == "test_789"
        assert d["description"] == "Dict test"
        assert d["state"] == "RUNNING"
        assert d["dry_run"] is True
        assert d["current_attempt"] == 3
        assert d["created_at"] == now.isoformat()

    def test_task_to_dict_timestamps_optional(self) -> None:
        """Optional timestamps handled correctly."""
        task = Task(id="t1", description="test")
        d = task.to_dict()

        assert d["started_at"] is None
        assert d["completed_at"] is None

    def test_task_default_run_ids_empty(self) -> None:
        """Default run_ids is empty list."""
        task = Task(id="t1", description="test")
        assert task.run_ids == []

    def test_task_run_ids_not_shared(self) -> None:
        """Each task has its own run_ids list."""
        task1 = Task(id="t1", description="test1")
        task2 = Task(id="t2", description="test2")
        task1.run_ids.append("run_1")

        assert "run_1" in task1.run_ids
        assert "run_1" not in task2.run_ids


class TestGenerateTaskId:
    """Tests for generate_task_id function."""

    def test_format(self) -> None:
        """Task ID has correct format."""
        task_id = generate_task_id()
        assert task_id.startswith("task_")
        parts = task_id.split("_")
        assert len(parts) == 4  # task, date, time, suffix

    def test_date_part(self) -> None:
        """Date part is 8 digits."""
        task_id = generate_task_id()
        date_part = task_id.split("_")[1]
        assert len(date_part) == 8
        assert date_part.isdigit()

    def test_time_part(self) -> None:
        """Time part is 6 digits."""
        task_id = generate_task_id()
        time_part = task_id.split("_")[2]
        assert len(time_part) == 6
        assert time_part.isdigit()

    def test_suffix_part(self) -> None:
        """Suffix is 6 alphanumeric characters."""
        task_id = generate_task_id()
        suffix = task_id.split("_")[3]
        assert len(suffix) == 6
        assert suffix.isalnum()

    def test_uniqueness(self) -> None:
        """Generated IDs are unique."""
        ids = [generate_task_id() for _ in range(100)]
        assert len(ids) == len(set(ids))


class TestCreateTask:
    """Tests for create_task factory function."""

    def test_creates_with_description(self) -> None:
        """Creates task with description."""
        task = create_task("Fix the bug")
        assert task.description == "Fix the bug"
        assert task.state == TaskState.QUEUED

    def test_generates_id(self) -> None:
        """Creates task with generated ID."""
        task = create_task("Test task")
        assert task.id.startswith("task_")

    def test_dry_run_flag(self) -> None:
        """Respects dry_run flag."""
        task = create_task("Test", dry_run=True)
        assert task.dry_run is True

    def test_verbose_flag(self) -> None:
        """Respects verbose flag."""
        task = create_task("Test", verbose=True)
        assert task.verbose is True

    def test_created_at_set(self) -> None:
        """Sets created_at timestamp."""
        before = datetime.now(timezone.utc)
        task = create_task("Test")
        after = datetime.now(timezone.utc)

        assert before <= task.created_at <= after
