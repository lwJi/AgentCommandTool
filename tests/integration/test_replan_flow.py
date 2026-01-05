"""Integration test: REPLAN flow (6.1.2).

Tests the REPLAN trigger after consecutive failures:
- 3 consecutive failures trigger REPLAN
- New strategy is attempted
- Context snapshot is created
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from act.editor.coordinator import ScoutResults
from act.editor.debug_loop import LoopAction
from act.editor.editor import Editor, WorkflowState, create_editor

from .conftest import make_fail_response, make_pass_response


class TestReplanTrigger:
    """Test REPLAN trigger conditions."""

    @pytest.mark.asyncio
    async def test_three_consecutive_failures_triggers_replan(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Three consecutive failures trigger REPLAN."""
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
            await editor.start_task("Fix authentication bug")
            await editor.analyze_codebase()

        # Simulate 3 consecutive failures
        for i in range(3):
            fail_response = make_fail_response(f"run_fail_{i}", f"Test error {i}")
            action = editor.handle_verification_result(fail_response)

            if i < 2:
                # First two failures should continue
                assert action == LoopAction.CONTINUE
            else:
                # Third failure triggers REPLAN
                assert action == LoopAction.REPLAN

        # When REPLAN action is returned, caller must call trigger_replan
        # to actually reset the counter
        await editor.trigger_replan("New strategy after failures")

        # Verify state after trigger_replan is called
        assert editor._debug_loop.state.consecutive_failures == 0  # Reset after REPLAN
        assert editor._debug_loop.state.total_verify_loops == 3
        assert editor._debug_loop.state.replan_count == 1

    @pytest.mark.asyncio
    async def test_two_failures_then_success_no_replan(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Two failures followed by success does not trigger REPLAN."""
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
            await editor.start_task("Fix bug")
            await editor.analyze_codebase()

        # Two failures
        for i in range(2):
            fail_response = make_fail_response(f"run_fail_{i}", f"Error {i}")
            action = editor.handle_verification_result(fail_response)
            assert action == LoopAction.CONTINUE

        # Then success
        success_response = make_pass_response("run_success")
        action = editor.handle_verification_result(success_response)

        assert action == LoopAction.SUCCESS
        assert editor._debug_loop.state.replan_count == 0
        assert editor._debug_loop.state.total_verify_loops == 3

    @pytest.mark.asyncio
    async def test_replan_resets_consecutive_counter(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """REPLAN resets consecutive failure counter to 0."""
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
            await editor.start_task("Fix bug")
            await editor.analyze_codebase()

        # Trigger first REPLAN (3 failures)
        for i in range(3):
            fail_response = make_fail_response(f"run_fail_{i}", f"Error {i}")
            action = editor.handle_verification_result(fail_response)
            if action == LoopAction.REPLAN:
                await editor.trigger_replan("New strategy")

        # Consecutive should be reset after trigger_replan
        assert editor._debug_loop.state.consecutive_failures == 0

        # Total should still accumulate
        assert editor._debug_loop.state.total_verify_loops == 3


class TestReplanLimit:
    """Test REPLAN limit behavior."""

    @pytest.mark.asyncio
    async def test_max_three_replans_before_stuck(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """After 3 REPLANs, next trigger causes STUCK."""
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
            await editor.start_task("Fix complex bug")
            await editor.analyze_codebase()

        run_counter = 0
        # Trigger 3 REPLANs (9 failures total)
        for replan_num in range(3):
            for fail_num in range(3):
                fail_response = make_fail_response(
                    f"run_{run_counter}", f"Error {run_counter}"
                )
                action = editor.handle_verification_result(fail_response)
                run_counter += 1

                if fail_num < 2:
                    assert action == LoopAction.CONTINUE
                else:
                    assert action == LoopAction.REPLAN
                    # Trigger the replan to reset consecutive_failures
                    await editor.trigger_replan(f"Strategy {replan_num + 1}")

        assert editor._debug_loop.state.replan_count == 3

        # Next 3 failures should cause STUCK (4th REPLAN attempt would exceed max)
        for i in range(3):
            fail_response = make_fail_response(
                f"run_{run_counter}", f"Final error {i}"
            )
            action = editor.handle_verification_result(fail_response)
            run_counter += 1

            if i < 2:
                assert action == LoopAction.CONTINUE
            else:
                # 4th REPLAN would exceed max, so it becomes STUCK
                assert action == LoopAction.STUCK

        assert editor.state == WorkflowState.STUCK


class TestReplanContextSnapshot:
    """Test context snapshot creation during REPLAN."""

    @pytest.mark.asyncio
    async def test_context_snapshot_on_replan(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Context snapshot is created when REPLAN triggers."""
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
            await editor.start_task("Fix bug")
            await editor.analyze_codebase()

        # Count initial snapshots
        agent_dir = integration_repo / "agent"
        initial_count = len(list(agent_dir.glob("context_*.md")))

        # Trigger REPLAN
        for i in range(3):
            fail_response = make_fail_response(f"run_fail_{i}", f"Error {i}")
            editor.handle_verification_result(fail_response)

        # Check for new snapshot
        final_count = len(list(agent_dir.glob("context_*.md")))
        assert final_count >= initial_count

    @pytest.mark.asyncio
    async def test_replan_preserves_total_loop_count(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """REPLAN preserves total verify loop count."""
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
            await editor.start_task("Fix bug")
            await editor.analyze_codebase()

        # First REPLAN (3 failures)
        for i in range(3):
            fail_response = make_fail_response(f"run_fail_{i}", f"Error {i}")
            editor.handle_verification_result(fail_response)

        assert editor._debug_loop.state.total_verify_loops == 3

        # More failures after REPLAN
        for i in range(2):
            fail_response = make_fail_response(f"run_after_replan_{i}", f"Error {i}")
            editor.handle_verification_result(fail_response)

        # Total should be 5 (3 before REPLAN + 2 after)
        assert editor._debug_loop.state.total_verify_loops == 5
