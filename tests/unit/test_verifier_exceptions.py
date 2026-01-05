"""Tests for verifier exception hierarchy and error types."""

import pytest

from act.verifier.exceptions import (
    ContainerError,
    InfraErrorType,
    LogError,
    PipelineError,
    VerifierError,
)


class TestVerifierError:
    """Tests for VerifierError base exception."""

    def test_can_be_instantiated_with_message(self) -> None:
        """VerifierError can be created with a message."""
        error = VerifierError("test error message")
        assert str(error) == "test error message"

    def test_inherits_from_exception(self) -> None:
        """VerifierError inherits from Exception."""
        error = VerifierError("test")
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        """VerifierError can be raised and caught."""
        with pytest.raises(VerifierError) as exc_info:
            raise VerifierError("test error")
        assert "test error" in str(exc_info.value)


class TestContainerError:
    """Tests for ContainerError exception."""

    def test_can_be_instantiated_with_message(self) -> None:
        """ContainerError can be created with a message."""
        error = ContainerError("container failed")
        assert str(error) == "container failed"

    def test_inherits_from_verifier_error(self) -> None:
        """ContainerError inherits from VerifierError."""
        error = ContainerError("test")
        assert isinstance(error, VerifierError)

    def test_can_be_caught_as_verifier_error(self) -> None:
        """ContainerError can be caught as VerifierError."""
        with pytest.raises(VerifierError):
            raise ContainerError("container error")


class TestPipelineError:
    """Tests for PipelineError exception."""

    def test_can_be_instantiated_with_message(self) -> None:
        """PipelineError can be created with a message."""
        error = PipelineError("pipeline failed")
        assert str(error) == "pipeline failed"

    def test_inherits_from_verifier_error(self) -> None:
        """PipelineError inherits from VerifierError."""
        error = PipelineError("test")
        assert isinstance(error, VerifierError)

    def test_can_be_caught_as_verifier_error(self) -> None:
        """PipelineError can be caught as VerifierError."""
        with pytest.raises(VerifierError):
            raise PipelineError("pipeline error")


class TestLogError:
    """Tests for LogError exception."""

    def test_can_be_instantiated_with_message(self) -> None:
        """LogError can be created with a message."""
        error = LogError("log failed")
        assert str(error) == "log failed"

    def test_inherits_from_verifier_error(self) -> None:
        """LogError inherits from VerifierError."""
        error = LogError("test")
        assert isinstance(error, VerifierError)

    def test_can_be_caught_as_verifier_error(self) -> None:
        """LogError can be caught as VerifierError."""
        with pytest.raises(VerifierError):
            raise LogError("log error")


class TestInfraErrorType:
    """Tests for InfraErrorType enum."""

    def test_has_docker_unavailable_value(self) -> None:
        """InfraErrorType has DOCKER_UNAVAILABLE value."""
        assert InfraErrorType.DOCKER_UNAVAILABLE.value == "docker_unavailable"

    def test_has_container_creation_value(self) -> None:
        """InfraErrorType has CONTAINER_CREATION value."""
        assert InfraErrorType.CONTAINER_CREATION.value == "container_creation"

    def test_has_image_pull_value(self) -> None:
        """InfraErrorType has IMAGE_PULL value."""
        assert InfraErrorType.IMAGE_PULL.value == "image_pull"

    def test_has_resource_exhaustion_value(self) -> None:
        """InfraErrorType has RESOURCE_EXHAUSTION value."""
        assert InfraErrorType.RESOURCE_EXHAUSTION.value == "resource_exhaustion"

    def test_has_unknown_value(self) -> None:
        """InfraErrorType has UNKNOWN value."""
        assert InfraErrorType.UNKNOWN.value == "unknown"

    def test_has_exactly_five_values(self) -> None:
        """InfraErrorType has exactly 5 values as per spec."""
        assert len(InfraErrorType) == 5

    def test_values_are_unique(self) -> None:
        """InfraErrorType values are all unique."""
        values = [e.value for e in InfraErrorType]
        assert len(values) == len(set(values))
