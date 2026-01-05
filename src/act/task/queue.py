"""FIFO task queue implementation.

Tasks execute sequentially - no concurrency. Strict first-in-first-out ordering.
"""

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from threading import Lock

from act.task.state import Task, TaskState


class TaskQueueError(Exception):
    """Base exception for task queue errors."""

    pass


class TaskNotFoundError(TaskQueueError):
    """Raised when a task is not found in the queue."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class InvalidTaskStateError(TaskQueueError):
    """Raised when task is in invalid state for operation."""

    def __init__(self, task_id: str, state: TaskState, operation: str) -> None:
        self.task_id = task_id
        self.state = state
        self.operation = operation
        super().__init__(
            f"Cannot {operation} task {task_id} in state {state.value}"
        )


@dataclass
class QueuedTask:
    """A task with its position in the queue."""

    task: Task
    position: int


@dataclass
class TaskQueue:
    """FIFO task queue with sequential execution.

    Thread-safe implementation using a lock for all operations.

    Attributes:
        _queue: Internal deque of pending tasks
        _current: Currently running task (None if idle)
        _completed: List of completed tasks (for history)
        _lock: Thread lock for safe concurrent access
    """

    _queue: deque[Task] = field(default_factory=deque)
    _current: Task | None = None
    _completed: list[Task] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def add(self, task: Task) -> int:
        """Add a task to the queue.

        Args:
            task: Task to add (should be in QUEUED state)

        Returns:
            Position in queue (1-based), or 0 if task starts immediately
        """
        with self._lock:
            self._queue.append(task)
            return len(self._queue)

    def size(self) -> int:
        """Get number of tasks waiting in queue."""
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        with self._lock:
            return len(self._queue) == 0

    def peek(self) -> Task | None:
        """Get the next task without removing it."""
        with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    def dequeue(self) -> Task | None:
        """Remove and return the next task from the queue.

        Returns:
            Next task, or None if queue is empty
        """
        with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    def get_current(self) -> Task | None:
        """Get the currently running task."""
        with self._lock:
            return self._current

    def set_current(self, task: Task | None) -> None:
        """Set the currently running task."""
        with self._lock:
            self._current = task

    def list_queued(self) -> list[QueuedTask]:
        """List all queued tasks with their positions.

        Returns:
            List of QueuedTask with 1-based positions
        """
        with self._lock:
            return [
                QueuedTask(task=task, position=i + 1)
                for i, task in enumerate(self._queue)
            ]

    def get_by_position(self, position: int) -> Task | None:
        """Get a queued task by its position (1-based).

        Args:
            position: 1-based position in queue

        Returns:
            Task at position, or None if invalid position
        """
        with self._lock:
            index = position - 1
            if 0 <= index < len(self._queue):
                return self._queue[index]
            return None

    def get_by_id(self, task_id: str) -> Task | None:
        """Get a task by ID (searches current and queue).

        Args:
            task_id: Task ID to find

        Returns:
            Task if found, None otherwise
        """
        with self._lock:
            # Check current task
            if self._current and self._current.id == task_id:
                return self._current
            # Check queue
            for task in self._queue:
                if task.id == task_id:
                    return task
            return None

    def remove_by_position(self, position: int) -> Task | None:
        """Remove a queued task by position (1-based).

        Only works for QUEUED tasks (not current/running).

        Args:
            position: 1-based position in queue

        Returns:
            Removed task, or None if invalid position
        """
        with self._lock:
            index = position - 1
            if 0 <= index < len(self._queue):
                # Convert deque to list, remove, convert back
                queue_list = list(self._queue)
                task = queue_list.pop(index)
                self._queue = deque(queue_list)
                return task
            return None

    def remove_by_id(self, task_id: str) -> Task | None:
        """Remove a queued task by ID.

        Only works for QUEUED tasks (not current/running).

        Args:
            task_id: Task ID to remove

        Returns:
            Removed task, or None if not found
        """
        with self._lock:
            for i, task in enumerate(self._queue):
                if task.id == task_id:
                    queue_list = list(self._queue)
                    task = queue_list.pop(i)
                    self._queue = deque(queue_list)
                    return task
            return None

    def mark_completed(self, task: Task) -> None:
        """Move a task to the completed list.

        Args:
            task: Task to mark as completed
        """
        with self._lock:
            if self._current and self._current.id == task.id:
                self._current = None
            self._completed.append(task)

    def get_completed(self, limit: int = 10) -> list[Task]:
        """Get recently completed tasks.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of completed tasks (most recent first)
        """
        with self._lock:
            return list(reversed(self._completed[-limit:]))

    def clear_completed(self) -> int:
        """Clear the completed task history.

        Returns:
            Number of tasks cleared
        """
        with self._lock:
            count = len(self._completed)
            self._completed.clear()
            return count

    def has_running_task(self) -> bool:
        """Check if a task is currently running."""
        with self._lock:
            return self._current is not None

    def __iter__(self) -> Iterator[Task]:
        """Iterate over queued tasks (not including current)."""
        with self._lock:
            return iter(list(self._queue))

    def __len__(self) -> int:
        """Get total number of tasks (current + queued)."""
        with self._lock:
            count = len(self._queue)
            if self._current:
                count += 1
            return count


# Global singleton queue instance
_global_queue: TaskQueue | None = None


def get_task_queue() -> TaskQueue:
    """Get the global task queue instance.

    Creates the queue on first call.
    """
    global _global_queue
    if _global_queue is None:
        _global_queue = TaskQueue()
    return _global_queue


def reset_task_queue() -> None:
    """Reset the global task queue (primarily for testing)."""
    global _global_queue
    _global_queue = None
