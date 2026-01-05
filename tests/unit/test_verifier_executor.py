"""Tests for verifier executor."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from act.config.schema import (
    AgentConfig,
    TimeoutsConfig,
    VerificationConfig,
    VerificationStep,
)
from act.verifier.exceptions import InfraErrorType
from act.verifier.executor import verify
from act.verifier.response import VerifierStatus


def _create_test_config() -> AgentConfig:
    """Create a test agent configuration."""
    return AgentConfig(
        verification=VerificationConfig(
            container_image="node:20-slim",
            steps=[
                VerificationStep(name="install", command="npm ci"),
                VerificationStep(name="test", command="npm test"),
            ],
        ),
        timeouts=TimeoutsConfig(verification_step=300000),
    )


class TestVerifyDockerUnavailable:
    """Tests for verify() when Docker is unavailable."""

    @patch("act.verifier.executor.ContainerManager")
    @patch("act.verifier.executor.ensure_artifact_dir_structure")
    @patch("act.verifier.executor.create_run_dir")
    @patch("act.verifier.executor.create_logs_dir")
    @patch("act.verifier.executor.create_tmp_dir")
    @patch("act.verifier.executor.create_db_dir")
    def test_returns_infra_error_when_docker_unavailable(
        self,
        mock_create_db_dir: MagicMock,
        mock_create_tmp_dir: MagicMock,
        mock_create_logs_dir: MagicMock,
        mock_create_run_dir: MagicMock,
        mock_ensure_artifact: MagicMock,
        mock_container_manager_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns INFRA_ERROR when Docker is unavailable."""
        # Setup mocks
        mock_create_run_dir.return_value = ("run_test", tmp_path / "run")
        mock_create_logs_dir.return_value = tmp_path / "run" / "logs"
        mock_create_tmp_dir.return_value = tmp_path / "run" / "tmp"
        mock_create_db_dir.return_value = tmp_path / "run" / "db"

        mock_manager = MagicMock()
        mock_manager.is_docker_available.return_value = False
        mock_container_manager_class.return_value = mock_manager

        config = _create_test_config()

        response = verify(
            repo_path=tmp_path / "repo",
            config=config,
            artifact_dir=tmp_path / "artifacts",
        )

        assert response.status == VerifierStatus.INFRA_ERROR
        assert response.error_type == InfraErrorType.DOCKER_UNAVAILABLE
        assert "Docker daemon" in (response.error_message or "")


class TestVerifyImagePullFailure:
    """Tests for verify() when image pull fails."""

    @patch("act.verifier.executor.ContainerManager")
    @patch("act.verifier.executor.ensure_artifact_dir_structure")
    @patch("act.verifier.executor.create_run_dir")
    @patch("act.verifier.executor.create_logs_dir")
    @patch("act.verifier.executor.create_tmp_dir")
    @patch("act.verifier.executor.create_db_dir")
    def test_returns_infra_error_on_image_pull_failure(
        self,
        mock_create_db_dir: MagicMock,
        mock_create_tmp_dir: MagicMock,
        mock_create_logs_dir: MagicMock,
        mock_create_run_dir: MagicMock,
        mock_ensure_artifact: MagicMock,
        mock_container_manager_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns INFRA_ERROR when image pull fails."""
        from act.verifier.exceptions import ContainerError

        # Setup mocks
        mock_create_run_dir.return_value = ("run_test", tmp_path / "run")
        mock_create_logs_dir.return_value = tmp_path / "run" / "logs"
        mock_create_tmp_dir.return_value = tmp_path / "run" / "tmp"
        mock_create_db_dir.return_value = tmp_path / "run" / "db"

        mock_manager = MagicMock()
        mock_manager.is_docker_available.return_value = True
        mock_manager.image_exists.return_value = False
        mock_manager.pull_image.side_effect = ContainerError("Pull failed")
        mock_container_manager_class.return_value = mock_manager

        config = _create_test_config()

        response = verify(
            repo_path=tmp_path / "repo",
            config=config,
            artifact_dir=tmp_path / "artifacts",
        )

        assert response.status == VerifierStatus.INFRA_ERROR
        assert response.error_type == InfraErrorType.IMAGE_PULL
        assert response.run_id == "run_test"


class TestVerifyContainerCreationFailure:
    """Tests for verify() when container creation fails."""

    @patch("act.verifier.executor.ContainerManager")
    @patch("act.verifier.executor.ensure_artifact_dir_structure")
    @patch("act.verifier.executor.create_run_dir")
    @patch("act.verifier.executor.create_logs_dir")
    @patch("act.verifier.executor.create_tmp_dir")
    @patch("act.verifier.executor.create_db_dir")
    def test_returns_infra_error_on_container_creation_failure(
        self,
        mock_create_db_dir: MagicMock,
        mock_create_tmp_dir: MagicMock,
        mock_create_logs_dir: MagicMock,
        mock_create_run_dir: MagicMock,
        mock_ensure_artifact: MagicMock,
        mock_container_manager_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns INFRA_ERROR when container creation fails."""
        from act.verifier.exceptions import ContainerError

        # Setup mocks
        mock_create_run_dir.return_value = ("run_test", tmp_path / "run")
        mock_create_logs_dir.return_value = tmp_path / "run" / "logs"
        mock_create_tmp_dir.return_value = tmp_path / "run" / "tmp"
        mock_create_db_dir.return_value = tmp_path / "run" / "db"

        mock_manager = MagicMock()
        mock_manager.is_docker_available.return_value = True
        mock_manager.image_exists.return_value = True
        mock_manager.create_container.side_effect = ContainerError("Creation failed")
        mock_container_manager_class.return_value = mock_manager

        config = _create_test_config()

        response = verify(
            repo_path=tmp_path / "repo",
            config=config,
            artifact_dir=tmp_path / "artifacts",
        )

        assert response.status == VerifierStatus.INFRA_ERROR
        assert response.error_type == InfraErrorType.CONTAINER_CREATION


class TestVerifyPass:
    """Tests for verify() successful execution."""

    @patch("act.verifier.executor.ContainerManager")
    @patch("act.verifier.executor.PipelineExecutor")
    @patch("act.verifier.executor.ensure_artifact_dir_structure")
    @patch("act.verifier.executor.create_run_dir")
    @patch("act.verifier.executor.create_logs_dir")
    @patch("act.verifier.executor.create_tmp_dir")
    @patch("act.verifier.executor.create_db_dir")
    @patch("act.verifier.executor.write_manifest")
    @patch("act.verifier.executor.read_manifest")
    @patch("act.verifier.executor.extract_tail_log")
    @patch("act.verifier.executor.list_artifact_paths")
    def test_returns_pass_on_success(
        self,
        mock_list_artifacts: MagicMock,
        mock_extract_tail: MagicMock,
        mock_read_manifest: MagicMock,
        mock_write_manifest: MagicMock,
        mock_create_db_dir: MagicMock,
        mock_create_tmp_dir: MagicMock,
        mock_create_logs_dir: MagicMock,
        mock_create_run_dir: MagicMock,
        mock_ensure_artifact: MagicMock,
        mock_pipeline_class: MagicMock,
        mock_container_manager_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns PASS when all steps succeed."""
        from act.artifacts.manifest import CommandResult, Manifest, PlatformInfo
        from act.verifier.pipeline import StepResult

        # Setup directory mocks
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)
        logs_dir = run_dir / "logs"
        logs_dir.mkdir()

        mock_create_run_dir.return_value = ("run_test", run_dir)
        mock_create_logs_dir.return_value = logs_dir
        mock_create_tmp_dir.return_value = run_dir / "tmp"
        mock_create_db_dir.return_value = run_dir / "db"

        # Setup container manager mock
        mock_manager = MagicMock()
        mock_manager.is_docker_available.return_value = True
        mock_manager.image_exists.return_value = True
        mock_container = MagicMock()
        mock_manager.create_container.return_value = mock_container
        mock_container_manager_class.return_value = mock_manager

        # Setup pipeline mock
        mock_pipeline = MagicMock()
        mock_pipeline.execute_steps.return_value = (
            [
                StepResult(name="test", command="npm test", exit_code=0, duration_ms=100)
            ],
            True,  # all_passed
        )
        mock_pipeline_class.return_value = mock_pipeline

        # Setup artifact mocks
        mock_extract_tail.return_value = "Test output"
        mock_list_artifacts.return_value = [str(logs_dir / "combined.log")]
        mock_read_manifest.return_value = Manifest(
            run_id="run_test",
            timestamp_start="2024-01-15T14:32:00Z",
            timestamp_end="2024-01-15T14:33:00Z",
            commit_sha="abc123",
            status="PASS",
            commands_executed=[
                CommandResult(name="test", command="npm test", exit_code=0, duration_ms=100)
            ],
            platform=PlatformInfo(os="linux", arch="x64", container_image="node:20-slim"),
        )

        config = _create_test_config()

        response = verify(
            repo_path=tmp_path / "repo",
            config=config,
            artifact_dir=tmp_path / "artifacts",
        )

        assert response.status == VerifierStatus.PASS
        assert response.run_id == "run_test"
        assert response.tail_log == "Test output"
        assert response.manifest is not None

    @patch("act.verifier.executor.ContainerManager")
    @patch("act.verifier.executor.PipelineExecutor")
    @patch("act.verifier.executor.ensure_artifact_dir_structure")
    @patch("act.verifier.executor.create_run_dir")
    @patch("act.verifier.executor.create_logs_dir")
    @patch("act.verifier.executor.create_tmp_dir")
    @patch("act.verifier.executor.create_db_dir")
    @patch("act.verifier.executor.write_manifest")
    @patch("act.verifier.executor.read_manifest")
    @patch("act.verifier.executor.extract_tail_log")
    @patch("act.verifier.executor.list_artifact_paths")
    def test_destroys_container_on_success(
        self,
        mock_list_artifacts: MagicMock,
        mock_extract_tail: MagicMock,
        mock_read_manifest: MagicMock,
        mock_write_manifest: MagicMock,
        mock_create_db_dir: MagicMock,
        mock_create_tmp_dir: MagicMock,
        mock_create_logs_dir: MagicMock,
        mock_create_run_dir: MagicMock,
        mock_ensure_artifact: MagicMock,
        mock_pipeline_class: MagicMock,
        mock_container_manager_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Destroys container after successful execution."""
        from act.artifacts.manifest import Manifest, PlatformInfo

        # Setup mocks
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)
        logs_dir = run_dir / "logs"
        logs_dir.mkdir()

        mock_create_run_dir.return_value = ("run_test", run_dir)
        mock_create_logs_dir.return_value = logs_dir
        mock_create_tmp_dir.return_value = run_dir / "tmp"
        mock_create_db_dir.return_value = run_dir / "db"

        mock_manager = MagicMock()
        mock_manager.is_docker_available.return_value = True
        mock_manager.image_exists.return_value = True
        mock_container = MagicMock()
        mock_manager.create_container.return_value = mock_container
        mock_container_manager_class.return_value = mock_manager

        mock_pipeline = MagicMock()
        mock_pipeline.execute_steps.return_value = ([], True)
        mock_pipeline_class.return_value = mock_pipeline

        mock_extract_tail.return_value = ""
        mock_list_artifacts.return_value = []
        mock_read_manifest.return_value = Manifest(
            run_id="run_test",
            timestamp_start="2024-01-15T14:32:00Z",
            timestamp_end="2024-01-15T14:33:00Z",
            commit_sha="abc123",
            status="PASS",
            commands_executed=[],
            platform=PlatformInfo(os="linux", arch="x64", container_image="node:20-slim"),
        )

        config = _create_test_config()
        verify(
            repo_path=tmp_path / "repo",
            config=config,
            artifact_dir=tmp_path / "artifacts",
        )

        mock_manager.destroy_container.assert_called_once_with(mock_container)


class TestVerifyFail:
    """Tests for verify() when pipeline fails."""

    @patch("act.verifier.executor.ContainerManager")
    @patch("act.verifier.executor.PipelineExecutor")
    @patch("act.verifier.executor.ensure_artifact_dir_structure")
    @patch("act.verifier.executor.create_run_dir")
    @patch("act.verifier.executor.create_logs_dir")
    @patch("act.verifier.executor.create_tmp_dir")
    @patch("act.verifier.executor.create_db_dir")
    @patch("act.verifier.executor.write_manifest")
    @patch("act.verifier.executor.read_manifest")
    @patch("act.verifier.executor.extract_tail_log")
    @patch("act.verifier.executor.list_artifact_paths")
    def test_returns_fail_on_step_failure(
        self,
        mock_list_artifacts: MagicMock,
        mock_extract_tail: MagicMock,
        mock_read_manifest: MagicMock,
        mock_write_manifest: MagicMock,
        mock_create_db_dir: MagicMock,
        mock_create_tmp_dir: MagicMock,
        mock_create_logs_dir: MagicMock,
        mock_create_run_dir: MagicMock,
        mock_ensure_artifact: MagicMock,
        mock_pipeline_class: MagicMock,
        mock_container_manager_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Returns FAIL when a step fails."""
        from act.artifacts.manifest import CommandResult, Manifest, PlatformInfo
        from act.verifier.pipeline import StepResult

        # Setup mocks
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)
        logs_dir = run_dir / "logs"
        logs_dir.mkdir()

        mock_create_run_dir.return_value = ("run_test", run_dir)
        mock_create_logs_dir.return_value = logs_dir
        mock_create_tmp_dir.return_value = run_dir / "tmp"
        mock_create_db_dir.return_value = run_dir / "db"

        mock_manager = MagicMock()
        mock_manager.is_docker_available.return_value = True
        mock_manager.image_exists.return_value = True
        mock_container = MagicMock()
        mock_manager.create_container.return_value = mock_container
        mock_container_manager_class.return_value = mock_manager

        mock_pipeline = MagicMock()
        mock_pipeline.execute_steps.return_value = (
            [
                StepResult(name="test", command="npm test", exit_code=1, duration_ms=100)
            ],
            False,  # all_passed = False
        )
        mock_pipeline_class.return_value = mock_pipeline

        mock_extract_tail.return_value = "Error: test failed"
        mock_list_artifacts.return_value = []
        mock_read_manifest.return_value = Manifest(
            run_id="run_test",
            timestamp_start="2024-01-15T14:32:00Z",
            timestamp_end="2024-01-15T14:33:00Z",
            commit_sha="abc123",
            status="FAIL",
            commands_executed=[
                CommandResult(name="test", command="npm test", exit_code=1, duration_ms=100)
            ],
            platform=PlatformInfo(os="linux", arch="x64", container_image="node:20-slim"),
        )

        config = _create_test_config()

        response = verify(
            repo_path=tmp_path / "repo",
            config=config,
            artifact_dir=tmp_path / "artifacts",
        )

        assert response.status == VerifierStatus.FAIL
        assert response.run_id == "run_test"
        assert response.tail_log == "Error: test failed"


class TestVerifyContainerCleanup:
    """Tests for container cleanup behavior."""

    @patch("act.verifier.executor.ContainerManager")
    @patch("act.verifier.executor.PipelineExecutor")
    @patch("act.verifier.executor.ensure_artifact_dir_structure")
    @patch("act.verifier.executor.create_run_dir")
    @patch("act.verifier.executor.create_logs_dir")
    @patch("act.verifier.executor.create_tmp_dir")
    @patch("act.verifier.executor.create_db_dir")
    @patch("act.verifier.executor.write_manifest")
    @patch("act.verifier.executor.read_manifest")
    @patch("act.verifier.executor.extract_tail_log")
    @patch("act.verifier.executor.list_artifact_paths")
    def test_destroys_container_on_failure(
        self,
        mock_list_artifacts: MagicMock,
        mock_extract_tail: MagicMock,
        mock_read_manifest: MagicMock,
        mock_write_manifest: MagicMock,
        mock_create_db_dir: MagicMock,
        mock_create_tmp_dir: MagicMock,
        mock_create_logs_dir: MagicMock,
        mock_create_run_dir: MagicMock,
        mock_ensure_artifact: MagicMock,
        mock_pipeline_class: MagicMock,
        mock_container_manager_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Destroys container even when pipeline fails."""
        from act.artifacts.manifest import CommandResult, Manifest, PlatformInfo
        from act.verifier.pipeline import StepResult

        # Setup mocks
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)
        logs_dir = run_dir / "logs"
        logs_dir.mkdir()

        mock_create_run_dir.return_value = ("run_test", run_dir)
        mock_create_logs_dir.return_value = logs_dir
        mock_create_tmp_dir.return_value = run_dir / "tmp"
        mock_create_db_dir.return_value = run_dir / "db"

        mock_manager = MagicMock()
        mock_manager.is_docker_available.return_value = True
        mock_manager.image_exists.return_value = True
        mock_container = MagicMock()
        mock_manager.create_container.return_value = mock_container
        mock_container_manager_class.return_value = mock_manager

        mock_pipeline = MagicMock()
        mock_pipeline.execute_steps.return_value = (
            [StepResult(name="test", command="npm test", exit_code=1, duration_ms=100)],
            False,
        )
        mock_pipeline_class.return_value = mock_pipeline

        mock_extract_tail.return_value = ""
        mock_list_artifacts.return_value = []
        mock_read_manifest.return_value = Manifest(
            run_id="run_test",
            timestamp_start="2024-01-15T14:32:00Z",
            timestamp_end="2024-01-15T14:33:00Z",
            commit_sha="abc123",
            status="FAIL",
            commands_executed=[
                CommandResult(name="test", command="npm test", exit_code=1, duration_ms=100)
            ],
            platform=PlatformInfo(os="linux", arch="x64", container_image="node:20-slim"),
        )

        config = _create_test_config()
        verify(
            repo_path=tmp_path / "repo",
            config=config,
            artifact_dir=tmp_path / "artifacts",
        )

        mock_manager.destroy_container.assert_called_once_with(mock_container)
