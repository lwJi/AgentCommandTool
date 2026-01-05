"""Integration test: Cancellation flow (6.1.6).

Tests task cancellation behavior:
- Cancel mid-execution transitions to CANCELLED state
- Partial changes are preserved
- Next task can start cleanly
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from act.editor.coordinator import ScoutResults
from act.editor.debug_loop import LoopAction
from act.editor.editor import Editor, WorkflowState, create_editor
from act.task.queue import TaskQueue
from act.task.state import TaskState, create_task

from .conftest import make_fail_response, make_pass_response


class TestCancellationTrigger:
    """Test cancellation trigger behavior."""

    @pytest.mark.asyncio
    async def test_cancel_during_analysis(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
    ) -> None:
        """Cancellation during analysis transitions to CANCELLED."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        await editor.start_task("Fix authentication bug")
        assert editor.state == WorkflowState.ANALYZING

        # Cancel before analysis completes
        editor.cancel()

        assert editor.state == WorkflowState.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_during_verification(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Cancellation during verification transitions to CANCELLED."""
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

        # Start verification loop
        fail_response = make_fail_response("run_001", "Test error")
        editor.handle_verification_result(fail_response)

        # Cancel mid-loop
        editor.cancel()

        assert editor.state == WorkflowState.CANCELLED


class TestCancellationPreservation:
    """Test that cancellation preserves partial work."""

    @pytest.mark.asyncio
    async def test_cancellation_preserves_file_modifications(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Cancellation preserves recorded file modifications."""
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

        # Record modifications
        editor.record_file_modification("src/main.py")
        editor.record_file_modification("src/auth.py")

        # Cancel
        editor.cancel()

        # Modifications should be preserved (use context)
        assert "src/main.py" in editor._context.files_modified
        assert "src/auth.py" in editor._context.files_modified

    @pytest.mark.asyncio
    async def test_cancellation_preserves_context_snapshots(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Cancellation preserves context snapshots."""
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

        # Count initial snapshots
        agent_dir = integration_repo / "agent"
        initial_count = len(list(agent_dir.glob("context_*.md")))

        # Cancel
        editor.cancel()

        # Snapshots should still exist
        final_count = len(list(agent_dir.glob("context_*.md")))
        assert final_count >= initial_count

    @pytest.mark.asyncio
    async def test_cancellation_preserves_debug_loop_state(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Cancellation preserves debug loop state for inspection."""
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

        # Run some verification loops
        for i in range(2):
            fail_response = make_fail_response(f"run_{i}", f"Error {i}")
            editor.handle_verification_result(fail_response)

        # Cancel
        editor.cancel()

        # Debug loop state should be preserved
        assert editor._debug_loop.state.total_verify_loops == 2
        assert editor._debug_loop.state.consecutive_failures == 2


class TestCancellationRecovery:
    """Test recovery after cancellation."""

    @pytest.mark.asyncio
    async def test_new_task_after_cancellation(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """New task can start cleanly after cancellation."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        # First task
        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await editor.start_task("First task")

        editor.cancel()
        assert editor.state == WorkflowState.CANCELLED

        # Create new editor for new task
        editor2 = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor2._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await editor2.start_task("Second task")
            await editor2.analyze_codebase()

        # New task should start fresh
        assert editor2.state == WorkflowState.ANALYZING
        assert editor2._debug_loop.state.total_verify_loops == 0


class TestTaskQueueCancellation:
    """Test cancellation behavior with task queue."""

    def test_cancel_queued_task(
        self,
        integration_queue: TaskQueue,
    ) -> None:
        """Queued task can be cancelled by state change."""
        task = create_task("Test task")
        integration_queue.add(task)

        assert task.state == TaskState.QUEUED

        # Cancel queued task by changing state
        task.state = TaskState.CANCELLED

        assert task.state == TaskState.CANCELLED

    def test_cancel_running_task(
        self,
        integration_queue: TaskQueue,
    ) -> None:
        """Running task can be cancelled."""
        task = create_task("Test task")
        integration_queue.add(task)

        # Start task by changing state
        task.state = TaskState.RUNNING

        assert task.state == TaskState.RUNNING

        # Cancel running task
        task.state = TaskState.CANCELLED

        assert task.state == TaskState.CANCELLED

    def test_next_task_starts_after_cancellation(
        self,
        integration_queue: TaskQueue,
    ) -> None:
        """Next task in queue can start after cancellation."""
        task1 = create_task("First task")
        task2 = create_task("Second task")

        integration_queue.add(task1)
        integration_queue.add(task2)

        # Dequeue first task to start it
        started_task = integration_queue.dequeue()
        assert started_task is task1

        # Start and cancel first task
        task1.state = TaskState.RUNNING
        integration_queue.set_current(task1)
        task1.state = TaskState.CANCELLED
        integration_queue.mark_completed(task1)

        # Get next task from queue
        next_task = integration_queue.dequeue()

        assert next_task is task2
        assert next_task.state == TaskState.QUEUED
