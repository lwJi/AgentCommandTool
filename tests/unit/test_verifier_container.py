"""Tests for verifier container management."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from docker.errors import APIError, DockerException, ImageNotFound

from act.verifier.container import (
    DEFAULT_CPU_LIMIT,
    DEFAULT_MEMORY_LIMIT,
    ContainerConfig,
    ContainerManager,
    classify_docker_error,
)
from act.verifier.exceptions import ContainerError, InfraErrorType


class TestContainerConfig:
    """Tests for ContainerConfig dataclass."""

    def test_creates_with_required_fields(self, tmp_path: Path) -> None:
        """Creates config with required fields."""
        config = ContainerConfig(
            image="node:20-slim",
            repo_path=tmp_path / "repo",
            run_dir=tmp_path / "run",
        )

        assert config.image == "node:20-slim"
        assert config.repo_path == tmp_path / "repo"
        assert config.run_dir == tmp_path / "run"

    def test_has_default_cpu_limit(self, tmp_path: Path) -> None:
        """Has default CPU limit of 4."""
        config = ContainerConfig(
            image="node:20-slim",
            repo_path=tmp_path / "repo",
            run_dir=tmp_path / "run",
        )

        assert config.cpu_limit == DEFAULT_CPU_LIMIT
        assert config.cpu_limit == 4

    def test_has_default_memory_limit(self, tmp_path: Path) -> None:
        """Has default memory limit of 8g."""
        config = ContainerConfig(
            image="node:20-slim",
            repo_path=tmp_path / "repo",
            run_dir=tmp_path / "run",
        )

        assert config.memory_limit == DEFAULT_MEMORY_LIMIT
        assert config.memory_limit == "8g"

    def test_has_default_working_dir(self, tmp_path: Path) -> None:
        """Has default working directory of /workspace."""
        config = ContainerConfig(
            image="node:20-slim",
            repo_path=tmp_path / "repo",
            run_dir=tmp_path / "run",
        )

        assert config.working_dir == "/workspace"

    def test_allows_custom_limits(self, tmp_path: Path) -> None:
        """Allows custom CPU and memory limits."""
        config = ContainerConfig(
            image="node:20-slim",
            repo_path=tmp_path / "repo",
            run_dir=tmp_path / "run",
            cpu_limit=2,
            memory_limit="4g",
        )

        assert config.cpu_limit == 2
        assert config.memory_limit == "4g"


class TestClassifyDockerError:
    """Tests for classify_docker_error function."""

    def test_classifies_image_not_found(self) -> None:
        """Classifies ImageNotFound as IMAGE_PULL."""
        error = ImageNotFound("image not found")

        result = classify_docker_error(error)

        assert result == InfraErrorType.IMAGE_PULL

    def test_classifies_oom_error(self) -> None:
        """Classifies OOM errors as RESOURCE_EXHAUSTION."""
        error = DockerException("Container killed due to OOM")

        result = classify_docker_error(error)

        assert result == InfraErrorType.RESOURCE_EXHAUSTION

    def test_classifies_memory_error(self) -> None:
        """Classifies memory errors as RESOURCE_EXHAUSTION."""
        error = DockerException("Out of memory")

        result = classify_docker_error(error)

        assert result == InfraErrorType.RESOURCE_EXHAUSTION

    def test_classifies_connection_refused(self) -> None:
        """Classifies connection refused as DOCKER_UNAVAILABLE."""
        error = DockerException("Connection refused")

        result = classify_docker_error(error)

        assert result == InfraErrorType.DOCKER_UNAVAILABLE

    def test_classifies_api_error_connection(self) -> None:
        """Classifies APIError with connection issue as DOCKER_UNAVAILABLE."""
        error = APIError("Connection refused")

        result = classify_docker_error(error)

        assert result == InfraErrorType.DOCKER_UNAVAILABLE

    def test_classifies_api_error_other(self) -> None:
        """Classifies other APIError as CONTAINER_CREATION."""
        error = APIError("Some other error")

        result = classify_docker_error(error)

        assert result == InfraErrorType.CONTAINER_CREATION

    def test_classifies_unknown_error(self) -> None:
        """Classifies unknown errors as UNKNOWN."""
        error = DockerException("Some unknown error")

        result = classify_docker_error(error)

        assert result == InfraErrorType.UNKNOWN


class TestContainerManager:
    """Tests for ContainerManager class."""

    def test_accepts_custom_client(self) -> None:
        """Accepts custom Docker client."""
        mock_client = MagicMock()

        manager = ContainerManager(client=mock_client)

        # Should use provided client
        assert manager._client is mock_client

    def test_is_docker_available_returns_true_when_available(self) -> None:
        """Returns True when Docker is available."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True

        manager = ContainerManager(client=mock_client)
        result = manager.is_docker_available()

        assert result is True
        mock_client.ping.assert_called_once()

    def test_is_docker_available_returns_false_when_unavailable(self) -> None:
        """Returns False when Docker is unavailable."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = DockerException("Connection refused")

        manager = ContainerManager(client=mock_client)
        result = manager.is_docker_available()

        assert result is False


class TestContainerManagerPullImage:
    """Tests for ContainerManager.pull_image method."""

    def test_pulls_image(self) -> None:
        """Pulls specified image."""
        mock_client = MagicMock()
        manager = ContainerManager(client=mock_client)

        manager.pull_image("node:20-slim")

        mock_client.images.pull.assert_called_once_with("node:20-slim")

    def test_raises_container_error_on_failure(self) -> None:
        """Raises ContainerError on pull failure."""
        mock_client = MagicMock()
        mock_client.images.pull.side_effect = ImageNotFound("not found")
        manager = ContainerManager(client=mock_client)

        with pytest.raises(ContainerError) as exc_info:
            manager.pull_image("nonexistent:image")

        assert "Failed to pull image" in str(exc_info.value)


class TestContainerManagerImageExists:
    """Tests for ContainerManager.image_exists method."""

    def test_returns_true_when_image_exists(self) -> None:
        """Returns True when image exists locally."""
        mock_client = MagicMock()
        manager = ContainerManager(client=mock_client)

        result = manager.image_exists("node:20-slim")

        assert result is True
        mock_client.images.get.assert_called_once_with("node:20-slim")

    def test_returns_false_when_image_not_found(self) -> None:
        """Returns False when image not found."""
        mock_client = MagicMock()
        mock_client.images.get.side_effect = ImageNotFound("not found")
        manager = ContainerManager(client=mock_client)

        result = manager.image_exists("nonexistent:image")

        assert result is False


class TestContainerManagerCreateContainer:
    """Tests for ContainerManager.create_container method."""

    def test_creates_container_with_mounts(self, tmp_path: Path) -> None:
        """Creates container with correct volume mounts."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.create.return_value = mock_container

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        config = ContainerConfig(
            image="node:20-slim",
            repo_path=repo_path,
            run_dir=run_dir,
        )
        manager = ContainerManager(client=mock_client)

        container = manager.create_container(config)

        assert container is mock_container
        call_kwargs = mock_client.containers.create.call_args.kwargs
        assert call_kwargs["image"] == "node:20-slim"
        assert call_kwargs["working_dir"] == "/workspace"

    def test_mounts_repo_as_readonly(self, tmp_path: Path) -> None:
        """Mounts repository as read-only."""
        mock_client = MagicMock()
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        config = ContainerConfig(
            image="node:20-slim",
            repo_path=repo_path,
            run_dir=run_dir,
        )
        manager = ContainerManager(client=mock_client)
        manager.create_container(config)

        call_kwargs = mock_client.containers.create.call_args.kwargs
        volumes = call_kwargs["volumes"]

        # Check repo is mounted read-only
        repo_mount = volumes[str(repo_path.resolve())]
        assert repo_mount["bind"] == "/workspace"
        assert repo_mount["mode"] == "ro"

    def test_mounts_run_dir_as_readwrite(self, tmp_path: Path) -> None:
        """Mounts run directory as read-write."""
        mock_client = MagicMock()
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        config = ContainerConfig(
            image="node:20-slim",
            repo_path=repo_path,
            run_dir=run_dir,
        )
        manager = ContainerManager(client=mock_client)
        manager.create_container(config)

        call_kwargs = mock_client.containers.create.call_args.kwargs
        volumes = call_kwargs["volumes"]

        # Check run_dir is mounted read-write
        run_mount = volumes[str(run_dir.resolve())]
        assert run_mount["bind"] == "/artifacts"
        assert run_mount["mode"] == "rw"

    def test_applies_cpu_limit(self, tmp_path: Path) -> None:
        """Applies CPU limit to container."""
        mock_client = MagicMock()
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        config = ContainerConfig(
            image="node:20-slim",
            repo_path=repo_path,
            run_dir=run_dir,
            cpu_limit=2,
        )
        manager = ContainerManager(client=mock_client)
        manager.create_container(config)

        call_kwargs = mock_client.containers.create.call_args.kwargs
        # 2 CPUs = 2e9 nano_cpus
        assert call_kwargs["nano_cpus"] == 2_000_000_000

    def test_applies_memory_limit(self, tmp_path: Path) -> None:
        """Applies memory limit to container."""
        mock_client = MagicMock()
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        config = ContainerConfig(
            image="node:20-slim",
            repo_path=repo_path,
            run_dir=run_dir,
            memory_limit="4g",
        )
        manager = ContainerManager(client=mock_client)
        manager.create_container(config)

        call_kwargs = mock_client.containers.create.call_args.kwargs
        assert call_kwargs["mem_limit"] == "4g"

    def test_raises_container_error_on_failure(self, tmp_path: Path) -> None:
        """Raises ContainerError on creation failure."""
        mock_client = MagicMock()
        mock_client.containers.create.side_effect = APIError("Creation failed")

        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        config = ContainerConfig(
            image="node:20-slim",
            repo_path=repo_path,
            run_dir=run_dir,
        )
        manager = ContainerManager(client=mock_client)

        with pytest.raises(ContainerError) as exc_info:
            manager.create_container(config)

        assert "Failed to create container" in str(exc_info.value)


class TestContainerManagerStartContainer:
    """Tests for ContainerManager.start_container method."""

    def test_starts_container(self) -> None:
        """Starts the container."""
        mock_client = MagicMock()
        mock_container = MagicMock()

        manager = ContainerManager(client=mock_client)
        manager.start_container(mock_container)

        mock_container.start.assert_called_once()

    def test_raises_container_error_on_failure(self) -> None:
        """Raises ContainerError on start failure."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.start.side_effect = DockerException("Start failed")

        manager = ContainerManager(client=mock_client)

        with pytest.raises(ContainerError) as exc_info:
            manager.start_container(mock_container)

        assert "Failed to start container" in str(exc_info.value)


class TestContainerManagerDestroyContainer:
    """Tests for ContainerManager.destroy_container method."""

    def test_stops_and_removes_container(self) -> None:
        """Stops and removes the container."""
        mock_client = MagicMock()
        mock_container = MagicMock()

        manager = ContainerManager(client=mock_client)
        manager.destroy_container(mock_container)

        mock_container.stop.assert_called_once_with(timeout=10)
        mock_container.remove.assert_called_once_with(force=True)

    def test_handles_already_stopped_container(self) -> None:
        """Handles already stopped container gracefully."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.stop.side_effect = DockerException("Already stopped")

        manager = ContainerManager(client=mock_client)

        # Should not raise
        manager.destroy_container(mock_container)

        mock_container.remove.assert_called_once()

    def test_handles_already_removed_container(self) -> None:
        """Handles already removed container gracefully."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.remove.side_effect = DockerException("Already removed")

        manager = ContainerManager(client=mock_client)

        # Should not raise
        manager.destroy_container(mock_container)


class TestContainerManagerExecInContainer:
    """Tests for ContainerManager.exec_in_container method."""

    def test_executes_command(self) -> None:
        """Executes command in container."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = MagicMock(
            exit_code=0,
            output=b"command output",
        )

        manager = ContainerManager(client=mock_client)
        exit_code, output = manager.exec_in_container(mock_container, "npm test")

        assert exit_code == 0
        assert output == "command output"

    def test_passes_environment_variables(self) -> None:
        """Passes environment variables to command."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = MagicMock(
            exit_code=0,
            output=b"",
        )

        manager = ContainerManager(client=mock_client)
        manager.exec_in_container(
            mock_container,
            "npm test",
            env_vars={"TMPDIR": "/artifacts/tmp"},
        )

        call_kwargs = mock_container.exec_run.call_args.kwargs
        assert "TMPDIR=/artifacts/tmp" in call_kwargs["environment"]

    def test_returns_nonzero_exit_code(self) -> None:
        """Returns non-zero exit code on failure."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = MagicMock(
            exit_code=1,
            output=b"Error: test failed",
        )

        manager = ContainerManager(client=mock_client)
        exit_code, output = manager.exec_in_container(mock_container, "npm test")

        assert exit_code == 1
        assert "Error: test failed" in output

    def test_handles_empty_output(self) -> None:
        """Handles commands with no output."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exec_run.return_value = MagicMock(
            exit_code=0,
            output=None,
        )

        manager = ContainerManager(client=mock_client)
        exit_code, output = manager.exec_in_container(mock_container, "true")

        assert exit_code == 0
        assert output == ""

    def test_raises_container_error_on_failure(self) -> None:
        """Raises ContainerError on execution failure."""
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.exec_run.side_effect = DockerException("Execution failed")

        manager = ContainerManager(client=mock_client)

        with pytest.raises(ContainerError) as exc_info:
            manager.exec_in_container(mock_container, "npm test")

        assert "Failed to execute command" in str(exc_info.value)
