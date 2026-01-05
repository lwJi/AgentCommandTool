"""Stuck report loading for future retry.

When a new task resumes from stuck state, this module provides access to:
- Stuck report with hypotheses
- Artifact references (run IDs) for prior run logs
"""

import re
from dataclasses import dataclass
from pathlib import Path

from act.artifacts.context_dir import get_agent_dir
from act.editor.outputs import (
    STUCK_REPORT_FILENAME,
    has_stuck_report,
)


class RetryContextError(Exception):
    """Error loading retry context from stuck report."""

    pass


@dataclass
class RetryContext:
    """Context for retrying a stuck task.

    Contains information from the stuck report that can inform
    a new attempt at the task.

    Attributes:
        task_description: Original task description
        constraints: Task constraints that must be preserved
        hypotheses: List of (title, description, investigation) tuples
        artifact_run_ids: List of run IDs from previous attempts
        files_modified: Files that were modified in previous attempts
        is_infra_error: Whether the stuck state was due to infrastructure
        infra_error_source: Source of infrastructure error (if applicable)
    """

    task_description: str
    constraints: list[str]
    hypotheses: list[tuple[str, str, str]]  # (title, description, investigation)
    artifact_run_ids: list[str]
    files_modified: list[str]
    is_infra_error: bool
    infra_error_source: str | None


def load_retry_context(repo_path: Path) -> RetryContext | None:
    """Load retry context from an existing stuck report.

    Loads the stuck report from agent/stuck_report.md and extracts
    relevant information for informing a new attempt.

    Note: Full context history is NOT loaded - only the stuck report.
    This is intentional per the specs (task-lifecycle.md).

    Args:
        repo_path: Path to the repository root

    Returns:
        RetryContext if a stuck report exists, None otherwise
    """
    agent_dir = get_agent_dir(repo_path)
    if not has_stuck_report(agent_dir):
        return None

    report_path = agent_dir / STUCK_REPORT_FILENAME
    if not report_path.exists():
        return None

    content = report_path.read_text()
    return _parse_stuck_report_markdown(content)


def _parse_stuck_report_markdown(content: str) -> RetryContext:
    """Parse a stuck report markdown file into RetryContext.

    Args:
        content: The markdown content of the stuck report

    Returns:
        RetryContext extracted from the markdown
    """
    # Extract task description (between ## Task and next ##)
    task_match = re.search(r"## Task\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    task_description = task_match.group(1).strip() if task_match else ""

    # Extract constraints
    constraints: list[str] = []
    constraints_match = re.search(
        r"## Constraints\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL
    )
    if constraints_match:
        for line in constraints_match.group(1).strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                constraints.append(line[2:])

    # Extract hypotheses
    hypotheses: list[tuple[str, str, str]] = []
    hypotheses_section = re.search(
        r"## Hypotheses\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if hypotheses_section:
        # Find each ### N. Title block
        hyp_pattern = r"### \d+\. (.+?)\n(.*?)(?=\n### |\n## |\Z)"
        for match in re.finditer(hyp_pattern, hypotheses_section.group(1), re.DOTALL):
            title = match.group(1).strip()
            body = match.group(2).strip()
            # Extract suggested investigation if present
            inv_match = re.search(
                r"\*Suggested investigation:\*\s*(.+)", body, re.DOTALL
            )
            if inv_match:
                investigation = inv_match.group(1).strip()
                description = body[: inv_match.start()].strip()
            else:
                investigation = ""
                description = body
            hypotheses.append((title, description, investigation))

    # Extract run IDs from artifact references
    artifact_run_ids = extract_run_ids_from_report(content)

    # Extract files modified
    files_modified: list[str] = []
    files_match = re.search(
        r"## Files Modified\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL
    )
    if files_match:
        for line in files_match.group(1).strip().split("\n"):
            line = line.strip()
            if line.startswith("- `") and line.endswith("`"):
                files_modified.append(line[3:-1])

    # Check for infrastructure error
    is_infra_error = "## Infrastructure Error" in content
    infra_error_source = None
    if is_infra_error:
        source_match = re.search(r"\*\*Source:\*\*\s*(.+)", content)
        if source_match:
            infra_error_source = source_match.group(1).strip()

    return RetryContext(
        task_description=task_description,
        constraints=constraints,
        hypotheses=hypotheses,
        artifact_run_ids=artifact_run_ids,
        files_modified=files_modified,
        is_infra_error=is_infra_error,
        infra_error_source=infra_error_source,
    )


def get_retry_summary(context: RetryContext) -> str:
    """Generate a summary of the retry context for display.

    Args:
        context: The retry context

    Returns:
        Human-readable summary string
    """
    lines = [
        "Previous attempt information:",
        f"  Task: {context.task_description[:60]}...",
        f"  Previous attempts: {len(context.artifact_run_ids)}",
        f"  Files modified: {len(context.files_modified)}",
    ]

    if context.is_infra_error:
        src = context.infra_error_source
        lines.append(f"  Previous failure: Infrastructure error ({src})")
    else:
        lines.append("  Previous failure: Reached hard stop (12 attempts)")

    if context.hypotheses:
        lines.append("")
        lines.append("Hypotheses from previous attempt:")
        for i, (title, desc, _) in enumerate(context.hypotheses[:3], 1):
            lines.append(f"  {i}. {title}: {desc[:60]}...")

    return "\n".join(lines)


def should_show_retry_context(repo_path: Path) -> bool:
    """Check if a stuck report exists that should be shown to the user.

    Args:
        repo_path: Path to the repository root

    Returns:
        True if a stuck report exists
    """
    agent_dir = get_agent_dir(repo_path)
    return has_stuck_report(agent_dir)


def clear_retry_context(repo_path: Path) -> bool:
    """Clear the stuck report after a successful retry.

    This removes the stuck report so it won't be loaded on future tasks.
    Should be called when a task succeeds after a retry.

    Args:
        repo_path: Path to the repository root

    Returns:
        True if a report was cleared, False if none existed
    """
    agent_dir = get_agent_dir(repo_path)
    report_path = agent_dir / STUCK_REPORT_FILENAME

    if report_path.exists():
        report_path.unlink()
        return True
    return False


def extract_run_ids_from_report(report_content: str) -> list[str]:
    """Extract run IDs from stuck report content.

    Useful when parsing raw report text without full deserialization.

    Args:
        report_content: Raw markdown content of stuck report

    Returns:
        List of run IDs found in the report
    """
    # Pattern matches run_YYYYMMDD_HHMMSS_xxxxxx format
    pattern = r"run_\d{8}_\d{6}_[a-z0-9]{6}"
    return list(set(re.findall(pattern, report_content)))


def get_artifact_paths_for_retry(
    artifact_dir: Path,
    run_ids: list[str],
) -> dict[str, Path]:
    """Get paths to artifact directories for previous runs.

    Args:
        artifact_dir: Root artifact directory
        run_ids: List of run IDs to locate

    Returns:
        Dict mapping run_id to artifact directory path
    """
    runs_dir = artifact_dir / "runs"
    paths: dict[str, Path] = {}

    for run_id in run_ids:
        run_path = runs_dir / run_id
        if run_path.exists():
            paths[run_id] = run_path

    return paths
