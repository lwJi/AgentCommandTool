"""Tests for agent context directory initialization."""

from pathlib import Path

import pytest

from act.artifacts.context_dir import (
    ContextDirError,
    ensure_agent_dir,
    ensure_gitignore_entry,
    get_agent_dir,
    initialize_agent_dir,
    is_agent_dir_initialized,
)


class TestGetAgentDir:
    """Tests for get_agent_dir function."""

    def test_returns_agent_path(self, tmp_path: Path) -> None:
        """Returns correct agent directory path."""
        agent_dir = get_agent_dir(tmp_path)

        assert agent_dir == tmp_path / "agent"


class TestEnsureAgentDir:
    """Tests for ensure_agent_dir function."""

    def test_creates_directory_when_missing(self, tmp_path: Path) -> None:
        """Creates agent directory when it doesn't exist."""
        agent_dir = ensure_agent_dir(tmp_path)

        assert agent_dir.is_dir()
        assert agent_dir == tmp_path / "agent"

    def test_idempotent_on_existing_dir(self, tmp_path: Path) -> None:
        """No error when directory already exists."""
        # Create directory first
        (tmp_path / "agent").mkdir()

        # Add a file to verify content is preserved
        test_file = tmp_path / "agent" / "test.txt"
        test_file.write_text("test content")

        # Should not error
        agent_dir = ensure_agent_dir(tmp_path)

        assert agent_dir.is_dir()
        assert test_file.exists()
        assert test_file.read_text() == "test content"


class TestEnsureGitignoreEntry:
    """Tests for ensure_gitignore_entry function."""

    def test_creates_gitignore_when_missing(self, tmp_path: Path) -> None:
        """Creates .gitignore with entry when it doesn't exist."""
        result = ensure_gitignore_entry(tmp_path)

        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert "agent/" in gitignore.read_text()
        assert result is True

    def test_appends_to_existing_gitignore(self, tmp_path: Path) -> None:
        """Appends entry to existing .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n*.log\n")

        result = ensure_gitignore_entry(tmp_path)

        content = gitignore.read_text()
        assert "node_modules/" in content
        assert "*.log" in content
        assert "agent/" in content
        assert result is True

    def test_appends_with_newline_if_needed(self, tmp_path: Path) -> None:
        """Adds newline before entry if file doesn't end with one."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/")  # No trailing newline

        ensure_gitignore_entry(tmp_path)

        content = gitignore.read_text()
        # Should have newline between existing content and new entry
        assert "node_modules/\nagent/" in content

    def test_no_duplicate_entry(self, tmp_path: Path) -> None:
        """Doesn't add duplicate entry if already present."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\nagent/\n")

        result = ensure_gitignore_entry(tmp_path)

        content = gitignore.read_text()
        # Should only have one agent/ entry
        assert content.count("agent/") == 1
        assert result is False

    def test_detects_various_agent_formats(self, tmp_path: Path) -> None:
        """Detects various formats of agent entry."""
        formats = ["agent/", "agent", "/agent/", "/agent"]

        for fmt in formats:
            gitignore = tmp_path / ".gitignore"
            gitignore.write_text(f"{fmt}\n")

            result = ensure_gitignore_entry(tmp_path)

            assert result is False, f"Should detect existing entry: {fmt}"


class TestInitializeAgentDir:
    """Tests for initialize_agent_dir function."""

    def test_creates_dir_and_updates_gitignore(self, tmp_path: Path) -> None:
        """Creates directory and updates .gitignore in one call."""
        agent_dir, gitignore_modified = initialize_agent_dir(tmp_path)

        assert agent_dir.is_dir()
        assert agent_dir == tmp_path / "agent"
        assert gitignore_modified is True

        gitignore = tmp_path / ".gitignore"
        assert "agent/" in gitignore.read_text()

    def test_idempotent_operation(self, tmp_path: Path) -> None:
        """Second call doesn't modify anything."""
        # First call
        initialize_agent_dir(tmp_path)

        # Second call
        agent_dir, gitignore_modified = initialize_agent_dir(tmp_path)

        assert agent_dir.is_dir()
        assert gitignore_modified is False

        # .gitignore should still have only one entry
        gitignore = tmp_path / ".gitignore"
        assert gitignore.read_text().count("agent/") == 1


class TestIsAgentDirInitialized:
    """Tests for is_agent_dir_initialized function."""

    def test_returns_true_when_initialized(self, tmp_path: Path) -> None:
        """Returns True when fully initialized."""
        initialize_agent_dir(tmp_path)

        assert is_agent_dir_initialized(tmp_path) is True

    def test_returns_false_when_dir_missing(self, tmp_path: Path) -> None:
        """Returns False when directory doesn't exist."""
        assert is_agent_dir_initialized(tmp_path) is False

    def test_returns_false_when_gitignore_missing(self, tmp_path: Path) -> None:
        """Returns False when .gitignore entry missing."""
        (tmp_path / "agent").mkdir()
        # No .gitignore

        assert is_agent_dir_initialized(tmp_path) is False

    def test_returns_false_when_gitignore_entry_missing(self, tmp_path: Path) -> None:
        """Returns False when directory exists but not in .gitignore."""
        (tmp_path / "agent").mkdir()
        (tmp_path / ".gitignore").write_text("node_modules/\n")

        assert is_agent_dir_initialized(tmp_path) is False
