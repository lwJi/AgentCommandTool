"""Unit tests for Editor outputs."""

from pathlib import Path

from act.editor.debug_loop import DebugLoopState, VerifyAttempt
from act.editor.outputs import (
    STUCK_REPORT_FILENAME,
    StuckReport,
    StuckReportHypothesis,
    SuccessSummary,
    generate_stuck_report,
    generate_stuck_report_hypotheses,
    generate_success_summary,
    has_stuck_report,
    read_stuck_report,
    write_stuck_report,
)
from act.editor.task import ParsedTask, SuccessCriteria, TaskConstraints


class TestSuccessSummary:
    """Tests for SuccessSummary dataclass."""

    def test_basic_summary(self) -> None:
        """Test basic summary creation."""
        summary = SuccessSummary(
            task_description="Fix login bug",
            what_changed="Fixed timeout handling",
            why="Login was timing out",
            how_verified="Tests pass",
            run_id="run_001",
        )
        assert summary.task_description == "Fix login bug"
        assert summary.run_id == "run_001"

    def test_to_markdown(self) -> None:
        """Test markdown generation."""
        summary = SuccessSummary(
            task_description="Add logout button",
            what_changed="Added button to header",
            why="Users need to log out",
            how_verified="Verification passed",
            run_id="run_002",
            files_modified=["src/header.tsx"],
        )
        md = summary.to_markdown()

        assert "# Task Completion Summary" in md
        assert "Add logout button" in md
        assert "run_002" in md
        assert "src/header.tsx" in md

    def test_markdown_includes_all_sections(self) -> None:
        """Test markdown includes all required sections."""
        summary = SuccessSummary(
            task_description="Task",
            what_changed="Changes",
            why="Reason",
            how_verified="Verified",
            run_id="run_003",
        )
        md = summary.to_markdown()

        assert "## Task" in md
        assert "## What Changed" in md
        assert "## Why" in md
        assert "## How Verified" in md


class TestStuckReportHypothesis:
    """Tests for StuckReportHypothesis dataclass."""

    def test_basic_hypothesis(self) -> None:
        """Test basic hypothesis creation."""
        hypothesis = StuckReportHypothesis(
            title="Import Issue",
            description="The import paths may be wrong",
        )
        assert hypothesis.title == "Import Issue"
        assert hypothesis.suggested_investigation == ""

    def test_hypothesis_with_investigation(self) -> None:
        """Test hypothesis with suggested investigation."""
        hypothesis = StuckReportHypothesis(
            title="Type Error",
            description="Types don't match",
            suggested_investigation="Check interface definitions",
        )
        assert hypothesis.suggested_investigation == "Check interface definitions"


class TestStuckReport:
    """Tests for StuckReport dataclass."""

    def test_basic_report(self) -> None:
        """Test basic stuck report."""
        report = StuckReport(
            task_description="Fix bug",
            constraints=[],
            status="Hard stop after 12 attempts",
            hypotheses=[],
            verification_history=[],
            artifact_references=[],
        )
        assert report.task_description == "Fix bug"
        assert report.is_infra_error is False

    def test_to_markdown_hard_stop(self) -> None:
        """Test markdown for hard stop report."""
        report = StuckReport(
            task_description="Add feature",
            constraints=["Don't break API"],
            status="Hard stop after 12 verification attempts.",
            hypotheses=[
                StuckReportHypothesis(
                    title="Wrong approach",
                    description="May need different strategy",
                ),
            ],
            verification_history=[
                {"run_id": "run_001", "passed": False, "failure_summary": "Error"},
            ],
            artifact_references=["run_001"],
            files_modified=["src/main.py"],
        )
        md = report.to_markdown()

        assert "# Stuck Report" in md
        assert "Add feature" in md
        assert "Don't break API" in md
        assert "Wrong approach" in md
        assert "run_001" in md or "001" in md
        assert "src/main.py" in md

    def test_to_markdown_infra_error(self) -> None:
        """Test markdown for infrastructure error report."""
        report = StuckReport(
            task_description="Task",
            constraints=[],
            status="Infrastructure failure",
            hypotheses=[],
            verification_history=[],
            artifact_references=[],
            is_infra_error=True,
            infra_error_source="verifier",
            infra_error_message="Docker unavailable",
        )
        md = report.to_markdown()

        assert "Infrastructure Error" in md
        assert "verifier" in md
        assert "Docker unavailable" in md

    def test_verification_history_table(self) -> None:
        """Test verification history table in markdown."""
        report = StuckReport(
            task_description="Task",
            constraints=[],
            status="Stuck",
            hypotheses=[],
            verification_history=[
                {"run_id": "run_001", "passed": False, "failure_summary": "Error 1"},
                {"run_id": "run_002", "passed": False, "failure_summary": "Error 2"},
                {"run_id": "run_003", "passed": True, "failure_summary": ""},
            ],
            artifact_references=["run_001", "run_002", "run_003"],
        )
        md = report.to_markdown()

        assert "Verification History" in md
        assert "| Run | Status | Primary Failure |" in md
        assert "FAIL" in md
        assert "PASS" in md


class TestGenerateSuccessSummary:
    """Tests for generate_success_summary function."""

    def test_generates_summary(self) -> None:
        """Test summary generation from task."""
        task = ParsedTask(
            raw_description="Fix login bug in auth module",
            main_objective="Fix login bug",
            constraints=TaskConstraints(),
            success_criteria=SuccessCriteria(),
        )
        summary = generate_success_summary(
            task=task,
            what_changed="Fixed timeout handling",
            run_id="run_001",
            files_modified=["src/auth.py"],
        )

        assert summary.task_description == "Fix login bug in auth module"
        assert summary.run_id == "run_001"
        assert "src/auth.py" in summary.files_modified


class TestGenerateStuckReportHypotheses:
    """Tests for generate_stuck_report_hypotheses function."""

    def test_import_error_hypothesis(self) -> None:
        """Test hypothesis generation for import errors."""
        state = DebugLoopState()
        state.attempts = [
            VerifyAttempt(
                run_id="run_001",
                passed=False,
                failure_summary="ImportError: module not found",
                attempt_number=1,
            ),
        ]
        hypotheses = generate_stuck_report_hypotheses(state, ["src/main.py"])

        assert any("import" in h.title.lower() for h in hypotheses)

    def test_type_error_hypothesis(self) -> None:
        """Test hypothesis generation for type errors."""
        state = DebugLoopState()
        state.attempts = [
            VerifyAttempt(
                run_id="run_001",
                passed=False,
                failure_summary="TypeError: expected string",
                attempt_number=1,
            ),
        ]
        hypotheses = generate_stuck_report_hypotheses(state, ["src/main.py"])

        assert any("type" in h.title.lower() for h in hypotheses)

    def test_timeout_hypothesis(self) -> None:
        """Test hypothesis generation for timeout errors."""
        state = DebugLoopState()
        state.attempts = [
            VerifyAttempt(
                run_id="run_001",
                passed=False,
                failure_summary="Test timeout after 30s",
                attempt_number=1,
            ),
        ]
        hypotheses = generate_stuck_report_hypotheses(state, ["src/main.py"])

        assert any("timeout" in h.title.lower() for h in hypotheses)

    def test_multiple_replans_hypothesis(self) -> None:
        """Test hypothesis for multiple REPLANs."""
        state = DebugLoopState()
        state.replan_count = 2
        state.attempts = [
            VerifyAttempt(run_id="run_001", passed=False, attempt_number=1),
        ]
        hypotheses = generate_stuck_report_hypotheses(state, ["src/main.py"])

        assert any("approach" in h.title.lower() or "strategy" in h.description.lower()
                  for h in hypotheses)

    def test_many_files_hypothesis(self) -> None:
        """Test hypothesis for too many modified files."""
        state = DebugLoopState()
        state.attempts = [
            VerifyAttempt(run_id="run_001", passed=False, attempt_number=1),
        ]
        many_files = [f"src/file{i}.py" for i in range(10)]
        hypotheses = generate_stuck_report_hypotheses(state, many_files)

        assert any("scope" in h.title.lower() or "large" in h.description.lower()
                  for h in hypotheses)

    def test_default_hypothesis(self) -> None:
        """Test default hypothesis when no patterns match."""
        state = DebugLoopState()
        state.attempts = [
            VerifyAttempt(
                run_id="run_001",
                passed=False,
                failure_summary="Unknown error xyz",
                attempt_number=1,
            ),
        ]
        hypotheses = generate_stuck_report_hypotheses(state, ["src/main.py"])

        # Should have at least one hypothesis
        assert len(hypotheses) >= 1


class TestGenerateStuckReport:
    """Tests for generate_stuck_report function."""

    def test_generates_report(self) -> None:
        """Test stuck report generation."""
        task = ParsedTask(
            raw_description="Fix bug",
            main_objective="Fix bug",
            constraints=TaskConstraints(must_preserve=["API compatibility"]),
            success_criteria=SuccessCriteria(),
        )
        state = DebugLoopState()
        state.attempts = [
            VerifyAttempt(run_id="run_001", passed=False, attempt_number=1),
        ]
        report = generate_stuck_report(
            task=task,
            loop_state=state,
            files_modified=["src/main.py"],
        )

        assert report.task_description == "Fix bug"
        assert "API compatibility" in report.constraints
        assert len(report.hypotheses) > 0

    def test_infra_error_report(self) -> None:
        """Test stuck report for infrastructure error."""
        task = ParsedTask(
            raw_description="Task",
            main_objective="Task",
            constraints=TaskConstraints(),
            success_criteria=SuccessCriteria(),
        )
        report = generate_stuck_report(
            task=task,
            loop_state=DebugLoopState(),
            files_modified=[],
            is_infra_error=True,
            infra_error_source="scout_a",
            infra_error_message="API timeout",
        )

        assert report.is_infra_error is True
        assert report.infra_error_source == "scout_a"


class TestStuckReportFileOperations:
    """Tests for stuck report file operations."""

    def test_write_stuck_report(self, tmp_path: Path) -> None:
        """Test writing stuck report."""
        agent_dir = tmp_path / "agent"
        report = StuckReport(
            task_description="Task",
            constraints=[],
            status="Stuck",
            hypotheses=[],
            verification_history=[],
            artifact_references=[],
        )
        path = write_stuck_report(agent_dir, report)

        assert path.exists()
        assert path.name == STUCK_REPORT_FILENAME
        assert "# Stuck Report" in path.read_text()

    def test_has_stuck_report_true(self, tmp_path: Path) -> None:
        """Test has_stuck_report returns True when exists."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / STUCK_REPORT_FILENAME).write_text("# Report")

        assert has_stuck_report(agent_dir) is True

    def test_has_stuck_report_false(self, tmp_path: Path) -> None:
        """Test has_stuck_report returns False when missing."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        assert has_stuck_report(agent_dir) is False

    def test_read_stuck_report(self, tmp_path: Path) -> None:
        """Test reading stuck report."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        content = "# Stuck Report\n\nSome content"
        (agent_dir / STUCK_REPORT_FILENAME).write_text(content)

        result = read_stuck_report(agent_dir)
        assert result == content

    def test_read_stuck_report_missing(self, tmp_path: Path) -> None:
        """Test reading non-existent stuck report."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        result = read_stuck_report(agent_dir)
        assert result is None

    def test_write_overwrites_existing(self, tmp_path: Path) -> None:
        """Test that write_stuck_report overwrites existing report."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / STUCK_REPORT_FILENAME).write_text("Old content")

        report = StuckReport(
            task_description="New task",
            constraints=[],
            status="New status",
            hypotheses=[],
            verification_history=[],
            artifact_references=[],
        )
        write_stuck_report(agent_dir, report)

        content = read_stuck_report(agent_dir)
        assert "New task" in content
        assert "Old content" not in content
