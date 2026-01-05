"""Unit tests for task retry module."""

import pytest
from pathlib import Path

from act.task.retry import (
    RetryContext,
    RetryContextError,
    load_retry_context,
    get_retry_summary,
    should_show_retry_context,
    clear_retry_context,
    extract_run_ids_from_report,
    get_artifact_paths_for_retry,
)
from act.editor.outputs import (
    StuckReport,
    StuckReportHypothesis,
    write_stuck_report,
    STUCK_REPORT_FILENAME,
)
from act.artifacts.context_dir import ensure_agent_dir


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    """Create a temporary repo path with agent directory."""
    ensure_agent_dir(tmp_path)
    return tmp_path


@pytest.fixture
def sample_stuck_report() -> StuckReport:
    """Create a sample stuck report."""
    return StuckReport(
        task_description="Fix the authentication bug",
        constraints=["Don't modify session storage", "Keep backward compatibility"],
        status="STUCK",
        hypotheses=[
            StuckReportHypothesis(
                title="Import Error",
                description="Module not found error in auth.py",
                suggested_investigation="Check import paths",
            ),
            StuckReportHypothesis(
                title="Type Mismatch",
                description="Return type doesn't match expected",
                suggested_investigation="Review type annotations",
            ),
        ],
        verification_history=[
            {"attempt": 1, "status": "FAIL", "run_id": "run_20260105_120000_abc123"},
            {"attempt": 2, "status": "FAIL", "run_id": "run_20260105_120100_def456"},
        ],
        artifact_references=[
            "run_20260105_120000_abc123",
            "run_20260105_120100_def456",
        ],
        files_modified=["src/auth.py", "src/utils.py"],
        is_infra_error=False,
        infra_error_source=None,
        infra_error_message=None,
    )


@pytest.fixture
def repo_with_stuck_report(repo_path: Path, sample_stuck_report: StuckReport) -> Path:
    """Create a repo with a stuck report."""
    agent_dir = repo_path / "agent"
    write_stuck_report(agent_dir, sample_stuck_report)
    return repo_path


class TestRetryContext:
    """Tests for RetryContext dataclass."""

    def test_retry_context_creation(self) -> None:
        """Create retry context."""
        ctx = RetryContext(
            task_description="Fix bug",
            constraints=["Keep API stable"],
            hypotheses=[("Error", "Description", "Investigate X")],
            artifact_run_ids=["run_1", "run_2"],
            files_modified=["file1.py"],
            is_infra_error=False,
            infra_error_source=None,
        )

        assert ctx.task_description == "Fix bug"
        assert len(ctx.constraints) == 1
        assert len(ctx.hypotheses) == 1
        assert len(ctx.artifact_run_ids) == 2

    def test_retry_context_infra_error(self) -> None:
        """Create retry context for infra error."""
        ctx = RetryContext(
            task_description="Test",
            constraints=[],
            hypotheses=[],
            artifact_run_ids=[],
            files_modified=[],
            is_infra_error=True,
            infra_error_source="Docker",
        )

        assert ctx.is_infra_error is True
        assert ctx.infra_error_source == "Docker"


class TestLoadRetryContext:
    """Tests for load_retry_context function."""

    def test_load_no_report(self, repo_path: Path) -> None:
        """Returns None when no stuck report exists."""
        ctx = load_retry_context(repo_path)
        assert ctx is None

    def test_load_with_report(self, repo_with_stuck_report: Path) -> None:
        """Loads context from stuck report."""
        ctx = load_retry_context(repo_with_stuck_report)

        assert ctx is not None
        assert ctx.task_description == "Fix the authentication bug"
        assert len(ctx.constraints) == 2
        assert len(ctx.hypotheses) == 2
        assert len(ctx.artifact_run_ids) == 2

    def test_load_extracts_hypotheses(self, repo_with_stuck_report: Path) -> None:
        """Extracts hypotheses correctly."""
        ctx = load_retry_context(repo_with_stuck_report)

        assert ctx is not None
        title, desc, investigation = ctx.hypotheses[0]
        assert title == "Import Error"
        assert "Module not found" in desc
        assert "import paths" in investigation

    def test_load_extracts_files_modified(self, repo_with_stuck_report: Path) -> None:
        """Extracts modified files."""
        ctx = load_retry_context(repo_with_stuck_report)

        assert ctx is not None
        assert "src/auth.py" in ctx.files_modified
        assert "src/utils.py" in ctx.files_modified


class TestGetRetrySummary:
    """Tests for get_retry_summary function."""

    def test_summary_contains_task(self) -> None:
        """Summary contains task description."""
        ctx = RetryContext(
            task_description="Fix the authentication bug",
            constraints=[],
            hypotheses=[],
            artifact_run_ids=["run_1", "run_2"],
            files_modified=["file.py"],
            is_infra_error=False,
            infra_error_source=None,
        )

        summary = get_retry_summary(ctx)

        assert "Fix the authentication" in summary

    def test_summary_contains_attempt_count(self) -> None:
        """Summary shows number of previous attempts."""
        ctx = RetryContext(
            task_description="Test",
            constraints=[],
            hypotheses=[],
            artifact_run_ids=["run_1", "run_2", "run_3"],
            files_modified=[],
            is_infra_error=False,
            infra_error_source=None,
        )

        summary = get_retry_summary(ctx)

        assert "3" in summary

    def test_summary_shows_infra_error(self) -> None:
        """Summary indicates infra error."""
        ctx = RetryContext(
            task_description="Test",
            constraints=[],
            hypotheses=[],
            artifact_run_ids=[],
            files_modified=[],
            is_infra_error=True,
            infra_error_source="Docker",
        )

        summary = get_retry_summary(ctx)

        assert "Infrastructure error" in summary
        assert "Docker" in summary

    def test_summary_shows_hypotheses(self) -> None:
        """Summary shows hypotheses."""
        ctx = RetryContext(
            task_description="Test",
            constraints=[],
            hypotheses=[
                ("First Hypothesis", "Description one", "Check A"),
                ("Second Hypothesis", "Description two", "Check B"),
            ],
            artifact_run_ids=[],
            files_modified=[],
            is_infra_error=False,
            infra_error_source=None,
        )

        summary = get_retry_summary(ctx)

        assert "First Hypothesis" in summary


class TestShouldShowRetryContext:
    """Tests for should_show_retry_context function."""

    def test_false_when_no_report(self, repo_path: Path) -> None:
        """Returns False when no stuck report."""
        assert should_show_retry_context(repo_path) is False

    def test_true_when_report_exists(self, repo_with_stuck_report: Path) -> None:
        """Returns True when stuck report exists."""
        assert should_show_retry_context(repo_with_stuck_report) is True


class TestClearRetryContext:
    """Tests for clear_retry_context function."""

    def test_clear_removes_report(self, repo_with_stuck_report: Path) -> None:
        """Clears the stuck report."""
        assert should_show_retry_context(repo_with_stuck_report) is True

        result = clear_retry_context(repo_with_stuck_report)

        assert result is True
        assert should_show_retry_context(repo_with_stuck_report) is False

    def test_clear_returns_false_when_no_report(self, repo_path: Path) -> None:
        """Returns False when no report to clear."""
        result = clear_retry_context(repo_path)
        assert result is False


class TestExtractRunIdsFromReport:
    """Tests for extract_run_ids_from_report function."""

    def test_extracts_run_ids(self) -> None:
        """Extracts run IDs from content."""
        content = """
        Verification attempts:
        - run_20260105_120000_abc123: FAIL
        - run_20260105_120100_def456: FAIL
        - run_20260105_120200_ghi789: PASS
        """

        ids = extract_run_ids_from_report(content)

        assert len(ids) == 3
        assert "run_20260105_120000_abc123" in ids
        assert "run_20260105_120100_def456" in ids
        assert "run_20260105_120200_ghi789" in ids

    def test_handles_no_run_ids(self) -> None:
        """Returns empty list when no run IDs."""
        content = "No run IDs here"
        ids = extract_run_ids_from_report(content)
        assert ids == []

    def test_deduplicates_run_ids(self) -> None:
        """Removes duplicate run IDs."""
        content = """
        First mention: run_20260105_120000_abc123
        Second mention: run_20260105_120000_abc123
        """

        ids = extract_run_ids_from_report(content)

        assert len(ids) == 1


class TestGetArtifactPathsForRetry:
    """Tests for get_artifact_paths_for_retry function."""

    def test_finds_existing_artifacts(self, tmp_path: Path) -> None:
        """Finds existing artifact directories."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir(parents=True)

        # Create some run directories
        (runs_dir / "run_20260105_120000_abc123").mkdir()
        (runs_dir / "run_20260105_120100_def456").mkdir()

        run_ids = [
            "run_20260105_120000_abc123",
            "run_20260105_120100_def456",
            "run_20260105_120200_missing",  # Doesn't exist
        ]

        paths = get_artifact_paths_for_retry(tmp_path, run_ids)

        assert len(paths) == 2
        assert "run_20260105_120000_abc123" in paths
        assert "run_20260105_120100_def456" in paths
        assert "run_20260105_120200_missing" not in paths

    def test_returns_correct_paths(self, tmp_path: Path) -> None:
        """Returns correct Path objects."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir(parents=True)
        (runs_dir / "run_20260105_120000_abc123").mkdir()

        paths = get_artifact_paths_for_retry(tmp_path, ["run_20260105_120000_abc123"])

        assert paths["run_20260105_120000_abc123"] == runs_dir / "run_20260105_120000_abc123"

    def test_handles_empty_run_ids(self, tmp_path: Path) -> None:
        """Returns empty dict for empty run_ids."""
        paths = get_artifact_paths_for_retry(tmp_path, [])
        assert paths == {}
