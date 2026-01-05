"""Unit tests for act.core.error_handling module."""

from __future__ import annotations

from io import StringIO
from typing import Any
from unittest.mock import MagicMock

import pytest

from act.core.error_handling import (
    ErrorContext,
    ErrorSeverity,
    GracefulErrorHandler,
    create_error_handler,
    get_error_handler,
    reset_error_handler,
    set_error_handler,
)
from act.core.logging import StructuredLogger


class TestErrorSeverity:
    """Tests for ErrorSeverity enum."""

    def test_severity_values(self) -> None:
        """ErrorSeverity has expected values."""
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.CRITICAL.value == "critical"


class TestErrorContext:
    """Tests for ErrorContext dataclass."""

    def test_create_with_required_fields(self) -> None:
        """ErrorContext can be created with required fields only."""
        context = ErrorContext(operation="test_op", component="test_comp")
        assert context.operation == "test_op"
        assert context.component == "test_comp"
        assert context.task_id is None
        assert context.additional_info == {}

    def test_create_with_all_fields(self) -> None:
        """ErrorContext can be created with all fields."""
        context = ErrorContext(
            operation="test_op",
            component="test_comp",
            task_id="task_001",
            additional_info={"key": "value"},
        )
        assert context.task_id == "task_001"
        assert context.additional_info["key"] == "value"

    def test_to_dict_required_fields(self) -> None:
        """to_dict() includes required fields."""
        context = ErrorContext(operation="test_op", component="test_comp")
        data = context.to_dict()
        assert data["operation"] == "test_op"
        assert data["component"] == "test_comp"
        assert "task_id" not in data
        assert "additional_info" not in data

    def test_to_dict_includes_optional_fields(self) -> None:
        """to_dict() includes optional fields when set."""
        context = ErrorContext(
            operation="test_op",
            component="test_comp",
            task_id="task_001",
            additional_info={"key": "value"},
        )
        data = context.to_dict()
        assert data["task_id"] == "task_001"
        assert data["additional_info"]["key"] == "value"


class TestGracefulErrorHandler:
    """Tests for GracefulErrorHandler class."""

    def test_create_without_logger(self) -> None:
        """GracefulErrorHandler can be created without logger."""
        handler = GracefulErrorHandler()
        assert handler._logger is None
        assert handler._on_error is None

    def test_create_with_logger(self) -> None:
        """GracefulErrorHandler can be created with logger."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        handler = GracefulErrorHandler(logger=logger)
        assert handler._logger is logger

    def test_create_with_callback(self) -> None:
        """GracefulErrorHandler can be created with callback."""
        callback = MagicMock()
        handler = GracefulErrorHandler(on_error=callback)
        assert handler._on_error is callback

    def test_handle_error_returns_state(self) -> None:
        """handle_error() returns recommended state."""
        handler = GracefulErrorHandler()
        context = ErrorContext(operation="test", component="test")
        state = handler.handle_error(ValueError("Test error"), context)
        assert state == "INFRA_ERROR"

    def test_handle_error_logs_to_logger(self) -> None:
        """handle_error() logs error to logger."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        handler = GracefulErrorHandler(logger=logger)
        context = ErrorContext(operation="test", component="test")
        handler.handle_error(ValueError("Test error"), context)
        assert "Test error" in output.getvalue()

    def test_handle_error_calls_callback(self) -> None:
        """handle_error() calls callback."""
        callback = MagicMock()
        handler = GracefulErrorHandler(on_error=callback)
        context = ErrorContext(operation="test", component="test")
        error = ValueError("Test error")
        handler.handle_error(error, context)
        callback.assert_called_once_with(context, error)

    def test_handle_error_suppresses_callback_errors(self) -> None:
        """handle_error() suppresses callback errors."""

        def bad_callback(context: ErrorContext, error: Exception) -> None:
            raise RuntimeError("Callback error")

        handler = GracefulErrorHandler(on_error=bad_callback)
        context = ErrorContext(operation="test", component="test")
        # Should not raise
        state = handler.handle_error(ValueError("Test"), context)
        assert state == "INFRA_ERROR"

    def test_handle_error_with_warning_severity(self) -> None:
        """handle_error() handles warning severity."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        handler = GracefulErrorHandler(logger=logger)
        context = ErrorContext(operation="test", component="test")
        handler.handle_error(
            ValueError("Warning"), context, severity=ErrorSeverity.WARNING
        )
        assert "WARNING" in output.getvalue()

    def test_handle_error_with_critical_severity(self) -> None:
        """handle_error() handles critical severity."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        handler = GracefulErrorHandler(logger=logger)
        context = ErrorContext(operation="test", component="test")
        state = handler.handle_error(
            ValueError("Critical"), context, severity=ErrorSeverity.CRITICAL
        )
        assert "CRITICAL" in output.getvalue()
        assert state == "INFRA_ERROR"

    def test_determine_state_infrastructure_error(self) -> None:
        """_determine_state() returns INFRA_ERROR for InfrastructureError."""
        from act.editor.exceptions import InfrastructureError

        handler = GracefulErrorHandler()
        context = ErrorContext(operation="test", component="test")
        error = InfrastructureError("Test", source="verifier")
        state = handler._determine_state(error, context, ErrorSeverity.ERROR)
        assert state == "INFRA_ERROR"

    def test_determine_state_hard_stop_error(self) -> None:
        """_determine_state() returns STUCK for HardStopError."""
        from act.editor.exceptions import HardStopError

        handler = GracefulErrorHandler()
        context = ErrorContext(operation="test", component="test")
        error = HardStopError("Hard stop reached", 12, ["run_1", "run_2"])
        state = handler._determine_state(error, context, ErrorSeverity.ERROR)
        assert state == "STUCK"

    def test_wrap_operation_success(self) -> None:
        """wrap_operation() returns result on success."""
        handler = GracefulErrorHandler()
        context = ErrorContext(operation="test", component="test")

        def operation() -> str:
            return "result"

        result = handler.wrap_operation(operation, context)
        assert result == "result"

    def test_wrap_operation_failure(self) -> None:
        """wrap_operation() returns default on failure."""
        handler = GracefulErrorHandler()
        context = ErrorContext(operation="test", component="test")

        def operation() -> str:
            raise ValueError("Error")

        result = handler.wrap_operation(operation, context, default_return="default")
        assert result == "default"


class TestErrorHandlerFactory:
    """Tests for error handler factory functions."""

    def test_create_error_handler(self) -> None:
        """create_error_handler() returns configured handler."""
        output = StringIO()
        logger = StructuredLogger(component="test", output=output)
        callback = MagicMock()
        handler = create_error_handler(logger=logger, on_error=callback)
        assert handler._logger is logger
        assert handler._on_error is callback

    def test_get_error_handler_returns_singleton(self) -> None:
        """get_error_handler() returns same instance."""
        reset_error_handler()
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        assert handler1 is handler2

    def test_set_error_handler(self) -> None:
        """set_error_handler() sets global handler."""
        reset_error_handler()
        custom_handler = GracefulErrorHandler()
        set_error_handler(custom_handler)
        assert get_error_handler() is custom_handler

    def test_reset_error_handler(self) -> None:
        """reset_error_handler() clears global handler."""
        reset_error_handler()
        handler1 = get_error_handler()
        reset_error_handler()
        handler2 = get_error_handler()
        assert handler1 is not handler2
