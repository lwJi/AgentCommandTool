"""Write boundary enforcement for the Editor.

Ensures the Editor only writes to allowed locations:
- Repository working tree
- agent/ context files

Rejects writes to:
- Files outside repo root
- ARTIFACT_DIR (read-only for Editor)
"""

from pathlib import Path

from act.editor.exceptions import WriteBoundaryError


class WriteBoundaryEnforcer:
    """Enforces write boundaries for the Editor.

    The Editor can only write to:
    - Repository working tree
    - agent/ directory (context files)

    The Editor cannot write to:
    - Files outside repo root
    - ARTIFACT_DIR (Verifier writes there)
    """

    def __init__(
        self,
        repo_root: Path,
        agent_dir_name: str = "agent",
        artifact_dir: Path | None = None,
    ) -> None:
        """Initialize the boundary enforcer.

        Args:
            repo_root: Root directory of the repository.
            agent_dir_name: Name of the agent directory (default: "agent").
            artifact_dir: Optional artifact directory to explicitly block.
        """
        self.repo_root = repo_root.resolve()
        self.agent_dir_name = agent_dir_name
        self.agent_dir = self.repo_root / agent_dir_name
        self.artifact_dir = artifact_dir.resolve() if artifact_dir else None

    def validate_path(self, path: Path | str) -> Path:
        """Validate that a path is within allowed write boundaries.

        Args:
            path: Path to validate.

        Returns:
            Resolved path if valid.

        Raises:
            WriteBoundaryError: If the path is outside allowed boundaries.
        """
        if isinstance(path, str):
            path = Path(path)

        # Resolve to absolute path
        if not path.is_absolute():
            path = (self.repo_root / path).resolve()
        else:
            path = path.resolve()

        # Check if within repo root
        try:
            path.relative_to(self.repo_root)
        except ValueError as e:
            raise WriteBoundaryError(
                f"Path is outside repository root: {path}",
                attempted_path=str(path),
            ) from e

        # Check if in artifact dir (if specified)
        if self.artifact_dir:
            try:
                path.relative_to(self.artifact_dir)
                raise WriteBoundaryError(
                    f"Cannot write to artifact directory: {path}",
                    attempted_path=str(path),
                )
            except ValueError:
                pass  # Not in artifact dir, which is good

        return path

    def is_in_agent_dir(self, path: Path | str) -> bool:
        """Check if a path is in the agent directory.

        Args:
            path: Path to check.

        Returns:
            True if the path is in the agent directory.
        """
        if isinstance(path, str):
            path = Path(path)

        if not path.is_absolute():
            path = (self.repo_root / path).resolve()
        else:
            path = path.resolve()

        try:
            path.relative_to(self.agent_dir)
            return True
        except ValueError:
            return False

    def is_in_repo(self, path: Path | str) -> bool:
        """Check if a path is in the repository.

        Args:
            path: Path to check.

        Returns:
            True if the path is in the repository.
        """
        if isinstance(path, str):
            path = Path(path)

        if not path.is_absolute():
            path = (self.repo_root / path).resolve()
        else:
            path = path.resolve()

        try:
            path.relative_to(self.repo_root)
            return True
        except ValueError:
            return False

    def get_relative_path(self, path: Path | str) -> str:
        """Get the path relative to repo root.

        Args:
            path: Path to convert.

        Returns:
            Relative path string.

        Raises:
            WriteBoundaryError: If the path is outside the repo.
        """
        validated = self.validate_path(path)
        return str(validated.relative_to(self.repo_root))


def create_boundary_enforcer(
    repo_root: Path | str,
    artifact_dir: Path | str | None = None,
) -> WriteBoundaryEnforcer:
    """Create a write boundary enforcer.

    Args:
        repo_root: Repository root path.
        artifact_dir: Optional artifact directory path.

    Returns:
        Configured WriteBoundaryEnforcer.
    """
    artifact_path = Path(artifact_dir) if artifact_dir else None
    return WriteBoundaryEnforcer(Path(repo_root), artifact_dir=artifact_path)
