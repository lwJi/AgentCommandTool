"""Unit tests for Scout file exclusion filter."""

import os
import tempfile
from pathlib import Path

import pytest

from act.scouts.file_filter import (
    BINARY_EXTENSIONS,
    EXCLUDED_DIRECTORIES,
    SECRET_PATTERNS,
    discover_files,
    filter_files,
    is_binary_file,
    is_excluded_directory,
    is_secret_file,
    should_exclude_file,
    should_exclude_path,
)


class TestBinaryExtensions:
    """Tests for binary extension list."""

    def test_common_image_extensions(self) -> None:
        """Test that common image extensions are included."""
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg"]:
            assert ext in BINARY_EXTENSIONS

    def test_common_binary_extensions(self) -> None:
        """Test that common binary extensions are included."""
        for ext in [".exe", ".dll", ".so", ".dylib"]:
            assert ext in BINARY_EXTENSIONS

    def test_archive_extensions(self) -> None:
        """Test that archive extensions are included."""
        for ext in [".zip", ".tar", ".gz"]:
            assert ext in BINARY_EXTENSIONS


class TestSecretPatterns:
    """Tests for secret file patterns."""

    def test_env_patterns(self) -> None:
        """Test that .env patterns are included."""
        assert ".env" in SECRET_PATTERNS
        assert ".env.*" in SECRET_PATTERNS

    def test_credential_patterns(self) -> None:
        """Test that credential patterns are included."""
        assert "*credentials*" in SECRET_PATTERNS
        assert "*secrets*" in SECRET_PATTERNS


class TestExcludedDirectories:
    """Tests for excluded directory list."""

    def test_common_excluded_dirs(self) -> None:
        """Test that common directories are excluded."""
        for dir_name in [".git", "node_modules", "__pycache__", ".venv"]:
            assert dir_name in EXCLUDED_DIRECTORIES


class TestIsBinaryFile:
    """Tests for is_binary_file function."""

    def test_binary_extensions(self) -> None:
        """Test that binary files are detected."""
        assert is_binary_file("image.png") is True
        assert is_binary_file("program.exe") is True
        assert is_binary_file("archive.zip") is True

    def test_non_binary_extensions(self) -> None:
        """Test that non-binary files are not flagged."""
        assert is_binary_file("code.py") is False
        assert is_binary_file("script.js") is False
        assert is_binary_file("config.yaml") is False

    def test_case_insensitive(self) -> None:
        """Test case insensitivity."""
        assert is_binary_file("image.PNG") is True
        assert is_binary_file("image.Png") is True

    def test_path_object(self) -> None:
        """Test with Path object."""
        assert is_binary_file(Path("image.png")) is True
        assert is_binary_file(Path("code.py")) is False


class TestIsSecretFile:
    """Tests for is_secret_file function."""

    def test_env_files(self) -> None:
        """Test .env file detection."""
        assert is_secret_file(".env") is True
        assert is_secret_file(".env.local") is True
        assert is_secret_file(".env.production") is True

    def test_credential_files(self) -> None:
        """Test credential file detection."""
        assert is_secret_file("credentials.json") is True
        assert is_secret_file("aws_credentials") is True
        assert is_secret_file("secrets.yaml") is True

    def test_key_files(self) -> None:
        """Test key file detection."""
        assert is_secret_file("private.pem") is True
        assert is_secret_file("server.key") is True
        assert is_secret_file("id_rsa") is True

    def test_non_secret_files(self) -> None:
        """Test that regular files are not flagged as secrets."""
        assert is_secret_file("config.yaml") is False
        assert is_secret_file("main.py") is False
        assert is_secret_file("README.md") is False

    def test_case_insensitive(self) -> None:
        """Test case insensitivity."""
        assert is_secret_file(".ENV") is True
        assert is_secret_file("CREDENTIALS.json") is True


class TestIsExcludedDirectory:
    """Tests for is_excluded_directory function."""

    def test_excluded_dirs(self) -> None:
        """Test that excluded directories are detected."""
        assert is_excluded_directory(".git") is True
        assert is_excluded_directory("node_modules") is True
        assert is_excluded_directory("__pycache__") is True

    def test_non_excluded_dirs(self) -> None:
        """Test that regular directories are not excluded."""
        assert is_excluded_directory("src") is False
        assert is_excluded_directory("lib") is False
        assert is_excluded_directory("tests") is False


class TestShouldExcludeFile:
    """Tests for should_exclude_file function."""

    def test_excludes_binary(self) -> None:
        """Test that binary files are excluded."""
        assert should_exclude_file("image.png") is True

    def test_excludes_secret(self) -> None:
        """Test that secret files are excluded."""
        assert should_exclude_file(".env") is True

    def test_allows_regular_files(self) -> None:
        """Test that regular files are allowed."""
        assert should_exclude_file("main.py") is False
        assert should_exclude_file("package.json") is False


class TestShouldExcludePath:
    """Tests for should_exclude_path function."""

    def test_excludes_files_in_excluded_dirs(self) -> None:
        """Test that files in excluded directories are excluded."""
        assert should_exclude_path("node_modules/package/index.js", "/repo") is True
        assert should_exclude_path(".git/config", "/repo") is True

    def test_excludes_binary_in_any_dir(self) -> None:
        """Test that binary files are excluded anywhere."""
        assert should_exclude_path("src/images/logo.png", "/repo") is True

    def test_allows_regular_files(self) -> None:
        """Test that regular files are allowed."""
        assert should_exclude_path("src/main.py", "/repo") is False

    def test_handles_absolute_paths(self) -> None:
        """Test with absolute paths."""
        assert should_exclude_path("/repo/src/main.py", "/repo") is False
        assert should_exclude_path("/repo/node_modules/x.js", "/repo") is True

    def test_path_outside_repo(self) -> None:
        """Test that paths outside repo are excluded."""
        assert should_exclude_path("/other/file.py", "/repo") is True


class TestFilterFiles:
    """Tests for filter_files function."""

    def test_filters_binary_files(self) -> None:
        """Test that binary files are filtered out."""
        files = ["main.py", "image.png", "script.js", "icon.ico"]
        result = filter_files(files, "/repo")
        assert "main.py" in result
        assert "script.js" in result
        assert "image.png" not in result
        assert "icon.ico" not in result

    def test_filters_secret_files(self) -> None:
        """Test that secret files are filtered out."""
        files = ["main.py", ".env", "config.yaml", "credentials.json"]
        result = filter_files(files, "/repo")
        assert "main.py" in result
        assert "config.yaml" in result
        assert ".env" not in result
        assert "credentials.json" not in result

    def test_empty_list(self) -> None:
        """Test with empty file list."""
        result = filter_files([], "/repo")
        assert result == []


class TestDiscoverFiles:
    """Tests for discover_files function."""

    def test_discovers_files(self) -> None:
        """Test that files are discovered in a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files
            Path(tmpdir, "main.py").write_text("print('hello')")
            Path(tmpdir, "lib.py").write_text("def foo(): pass")
            Path(tmpdir, "config.yaml").write_text("key: value")

            files = discover_files(tmpdir)

            assert "main.py" in files
            assert "lib.py" in files
            assert "config.yaml" in files

    def test_excludes_binary_files(self) -> None:
        """Test that binary files are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("print('hello')")
            Path(tmpdir, "image.png").write_bytes(b"\x89PNG\r\n")

            files = discover_files(tmpdir)

            assert "main.py" in files
            assert "image.png" not in files

    def test_excludes_secret_files(self) -> None:
        """Test that secret files are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("print('hello')")
            Path(tmpdir, ".env").write_text("SECRET=value")

            files = discover_files(tmpdir)

            assert "main.py" in files
            assert ".env" not in files

    def test_skips_excluded_directories(self) -> None:
        """Test that excluded directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src", "main.py").write_text("print('hello')")
            Path(tmpdir, "node_modules").mkdir()
            Path(tmpdir, "node_modules", "pkg.js").write_text("module.exports = {}")

            files = discover_files(tmpdir)

            # Files in src should be included
            assert any("main.py" in f for f in files)
            # Files in node_modules should not
            assert not any("node_modules" in f for f in files)

    def test_max_files_limit(self) -> None:
        """Test that max_files limit is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many files
            for i in range(20):
                Path(tmpdir, f"file{i}.py").write_text(f"# file {i}")

            files = discover_files(tmpdir, max_files=5)

            assert len(files) == 5

    def test_nested_directories(self) -> None:
        """Test discovery in nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "a", "b", "c").mkdir(parents=True)
            Path(tmpdir, "a", "b", "c", "deep.py").write_text("# deep")

            files = discover_files(tmpdir)

            assert any("deep.py" in f for f in files)
