"""Unit tests for Editor dry-run mode."""

from pathlib import Path

import pytest

from act.editor.dry_run import (
    DryRunManager,
    DryRunProposal,
    FileChange,
    create_dry_run_manager,
    format_proposal_output,
)


class TestFileChange:
    """Tests for FileChange dataclass."""

    def test_modified_file_diff(self) -> None:
        """Test unified diff for modified file."""
        change = FileChange(
            path="src/main.py",
            original_content="def foo():\n    return 1\n",
            new_content="def foo():\n    return 2\n",
        )
        diff = change.to_unified_diff()

        assert "--- a/src/main.py" in diff
        assert "+++ b/src/main.py" in diff
        assert "-    return 1" in diff
        assert "+    return 2" in diff

    def test_new_file_diff(self) -> None:
        """Test unified diff for new file."""
        change = FileChange(
            path="src/new.py",
            original_content="",
            new_content="print('hello')\n",
            is_new_file=True,
        )
        diff = change.to_unified_diff()

        assert "--- /dev/null" in diff
        assert "+++ b/src/new.py" in diff
        assert "+print('hello')" in diff

    def test_deleted_file_diff(self) -> None:
        """Test unified diff for deleted file."""
        change = FileChange(
            path="src/old.py",
            original_content="print('goodbye')\n",
            new_content="",
            is_deleted=True,
        )
        diff = change.to_unified_diff()

        assert "--- a/src/old.py" in diff
        assert "+++ /dev/null" in diff
        assert "-print('goodbye')" in diff


class TestDryRunProposal:
    """Tests for DryRunProposal dataclass."""

    def test_empty_proposal(self) -> None:
        """Test empty proposal."""
        proposal = DryRunProposal()
        assert proposal.changes == []
        assert proposal.summary == ""

    def test_add_change(self) -> None:
        """Test adding a change."""
        proposal = DryRunProposal()
        proposal.add_change(
            path="src/main.py",
            original_content="old",
            new_content="new",
        )
        assert len(proposal.changes) == 1
        assert proposal.changes[0].path == "src/main.py"

    def test_to_unified_diff(self) -> None:
        """Test combined unified diff."""
        proposal = DryRunProposal()
        proposal.add_change("a.py", "old a", "new a")
        proposal.add_change("b.py", "old b", "new b")
        diff = proposal.to_unified_diff()

        assert "a.py" in diff
        assert "b.py" in diff

    def test_get_modified_files(self) -> None:
        """Test getting modified files."""
        proposal = DryRunProposal()
        proposal.add_change("a.py", "old", "new")
        proposal.add_change("b.py", "old", "new", is_deleted=True)
        proposal.add_change("c.py", "", "new", is_new_file=True)

        modified = proposal.get_modified_files()
        assert "a.py" in modified
        assert "c.py" in modified
        assert "b.py" not in modified

    def test_get_deleted_files(self) -> None:
        """Test getting deleted files."""
        proposal = DryRunProposal()
        proposal.add_change("a.py", "old", "new")
        proposal.add_change("b.py", "old", "", is_deleted=True)

        deleted = proposal.get_deleted_files()
        assert deleted == ["b.py"]

    def test_get_new_files(self) -> None:
        """Test getting new files."""
        proposal = DryRunProposal()
        proposal.add_change("a.py", "old", "new")
        proposal.add_change("b.py", "", "new", is_new_file=True)

        new_files = proposal.get_new_files()
        assert new_files == ["b.py"]

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        proposal = DryRunProposal()
        proposal.summary = "Test changes"
        proposal.add_change("a.py", "old", "new")

        result = proposal.to_dict()
        assert result["summary"] == "Test changes"
        assert len(result["changes"]) == 1


class TestDryRunManager:
    """Tests for DryRunManager class."""

    def test_initial_state(self, tmp_path: Path) -> None:
        """Test initial manager state."""
        manager = DryRunManager(tmp_path)
        assert manager.is_active is False
        assert manager.proposal is None

    def test_start_activates_mode(self, tmp_path: Path) -> None:
        """Test start activates dry-run mode."""
        manager = DryRunManager(tmp_path)
        manager.start()
        assert manager.is_active is True
        assert manager.proposal is not None

    def test_stop_deactivates_mode(self, tmp_path: Path) -> None:
        """Test stop deactivates dry-run mode."""
        manager = DryRunManager(tmp_path)
        manager.start()
        manager.stop()
        assert manager.is_active is False

    def test_reset_clears_state(self, tmp_path: Path) -> None:
        """Test reset clears all state."""
        manager = DryRunManager(tmp_path)
        manager.start()
        manager.propose_file_change("test.py", "content")
        manager.reset()
        assert manager.is_active is False
        assert manager.proposal is None

    def test_propose_file_change_new_file(self, tmp_path: Path) -> None:
        """Test proposing a new file."""
        manager = DryRunManager(tmp_path)
        manager.start()
        manager.propose_file_change("new.py", "print('hello')")

        assert len(manager.proposal.changes) == 1
        assert manager.proposal.changes[0].is_new_file is True

    def test_propose_file_change_existing_file(self, tmp_path: Path) -> None:
        """Test proposing changes to existing file."""
        (tmp_path / "existing.py").write_text("old content")

        manager = DryRunManager(tmp_path)
        manager.start()
        manager.propose_file_change("existing.py", "new content")

        assert len(manager.proposal.changes) == 1
        assert manager.proposal.changes[0].original_content == "old content"
        assert manager.proposal.changes[0].is_new_file is False

    def test_propose_without_start_raises(self, tmp_path: Path) -> None:
        """Test that proposing without start raises error."""
        manager = DryRunManager(tmp_path)
        with pytest.raises(RuntimeError, match="not active"):
            manager.propose_file_change("test.py", "content")

    def test_propose_file_deletion(self, tmp_path: Path) -> None:
        """Test proposing file deletion."""
        (tmp_path / "delete_me.py").write_text("content")

        manager = DryRunManager(tmp_path)
        manager.start()
        manager.propose_file_deletion("delete_me.py")

        assert len(manager.proposal.changes) == 1
        assert manager.proposal.changes[0].is_deleted is True

    def test_propose_deletion_nonexistent_raises(self, tmp_path: Path) -> None:
        """Test proposing deletion of non-existent file raises error."""
        manager = DryRunManager(tmp_path)
        manager.start()
        with pytest.raises(FileNotFoundError):
            manager.propose_file_deletion("nonexistent.py")

    def test_set_summary(self, tmp_path: Path) -> None:
        """Test setting proposal summary."""
        manager = DryRunManager(tmp_path)
        manager.start()
        manager.set_summary("Fixed the bug")
        assert manager.proposal.summary == "Fixed the bug"

    def test_get_diff(self, tmp_path: Path) -> None:
        """Test getting diff from manager."""
        manager = DryRunManager(tmp_path)
        manager.start()
        manager.propose_file_change("test.py", "content")
        diff = manager.get_diff()
        assert "test.py" in diff

    def test_apply_changes(self, tmp_path: Path) -> None:
        """Test applying proposed changes."""
        manager = DryRunManager(tmp_path)
        manager.start()
        manager.propose_file_change("new_file.py", "print('hello')")

        modified = manager.apply_changes()

        assert "new_file.py" in modified
        assert (tmp_path / "new_file.py").exists()
        assert (tmp_path / "new_file.py").read_text() == "print('hello')"
        assert manager.is_active is False

    def test_apply_changes_creates_directories(self, tmp_path: Path) -> None:
        """Test that apply_changes creates parent directories."""
        manager = DryRunManager(tmp_path)
        manager.start()
        manager.propose_file_change("src/lib/module.py", "content")

        manager.apply_changes()

        assert (tmp_path / "src" / "lib" / "module.py").exists()

    def test_apply_changes_deletes_files(self, tmp_path: Path) -> None:
        """Test that apply_changes deletes files."""
        (tmp_path / "to_delete.py").write_text("delete me")

        manager = DryRunManager(tmp_path)
        manager.start()
        manager.propose_file_deletion("to_delete.py")

        manager.apply_changes()

        assert not (tmp_path / "to_delete.py").exists()

    def test_apply_without_proposal_raises(self, tmp_path: Path) -> None:
        """Test that apply without proposal raises error."""
        manager = DryRunManager(tmp_path)
        with pytest.raises(RuntimeError, match="No proposal"):
            manager.apply_changes()

    def test_discard_changes(self, tmp_path: Path) -> None:
        """Test discarding changes."""
        manager = DryRunManager(tmp_path)
        manager.start()
        manager.propose_file_change("test.py", "content")

        manager.discard_changes()

        assert manager.is_active is False
        assert manager.proposal is None
        assert not (tmp_path / "test.py").exists()


class TestCreateDryRunManager:
    """Tests for create_dry_run_manager factory."""

    def test_creates_manager(self, tmp_path: Path) -> None:
        """Test factory creates manager."""
        manager = create_dry_run_manager(tmp_path)
        assert manager.repo_root == tmp_path

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Test factory accepts string path."""
        manager = create_dry_run_manager(str(tmp_path))
        assert manager.repo_root == tmp_path


class TestFormatProposalOutput:
    """Tests for format_proposal_output function."""

    def test_formats_proposal(self) -> None:
        """Test proposal formatting."""
        proposal = DryRunProposal()
        proposal.summary = "Added new feature"
        proposal.add_change("new.py", "", "content", is_new_file=True)
        proposal.add_change("mod.py", "old", "new")
        proposal.add_change("del.py", "content", "", is_deleted=True)

        output = format_proposal_output(proposal)

        assert "# Proposed Changes" in output
        assert "Added new feature" in output
        assert "New files:" in output
        assert "Modified files:" in output
        assert "Deleted files:" in output
        assert "```diff" in output

    def test_formats_empty_proposal(self) -> None:
        """Test formatting empty proposal."""
        proposal = DryRunProposal()
        output = format_proposal_output(proposal)
        assert "# Proposed Changes" in output
