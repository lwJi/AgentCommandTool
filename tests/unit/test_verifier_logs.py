"""Tests for verifier log utilities."""

from pathlib import Path

from act.verifier.logs import (
    TAIL_LOG_LINES,
    append_combined_log,
    create_db_dir,
    create_logs_dir,
    create_tmp_dir,
    extract_tail_log,
    get_step_log_filename,
    list_artifact_paths,
    write_step_log,
)


class TestCreateLogsDir:
    """Tests for create_logs_dir function."""

    def test_creates_logs_directory(self, tmp_path: Path) -> None:
        """Creates logs subdirectory in run directory."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()

        logs_dir = create_logs_dir(run_dir)

        assert logs_dir.exists()
        assert logs_dir.is_dir()
        assert logs_dir == run_dir / "logs"

    def test_returns_path_to_logs_dir(self, tmp_path: Path) -> None:
        """Returns path to created logs directory."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()

        result = create_logs_dir(run_dir)

        assert result == run_dir / "logs"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Creates parent directories if needed."""
        run_dir = tmp_path / "deep" / "nested" / "run_test"

        logs_dir = create_logs_dir(run_dir)

        assert logs_dir.exists()

    def test_handles_existing_directory(self, tmp_path: Path) -> None:
        """Handles existing logs directory gracefully."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        existing_logs = run_dir / "logs"
        existing_logs.mkdir()

        logs_dir = create_logs_dir(run_dir)

        assert logs_dir.exists()
        assert logs_dir == existing_logs


class TestCreateTmpDir:
    """Tests for create_tmp_dir function."""

    def test_creates_tmp_directory(self, tmp_path: Path) -> None:
        """Creates tmp subdirectory in run directory."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()

        tmp_dir = create_tmp_dir(run_dir)

        assert tmp_dir.exists()
        assert tmp_dir.is_dir()
        assert tmp_dir == run_dir / "tmp"

    def test_handles_existing_directory(self, tmp_path: Path) -> None:
        """Handles existing tmp directory gracefully."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        existing_tmp = run_dir / "tmp"
        existing_tmp.mkdir()

        tmp_dir = create_tmp_dir(run_dir)

        assert tmp_dir.exists()


class TestCreateDbDir:
    """Tests for create_db_dir function."""

    def test_creates_db_directory(self, tmp_path: Path) -> None:
        """Creates db subdirectory in run directory."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()

        db_dir = create_db_dir(run_dir)

        assert db_dir.exists()
        assert db_dir.is_dir()
        assert db_dir == run_dir / "db"


class TestGetStepLogFilename:
    """Tests for get_step_log_filename function."""

    def test_returns_formatted_filename(self) -> None:
        """Returns correctly formatted filename."""
        filename = get_step_log_filename(1, "install")

        assert filename == "step-01-install.log"

    def test_zero_pads_step_number(self) -> None:
        """Zero-pads step number to 2 digits."""
        assert get_step_log_filename(1, "test") == "step-01-test.log"
        assert get_step_log_filename(5, "build") == "step-05-build.log"
        assert get_step_log_filename(12, "lint") == "step-12-lint.log"

    def test_handles_various_step_names(self) -> None:
        """Handles various step names correctly."""
        assert get_step_log_filename(1, "install") == "step-01-install.log"
        assert get_step_log_filename(2, "typecheck") == "step-02-typecheck.log"
        assert get_step_log_filename(3, "build") == "step-03-build.log"
        assert get_step_log_filename(4, "test") == "step-04-test.log"


class TestExtractTailLog:
    """Tests for extract_tail_log function."""

    def test_returns_last_n_lines(self, tmp_path: Path) -> None:
        """Returns last N lines of log."""
        log_path = tmp_path / "combined.log"
        lines = [f"Line {i}" for i in range(500)]
        log_path.write_text("\n".join(lines))

        result = extract_tail_log(log_path, lines=200)
        result_lines = result.split("\n")

        assert len(result_lines) == 200
        assert result_lines[0] == "Line 300"
        assert result_lines[-1] == "Line 499"

    def test_returns_all_lines_when_less_than_n(self, tmp_path: Path) -> None:
        """Returns all lines when log has fewer than N lines."""
        log_path = tmp_path / "combined.log"
        lines = [f"Line {i}" for i in range(50)]
        log_path.write_text("\n".join(lines))

        result = extract_tail_log(log_path, lines=200)
        result_lines = result.split("\n")

        assert len(result_lines) == 50
        assert result_lines[0] == "Line 0"
        assert result_lines[-1] == "Line 49"

    def test_returns_empty_string_for_empty_log(self, tmp_path: Path) -> None:
        """Returns empty string for empty log file."""
        log_path = tmp_path / "combined.log"
        log_path.write_text("")

        result = extract_tail_log(log_path)

        assert result == ""

    def test_returns_empty_string_for_missing_log(self, tmp_path: Path) -> None:
        """Returns empty string when log file doesn't exist."""
        log_path = tmp_path / "nonexistent.log"

        result = extract_tail_log(log_path)

        assert result == ""

    def test_uses_default_200_lines(self, tmp_path: Path) -> None:
        """Uses default of 200 lines."""
        assert TAIL_LOG_LINES == 200

        log_path = tmp_path / "combined.log"
        lines = [f"Line {i}" for i in range(300)]
        log_path.write_text("\n".join(lines))

        result = extract_tail_log(log_path)
        result_lines = result.split("\n")

        assert len(result_lines) == 200

    def test_handles_single_line(self, tmp_path: Path) -> None:
        """Handles single line log correctly."""
        log_path = tmp_path / "combined.log"
        log_path.write_text("Single line")

        result = extract_tail_log(log_path)

        assert result == "Single line"


class TestListArtifactPaths:
    """Tests for list_artifact_paths function."""

    def test_lists_all_files(self, tmp_path: Path) -> None:
        """Lists all files in run directory."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text("{}")
        logs_dir = run_dir / "logs"
        logs_dir.mkdir()
        (logs_dir / "combined.log").write_text("test")
        (logs_dir / "step-01-test.log").write_text("test")

        paths = list_artifact_paths(run_dir)

        assert len(paths) == 3
        assert str(run_dir / "manifest.json") in paths
        assert str(logs_dir / "combined.log") in paths
        assert str(logs_dir / "step-01-test.log") in paths

    def test_returns_sorted_paths(self, tmp_path: Path) -> None:
        """Returns paths in sorted order."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        (run_dir / "z_file.txt").write_text("z")
        (run_dir / "a_file.txt").write_text("a")

        paths = list_artifact_paths(run_dir)

        assert paths[0].endswith("a_file.txt")
        assert paths[1].endswith("z_file.txt")

    def test_returns_absolute_paths(self, tmp_path: Path) -> None:
        """Returns absolute paths."""
        run_dir = tmp_path / "run_test"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("test")

        paths = list_artifact_paths(run_dir)

        assert all(Path(p).is_absolute() for p in paths)

    def test_returns_empty_for_nonexistent_directory(self, tmp_path: Path) -> None:
        """Returns empty list for nonexistent directory."""
        run_dir = tmp_path / "nonexistent"

        paths = list_artifact_paths(run_dir)

        assert paths == []

    def test_returns_empty_for_empty_directory(self, tmp_path: Path) -> None:
        """Returns empty list for empty directory."""
        run_dir = tmp_path / "empty"
        run_dir.mkdir()

        paths = list_artifact_paths(run_dir)

        assert paths == []


class TestWriteStepLog:
    """Tests for write_step_log function."""

    def test_writes_log_file(self, tmp_path: Path) -> None:
        """Writes step output to log file."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        log_path = write_step_log(logs_dir, 1, "install", "npm install output")

        assert log_path.exists()
        assert log_path.read_text() == "npm install output"

    def test_uses_correct_filename(self, tmp_path: Path) -> None:
        """Uses correct filename format."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        log_path = write_step_log(logs_dir, 2, "build", "build output")

        assert log_path.name == "step-02-build.log"

    def test_returns_path_to_log(self, tmp_path: Path) -> None:
        """Returns path to written log file."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        log_path = write_step_log(logs_dir, 1, "test", "test output")

        assert log_path == logs_dir / "step-01-test.log"


class TestAppendCombinedLog:
    """Tests for append_combined_log function."""

    def test_creates_file_on_first_write(self, tmp_path: Path) -> None:
        """Creates combined.log on first write."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        combined_path = append_combined_log(logs_dir, "first output")

        assert combined_path.exists()
        assert combined_path.name == "combined.log"

    def test_appends_to_existing_file(self, tmp_path: Path) -> None:
        """Appends to existing combined.log."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        append_combined_log(logs_dir, "first output\n")
        append_combined_log(logs_dir, "second output\n")

        combined_path = logs_dir / "combined.log"
        content = combined_path.read_text()

        assert "first output" in content
        assert "second output" in content

    def test_adds_newline_if_missing(self, tmp_path: Path) -> None:
        """Adds newline at end if output doesn't have one."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        append_combined_log(logs_dir, "no newline")

        combined_path = logs_dir / "combined.log"
        content = combined_path.read_text()

        assert content.endswith("\n")

    def test_preserves_existing_newline(self, tmp_path: Path) -> None:
        """Preserves existing newline at end."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        append_combined_log(logs_dir, "has newline\n")

        combined_path = logs_dir / "combined.log"
        content = combined_path.read_text()

        # Should not have double newlines
        assert content == "has newline\n"

    def test_returns_path_to_combined_log(self, tmp_path: Path) -> None:
        """Returns path to combined log file."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        combined_path = append_combined_log(logs_dir, "test")

        assert combined_path == logs_dir / "combined.log"
