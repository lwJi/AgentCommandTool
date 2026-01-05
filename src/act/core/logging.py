"""Structured logging for AgentCommandTool.

Provides:
- JSON-formatted log output
- Context-aware logging
- Log level management
- State transition logging
- Scout query logging
- Verifier result logging
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TextIO


class LogLevel(Enum):
    """Log levels."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LogEntry:
    """A structured log entry."""

    timestamp: str
    level: str
    message: str
    component: str
    event_type: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    duration_ms: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert to JSON string."""
        data = {k: v for k, v in asdict(self).items() if v is not None}
        # Remove empty extra dict
        if "extra" in data and not data["extra"]:
            del data["extra"]
        return json.dumps(data, default=str)

    def to_human_readable(self) -> str:
        """Convert to human-readable format."""
        parts = [f"[{self.timestamp}]", f"[{self.level}]", f"[{self.component}]"]
        if self.event_type:
            parts.append(f"[{self.event_type}]")
        parts.append(self.message)
        return " ".join(parts)


class StructuredLogger:
    """Structured logger for the system.

    Logs events in JSON format with consistent structure.
    Supports:
    - State transitions
    - Scout queries (summarized)
    - Verifier triggers and results
    """

    def __init__(
        self,
        component: str,
        level: LogLevel = LogLevel.INFO,
        output: TextIO | None = None,
        json_format: bool = True,
    ) -> None:
        """Initialize logger.

        Args:
            component: Component name (editor, scout_a, scout_b, verifier, runner)
            level: Minimum log level
            output: Output stream (defaults to stderr)
            json_format: Whether to use JSON format
        """
        self.component = component
        self.level = level
        self.output = output or sys.stderr
        self.json_format = json_format
        self._context: dict[str, Any] = {}

    def set_context(self, **kwargs: Any) -> None:
        """Set persistent context for all log entries."""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear persistent context."""
        self._context.clear()

    def with_context(self, **kwargs: Any) -> StructuredLogger:
        """Create a new logger with additional context.

        Args:
            **kwargs: Context key-value pairs

        Returns:
            New logger instance with merged context
        """
        new_logger = StructuredLogger(
            component=self.component,
            level=self.level,
            output=self.output,
            json_format=self.json_format,
        )
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _log(
        self,
        level: LogLevel,
        message: str,
        event_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Internal log method."""
        if level.value < self.level.value:
            return

        # Extract special fields from kwargs
        run_id = kwargs.pop("run_id", None)
        duration_ms = kwargs.pop("duration_ms", None)

        # Merge context with kwargs
        extra = {**self._context, **kwargs}

        entry = LogEntry(
            timestamp=datetime.now(UTC).isoformat(),
            level=level.name,
            message=message,
            component=self.component,
            event_type=event_type,
            task_id=extra.pop("task_id", None),
            run_id=run_id,
            duration_ms=duration_ms,
            extra=extra,
        )

        if self.json_format:
            self.output.write(entry.to_json() + "\n")
        else:
            self.output.write(entry.to_human_readable() + "\n")
        self.output.flush()

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, **kwargs)

    # Specialized logging methods

    def log_state_transition(
        self,
        from_state: str,
        to_state: str,
        reason: str = "",
    ) -> None:
        """Log a state transition.

        Args:
            from_state: Previous state
            to_state: New state
            reason: Reason for transition
        """
        self._log(
            LogLevel.INFO,
            f"State transition: {from_state} -> {to_state}",
            event_type="state_transition",
            from_state=from_state,
            to_state=to_state,
            reason=reason,
        )

    def log_scout_query(
        self,
        scout_name: str,
        query_summary: str,
        duration_ms: int,
        success: bool,
    ) -> None:
        """Log a Scout query (summarized).

        Args:
            scout_name: Name of scout (scout_a, scout_b)
            query_summary: Brief summary of query (truncated to 200 chars)
            duration_ms: Query duration in milliseconds
            success: Whether query succeeded
        """
        self._log(
            LogLevel.INFO,
            f"Scout query: {scout_name}",
            event_type="scout_query",
            scout_name=scout_name,
            query_summary=query_summary[:200] if query_summary else "",
            duration_ms=duration_ms,
            success=success,
        )

    def log_verifier_trigger(
        self,
        run_id: str,
        attempt_number: int,
    ) -> None:
        """Log a Verifier trigger.

        Args:
            run_id: Verification run ID
            attempt_number: Current attempt number
        """
        self._log(
            LogLevel.INFO,
            f"Verification triggered: attempt {attempt_number}",
            event_type="verifier_trigger",
            run_id=run_id,
            attempt_number=attempt_number,
        )

    def log_verifier_result(
        self,
        run_id: str,
        status: str,
        duration_ms: int,
    ) -> None:
        """Log a Verifier result.

        Args:
            run_id: Verification run ID
            status: Verification status (PASS, FAIL, INFRA_ERROR)
            duration_ms: Verification duration in milliseconds
        """
        self._log(
            LogLevel.INFO,
            f"Verification result: {status}",
            event_type="verifier_result",
            run_id=run_id,
            status=status,
            duration_ms=duration_ms,
        )

    def log_replan(
        self,
        attempt_number: int,
        new_strategy_summary: str,
    ) -> None:
        """Log a REPLAN event.

        Args:
            attempt_number: Current attempt number when REPLAN triggered
            new_strategy_summary: Brief summary of new strategy (truncated)
        """
        self._log(
            LogLevel.INFO,
            f"REPLAN triggered at attempt {attempt_number}",
            event_type="replan",
            attempt_number=attempt_number,
            strategy_summary=new_strategy_summary[:200] if new_strategy_summary else "",
        )

    def log_task_start(
        self,
        task_id: str,
        task_description: str,
        dry_run: bool = False,
    ) -> None:
        """Log task start.

        Args:
            task_id: Task identifier
            task_description: Task description (truncated)
            dry_run: Whether this is a dry-run
        """
        self._log(
            LogLevel.INFO,
            f"Task started: {task_id}",
            event_type="task_start",
            task_id=task_id,
            task_description=task_description[:200] if task_description else "",
            dry_run=dry_run,
        )

    def log_task_end(
        self,
        task_id: str,
        final_state: str,
        duration_ms: int | None = None,
    ) -> None:
        """Log task completion.

        Args:
            task_id: Task identifier
            final_state: Final task state
            duration_ms: Total task duration in milliseconds
        """
        self._log(
            LogLevel.INFO,
            f"Task completed: {task_id} -> {final_state}",
            event_type="task_end",
            task_id=task_id,
            final_state=final_state,
            duration_ms=duration_ms,
        )


def create_logger(
    component: str,
    level: LogLevel = LogLevel.INFO,
    json_format: bool = True,
    output: TextIO | None = None,
) -> StructuredLogger:
    """Create a structured logger.

    Args:
        component: Component name
        level: Minimum log level
        json_format: Whether to use JSON format
        output: Output stream (defaults to stderr)

    Returns:
        Configured logger
    """
    return StructuredLogger(
        component=component,
        level=level,
        json_format=json_format,
        output=output,
    )


# Global loggers for each component
_loggers: dict[str, StructuredLogger] = {}


def get_logger(component: str) -> StructuredLogger:
    """Get or create a logger for a component.

    Args:
        component: Component name

    Returns:
        Logger instance
    """
    if component not in _loggers:
        _loggers[component] = create_logger(component)
    return _loggers[component]


def reset_loggers() -> None:
    """Reset all global loggers. Useful for testing."""
    _loggers.clear()


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    json_format: bool = True,
    output: TextIO | None = None,
) -> None:
    """Configure global logging settings.

    Args:
        level: Minimum log level for all loggers
        json_format: Whether to use JSON format
        output: Output stream
    """
    for logger in _loggers.values():
        logger.level = level
        logger.json_format = json_format
        if output is not None:
            logger.output = output
