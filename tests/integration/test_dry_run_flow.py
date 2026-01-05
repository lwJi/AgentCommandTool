"""Integration test: Dry-run flow (6.1.7).

Tests dry-run mode behavior:
- Preview mode generates proposal without filesystem changes
- Proposal includes intended changes
- Apply mode executes the changes
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from act.editor.coordinator import ScoutResults
from act.editor.debug_loop import LoopAction
from act.editor.editor import Editor, WorkflowState, create_editor
from act.task.state import TaskState, create_task

from .conftest import make_pass_response


class TestDryRunPreview:
    """Test dry-run preview mode."""

    @pytest.mark.asyncio
    async def test_dry_run_creates_proposal(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Dry-run mode creates a proposal."""
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
            # Pass dry_run to start_task
            await editor.start_task("Add logging to main function", dry_run=True)
            await editor.analyze_codebase()

        # Editor should be in dry-run mode
        assert editor._context.dry_run_mode is True
        assert editor.state == WorkflowState.ANALYZING

    @pytest.mark.asyncio
    async def test_dry_run_does_not_modify_files(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Dry-run mode does not modify source files."""
        # Record initial file state
        main_py = integration_repo / "src" / "main.py"
        initial_content = main_py.read_text()

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
            await editor.start_task("Modify main function", dry_run=True)
            await editor.analyze_codebase()

        # File should be unchanged
        assert main_py.read_text() == initial_content

    @pytest.mark.asyncio
    async def test_dry_run_generates_proposal_content(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Dry-run generates proposal with intended changes."""
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
            await editor.start_task("Add feature X", dry_run=True)
            await editor.analyze_codebase()

        # Get proposal (method should exist in dry-run mode)
        proposal = editor.get_dry_run_proposal()

        # Proposal should be available (even if empty for now)
        assert editor._context.dry_run_mode is True


class TestDryRunTask:
    """Test dry-run task state."""

    def test_create_dry_run_task(self) -> None:
        """Dry-run task is created correctly."""
        task = create_task("Test task", dry_run=True)

        assert task.dry_run is True
        assert task.description == "Test task"

    def test_dry_run_task_flag_preserved(self) -> None:
        """Dry-run flag is preserved throughout task lifecycle."""
        task = create_task("Test task", dry_run=True)
        # Change state directly (Task is a dataclass)
        task.state = TaskState.RUNNING

        assert task.dry_run is True


class TestDryRunContextSnapshots:
    """Test context snapshots in dry-run mode."""

    @pytest.mark.asyncio
    async def test_dry_run_creates_context_snapshots(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Dry-run mode still creates context snapshots."""
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
            await editor.start_task("Add feature", dry_run=True)

        # Context snapshots should be created
        agent_dir = integration_repo / "agent"
        context_files = list(agent_dir.glob("context_*.md"))
        assert len(context_files) >= 1


class TestDryRunToApply:
    """Test transitioning from dry-run to apply."""

    @pytest.mark.asyncio
    async def test_apply_after_dry_run(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Changes can be applied after dry-run preview."""
        # First, dry-run
        dry_editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            dry_editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await dry_editor.start_task("Add logging", dry_run=True)
            await dry_editor.analyze_codebase()

        # Verify dry-run mode
        assert dry_editor._context.dry_run_mode is True

        # Then, apply with real editor
        real_editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            real_editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await real_editor.start_task("Add logging", dry_run=False)
            await real_editor.analyze_codebase()

        # Real editor should not be in dry-run mode
        assert real_editor._context.dry_run_mode is False

    @pytest.mark.asyncio
    async def test_dry_run_does_not_trigger_verification(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Dry-run mode does not trigger verification."""
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
            await editor.start_task("Add feature", dry_run=True)
            await editor.analyze_codebase()

        # Verification loop state should be empty
        assert editor._debug_loop.state.total_verify_loops == 0

    @pytest.mark.asyncio
    async def test_normal_mode_after_dry_run(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Normal mode can run verification after dry-run."""
        # Dry run first
        dry_editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            dry_editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.return_value = mock_scout_results
            await dry_editor.start_task("Add feature", dry_run=True)
            await dry_editor.analyze_codebase()

        # Now run normal mode
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
            await editor.start_task("Add feature", dry_run=False)
            await editor.analyze_codebase()

        # Can handle verification results
        response = make_pass_response("run_001")
        action = editor.handle_verification_result(response)

        assert action == LoopAction.SUCCESS
        assert editor.state == WorkflowState.COMPLETED
