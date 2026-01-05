"""Context snapshot management for agent workflow."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ContextError(Exception):
    """Error related to context operations."""

    pass


class Milestone(Enum):
    """Milestone types that trigger context snapshots.

    Only these milestones trigger snapshot creation:
    - TASK_START: When a new task begins
    - REPLAN: When a REPLAN event occurs (after 3 consecutive failures)
    - TASK_SUCCESS: When a task completes successfully
    """

    TASK_START = "TASK_START"
    REPLAN = "REPLAN"
    TASK_SUCCESS = "TASK_SUCCESS"


@dataclass
class EditorState:
    """Editor state to include in context snapshots."""

    hypothesis: str = ""
    files_modified: list[str] = field(default_factory=list)
    verify_attempts: int = 0
    consecutive_failures: int = 0
    total_verify_loops: int = 0


@dataclass
class ContextSnapshot:
    """A context snapshot containing Scout reports and Editor state."""

    snapshot_number: int
    timestamp: str
    milestone: Milestone
    scout_a_payload: dict[str, Any] | None = None
    scout_b_payload: dict[str, Any] | None = None
    editor_state: EditorState | None = None


CONTEXT_FILE_PATTERN = re.compile(r"^context_(\d{3})\.md$")
CONTEXT_LATEST_NAME = "context_latest.md"


def _get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_next_snapshot_number(agent_dir: Path) -> int:
    """Get the next available snapshot number.

    Args:
        agent_dir: Path to the agent directory.

    Returns:
        Next available snapshot number (starting from 1).
    """
    if not agent_dir.exists():
        return 1

    max_number = 0
    for entry in agent_dir.iterdir():
        if entry.is_file():
            match = CONTEXT_FILE_PATTERN.match(entry.name)
            if match:
                number = int(match.group(1))
                max_number = max(max_number, number)

    return max_number + 1


def _format_payload(payload: dict[str, Any] | None, indent: int = 0) -> str:
    """Format a JSON-like payload as indented text.

    Args:
        payload: Dictionary to format.
        indent: Indentation level.

    Returns:
        Formatted string representation.
    """
    if payload is None:
        return "(empty)"

    import json

    return json.dumps(payload, indent=2)


def _format_snapshot_content(snapshot: ContextSnapshot) -> str:
    """Format a context snapshot as markdown content.

    Args:
        snapshot: The snapshot to format.

    Returns:
        Markdown formatted string.
    """
    lines = [
        f"# Context Snapshot {snapshot.snapshot_number:03d}",
        "",
        "## Timestamp",
        snapshot.timestamp,
        "",
        "## Milestone",
        f"{snapshot.milestone.value}",
        "",
        "## Scout A Report",
        "```json",
        _format_payload(snapshot.scout_a_payload),
        "```",
        "",
        "## Scout B Report",
        "```json",
        _format_payload(snapshot.scout_b_payload),
        "```",
        "",
    ]

    if snapshot.editor_state:
        lines.extend(
            [
                "## Editor State",
                f"- Current hypothesis: {snapshot.editor_state.hypothesis or '(none)'}",
                f"- Files modified: "
                f"{', '.join(snapshot.editor_state.files_modified) or '(none)'}",
                f"- Verify attempts: {snapshot.editor_state.verify_attempts}",
                f"- Consecutive failures: {snapshot.editor_state.consecutive_failures}",
                f"- Total verify loops: {snapshot.editor_state.total_verify_loops}",
                "",
            ]
        )

    return "\n".join(lines)


def write_context_snapshot(
    agent_dir: Path,
    milestone: Milestone,
    scout_a_payload: dict[str, Any] | None = None,
    scout_b_payload: dict[str, Any] | None = None,
    editor_state: EditorState | None = None,
    timestamp: str | None = None,
) -> Path:
    """Write a context snapshot to the agent directory.

    Creates a new numbered snapshot file (context_001.md, context_002.md, etc.)
    and updates the context_latest.md symlink to point to it.

    Args:
        agent_dir: Path to the agent directory.
        milestone: The milestone that triggered this snapshot.
        scout_a_payload: Raw Scout A response payload.
        scout_b_payload: Raw Scout B response payload.
        editor_state: Current Editor state.
        timestamp: Optional timestamp (uses current UTC if not provided).

    Returns:
        Path to the written snapshot file.

    Raises:
        ContextError: If writing fails.
    """
    # Ensure agent dir exists
    agent_dir.mkdir(exist_ok=True)

    snapshot_number = _get_next_snapshot_number(agent_dir)

    if timestamp is None:
        timestamp = _get_utc_timestamp()

    snapshot = ContextSnapshot(
        snapshot_number=snapshot_number,
        timestamp=timestamp,
        milestone=milestone,
        scout_a_payload=scout_a_payload,
        scout_b_payload=scout_b_payload,
        editor_state=editor_state,
    )

    # Write the snapshot file
    snapshot_filename = f"context_{snapshot_number:03d}.md"
    snapshot_path = agent_dir / snapshot_filename

    try:
        content = _format_snapshot_content(snapshot)
        snapshot_path.write_text(content)
    except OSError as e:
        raise ContextError(f"Failed to write context snapshot: {e}") from e

    # Update the symlink
    _update_latest_symlink(agent_dir, snapshot_filename)

    return snapshot_path


def _update_latest_symlink(agent_dir: Path, target_filename: str) -> None:
    """Update the context_latest.md symlink.

    Args:
        agent_dir: Path to the agent directory.
        target_filename: Name of the file to link to.
    """
    symlink_path = agent_dir / CONTEXT_LATEST_NAME

    try:
        # Remove existing symlink if present
        if symlink_path.is_symlink() or symlink_path.exists():
            symlink_path.unlink()

        # Create new symlink
        symlink_path.symlink_to(target_filename)
    except OSError:
        # Fall back to copying on systems that don't support symlinks
        target_path = agent_dir / target_filename
        if target_path.exists():
            symlink_path.write_text(target_path.read_text())


def get_latest_snapshot_path(agent_dir: Path) -> Path | None:
    """Get the path to the latest context snapshot.

    Args:
        agent_dir: Path to the agent directory.

    Returns:
        Path to the latest snapshot, or None if no snapshots exist.
    """
    latest_link = agent_dir / CONTEXT_LATEST_NAME
    if latest_link.exists():
        if latest_link.is_symlink():
            # Resolve the symlink
            target = latest_link.resolve()
            if target.exists():
                return target
        else:
            return latest_link

    # Fall back to finding the highest numbered snapshot
    snapshot_number = _get_next_snapshot_number(agent_dir) - 1
    if snapshot_number > 0:
        return agent_dir / f"context_{snapshot_number:03d}.md"

    return None


def get_snapshot_count(agent_dir: Path) -> int:
    """Get the number of context snapshots in the agent directory.

    Args:
        agent_dir: Path to the agent directory.

    Returns:
        Number of snapshot files.
    """
    if not agent_dir.exists():
        return 0

    count = 0
    for entry in agent_dir.iterdir():
        if entry.is_file() and CONTEXT_FILE_PATTERN.match(entry.name):
            count += 1
    return count


def should_create_snapshot(milestone: Milestone | str) -> bool:
    """Check if a milestone type should trigger snapshot creation.

    Only semantic milestones (TASK_START, REPLAN, TASK_SUCCESS) create snapshots.
    Scout queries, verify attempts, and fix iterations do NOT create snapshots.

    Args:
        milestone: The milestone to check (Milestone enum or string).

    Returns:
        True if the milestone should trigger a snapshot.
    """
    if isinstance(milestone, str):
        try:
            milestone = Milestone(milestone)
        except ValueError:
            return False

    return milestone in (Milestone.TASK_START, Milestone.REPLAN, Milestone.TASK_SUCCESS)
