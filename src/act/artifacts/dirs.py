"""ARTIFACT_DIR directory structure management."""

from pathlib import Path

from act.config.env import get_artifact_dir


class ArtifactDirError(Exception):
    """Error related to artifact directory operations."""

    pass


def ensure_artifact_dir_structure(artifact_dir: Path | None = None) -> Path:
    """Ensure the artifact directory structure exists.

    Creates the following structure:
        ARTIFACT_DIR/
        ├── runs/
        └── cache/

    Args:
        artifact_dir: Path to artifact directory. If None, uses default from env.

    Returns:
        Path to the artifact directory.

    Raises:
        ArtifactDirError: If directory creation fails.
    """
    if artifact_dir is None:
        artifact_dir = get_artifact_dir()

    try:
        # Create main directory
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        runs_dir = artifact_dir / "runs"
        runs_dir.mkdir(exist_ok=True)

        cache_dir = artifact_dir / "cache"
        cache_dir.mkdir(exist_ok=True)

    except OSError as e:
        raise ArtifactDirError(
            f"Failed to create artifact directory structure: {e}"
        ) from e

    return artifact_dir


def get_runs_dir(artifact_dir: Path | None = None) -> Path:
    """Get the runs subdirectory path.

    Args:
        artifact_dir: Path to artifact directory. If None, uses default from env.

    Returns:
        Path to runs subdirectory.
    """
    if artifact_dir is None:
        artifact_dir = get_artifact_dir()
    return artifact_dir / "runs"


def get_cache_dir(artifact_dir: Path | None = None) -> Path:
    """Get the cache subdirectory path.

    Args:
        artifact_dir: Path to artifact directory. If None, uses default from env.

    Returns:
        Path to cache subdirectory.
    """
    if artifact_dir is None:
        artifact_dir = get_artifact_dir()
    return artifact_dir / "cache"


def is_artifact_dir_initialized(artifact_dir: Path | None = None) -> bool:
    """Check if the artifact directory structure is properly initialized.

    Args:
        artifact_dir: Path to artifact directory. If None, uses default from env.

    Returns:
        True if the directory structure exists.
    """
    if artifact_dir is None:
        artifact_dir = get_artifact_dir()

    runs_dir = artifact_dir / "runs"
    cache_dir = artifact_dir / "cache"

    return artifact_dir.is_dir() and runs_dir.is_dir() and cache_dir.is_dir()
