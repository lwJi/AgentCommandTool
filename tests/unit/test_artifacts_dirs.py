"""Tests for ARTIFACT_DIR directory structure management."""

import tempfile
from pathlib import Path

import pytest

from act.artifacts.dirs import (
    ArtifactDirError,
    ensure_artifact_dir_structure,
    get_cache_dir,
    get_runs_dir,
    is_artifact_dir_initialized,
)


class TestEnsureArtifactDirStructure:
    """Tests for ensure_artifact_dir_structure function."""

    def test_creates_directories_on_fresh_path(self, tmp_path: Path) -> None:
        """Fresh path creates all directories."""
        artifact_dir = tmp_path / "artifacts"

        result = ensure_artifact_dir_structure(artifact_dir)

        assert result == artifact_dir
        assert artifact_dir.is_dir()
        assert (artifact_dir / "runs").is_dir()
        assert (artifact_dir / "cache").is_dir()

    def test_idempotent_on_existing_path(self, tmp_path: Path) -> None:
        """Existing path causes no error, structure unchanged."""
        artifact_dir = tmp_path / "artifacts"

        # First call - creates structure
        ensure_artifact_dir_structure(artifact_dir)

        # Add a file to verify structure is preserved
        test_file = artifact_dir / "runs" / "test.txt"
        test_file.write_text("test content")

        # Second call - should not error or modify existing content
        result = ensure_artifact_dir_structure(artifact_dir)

        assert result == artifact_dir
        assert artifact_dir.is_dir()
        assert (artifact_dir / "runs").is_dir()
        assert (artifact_dir / "cache").is_dir()
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    def test_creates_nested_path(self, tmp_path: Path) -> None:
        """Nested path creates parent directories."""
        artifact_dir = tmp_path / "deep" / "nested" / "artifacts"

        ensure_artifact_dir_structure(artifact_dir)

        assert artifact_dir.is_dir()
        assert (artifact_dir / "runs").is_dir()
        assert (artifact_dir / "cache").is_dir()

    def test_handles_partial_structure(self, tmp_path: Path) -> None:
        """Partial existing structure is completed."""
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        (artifact_dir / "runs").mkdir()
        # cache is missing

        ensure_artifact_dir_structure(artifact_dir)

        assert (artifact_dir / "runs").is_dir()
        assert (artifact_dir / "cache").is_dir()


class TestGetRunsDir:
    """Tests for get_runs_dir function."""

    def test_returns_runs_subdirectory(self, tmp_path: Path) -> None:
        """Returns correct runs subdirectory path."""
        artifact_dir = tmp_path / "artifacts"

        runs_dir = get_runs_dir(artifact_dir)

        assert runs_dir == artifact_dir / "runs"

    def test_does_not_create_directory(self, tmp_path: Path) -> None:
        """get_runs_dir does not create the directory."""
        artifact_dir = tmp_path / "nonexistent"

        runs_dir = get_runs_dir(artifact_dir)

        assert runs_dir == artifact_dir / "runs"
        assert not runs_dir.exists()


class TestGetCacheDir:
    """Tests for get_cache_dir function."""

    def test_returns_cache_subdirectory(self, tmp_path: Path) -> None:
        """Returns correct cache subdirectory path."""
        artifact_dir = tmp_path / "artifacts"

        cache_dir = get_cache_dir(artifact_dir)

        assert cache_dir == artifact_dir / "cache"


class TestIsArtifactDirInitialized:
    """Tests for is_artifact_dir_initialized function."""

    def test_returns_true_when_initialized(self, tmp_path: Path) -> None:
        """Returns True when all directories exist."""
        artifact_dir = tmp_path / "artifacts"
        ensure_artifact_dir_structure(artifact_dir)

        assert is_artifact_dir_initialized(artifact_dir) is True

    def test_returns_false_when_missing(self, tmp_path: Path) -> None:
        """Returns False when directory doesn't exist."""
        artifact_dir = tmp_path / "nonexistent"

        assert is_artifact_dir_initialized(artifact_dir) is False

    def test_returns_false_when_partial(self, tmp_path: Path) -> None:
        """Returns False when structure is partial."""
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        (artifact_dir / "runs").mkdir()
        # cache is missing

        assert is_artifact_dir_initialized(artifact_dir) is False

    def test_returns_false_when_only_main_dir(self, tmp_path: Path) -> None:
        """Returns False when only main directory exists."""
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()

        assert is_artifact_dir_initialized(artifact_dir) is False
