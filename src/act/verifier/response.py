"""Verifier response data structures and factory functions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from act.artifacts.manifest import Manifest
from act.verifier.exceptions import InfraErrorType


class VerifierStatus(Enum):
    """Status of a verification run."""

    PASS = "PASS"
    FAIL = "FAIL"
    INFRA_ERROR = "INFRA_ERROR"


@dataclass
class VerifierResponse:
    """Unified response from Verifier (PASS, FAIL, or INFRA_ERROR).

    All Verifier responses use this unified schema. The status field
    determines which optional fields are present.

    Attributes:
        status: The verification status (PASS, FAIL, or INFRA_ERROR).
        run_id: Unique identifier for this run (optional for INFRA_ERROR).
        tail_log: Last 200 lines of combined log output.
        artifact_paths: List of paths to artifacts in the run directory.
        manifest: The verification run manifest.
        error_type: Type of infrastructure error (INFRA_ERROR only).
        error_message: Human-readable error message (INFRA_ERROR only).
    """

    status: VerifierStatus
    run_id: str | None = None
    tail_log: str | None = None
    artifact_paths: list[str] = field(default_factory=list)
    manifest: Manifest | None = None
    error_type: InfraErrorType | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the response.
        """
        result: dict[str, Any] = {"status": self.status.value}

        if self.run_id is not None:
            result["run_id"] = self.run_id
        if self.tail_log is not None:
            result["tail_log"] = self.tail_log
        if self.artifact_paths:
            result["artifact_paths"] = self.artifact_paths
        if self.manifest is not None:
            result["manifest"] = self.manifest.to_dict()
        if self.error_type is not None:
            result["error_type"] = self.error_type.value
        if self.error_message is not None:
            result["error_message"] = self.error_message

        return result


def create_pass_response(
    run_id: str,
    tail_log: str,
    artifact_paths: list[str],
    manifest: Manifest,
) -> VerifierResponse:
    """Create a PASS response.

    Args:
        run_id: Unique identifier for this run.
        tail_log: Last 200 lines of combined log output.
        artifact_paths: List of paths to artifacts.
        manifest: The verification run manifest.

    Returns:
        VerifierResponse with PASS status.
    """
    return VerifierResponse(
        status=VerifierStatus.PASS,
        run_id=run_id,
        tail_log=tail_log,
        artifact_paths=artifact_paths,
        manifest=manifest,
    )


def create_fail_response(
    run_id: str,
    tail_log: str,
    artifact_paths: list[str],
    manifest: Manifest,
) -> VerifierResponse:
    """Create a FAIL response.

    Args:
        run_id: Unique identifier for this run.
        tail_log: Last 200 lines of combined log output.
        artifact_paths: List of paths to artifacts.
        manifest: The verification run manifest.

    Returns:
        VerifierResponse with FAIL status.
    """
    return VerifierResponse(
        status=VerifierStatus.FAIL,
        run_id=run_id,
        tail_log=tail_log,
        artifact_paths=artifact_paths,
        manifest=manifest,
    )


def create_infra_error_response(
    error_type: InfraErrorType,
    error_message: str,
    run_id: str | None = None,
    tail_log: str | None = None,
    artifact_paths: list[str] | None = None,
    manifest: Manifest | None = None,
) -> VerifierResponse:
    """Create an INFRA_ERROR response.

    Args:
        error_type: Type of infrastructure error.
        error_message: Human-readable error message.
        run_id: Optional unique identifier (may be None if container never started).
        tail_log: Optional partial logs if available.
        artifact_paths: Optional list of artifact paths.
        manifest: Optional manifest if available.

    Returns:
        VerifierResponse with INFRA_ERROR status.
    """
    return VerifierResponse(
        status=VerifierStatus.INFRA_ERROR,
        run_id=run_id,
        tail_log=tail_log,
        artifact_paths=artifact_paths or [],
        manifest=manifest,
        error_type=error_type,
        error_message=error_message,
    )
