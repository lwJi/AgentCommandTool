"""Sequential step execution and logging."""

import contextlib
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docker.models.containers import Container

from act.config.schema import VerificationStep
from act.verifier.container import ContainerManager
from act.verifier.logs import append_combined_log, write_step_log

# Default timeout for verification steps (5 minutes in milliseconds)
DEFAULT_TIMEOUT_MS = 300000


@dataclass
class StepResult:
    """Result of executing a single pipeline step.

    Attributes:
        name: Name of the step.
        command: The command that was executed.
        exit_code: Exit code of the command.
        duration_ms: Duration in milliseconds.
        timed_out: Whether the step timed out.
    """

    name: str
    command: str
    exit_code: int
    duration_ms: int
    timed_out: bool = False


class PipelineExecutor:
    """Executes verification pipeline steps in container.

    This class manages the execution of verification steps, handling:
    - Sequential execution
    - Per-step logging
    - Timeout handling
    - Combined log aggregation
    """

    def __init__(
        self,
        container_manager: ContainerManager,
        container: Container,
        logs_dir: Path,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        """Initialize pipeline executor.

        Args:
            container_manager: Container manager instance.
            container: Container to execute steps in.
            logs_dir: Directory to write logs to.
            timeout_ms: Timeout per step in milliseconds.
        """
        self._container_manager = container_manager
        self._container = container
        self._logs_dir = logs_dir
        self._timeout_ms = timeout_ms

    def execute_steps(
        self,
        steps: list[VerificationStep],
        env_vars: dict[str, str] | None = None,
    ) -> tuple[list[StepResult], bool]:
        """Execute steps sequentially, stop on first failure.

        Args:
            steps: List of verification steps to execute.
            env_vars: Optional environment variables for all steps.

        Returns:
            Tuple of (results, all_passed).
            - results: List of StepResult for executed steps.
            - all_passed: True if all steps passed.
        """
        results: list[StepResult] = []
        all_passed = True

        for i, step in enumerate(steps, start=1):
            result = self._execute_step(step, i, env_vars)
            results.append(result)

            if result.exit_code != 0:
                all_passed = False
                break  # Stop on first failure

        return results, all_passed

    def _execute_step(
        self,
        step: VerificationStep,
        step_number: int,
        env_vars: dict[str, str] | None = None,
    ) -> StepResult:
        """Execute a single step with timeout handling.

        Args:
            step: Verification step to execute.
            step_number: 1-based step number.
            env_vars: Optional environment variables.

        Returns:
            StepResult with execution details.
        """
        start_time = datetime.now(UTC)

        # Calculate timeout in seconds
        timeout_seconds = self._timeout_ms / 1000

        # Execute with timeout
        exit_code, output, timed_out = self._execute_with_timeout(
            step.command,
            env_vars,
            timeout_seconds,
        )

        end_time = datetime.now(UTC)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Write logs
        step_header = f"=== Step {step_number}: {step.name} ===\n"
        step_header += f"Command: {step.command}\n"
        step_header += f"{'=' * 40}\n\n"

        full_output = step_header + output

        if timed_out:
            full_output += f"\n\n[TIMEOUT] Step killed after {timeout_seconds}s\n"

        full_output += f"\n\nExit code: {exit_code}\n"

        # Write individual step log
        write_step_log(self._logs_dir, step_number, step.name, full_output)

        # Append to combined log
        append_combined_log(self._logs_dir, full_output)

        return StepResult(
            name=step.name,
            command=step.command,
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )

    def _execute_with_timeout(
        self,
        command: str,
        env_vars: dict[str, str] | None,
        timeout_seconds: float,
    ) -> tuple[int, str, bool]:
        """Execute command with timeout.

        Args:
            command: Command to execute.
            env_vars: Environment variables.
            timeout_seconds: Timeout in seconds.

        Returns:
            Tuple of (exit_code, output, timed_out).
        """
        result: dict[str, Any] = {
            "exit_code": -1,
            "output": "",
            "timed_out": False,
        }

        def run_command() -> None:
            try:
                exit_code, output = self._container_manager.exec_in_container(
                    self._container,
                    command,
                    env_vars=env_vars,
                )
                result["exit_code"] = exit_code
                result["output"] = output
            except Exception as e:
                result["exit_code"] = -1
                result["output"] = f"Error executing command: {e}"

        thread = threading.Thread(target=run_command)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            # Timeout occurred
            result["timed_out"] = True
            result["exit_code"] = 124  # Standard timeout exit code

            # Try to kill any running processes in the container
            with contextlib.suppress(Exception):
                self._container_manager.exec_in_container(
                    self._container,
                    "pkill -9 -f .",
                    env_vars=None,
                )

            # Wait a bit more for thread to finish
            thread.join(timeout=5)

        return result["exit_code"], result["output"], result["timed_out"]
