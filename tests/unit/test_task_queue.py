"""Unit tests for task queue module."""

import pytest
from datetime import datetime, timezone

from act.task.state import Task, TaskState, create_task
from act.task.queue import (
    TaskQueue,
    TaskQueueError,
    TaskNotFoundError,
    InvalidTaskStateError,
    QueuedTask,
    get_task_queue,
    reset_task_queue,
)


@pytest.fixture
def queue() -> TaskQueue:
    """Create a fresh task queue."""
    return TaskQueue()


@pytest.fixture
def sample_tasks() -> list[Task]:
    """Create sample tasks for testing."""
    return [
        create_task("Task A"),
        create_task("Task B"),
        create_task("Task C"),
    ]


class TestTaskQueueExceptions:
    """Tests for queue exception classes."""

    def test_task_not_found_error(self) -> None:
        """TaskNotFoundError has task_id attribute."""
        error = TaskNotFoundError("task_123")
        assert error.task_id == "task_123"
        assert "task_123" in str(error)

    def test_invalid_task_state_error(self) -> None:
        """InvalidTaskStateError has attributes."""
        error = InvalidTaskStateError("task_456", TaskState.RUNNING, "cancel")
        assert error.task_id == "task_456"
        assert error.state == TaskState.RUNNING
        assert error.operation == "cancel"


class TestQueuedTask:
    """Tests for QueuedTask dataclass."""

    def test_queued_task_creation(self) -> None:
        """QueuedTask holds task and position."""
        task = create_task("Test")
        qt = QueuedTask(task=task, position=3)
        assert qt.task == task
        assert qt.position == 3


class TestTaskQueueBasic:
    """Tests for basic queue operations."""

    def test_empty_queue(self, queue: TaskQueue) -> None:
        """New queue is empty."""
        assert queue.is_empty()
        assert queue.size() == 0
        assert len(queue) == 0

    def test_add_task(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Adding a task increases size."""
        pos = queue.add(sample_tasks[0])
        assert pos == 1
        assert queue.size() == 1
        assert not queue.is_empty()

    def test_add_multiple_tasks(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Multiple tasks get sequential positions."""
        for i, task in enumerate(sample_tasks):
            pos = queue.add(task)
            assert pos == i + 1

        assert queue.size() == 3

    def test_peek_empty(self, queue: TaskQueue) -> None:
        """Peek on empty queue returns None."""
        assert queue.peek() is None

    def test_peek_returns_first(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Peek returns first task without removing."""
        queue.add(sample_tasks[0])
        queue.add(sample_tasks[1])

        peeked = queue.peek()
        assert peeked == sample_tasks[0]
        assert queue.size() == 2  # Not removed

    def test_dequeue_empty(self, queue: TaskQueue) -> None:
        """Dequeue on empty queue returns None."""
        assert queue.dequeue() is None

    def test_dequeue_fifo(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Dequeue returns tasks in FIFO order."""
        for task in sample_tasks:
            queue.add(task)

        assert queue.dequeue() == sample_tasks[0]
        assert queue.dequeue() == sample_tasks[1]
        assert queue.dequeue() == sample_tasks[2]
        assert queue.dequeue() is None


class TestTaskQueueCurrent:
    """Tests for current task management."""

    def test_no_current_initially(self, queue: TaskQueue) -> None:
        """No current task initially."""
        assert queue.get_current() is None
        assert not queue.has_running_task()

    def test_set_current(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Can set current task."""
        queue.set_current(sample_tasks[0])
        assert queue.get_current() == sample_tasks[0]
        assert queue.has_running_task()

    def test_clear_current(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Can clear current task."""
        queue.set_current(sample_tasks[0])
        queue.set_current(None)
        assert queue.get_current() is None
        assert not queue.has_running_task()

    def test_len_includes_current(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """len() includes current task."""
        queue.add(sample_tasks[0])
        queue.set_current(sample_tasks[1])
        assert len(queue) == 2


class TestTaskQueueListing:
    """Tests for queue listing operations."""

    def test_list_queued_empty(self, queue: TaskQueue) -> None:
        """List queued on empty returns empty list."""
        assert queue.list_queued() == []

    def test_list_queued_positions(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """List queued returns correct positions."""
        for task in sample_tasks:
            queue.add(task)

        queued = queue.list_queued()
        assert len(queued) == 3
        assert queued[0].position == 1
        assert queued[0].task == sample_tasks[0]
        assert queued[1].position == 2
        assert queued[2].position == 3

    def test_get_by_position_valid(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Get by position returns correct task."""
        for task in sample_tasks:
            queue.add(task)

        assert queue.get_by_position(1) == sample_tasks[0]
        assert queue.get_by_position(2) == sample_tasks[1]
        assert queue.get_by_position(3) == sample_tasks[2]

    def test_get_by_position_invalid(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Get by position with invalid position returns None."""
        queue.add(sample_tasks[0])

        assert queue.get_by_position(0) is None
        assert queue.get_by_position(2) is None
        assert queue.get_by_position(-1) is None

    def test_get_by_id_in_queue(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Get by ID finds task in queue."""
        for task in sample_tasks:
            queue.add(task)

        found = queue.get_by_id(sample_tasks[1].id)
        assert found == sample_tasks[1]

    def test_get_by_id_current(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Get by ID finds current task."""
        queue.set_current(sample_tasks[0])
        found = queue.get_by_id(sample_tasks[0].id)
        assert found == sample_tasks[0]

    def test_get_by_id_not_found(self, queue: TaskQueue) -> None:
        """Get by ID returns None if not found."""
        assert queue.get_by_id("nonexistent") is None


class TestTaskQueueRemoval:
    """Tests for task removal operations."""

    def test_remove_by_position(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Remove by position works correctly."""
        for task in sample_tasks:
            queue.add(task)

        removed = queue.remove_by_position(2)
        assert removed == sample_tasks[1]
        assert queue.size() == 2

    def test_remove_by_position_shifts(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Remove by position shifts remaining tasks."""
        for task in sample_tasks:
            queue.add(task)

        queue.remove_by_position(1)

        # Position 1 should now be task B
        assert queue.get_by_position(1) == sample_tasks[1]
        assert queue.get_by_position(2) == sample_tasks[2]

    def test_remove_by_position_invalid(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Remove by invalid position returns None."""
        queue.add(sample_tasks[0])

        assert queue.remove_by_position(0) is None
        assert queue.remove_by_position(5) is None
        assert queue.size() == 1  # Unchanged

    def test_remove_by_id(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Remove by ID works correctly."""
        for task in sample_tasks:
            queue.add(task)

        removed = queue.remove_by_id(sample_tasks[1].id)
        assert removed == sample_tasks[1]
        assert queue.size() == 2

    def test_remove_by_id_not_found(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Remove by ID with unknown ID returns None."""
        queue.add(sample_tasks[0])

        assert queue.remove_by_id("nonexistent") is None
        assert queue.size() == 1


class TestTaskQueueCompleted:
    """Tests for completed task management."""

    def test_mark_completed(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Mark completed adds to completed list."""
        queue.set_current(sample_tasks[0])
        queue.mark_completed(sample_tasks[0])

        completed = queue.get_completed()
        assert len(completed) == 1
        assert completed[0] == sample_tasks[0]

    def test_mark_completed_clears_current(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Mark completed clears current task."""
        queue.set_current(sample_tasks[0])
        queue.mark_completed(sample_tasks[0])

        assert queue.get_current() is None

    def test_get_completed_limit(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Get completed respects limit."""
        for task in sample_tasks:
            queue.mark_completed(task)

        completed = queue.get_completed(limit=2)
        assert len(completed) == 2

    def test_get_completed_order(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Get completed returns most recent first."""
        for task in sample_tasks:
            queue.mark_completed(task)

        completed = queue.get_completed()
        # Most recent first
        assert completed[0] == sample_tasks[2]
        assert completed[2] == sample_tasks[0]

    def test_clear_completed(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Clear completed removes all."""
        for task in sample_tasks:
            queue.mark_completed(task)

        count = queue.clear_completed()
        assert count == 3
        assert queue.get_completed() == []


class TestTaskQueueIteration:
    """Tests for queue iteration."""

    def test_iterate_queued(self, queue: TaskQueue, sample_tasks: list[Task]) -> None:
        """Can iterate over queued tasks."""
        for task in sample_tasks:
            queue.add(task)

        tasks = list(queue)
        assert len(tasks) == 3
        assert tasks[0] == sample_tasks[0]


class TestGlobalQueue:
    """Tests for global queue functions."""

    def test_get_task_queue_singleton(self) -> None:
        """get_task_queue returns same instance."""
        reset_task_queue()  # Start fresh
        q1 = get_task_queue()
        q2 = get_task_queue()
        assert q1 is q2

    def test_reset_task_queue(self) -> None:
        """reset_task_queue creates new instance."""
        reset_task_queue()
        q1 = get_task_queue()
        reset_task_queue()
        q2 = get_task_queue()
        assert q1 is not q2
