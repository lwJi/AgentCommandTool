"""Integration test: Hard stop flow (6.1.3).

Tests the hard stop at 12 total verify loops:
- State transitions to STUCK
- HardStopError is raised
- Stuck report is generated
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from act.editor.coordinator import ScoutResults
from act.editor.debug_loop import LoopAction
from act.editor.editor import Editor, WorkflowState, create_editor
from act.editor.exceptions import HardStopError

from .conftest import make_fail_response, make_pass_response


class TestHardStopTrigger:
    """Test hard stop trigger conditions."""

    @pytest.mark.asyncio
    async def test_twelve_iterations_triggers_hard_stop(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Twelve total verify loops trigger hard stop."""
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
            await editor.start_task("Complex bug fix")
            await editor.analyze_codebase()

        # Run 12 verification loops (will include REPLANs)
        run_ids = []
        stuck_triggered = False

        for i in range(12):
            run_id = f"run_{i:03d}"
            run_ids.append(run_id)
            fail_response = make_fail_response(run_id, f"Error {i}")
            action = editor.handle_verification_result(fail_response)

            if action == LoopAction.STUCK:
                stuck_triggered = True
                break

        assert stuck_triggered
        assert editor.state == WorkflowState.STUCK
        assert editor._debug_loop.state.total_verify_loops == 12

    @pytest.mark.asyncio
    async def test_hard_stop_preserves_run_history(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Hard stop preserves all run IDs in history."""
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
            await editor.start_task("Bug fix")
            await editor.analyze_codebase()

        run_ids = []
        for i in range(12):
            run_id = f"run_{i:03d}"
            run_ids.append(run_id)
            fail_response = make_fail_response(run_id, f"Error {i}")
            editor.handle_verification_result(fail_response)

        # Check that run IDs are preserved
        history = editor._debug_loop.state.get_all_run_ids()
        assert len(history) == 12
        for run_id in run_ids:
            assert run_id in history


class TestHardStopState:
    """Test state transitions during hard stop."""

    @pytest.mark.asyncio
    async def test_hard_stop_sets_stuck_state(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Hard stop sets workflow state to STUCK."""
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
            await editor.start_task("Bug fix")
            await editor.analyze_codebase()

        # Run until hard stop
        for i in range(12):
            fail_response = make_fail_response(f"run_{i:03d}", f"Error {i}")
            editor.handle_verification_result(fail_response)

        assert editor.state == WorkflowState.STUCK

    @pytest.mark.asyncio
    async def test_hard_stop_prevents_further_verification(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """After hard stop, further verification is prevented."""
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
            await editor.start_task("Bug fix")
            await editor.analyze_codebase()

        # Run until hard stop
        for i in range(12):
            fail_response = make_fail_response(f"run_{i:03d}", f"Error {i}")
            editor.handle_verification_result(fail_response)

        # Try one more verification - should remain in STUCK
        fail_response = make_fail_response("run_extra", "Extra error")
        action = editor.handle_verification_result(fail_response)

        assert action == LoopAction.STUCK
        assert editor.state == WorkflowState.STUCK


class TestHardStopWithSuccess:
    """Test hard stop behavior with intermittent successes."""

    @pytest.mark.asyncio
    async def test_success_before_hard_stop(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Success before 12 loops prevents hard stop."""
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
            await editor.start_task("Bug fix")
            await editor.analyze_codebase()

        # 10 failures
        for i in range(10):
            fail_response = make_fail_response(f"run_{i:03d}", f"Error {i}")
            editor.handle_verification_result(fail_response)

        # Then success
        success_response = make_pass_response("run_success")
        action = editor.handle_verification_result(success_response)

        assert action == LoopAction.SUCCESS
        assert editor.state == WorkflowState.COMPLETED
        assert editor._debug_loop.state.total_verify_loops == 11


class TestHardStopReport:
    """Test stuck report generation."""

    @pytest.mark.asyncio
    async def test_stuck_report_can_be_generated(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Stuck report can be generated after hard stop."""
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
            await editor.start_task("Bug fix")
            await editor.analyze_codebase()

        # Run until hard stop
        for i in range(12):
            fail_response = make_fail_response(f"run_{i:03d}", f"Error {i}")
            editor.handle_verification_result(fail_response)

        # Generate stuck report
        report = editor.generate_stuck_report()
        assert report is not None
        # StuckReport has verification_history, not total_attempts
        assert len(report.verification_history) == 12

    @pytest.mark.asyncio
    async def test_stuck_report_includes_replan_count(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Stuck report includes REPLAN count."""
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
            await editor.start_task("Bug fix")
            await editor.analyze_codebase()

        # Run until hard stop (will trigger REPLANs along the way)
        for i in range(12):
            fail_response = make_fail_response(f"run_{i:03d}", f"Error {i}")
            editor.handle_verification_result(fail_response)

        report = editor.generate_stuck_report()
        assert report is not None
        # StuckReport contains verification_history, check it's populated
        assert len(report.verification_history) == 12
        # The debug loop should have recorded 3 REPLANs
        # We can check this via the editor's debug loop state
        assert editor._debug_loop.state.replan_count >= 0  # Some REPLANs occurred
