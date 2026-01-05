"""Task state definitions and task data structures."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class TaskState(Enum):
    """Task execution states as defined in task-lifecycle.md."""

    QUEUED = "QUEUED"  # Waiting for prior tasks to complete
    RUNNING = "RUNNING"  # Editor actively working on task
    SUCCESS = "SUCCESS"  # Verifier returned PASS; summary generated
    CANCELLED = "CANCELLED"  # User cancelled mid-execution
    STUCK = "STUCK"  # Hard stop reached (12 verify loops)
    INFRA_ERROR = "INFRA_ERROR"  # Infrastructure failure


# Terminal states - task cannot transition from these
TERMINAL_STATES = frozenset({
    TaskState.SUCCESS,
    TaskState.CANCELLED,
    TaskState.STUCK,
    TaskState.INFRA_ERROR,
})


def is_terminal_state(state: TaskState) -> bool:
    """Check if a state is terminal (no further transitions possible)."""
    return state in TERMINAL_STATES


@dataclass
class Task:
    """Represents a task in the system.

    Attributes:
        id: Unique task identifier (auto-generated)
        description: Free-form natural language task description
        state: Current task state
        created_at: UTC timestamp when task was created
        started_at: UTC timestamp when task started running (None if not started)
        completed_at: UTC timestamp when task completed (None if not completed)
        dry_run: Whether this is a dry-run task
        verbose: Whether verbose output is enabled
        run_ids: List of verification run IDs from this task
        current_attempt: Current verification attempt number (1-based)
        summary: Success summary (set on SUCCESS)
        error_message: Error message (set on failure states)
    """

    id: str
    description: str
    state: TaskState = TaskState.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    dry_run: bool = False
    verbose: bool = False
    run_ids: list[str] = field(default_factory=list)
    current_attempt: int = 0
    summary: str | None = None
    error_message: str | None = None

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return is_terminal_state(self.state)

    def can_cancel(self) -> bool:
        """Check if task can be cancelled."""
        return self.state in {TaskState.QUEUED, TaskState.RUNNING}

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return {
            "id": self.id,
            "description": self.description,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "dry_run": self.dry_run,
            "verbose": self.verbose,
            "run_ids": self.run_ids,
            "current_attempt": self.current_attempt,
            "summary": self.summary,
            "error_message": self.error_message,
        }


def generate_task_id() -> str:
    """Generate a unique task ID.

    Format: task_{YYYYMMDD}_{HHMMSS}_{random6chars}
    Uses UTC timezone.
    """
    import random
    import string

    now = datetime.now(UTC)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"task_{timestamp}_{suffix}"


def create_task(
    description: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> Task:
    """Create a new task with generated ID.

    Args:
        description: Free-form natural language task description
        dry_run: Whether this is a dry-run task
        verbose: Whether verbose output is enabled

    Returns:
        New Task instance in QUEUED state
    """
    return Task(
        id=generate_task_id(),
        description=description,
        dry_run=dry_run,
        verbose=verbose,
    )
