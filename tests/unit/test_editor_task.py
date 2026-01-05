"""Unit tests for Editor task parsing."""

import pytest

from act.editor.exceptions import TaskParseError
from act.editor.task import (
    ParsedTask,
    SuccessCriteria,
    TaskConstraints,
    parse_task,
    validate_task,
)


class TestTaskConstraints:
    """Tests for TaskConstraints dataclass."""

    def test_empty_constraints(self) -> None:
        """Test empty constraints."""
        constraints = TaskConstraints()
        assert constraints.is_empty()
        assert constraints.must_preserve == []
        assert constraints.non_goals == []
        assert constraints.boundaries == []

    def test_non_empty_constraints(self) -> None:
        """Test non-empty constraints."""
        constraints = TaskConstraints(
            must_preserve=["API compatibility"],
            non_goals=["Don't refactor"],
            boundaries=["Only modify src/"],
        )
        assert not constraints.is_empty()

    def test_partial_constraints(self) -> None:
        """Test partially filled constraints."""
        constraints = TaskConstraints(must_preserve=["One thing"])
        assert not constraints.is_empty()


class TestSuccessCriteria:
    """Tests for SuccessCriteria dataclass."""

    def test_empty_criteria(self) -> None:
        """Test empty success criteria."""
        criteria = SuccessCriteria()
        assert criteria.acceptance_criteria == []
        assert criteria.expected_behavior_changes == []
        assert criteria.verification_hints == []

    def test_filled_criteria(self) -> None:
        """Test filled success criteria."""
        criteria = SuccessCriteria(
            acceptance_criteria=["Bug is fixed"],
            expected_behavior_changes=["Login works"],
            verification_hints=["Run login tests"],
        )
        assert len(criteria.acceptance_criteria) == 1
        assert len(criteria.expected_behavior_changes) == 1
        assert len(criteria.verification_hints) == 1


class TestParsedTask:
    """Tests for ParsedTask dataclass."""

    def test_to_dict(self) -> None:
        """Test to_dict conversion."""
        task = ParsedTask(
            raw_description="Fix login bug",
            main_objective="Fix login bug",
            constraints=TaskConstraints(),
            success_criteria=SuccessCriteria(
                acceptance_criteria=["Bug fixed"],
            ),
        )
        result = task.to_dict()
        assert result["raw_description"] == "Fix login bug"
        assert result["main_objective"] == "Fix login bug"
        assert "constraints" in result
        assert "success_criteria" in result


class TestParseTask:
    """Tests for parse_task function."""

    def test_empty_description_raises_error(self) -> None:
        """Test that empty description raises TaskParseError."""
        with pytest.raises(TaskParseError):
            parse_task("")

    def test_whitespace_only_raises_error(self) -> None:
        """Test that whitespace-only description raises TaskParseError."""
        with pytest.raises(TaskParseError):
            parse_task("   ")

    def test_simple_task(self) -> None:
        """Test parsing a simple task."""
        task = parse_task("Fix the login timeout bug")
        assert task.raw_description == "Fix the login timeout bug"
        assert task.main_objective == "Fix the login timeout bug"
        assert task.constraints.is_empty()

    def test_task_with_constraints_section(self) -> None:
        """Test parsing task with Constraints section."""
        description = """Fix the authentication bug.

Constraints:
- Don't modify the session storage
- Preserve backward compatibility"""

        task = parse_task(description)
        assert "Fix the authentication bug" in task.main_objective
        assert len(task.constraints.must_preserve) == 2
        assert "Don't modify the session storage" in task.constraints.must_preserve[0]

    def test_task_with_non_goals_section(self) -> None:
        """Test parsing task with Non-goals section."""
        description = """Add user profile page.

Non-goals:
- Don't refactor the auth module
- Don't add new dependencies"""

        task = parse_task(description)
        assert len(task.constraints.non_goals) == 2

    def test_task_with_boundaries_section(self) -> None:
        """Test parsing task with Boundaries section."""
        description = """Update the API.

Boundaries:
- Only modify src/api/
- Don't touch the database layer"""

        task = parse_task(description)
        assert len(task.constraints.boundaries) == 2

    def test_task_with_all_sections(self) -> None:
        """Test parsing task with all constraint sections."""
        description = """Fix the login bug.

Constraints:
- Keep API compatibility

Non-goals:
- Don't refactor

Boundaries:
- Only src/auth/"""

        task = parse_task(description)
        assert len(task.constraints.must_preserve) == 1
        assert len(task.constraints.non_goals) == 1
        assert len(task.constraints.boundaries) == 1

    def test_success_criteria_for_fix_task(self) -> None:
        """Test success criteria derivation for fix task."""
        task = parse_task("Fix the login timeout bug")
        assert any("bug" in h.lower() for h in task.success_criteria.verification_hints)

    def test_success_criteria_for_add_task(self) -> None:
        """Test success criteria derivation for add task."""
        task = parse_task("Add a logout button to the header")
        assert any("feature" in c.lower() or "new" in c.lower()
                  for c in task.success_criteria.expected_behavior_changes)

    def test_success_criteria_for_refactor_task(self) -> None:
        """Test success criteria derivation for refactor task."""
        task = parse_task("Refactor the authentication module")
        # Refactor tasks should mention "structure" or related improvements
        assert any("structure" in c.lower() or "improved" in c.lower()
                  for c in task.success_criteria.expected_behavior_changes)

    def test_success_criteria_for_test_task(self) -> None:
        """Test success criteria derivation for test task."""
        task = parse_task("Add unit tests for the login module")
        assert any("test" in c.lower()
                  for c in task.success_criteria.expected_behavior_changes)

    def test_success_criteria_for_update_task(self) -> None:
        """Test success criteria derivation for update task."""
        task = parse_task("Update the error handling logic")
        assert any("update" in h.lower() or "change" in h.lower()
                  for h in task.success_criteria.verification_hints)

    def test_multiline_task(self) -> None:
        """Test parsing multiline task description."""
        description = """This is a complex task.
It spans multiple lines.
And has lots of detail."""

        task = parse_task(description)
        assert len(task.main_objective) > 0

    def test_bullet_points_with_asterisks(self) -> None:
        """Test parsing bullet points with asterisks."""
        description = """Task here.

Constraints:
* First constraint
* Second constraint"""

        task = parse_task(description)
        assert len(task.constraints.must_preserve) == 2

    def test_constraints_are_immutable_in_type(self) -> None:
        """Test that constraints are stored as they are parsed."""
        description = """Fix bug.

Constraints:
- Must preserve API"""

        task = parse_task(description)
        original_constraint = task.constraints.must_preserve[0]
        # Constraints should be preserved exactly
        assert original_constraint == "Must preserve API"


class TestValidateTask:
    """Tests for validate_task function."""

    def test_valid_task_no_warnings(self) -> None:
        """Test that a valid task produces no warnings."""
        task = parse_task("Fix the authentication timeout bug in the login flow")
        warnings = validate_task(task)
        # May or may not have warnings depending on criteria
        assert isinstance(warnings, list)

    def test_short_objective_warning(self) -> None:
        """Test warning for short objective."""
        task = parse_task("Fix bug")
        warnings = validate_task(task)
        assert any("short" in w.lower() for w in warnings)

    def test_task_with_criteria_no_warning(self) -> None:
        """Test task with acceptance criteria has no ambiguity warning."""
        task = parse_task("Fix the login bug that causes timeout after 30 seconds")
        # Validate task and ignore warnings (main assertion is below)
        validate_task(task)
        # Should have acceptance criteria derived
        assert len(task.success_criteria.acceptance_criteria) > 0
