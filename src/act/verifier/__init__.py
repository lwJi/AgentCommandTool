"""Sandboxed verification execution in Docker containers."""

from act.verifier.container import (
    DEFAULT_CPU_LIMIT,
    DEFAULT_MEMORY_LIMIT,
    ContainerConfig,
    ContainerManager,
)
from act.verifier.exceptions import (
    ContainerError,
    InfraErrorType,
    LogError,
    PipelineError,
    VerifierError,
)
from act.verifier.executor import verify
from act.verifier.logs import TAIL_LOG_LINES
from act.verifier.pipeline import PipelineExecutor, StepResult
from act.verifier.response import (
    VerifierResponse,
    VerifierStatus,
    create_fail_response,
    create_infra_error_response,
    create_pass_response,
)

__all__ = [
    # Main entry point
    "verify",
    # Response types
    "VerifierResponse",
    "VerifierStatus",
    "create_pass_response",
    "create_fail_response",
    "create_infra_error_response",
    # Exceptions
    "VerifierError",
    "ContainerError",
    "PipelineError",
    "LogError",
    "InfraErrorType",
    # Container management
    "ContainerManager",
    "ContainerConfig",
    "DEFAULT_CPU_LIMIT",
    "DEFAULT_MEMORY_LIMIT",
    # Pipeline execution
    "PipelineExecutor",
    "StepResult",
    # Constants
    "TAIL_LOG_LINES",
]
