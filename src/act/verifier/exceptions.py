"""Verifier-specific exception hierarchy and error types."""

from enum import Enum


class VerifierError(Exception):
    """Base exception for verifier errors."""

    pass


class ContainerError(VerifierError):
    """Error related to container operations."""

    pass


class PipelineError(VerifierError):
    """Error related to pipeline execution."""

    pass


class LogError(VerifierError):
    """Error related to log operations."""

    pass


class InfraErrorType(Enum):
    """Infrastructure error types for INFRA_ERROR responses.

    These error types indicate infrastructure failures that prevent
    verification from completing successfully.
    """

    DOCKER_UNAVAILABLE = "docker_unavailable"
    CONTAINER_CREATION = "container_creation"
    IMAGE_PULL = "image_pull"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNKNOWN = "unknown"
