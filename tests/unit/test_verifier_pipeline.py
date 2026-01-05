"""Tests for verifier pipeline execution."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from act.config.schema import VerificationStep
from act.verifier.pipeline import (
    DEFAULT_TIMEOUT_MS,
    PipelineExecutor,
    StepResult,
)


class TestStepResult:
    """Tests for StepResult dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """Creates StepResult with required fields."""
        result = StepResult(
            name="test",
            command="npm test",
            exit_code=0,
            duration_ms=1234,
        )

        assert result.name == "test"
        assert result.command == "npm test"
        assert result.exit_code == 0
        assert result.duration_ms == 1234

    def test_timed_out_defaults_to_false(self) -> None:
        """timed_out defaults to False."""
        result = StepResult(
            name="test",
            command="npm test",
            exit_code=0,
            duration_ms=1234,
        )

        assert result.timed_out is False

    def test_can_set_timed_out_true(self) -> None:
        """Can set timed_out to True."""
        result = StepResult(
            name="test",
            command="npm test",
            exit_code=124,
            duration_ms=5000,
            timed_out=True,
        )

        assert result.timed_out is True


class TestPipelineExecutor:
    """Tests for PipelineExecutor class."""

    def test_initializes_with_parameters(self, tmp_path: Path) -> None:
        """Initializes with provided parameters."""
        mock_manager = MagicMock()
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
            timeout_ms=60000,
        )

        assert executor._timeout_ms == 60000

    def test_default_timeout_is_5_minutes(self) -> None:
        """Default timeout is 5 minutes (300000ms)."""
        assert DEFAULT_TIMEOUT_MS == 300000


class TestPipelineExecutorExecuteSteps:
    """Tests for PipelineExecutor.execute_steps method."""

    def test_executes_all_steps_on_success(self, tmp_path: Path) -> None:
        """Executes all steps when all succeed."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (0, "success")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [
            VerificationStep(name="install", command="npm ci"),
            VerificationStep(name="build", command="npm run build"),
            VerificationStep(name="test", command="npm test"),
        ]

        results, all_passed = executor.execute_steps(steps)

        assert len(results) == 3
        assert all_passed is True
        assert all(r.exit_code == 0 for r in results)

    def test_stops_on_first_failure(self, tmp_path: Path) -> None:
        """Stops execution on first failing step."""
        mock_manager = MagicMock()
        # First succeeds, second fails
        mock_manager.exec_in_container.side_effect = [
            (0, "install success"),
            (1, "build failed"),
        ]
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [
            VerificationStep(name="install", command="npm ci"),
            VerificationStep(name="build", command="npm run build"),
            VerificationStep(name="test", command="npm test"),
        ]

        results, all_passed = executor.execute_steps(steps)

        assert len(results) == 2  # Only 2 steps executed
        assert all_passed is False
        assert results[0].exit_code == 0
        assert results[1].exit_code == 1

    def test_returns_all_passed_true_on_success(self, tmp_path: Path) -> None:
        """Returns all_passed=True when all steps succeed."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (0, "success")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [VerificationStep(name="test", command="npm test")]
        results, all_passed = executor.execute_steps(steps)

        assert all_passed is True

    def test_returns_all_passed_false_on_failure(self, tmp_path: Path) -> None:
        """Returns all_passed=False when any step fails."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (1, "failed")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [VerificationStep(name="test", command="npm test")]
        results, all_passed = executor.execute_steps(steps)

        assert all_passed is False

    def test_passes_environment_variables(self, tmp_path: Path) -> None:
        """Passes environment variables to steps."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (0, "success")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [VerificationStep(name="test", command="npm test")]
        env_vars = {"TMPDIR": "/artifacts/tmp"}
        executor.execute_steps(steps, env_vars=env_vars)

        call_kwargs = mock_manager.exec_in_container.call_args.kwargs
        assert call_kwargs["env_vars"] == env_vars


class TestPipelineExecutorLogs:
    """Tests for PipelineExecutor logging behavior."""

    def test_writes_step_log_files(self, tmp_path: Path) -> None:
        """Writes individual step log files."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (0, "test output")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [
            VerificationStep(name="install", command="npm ci"),
            VerificationStep(name="test", command="npm test"),
        ]
        executor.execute_steps(steps)

        assert (logs_dir / "step-01-install.log").exists()
        assert (logs_dir / "step-02-test.log").exists()

    def test_writes_combined_log(self, tmp_path: Path) -> None:
        """Writes combined.log with all step outputs."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (0, "test output")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [
            VerificationStep(name="install", command="npm ci"),
            VerificationStep(name="test", command="npm test"),
        ]
        executor.execute_steps(steps)

        combined_log = logs_dir / "combined.log"
        assert combined_log.exists()
        content = combined_log.read_text()
        assert "install" in content
        assert "test" in content

    def test_log_contains_command_output(self, tmp_path: Path) -> None:
        """Log files contain command output."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (0, "Expected output text")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [VerificationStep(name="test", command="npm test")]
        executor.execute_steps(steps)

        content = (logs_dir / "step-01-test.log").read_text()
        assert "Expected output text" in content

    def test_log_contains_exit_code(self, tmp_path: Path) -> None:
        """Log files contain exit code."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (1, "Error output")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [VerificationStep(name="test", command="npm test")]
        executor.execute_steps(steps)

        content = (logs_dir / "step-01-test.log").read_text()
        assert "Exit code: 1" in content


class TestPipelineExecutorStepResult:
    """Tests for step result details."""

    def test_result_contains_step_name(self, tmp_path: Path) -> None:
        """Result contains step name."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (0, "output")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [VerificationStep(name="install", command="npm ci")]
        results, _ = executor.execute_steps(steps)

        assert results[0].name == "install"

    def test_result_contains_command(self, tmp_path: Path) -> None:
        """Result contains command."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (0, "output")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [VerificationStep(name="install", command="npm ci")]
        results, _ = executor.execute_steps(steps)

        assert results[0].command == "npm ci"

    def test_result_contains_exit_code(self, tmp_path: Path) -> None:
        """Result contains exit code."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (42, "output")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [VerificationStep(name="test", command="exit 42")]
        results, _ = executor.execute_steps(steps)

        assert results[0].exit_code == 42

    def test_result_contains_duration(self, tmp_path: Path) -> None:
        """Result contains duration in milliseconds."""
        mock_manager = MagicMock()
        mock_manager.exec_in_container.return_value = (0, "output")
        mock_container = MagicMock()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        executor = PipelineExecutor(
            container_manager=mock_manager,
            container=mock_container,
            logs_dir=logs_dir,
        )

        steps = [VerificationStep(name="test", command="npm test")]
        results, _ = executor.execute_steps(steps)

        assert results[0].duration_ms >= 0
        assert isinstance(results[0].duration_ms, int)
