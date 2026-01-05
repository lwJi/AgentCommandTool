"""Agent context directory initialization."""

from pathlib import Path


class ContextDirError(Exception):
    """Error related to context directory operations."""

    pass


AGENT_DIR_NAME = "agent"
GITIGNORE_ENTRY = "agent/"


def get_agent_dir(repo_root: Path) -> Path:
    """Get the agent directory path for a repository.

    Args:
        repo_root: Path to the repository root.

    Returns:
        Path to the agent directory.
    """
    return repo_root / AGENT_DIR_NAME


def ensure_agent_dir(repo_root: Path) -> Path:
    """Ensure the agent directory exists in the repository.

    Creates the agent/ directory if it doesn't exist.

    Args:
        repo_root: Path to the repository root.

    Returns:
        Path to the agent directory.

    Raises:
        ContextDirError: If directory creation fails.
    """
    agent_dir = get_agent_dir(repo_root)

    try:
        agent_dir.mkdir(exist_ok=True)
    except OSError as e:
        raise ContextDirError(f"Failed to create agent directory: {e}") from e

    return agent_dir


def _read_gitignore(gitignore_path: Path) -> list[str]:
    """Read .gitignore file and return lines.

    Args:
        gitignore_path: Path to .gitignore file.

    Returns:
        List of lines in the file, or empty list if file doesn't exist.
    """
    if not gitignore_path.exists():
        return []

    try:
        content = gitignore_path.read_text()
        return content.splitlines()
    except OSError:
        return []


def _has_agent_entry(lines: list[str]) -> bool:
    """Check if .gitignore already has the agent/ entry.

    Args:
        lines: Lines from .gitignore file.

    Returns:
        True if agent/ entry already exists.
    """
    for line in lines:
        stripped = line.strip()
        # Match "agent/", "agent", "/agent/", "/agent"
        if stripped in ("agent/", "agent", "/agent/", "/agent"):
            return True
    return False


def ensure_gitignore_entry(repo_root: Path) -> bool:
    """Ensure agent/ is in .gitignore.

    Appends agent/ to .gitignore if not already present.
    Creates .gitignore if it doesn't exist.

    Args:
        repo_root: Path to the repository root.

    Returns:
        True if entry was added, False if already present.

    Raises:
        ContextDirError: If updating .gitignore fails.
    """
    gitignore_path = repo_root / ".gitignore"
    lines = _read_gitignore(gitignore_path)

    if _has_agent_entry(lines):
        return False

    # Append the entry
    try:
        # Add newline before if file exists and doesn't end with newline
        content = gitignore_path.read_text() if gitignore_path.exists() else ""
        if content and not content.endswith("\n"):
            content += "\n"
        content += GITIGNORE_ENTRY + "\n"
        gitignore_path.write_text(content)
    except OSError as e:
        raise ContextDirError(f"Failed to update .gitignore: {e}") from e

    return True


def initialize_agent_dir(repo_root: Path) -> tuple[Path, bool]:
    """Initialize the agent directory and ensure .gitignore entry.

    This is the main entry point for agent directory initialization.
    It creates the agent/ directory and ensures it's in .gitignore.

    Args:
        repo_root: Path to the repository root.

    Returns:
        Tuple of (agent_directory_path, gitignore_was_modified).

    Raises:
        ContextDirError: If initialization fails.
    """
    agent_dir = ensure_agent_dir(repo_root)
    gitignore_modified = ensure_gitignore_entry(repo_root)
    return agent_dir, gitignore_modified


def is_agent_dir_initialized(repo_root: Path) -> bool:
    """Check if the agent directory is properly initialized.

    Args:
        repo_root: Path to the repository root.

    Returns:
        True if agent/ directory exists and is in .gitignore.
    """
    agent_dir = get_agent_dir(repo_root)
    if not agent_dir.is_dir():
        return False

    gitignore_path = repo_root / ".gitignore"
    lines = _read_gitignore(gitignore_path)
    return _has_agent_entry(lines)
