"""Editor exceptions hierarchy.

Defines exception classes for Editor operations including task parsing,
implementation, verification, and coordination errors.
"""

from enum import Enum


class EditorErrorType(Enum):
    """Types of Editor errors."""

    TASK_PARSE = "task_parse"
    SCOUT_FAILURE = "scout_failure"
    VERIFICATION_FAILURE = "verification_failure"
    IMPLEMENTATION = "implementation"
    WRITE_BOUNDARY = "write_boundary"
    HARD_STOP = "hard_stop"
    INFRA_ERROR = "infra_error"
    UNKNOWN = "unknown"


class EditorError(Exception):
    """Base exception for all Editor errors."""

    def __init__(
        self,
        message: str,
        error_type: EditorErrorType = EditorErrorType.UNKNOWN,
    ) -> None:
        """Initialize EditorError.

        Args:
            message: Error message.
            error_type: Type of error.
        """
        super().__init__(message)
        self.error_type = error_type


class TaskParseError(EditorError):
    """Error parsing task description."""

    def __init__(self, message: str) -> None:
        """Initialize TaskParseError.

        Args:
            message: Error message.
        """
        super().__init__(message, EditorErrorType.TASK_PARSE)


class ScoutCoordinationError(EditorError):
    """Error coordinating with Scouts."""

    def __init__(self, message: str, scout_name: str = "") -> None:
        """Initialize ScoutCoordinationError.

        Args:
            message: Error message.
            scout_name: Name of the Scout that failed (optional).
        """
        super().__init__(message, EditorErrorType.SCOUT_FAILURE)
        self.scout_name = scout_name


class ImplementationError(EditorError):
    """Error during implementation."""

    def __init__(self, message: str, file_path: str = "") -> None:
        """Initialize ImplementationError.

        Args:
            message: Error message.
            file_path: Path to the file where error occurred.
        """
        super().__init__(message, EditorErrorType.IMPLEMENTATION)
        self.file_path = file_path


class WriteBoundaryError(EditorError):
    """Error when attempting to write outside allowed boundaries."""

    def __init__(self, message: str, attempted_path: str) -> None:
        """Initialize WriteBoundaryError.

        Args:
            message: Error message.
            attempted_path: Path that was attempted to be written.
        """
        super().__init__(message, EditorErrorType.WRITE_BOUNDARY)
        self.attempted_path = attempted_path


class HardStopError(EditorError):
    """Error when hard stop threshold is reached."""

    def __init__(
        self,
        message: str,
        total_attempts: int,
        run_ids: list[str],
    ) -> None:
        """Initialize HardStopError.

        Args:
            message: Error message.
            total_attempts: Total number of verification attempts.
            run_ids: List of all run_ids from failed attempts.
        """
        super().__init__(message, EditorErrorType.HARD_STOP)
        self.total_attempts = total_attempts
        self.run_ids = run_ids


class InfrastructureError(EditorError):
    """Error when infrastructure failure occurs."""

    def __init__(
        self,
        message: str,
        source: str,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize InfrastructureError.

        Args:
            message: Error message.
            source: Source of the error (e.g., "verifier", "scout_a", "scout_b").
            original_error: The original exception that caused this error.
        """
        super().__init__(message, EditorErrorType.INFRA_ERROR)
        self.source = source
        self.original_error = original_error
