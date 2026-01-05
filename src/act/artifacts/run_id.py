"""Run ID generation and run directory management."""

import random
import string
from datetime import UTC, datetime
from pathlib import Path

from act.artifacts.dirs import ensure_artifact_dir_structure, get_runs_dir


class RunIDError(Exception):
    """Error related to run ID operations."""

    pass


def generate_run_id() -> str:
    """Generate a unique run ID.

    Format: run_{YYYYMMDD}_{HHMMSS}_{random6chars}
    Uses UTC timezone.

    Returns:
        Unique run ID string.
    """
    now = datetime.now(UTC)
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"run_{date_part}_{time_part}_{random_suffix}"


def get_run_dir(run_id: str, artifact_dir: Path | None = None) -> Path:
    """Get the directory path for a specific run.

    Args:
        run_id: The run ID.
        artifact_dir: Path to artifact directory. If None, uses default.

    Returns:
        Path to the run directory.
    """
    runs_dir = get_runs_dir(artifact_dir)
    return runs_dir / run_id


def create_run_dir(artifact_dir: Path | None = None) -> tuple[str, Path]:
    """Generate a run ID and create its directory.

    Ensures the artifact directory structure exists first.

    Args:
        artifact_dir: Path to artifact directory. If None, uses default.

    Returns:
        Tuple of (run_id, run_directory_path).

    Raises:
        RunIDError: If directory creation fails.
    """
    # Ensure artifact dir structure exists
    if artifact_dir is not None:
        ensure_artifact_dir_structure(artifact_dir)
    else:
        from act.config.env import get_artifact_dir

        artifact_dir = get_artifact_dir()
        ensure_artifact_dir_structure(artifact_dir)

    run_id = generate_run_id()
    run_dir = get_run_dir(run_id, artifact_dir)

    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as e:
        # Extremely unlikely due to random suffix, but handle it
        raise RunIDError(f"Run directory already exists: {run_dir}") from e
    except OSError as e:
        raise RunIDError(f"Failed to create run directory: {e}") from e

    return run_id, run_dir


def parse_run_id_timestamp(run_id: str) -> datetime | None:
    """Parse the timestamp from a run ID.

    Args:
        run_id: The run ID to parse.

    Returns:
        datetime object (UTC) or None if parsing fails.
    """
    try:
        # Format: run_{YYYYMMDD}_{HHMMSS}_{random}
        parts = run_id.split("_")
        if len(parts) != 4 or parts[0] != "run":
            return None

        date_str = parts[1]
        time_str = parts[2]

        # Validate exact format lengths
        if len(date_str) != 8 or len(time_str) != 6:
            return None

        return datetime.strptime(
            f"{date_str}_{time_str}", "%Y%m%d_%H%M%S"
        ).replace(tzinfo=UTC)
    except (ValueError, IndexError):
        return None


def is_valid_run_id(run_id: str) -> bool:
    """Check if a string is a valid run ID format.

    Args:
        run_id: String to validate.

    Returns:
        True if valid run ID format.
    """
    if not run_id.startswith("run_"):
        return False

    parts = run_id.split("_")
    if len(parts) != 4:
        return False

    date_part = parts[1]
    time_part = parts[2]
    random_part = parts[3]

    # Validate date format (8 digits)
    if len(date_part) != 8 or not date_part.isdigit():
        return False

    # Validate time format (6 digits)
    if len(time_part) != 6 or not time_part.isdigit():
        return False

    # Validate random suffix (6 lowercase alphanumeric)
    if len(random_part) != 6:
        return False
    valid_chars = set(string.ascii_lowercase + string.digits)
    if not all(c in valid_chars for c in random_part):
        return False

    # Validate actual date/time values
    return parse_run_id_timestamp(run_id) is not None
