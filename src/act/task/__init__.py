"""Task lifecycle management and queue handling.

This module provides:
- Task state machine (QUEUED → RUNNING → terminal states)
- FIFO task queue with sequential execution
- Rich TUI status display with spinners and progress
- Task runner for execution orchestration
- Stuck report loading for future retry
"""

# Task state and types
# Status display
from act.task.display import (
    MILESTONE_ICONS,
    STATE_STYLES,
    Milestone,
    StatusDisplay,
    StatusMessage,
    create_status_display,
)

# Task queue
from act.task.queue import (
    InvalidTaskStateError,
    QueuedTask,
    TaskNotFoundError,
    TaskQueue,
    TaskQueueError,
    get_task_queue,
    reset_task_queue,
)

# Retry context
from act.task.retry import (
    RetryContext,
    RetryContextError,
    clear_retry_context,
    extract_run_ids_from_report,
    get_artifact_paths_for_retry,
    get_retry_summary,
    load_retry_context,
    should_show_retry_context,
)

# Task runner
from act.task.runner import (
    EditorProtocol,
    TaskCancelledError,
    TaskResult,
    TaskRunner,
    TaskRunnerError,
    VerifierProtocol,
    create_task_runner,
)
from act.task.state import (
    TERMINAL_STATES,
    Task,
    TaskState,
    create_task,
    generate_task_id,
    is_terminal_state,
)

__all__ = [
    # State
    "TaskState",
    "Task",
    "TERMINAL_STATES",
    "is_terminal_state",
    "generate_task_id",
    "create_task",
    # Queue
    "TaskQueue",
    "TaskQueueError",
    "TaskNotFoundError",
    "InvalidTaskStateError",
    "QueuedTask",
    "get_task_queue",
    "reset_task_queue",
    # Display
    "Milestone",
    "StatusMessage",
    "StatusDisplay",
    "STATE_STYLES",
    "MILESTONE_ICONS",
    "create_status_display",
    # Runner
    "TaskRunner",
    "TaskRunnerError",
    "TaskCancelledError",
    "TaskResult",
    "EditorProtocol",
    "VerifierProtocol",
    "create_task_runner",
    # Retry
    "RetryContext",
    "RetryContextError",
    "load_retry_context",
    "get_retry_summary",
    "should_show_retry_context",
    "clear_retry_context",
    "extract_run_ids_from_report",
    "get_artifact_paths_for_retry",
]
