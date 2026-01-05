"""CLI entry point for AgentCommandTool.

Provides commands for:
- Running tasks (act run)
- Viewing status (act status)
- Managing queue (act queue)
- Cancelling tasks (act cancel)
"""

import sys
from pathlib import Path

import click
from rich.console import Console

from act import __version__
from act.config import (
    ConfigError,
    load_config,
    load_env_config,
    validate_startup,
)
from act.task import (
    TaskState,
    create_status_display,
    create_task,
    create_task_runner,
    get_retry_summary,
    get_task_queue,
    load_retry_context,
    should_show_retry_context,
)

# Global console for Rich output
console = Console()


def get_repo_path() -> Path:
    """Get the repository path (current working directory)."""
    return Path.cwd()


def validate_environment(repo_path: Path) -> tuple[bool, str | None]:
    """Validate the environment for task execution.

    Returns:
        Tuple of (is_valid, error_message)
    """
    result = validate_startup(repo_path)
    if result.valid:
        return True, None

    # Return error messages from validation
    return False, "; ".join(result.errors)


@click.group()
@click.version_option(version=__version__, prog_name="act")
def main() -> None:
    """AgentCommandTool - A pull-based, editor-centric coding agent."""
    pass


@main.command()
@click.argument("task", required=True)
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed output")
def run(task: str, dry_run: bool, verbose: bool) -> None:
    """Submit and run a task.

    TASK is a free-form natural language description of what you want done.

    Examples:
        act run "Fix the login timeout bug"
        act run --dry-run "Add user authentication"
        act run -v "Refactor the API handlers"
    """
    # Validate task description
    if not task.strip():
        console.print("[red]Error:[/red] Task description cannot be empty")
        sys.exit(1)

    repo_path = get_repo_path()

    # Validate environment
    is_valid, error = validate_environment(repo_path)
    if not is_valid:
        console.print(f"[red]Error:[/red] {error}")
        sys.exit(1)

    # Load configuration
    try:
        config = load_config(repo_path / "agent.yaml")
        _ = load_env_config()  # Validate env config
    except ConfigError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        sys.exit(1)

    # Check for existing stuck report (retry context)
    if should_show_retry_context(repo_path):
        retry_context = load_retry_context(repo_path)
        if retry_context:
            console.print()
            console.print("[yellow]⚠️  Previous stuck report found:[/yellow]")
            console.print(get_retry_summary(retry_context))
            console.print()

    # Create task
    task_obj = create_task(task, dry_run=dry_run, verbose=verbose)

    # Create display and runner
    display = create_status_display(console=console, verbose=verbose)
    runner = create_task_runner(
        repo_path=repo_path,
        config=config,
        display=display,
        verbose=verbose,
    )

    # Submit and run
    try:
        position = runner.submit(task_obj)
        if position > 0:
            console.print(f"[dim]Task queued at position {position}[/dim]")

        # Wait for completion
        runner.wait_for_completion()

        # Exit with appropriate code
        if task_obj.state == TaskState.SUCCESS:
            sys.exit(0)
        elif task_obj.state == TaskState.CANCELLED:
            sys.exit(130)  # Standard "interrupted" exit code
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelling...[/yellow]")
        runner.cancel_current()
        runner.wait_for_completion(timeout=5.0)
        sys.exit(130)


@main.command()
def status() -> None:
    """Show current task status.

    Displays information about the currently running task, if any,
    including state, attempt count, and progress.
    """
    queue = get_task_queue()
    current = queue.get_current()
    display = create_status_display(console=console)

    if current is None:
        console.print("[dim]No task currently running[/dim]")
        return

    display.show_task_status(current)


@main.command()
def queue() -> None:
    """List queued tasks.

    Shows all tasks waiting to be executed, with their positions
    and descriptions.
    """
    task_queue = get_task_queue()
    queued = task_queue.list_queued()
    display = create_status_display(console=console)

    # Also show current task if running
    current = task_queue.get_current()
    if current:
        console.print("[bold]Currently Running:[/bold]")
        display.show_task_status(current)
        console.print()

    if queued:
        console.print("[bold]Queued Tasks:[/bold]")
        display.show_queue([(qt.position, qt.task) for qt in queued])
    else:
        console.print("[dim]No tasks in queue[/dim]")


@main.command()
@click.option("--id", "task_id", type=int, help="Cancel queued task by position")
def cancel(task_id: int | None) -> None:
    """Cancel running or queued task.

    Without --id: Cancels the currently running task.
    With --id N: Cancels the task at queue position N.

    Examples:
        act cancel          # Cancel running task
        act cancel --id 2   # Cancel task at position 2
    """
    task_queue = get_task_queue()

    if task_id is not None:
        # Cancel by position
        task = task_queue.remove_by_position(task_id)
        if task:
            task.state = TaskState.CANCELLED
            console.print(f"[green]Cancelled queued task at position {task_id}[/green]")
            console.print(f"  ID: {task.id}")
            console.print(f"  Description: {task.description[:50]}...")
        else:
            console.print(f"[red]No task found at position {task_id}[/red]")
            sys.exit(1)
    else:
        # Cancel current task
        current = task_queue.get_current()
        if current is None:
            console.print("[dim]No task currently running[/dim]")
            return

        # Note: This sets cancel flag but the runner handles actual cancellation
        console.print(
            f"[yellow]Requesting cancellation of task {current.id}...[/yellow]"
        )
        console.print("[dim]Task will be cancelled at next checkpoint[/dim]")


@main.command()
@click.option("--clear", is_flag=True, help="Clear completed task history")
def history(clear: bool) -> None:
    """Show or clear task history.

    Displays recently completed tasks. Use --clear to remove history.
    """
    task_queue = get_task_queue()

    if clear:
        count = task_queue.clear_completed()
        console.print(f"[green]Cleared {count} completed tasks[/green]")
        return

    completed = task_queue.get_completed(limit=10)
    if not completed:
        console.print("[dim]No completed tasks[/dim]")
        return

    console.print("[bold]Recent Tasks:[/bold]")
    for task in completed:
        state_color = {
            TaskState.SUCCESS: "green",
            TaskState.CANCELLED: "yellow",
            TaskState.STUCK: "red",
            TaskState.INFRA_ERROR: "red",
        }.get(task.state, "white")

        if len(task.description) > 40:
            desc = task.description[:40] + "..."
        else:
            desc = task.description
        state_val = task.state.value
        console.print(f"  [{state_color}]{state_val}[/{state_color}] {task.id}: {desc}")


if __name__ == "__main__":
    main()
