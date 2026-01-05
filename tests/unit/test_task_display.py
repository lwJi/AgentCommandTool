"""Unit tests for task display module."""

import pytest
from io import StringIO
from datetime import datetime, timezone

from rich.console import Console

from act.task.state import Task, TaskState, create_task
from act.task.display import (
    Milestone,
    StatusMessage,
    StatusDisplay,
    STATE_STYLES,
    MILESTONE_ICONS,
    create_status_display,
)


@pytest.fixture
def console() -> Console:
    """Create a console that captures output."""
    return Console(file=StringIO(), force_terminal=True, width=120)


@pytest.fixture
def display(console: Console) -> StatusDisplay:
    """Create a status display with test console."""
    return StatusDisplay(console=console, verbose=False)


@pytest.fixture
def verbose_display(console: Console) -> StatusDisplay:
    """Create a verbose status display."""
    return StatusDisplay(console=console, verbose=True)


def get_output(console: Console) -> str:
    """Get captured console output."""
    file = console.file
    assert isinstance(file, StringIO)
    return file.getvalue()


class TestMilestone:
    """Tests for Milestone enum."""

    def test_all_milestones_have_values(self) -> None:
        """All milestones have string values."""
        for milestone in Milestone:
            assert isinstance(milestone.value, str)
            assert len(milestone.value) > 0

    def test_key_milestones_defined(self) -> None:
        """Key milestones are defined."""
        assert Milestone.TASK_STARTED.value == "Task started"
        assert Milestone.ANALYZING_CODEBASE.value == "Analyzing codebase..."
        assert Milestone.RUNNING_VERIFICATION.value == "Running verification..."
        assert Milestone.TASK_SUCCESS.value == "Task completed successfully"

    def test_all_milestones_have_icons(self) -> None:
        """All milestones have icons defined."""
        for milestone in Milestone:
            assert milestone in MILESTONE_ICONS


class TestStatusMessage:
    """Tests for StatusMessage dataclass."""

    def test_creation_minimal(self) -> None:
        """Create with minimal arguments."""
        msg = StatusMessage(
            milestone=Milestone.TASK_STARTED,
            message="Test message",
        )
        assert msg.milestone == Milestone.TASK_STARTED
        assert msg.message == "Test message"
        assert msg.detail is None
        assert msg.timestamp is not None

    def test_creation_with_detail(self) -> None:
        """Create with detail."""
        msg = StatusMessage(
            milestone=Milestone.VERIFICATION_FAILED,
            message="Test failed",
            detail="Error details here",
        )
        assert msg.detail == "Error details here"

    def test_timestamp_auto_generated(self) -> None:
        """Timestamp is auto-generated."""
        before = datetime.now(timezone.utc)
        msg = StatusMessage(milestone=Milestone.TASK_STARTED, message="Test")
        after = datetime.now(timezone.utc)

        assert before <= msg.timestamp <= after


class TestStateStyles:
    """Tests for state style mapping."""

    def test_all_states_have_styles(self) -> None:
        """All task states have styles defined."""
        for state in TaskState:
            assert state in STATE_STYLES

    def test_success_style_green(self) -> None:
        """SUCCESS state has green style."""
        style = STATE_STYLES[TaskState.SUCCESS]
        assert style.color is not None
        assert style.color.name == "green"

    def test_error_styles_red(self) -> None:
        """Error states have red styles."""
        for state in [TaskState.STUCK, TaskState.INFRA_ERROR]:
            style = STATE_STYLES[state]
            assert style.color is not None
            assert style.color.name == "red"


class TestStatusDisplayBasic:
    """Tests for basic StatusDisplay operations."""

    def test_create_with_defaults(self) -> None:
        """Create display with defaults."""
        display = StatusDisplay()
        assert display.console is not None
        assert display.verbose is False

    def test_create_with_verbose(self) -> None:
        """Create display with verbose flag."""
        display = StatusDisplay(verbose=True)
        assert display.verbose is True

    def test_set_task(self, display: StatusDisplay) -> None:
        """Can set current task."""
        task = create_task("Test")
        display.set_task(task)
        assert display._current_task == task

    def test_clear(self, display: StatusDisplay) -> None:
        """Clear resets state."""
        task = create_task("Test")
        display.set_task(task)
        display.emit(Milestone.TASK_STARTED)

        display.clear()

        assert display._current_task is None
        assert len(display._messages) == 0


class TestStatusDisplayEmit:
    """Tests for status emission."""

    def test_emit_adds_message(self, display: StatusDisplay) -> None:
        """Emit adds message to list."""
        display.emit(Milestone.TASK_STARTED)
        assert len(display._messages) == 1
        assert display._messages[0].milestone == Milestone.TASK_STARTED

    def test_emit_with_detail(self, display: StatusDisplay) -> None:
        """Emit stores detail."""
        display.emit(Milestone.VERIFICATION_FAILED, "Error info")
        assert display._messages[0].detail == "Error info"

    def test_emit_prints_to_console(self, display: StatusDisplay, console: Console) -> None:
        """Emit prints to console."""
        display.emit(Milestone.TASK_STARTED)
        output = get_output(console)
        assert "Task started" in output

    def test_emit_prints_icon(self, display: StatusDisplay, console: Console) -> None:
        """Emit includes icon."""
        display.emit(Milestone.TASK_STARTED)
        output = get_output(console)
        assert MILESTONE_ICONS[Milestone.TASK_STARTED] in output

    def test_emit_callback(self, display: StatusDisplay) -> None:
        """Emit triggers callbacks."""
        received: list[StatusMessage] = []

        def callback(msg: StatusMessage) -> None:
            received.append(msg)

        display.add_callback(callback)
        display.emit(Milestone.TASK_STARTED)

        assert len(received) == 1
        assert received[0].milestone == Milestone.TASK_STARTED

    def test_remove_callback(self, display: StatusDisplay) -> None:
        """Can remove callbacks."""
        received: list[StatusMessage] = []

        def callback(msg: StatusMessage) -> None:
            received.append(msg)

        display.add_callback(callback)
        display.remove_callback(callback)
        display.emit(Milestone.TASK_STARTED)

        assert len(received) == 0


class TestStatusDisplayVerbose:
    """Tests for verbose mode."""

    def test_verbose_shows_timestamp(self, verbose_display: StatusDisplay, console: Console) -> None:
        """Verbose mode shows timestamps."""
        verbose_display.emit(Milestone.TASK_STARTED)
        output = get_output(console)
        # Should contain HH:MM:SS format
        assert ":" in output

    def test_verbose_shows_detail(self, verbose_display: StatusDisplay, console: Console) -> None:
        """Verbose mode shows detail."""
        verbose_display.emit(Milestone.VERIFICATION_FAILED, "Detailed error info")
        output = get_output(console)
        assert "Detailed error info" in output

    def test_non_verbose_hides_detail(self, display: StatusDisplay, console: Console) -> None:
        """Non-verbose hides detail."""
        display.emit(Milestone.VERIFICATION_FAILED, "Hidden detail")
        output = get_output(console)
        assert "Hidden detail" not in output


class TestStatusDisplayAttempt:
    """Tests for attempt counter display."""

    def test_emit_attempt(self, display: StatusDisplay, console: Console) -> None:
        """Emit attempt shows counter."""
        display.emit_attempt(3, 12)
        output = get_output(console)
        # ANSI codes may split the text, so check for parts
        assert "Attempt" in output
        assert "3" in output
        assert "12" in output

    def test_emit_attempt_default_total(self, display: StatusDisplay, console: Console) -> None:
        """Emit attempt uses default total."""
        display.emit_attempt(5)
        output = get_output(console)
        # ANSI codes may split the text, so check for parts
        assert "Attempt" in output
        assert "5" in output
        assert "12" in output


class TestStatusDisplayTaskStatus:
    """Tests for task status panel."""

    def test_show_task_status(self, display: StatusDisplay, console: Console) -> None:
        """Show task status displays panel."""
        task = create_task("Test task description")
        task.state = TaskState.RUNNING
        task.current_attempt = 5

        display.show_task_status(task)
        output = get_output(console)

        assert task.id in output
        assert "RUNNING" in output
        assert "5/12" in output

    def test_show_task_status_dry_run(self, display: StatusDisplay, console: Console) -> None:
        """Show task status indicates dry-run."""
        task = create_task("Test", dry_run=True)
        display.show_task_status(task)
        output = get_output(console)

        assert "Dry-run" in output


class TestStatusDisplayQueue:
    """Tests for queue display."""

    def test_show_queue_empty(self, display: StatusDisplay, console: Console) -> None:
        """Show empty queue."""
        display.show_queue([])
        output = get_output(console)
        assert "empty" in output.lower()

    def test_show_queue_with_tasks(self, display: StatusDisplay, console: Console) -> None:
        """Show queue with tasks."""
        tasks = [
            (1, create_task("First task")),
            (2, create_task("Second task")),
        ]
        display.show_queue(tasks)
        output = get_output(console)

        assert "First task" in output
        assert "Second task" in output


class TestStatusDisplayResults:
    """Tests for result displays."""

    def test_show_success(self, display: StatusDisplay, console: Console) -> None:
        """Show success message."""
        task = create_task("Test")
        task.state = TaskState.SUCCESS

        display.show_success(task, "Task completed successfully!")
        output = get_output(console)

        assert "Successfully" in output or "successfully" in output

    def test_show_stuck(self, display: StatusDisplay, console: Console) -> None:
        """Show stuck message."""
        task = create_task("Test")
        task.state = TaskState.STUCK

        display.show_stuck(task, "agent/stuck_report.md")
        output = get_output(console)

        assert "stuck" in output.lower()
        assert "stuck_report.md" in output

    def test_show_infra_error(self, display: StatusDisplay, console: Console) -> None:
        """Show infrastructure error."""
        task = create_task("Test")
        task.state = TaskState.INFRA_ERROR

        display.show_infra_error(task, "Docker unavailable")
        output = get_output(console)

        assert "Docker unavailable" in output


class TestStatusDisplayDryRun:
    """Tests for dry-run display."""

    def test_show_dry_run_diff(self, display: StatusDisplay, console: Console) -> None:
        """Show dry-run diff."""
        diff = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new"
        display.show_dry_run_diff(diff)
        output = get_output(console)

        assert "file.py" in output


class TestStatusDisplayVerboseLog:
    """Tests for verbose log display."""

    def test_verbose_log_shown_in_verbose_mode(self, verbose_display: StatusDisplay, console: Console) -> None:
        """Verbose log shown in verbose mode."""
        verbose_display.show_verbose_log("Build Output", "Line 1\nLine 2")
        output = get_output(console)

        assert "Build Output" in output
        assert "Line 1" in output

    def test_verbose_log_hidden_in_normal_mode(self, display: StatusDisplay, console: Console) -> None:
        """Verbose log hidden in normal mode."""
        display.show_verbose_log("Build Output", "Should not appear")
        output = get_output(console)

        assert "Build Output" not in output


class TestCreateStatusDisplay:
    """Tests for factory function."""

    def test_create_status_display_default(self) -> None:
        """Create with defaults."""
        display = create_status_display()
        assert isinstance(display, StatusDisplay)
        assert display.verbose is False

    def test_create_status_display_verbose(self) -> None:
        """Create with verbose."""
        display = create_status_display(verbose=True)
        assert display.verbose is True

    def test_create_status_display_custom_console(self, console: Console) -> None:
        """Create with custom console."""
        display = create_status_display(console=console)
        assert display.console is console
