"""Unit tests for Scout exception hierarchy."""

import pytest

from act.scouts.exceptions import (
    FileExclusionError,
    LLMError,
    RetryExhaustedError,
    SchemaError,
    ScoutError,
    ScoutErrorType,
)


class TestScoutErrorType:
    """Tests for ScoutErrorType enum."""

    def test_all_error_types_exist(self) -> None:
        """Test that all expected error types exist."""
        expected_types = [
            "LLM_UNAVAILABLE",
            "LLM_TIMEOUT",
            "LLM_RATE_LIMIT",
            "LLM_RESPONSE_INVALID",
            "SCHEMA_VALIDATION",
            "RETRY_EXHAUSTED",
            "UNKNOWN",
        ]
        for error_type in expected_types:
            assert hasattr(ScoutErrorType, error_type)

    def test_error_type_values(self) -> None:
        """Test error type string values."""
        assert ScoutErrorType.LLM_UNAVAILABLE.value == "llm_unavailable"
        assert ScoutErrorType.LLM_TIMEOUT.value == "llm_timeout"
        assert ScoutErrorType.LLM_RATE_LIMIT.value == "llm_rate_limit"
        assert ScoutErrorType.UNKNOWN.value == "unknown"


class TestScoutError:
    """Tests for ScoutError base exception."""

    def test_init_with_message(self) -> None:
        """Test ScoutError initialization."""
        error = ScoutError("test message")
        assert error.message == "test message"
        assert str(error) == "test message"

    def test_is_exception(self) -> None:
        """Test that ScoutError is an Exception."""
        assert issubclass(ScoutError, Exception)

    def test_can_be_raised(self) -> None:
        """Test that ScoutError can be raised and caught."""
        with pytest.raises(ScoutError) as exc_info:
            raise ScoutError("test error")
        assert exc_info.value.message == "test error"


class TestLLMError:
    """Tests for LLMError exception."""

    def test_init_with_error_type(self) -> None:
        """Test LLMError initialization."""
        error = LLMError("LLM failed", ScoutErrorType.LLM_TIMEOUT)
        assert error.message == "LLM failed"
        assert error.error_type == ScoutErrorType.LLM_TIMEOUT

    def test_is_scout_error(self) -> None:
        """Test that LLMError inherits from ScoutError."""
        assert issubclass(LLMError, ScoutError)

    def test_different_error_types(self) -> None:
        """Test LLMError with different error types."""
        for error_type in ScoutErrorType:
            error = LLMError(f"Error: {error_type.value}", error_type)
            assert error.error_type == error_type


class TestSchemaError:
    """Tests for SchemaError exception."""

    def test_init_without_payload(self) -> None:
        """Test SchemaError initialization without payload."""
        error = SchemaError("Invalid schema")
        assert error.message == "Invalid schema"
        assert error.payload is None

    def test_init_with_payload(self) -> None:
        """Test SchemaError initialization with payload."""
        payload = {"field": "value"}
        error = SchemaError("Invalid schema", payload=payload)
        assert error.message == "Invalid schema"
        assert error.payload == payload

    def test_is_scout_error(self) -> None:
        """Test that SchemaError inherits from ScoutError."""
        assert issubclass(SchemaError, ScoutError)


class TestRetryExhaustedError:
    """Tests for RetryExhaustedError exception."""

    def test_init_basic(self) -> None:
        """Test RetryExhaustedError initialization."""
        error = RetryExhaustedError("Retries exhausted", attempts=3)
        assert error.message == "Retries exhausted"
        assert error.attempts == 3
        assert error.last_error is None

    def test_init_with_last_error(self) -> None:
        """Test RetryExhaustedError with last_error."""
        last = ValueError("Original error")
        error = RetryExhaustedError("Retries exhausted", attempts=3, last_error=last)
        assert error.attempts == 3
        assert error.last_error is last

    def test_is_scout_error(self) -> None:
        """Test that RetryExhaustedError inherits from ScoutError."""
        assert issubclass(RetryExhaustedError, ScoutError)


class TestFileExclusionError:
    """Tests for FileExclusionError exception."""

    def test_init_without_file_path(self) -> None:
        """Test FileExclusionError initialization without file_path."""
        error = FileExclusionError("File excluded")
        assert error.message == "File excluded"
        assert error.file_path is None

    def test_init_with_file_path(self) -> None:
        """Test FileExclusionError initialization with file_path."""
        error = FileExclusionError("File excluded", file_path="/path/to/file")
        assert error.message == "File excluded"
        assert error.file_path == "/path/to/file"

    def test_is_scout_error(self) -> None:
        """Test that FileExclusionError inherits from ScoutError."""
        assert issubclass(FileExclusionError, ScoutError)
