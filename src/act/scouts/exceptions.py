"""Exception hierarchy for Scout components."""

from enum import Enum


class ScoutErrorType(Enum):
    """Types of Scout infrastructure errors."""

    LLM_UNAVAILABLE = "llm_unavailable"
    LLM_TIMEOUT = "llm_timeout"
    LLM_RATE_LIMIT = "llm_rate_limit"
    LLM_RESPONSE_INVALID = "llm_response_invalid"
    SCHEMA_VALIDATION = "schema_validation"
    RETRY_EXHAUSTED = "retry_exhausted"
    UNKNOWN = "unknown"


class ScoutError(Exception):
    """Base exception for all Scout errors."""

    def __init__(self, message: str) -> None:
        """Initialize ScoutError.

        Args:
            message: Error description.
        """
        self.message = message
        super().__init__(message)


class LLMError(ScoutError):
    """Exception for LLM-related errors."""

    def __init__(self, message: str, error_type: ScoutErrorType) -> None:
        """Initialize LLMError.

        Args:
            message: Error description.
            error_type: Type of LLM error.
        """
        self.error_type = error_type
        super().__init__(message)


class SchemaError(ScoutError):
    """Exception for schema validation errors."""

    def __init__(self, message: str, payload: dict[str, object] | None = None) -> None:
        """Initialize SchemaError.

        Args:
            message: Error description.
            payload: The invalid payload that failed validation.
        """
        self.payload = payload
        super().__init__(message)


class RetryExhaustedError(ScoutError):
    """Exception raised when all retries have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_error: Exception | None = None,
    ) -> None:
        """Initialize RetryExhaustedError.

        Args:
            message: Error description.
            attempts: Number of attempts made.
            last_error: The last error that occurred.
        """
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(message)


class FileExclusionError(ScoutError):
    """Exception for file exclusion filter errors."""

    def __init__(self, message: str, file_path: str | None = None) -> None:
        """Initialize FileExclusionError.

        Args:
            message: Error description.
            file_path: Path to the file that caused the error.
        """
        self.file_path = file_path
        super().__init__(message)
