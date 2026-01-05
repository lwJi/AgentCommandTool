"""Unit tests for Editor write boundaries."""

from pathlib import Path

import pytest

from act.editor.boundaries import (
    WriteBoundaryEnforcer,
    create_boundary_enforcer,
)
from act.editor.exceptions import WriteBoundaryError


class TestWriteBoundaryEnforcer:
    """Tests for WriteBoundaryEnforcer class."""

    def test_validate_path_in_repo(self, tmp_path: Path) -> None:
        """Test validating path within repo."""
        enforcer = WriteBoundaryEnforcer(tmp_path)
        path = enforcer.validate_path("src/main.py")
        assert path == tmp_path / "src" / "main.py"

    def test_validate_absolute_path_in_repo(self, tmp_path: Path) -> None:
        """Test validating absolute path within repo."""
        enforcer = WriteBoundaryEnforcer(tmp_path)
        abs_path = tmp_path / "src" / "main.py"
        validated = enforcer.validate_path(abs_path)
        assert validated == abs_path

    def test_validate_path_outside_repo_raises(self, tmp_path: Path) -> None:
        """Test that path outside repo raises error."""
        enforcer = WriteBoundaryEnforcer(tmp_path)
        with pytest.raises(WriteBoundaryError) as exc_info:
            enforcer.validate_path("/etc/passwd")
        assert "outside repository root" in str(exc_info.value)

    def test_validate_path_in_artifact_dir_raises(self, tmp_path: Path) -> None:
        """Test that path in artifact dir raises error."""
        # Create artifact dir inside repo root
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        artifact_dir = repo_root / ".artifacts"
        artifact_dir.mkdir()

        enforcer = WriteBoundaryEnforcer(repo_root, artifact_dir=artifact_dir)

        with pytest.raises(WriteBoundaryError) as exc_info:
            enforcer.validate_path(artifact_dir / "run_001" / "log.txt")
        assert "artifact directory" in str(exc_info.value)

    def test_is_in_agent_dir(self, tmp_path: Path) -> None:
        """Test checking if path is in agent directory."""
        enforcer = WriteBoundaryEnforcer(tmp_path)

        assert enforcer.is_in_agent_dir("agent/context_001.md")
        assert enforcer.is_in_agent_dir(tmp_path / "agent" / "context.md")
        assert not enforcer.is_in_agent_dir("src/main.py")

    def test_is_in_repo(self, tmp_path: Path) -> None:
        """Test checking if path is in repo."""
        enforcer = WriteBoundaryEnforcer(tmp_path)

        assert enforcer.is_in_repo("src/main.py")
        assert enforcer.is_in_repo(tmp_path / "src" / "main.py")
        assert not enforcer.is_in_repo("/etc/passwd")

    def test_get_relative_path(self, tmp_path: Path) -> None:
        """Test getting relative path."""
        enforcer = WriteBoundaryEnforcer(tmp_path)
        rel = enforcer.get_relative_path(tmp_path / "src" / "main.py")
        assert rel == "src/main.py"

    def test_get_relative_path_from_relative(self, tmp_path: Path) -> None:
        """Test getting relative path from relative input."""
        enforcer = WriteBoundaryEnforcer(tmp_path)
        rel = enforcer.get_relative_path("src/main.py")
        assert rel == "src/main.py"

    def test_get_relative_path_outside_raises(self, tmp_path: Path) -> None:
        """Test that getting relative path outside repo raises."""
        enforcer = WriteBoundaryEnforcer(tmp_path)
        with pytest.raises(WriteBoundaryError):
            enforcer.get_relative_path("/etc/passwd")

    def test_custom_agent_dir_name(self, tmp_path: Path) -> None:
        """Test custom agent directory name."""
        enforcer = WriteBoundaryEnforcer(
            tmp_path,
            agent_dir_name=".agent",
        )
        assert enforcer.agent_dir == tmp_path / ".agent"
        assert enforcer.is_in_agent_dir(".agent/context.md")

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        """Test that path traversal is blocked."""
        enforcer = WriteBoundaryEnforcer(tmp_path)
        # Try to escape with ..
        with pytest.raises(WriteBoundaryError):
            enforcer.validate_path("../../../etc/passwd")


class TestCreateBoundaryEnforcer:
    """Tests for create_boundary_enforcer factory."""

    def test_creates_enforcer(self, tmp_path: Path) -> None:
        """Test factory creates enforcer."""
        enforcer = create_boundary_enforcer(tmp_path)
        assert enforcer.repo_root == tmp_path.resolve()

    def test_creates_enforcer_with_artifact_dir(self, tmp_path: Path) -> None:
        """Test factory creates enforcer with artifact dir."""
        artifact_dir = tmp_path / "artifacts"
        enforcer = create_boundary_enforcer(tmp_path, artifact_dir=artifact_dir)
        assert enforcer.artifact_dir == artifact_dir.resolve()

    def test_accepts_string_paths(self, tmp_path: Path) -> None:
        """Test factory accepts string paths."""
        enforcer = create_boundary_enforcer(
            str(tmp_path),
            artifact_dir=str(tmp_path / "artifacts"),
        )
        assert enforcer.repo_root == tmp_path.resolve()


class TestWriteBoundaryScenarios:
    """Integration scenarios for write boundaries."""

    def test_allow_agent_context_files(self, tmp_path: Path) -> None:
        """Test that agent context files are allowed."""
        enforcer = WriteBoundaryEnforcer(tmp_path)

        paths = [
            "agent/context_001.md",
            "agent/context_latest.md",
            "agent/stuck_report.md",
        ]

        for path in paths:
            validated = enforcer.validate_path(path)
            assert enforcer.is_in_agent_dir(validated)

    def test_allow_source_files(self, tmp_path: Path) -> None:
        """Test that source files are allowed."""
        enforcer = WriteBoundaryEnforcer(tmp_path)

        paths = [
            "src/main.py",
            "tests/test_main.py",
            "lib/utils.js",
        ]

        for path in paths:
            validated = enforcer.validate_path(path)
            assert enforcer.is_in_repo(validated)

    def test_block_system_files(self, tmp_path: Path) -> None:
        """Test that system files are blocked."""
        enforcer = WriteBoundaryEnforcer(tmp_path)

        paths = [
            "/etc/passwd",
            "/tmp/malicious.sh",
            "/var/log/auth.log",
        ]

        for path in paths:
            with pytest.raises(WriteBoundaryError):
                enforcer.validate_path(path)

    def test_block_home_directory(self, tmp_path: Path) -> None:
        """Test that home directory files are blocked."""
        import os
        enforcer = WriteBoundaryEnforcer(tmp_path)

        home = os.path.expanduser("~")
        with pytest.raises(WriteBoundaryError):
            enforcer.validate_path(f"{home}/.bashrc")

    def test_nested_agent_directory(self, tmp_path: Path) -> None:
        """Test nested paths in agent directory."""
        enforcer = WriteBoundaryEnforcer(tmp_path)

        # Even nested paths in agent/ should be recognized
        assert enforcer.is_in_agent_dir("agent/subdir/file.md")
        validated = enforcer.validate_path("agent/subdir/file.md")
        assert enforcer.is_in_repo(validated)
