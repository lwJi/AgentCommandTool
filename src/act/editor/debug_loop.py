"""Debug loop with iteration controls.

Implements the fix-forward strategy with REPLAN and hard stop thresholds.
Tracks consecutive failures and total verification loops.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Iteration control thresholds
CONSECUTIVE_FAILURE_THRESHOLD = 3  # Triggers REPLAN
TOTAL_VERIFY_LOOP_THRESHOLD = 12  # Triggers hard stop
MAX_REPLANS = 3  # Maximum number of REPLANs (at attempts 3, 6, 9)


class LoopAction(Enum):
    """Action to take after a verification result."""

    CONTINUE = "continue"  # Continue with fix-forward
    REPLAN = "replan"  # Trigger REPLAN
    HARD_STOP = "hard_stop"  # Trigger hard stop
    SUCCESS = "success"  # Task completed successfully


@dataclass
class VerifyAttempt:
    """Record of a single verification attempt."""

    run_id: str
    passed: bool
    failure_summary: str = ""
    attempt_number: int = 0


@dataclass
class DebugLoopState:
    """State of the debug loop."""

    consecutive_failures: int = 0
    total_verify_loops: int = 0
    replan_count: int = 0
    attempts: list[VerifyAttempt] = field(default_factory=list)
    current_hypothesis: str = ""
    strategy_history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary.

        Returns:
            Dictionary representation of the loop state.
        """
        return {
            "consecutive_failures": self.consecutive_failures,
            "total_verify_loops": self.total_verify_loops,
            "replan_count": self.replan_count,
            "attempts": [
                {
                    "run_id": a.run_id,
                    "passed": a.passed,
                    "failure_summary": a.failure_summary,
                    "attempt_number": a.attempt_number,
                }
                for a in self.attempts
            ],
            "current_hypothesis": self.current_hypothesis,
            "strategy_history": self.strategy_history,
        }

    def get_all_run_ids(self) -> list[str]:
        """Get all run IDs from all attempts.

        Returns:
            List of run IDs.
        """
        return [a.run_id for a in self.attempts]


class DebugLoop:
    """Manages the debug loop with fix-forward strategy.

    The debug loop handles:
    - Consecutive failure counting (resets on REPLAN or success)
    - Total verify loop counting (only resets on success)
    - REPLAN triggering at 3 consecutive failures
    - Hard stop at 12 total verify loops
    - Recording of all verification attempts
    """

    def __init__(self) -> None:
        """Initialize the debug loop."""
        self._state = DebugLoopState()

    @property
    def state(self) -> DebugLoopState:
        """Get the current loop state."""
        return self._state

    @property
    def consecutive_failures(self) -> int:
        """Get the current consecutive failure count."""
        return self._state.consecutive_failures

    @property
    def total_verify_loops(self) -> int:
        """Get the total verification loop count."""
        return self._state.total_verify_loops

    @property
    def replan_count(self) -> int:
        """Get the number of REPLANs that have occurred."""
        return self._state.replan_count

    def reset(self) -> None:
        """Reset the debug loop for a new task."""
        self._state = DebugLoopState()

    def record_success(self, run_id: str) -> LoopAction:
        """Record a successful verification.

        Args:
            run_id: The run_id of the successful verification.

        Returns:
            LoopAction.SUCCESS
        """
        self._state.total_verify_loops += 1

        attempt = VerifyAttempt(
            run_id=run_id,
            passed=True,
            attempt_number=self._state.total_verify_loops,
        )
        self._state.attempts.append(attempt)

        # Reset all counters on success
        self._state.consecutive_failures = 0

        return LoopAction.SUCCESS

    def record_failure(
        self,
        run_id: str,
        failure_summary: str = "",
    ) -> LoopAction:
        """Record a failed verification.

        Args:
            run_id: The run_id of the failed verification.
            failure_summary: Summary of what failed.

        Returns:
            The action to take (CONTINUE, REPLAN, or HARD_STOP).
        """
        self._state.total_verify_loops += 1
        self._state.consecutive_failures += 1

        attempt = VerifyAttempt(
            run_id=run_id,
            passed=False,
            failure_summary=failure_summary,
            attempt_number=self._state.total_verify_loops,
        )
        self._state.attempts.append(attempt)

        # Determine action based on thresholds
        # Hard stop takes precedence over REPLAN
        if self._state.total_verify_loops >= TOTAL_VERIFY_LOOP_THRESHOLD:
            return LoopAction.HARD_STOP

        if self._state.consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD:
            return LoopAction.REPLAN

        return LoopAction.CONTINUE

    def trigger_replan(self, new_strategy: str) -> None:
        """Trigger a REPLAN event.

        Resets consecutive failure counter but keeps total verify loops.

        Args:
            new_strategy: Description of the new strategy.
        """
        self._state.consecutive_failures = 0
        self._state.replan_count += 1
        self._state.strategy_history.append(new_strategy)
        self._state.current_hypothesis = new_strategy

    def set_hypothesis(self, hypothesis: str) -> None:
        """Set the current hypothesis being tested.

        Args:
            hypothesis: Description of the current hypothesis.
        """
        self._state.current_hypothesis = hypothesis

    def should_requery_scouts(self, failure_pattern: str) -> bool:
        """Determine if Scouts should be re-queried during REPLAN.

        Args:
            failure_pattern: Pattern of failures observed.

        Returns:
            True if Scouts should be re-queried.
        """
        failure_lower = failure_pattern.lower()

        # Re-query Scout A if failures suggest wrong files or missed dependencies
        if any(
            keyword in failure_lower
            for keyword in [
                "import",
                "module",
                "dependency",
                "not found",
                "undefined",
                "missing",
            ]
        ):
            return True

        # Re-query Scout B if failures suggest build/test misconfiguration
        return any(
            keyword in failure_lower
            for keyword in ["build", "compile", "test setup", "environment", "timeout"]
        )

    def get_failure_summary(self) -> str:
        """Get a summary of all failures.

        Returns:
            Markdown formatted failure summary.
        """
        if not self._state.attempts:
            return "No verification attempts recorded."

        failed = [a for a in self._state.attempts if not a.passed]
        if not failed:
            return "All attempts passed."

        lines = [f"## Failure Summary ({len(failed)} failures)\n"]

        for attempt in failed:
            lines.append(f"### Attempt {attempt.attempt_number}")
            lines.append(f"- Run ID: {attempt.run_id}")
            if attempt.failure_summary:
                lines.append(f"- Summary: {attempt.failure_summary}")
            lines.append("")

        return "\n".join(lines)

    def get_attempt_count_display(self) -> str:
        """Get a display string for current attempt count.

        Returns:
            String like "Attempt 3/12..."
        """
        return f"Attempt {self._state.total_verify_loops}/{TOTAL_VERIFY_LOOP_THRESHOLD}"


def create_debug_loop() -> DebugLoop:
    """Create a new debug loop instance.

    Returns:
        Fresh DebugLoop instance.
    """
    return DebugLoop()
