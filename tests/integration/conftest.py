"""Shared fixtures for integration tests."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from act.config.env import EnvConfig, LLMBackend, LLMConfig
from act.config.schema import (
    AgentConfig,
    TimeoutsConfig,
    VerificationConfig,
    VerificationStep,
)
from act.editor.coordinator import ScoutResults
from act.scouts.schemas import (
    BuildCommands,
    BuildInfo,
    BuildSystem,
    ChangeBoundaries,
    Conventions,
    FailureAnalysis,
    RelevantFile,
    Relevance,
    RepoMap,
    ScoutAResponse,
    ScoutBResponse,
    TestCommands,
    TestFramework,
    TestInfo,
)
from act.task.display import StatusDisplay
from act.task.queue import TaskQueue
from act.task.state import Task, create_task
from act.verifier.response import (
    VerifierResponse,
    VerifierStatus,
    create_fail_response,
    create_infra_error_response,
    create_pass_response,
)
from act.verifier.exceptions import InfraErrorType
from act.artifacts.manifest import Manifest, CommandResult, PlatformInfo


# =============================================================================
# Repository Fixtures
# =============================================================================


@pytest.fixture
def integration_repo(tmp_path: Path) -> Path:
    """Create a realistic repository structure for integration tests."""
    # Create directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "agent").mkdir()

    # Create sample source files
    (tmp_path / "src" / "main.py").write_text(
        'def main():\n    print("Hello, World!")\n\n\nif __name__ == "__main__":\n    main()\n'
    )
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tmp_path / "tests" / "test_main.py").write_text(
        "from src.main import main\n\n\ndef test_main():\n    main()\n"
    )

    # Create agent.yaml
    agent_yaml = """verification:
  container_image: python:3.11-slim
  steps:
    - name: install
      command: pip install -e .
    - name: test
      command: pytest tests/
"""
    (tmp_path / "agent.yaml").write_text(agent_yaml)

    # Create .gitignore with agent/
    (tmp_path / ".gitignore").write_text("agent/\n__pycache__/\n*.pyc\n")

    # Create .git directory to simulate git repo
    (tmp_path / ".git").mkdir()

    return tmp_path


@pytest.fixture
def artifact_dir(tmp_path: Path) -> Path:
    """Create artifact directory for tests."""
    artifact_path = tmp_path / "artifacts"
    artifact_path.mkdir()
    (artifact_path / "runs").mkdir()
    (artifact_path / "cache").mkdir()
    return artifact_path


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def mock_llm_config() -> LLMConfig:
    """Create mock LLM configuration."""
    return LLMConfig(
        backend=LLMBackend.ANTHROPIC,
        api_key="test-api-key-for-integration",
        model="claude-sonnet-4-20250514",
    )


@pytest.fixture
def mock_env_config(mock_llm_config: LLMConfig, artifact_dir: Path) -> EnvConfig:
    """Create mock environment configuration."""
    return EnvConfig(
        llm=mock_llm_config,
        artifact_dir=artifact_dir,
    )


@pytest.fixture
def mock_agent_config() -> AgentConfig:
    """Create mock agent configuration."""
    return AgentConfig(
        verification=VerificationConfig(
            container_image="python:3.11-slim",
            steps=[
                VerificationStep(name="install", command="pip install -e ."),
                VerificationStep(name="test", command="pytest tests/"),
            ],
        ),
        timeouts=TimeoutsConfig(
            verification_step=300000,
            scout_query=60000,
        ),
    )


# =============================================================================
# Scout Response Fixtures
# =============================================================================


@pytest.fixture
def mock_scout_a_response() -> ScoutAResponse:
    """Create a realistic mock Scout A response for integration tests."""
    return ScoutAResponse(
        schema_version="1",
        repo_map=RepoMap(
            relevant_files=[
                RelevantFile(
                    path="src/main.py",
                    purpose="Main entry point",
                    relevance=Relevance.PRIMARY,
                ),
            ],
            entry_points=["src/main.py"],
            dependency_graph={"src/main.py": []},
        ),
        risk_zones=[],
        change_boundaries=ChangeBoundaries(
            safe_slices=[],
            ordering_constraints=[],
        ),
        conventions=Conventions(
            naming="snake_case for functions",
            patterns=["simple function structure"],
            anti_patterns=[],
        ),
        prior_art=[],
        verification_tips=["Run pytest"],
        hypotheses=[],
    )


@pytest.fixture
def mock_scout_b_response() -> ScoutBResponse:
    """Create a realistic mock Scout B response for integration tests."""
    return ScoutBResponse(
        schema_version="1",
        build=BuildInfo(
            detected_system=BuildSystem.CUSTOM,
            commands=BuildCommands(
                install="pip install -e .",
                build="",
                clean="",
            ),
            prerequisites=["Python 3.11+"],
            notes="Simple Python project",
        ),
        test=TestInfo(
            detected_framework=TestFramework.PYTEST,
            commands=TestCommands(
                all="pytest tests/",
                unit="pytest tests/ -m unit",
                integration="pytest tests/ -m integration",
            ),
            coverage_command="pytest tests/ --cov",
            notes="pytest configured",
        ),
        failure_analysis=FailureAnalysis(
            root_cause="",
            affected_files=[],
            suggested_investigation=[],
            is_flaky=False,
            flaky_reason=None,
        ),
        environment_issues=[],
    )


@pytest.fixture
def mock_scout_results(
    mock_scout_a_response: ScoutAResponse,
    mock_scout_b_response: ScoutBResponse,
) -> ScoutResults:
    """Create mock scout results with both responses."""
    return ScoutResults(
        scout_a_response=mock_scout_a_response,
        scout_b_response=mock_scout_b_response,
        scout_a_raw=mock_scout_a_response.to_dict(),
        scout_b_raw=mock_scout_b_response.to_dict(),
    )


# =============================================================================
# Display and Queue Fixtures
# =============================================================================


@pytest.fixture
def capture_console() -> Console:
    """Create a console that captures output for assertions."""
    return Console(file=StringIO(), force_terminal=True, width=120)


@pytest.fixture
def integration_queue() -> TaskQueue:
    """Create a fresh task queue for each integration test."""
    return TaskQueue()


@pytest.fixture
def integration_display(capture_console: Console) -> StatusDisplay:
    """Create a status display for integration tests."""
    return StatusDisplay(console=capture_console, verbose=True)


# =============================================================================
# Verifier Response Helper Functions
# =============================================================================


def make_pass_response(
    run_id: str = "run_001",
    tail_log: str = "All tests passed\n",
) -> VerifierResponse:
    """Create a PASS verifier response.

    Args:
        run_id: Unique run identifier
        tail_log: Log output from verification

    Returns:
        VerifierResponse with PASS status
    """
    manifest = Manifest(
        run_id=run_id,
        timestamp_start="2024-01-15T12:00:00Z",
        timestamp_end="2024-01-15T12:05:00Z",
        commit_sha="abc123def456",
        status="PASS",
        commands_executed=[
            CommandResult(name="test", command="pytest tests/", exit_code=0, duration_ms=5000),
        ],
        platform=PlatformInfo(os="linux", arch="x86_64", container_image="python:3.11-slim"),
    )
    return create_pass_response(
        run_id=run_id,
        tail_log=tail_log,
        artifact_paths=[f"/artifacts/runs/{run_id}/logs/combined.log"],
        manifest=manifest,
    )


def make_fail_response(
    run_id: str = "run_001",
    error_msg: str = "Test failed",
) -> VerifierResponse:
    """Create a FAIL verifier response.

    Args:
        run_id: Unique run identifier
        error_msg: Error message in the log

    Returns:
        VerifierResponse with FAIL status
    """
    manifest = Manifest(
        run_id=run_id,
        timestamp_start="2024-01-15T12:00:00Z",
        timestamp_end="2024-01-15T12:05:00Z",
        commit_sha="abc123def456",
        status="FAIL",
        commands_executed=[
            CommandResult(name="test", command="pytest tests/", exit_code=1, duration_ms=5000),
        ],
        platform=PlatformInfo(os="linux", arch="x86_64", container_image="python:3.11-slim"),
    )
    return create_fail_response(
        run_id=run_id,
        tail_log=f"FAILED: {error_msg}\n",
        artifact_paths=[f"/artifacts/runs/{run_id}/logs/combined.log"],
        manifest=manifest,
    )


def make_infra_error_response(
    error_type: InfraErrorType = InfraErrorType.DOCKER_UNAVAILABLE,
    error_msg: str = "Docker daemon is not running",
    run_id: str | None = None,
) -> VerifierResponse:
    """Create an INFRA_ERROR verifier response.

    Args:
        error_type: Type of infrastructure error
        error_msg: Error message
        run_id: Optional run ID (may be None if error occurred before run started)

    Returns:
        VerifierResponse with INFRA_ERROR status
    """
    return create_infra_error_response(
        error_type=error_type,
        error_message=error_msg,
        run_id=run_id,
    )


# =============================================================================
# Task Fixtures
# =============================================================================


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task for testing."""
    return create_task("Fix the login bug in auth module")


@pytest.fixture
def sample_dry_run_task() -> Task:
    """Create a sample dry-run task for testing."""
    return create_task("Add logging to main function", dry_run=True)


# =============================================================================
# Editor Fixtures (for quick access in tests)
# =============================================================================


@pytest.fixture
def mock_editor_context() -> dict[str, Any]:
    """Create a mock editor context dictionary."""
    return {
        "hypothesis": "Fix by updating validation logic",
        "files_modified": ["src/main.py"],
        "verify_attempts": 0,
        "consecutive_failures": 0,
        "total_verify_loops": 0,
    }
