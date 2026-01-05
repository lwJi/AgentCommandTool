"""Tests for verifier response data structures and factory functions."""

from act.artifacts.manifest import CommandResult, Manifest, PlatformInfo
from act.verifier.exceptions import InfraErrorType
from act.verifier.response import (
    VerifierResponse,
    VerifierStatus,
    create_fail_response,
    create_infra_error_response,
    create_pass_response,
)


def _create_test_manifest() -> Manifest:
    """Create a test manifest for use in tests."""
    return Manifest(
        run_id="run_20240115_143200_abc123",
        timestamp_start="2024-01-15T14:32:00Z",
        timestamp_end="2024-01-15T14:35:42Z",
        commit_sha="a1b2c3d4e5f6",
        status="PASS",
        commands_executed=[
            CommandResult(
                name="test",
                command="npm test",
                exit_code=0,
                duration_ms=12340,
            )
        ],
        platform=PlatformInfo(
            os="linux",
            arch="x64",
            container_image="node:20-slim",
        ),
    )


class TestVerifierStatus:
    """Tests for VerifierStatus enum."""

    def test_has_pass_value(self) -> None:
        """VerifierStatus has PASS value."""
        assert VerifierStatus.PASS.value == "PASS"

    def test_has_fail_value(self) -> None:
        """VerifierStatus has FAIL value."""
        assert VerifierStatus.FAIL.value == "FAIL"

    def test_has_infra_error_value(self) -> None:
        """VerifierStatus has INFRA_ERROR value."""
        assert VerifierStatus.INFRA_ERROR.value == "INFRA_ERROR"

    def test_has_exactly_three_values(self) -> None:
        """VerifierStatus has exactly 3 values as per spec."""
        assert len(VerifierStatus) == 3


class TestVerifierResponse:
    """Tests for VerifierResponse dataclass."""

    def test_can_be_created_with_status_only(self) -> None:
        """VerifierResponse can be created with just status."""
        response = VerifierResponse(status=VerifierStatus.PASS)
        assert response.status == VerifierStatus.PASS
        assert response.run_id is None
        assert response.tail_log is None
        assert response.artifact_paths == []
        assert response.manifest is None
        assert response.error_type is None
        assert response.error_message is None

    def test_can_be_created_with_all_fields(self) -> None:
        """VerifierResponse can be created with all fields."""
        manifest = _create_test_manifest()
        response = VerifierResponse(
            status=VerifierStatus.PASS,
            run_id="run_20240115_143200_abc123",
            tail_log="test output",
            artifact_paths=["/path/to/artifact"],
            manifest=manifest,
            error_type=None,
            error_message=None,
        )
        assert response.run_id == "run_20240115_143200_abc123"
        assert response.tail_log == "test output"
        assert response.artifact_paths == ["/path/to/artifact"]
        assert response.manifest == manifest


class TestVerifierResponseToDict:
    """Tests for VerifierResponse.to_dict() method."""

    def test_pass_response_has_required_fields(self) -> None:
        """PASS response to_dict has all required fields."""
        manifest = _create_test_manifest()
        response = VerifierResponse(
            status=VerifierStatus.PASS,
            run_id="run_20240115_143200_abc123",
            tail_log="test output",
            artifact_paths=["/path/to/logs"],
            manifest=manifest,
        )
        result = response.to_dict()

        assert result["status"] == "PASS"
        assert result["run_id"] == "run_20240115_143200_abc123"
        assert result["tail_log"] == "test output"
        assert result["artifact_paths"] == ["/path/to/logs"]
        assert "manifest" in result
        assert result["manifest"]["run_id"] == "run_20240115_143200_abc123"
        # PASS should not have error fields
        assert "error_type" not in result
        assert "error_message" not in result

    def test_fail_response_has_required_fields(self) -> None:
        """FAIL response to_dict has all required fields."""
        manifest = _create_test_manifest()
        manifest.status = "FAIL"
        response = VerifierResponse(
            status=VerifierStatus.FAIL,
            run_id="run_20240115_143200_abc123",
            tail_log="Error: test failed",
            artifact_paths=["/path/to/logs"],
            manifest=manifest,
        )
        result = response.to_dict()

        assert result["status"] == "FAIL"
        assert result["run_id"] == "run_20240115_143200_abc123"
        assert result["tail_log"] == "Error: test failed"
        assert "error_type" not in result
        assert "error_message" not in result

    def test_infra_error_response_has_required_fields(self) -> None:
        """INFRA_ERROR response to_dict has error fields."""
        response = VerifierResponse(
            status=VerifierStatus.INFRA_ERROR,
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_message="Docker daemon is not running",
        )
        result = response.to_dict()

        assert result["status"] == "INFRA_ERROR"
        assert result["error_type"] == "docker_unavailable"
        assert result["error_message"] == "Docker daemon is not running"

    def test_infra_error_omits_null_optional_fields(self) -> None:
        """INFRA_ERROR response omits null optional fields."""
        response = VerifierResponse(
            status=VerifierStatus.INFRA_ERROR,
            run_id=None,
            tail_log=None,
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_message="Docker unavailable",
        )
        result = response.to_dict()

        assert "run_id" not in result
        assert "tail_log" not in result
        assert "manifest" not in result

    def test_infra_error_includes_partial_data_when_available(self) -> None:
        """INFRA_ERROR response includes partial data when available."""
        response = VerifierResponse(
            status=VerifierStatus.INFRA_ERROR,
            run_id="run_20240115_143200_abc123",
            tail_log="Partial output before failure",
            artifact_paths=["/path/to/partial/logs"],
            error_type=InfraErrorType.CONTAINER_CREATION,
            error_message="Failed to create container",
        )
        result = response.to_dict()

        assert result["run_id"] == "run_20240115_143200_abc123"
        assert result["tail_log"] == "Partial output before failure"
        assert result["artifact_paths"] == ["/path/to/partial/logs"]

    def test_empty_artifact_paths_omitted(self) -> None:
        """Empty artifact_paths list is omitted from to_dict."""
        response = VerifierResponse(
            status=VerifierStatus.INFRA_ERROR,
            artifact_paths=[],
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_message="Docker unavailable",
        )
        result = response.to_dict()

        assert "artifact_paths" not in result


class TestCreatePassResponse:
    """Tests for create_pass_response factory function."""

    def test_creates_pass_status(self) -> None:
        """create_pass_response creates response with PASS status."""
        manifest = _create_test_manifest()
        response = create_pass_response(
            run_id="run_20240115_143200_abc123",
            tail_log="All tests passed",
            artifact_paths=["/path/to/logs"],
            manifest=manifest,
        )
        assert response.status == VerifierStatus.PASS

    def test_sets_all_required_fields(self) -> None:
        """create_pass_response sets all required fields."""
        manifest = _create_test_manifest()
        response = create_pass_response(
            run_id="run_20240115_143200_abc123",
            tail_log="All tests passed",
            artifact_paths=["/path/to/logs", "/path/to/build"],
            manifest=manifest,
        )
        assert response.run_id == "run_20240115_143200_abc123"
        assert response.tail_log == "All tests passed"
        assert response.artifact_paths == ["/path/to/logs", "/path/to/build"]
        assert response.manifest == manifest

    def test_does_not_set_error_fields(self) -> None:
        """create_pass_response does not set error fields."""
        manifest = _create_test_manifest()
        response = create_pass_response(
            run_id="run_20240115_143200_abc123",
            tail_log="All tests passed",
            artifact_paths=[],
            manifest=manifest,
        )
        assert response.error_type is None
        assert response.error_message is None


class TestCreateFailResponse:
    """Tests for create_fail_response factory function."""

    def test_creates_fail_status(self) -> None:
        """create_fail_response creates response with FAIL status."""
        manifest = _create_test_manifest()
        response = create_fail_response(
            run_id="run_20240115_143200_abc123",
            tail_log="Test failed",
            artifact_paths=["/path/to/logs"],
            manifest=manifest,
        )
        assert response.status == VerifierStatus.FAIL

    def test_sets_all_required_fields(self) -> None:
        """create_fail_response sets all required fields."""
        manifest = _create_test_manifest()
        response = create_fail_response(
            run_id="run_20240115_143200_abc123",
            tail_log="Error: assertion failed",
            artifact_paths=["/path/to/logs"],
            manifest=manifest,
        )
        assert response.run_id == "run_20240115_143200_abc123"
        assert response.tail_log == "Error: assertion failed"
        assert response.artifact_paths == ["/path/to/logs"]
        assert response.manifest == manifest

    def test_does_not_set_error_fields(self) -> None:
        """create_fail_response does not set error fields."""
        manifest = _create_test_manifest()
        response = create_fail_response(
            run_id="run_20240115_143200_abc123",
            tail_log="Test failed",
            artifact_paths=[],
            manifest=manifest,
        )
        assert response.error_type is None
        assert response.error_message is None


class TestCreateInfraErrorResponse:
    """Tests for create_infra_error_response factory function."""

    def test_creates_infra_error_status(self) -> None:
        """create_infra_error_response creates response with INFRA_ERROR status."""
        response = create_infra_error_response(
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_message="Docker is not running",
        )
        assert response.status == VerifierStatus.INFRA_ERROR

    def test_sets_error_fields(self) -> None:
        """create_infra_error_response sets error type and message."""
        response = create_infra_error_response(
            error_type=InfraErrorType.IMAGE_PULL,
            error_message="Failed to pull image: node:20-slim",
        )
        assert response.error_type == InfraErrorType.IMAGE_PULL
        assert response.error_message == "Failed to pull image: node:20-slim"

    def test_optional_fields_default_to_none(self) -> None:
        """create_infra_error_response optional fields default to None/empty."""
        response = create_infra_error_response(
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_message="Docker unavailable",
        )
        assert response.run_id is None
        assert response.tail_log is None
        assert response.artifact_paths == []
        assert response.manifest is None

    def test_accepts_optional_run_id(self) -> None:
        """create_infra_error_response accepts optional run_id."""
        response = create_infra_error_response(
            error_type=InfraErrorType.RESOURCE_EXHAUSTION,
            error_message="Out of memory",
            run_id="run_20240115_143200_abc123",
        )
        assert response.run_id == "run_20240115_143200_abc123"

    def test_accepts_optional_tail_log(self) -> None:
        """create_infra_error_response accepts optional tail_log."""
        response = create_infra_error_response(
            error_type=InfraErrorType.CONTAINER_CREATION,
            error_message="Failed to create container",
            tail_log="Partial output before failure",
        )
        assert response.tail_log == "Partial output before failure"

    def test_accepts_optional_artifact_paths(self) -> None:
        """create_infra_error_response accepts optional artifact_paths."""
        response = create_infra_error_response(
            error_type=InfraErrorType.UNKNOWN,
            error_message="Unknown error",
            artifact_paths=["/path/to/partial"],
        )
        assert response.artifact_paths == ["/path/to/partial"]

    def test_accepts_optional_manifest(self) -> None:
        """create_infra_error_response accepts optional manifest."""
        manifest = _create_test_manifest()
        response = create_infra_error_response(
            error_type=InfraErrorType.RESOURCE_EXHAUSTION,
            error_message="Out of memory",
            manifest=manifest,
        )
        assert response.manifest == manifest

    def test_all_error_types_supported(self) -> None:
        """create_infra_error_response supports all InfraErrorType values."""
        for error_type in InfraErrorType:
            response = create_infra_error_response(
                error_type=error_type,
                error_message=f"Test error: {error_type.value}",
            )
            assert response.error_type == error_type
