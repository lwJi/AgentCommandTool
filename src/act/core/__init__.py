"""Core infrastructure for AgentCommandTool.

Provides:
- Structured logging
- Metrics collection
- Error handling with graceful degradation
- Input validation
"""

from act.core.error_handling import (
    ErrorContext,
    ErrorSeverity,
    GracefulErrorHandler,
    create_error_handler,
    get_error_handler,
    reset_error_handler,
    set_error_handler,
)
from act.core.logging import (
    LogEntry,
    LogLevel,
    StructuredLogger,
    configure_logging,
    create_logger,
    get_logger,
    reset_loggers,
)
from act.core.metrics import (
    LatencyStats,
    MetricsCollector,
    TaskMetrics,
    Timer,
    get_metrics_collector,
    reset_metrics_collector,
)
from act.core.validation import (
    MAX_TASK_DESCRIPTION_LENGTH,
    MIN_TASK_DESCRIPTION_LENGTH,
    ValidationError,
    ValidationResult,
    require_valid_inputs,
    validate_agent_config,
    validate_all_inputs,
    validate_docker_available,
    validate_repo_path,
    validate_task_input,
)

__all__ = [
    # Logging
    "LogLevel",
    "LogEntry",
    "StructuredLogger",
    "create_logger",
    "get_logger",
    "reset_loggers",
    "configure_logging",
    # Metrics
    "LatencyStats",
    "TaskMetrics",
    "MetricsCollector",
    "Timer",
    "get_metrics_collector",
    "reset_metrics_collector",
    # Error handling
    "ErrorSeverity",
    "ErrorContext",
    "GracefulErrorHandler",
    "create_error_handler",
    "get_error_handler",
    "set_error_handler",
    "reset_error_handler",
    # Validation
    "ValidationResult",
    "ValidationError",
    "validate_task_input",
    "validate_agent_config",
    "validate_docker_available",
    "validate_repo_path",
    "validate_all_inputs",
    "require_valid_inputs",
    "MAX_TASK_DESCRIPTION_LENGTH",
    "MIN_TASK_DESCRIPTION_LENGTH",
]
