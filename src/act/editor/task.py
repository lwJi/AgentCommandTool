"""Task parsing and interpretation.

Handles parsing of free-form natural language task descriptions,
extraction of constraints, non-goals, and boundaries, and derivation
of success criteria.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from act.editor.exceptions import TaskParseError


@dataclass
class TaskConstraints:
    """Constraints extracted from task description.

    These constraints are immutable and cannot be modified by REPLAN.
    """

    must_preserve: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    boundaries: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Check if there are no constraints.

        Returns:
            True if all constraint lists are empty.
        """
        return (
            len(self.must_preserve) == 0
            and len(self.non_goals) == 0
            and len(self.boundaries) == 0
        )


@dataclass
class SuccessCriteria:
    """Derived success criteria for a task."""

    acceptance_criteria: list[str] = field(default_factory=list)
    expected_behavior_changes: list[str] = field(default_factory=list)
    verification_hints: list[str] = field(default_factory=list)


@dataclass
class ParsedTask:
    """A parsed task with extracted components."""

    raw_description: str
    main_objective: str
    constraints: TaskConstraints
    success_criteria: SuccessCriteria

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all task components.
        """
        return {
            "raw_description": self.raw_description,
            "main_objective": self.main_objective,
            "constraints": {
                "must_preserve": self.constraints.must_preserve,
                "non_goals": self.constraints.non_goals,
                "boundaries": self.constraints.boundaries,
            },
            "success_criteria": {
                "acceptance_criteria": self.success_criteria.acceptance_criteria,
                "expected_behavior_changes": (
                    self.success_criteria.expected_behavior_changes
                ),
                "verification_hints": self.success_criteria.verification_hints,
            },
        }


# Section header patterns for constraint extraction
CONSTRAINTS_PATTERN = re.compile(
    r"(?:^|\n)(?:constraints?|must\s+preserve|requirements?):\s*\n?((?:[-*]\s+.+\n?)+)",
    re.IGNORECASE | re.MULTILINE,
)
NON_GOALS_PATTERN = re.compile(
    r"(?:^|\n)(?:non[-\s]?goals?|don'?t|do\s+not|avoid):\s*\n?((?:[-*]\s+.+\n?)+)",
    re.IGNORECASE | re.MULTILINE,
)
BOUNDARIES_PATTERN = re.compile(
    r"(?:^|\n)(?:boundaries?|out\s+of\s+scope|scope\s+limits?):\s*\n?((?:[-*]\s+.+\n?)+)",
    re.IGNORECASE | re.MULTILINE,
)
BULLET_PATTERN = re.compile(r"[-*]\s+(.+)")


def _extract_bullet_items(text: str) -> list[str]:
    """Extract bullet point items from text.

    Args:
        text: Text containing bullet points.

    Returns:
        List of extracted items.
    """
    items = []
    for match in BULLET_PATTERN.finditer(text):
        item = match.group(1).strip()
        if item:
            items.append(item)
    return items


def _extract_constraints(description: str) -> TaskConstraints:
    """Extract constraints from task description.

    Args:
        description: Raw task description.

    Returns:
        Extracted constraints.
    """
    constraints = TaskConstraints()

    # Extract "Constraints:" section
    match = CONSTRAINTS_PATTERN.search(description)
    if match:
        constraints.must_preserve = _extract_bullet_items(match.group(1))

    # Extract "Non-goals:" section
    match = NON_GOALS_PATTERN.search(description)
    if match:
        constraints.non_goals = _extract_bullet_items(match.group(1))

    # Extract "Boundaries:" section
    match = BOUNDARIES_PATTERN.search(description)
    if match:
        constraints.boundaries = _extract_bullet_items(match.group(1))

    return constraints


def _extract_main_objective(description: str) -> str:
    """Extract the main objective from task description.

    The main objective is the task description without constraint sections.

    Args:
        description: Raw task description.

    Returns:
        Main objective text.
    """
    # Remove all constraint sections
    text = description

    for pattern in [CONSTRAINTS_PATTERN, NON_GOALS_PATTERN, BOUNDARIES_PATTERN]:
        text = pattern.sub("", text)

    # Clean up the remaining text
    lines = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line:
            lines.append(line)

    return " ".join(lines)


def _derive_success_criteria(
    main_objective: str,
    constraints: TaskConstraints,
) -> SuccessCriteria:
    """Derive success criteria from task components.

    Args:
        main_objective: The main task objective.
        constraints: Extracted constraints.

    Returns:
        Derived success criteria.
    """
    criteria = SuccessCriteria()

    # Primary acceptance criterion is that the objective is met
    if main_objective:
        criteria.acceptance_criteria.append(main_objective)

    # Add constraints as things that must remain true
    for constraint in constraints.must_preserve:
        criteria.acceptance_criteria.append(f"Preserved: {constraint}")

    # Verification hints based on keywords in objective
    objective_lower = main_objective.lower()

    if "fix" in objective_lower or "bug" in objective_lower:
        criteria.verification_hints.append("Verify the bug is fixed by test")
        criteria.expected_behavior_changes.append("Bug behavior corrected")

    if "add" in objective_lower or "implement" in objective_lower:
        criteria.verification_hints.append("Verify new functionality works as expected")
        criteria.expected_behavior_changes.append("New feature added")

    if "refactor" in objective_lower:
        criteria.verification_hints.append("Verify behavior unchanged after refactor")
        criteria.expected_behavior_changes.append("Code structure improved")

    if "test" in objective_lower:
        criteria.verification_hints.append("Verify tests pass")
        criteria.expected_behavior_changes.append("Test coverage improved")

    if "update" in objective_lower or "change" in objective_lower:
        criteria.verification_hints.append("Verify update applied correctly")
        criteria.expected_behavior_changes.append("Existing behavior modified")

    # Default hint if none matched
    if not criteria.verification_hints:
        criteria.verification_hints.append("Verify all tests pass after changes")

    return criteria


def parse_task(description: str) -> ParsedTask:
    """Parse a free-form task description.

    Args:
        description: Raw task description from user.

    Returns:
        ParsedTask with extracted components.

    Raises:
        TaskParseError: If the task description is empty or invalid.
    """
    if not description or not description.strip():
        raise TaskParseError("Task description cannot be empty")

    description = description.strip()

    # Extract constraints (immutable)
    constraints = _extract_constraints(description)

    # Extract main objective
    main_objective = _extract_main_objective(description)

    if not main_objective:
        # If no main objective remains after extracting constraints,
        # use the original description as the objective
        main_objective = description.split("\n")[0].strip()

    # Derive success criteria
    success_criteria = _derive_success_criteria(main_objective, constraints)

    return ParsedTask(
        raw_description=description,
        main_objective=main_objective,
        constraints=constraints,
        success_criteria=success_criteria,
    )


def validate_task(task: ParsedTask) -> list[str]:
    """Validate a parsed task for potential issues.

    Args:
        task: The parsed task to validate.

    Returns:
        List of warning messages (empty if no issues).
    """
    warnings = []

    if len(task.main_objective) < 10:
        warnings.append("Task objective is very short - may need more detail")

    if not task.success_criteria.acceptance_criteria:
        warnings.append("No acceptance criteria derived - task may be ambiguous")

    return warnings
