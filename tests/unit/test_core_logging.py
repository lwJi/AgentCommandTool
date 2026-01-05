"""Unit tests for act.core.logging module."""

from __future__ import annotations

import json
from io import StringIO

import pytest

from act.core.logging import (
    LogEntry,
    LogLevel,
    StructuredLogger,
    configure_logging,
    create_logger,
    get_logger,
    reset_loggers,
)


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_levels_have_correct_values(self) -> None:
        """Log levels have expected numeric values."""
        assert LogLevel.DEBUG.value == 10
        assert LogLevel.INFO.value == 20
        assert LogLevel.WARNING.value == 30
        assert LogLevel.ERROR.value == 40
        assert LogLevel.CRITICAL.value == 50

    def test_log_levels_are_ordered(self) -> None:
        """Log levels can be compared by value."""
        assert LogLevel.DEBUG.value < LogLevel.INFO.value
        assert LogLevel.INFO.value < LogLevel.WARNING.value
        assert LogLevel.WARNING.value < LogLevel.ERROR.value
        assert LogLevel.ERROR.value < LogLevel.CRITICAL.value


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_to_json_includes_required_fields(self) -> None:
        """JSON output includes all required fields."""
        entry = LogEntry(
            timestamp="2024-01-15T12:00:00Z",
            level="INFO",
            message="Test message",
            component="test",
        )
        data = json.loads(entry.to_json())
        assert data["timestamp"] == "2024-01-15T12:00:00Z"
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["component"] == "test"

    def test_to_json_excludes_none_fields(self) -> None:
        """JSON output excludes None optional fields."""
        entry = LogEntry(
            timestamp="2024-01-15T12:00:00Z",
            level="INFO",
            message="Test",
            component="test",
            event_type=None,
            task_id=None,
        )
        data = json.loads(entry.to_json())
        assert "event_type" not in data
        assert "task_id" not in data

    def test_to_json_includes_optional_fields_when_set(self) -> None:
        """JSON output includes optional fields when they have values."""
        entry = LogEntry(
            timestamp="2024-01-15T12:00:00Z",
            level="INFO",
            message="Test",
            component="test",
            event_type="state_transition",
            task_id="task_001",
            run_id="run_001",
            duration_ms=100,
        )
        data = json.loads(entry.to_json())
        assert data["event_type"] == "state_transition"
        assert data["task_id"] == "task_001"
        assert data["run_id"] == "run_001"
        assert data["duration_ms"] == 100

    def test_to_json_excludes_empty_extra(self) -> None:
        """JSON output excludes empty extra dict."""
        entry = LogEntry(
            timestamp="2024-01-15T12:00:00Z",
            level="INFO",
            message="Test",
            component="test",
            extra={},
        )
        data = json.loads(entry.to_json())
        assert "extra" not in data

    def test_to_json_includes_extra_when_populated(self) -> None:
        """JSON output includes extra when populated."""
        entry = LogEntry(
            timestamp="2024-01-15T12:00:00Z",
            level="INFO",
            message="Test",
            component="test",
            extra={"key": "value"},
        )
        data = json.loads(entry.to_json())
        assert data["extra"]["key"] == "value"

    def test_to_human_readable_basic(self) -> None:
        """Human-readable output has expected format."""
        entry = LogEntry(
            timestamp="2024-01-15T12:00:00Z",
            level="INFO",
            message="Test message",
            component="test",
        )
        output = entry.to_human_readable()
        assert "[2024-01-15T12:00:00Z]" in output
        assert "[INFO]" in output
        assert "[test]" in output
        assert "Test message" in output

    def test_to_human_readable_with_event_type(self) -> None:
        """Human-readable output includes event type when set."""
        entry = LogEntry(
            timestamp="2024-01-15T12:00:00Z",
            level="INFO",
            message="Test",
            component="test",
            event_type="state_transition",
        )
        output = entry.to_human_readable()
        assert "[state_transition]" in output


class TestStructuredLogger:
    """Tests for StructuredLogger class."""

    def test_create_logger_with_defaults(self) -> None:
        """Logger is created with default settings."""
        logger = StructuredLogger(component="test")
        assert logger.component == "test"
        assert logger.level == LogLevel.INFO
        assert logger.json_format is True

    def test_create_logger_with_custom_settings(self) -> None:
        """Logger can be created with custom settings."""
        output = StringIO()
        logger = StructuredLogger(
            component="custom",
            level=LogLevel.DEBUG,
            output=output,
            json_format=False,
        )
        assert logger.component == "custom"
        assert logger.level == LogLevel.DEBUG
        assert logger.json_format is False

    def test_info_logs_message(self) -> None:
        """info() logs a message."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        logger.info("Test message")
        logged = output.getvalue()
        data = json.loads(logged)
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"

    def test_debug_respects_log_level(self) -> None:
        """debug() respects log level setting."""
        output = StringIO()
        logger = StructuredLogger(component="test", level=LogLevel.INFO, output=output)
        logger.debug("Debug message")
        assert output.getvalue() == ""

    def test_debug_logs_when_level_allows(self) -> None:
        """debug() logs when level is DEBUG."""
        output = StringIO()
        logger = StructuredLogger(
            component="test", level=LogLevel.DEBUG, output=output
        )
        logger.debug("Debug message")
        assert "DEBUG" in output.getvalue()

    def test_warning_logs_message(self) -> None:
        """warning() logs a message."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        logger.warning("Warning message")
        data = json.loads(output.getvalue())
        assert data["level"] == "WARNING"

    def test_error_logs_message(self) -> None:
        """error() logs a message."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        logger.error("Error message")
        data = json.loads(output.getvalue())
        assert data["level"] == "ERROR"

    def test_critical_logs_message(self) -> None:
        """critical() logs a message."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        logger.critical("Critical message")
        data = json.loads(output.getvalue())
        assert data["level"] == "CRITICAL"

    def test_set_context_persists_across_logs(self) -> None:
        """set_context() values appear in subsequent logs."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        logger.set_context(task_id="task_001")
        logger.info("Message 1")
        logger.info("Message 2")
        lines = output.getvalue().strip().split("\n")
        for line in lines:
            data = json.loads(line)
            assert data["task_id"] == "task_001"

    def test_clear_context_removes_values(self) -> None:
        """clear_context() removes persistent context."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        logger.set_context(task_id="task_001")
        logger.clear_context()
        logger.info("Message")
        data = json.loads(output.getvalue())
        assert "task_id" not in data

    def test_with_context_creates_new_logger(self) -> None:
        """with_context() creates a new logger with merged context."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        logger.set_context(key1="value1")
        new_logger = logger.with_context(key2="value2")
        new_logger.info("Message")
        data = json.loads(output.getvalue())
        assert data["extra"]["key1"] == "value1"
        assert data["extra"]["key2"] == "value2"

    def test_human_readable_format(self) -> None:
        """Logger can output human-readable format."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output, json_format=False)
        logger.info("Test message")
        logged = output.getvalue()
        assert "[INFO]" in logged
        assert "[test]" in logged
        assert "Test message" in logged


class TestSpecializedLogging:
    """Tests for specialized logging methods."""

    def test_log_state_transition(self) -> None:
        """log_state_transition() logs correct fields."""
        output = StringIO()
        logger = StructuredLogger(component="editor", output=output)
        logger.log_state_transition("IDLE", "ANALYZING", "Task started")
        data = json.loads(output.getvalue())
        assert data["event_type"] == "state_transition"
        assert data["extra"]["from_state"] == "IDLE"
        assert data["extra"]["to_state"] == "ANALYZING"
        assert data["extra"]["reason"] == "Task started"

    def test_log_scout_query(self) -> None:
        """log_scout_query() logs correct fields."""
        output = StringIO()
        logger = StructuredLogger(component="coordinator", output=output)
        logger.log_scout_query(
            scout_name="scout_a",
            query_summary="Find relevant files",
            duration_ms=1500,
            success=True,
        )
        data = json.loads(output.getvalue())
        assert data["event_type"] == "scout_query"
        assert data["extra"]["scout_name"] == "scout_a"
        assert data["extra"]["query_summary"] == "Find relevant files"
        assert data["duration_ms"] == 1500
        assert data["extra"]["success"] is True

    def test_log_scout_query_truncates_summary(self) -> None:
        """log_scout_query() truncates long summaries."""
        output = StringIO()
        logger = StructuredLogger(component="coordinator", output=output)
        long_summary = "x" * 300
        logger.log_scout_query(
            scout_name="scout_a",
            query_summary=long_summary,
            duration_ms=100,
            success=True,
        )
        data = json.loads(output.getvalue())
        assert len(data["extra"]["query_summary"]) == 200

    def test_log_verifier_trigger(self) -> None:
        """log_verifier_trigger() logs correct fields."""
        output = StringIO()
        logger = StructuredLogger(component="editor", output=output)
        logger.log_verifier_trigger(run_id="run_001", attempt_number=3)
        data = json.loads(output.getvalue())
        assert data["event_type"] == "verifier_trigger"
        assert data["run_id"] == "run_001"
        assert data["extra"]["attempt_number"] == 3

    def test_log_verifier_result(self) -> None:
        """log_verifier_result() logs correct fields."""
        output = StringIO()
        logger = StructuredLogger(component="editor", output=output)
        logger.log_verifier_result(run_id="run_001", status="PASS", duration_ms=5000)
        data = json.loads(output.getvalue())
        assert data["event_type"] == "verifier_result"
        assert data["run_id"] == "run_001"
        assert data["extra"]["status"] == "PASS"
        assert data["duration_ms"] == 5000

    def test_log_replan(self) -> None:
        """log_replan() logs correct fields."""
        output = StringIO()
        logger = StructuredLogger(component="editor", output=output)
        logger.log_replan(attempt_number=3, new_strategy_summary="Try different approach")
        data = json.loads(output.getvalue())
        assert data["event_type"] == "replan"
        assert data["extra"]["attempt_number"] == 3
        assert data["extra"]["strategy_summary"] == "Try different approach"

    def test_log_task_start(self) -> None:
        """log_task_start() logs correct fields."""
        output = StringIO()
        logger = StructuredLogger(component="runner", output=output)
        logger.log_task_start(
            task_id="task_001",
            task_description="Fix the bug",
            dry_run=False,
        )
        data = json.loads(output.getvalue())
        assert data["event_type"] == "task_start"
        assert data["task_id"] == "task_001"
        assert data["extra"]["task_description"] == "Fix the bug"
        assert data["extra"]["dry_run"] is False

    def test_log_task_end(self) -> None:
        """log_task_end() logs correct fields."""
        output = StringIO()
        logger = StructuredLogger(component="runner", output=output)
        logger.log_task_end(
            task_id="task_001",
            final_state="SUCCESS",
            duration_ms=10000,
        )
        data = json.loads(output.getvalue())
        assert data["event_type"] == "task_end"
        assert data["task_id"] == "task_001"
        assert data["extra"]["final_state"] == "SUCCESS"
        assert data["duration_ms"] == 10000


class TestLoggerFactory:
    """Tests for logger factory functions."""

    def test_create_logger_returns_logger(self) -> None:
        """create_logger() returns a StructuredLogger."""
        logger = create_logger("test")
        assert isinstance(logger, StructuredLogger)
        assert logger.component == "test"

    def test_get_logger_creates_singleton(self) -> None:
        """get_logger() returns same instance for same component."""
        reset_loggers()
        logger1 = get_logger("component_a")
        logger2 = get_logger("component_a")
        assert logger1 is logger2

    def test_get_logger_different_components(self) -> None:
        """get_logger() returns different instances for different components."""
        reset_loggers()
        logger1 = get_logger("component_a")
        logger2 = get_logger("component_b")
        assert logger1 is not logger2

    def test_reset_loggers_clears_cache(self) -> None:
        """reset_loggers() clears the logger cache."""
        reset_loggers()
        logger1 = get_logger("test")
        reset_loggers()
        logger2 = get_logger("test")
        assert logger1 is not logger2

    def test_configure_logging_updates_loggers(self) -> None:
        """configure_logging() updates existing loggers."""
        reset_loggers()
        logger = get_logger("test")
        output = StringIO()
        configure_logging(level=LogLevel.WARNING, json_format=False, output=output)
        assert logger.level == LogLevel.WARNING
        assert logger.json_format is False
