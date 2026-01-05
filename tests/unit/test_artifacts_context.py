"""Tests for context snapshot management."""

from pathlib import Path

from act.artifacts.context import (
    EditorState,
    Milestone,
    get_latest_snapshot_path,
    get_snapshot_count,
    should_create_snapshot,
    write_context_snapshot,
)


class TestWriteContextSnapshot:
    """Tests for write_context_snapshot function."""

    def test_creates_first_snapshot(self, tmp_path: Path) -> None:
        """First snapshot creates context_001.md."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        snapshot_path = write_context_snapshot(
            agent_dir=agent_dir,
            milestone=Milestone.TASK_START,
            timestamp="2024-01-15T14:32:00Z",
        )

        assert snapshot_path.exists()
        assert snapshot_path.name == "context_001.md"

    def test_creates_subsequent_snapshots(self, tmp_path: Path) -> None:
        """Subsequent snapshots increment the number."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        # First snapshot
        path1 = write_context_snapshot(
            agent_dir=agent_dir,
            milestone=Milestone.TASK_START,
        )

        # Second snapshot
        path2 = write_context_snapshot(
            agent_dir=agent_dir,
            milestone=Milestone.REPLAN,
        )

        assert path1.name == "context_001.md"
        assert path2.name == "context_002.md"

    def test_updates_latest_symlink(self, tmp_path: Path) -> None:
        """Updates context_latest.md symlink."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        write_context_snapshot(
            agent_dir=agent_dir,
            milestone=Milestone.TASK_START,
        )

        latest = agent_dir / "context_latest.md"
        assert latest.exists()

        # Check it points to the right file
        if latest.is_symlink():
            # On systems with symlink support
            target = latest.resolve()
            assert target.name == "context_001.md"
        else:
            # On systems without symlink support (copied content)
            content = latest.read_text()
            assert "Context Snapshot 001" in content

    def test_symlink_updates_on_new_snapshot(self, tmp_path: Path) -> None:
        """Symlink updates when new snapshot created."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.TASK_START)
        write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.REPLAN)

        latest = agent_dir / "context_latest.md"

        # Should now point to context_002.md
        if latest.is_symlink():
            target = latest.resolve()
            assert target.name == "context_002.md"
        else:
            content = latest.read_text()
            assert "Context Snapshot 002" in content

    def test_snapshot_contains_timestamp(self, tmp_path: Path) -> None:
        """Snapshot contains UTC timestamp."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        write_context_snapshot(
            agent_dir=agent_dir,
            milestone=Milestone.TASK_START,
            timestamp="2024-01-15T14:32:00Z",
        )

        content = (agent_dir / "context_001.md").read_text()
        assert "2024-01-15T14:32:00Z" in content

    def test_snapshot_contains_milestone(self, tmp_path: Path) -> None:
        """Snapshot contains milestone type."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        write_context_snapshot(
            agent_dir=agent_dir,
            milestone=Milestone.REPLAN,
        )

        content = (agent_dir / "context_001.md").read_text()
        assert "REPLAN" in content

    def test_snapshot_contains_scout_payloads(self, tmp_path: Path) -> None:
        """Snapshot contains raw Scout payloads."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        scout_a = {"schema_version": "1", "repo_map": {"relevant_files": []}}
        scout_b = {"schema_version": "1", "build": {"detected_system": "npm"}}

        write_context_snapshot(
            agent_dir=agent_dir,
            milestone=Milestone.TASK_START,
            scout_a_payload=scout_a,
            scout_b_payload=scout_b,
        )

        content = (agent_dir / "context_001.md").read_text()
        assert "Scout A Report" in content
        assert "Scout B Report" in content
        assert "schema_version" in content
        assert "relevant_files" in content
        assert "detected_system" in content

    def test_snapshot_contains_editor_state(self, tmp_path: Path) -> None:
        """Snapshot contains Editor state."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        editor_state = EditorState(
            hypothesis="The bug is in auth module",
            files_modified=["src/auth.py", "tests/test_auth.py"],
            verify_attempts=3,
            consecutive_failures=2,
            total_verify_loops=5,
        )

        write_context_snapshot(
            agent_dir=agent_dir,
            milestone=Milestone.REPLAN,
            editor_state=editor_state,
        )

        content = (agent_dir / "context_001.md").read_text()
        assert "Editor State" in content
        assert "The bug is in auth module" in content
        assert "src/auth.py" in content
        assert "Verify attempts: 3" in content

    def test_creates_agent_dir_if_missing(self, tmp_path: Path) -> None:
        """Creates agent directory if it doesn't exist."""
        agent_dir = tmp_path / "agent"
        # Don't create it

        write_context_snapshot(
            agent_dir=agent_dir,
            milestone=Milestone.TASK_START,
        )

        assert agent_dir.is_dir()
        assert (agent_dir / "context_001.md").exists()


class TestGetLatestSnapshotPath:
    """Tests for get_latest_snapshot_path function."""

    def test_returns_latest_via_symlink(self, tmp_path: Path) -> None:
        """Returns latest snapshot path via symlink."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.TASK_START)
        write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.REPLAN)

        latest = get_latest_snapshot_path(agent_dir)

        assert latest is not None
        assert "002" in latest.name or latest.name == "context_latest.md"

    def test_returns_none_for_empty_dir(self, tmp_path: Path) -> None:
        """Returns None when no snapshots exist."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        latest = get_latest_snapshot_path(agent_dir)

        assert latest is None

    def test_returns_none_for_missing_dir(self, tmp_path: Path) -> None:
        """Returns None when agent dir doesn't exist."""
        agent_dir = tmp_path / "agent"

        latest = get_latest_snapshot_path(agent_dir)

        assert latest is None


class TestGetSnapshotCount:
    """Tests for get_snapshot_count function."""

    def test_counts_snapshots(self, tmp_path: Path) -> None:
        """Counts snapshot files correctly."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.TASK_START)
        write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.REPLAN)
        write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.TASK_SUCCESS)

        assert get_snapshot_count(agent_dir) == 3

    def test_returns_zero_for_empty_dir(self, tmp_path: Path) -> None:
        """Returns 0 for empty directory."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        assert get_snapshot_count(agent_dir) == 0

    def test_returns_zero_for_missing_dir(self, tmp_path: Path) -> None:
        """Returns 0 for missing directory."""
        agent_dir = tmp_path / "agent"

        assert get_snapshot_count(agent_dir) == 0

    def test_ignores_non_snapshot_files(self, tmp_path: Path) -> None:
        """Ignores files that aren't snapshots."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.TASK_START)

        # Create non-snapshot files
        (agent_dir / "other_file.md").write_text("other content")
        (agent_dir / "context_latest.md")  # symlink, shouldn't be counted

        # Only 1 actual snapshot
        assert get_snapshot_count(agent_dir) == 1


class TestShouldCreateSnapshot:
    """Tests for should_create_snapshot function."""

    def test_task_start_creates_snapshot(self) -> None:
        """TASK_START triggers snapshot."""
        assert should_create_snapshot(Milestone.TASK_START) is True

    def test_replan_creates_snapshot(self) -> None:
        """REPLAN triggers snapshot."""
        assert should_create_snapshot(Milestone.REPLAN) is True

    def test_task_success_creates_snapshot(self) -> None:
        """TASK_SUCCESS triggers snapshot."""
        assert should_create_snapshot(Milestone.TASK_SUCCESS) is True

    def test_string_milestones_work(self) -> None:
        """String milestone values also work."""
        assert should_create_snapshot("TASK_START") is True
        assert should_create_snapshot("REPLAN") is True
        assert should_create_snapshot("TASK_SUCCESS") is True

    def test_invalid_milestone_returns_false(self) -> None:
        """Invalid milestone strings return False."""
        assert should_create_snapshot("SCOUT_QUERY") is False
        assert should_create_snapshot("VERIFY_ATTEMPT") is False
        assert should_create_snapshot("FIX_ITERATION") is False
        assert should_create_snapshot("unknown") is False


class TestSnapshotTriggerScenario:
    """Tests for snapshot trigger behavior in realistic scenarios."""

    def test_task_with_replan_creates_three_snapshots(self, tmp_path: Path) -> None:
        """Mock task with 3 verifies + 1 REPLAN = exactly 3 snapshots."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        # Simulate: TASK_START, 3 verify attempts (no snapshots), REPLAN, SUCCESS
        # Only semantic milestones create snapshots

        # 1. Task starts
        if should_create_snapshot(Milestone.TASK_START):
            write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.TASK_START)

        # 2. Three verify attempts (should NOT create snapshots)
        for _ in range(3):
            if should_create_snapshot("VERIFY_ATTEMPT"):
                write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.REPLAN)
            # No snapshot for verify attempts

        # 3. REPLAN triggered
        if should_create_snapshot(Milestone.REPLAN):
            write_context_snapshot(agent_dir=agent_dir, milestone=Milestone.REPLAN)

        # 4. Task succeeds
        if should_create_snapshot(Milestone.TASK_SUCCESS):
            write_context_snapshot(
                agent_dir=agent_dir, milestone=Milestone.TASK_SUCCESS
            )

        # Should have exactly 3 snapshots: start, replan, success
        assert get_snapshot_count(agent_dir) == 3


class TestEditorState:
    """Tests for EditorState dataclass."""

    def test_default_values(self) -> None:
        """EditorState has sensible defaults."""
        state = EditorState()

        assert state.hypothesis == ""
        assert state.files_modified == []
        assert state.verify_attempts == 0
        assert state.consecutive_failures == 0
        assert state.total_verify_loops == 0

    def test_custom_values(self) -> None:
        """EditorState accepts custom values."""
        state = EditorState(
            hypothesis="test",
            files_modified=["a.py", "b.py"],
            verify_attempts=5,
            consecutive_failures=2,
            total_verify_loops=8,
        )

        assert state.hypothesis == "test"
        assert len(state.files_modified) == 2
        assert state.verify_attempts == 5


class TestMilestoneEnum:
    """Tests for Milestone enum."""

    def test_all_milestones(self) -> None:
        """All milestone values exist."""
        assert Milestone.TASK_START.value == "TASK_START"
        assert Milestone.REPLAN.value == "REPLAN"
        assert Milestone.TASK_SUCCESS.value == "TASK_SUCCESS"
