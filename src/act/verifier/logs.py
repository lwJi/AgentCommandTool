"""Log file management and tail log extraction."""

from pathlib import Path

from act.verifier.exceptions import LogError

# Number of lines to include in tail_log
TAIL_LOG_LINES = 200


def create_logs_dir(run_dir: Path) -> Path:
    """Create logs subdirectory in run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        Path to the created logs directory.

    Raises:
        LogError: If directory creation fails.
    """
    logs_dir = run_dir / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise LogError(f"Failed to create logs directory: {e}") from e
    return logs_dir


def create_tmp_dir(run_dir: Path) -> Path:
    """Create tmp subdirectory for test writes.

    Args:
        run_dir: Path to the run directory.

    Returns:
        Path to the created tmp directory.

    Raises:
        LogError: If directory creation fails.
    """
    tmp_dir = run_dir / "tmp"
    try:
        tmp_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise LogError(f"Failed to create tmp directory: {e}") from e
    return tmp_dir


def create_db_dir(run_dir: Path) -> Path:
    """Create db subdirectory for test database writes.

    Args:
        run_dir: Path to the run directory.

    Returns:
        Path to the created db directory.

    Raises:
        LogError: If directory creation fails.
    """
    db_dir = run_dir / "db"
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise LogError(f"Failed to create db directory: {e}") from e
    return db_dir


def get_step_log_filename(step_number: int, step_name: str) -> str:
    """Generate step log filename.

    Format: step-{nn}-{name}.log where nn is zero-padded step number.

    Args:
        step_number: 1-based step number.
        step_name: Name of the step.

    Returns:
        Filename for the step log.
    """
    return f"step-{step_number:02d}-{step_name}.log"


def extract_tail_log(
    combined_log_path: Path,
    lines: int = TAIL_LOG_LINES,
) -> str:
    """Extract last N lines from combined log.

    Handles:
    - Logs shorter than N lines (returns all)
    - Empty logs (returns empty string)
    - Missing logs (returns empty string)

    Args:
        combined_log_path: Path to the combined.log file.
        lines: Number of lines to extract (default: 200).

    Returns:
        Last N lines of the log as a string.
    """
    if not combined_log_path.exists():
        return ""

    try:
        content = combined_log_path.read_text()
    except OSError:
        return ""

    if not content:
        return ""

    # Split into lines and get last N
    all_lines = content.splitlines()
    tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

    return "\n".join(tail_lines)


def list_artifact_paths(run_dir: Path) -> list[str]:
    """List all artifact paths in run directory.

    Recursively lists all files in the run directory.

    Args:
        run_dir: Path to the run directory.

    Returns:
        List of absolute paths to all artifacts.
    """
    if not run_dir.exists():
        return []

    paths: list[str] = []
    for path in run_dir.rglob("*"):
        if path.is_file():
            paths.append(str(path))

    return sorted(paths)


def write_step_log(
    logs_dir: Path,
    step_number: int,
    step_name: str,
    output: str,
) -> Path:
    """Write step output to individual log file.

    Args:
        logs_dir: Path to the logs directory.
        step_number: 1-based step number.
        step_name: Name of the step.
        output: Output content to write.

    Returns:
        Path to the written log file.

    Raises:
        LogError: If writing fails.
    """
    filename = get_step_log_filename(step_number, step_name)
    log_path = logs_dir / filename

    try:
        log_path.write_text(output)
    except OSError as e:
        raise LogError(f"Failed to write step log: {e}") from e

    return log_path


def append_combined_log(logs_dir: Path, output: str) -> Path:
    """Append output to combined.log.

    Creates the file if it doesn't exist.

    Args:
        logs_dir: Path to the logs directory.
        output: Output content to append.

    Returns:
        Path to the combined log file.

    Raises:
        LogError: If writing fails.
    """
    combined_path = logs_dir / "combined.log"

    try:
        with combined_path.open("a") as f:
            f.write(output)
            # Ensure newline at end if output doesn't have one
            if output and not output.endswith("\n"):
                f.write("\n")
    except OSError as e:
        raise LogError(f"Failed to append to combined log: {e}") from e

    return combined_path
