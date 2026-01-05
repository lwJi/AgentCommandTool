"""Unit tests for Editor exceptions."""


from act.editor.exceptions import (
    EditorError,
    EditorErrorType,
    HardStopError,
    ImplementationError,
    InfrastructureError,
    ScoutCoordinationError,
    TaskParseError,
    WriteBoundaryError,
)


class TestEditorErrorType:
    """Tests for EditorErrorType enum."""

    def test_all_types_defined(self) -> None:
        """Test that all expected error types are defined."""
        expected = [
            "TASK_PARSE",
            "SCOUT_FAILURE",
            "VERIFICATION_FAILURE",
            "IMPLEMENTATION",
            "WRITE_BOUNDARY",
            "HARD_STOP",
            "INFRA_ERROR",
            "UNKNOWN",
        ]
        actual = [e.name for e in EditorErrorType]
        assert set(expected) == set(actual)

    def test_error_type_values(self) -> None:
        """Test that error type values are strings."""
        for error_type in EditorErrorType:
            assert isinstance(error_type.value, str)


class TestEditorError:
    """Tests for EditorError base exception."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = EditorError("Test error")
        assert str(error) == "Test error"
        assert error.error_type == EditorErrorType.UNKNOWN

    def test_error_with_type(self) -> None:
        """Test error with specific type."""
        error = EditorError("Test error", EditorErrorType.TASK_PARSE)
        assert error.error_type == EditorErrorType.TASK_PARSE

    def test_is_exception(self) -> None:
        """Test that EditorError is an Exception."""
        error = EditorError("Test")
        assert isinstance(error, Exception)


class TestTaskParseError:
    """Tests for TaskParseError."""

    def test_task_parse_error(self) -> None:
        """Test TaskParseError creation."""
        error = TaskParseError("Invalid task format")
        assert str(error) == "Invalid task format"
        assert error.error_type == EditorErrorType.TASK_PARSE

    def test_inherits_from_editor_error(self) -> None:
        """Test that TaskParseError inherits from EditorError."""
        error = TaskParseError("Test")
        assert isinstance(error, EditorError)


class TestScoutCoordinationError:
    """Tests for ScoutCoordinationError."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = ScoutCoordinationError("Scout failed")
        assert str(error) == "Scout failed"
        assert error.error_type == EditorErrorType.SCOUT_FAILURE
        assert error.scout_name == ""

    def test_with_scout_name(self) -> None:
        """Test error with scout name."""
        error = ScoutCoordinationError("Scout A query failed", scout_name="Scout A")
        assert error.scout_name == "Scout A"


class TestImplementationError:
    """Tests for ImplementationError."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = ImplementationError("Failed to implement")
        assert str(error) == "Failed to implement"
        assert error.error_type == EditorErrorType.IMPLEMENTATION
        assert error.file_path == ""

    def test_with_file_path(self) -> None:
        """Test error with file path."""
        error = ImplementationError("Write failed", file_path="/src/main.py")
        assert error.file_path == "/src/main.py"


class TestWriteBoundaryError:
    """Tests for WriteBoundaryError."""

    def test_write_boundary_error(self) -> None:
        """Test WriteBoundaryError creation."""
        error = WriteBoundaryError(
            "Path outside boundary",
            attempted_path="/etc/passwd",
        )
        assert str(error) == "Path outside boundary"
        assert error.error_type == EditorErrorType.WRITE_BOUNDARY
        assert error.attempted_path == "/etc/passwd"


class TestHardStopError:
    """Tests for HardStopError."""

    def test_hard_stop_error(self) -> None:
        """Test HardStopError creation."""
        run_ids = ["run_001", "run_002", "run_003"]
        error = HardStopError(
            "Hard stop reached",
            total_attempts=12,
            run_ids=run_ids,
        )
        assert str(error) == "Hard stop reached"
        assert error.error_type == EditorErrorType.HARD_STOP
        assert error.total_attempts == 12
        assert error.run_ids == run_ids

    def test_empty_run_ids(self) -> None:
        """Test HardStopError with empty run_ids."""
        error = HardStopError("Hard stop", total_attempts=0, run_ids=[])
        assert error.run_ids == []


class TestInfrastructureError:
    """Tests for InfrastructureError."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = InfrastructureError("Docker unavailable", source="verifier")
        assert str(error) == "Docker unavailable"
        assert error.error_type == EditorErrorType.INFRA_ERROR
        assert error.source == "verifier"
        assert error.original_error is None

    def test_with_original_error(self) -> None:
        """Test error with original exception."""
        original = ConnectionError("Network down")
        error = InfrastructureError(
            "LLM API failed",
            source="scout_a",
            original_error=original,
        )
        assert error.source == "scout_a"
        assert error.original_error is original

    def test_different_sources(self) -> None:
        """Test different error sources."""
        sources = ["verifier", "scout_a", "scout_b"]
        for source in sources:
            error = InfrastructureError("Error", source=source)
            assert error.source == source
