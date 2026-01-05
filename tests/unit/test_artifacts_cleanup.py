"""Tests for artifact retention and cleanup management."""

from datetime import UTC, datetime
from pathlib import Path

from act.artifacts.cleanup import (
    STUCK_REPORT_FILENAME,
    RunInfo,
    cleanup_runs,
    get_run_count,
    get_runs_to_delete,
    list_runs,
)


def _create_run_dir(
    runs_dir: Path,
    run_id: str,
    has_stuck_report: bool = False,
) -> Path:
    """Helper to create a mock run directory."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)

    # Create a manifest.json to make it look like a real run
    (run_dir / "manifest.json").write_text("{}")

    if has_stuck_report:
        (run_dir / STUCK_REPORT_FILENAME).write_text("# Stuck Report")

    return run_dir


def _create_artifact_structure(tmp_path: Path) -> tuple[Path, Path]:
    """Helper to create artifact directory structure."""
    artifact_dir = tmp_path / "artifacts"
    runs_dir = artifact_dir / "runs"
    runs_dir.mkdir(parents=True)
    return artifact_dir, runs_dir


class TestListRuns:
    """Tests for list_runs function."""

    def test_returns_empty_for_no_runs(self, tmp_path: Path) -> None:
        """Returns empty list when no runs exist."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        runs = list_runs(artifact_dir)

        assert runs == []

    def test_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        """Returns empty list when runs dir doesn't exist."""
        artifact_dir = tmp_path / "artifacts"

        runs = list_runs(artifact_dir)

        assert runs == []

    def test_lists_valid_runs(self, tmp_path: Path) -> None:
        """Lists all valid run directories."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        _create_run_dir(runs_dir, "run_20240115_100000_abc123")
        _create_run_dir(runs_dir, "run_20240115_110000_def456")

        runs = list_runs(artifact_dir)

        assert len(runs) == 2
        assert all(isinstance(r, RunInfo) for r in runs)

    def test_ignores_invalid_directories(self, tmp_path: Path) -> None:
        """Ignores directories that aren't valid runs."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        _create_run_dir(runs_dir, "run_20240115_100000_abc123")
        (runs_dir / "not_a_run").mkdir()
        (runs_dir / "invalid_format").mkdir()

        runs = list_runs(artifact_dir)

        assert len(runs) == 1
        assert runs[0].run_id == "run_20240115_100000_abc123"

    def test_sorts_by_timestamp_oldest_first(self, tmp_path: Path) -> None:
        """Runs are sorted with oldest first."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        _create_run_dir(runs_dir, "run_20240115_120000_ccc333")  # newest
        _create_run_dir(runs_dir, "run_20240115_100000_aaa111")  # oldest
        _create_run_dir(runs_dir, "run_20240115_110000_bbb222")  # middle

        runs = list_runs(artifact_dir)

        assert len(runs) == 3
        assert runs[0].run_id == "run_20240115_100000_aaa111"
        assert runs[1].run_id == "run_20240115_110000_bbb222"
        assert runs[2].run_id == "run_20240115_120000_ccc333"

    def test_detects_stuck_reports(self, tmp_path: Path) -> None:
        """Detects runs with stuck reports."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        _create_run_dir(runs_dir, "run_20240115_100000_abc123", has_stuck_report=True)
        _create_run_dir(runs_dir, "run_20240115_110000_def456", has_stuck_report=False)

        runs = list_runs(artifact_dir)

        stuck_run = next(r for r in runs if r.run_id == "run_20240115_100000_abc123")
        normal_run = next(r for r in runs if r.run_id == "run_20240115_110000_def456")

        assert stuck_run.has_stuck_report is True
        assert normal_run.has_stuck_report is False


class TestGetRunsToDelete:
    """Tests for get_runs_to_delete function."""

    def test_deletes_oldest_when_over_max(self) -> None:
        """Deletes oldest runs when count exceeds max."""
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        runs = [
            RunInfo(
                run_id=f"run_20240115_0{i}0000_abc{i:03d}",
                run_dir=Path(f"/runs/run_{i}"),
                timestamp=datetime(2024, 1, 15, i, 0, 0, tzinfo=UTC),
                has_stuck_report=False,
            )
            for i in range(10, 16)  # 6 runs
        ]

        to_delete = get_runs_to_delete(runs, max_runs=4, now=now)

        # Should delete 2 oldest
        assert len(to_delete) == 2
        assert to_delete[0].run_id == "run_20240115_0100000_abc010"
        assert to_delete[1].run_id == "run_20240115_0110000_abc011"

    def test_deletes_old_runs_by_age(self) -> None:
        """Deletes runs older than max age."""
        now = datetime(2024, 1, 30, 12, 0, 0, tzinfo=UTC)

        runs = [
            RunInfo(
                run_id="run_20240110_100000_old001",
                run_dir=Path("/runs/old1"),
                timestamp=datetime(2024, 1, 10, 10, 0, 0, tzinfo=UTC),  # 20 days old
                has_stuck_report=False,
            ),
            RunInfo(
                run_id="run_20240125_100000_new001",
                run_dir=Path("/runs/new1"),
                timestamp=datetime(2024, 1, 25, 10, 0, 0, tzinfo=UTC),  # 5 days old
                has_stuck_report=False,
            ),
        ]

        to_delete = get_runs_to_delete(runs, max_age_days=14, now=now)

        assert len(to_delete) == 1
        assert to_delete[0].run_id == "run_20240110_100000_old001"

    def test_preserves_stuck_report_runs(self) -> None:
        """Never deletes runs with stuck reports."""
        now = datetime(2024, 1, 30, 12, 0, 0, tzinfo=UTC)

        runs = [
            RunInfo(
                run_id="run_20240101_100000_stuck1",
                run_dir=Path("/runs/stuck1"),
                timestamp=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),  # Very old
                has_stuck_report=True,
            ),
            RunInfo(
                run_id="run_20240125_100000_normal",
                run_dir=Path("/runs/normal"),
                timestamp=datetime(2024, 1, 25, 10, 0, 0, tzinfo=UTC),
                has_stuck_report=False,
            ),
        ]

        # Even with max_runs=1, stuck run should be preserved (but normal can be deleted)
        to_delete = get_runs_to_delete(runs, max_runs=1, max_age_days=14, now=now)

        # The normal run may be deleted to meet max_runs, but stuck run is never deleted
        assert all(not r.has_stuck_report for r in to_delete)


class TestCleanupRuns:
    """Tests for cleanup_runs function."""

    def test_deletes_oldest_to_reach_max(self, tmp_path: Path) -> None:
        """Deletes oldest runs to reach max count."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        # Create 25 runs (use valid hours 0-23, then minutes for remaining)
        for i in range(25):
            hour = i % 24
            minute = i // 24
            _create_run_dir(runs_dir, f"run_20240115_{hour:02d}{minute:02d}00_abc{i:03d}")

        # Use a fixed "now" that's close to the run dates (so they're not considered old by age)
        now = datetime(2024, 1, 16, 12, 0, 0, tzinfo=UTC)

        # Should delete 5 to get to 20
        deleted = cleanup_runs(artifact_dir, max_runs=20, now=now)

        assert deleted == 5
        assert get_run_count(artifact_dir) == 20

    def test_deletes_by_age(self, tmp_path: Path) -> None:
        """Deletes runs older than max age."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        # Create some old runs (15+ days old)
        _create_run_dir(runs_dir, "run_20240101_100000_old001")
        _create_run_dir(runs_dir, "run_20240102_100000_old002")

        # Create some recent runs
        _create_run_dir(runs_dir, "run_20240125_100000_new001")

        now = datetime(2024, 1, 30, 12, 0, 0, tzinfo=UTC)
        deleted = cleanup_runs(artifact_dir, max_age_days=14, now=now)

        assert deleted == 2
        remaining = list_runs(artifact_dir)
        assert len(remaining) == 1
        assert remaining[0].run_id == "run_20240125_100000_new001"

    def test_preserves_stuck_reports(self, tmp_path: Path) -> None:
        """Preserves runs with stuck reports."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        # Create old stuck run
        _create_run_dir(
            runs_dir, "run_20240101_100000_stuck1", has_stuck_report=True
        )

        # Create recent normal run
        _create_run_dir(runs_dir, "run_20240125_100000_new001")

        now = datetime(2024, 1, 30, 12, 0, 0, tzinfo=UTC)
        deleted = cleanup_runs(artifact_dir, max_age_days=14, now=now)

        # Stuck run should be preserved despite being old
        assert deleted == 0
        remaining = list_runs(artifact_dir)
        assert len(remaining) == 2

        stuck = next(r for r in remaining if r.has_stuck_report)
        assert stuck.run_id == "run_20240101_100000_stuck1"


class TestGetRunCount:
    """Tests for get_run_count function."""

    def test_counts_runs(self, tmp_path: Path) -> None:
        """Counts runs correctly."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        _create_run_dir(runs_dir, "run_20240115_100000_abc123")
        _create_run_dir(runs_dir, "run_20240115_110000_def456")

        assert get_run_count(artifact_dir) == 2

    def test_returns_zero_for_empty(self, tmp_path: Path) -> None:
        """Returns 0 for empty artifact dir."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        assert get_run_count(artifact_dir) == 0


class TestRetentionPolicy:
    """Tests for overall retention policy behavior."""

    def test_25_runs_cleaned_to_20(self, tmp_path: Path) -> None:
        """25 runs cleaned to exactly 20, oldest 5 deleted."""
        artifact_dir, runs_dir = _create_artifact_structure(tmp_path)

        # Create 25 runs spread across multiple days to ensure correct ordering
        # Day 1 (10th): runs 0-9, Day 2 (11th): runs 10-19, Day 3 (12th): runs 20-24
        for i in range(25):
            day = 10 + (i // 10)  # 10, 10, 10... 11, 11... 12, 12...
            hour = (i % 10) * 2  # 0, 2, 4, 6... to spread within day
            _create_run_dir(runs_dir, f"run_202401{day:02d}_{hour:02d}0000_abc{i:03d}")

        # Use a fixed "now" that's close to the run dates (so they're not considered old by age)
        now = datetime(2024, 1, 16, 12, 0, 0, tzinfo=UTC)

        # Cleanup
        deleted = cleanup_runs(artifact_dir, max_runs=20, now=now)

        assert deleted == 5
        remaining = list_runs(artifact_dir)
        assert len(remaining) == 20

        # Check oldest runs are gone (first 5 by chronological order)
        remaining_suffixes = {run.run_id.split("_")[3] for run in remaining}
        assert "abc000" not in remaining_suffixes  # Day 10, hour 0
        assert "abc004" not in remaining_suffixes  # Day 10, hour 8
        assert "abc005" in remaining_suffixes  # Day 10, hour 10 (first kept)
        assert "abc024" in remaining_suffixes  # Day 12, last run (kept)
