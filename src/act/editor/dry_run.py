"""Dry-run mode for the Editor.

Generates proposed changes as unified diffs without writing to the filesystem.
Supports applying dry-run changes after user approval.
"""

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileChange:
    """A proposed change to a file."""

    path: str
    original_content: str
    new_content: str
    is_new_file: bool = False
    is_deleted: bool = False

    def to_unified_diff(self) -> str:
        """Generate a unified diff for this change.

        Returns:
            Git-style unified diff string.
        """
        if self.is_new_file:
            # New file
            diff_lines = [
                "--- /dev/null",
                f"+++ b/{self.path}",
                f"@@ -0,0 +1,{len(self.new_content.splitlines())} @@",
            ]
            for line in self.new_content.splitlines():
                diff_lines.append(f"+{line}")
            return "\n".join(diff_lines)

        if self.is_deleted:
            # Deleted file
            diff_lines = [
                f"--- a/{self.path}",
                "+++ /dev/null",
                f"@@ -1,{len(self.original_content.splitlines())} +0,0 @@",
            ]
            for line in self.original_content.splitlines():
                diff_lines.append(f"-{line}")
            return "\n".join(diff_lines)

        # Modified file
        original_lines = self.original_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)

        # Ensure lines end with newline for proper diff
        if original_lines and not original_lines[-1].endswith("\n"):
            original_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"a/{self.path}",
            tofile=f"b/{self.path}",
        )

        return "".join(diff).rstrip("\n")


@dataclass
class DryRunProposal:
    """A complete dry-run proposal with all changes."""

    changes: list[FileChange] = field(default_factory=list)
    summary: str = ""

    def add_change(
        self,
        path: str,
        original_content: str,
        new_content: str,
        is_new_file: bool = False,
        is_deleted: bool = False,
    ) -> None:
        """Add a change to the proposal.

        Args:
            path: Relative path to the file.
            original_content: Original file content.
            new_content: New file content.
            is_new_file: Whether this is a new file.
            is_deleted: Whether this file is being deleted.
        """
        self.changes.append(
            FileChange(
                path=path,
                original_content=original_content,
                new_content=new_content,
                is_new_file=is_new_file,
                is_deleted=is_deleted,
            )
        )

    def to_unified_diff(self) -> str:
        """Generate a combined unified diff for all changes.

        Returns:
            Git-style unified diff string.
        """
        diffs = []
        for change in self.changes:
            diff = change.to_unified_diff()
            if diff:
                diffs.append(diff)
        return "\n".join(diffs)

    def get_modified_files(self) -> list[str]:
        """Get list of files that will be modified.

        Returns:
            List of file paths.
        """
        return [c.path for c in self.changes if not c.is_deleted]

    def get_deleted_files(self) -> list[str]:
        """Get list of files that will be deleted.

        Returns:
            List of file paths.
        """
        return [c.path for c in self.changes if c.is_deleted]

    def get_new_files(self) -> list[str]:
        """Get list of new files that will be created.

        Returns:
            List of file paths.
        """
        return [c.path for c in self.changes if c.is_new_file]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with proposal details.
        """
        return {
            "summary": self.summary,
            "changes": [
                {
                    "path": c.path,
                    "is_new_file": c.is_new_file,
                    "is_deleted": c.is_deleted,
                }
                for c in self.changes
            ],
            "modified_files": self.get_modified_files(),
            "deleted_files": self.get_deleted_files(),
            "new_files": self.get_new_files(),
        }


class DryRunManager:
    """Manages dry-run mode operations.

    Handles:
    - Tracking proposed changes without writing
    - Generating unified diff output
    - Applying changes after approval
    """

    def __init__(self, repo_root: Path) -> None:
        """Initialize the dry-run manager.

        Args:
            repo_root: Root directory of the repository.
        """
        self.repo_root = repo_root
        self._proposal: DryRunProposal | None = None
        self._is_active = False

    @property
    def is_active(self) -> bool:
        """Check if dry-run mode is active."""
        return self._is_active

    @property
    def proposal(self) -> DryRunProposal | None:
        """Get the current proposal."""
        return self._proposal

    def start(self) -> None:
        """Start a new dry-run session."""
        self._is_active = True
        self._proposal = DryRunProposal()

    def stop(self) -> None:
        """Stop the dry-run session."""
        self._is_active = False

    def reset(self) -> None:
        """Reset the dry-run manager."""
        self._is_active = False
        self._proposal = None

    def propose_file_change(
        self,
        relative_path: str,
        new_content: str,
    ) -> None:
        """Propose a change to a file.

        Args:
            relative_path: Path relative to repo root.
            new_content: New content for the file.

        Raises:
            RuntimeError: If dry-run mode is not active.
        """
        if not self._is_active or not self._proposal:
            raise RuntimeError("Dry-run mode is not active")

        file_path = self.repo_root / relative_path

        if file_path.exists():
            original_content = file_path.read_text()
            is_new_file = False
        else:
            original_content = ""
            is_new_file = True

        self._proposal.add_change(
            path=relative_path,
            original_content=original_content,
            new_content=new_content,
            is_new_file=is_new_file,
        )

    def propose_file_deletion(self, relative_path: str) -> None:
        """Propose deletion of a file.

        Args:
            relative_path: Path relative to repo root.

        Raises:
            RuntimeError: If dry-run mode is not active.
            FileNotFoundError: If the file doesn't exist.
        """
        if not self._is_active or not self._proposal:
            raise RuntimeError("Dry-run mode is not active")

        file_path = self.repo_root / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"Cannot delete non-existent file: {relative_path}")

        original_content = file_path.read_text()

        self._proposal.add_change(
            path=relative_path,
            original_content=original_content,
            new_content="",
            is_deleted=True,
        )

    def set_summary(self, summary: str) -> None:
        """Set the summary for the proposal.

        Args:
            summary: Description of what the changes do.
        """
        if self._proposal:
            self._proposal.summary = summary

    def get_diff(self) -> str:
        """Get the unified diff for all proposed changes.

        Returns:
            Git-style unified diff string.
        """
        if not self._proposal:
            return ""
        return self._proposal.to_unified_diff()

    def apply_changes(self) -> list[str]:
        """Apply all proposed changes to the filesystem.

        Returns:
            List of files that were modified.

        Raises:
            RuntimeError: If no proposal exists.
        """
        if not self._proposal:
            raise RuntimeError("No proposal to apply")

        modified_files = []

        for change in self._proposal.changes:
            file_path = self.repo_root / change.path

            if change.is_deleted:
                if file_path.exists():
                    file_path.unlink()
                    modified_files.append(change.path)
            else:
                # Create parent directories if needed
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(change.new_content)
                modified_files.append(change.path)

        # Clear the proposal after applying
        self._proposal = None
        self._is_active = False

        return modified_files

    def discard_changes(self) -> None:
        """Discard all proposed changes without applying."""
        self._proposal = None
        self._is_active = False


def create_dry_run_manager(repo_root: Path | str) -> DryRunManager:
    """Create a dry-run manager.

    Args:
        repo_root: Repository root path.

    Returns:
        Configured DryRunManager.
    """
    return DryRunManager(Path(repo_root))


def format_proposal_output(proposal: DryRunProposal) -> str:
    """Format a proposal for display to the user.

    Args:
        proposal: The dry-run proposal.

    Returns:
        Formatted string for display.
    """
    lines = [
        "# Proposed Changes",
        "",
    ]

    if proposal.summary:
        lines.extend([proposal.summary, ""])

    new_files = proposal.get_new_files()
    modified = [
        c.path for c in proposal.changes if not c.is_new_file and not c.is_deleted
    ]
    deleted = proposal.get_deleted_files()

    if new_files:
        lines.append(f"**New files:** {len(new_files)}")
        for f in new_files:
            lines.append(f"  + {f}")
        lines.append("")

    if modified:
        lines.append(f"**Modified files:** {len(modified)}")
        for f in modified:
            lines.append(f"  ~ {f}")
        lines.append("")

    if deleted:
        lines.append(f"**Deleted files:** {len(deleted)}")
        for f in deleted:
            lines.append(f"  - {f}")
        lines.append("")

    lines.extend(
        [
            "## Diff",
            "",
            "```diff",
            proposal.to_unified_diff(),
            "```",
        ]
    )

    return "\n".join(lines)
