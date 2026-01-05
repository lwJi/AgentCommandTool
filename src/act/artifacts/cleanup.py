"""Artifact retention and cleanup management."""

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from act.artifacts.dirs import get_runs_dir
from act.artifacts.run_id import is_valid_run_id, parse_run_id_timestamp


class CleanupError(Exception):
    """Error related to cleanup operations."""

    pass


# Retention limits
MAX_RUNS = 20
MAX_AGE_DAYS = 14

# Stuck report filename
STUCK_REPORT_FILENAME = "stuck_report.md"


@dataclass
class RunInfo:
    """Information about a verification run."""

    run_id: str
    run_dir: Path
    timestamp: datetime | None
    has_stuck_report: bool


def _get_run_info(run_dir: Path) -> RunInfo | None:
    """Get information about a run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        RunInfo if valid run directory, None otherwise.
    """
    run_id = run_dir.name

    if not is_valid_run_id(run_id):
        return None

    if not run_dir.is_dir():
        return None

    timestamp = parse_run_id_timestamp(run_id)
    has_stuck_report = (run_dir / STUCK_REPORT_FILENAME).exists()

    return RunInfo(
        run_id=run_id,
        run_dir=run_dir,
        timestamp=timestamp,
        has_stuck_report=has_stuck_report,
    )


def list_runs(artifact_dir: Path) -> list[RunInfo]:
    """List all verification runs in the artifact directory.

    Args:
        artifact_dir: Path to the artifact directory.

    Returns:
        List of RunInfo objects, sorted by timestamp (oldest first).
    """
    runs_dir = get_runs_dir(artifact_dir)

    if not runs_dir.exists():
        return []

    runs = []
    for entry in runs_dir.iterdir():
        if entry.is_dir():
            run_info = _get_run_info(entry)
            if run_info is not None:
                runs.append(run_info)

    # Sort by timestamp (oldest first), with None timestamps at the end
    runs.sort(key=lambda r: r.timestamp or datetime.max.replace(tzinfo=UTC))

    return runs


def get_runs_to_delete(
    runs: list[RunInfo],
    max_runs: int = MAX_RUNS,
    max_age_days: int = MAX_AGE_DAYS,
    now: datetime | None = None,
) -> list[RunInfo]:
    """Determine which runs should be deleted based on retention policy.

    Retention rules:
    1. Keep at most `max_runs` runs
    2. Delete runs older than `max_age_days`
    3. Never delete runs with stuck reports

    Args:
        runs: List of RunInfo objects (should be sorted oldest first).
        max_runs: Maximum number of runs to keep.
        max_age_days: Maximum age in days.
        now: Current time for age calculation (uses UTC now if not provided).

    Returns:
        List of RunInfo objects that should be deleted.
    """
    if now is None:
        now = datetime.now(UTC)

    cutoff_time = now - timedelta(days=max_age_days)
    to_delete = []

    # First pass: mark runs that are too old
    for run in runs:
        if run.has_stuck_report:
            # Never delete stuck report runs
            continue

        if run.timestamp and run.timestamp < cutoff_time:
            to_delete.append(run)

    # Second pass: if we still have too many runs, delete oldest non-stuck runs
    remaining = [r for r in runs if r not in to_delete]
    non_stuck_remaining = [r for r in remaining if not r.has_stuck_report]

    excess_count = len(remaining) - max_runs
    if excess_count > 0:
        # Delete oldest excess runs (already sorted oldest first)
        for run in non_stuck_remaining[:excess_count]:
            if run not in to_delete:
                to_delete.append(run)

    return to_delete


def delete_run(run_info: RunInfo) -> bool:
    """Delete a verification run directory.

    Args:
        run_info: RunInfo for the run to delete.

    Returns:
        True if deletion succeeded, False otherwise.
    """
    try:
        if run_info.run_dir.exists():
            shutil.rmtree(run_info.run_dir)
            return True
        return False
    except OSError:
        return False


def cleanup_runs(
    artifact_dir: Path,
    max_runs: int = MAX_RUNS,
    max_age_days: int = MAX_AGE_DAYS,
    now: datetime | None = None,
) -> int:
    """Run the cleanup process on the artifact directory.

    Args:
        artifact_dir: Path to the artifact directory.
        max_runs: Maximum number of runs to keep.
        max_age_days: Maximum age in days.
        now: Current time for age calculation.

    Returns:
        Number of runs deleted.
    """
    runs = list_runs(artifact_dir)
    to_delete = get_runs_to_delete(runs, max_runs, max_age_days, now)

    deleted_count = 0
    for run_info in to_delete:
        if delete_run(run_info):
            deleted_count += 1

    return deleted_count


def get_run_count(artifact_dir: Path) -> int:
    """Get the count of verification runs.

    Args:
        artifact_dir: Path to the artifact directory.

    Returns:
        Number of verification runs.
    """
    return len(list_runs(artifact_dir))
