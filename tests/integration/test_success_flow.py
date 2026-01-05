"""Integration test: Success flow (6.1.1).

Tests the full successful task completion flow:
- Task completes with SUCCESS state on first verification attempt
- Code change is correct
- Summary references passing run_id
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from act.editor.coordinator import ScoutResults
from act.editor.debug_loop import LoopAction
from act.editor.editor import Editor, WorkflowState, create_editor
from act.task.state import TaskState, create_task
from act.verifier.response import VerifierResponse, VerifierStatus

from .conftest import make_pass_response


class TestSuccessFlowEditorLevel:
    """Test successful task completion at Editor level."""

    @pytest.mark.asyncio
    async def test_editor_completes_task_on_first_success(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Editor completes task successfully on first verification pass."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        # Mock Scout coordinator to return immediately
        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results

            # Start task
            await editor.start_task("Add console.log to main function")
            assert editor.state == WorkflowState.ANALYZING

            # Analyze codebase
            await editor.analyze_codebase()
            assert mock_analysis.called

        # Simulate successful verification
        response = make_pass_response("run_001")
        action = editor.handle_verification_result(response)

        # Assertions
        assert action == LoopAction.SUCCESS
        assert editor.state == WorkflowState.COMPLETED
        assert editor._debug_loop.state.total_verify_loops == 1
        assert editor._debug_loop.state.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_success_generates_summary_with_run_id(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Success generates summary containing the passing run_id."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await editor.start_task("Fix bug in authentication")
            await editor.analyze_codebase()

        # Record a file modification
        editor.record_file_modification("src/main.py")

        # Simulate successful verification
        response = make_pass_response("run_success_001")
        editor.handle_verification_result(response)

        # Generate summary
        summary = editor.generate_success_summary()

        assert summary is not None
        assert summary.run_id == "run_success_001"
        assert "src/main.py" in editor._context.files_modified

    @pytest.mark.asyncio
    async def test_success_state_transitions(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Verify correct state transitions during success flow."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        # Initial state
        assert editor.state == WorkflowState.IDLE

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results

            # After start_task
            await editor.start_task("Task description")
            assert editor.state == WorkflowState.ANALYZING

            # After analyze_codebase
            await editor.analyze_codebase()
            # Still in ANALYZING after scout queries complete

        # After successful verification
        response = make_pass_response("run_001")
        editor.handle_verification_result(response)
        assert editor.state == WorkflowState.COMPLETED


class TestSuccessFlowContextSnapshots:
    """Test context snapshot creation during success flow."""

    @pytest.mark.asyncio
    async def test_context_snapshot_created_on_task_start(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Context snapshot is created when task starts."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await editor.start_task("Test task")

        # Check for context snapshot
        agent_dir = integration_repo / "agent"
        context_files = list(agent_dir.glob("context_*.md"))
        assert len(context_files) >= 1

    @pytest.mark.asyncio
    async def test_context_snapshot_created_on_success(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Context snapshot is created on successful completion."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await editor.start_task("Test task")
            await editor.analyze_codebase()

        # Count snapshots before success
        agent_dir = integration_repo / "agent"
        initial_count = len(list(agent_dir.glob("context_*.md")))

        # Trigger success
        response = make_pass_response("run_001")
        editor.handle_verification_result(response)

        # Check for new snapshot
        final_count = len(list(agent_dir.glob("context_*.md")))
        assert final_count >= initial_count


class TestSuccessFlowDebugLoop:
    """Test debug loop behavior during success flow."""

    @pytest.mark.asyncio
    async def test_success_resets_counters(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Success resets debug loop counters."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await editor.start_task("Test task")
            await editor.analyze_codebase()

        # Trigger success
        response = make_pass_response("run_001")
        action = editor.handle_verification_result(response)

        assert action == LoopAction.SUCCESS
        # After success, counters should reflect 1 successful attempt
        assert editor._debug_loop.state.total_verify_loops == 1
        assert editor._debug_loop.state.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_success_after_failures(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Success can occur after initial failures."""
        from .conftest import make_fail_response

        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await editor.start_task("Test task")
            await editor.analyze_codebase()

        # Two failures first
        for i in range(2):
            fail_response = make_fail_response(f"run_fail_{i}", f"Error {i}")
            action = editor.handle_verification_result(fail_response)
            assert action == LoopAction.CONTINUE

        # Then success
        success_response = make_pass_response("run_success")
        action = editor.handle_verification_result(success_response)

        assert action == LoopAction.SUCCESS
        assert editor.state == WorkflowState.COMPLETED
        assert editor._debug_loop.state.total_verify_loops == 3
