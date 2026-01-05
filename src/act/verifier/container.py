"""Docker container creation and lifecycle management."""

import contextlib
from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, ImageNotFound
from docker.models.containers import Container

from act.verifier.exceptions import ContainerError, InfraErrorType

# Default resource limits from specs
DEFAULT_CPU_LIMIT = 4
DEFAULT_MEMORY_LIMIT = "8g"


@dataclass
class ContainerConfig:
    """Configuration for container creation.

    Attributes:
        image: Docker image name and tag.
        repo_path: Path to repository root (mounted read-only).
        run_dir: Path to run directory (mounted read-write as /artifacts).
        cpu_limit: CPU limit for container.
        memory_limit: Memory limit for container (e.g., "8g").
        working_dir: Working directory inside container.
    """

    image: str
    repo_path: Path
    run_dir: Path
    cpu_limit: int = DEFAULT_CPU_LIMIT
    memory_limit: str = DEFAULT_MEMORY_LIMIT
    working_dir: str = "/workspace"


def classify_docker_error(error: DockerException) -> InfraErrorType:
    """Classify Docker exception to InfraErrorType.

    Args:
        error: Docker exception to classify.

    Returns:
        Appropriate InfraErrorType for the error.
    """
    error_str = str(error).lower()

    if isinstance(error, ImageNotFound):
        return InfraErrorType.IMAGE_PULL

    if "oom" in error_str or "memory" in error_str or "killed" in error_str:
        return InfraErrorType.RESOURCE_EXHAUSTION

    if isinstance(error, APIError):
        if "connection" in error_str or "refused" in error_str:
            return InfraErrorType.DOCKER_UNAVAILABLE
        return InfraErrorType.CONTAINER_CREATION

    if "connection" in error_str or "refused" in error_str:
        return InfraErrorType.DOCKER_UNAVAILABLE

    return InfraErrorType.UNKNOWN


class ContainerManager:
    """Manages Docker container lifecycle.

    This class handles container creation, execution, and destruction
    for verification runs.
    """

    def __init__(self, client: docker.DockerClient | None = None) -> None:
        """Initialize with optional Docker client.

        Args:
            client: Optional Docker client. If not provided, uses default.
        """
        self._client = client
        self._client_initialized = client is not None

    def _get_client(self) -> docker.DockerClient:
        """Get Docker client, initializing lazily if needed.

        Returns:
            Docker client instance.

        Raises:
            ContainerError: If Docker is unavailable.
        """
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client_initialized = True
            except DockerException as e:
                raise ContainerError(f"Failed to connect to Docker: {e}") from e
        return self._client

    def is_docker_available(self) -> bool:
        """Check if Docker daemon is available.

        Returns:
            True if Docker is available and responding.
        """
        try:
            client = self._get_client()
            client.ping()
            return True
        except (DockerException, ContainerError):
            return False

    def pull_image(self, image: str) -> None:
        """Pull Docker image if not present.

        Args:
            image: Image name and tag to pull.

        Raises:
            ContainerError: If image pull fails.
        """
        client = self._get_client()
        try:
            client.images.pull(image)
        except DockerException as e:
            raise ContainerError(
                f"Failed to pull image {image}: {e}",
            ) from e

    def image_exists(self, image: str) -> bool:
        """Check if image exists locally.

        Args:
            image: Image name and tag to check.

        Returns:
            True if image exists locally.
        """
        client = self._get_client()
        try:
            client.images.get(image)
            return True
        except ImageNotFound:
            return False
        except DockerException:
            return False

    def create_container(self, config: ContainerConfig) -> Container:
        """Create ephemeral container with configured mounts.

        Creates a container with:
        - Repository mounted read-only at /workspace
        - Run directory mounted read-write at /artifacts

        Args:
            config: Container configuration.

        Returns:
            Created container instance.

        Raises:
            ContainerError: If container creation fails.
        """
        client = self._get_client()

        # Define mounts
        volumes: dict[str, dict[str, str]] = {
            str(config.repo_path.resolve()): {
                "bind": "/workspace",
                "mode": "ro",  # Read-only
            },
            str(config.run_dir.resolve()): {
                "bind": "/artifacts",
                "mode": "rw",  # Read-write
            },
        }

        # Convert memory limit to bytes for nano_cpus calculation
        # CPU limit is in number of CPUs, Docker expects nano_cpus (1e9 per CPU)
        nano_cpus = int(config.cpu_limit * 1e9)

        try:
            container: Container = client.containers.create(
                image=config.image,
                volumes=volumes,
                working_dir=config.working_dir,
                nano_cpus=nano_cpus,
                mem_limit=config.memory_limit,
                # Keep container running for exec commands
                command="tail -f /dev/null",
                detach=True,
            )
            return container
        except DockerException as e:
            raise ContainerError(
                f"Failed to create container: {e}",
            ) from e

    def start_container(self, container: Container) -> None:
        """Start a created container.

        Args:
            container: Container to start.

        Raises:
            ContainerError: If container fails to start.
        """
        try:
            container.start()
        except DockerException as e:
            raise ContainerError(f"Failed to start container: {e}") from e

    def destroy_container(self, container: Container) -> None:
        """Destroy container after run.

        Stops and removes the container, handling already-removed
        containers gracefully.

        Args:
            container: Container to destroy.
        """
        with contextlib.suppress(DockerException):
            container.stop(timeout=10)

        with contextlib.suppress(DockerException):
            container.remove(force=True)

    def exec_in_container(
        self,
        container: Container,
        command: str,
        env_vars: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> tuple[int, str]:
        """Execute command in container.

        Args:
            container: Container to execute in.
            command: Shell command to execute.
            env_vars: Optional environment variables.
            timeout: Optional timeout in seconds.

        Returns:
            Tuple of (exit_code, output).

        Raises:
            ContainerError: If execution fails.
        """
        try:
            # Build environment list as KEY=VALUE strings
            environment: list[str] | None = None
            if env_vars:
                environment = [f"{k}={v}" for k, v in env_vars.items()]

            # Execute command
            exec_result = container.exec_run(
                cmd=["sh", "-c", command],
                environment=environment,
                workdir="/workspace",
                demux=False,  # Combined stdout/stderr
            )

            exit_code: int = exec_result.exit_code
            output: bytes = exec_result.output or b""

            return exit_code, output.decode("utf-8", errors="replace")

        except DockerException as e:
            raise ContainerError(f"Failed to execute command: {e}") from e
