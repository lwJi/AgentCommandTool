"""Output generators for Editor.

Generates success summaries and stuck reports based on task outcomes.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from act.editor.debug_loop import DebugLoopState
from act.editor.task import ParsedTask

STUCK_REPORT_FILENAME = "stuck_report.md"


@dataclass
class SuccessSummary:
    """Summary generated on successful task completion."""

    task_description: str
    what_changed: str
    why: str
    how_verified: str
    run_id: str
    files_modified: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_markdown(self) -> str:
        """Convert to markdown format.

        Returns:
            Markdown formatted summary.
        """
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        lines = [
            "# Task Completion Summary",
            "",
            f"**Completed:** {self.timestamp}",
            "",
            "## Task",
            self.task_description,
            "",
            "## What Changed",
            self.what_changed,
            "",
            "## Why",
            self.why,
            "",
            "## How Verified",
            self.how_verified,
            "",
            f"**Verification Run ID:** `{self.run_id}`",
            "",
        ]

        if self.files_modified:
            lines.append("## Files Modified")
            for f in self.files_modified:
                lines.append(f"- `{f}`")
            lines.append("")

        return "\n".join(lines)


@dataclass
class StuckReportHypothesis:
    """A hypothesis about why the task is stuck."""

    title: str
    description: str
    suggested_investigation: str = ""


@dataclass
class StuckReport:
    """Report generated when hard stop or infrastructure failure occurs."""

    task_description: str
    constraints: list[str]
    status: str
    hypotheses: list[StuckReportHypothesis]
    verification_history: list[dict[str, Any]]
    artifact_references: list[str]
    files_modified: list[str] = field(default_factory=list)
    is_infra_error: bool = False
    infra_error_source: str = ""
    infra_error_message: str = ""
    timestamp: str = ""

    def to_markdown(self) -> str:
        """Convert to markdown format.

        Returns:
            Markdown formatted stuck report.
        """
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        lines = [
            "# Stuck Report",
            "",
            f"**Generated:** {self.timestamp}",
            "",
            "## Task",
            self.task_description,
            "",
        ]

        if self.constraints:
            lines.append("## Constraints")
            for constraint in self.constraints:
                lines.append(f"- {constraint}")
            lines.append("")

        lines.extend(
            [
                "## Status",
                self.status,
                "",
            ]
        )

        if self.is_infra_error:
            lines.extend(
                [
                    "## Infrastructure Error",
                    f"**Source:** {self.infra_error_source}",
                    f"**Error:** {self.infra_error_message}",
                    "",
                    "This is an infrastructure issue, not a code problem.",
                    "Possible resolutions:",
                    "- Check if Docker is running (for Verifier errors)",
                    "- Check API keys and network connectivity (for Scout errors)",
                    "- Review system resources (memory, disk space)",
                    "",
                ]
            )

        if self.hypotheses:
            lines.append("## Hypotheses")
            lines.append("")
            for i, h in enumerate(self.hypotheses, 1):
                lines.append(f"### {i}. {h.title}")
                lines.append(h.description)
                if h.suggested_investigation:
                    investigation = h.suggested_investigation
                    lines.append(f"\n*Suggested investigation:* {investigation}")
                lines.append("")

        if self.verification_history:
            lines.append("## Verification History")
            lines.append("")
            lines.append("| Run | Status | Primary Failure |")
            lines.append("|-----|--------|-----------------|")
            for record in self.verification_history:
                run_id = record.get("run_id", "unknown")
                # Shorten run_id for display
                short_id = run_id.split("_")[-1] if "_" in run_id else run_id[:8]
                status = "PASS" if record.get("passed", False) else "FAIL"
                failure = record.get("failure_summary", "")[:40] or "-"
                lines.append(f"| {short_id} | {status} | {failure} |")
            lines.append("")

        if self.artifact_references:
            lines.append("## Artifact References")
            lines.append("")
            for ref in self.artifact_references:
                lines.append(f"- `{ref}`")
            lines.append("")

        if self.files_modified:
            lines.append("## Files Modified")
            lines.append("")
            for f in self.files_modified:
                lines.append(f"- `{f}`")
            lines.append("")

        return "\n".join(lines)


def generate_success_summary(
    task: ParsedTask,
    what_changed: str,
    run_id: str,
    files_modified: list[str],
) -> SuccessSummary:
    """Generate a success summary for a completed task.

    Args:
        task: The parsed task that was completed.
        what_changed: Description of what was changed.
        run_id: The run_id of the passing verification.
        files_modified: List of files that were modified.

    Returns:
        SuccessSummary instance.
    """
    return SuccessSummary(
        task_description=task.raw_description,
        what_changed=what_changed,
        why=task.main_objective,
        how_verified=f"Verification passed with run_id: {run_id}",
        run_id=run_id,
        files_modified=files_modified,
    )


def generate_stuck_report_hypotheses(
    loop_state: DebugLoopState,
    files_modified: list[str],
) -> list[StuckReportHypothesis]:
    """Generate hypotheses for a stuck report.

    Editor generates these autonomously without consulting Scouts.

    Args:
        loop_state: Current debug loop state.
        files_modified: Files that were modified during attempts.

    Returns:
        List of hypotheses.
    """
    hypotheses = []

    # Analyze failure patterns
    failures = [a for a in loop_state.attempts if not a.passed]
    failure_summaries = [
        a.failure_summary.lower() for a in failures if a.failure_summary
    ]

    # Check for common patterns
    if any("import" in s or "module" in s for s in failure_summaries):
        hypotheses.append(
            StuckReportHypothesis(
                title="Import or Module Resolution Issue",
                description=(
                    "Multiple failures mention import or module errors. "
                    "The changes may have broken import paths or created "
                    "circular dependencies."
                ),
                suggested_investigation=(
                    "Review the import statements in modified files and check "
                    "for circular import issues."
                ),
            )
        )

    if any("type" in s or "typescript" in s for s in failure_summaries):
        hypotheses.append(
            StuckReportHypothesis(
                title="Type System Incompatibility",
                description=(
                    "Type errors persist across attempts. The changes may "
                    "require updating type definitions or there's a fundamental "
                    "type mismatch in the approach."
                ),
                suggested_investigation=(
                    "Check if the modified code follows the existing type "
                    "conventions and update type definitions as needed."
                ),
            )
        )

    if any("timeout" in s for s in failure_summaries):
        hypotheses.append(
            StuckReportHypothesis(
                title="Test Timeout Issue",
                description=(
                    "Tests are timing out consistently. This could indicate "
                    "an infinite loop, blocking operation, or the test "
                    "infrastructure needs adjustment."
                ),
                suggested_investigation=(
                    "Review any loops or async operations in the modified code. "
                    "Consider if the test timeout values need to be increased."
                ),
            )
        )

    if any("permission" in s or "access" in s for s in failure_summaries):
        hypotheses.append(
            StuckReportHypothesis(
                title="Permission or Access Issue",
                description=(
                    "Failures mention permission or access problems. "
                    "The code may be trying to access resources it shouldn't "
                    "or environment permissions are misconfigured."
                ),
                suggested_investigation=(
                    "Verify the code doesn't access files outside the expected "
                    "directories and check test environment permissions."
                ),
            )
        )

    # Strategy-based hypothesis if multiple REPLANs occurred
    if loop_state.replan_count >= 2:
        hypotheses.append(
            StuckReportHypothesis(
                title="Fundamental Approach May Be Wrong",
                description=(
                    f"After {loop_state.replan_count} strategy changes, the task "
                    f"still fails. The problem may require a fundamentally "
                    f"different approach or additional context."
                ),
                suggested_investigation=(
                    "Consider if there are undocumented constraints or if "
                    "the task description needs clarification."
                ),
            )
        )

    # File-based hypothesis
    if len(files_modified) > 5:
        hypotheses.append(
            StuckReportHypothesis(
                title="Change Scope Too Large",
                description=(
                    f"Modified {len(files_modified)} files which may be causing "
                    f"cascading issues. Consider breaking the task into smaller "
                    f"incremental changes."
                ),
                suggested_investigation=(
                    "Try implementing changes file by file with verification "
                    "after each change."
                ),
            )
        )

    # Default hypothesis if no patterns matched
    if not hypotheses:
        hypotheses.append(
            StuckReportHypothesis(
                title="Undiagnosed Issue",
                description=(
                    "The failure pattern doesn't match common categories. "
                    "Manual investigation of the verification logs is recommended."
                ),
                suggested_investigation=(
                    "Review the combined.log files in the artifact directories "
                    "for detailed error information."
                ),
            )
        )

    return hypotheses


def generate_stuck_report(
    task: ParsedTask,
    loop_state: DebugLoopState,
    files_modified: list[str],
    is_infra_error: bool = False,
    infra_error_source: str = "",
    infra_error_message: str = "",
) -> StuckReport:
    """Generate a stuck report for hard stop or infrastructure failure.

    Args:
        task: The parsed task.
        loop_state: Current debug loop state.
        files_modified: Files that were modified.
        is_infra_error: Whether this is an infrastructure error.
        infra_error_source: Source of infrastructure error.
        infra_error_message: Infrastructure error message.

    Returns:
        StuckReport instance.
    """
    # Determine status message
    if is_infra_error:
        status = f"Infrastructure failure from {infra_error_source}"
    else:
        status = (
            f"Hard stop reached after {loop_state.total_verify_loops} "
            f"verification attempts."
        )

    # Extract constraints
    constraints = []
    constraints.extend(task.constraints.must_preserve)
    constraints.extend(f"Non-goal: {ng}" for ng in task.constraints.non_goals)
    constraints.extend(f"Boundary: {b}" for b in task.constraints.boundaries)

    # Generate hypotheses
    hypotheses = generate_stuck_report_hypotheses(loop_state, files_modified)

    # Build verification history
    verification_history = [
        {
            "run_id": a.run_id,
            "passed": a.passed,
            "failure_summary": a.failure_summary,
        }
        for a in loop_state.attempts
    ]

    # Build artifact references
    artifact_references = loop_state.get_all_run_ids()

    return StuckReport(
        task_description=task.raw_description,
        constraints=constraints,
        status=status,
        hypotheses=hypotheses,
        verification_history=verification_history,
        artifact_references=artifact_references,
        files_modified=files_modified,
        is_infra_error=is_infra_error,
        infra_error_source=infra_error_source,
        infra_error_message=infra_error_message,
    )


def write_stuck_report(
    agent_dir: Path,
    report: StuckReport,
) -> Path:
    """Write a stuck report to the agent directory.

    Overwrites any existing stuck report.

    Args:
        agent_dir: Path to the agent directory.
        report: The stuck report to write.

    Returns:
        Path to the written report.
    """
    agent_dir.mkdir(exist_ok=True)
    report_path = agent_dir / STUCK_REPORT_FILENAME
    report_path.write_text(report.to_markdown())
    return report_path


def read_stuck_report(agent_dir: Path) -> str | None:
    """Read an existing stuck report from the agent directory.

    Args:
        agent_dir: Path to the agent directory.

    Returns:
        Stuck report content or None if not found.
    """
    report_path = agent_dir / STUCK_REPORT_FILENAME
    if report_path.exists():
        return report_path.read_text()
    return None


def has_stuck_report(agent_dir: Path) -> bool:
    """Check if a stuck report exists.

    Args:
        agent_dir: Path to the agent directory.

    Returns:
        True if a stuck report exists.
    """
    return (agent_dir / STUCK_REPORT_FILENAME).exists()
