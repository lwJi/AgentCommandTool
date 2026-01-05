"""Centralized error handling with graceful degradation.

Provides:
- Global exception handler for unexpected errors
- Context-aware error logging
- Automatic state transition to appropriate terminal state
"""

from __future__ import annotations

import contextlib
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from act.core.logging import StructuredLogger


class ErrorSeverity(Enum):
    """Severity levels for errors."""

    WARNING = "warning"  # Non-fatal, continue execution
    ERROR = "error"  # Task-level failure, transition to error state
    CRITICAL = "critical"  # System-level failure, shutdown required


@dataclass
class ErrorContext:
    """Context information for error handling."""

    operation: str  # What was being attempted
    component: str  # Which component failed (editor, scout, verifier)
    task_id: str | None = None  # Associated task ID
    additional_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        result: dict[str, Any] = {
            "operation": self.operation,
            "component": self.component,
        }
        if self.task_id is not None:
            result["task_id"] = self.task_id
        if self.additional_info:
            result["additional_info"] = self.additional_info
        return result


class GracefulErrorHandler:
    """Handles errors gracefully without crashing.

    Ensures:
    - Errors are logged with full context
    - Task transitions to appropriate terminal state
    - System remains stable after errors
    """

    def __init__(
        self,
        logger: StructuredLogger | None = None,
        on_error: Callable[[ErrorContext, Exception], None] | None = None,
    ) -> None:
        """Initialize error handler.

        Args:
            logger: Structured logger instance
            on_error: Callback for error notifications
        """
        self._logger = logger
        self._on_error = on_error

    def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
    ) -> str:
        """Handle an error gracefully.

        Args:
            error: The exception that occurred
            context: Error context information
            severity: How severe the error is

        Returns:
            Recommended TaskState value as string
        """
        # Log the error with context
        self._log_error(error, context, severity)

        # Notify callback if set (suppress callback errors)
        if self._on_error:
            with contextlib.suppress(Exception):
                self._on_error(context, error)

        # Determine appropriate state
        return self._determine_state(error, context, severity)

    def _log_error(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity,
    ) -> None:
        """Log error with full context."""
        if self._logger is None:
            return

        log_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "severity": severity.value,
            **context.to_dict(),
            "traceback": traceback.format_exc(),
        }

        if severity == ErrorSeverity.CRITICAL:
            self._logger.critical("Critical error occurred", **log_data)
        elif severity == ErrorSeverity.ERROR:
            self._logger.error("Error occurred", **log_data)
        else:
            self._logger.warning("Warning occurred", **log_data)

    def _determine_state(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity,
    ) -> str:
        """Determine appropriate task state based on error.

        Args:
            error: The exception that occurred
            context: Error context information
            severity: Error severity

        Returns:
            Recommended TaskState value as string
        """
        # Import here to avoid circular imports
        try:
            from act.editor.exceptions import HardStopError, InfrastructureError
        except ImportError:
            # If imports fail, default to INFRA_ERROR
            return "INFRA_ERROR"

        # Infrastructure errors -> INFRA_ERROR state
        if isinstance(error, InfrastructureError):
            return "INFRA_ERROR"

        # Hard stop -> STUCK state
        if isinstance(error, HardStopError):
            return "STUCK"

        # Critical severity always leads to INFRA_ERROR
        if severity == ErrorSeverity.CRITICAL:
            return "INFRA_ERROR"

        # Default to INFRA_ERROR for unexpected errors
        return "INFRA_ERROR"

    def wrap_operation(
        self,
        operation: Callable[[], Any],
        context: ErrorContext,
        default_return: Any = None,
    ) -> Any:
        """Wrap an operation with error handling.

        Args:
            operation: The operation to execute
            context: Error context for logging
            default_return: Value to return on error

        Returns:
            Operation result or default_return on error
        """
        try:
            return operation()
        except Exception as e:
            self.handle_error(e, context)
            return default_return


def create_error_handler(
    logger: StructuredLogger | None = None,
    on_error: Callable[[ErrorContext, Exception], None] | None = None,
) -> GracefulErrorHandler:
    """Create a graceful error handler.

    Args:
        logger: Structured logger instance
        on_error: Error callback

    Returns:
        Configured error handler
    """
    return GracefulErrorHandler(logger=logger, on_error=on_error)


# Global error handler
_error_handler: GracefulErrorHandler | None = None


def get_error_handler() -> GracefulErrorHandler:
    """Get the global error handler.

    Returns:
        GracefulErrorHandler instance
    """
    global _error_handler
    if _error_handler is None:
        _error_handler = GracefulErrorHandler()
    return _error_handler


def set_error_handler(handler: GracefulErrorHandler) -> None:
    """Set the global error handler.

    Args:
        handler: Error handler to use
    """
    global _error_handler
    _error_handler = handler


def reset_error_handler() -> None:
    """Reset the global error handler. Useful for testing."""
    global _error_handler
    _error_handler = None
