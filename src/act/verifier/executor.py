"""Main entry point for verification execution."""

from pathlib import Path

from act.artifacts import (
    CommandResult,
    create_run_dir,
    ensure_artifact_dir_structure,
    get_utc_timestamp,
    read_manifest,
    write_manifest,
)
from act.config.env import DEFAULT_ARTIFACT_DIR, load_env_config
from act.config.schema import AgentConfig
from act.verifier.container import (
    ContainerConfig,
    ContainerManager,
)
from act.verifier.exceptions import ContainerError, InfraErrorType, PipelineError
from act.verifier.logs import (
    create_db_dir,
    create_logs_dir,
    create_tmp_dir,
    extract_tail_log,
    list_artifact_paths,
)
from act.verifier.pipeline import PipelineExecutor
from act.verifier.response import (
    VerifierResponse,
    create_fail_response,
    create_infra_error_response,
    create_pass_response,
)


def verify(
    repo_path: Path,
    config: AgentConfig,
    artifact_dir: Path | None = None,
) -> VerifierResponse:
    """Execute full verification pipeline.

    This is the main entry point for the Verifier component.
    It orchestrates container creation, pipeline execution, and
    artifact management.

    Args:
        repo_path: Path to repository root.
        config: Agent configuration with verification steps.
        artifact_dir: Override artifact directory (uses env default if None).

    Returns:
        VerifierResponse with PASS, FAIL, or INFRA_ERROR status.
    """
    # Resolve artifact directory
    if artifact_dir is None:
        env_config = load_env_config()
        artifact_dir = env_config.artifact_dir or DEFAULT_ARTIFACT_DIR

    # Ensure artifact directory structure exists
    ensure_artifact_dir_structure(artifact_dir)

    # Create run directory
    run_id, run_dir = create_run_dir(artifact_dir)

    # Create subdirectories
    logs_dir = create_logs_dir(run_dir)
    create_tmp_dir(run_dir)
    create_db_dir(run_dir)

    # Record start time
    timestamp_start = get_utc_timestamp()

    # Create container manager and check Docker availability
    container_manager = ContainerManager()

    if not container_manager.is_docker_available():
        return create_infra_error_response(
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_message="Docker daemon is not running or not accessible",
            run_id=run_id,
        )

    # Get container image
    container_image = config.verification.container_image

    # Pull image if needed
    if not container_manager.image_exists(container_image):
        try:
            container_manager.pull_image(container_image)
        except ContainerError as e:
            return create_infra_error_response(
                error_type=InfraErrorType.IMAGE_PULL,
                error_message=f"Failed to pull image {container_image}: {e}",
                run_id=run_id,
            )

    # Create container config
    container_config = ContainerConfig(
        image=container_image,
        repo_path=repo_path,
        run_dir=run_dir,
    )

    # Create container
    try:
        container = container_manager.create_container(container_config)
    except ContainerError as e:
        return create_infra_error_response(
            error_type=InfraErrorType.CONTAINER_CREATION,
            error_message=f"Failed to create container: {e}",
            run_id=run_id,
        )

    try:
        # Start container
        try:
            container_manager.start_container(container)
        except ContainerError as e:
            return create_infra_error_response(
                error_type=InfraErrorType.CONTAINER_CREATION,
                error_message=f"Failed to start container: {e}",
                run_id=run_id,
            )

        # Set up environment variables for test write redirection
        env_vars = {
            "TMPDIR": "/artifacts/tmp",
            "TEST_DB_PATH": "/artifacts/db",
        }

        # Get timeout from config
        timeout_ms = config.timeouts.verification_step

        # Create pipeline executor
        pipeline = PipelineExecutor(
            container_manager=container_manager,
            container=container,
            logs_dir=logs_dir,
            timeout_ms=timeout_ms,
        )

        # Execute verification steps
        try:
            results, all_passed = pipeline.execute_steps(
                config.verification.steps,
                env_vars=env_vars,
            )
        except PipelineError as e:
            # Check for resource exhaustion
            error_str = str(e).lower()
            if "memory" in error_str or "oom" in error_str or "killed" in error_str:
                return create_infra_error_response(
                    error_type=InfraErrorType.RESOURCE_EXHAUSTION,
                    error_message=f"Container killed due to resource exhaustion: {e}",
                    run_id=run_id,
                    tail_log=extract_tail_log(logs_dir / "combined.log"),
                    artifact_paths=list_artifact_paths(run_dir),
                )
            raise

        # Record end time
        timestamp_end = get_utc_timestamp()

        # Convert step results to CommandResult
        commands_executed = [
            CommandResult(
                name=r.name,
                command=r.command,
                exit_code=r.exit_code,
                duration_ms=r.duration_ms,
            )
            for r in results
        ]

        # Determine status
        status = "PASS" if all_passed else "FAIL"

        # Write manifest
        write_manifest(
            run_dir=run_dir,
            run_id=run_id,
            timestamp_start=timestamp_start,
            timestamp_end=timestamp_end,
            status=status,
            commands_executed=commands_executed,
            container_image=container_image,
        )

        # Extract tail log
        tail_log = extract_tail_log(logs_dir / "combined.log")

        # List artifact paths
        artifact_paths = list_artifact_paths(run_dir)

        # Read back manifest for response
        manifest = read_manifest(run_dir / "manifest.json")

        # Build response
        if all_passed:
            return create_pass_response(
                run_id=run_id,
                tail_log=tail_log,
                artifact_paths=artifact_paths,
                manifest=manifest,
            )
        else:
            return create_fail_response(
                run_id=run_id,
                tail_log=tail_log,
                artifact_paths=artifact_paths,
                manifest=manifest,
            )

    finally:
        # Always destroy container
        container_manager.destroy_container(container)
