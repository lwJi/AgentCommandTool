"""CLI entry point for AgentCommandTool."""

import click

from act import __version__


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
    """Submit and run a task."""
    click.echo(f"Task: {task}")
    if dry_run:
        click.echo("Mode: dry-run (preview only)")
    if verbose:
        click.echo("Verbose output enabled")
    click.echo("Not yet implemented")


@main.command()
def status() -> None:
    """Show current task status."""
    click.echo("No task currently running")


@main.command()
def queue() -> None:
    """List queued tasks."""
    click.echo("Queue is empty")


@main.command()
@click.option("--id", "task_id", type=int, help="Cancel queued task by position")
def cancel(task_id: int | None) -> None:
    """Cancel running or queued task."""
    if task_id:
        click.echo(f"Cancelling queued task at position {task_id}")
    else:
        click.echo("Cancelling current task")
    click.echo("Not yet implemented")


if __name__ == "__main__":
    main()
