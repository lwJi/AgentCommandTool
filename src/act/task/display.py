"""Rich TUI status display for task execution.

Provides real-time status updates with spinners, progress bars, and panels.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn
from rich.style import Style
from rich.table import Table
from rich.text import Text

from act.task.state import Task, TaskState


class Milestone(Enum):
    """Task execution milestones for status updates."""

    # Initial phase
    TASK_QUEUED = "Task queued"
    TASK_STARTED = "Task started"

    # Analysis phase
    ANALYZING_CODEBASE = "Analyzing codebase..."
    QUERYING_SCOUT_A = "Querying Scout A..."
    QUERYING_SCOUT_B = "Querying Scout B..."
    ANALYSIS_COMPLETE = "Analysis complete"

    # Implementation phase
    IMPLEMENTING_CHANGES = "Implementing changes..."
    CHANGES_APPLIED = "Changes applied"

    # Verification phase
    RUNNING_VERIFICATION = "Running verification..."
    VERIFICATION_PASSED = "Verification passed"
    VERIFICATION_FAILED = "Verification failed, debugging..."

    # Debug loop
    REPLANNING = "Replanning strategy..."
    REPLAN_COMPLETE = "New strategy defined"

    # Completion
    TASK_SUCCESS = "Task completed successfully"
    TASK_STUCK = "Task reached hard stop"
    TASK_CANCELLED = "Task cancelled"
    TASK_INFRA_ERROR = "Infrastructure error"

    # Dry-run
    DRY_RUN_COMPLETE = "Dry-run proposal ready"
    APPLYING_DRY_RUN = "Applying dry-run changes..."


@dataclass
class StatusMessage:
    """A status message with timestamp."""

    milestone: Milestone
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    detail: str | None = None


# Style mapping for different states
STATE_STYLES: dict[TaskState, Style] = {
    TaskState.QUEUED: Style(color="yellow"),
    TaskState.RUNNING: Style(color="blue", bold=True),
    TaskState.SUCCESS: Style(color="green", bold=True),
    TaskState.CANCELLED: Style(color="yellow"),
    TaskState.STUCK: Style(color="red", bold=True),
    TaskState.INFRA_ERROR: Style(color="red", bold=True),
}

MILESTONE_ICONS: dict[Milestone, str] = {
    Milestone.TASK_QUEUED: "📋",
    Milestone.TASK_STARTED: "🚀",
    Milestone.ANALYZING_CODEBASE: "🔍",
    Milestone.QUERYING_SCOUT_A: "🗺️",
    Milestone.QUERYING_SCOUT_B: "🔧",
    Milestone.ANALYSIS_COMPLETE: "✅",
    Milestone.IMPLEMENTING_CHANGES: "✏️",
    Milestone.CHANGES_APPLIED: "✅",
    Milestone.RUNNING_VERIFICATION: "🧪",
    Milestone.VERIFICATION_PASSED: "✅",
    Milestone.VERIFICATION_FAILED: "❌",
    Milestone.REPLANNING: "🔄",
    Milestone.REPLAN_COMPLETE: "✅",
    Milestone.TASK_SUCCESS: "🎉",
    Milestone.TASK_STUCK: "🛑",
    Milestone.TASK_CANCELLED: "⏹️",
    Milestone.TASK_INFRA_ERROR: "⚠️",
    Milestone.DRY_RUN_COMPLETE: "📝",
    Milestone.APPLYING_DRY_RUN: "📥",
}


class StatusDisplay:
    """Rich TUI display for task status updates.

    Provides:
    - Live-updating spinner during execution
    - Milestone messages as they occur
    - Progress tracking (attempt X/12)
    - Optional verbose mode with full details
    """

    def __init__(
        self,
        console: Console | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the status display.

        Args:
            console: Rich console (uses default if None)
            verbose: Whether to show detailed output
        """
        self.console = console or Console()
        self.verbose = verbose
        self._messages: list[StatusMessage] = []
        self._current_task: Task | None = None
        self._live: Live | None = None
        self._progress: Progress | None = None
        self._progress_task: TaskID | None = None
        self._callbacks: list[Callable[[StatusMessage], None]] = []

    def add_callback(self, callback: Callable[[StatusMessage], None]) -> None:
        """Add a callback to be called on each status update."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[StatusMessage], None]) -> None:
        """Remove a status callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def set_task(self, task: Task) -> None:
        """Set the current task being displayed."""
        self._current_task = task

    def emit(
        self,
        milestone: Milestone,
        detail: str | None = None,
    ) -> None:
        """Emit a status milestone.

        Args:
            milestone: The milestone event
            detail: Optional additional detail (shown in verbose mode)
        """
        msg = StatusMessage(
            milestone=milestone,
            message=milestone.value,
            detail=detail,
        )
        self._messages.append(msg)

        # Notify callbacks
        for callback in self._callbacks:
            callback(msg)

        # Print to console
        self._print_milestone(msg)

    def emit_attempt(self, current: int, total: int = 12) -> None:
        """Emit an attempt counter update.

        Args:
            current: Current attempt number (1-based)
            total: Total maximum attempts (default 12)
        """
        self.console.print(
            f"[blue]Attempt {current}/{total}[/blue]"
        )

    def _print_milestone(self, msg: StatusMessage) -> None:
        """Print a milestone message to the console."""
        icon = MILESTONE_ICONS.get(msg.milestone, "•")
        text = f"{icon} {msg.message}"

        # Add timestamp in verbose mode
        if self.verbose:
            ts = msg.timestamp.strftime("%H:%M:%S")
            text = f"[dim]{ts}[/dim] {text}"

        # Add detail in verbose mode
        if self.verbose and msg.detail:
            self.console.print(text)
            self.console.print(f"  [dim]{msg.detail}[/dim]")
        else:
            self.console.print(text)

    def start_spinner(self, message: str = "Working...") -> None:
        """Start a spinner for long-running operations."""
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        )
        self._progress_task = self._progress.add_task(message, total=None)
        self._live = Live(self._progress, console=self.console, refresh_per_second=10)
        self._live.start()

    def update_spinner(self, message: str) -> None:
        """Update the spinner message."""
        if self._progress and self._progress_task is not None:
            self._progress.update(self._progress_task, description=message)

    def stop_spinner(self) -> None:
        """Stop the spinner."""
        if self._live:
            self._live.stop()
            self._live = None
        self._progress = None
        self._progress_task = None

    def show_task_status(self, task: Task) -> None:
        """Display a task status panel.

        Args:
            task: Task to display
        """
        style = STATE_STYLES.get(task.state, Style())

        # Build status table
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="bold")
        table.add_column("Value")

        table.add_row("ID", task.id)
        table.add_row("State", Text(task.state.value, style=style))
        desc = task.description[:60]
        if len(task.description) > 60:
            desc += "..."
        table.add_row("Description", desc)

        if task.current_attempt > 0:
            table.add_row("Attempt", f"{task.current_attempt}/12")

        if task.run_ids:
            table.add_row("Run IDs", str(len(task.run_ids)))

        if task.dry_run:
            table.add_row("Mode", "Dry-run")

        panel = Panel(
            table,
            title="[bold]Task Status[/bold]",
            border_style="blue" if task.state == TaskState.RUNNING else "dim",
        )
        self.console.print(panel)

    def show_queue(self, tasks: list[tuple[int, Task]]) -> None:
        """Display the task queue.

        Args:
            tasks: List of (position, task) tuples
        """
        if not tasks:
            self.console.print("[dim]Queue is empty[/dim]")
            return

        table = Table(title="Task Queue", show_header=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("ID", width=30)
        table.add_column("Description", width=50)
        table.add_column("Mode", width=10)

        for pos, task in tasks:
            mode = "dry-run" if task.dry_run else "-"
            desc = task.description[:47]
            if len(task.description) > 47:
                desc += "..."
            table.add_row(str(pos), task.id, desc, mode)

        self.console.print(table)

    def show_success(self, task: Task, summary: str) -> None:
        """Display success message.

        Args:
            task: Completed task
            summary: Success summary text
        """
        panel = Panel(
            summary,
            title="[bold green]✅ Task Completed Successfully[/bold green]",
            border_style="green",
        )
        self.console.print(panel)

    def show_stuck(self, task: Task, report_path: str) -> None:
        """Display stuck/hard-stop message.

        Args:
            task: Stuck task
            report_path: Path to stuck report
        """
        content = Text()
        content.append(
            "Task reached hard stop after 12 verification attempts.\n\n",
            style="bold red",
        )
        content.append("A stuck report has been generated at:\n", style="dim")
        content.append(f"  {report_path}\n\n", style="bold")
        content.append(
            "Review the report for hypotheses and next steps.", style="dim"
        )

        panel = Panel(
            content,
            title="[bold red]🛑 Task Stuck[/bold red]",
            border_style="red",
        )
        self.console.print(panel)

    def show_infra_error(self, task: Task, error_message: str) -> None:
        """Display infrastructure error message.

        Args:
            task: Failed task
            error_message: Error description
        """
        content = Text()
        content.append("An infrastructure error occurred:\n\n", style="bold red")
        content.append(f"  {error_message}\n\n", style="yellow")
        content.append(
            "This is not a code issue - check your infrastructure.", style="dim"
        )

        panel = Panel(
            content,
            title="[bold red]⚠️ Infrastructure Error[/bold red]",
            border_style="red",
        )
        self.console.print(panel)

    def show_dry_run_diff(self, diff: str) -> None:
        """Display dry-run diff output.

        Args:
            diff: Unified diff string
        """
        panel = Panel(
            diff,
            title="[bold]📝 Proposed Changes (Dry-Run)[/bold]",
            border_style="blue",
        )
        self.console.print(panel)

    def show_verbose_log(self, title: str, content: str) -> None:
        """Display verbose log content (only in verbose mode).

        Args:
            title: Log section title
            content: Log content
        """
        if not self.verbose:
            return

        panel = Panel(
            content,
            title=f"[dim]{title}[/dim]",
            border_style="dim",
        )
        self.console.print(panel)

    def clear(self) -> None:
        """Clear the display and messages."""
        self._messages.clear()
        self._current_task = None
        self.stop_spinner()


def create_status_display(
    console: Console | None = None,
    verbose: bool = False,
) -> StatusDisplay:
    """Create a new status display.

    Args:
        console: Rich console (uses default if None)
        verbose: Whether to show detailed output

    Returns:
        New StatusDisplay instance
    """
    return StatusDisplay(console=console, verbose=verbose)
