"""Unit tests for main Editor orchestrator."""

from pathlib import Path
from unittest.mock import patch

import pytest

from act.config.env import EnvConfig, LLMBackend, LLMConfig
from act.config.schema import AgentConfig, VerificationConfig, VerificationStep
from act.editor.debug_loop import LoopAction
from act.editor.editor import (
    Editor,
    EditorContext,
    WorkflowState,
    create_editor,
)
from act.editor.exceptions import (
    EditorError,
    HardStopError,
    InfrastructureError,
    WriteBoundaryError,
)
from act.verifier import VerifierResponse, VerifierStatus


# Fixtures
@pytest.fixture
def mock_llm_config() -> LLMConfig:
    """Create a mock LLM config."""
    return LLMConfig(
        backend=LLMBackend.ANTHROPIC,
        api_key="test-key",
        model="test-model",
    )


@pytest.fixture
def mock_env_config(mock_llm_config: LLMConfig, tmp_path: Path) -> EnvConfig:
    """Create a mock environment config."""
    return EnvConfig(
        llm=mock_llm_config,
        artifact_dir=tmp_path / "artifacts",
    )


@pytest.fixture
def mock_agent_config() -> AgentConfig:
    """Create a mock agent config."""
    return AgentConfig(
        verification=VerificationConfig(
            container_image="python:3.11",
            steps=[
                VerificationStep(name="test", command="pytest"),
            ],
        ),
    )


@pytest.fixture
def editor(
    tmp_path: Path,
    mock_agent_config: AgentConfig,
    mock_llm_config: LLMConfig,
    mock_env_config: EnvConfig,
) -> Editor:
    """Create an Editor instance for testing."""
    return Editor(
        repo_root=tmp_path,
        agent_config=mock_agent_config,
        llm_config=mock_llm_config,
        env_config=mock_env_config,
    )


class TestEditorState:
    """Tests for WorkflowState enum."""

    def test_all_states_defined(self) -> None:
        """Test all expected states are defined."""
        expected = [
            "IDLE",
            "ANALYZING",
            "IMPLEMENTING",
            "VERIFYING",
            "DEBUGGING",
            "REPLANNING",
            "COMPLETED",
            "STUCK",
            "INFRA_ERROR",
            "CANCELLED",
        ]
        actual = [s.name for s in WorkflowState]
        assert set(expected) == set(actual)


class TestEditorContext:
    """Tests for EditorContext dataclass."""

    def test_default_context(self) -> None:
        """Test default context values."""
        ctx = EditorContext()
        assert ctx.task is None
        assert ctx.scout_results is None
        assert ctx.files_modified == []
        assert ctx.current_hypothesis == ""
        assert ctx.dry_run_mode is False

    def test_to_dict(self) -> None:
        """Test to_dict conversion."""
        ctx = EditorContext(
            files_modified=["src/main.py"],
            current_hypothesis="Test hypothesis",
            dry_run_mode=True,
        )
        d = ctx.to_dict()

        assert d["files_modified"] == ["src/main.py"]
        assert d["current_hypothesis"] == "Test hypothesis"
        assert d["dry_run_mode"] is True


class TestEditorInitialization:
    """Tests for Editor initialization."""

    def test_editor_initialization(self, editor: Editor, tmp_path: Path) -> None:
        """Test editor initializes correctly."""
        assert editor.repo_root == tmp_path
        assert editor.state == WorkflowState.IDLE
        assert editor.agent_dir == tmp_path / "agent"

    def test_editor_components_initialized(self, editor: Editor) -> None:
        """Test editor components are initialized."""
        assert editor.coordinator is not None
        assert editor.debug_loop is not None
        assert editor.dry_run_manager is not None
        assert editor.boundary_enforcer is not None


class TestEditorReset:
    """Tests for Editor reset."""

    def test_reset_clears_state(self, editor: Editor) -> None:
        """Test reset clears all state."""
        editor._state = WorkflowState.DEBUGGING
        editor._context.current_hypothesis = "Test"
        editor._context.files_modified = ["file.py"]

        editor.reset()

        assert editor.state == WorkflowState.IDLE
        assert editor.context.current_hypothesis == ""
        assert editor.context.files_modified == []


class TestEditorStartTask:
    """Tests for Editor start_task method."""

    @pytest.mark.asyncio
    async def test_start_task(self, editor: Editor) -> None:
        """Test starting a new task."""
        task = await editor.start_task("Fix the login bug")

        assert task.main_objective == "Fix the login bug"
        assert editor.state == WorkflowState.ANALYZING
        assert editor.context.task is not None

    @pytest.mark.asyncio
    async def test_start_task_dry_run(self, editor: Editor) -> None:
        """Test starting a task in dry-run mode."""
        await editor.start_task("Fix bug", dry_run=True)

        assert editor.context.dry_run_mode is True
        assert editor.dry_run_manager.is_active is True

    @pytest.mark.asyncio
    async def test_start_task_creates_snapshot(
        self, editor: Editor, tmp_path: Path
    ) -> None:
        """Test that starting a task creates a context snapshot."""
        await editor.start_task("Fix bug")

        # Check that context file was created
        agent_dir = tmp_path / "agent"
        context_files = list(agent_dir.glob("context_*.md"))
        assert len(context_files) >= 1


class TestEditorBoundaries:
    """Tests for Editor write boundaries."""

    def test_validate_write_path_in_repo(
        self, editor: Editor, tmp_path: Path
    ) -> None:
        """Test validating path within repo."""
        path = editor.validate_write_path("src/main.py")
        assert path == tmp_path / "src" / "main.py"

    def test_validate_write_path_outside_repo(self, editor: Editor) -> None:
        """Test validating path outside repo raises error."""
        with pytest.raises(WriteBoundaryError):
            editor.validate_write_path("/etc/passwd")

    def test_record_file_modification(self, editor: Editor) -> None:
        """Test recording file modifications."""
        editor.record_file_modification("src/main.py")
        editor.record_file_modification("src/utils.py")

        assert "src/main.py" in editor.context.files_modified
        assert "src/utils.py" in editor.context.files_modified

    def test_record_file_modification_no_duplicates(self, editor: Editor) -> None:
        """Test that duplicate modifications aren't recorded."""
        editor.record_file_modification("src/main.py")
        editor.record_file_modification("src/main.py")

        assert editor.context.files_modified.count("src/main.py") == 1


class TestEditorVerification:
    """Tests for Editor verification handling."""

    @pytest.mark.asyncio
    async def test_handle_verification_pass(self, editor: Editor) -> None:
        """Test handling successful verification."""
        await editor.start_task("Fix bug")

        response = VerifierResponse(
            status=VerifierStatus.PASS,
            run_id="run_001",
        )
        action = editor.handle_verification_result(response)

        assert action == LoopAction.SUCCESS
        assert editor.state == WorkflowState.COMPLETED

    @pytest.mark.asyncio
    async def test_handle_verification_fail(self, editor: Editor) -> None:
        """Test handling failed verification."""
        await editor.start_task("Fix bug")

        response = VerifierResponse(
            status=VerifierStatus.FAIL,
            run_id="run_001",
            tail_log="Error: test failed",
        )
        action = editor.handle_verification_result(response)

        assert action == LoopAction.CONTINUE
        assert editor.state == WorkflowState.DEBUGGING

    @pytest.mark.asyncio
    async def test_handle_verification_infra_error(self, editor: Editor) -> None:
        """Test handling infrastructure error."""
        await editor.start_task("Fix bug")

        response = VerifierResponse(
            status=VerifierStatus.INFRA_ERROR,
            error_message="Docker unavailable",
        )

        action = editor.handle_verification_result(response)

        assert action == LoopAction.INFRA_ERROR
        assert editor.state == WorkflowState.INFRA_ERROR

    @pytest.mark.asyncio
    async def test_three_failures_triggers_replan(self, editor: Editor) -> None:
        """Test that 3 consecutive failures triggers REPLAN."""
        await editor.start_task("Fix bug")

        for i in range(3):
            response = VerifierResponse(
                status=VerifierStatus.FAIL,
                run_id=f"run_{i:03d}",
            )
            action = editor.handle_verification_result(response)

        assert action == LoopAction.REPLAN
        assert editor.state == WorkflowState.REPLANNING

    @pytest.mark.asyncio
    async def test_twelve_failures_triggers_hard_stop(self, editor: Editor) -> None:
        """Test that 12 total failures triggers hard stop."""
        await editor.start_task("Fix bug")

        for i in range(12):
            response = VerifierResponse(
                status=VerifierStatus.FAIL,
                run_id=f"run_{i:03d}",
            )
            action = editor.handle_verification_result(response)
            if action == LoopAction.REPLAN:
                await editor.trigger_replan(f"Strategy {i}")
            elif action == LoopAction.STUCK:
                # Expected at loop 12
                break

        assert editor.state == WorkflowState.STUCK


class TestEditorReplan:
    """Tests for Editor REPLAN functionality."""

    @pytest.mark.asyncio
    async def test_trigger_replan(self, editor: Editor) -> None:
        """Test triggering REPLAN."""
        await editor.start_task("Fix bug")

        await editor.trigger_replan("Try different approach")

        assert editor.debug_loop.replan_count == 1
        assert editor.context.current_hypothesis == "Try different approach"

    @pytest.mark.asyncio
    async def test_trigger_replan_creates_snapshot(
        self, editor: Editor, tmp_path: Path
    ) -> None:
        """Test that REPLAN creates a context snapshot."""
        await editor.start_task("Fix bug")

        # Get initial snapshot count
        agent_dir = tmp_path / "agent"
        initial_count = len(list(agent_dir.glob("context_*.md")))

        await editor.trigger_replan("New strategy")

        # Should have one more snapshot
        new_count = len(list(agent_dir.glob("context_*.md")))
        assert new_count == initial_count + 1


class TestEditorOutputs:
    """Tests for Editor output generation."""

    @pytest.mark.asyncio
    async def test_generate_success_summary(self, editor: Editor) -> None:
        """Test generating success summary."""
        await editor.start_task("Fix login bug")
        editor.context.current_hypothesis = "Fixed timeout"

        # Simulate successful verification
        editor._context.last_verification = VerifierResponse(
            status=VerifierStatus.PASS,
            run_id="run_001",
        )
        editor.record_file_modification("src/login.py")

        summary = editor.generate_success_summary()

        assert summary.run_id == "run_001"
        assert "src/login.py" in summary.files_modified

    @pytest.mark.asyncio
    async def test_generate_success_summary_no_task_raises(
        self, editor: Editor
    ) -> None:
        """Test that generating summary without task raises error."""
        with pytest.raises(EditorError, match="No task"):
            editor.generate_success_summary()

    @pytest.mark.asyncio
    async def test_generate_stuck_report(self, editor: Editor) -> None:
        """Test generating stuck report."""
        await editor.start_task("Fix bug")
        editor.record_file_modification("src/main.py")

        # Simulate some failures
        for i in range(3):
            editor.debug_loop.record_failure(f"run_{i:03d}", "Error")

        report = editor.generate_stuck_report()

        assert report.task_description == "Fix bug"
        assert len(report.hypotheses) > 0

    @pytest.mark.asyncio
    async def test_generate_stuck_report_writes_file(
        self, editor: Editor, tmp_path: Path
    ) -> None:
        """Test that stuck report is written to file."""
        await editor.start_task("Fix bug")

        editor.generate_stuck_report()

        report_path = tmp_path / "agent" / "stuck_report.md"
        assert report_path.exists()


class TestEditorDryRun:
    """Tests for Editor dry-run mode."""

    @pytest.mark.asyncio
    async def test_get_dry_run_proposal_not_active(self, editor: Editor) -> None:
        """Test getting proposal when not in dry-run mode."""
        await editor.start_task("Fix bug", dry_run=False)
        assert editor.get_dry_run_proposal() is None

    @pytest.mark.asyncio
    async def test_get_dry_run_proposal_active(self, editor: Editor) -> None:
        """Test getting proposal when in dry-run mode."""
        await editor.start_task("Fix bug", dry_run=True)
        assert editor.get_dry_run_proposal() is not None

    @pytest.mark.asyncio
    async def test_apply_dry_run_changes_not_active_raises(
        self, editor: Editor
    ) -> None:
        """Test applying changes when not in dry-run mode raises error."""
        await editor.start_task("Fix bug", dry_run=False)
        with pytest.raises(EditorError, match="dry-run"):
            editor.apply_dry_run_changes()

    @pytest.mark.asyncio
    async def test_discard_dry_run_changes(self, editor: Editor) -> None:
        """Test discarding dry-run changes."""
        await editor.start_task("Fix bug", dry_run=True)
        editor.discard_dry_run_changes()
        assert editor.context.dry_run_mode is False


class TestEditorStatus:
    """Tests for Editor status messages."""

    def test_get_status_message_idle(self, editor: Editor) -> None:
        """Test status message when idle."""
        msg = editor.get_status_message()
        assert "Idle" in msg

    @pytest.mark.asyncio
    async def test_get_status_message_analyzing(self, editor: Editor) -> None:
        """Test status message when analyzing."""
        await editor.start_task("Fix bug")
        msg = editor.get_status_message()
        assert "Analyzing" in msg

    @pytest.mark.asyncio
    async def test_get_status_message_debugging(self, editor: Editor) -> None:
        """Test status message when debugging."""
        await editor.start_task("Fix bug")
        editor._state = WorkflowState.DEBUGGING
        msg = editor.get_status_message()
        assert "Debugging" in msg
        assert "/12" in msg  # Should show attempt count


class TestCreateEditor:
    """Tests for create_editor factory."""

    def test_creates_editor(
        self,
        tmp_path: Path,
        mock_agent_config: AgentConfig,
        mock_llm_config: LLMConfig,
    ) -> None:
        """Test factory creates editor."""
        editor = create_editor(
            tmp_path,
            mock_agent_config,
            mock_llm_config,
        )
        assert editor.repo_root == tmp_path

    def test_creates_editor_without_llm_config(
        self,
        tmp_path: Path,
        mock_agent_config: AgentConfig,
    ) -> None:
        """Test factory creates editor without explicit LLM config."""
        # This would load from environment, but we patch it
        with patch("act.editor.editor.load_env_config") as mock_load:
            mock_load.return_value = EnvConfig(
                llm=LLMConfig(
                    backend=LLMBackend.ANTHROPIC,
                    api_key="test",
                ),
                artifact_dir=tmp_path / "artifacts",
            )
            editor = create_editor(tmp_path, mock_agent_config)
            assert editor is not None
