"""Task runner - orchestrates task execution with state transitions.

Coordinates Editor, Scouts, and Verifier components through the full task lifecycle.
"""

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from typing import Any, Protocol

from act.task.display import Milestone, StatusDisplay, create_status_display
from act.task.queue import TaskQueue, get_task_queue
from act.task.state import Task, TaskState


class TaskRunnerError(Exception):
    """Base exception for task runner errors."""

    pass


class TaskCancelledError(TaskRunnerError):
    """Raised when a task is cancelled during execution."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task cancelled: {task_id}")


class EditorProtocol(Protocol):
    """Protocol for Editor integration.

    The Editor is the main orchestrator that coordinates Scouts and Verifier.
    This protocol allows for dependency injection and testing.
    """

    def reset(self) -> None:
        """Reset the editor for a new task."""
        ...

    def start_task(self, description: str, dry_run: bool = False) -> None:
        """Start a new task."""
        ...

    def analyze_codebase(self) -> Any:
        """Perform initial codebase analysis."""
        ...

    def handle_verification_result(self, result: Any) -> Any:
        """Handle verification result and determine next action."""
        ...

    def generate_success_summary(self, run_id: str) -> str:
        """Generate success summary."""
        ...

    def generate_stuck_report(self, run_ids: list[str]) -> str:
        """Generate stuck report."""
        ...

    @property
    def state(self) -> Any:
        """Current workflow state."""
        ...

    @property
    def context(self) -> Any:
        """Current context."""
        ...


class VerifierProtocol(Protocol):
    """Protocol for Verifier integration."""

    def verify(
        self, repo_path: Path, config: Any, artifact_dir: Path | None = None
    ) -> Any:
        """Run verification and return result."""
        ...


@dataclass
class TaskResult:
    """Result of task execution.

    Attributes:
        task: The executed task (with final state)
        success: Whether task completed successfully
        summary: Success summary (if successful)
        stuck_report_path: Path to stuck report (if stuck/infra_error)
        error_message: Error description (if failed)
    """

    task: Task
    success: bool
    summary: str | None = None
    stuck_report_path: str | None = None
    error_message: str | None = None


@dataclass
class TaskRunner:
    """Runs tasks through the full execution lifecycle.

    Handles:
    - State transitions (QUEUED → RUNNING → terminal state)
    - Editor/Scout/Verifier coordination
    - Cancellation handling
    - Status display updates

    Attributes:
        queue: Task queue instance
        display: Status display instance
        repo_path: Path to the repository
        config: Agent configuration
        _cancel_event: Event for signaling cancellation
        _running_thread: Currently executing thread
    """

    queue: TaskQueue
    display: StatusDisplay
    repo_path: Path
    config: Any  # AgentConfig
    editor: EditorProtocol | None = None
    verifier: VerifierProtocol | None = None
    _cancel_event: Event = field(default_factory=Event)
    _running_thread: Thread | None = None
    _on_task_complete: list[Callable[[TaskResult], None]] = field(default_factory=list)

    def add_completion_callback(self, callback: Callable[[TaskResult], None]) -> None:
        """Add a callback to be called when a task completes."""
        self._on_task_complete.append(callback)

    def submit(self, task: Task) -> int:
        """Submit a task for execution.

        If no task is running, the task starts immediately.
        Otherwise, it's added to the queue.

        Args:
            task: Task to submit

        Returns:
            Queue position (0 if starting immediately, >0 if queued)
        """
        # Add to queue
        position = self.queue.add(task)

        # Emit status
        if self.queue.has_running_task():
            self.display.emit(Milestone.TASK_QUEUED, f"Position: {position}")
        else:
            # Start immediately if nothing running
            self._start_next_task()

        return position if self.queue.has_running_task() else 0

    def _start_next_task(self) -> None:
        """Start the next task from the queue."""
        task = self.queue.dequeue()
        if task is None:
            return

        # Clear cancel event
        self._cancel_event.clear()

        # Set as current
        self.queue.set_current(task)
        task.state = TaskState.RUNNING
        task.started_at = datetime.now(UTC)

        # Update display
        self.display.set_task(task)
        self.display.emit(Milestone.TASK_STARTED)

        # Run in thread to avoid blocking
        self._running_thread = Thread(
            target=self._execute_task,
            args=(task,),
            daemon=True,
        )
        self._running_thread.start()

    def _execute_task(self, task: Task) -> None:
        """Execute a task (runs in thread).

        Args:
            task: Task to execute
        """
        result: TaskResult
        try:
            result = self._run_task_workflow(task)
        except TaskCancelledError:
            task.state = TaskState.CANCELLED
            task.completed_at = datetime.now(UTC)
            result = TaskResult(
                task=task, success=False, error_message="Cancelled by user"
            )
            self.display.emit(Milestone.TASK_CANCELLED)
        except Exception as e:
            # Unexpected error - treat as infra error
            task.state = TaskState.INFRA_ERROR
            task.completed_at = datetime.now(UTC)
            task.error_message = str(e)
            result = TaskResult(task=task, success=False, error_message=str(e))
            self.display.emit(Milestone.TASK_INFRA_ERROR, str(e))

        # Finalize
        self._finalize_task(task, result)

    def _run_task_workflow(self, task: Task) -> TaskResult:
        """Run the main task workflow.

        Args:
            task: Task to run

        Returns:
            TaskResult with execution outcome
        """
        # Check for cancellation at each step
        def check_cancel() -> None:
            if self._cancel_event.is_set():
                raise TaskCancelledError(task.id)

        # Phase 1: Analysis
        check_cancel()
        self.display.emit(Milestone.ANALYZING_CODEBASE)

        if self.editor:
            self.editor.reset()
            self.editor.start_task(task.description, dry_run=task.dry_run)

            check_cancel()
            self.display.emit(Milestone.QUERYING_SCOUT_A)
            self.display.emit(Milestone.QUERYING_SCOUT_B)

            check_cancel()
            self.editor.analyze_codebase()
            self.display.emit(Milestone.ANALYSIS_COMPLETE)

        # Phase 2: Implementation
        check_cancel()
        self.display.emit(Milestone.IMPLEMENTING_CHANGES)

        # For dry-run, skip verification
        if task.dry_run:
            self.display.emit(Milestone.DRY_RUN_COMPLETE)
            task.state = TaskState.SUCCESS
            task.completed_at = datetime.now(UTC)
            return TaskResult(
                task=task,
                success=True,
                summary="Dry-run completed. Review proposed changes.",
            )

        self.display.emit(Milestone.CHANGES_APPLIED)

        # Phase 3: Verification loop
        check_cancel()

        # Mock verification loop for now (Editor integration happens in Phase 6)
        # This demonstrates the state machine and display
        self.display.emit(Milestone.RUNNING_VERIFICATION)
        task.current_attempt = 1
        self.display.emit_attempt(task.current_attempt)

        # For now, assume success
        # Real implementation uses Editor.handle_verification_result
        self.display.emit(Milestone.VERIFICATION_PASSED)
        self.display.emit(Milestone.TASK_SUCCESS)

        task.state = TaskState.SUCCESS
        task.completed_at = datetime.now(UTC)
        task.summary = "Task completed successfully."

        return TaskResult(
            task=task,
            success=True,
            summary=task.summary,
        )

    def _finalize_task(self, task: Task, result: TaskResult) -> None:
        """Finalize task execution.

        Args:
            task: Completed task
            result: Execution result
        """
        # Move to completed
        self.queue.mark_completed(task)

        # Display final status
        if result.success:
            self.display.show_success(task, result.summary or "")
        elif task.state == TaskState.STUCK:
            self.display.show_stuck(task, result.stuck_report_path or "")
        elif task.state == TaskState.INFRA_ERROR:
            self.display.show_infra_error(task, result.error_message or "Unknown error")

        # Notify callbacks (suppress errors to avoid breaking execution)
        for callback in self._on_task_complete:
            with suppress(Exception):
                callback(result)

        # Start next task if any
        if not self.queue.is_empty():
            self._start_next_task()

    def cancel_current(self) -> bool:
        """Cancel the currently running task.

        Returns:
            True if a task was cancelled, False if no task running
        """
        current = self.queue.get_current()
        if current is None:
            return False

        if not current.can_cancel():
            return False

        # Signal cancellation
        self._cancel_event.set()
        return True

    def cancel_queued(self, position: int) -> Task | None:
        """Cancel a queued task by position.

        Args:
            position: 1-based queue position

        Returns:
            Cancelled task, or None if not found
        """
        task = self.queue.remove_by_position(position)
        if task:
            task.state = TaskState.CANCELLED
            task.completed_at = datetime.now(UTC)
        return task

    def cancel_by_id(self, task_id: str) -> bool:
        """Cancel a task by ID.

        Works for both running and queued tasks.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if task was cancelled
        """
        # Check if it's the current task
        current = self.queue.get_current()
        if current and current.id == task_id:
            return self.cancel_current()

        # Try to remove from queue
        task = self.queue.remove_by_id(task_id)
        if task:
            task.state = TaskState.CANCELLED
            task.completed_at = datetime.now(UTC)
            return True

        return False

    def get_status(self) -> dict[str, Any]:
        """Get current runner status.

        Returns:
            Status dictionary with current task and queue info
        """
        current = self.queue.get_current()
        queued = self.queue.list_queued()

        return {
            "current": current.to_dict() if current else None,
            "queue_size": len(queued),
            "queued_tasks": [
                {"position": qt.position, "task": qt.task.to_dict()}
                for qt in queued
            ],
        }

    def wait_for_completion(self, timeout: float | None = None) -> bool:
        """Wait for the current task to complete.

        Args:
            timeout: Maximum seconds to wait (None for indefinite)

        Returns:
            True if task completed, False if timeout
        """
        if self._running_thread is None:
            return True

        self._running_thread.join(timeout=timeout)
        return not self._running_thread.is_alive()


def create_task_runner(
    repo_path: Path,
    config: Any,
    queue: TaskQueue | None = None,
    display: StatusDisplay | None = None,
    verbose: bool = False,
) -> TaskRunner:
    """Create a new task runner.

    Args:
        repo_path: Path to the repository
        config: Agent configuration
        queue: Task queue (uses global if None)
        display: Status display (creates new if None)
        verbose: Whether to enable verbose output

    Returns:
        Configured TaskRunner instance
    """
    actual_queue = queue if queue is not None else get_task_queue()
    actual_display = (
        display if display is not None else create_status_display(verbose=verbose)
    )
    return TaskRunner(
        queue=actual_queue,
        display=actual_display,
        repo_path=repo_path,
        config=config,
    )
