"""Integration test: INFRA_ERROR from Scout (6.1.5).

Tests infrastructure errors from scout queries:
- LLM blocked/unavailable triggers INFRA_ERROR
- State transitions correctly
- InfrastructureError raised with source="scout_a" or "scout_b"
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from act.editor.coordinator import ScoutResults
from act.editor.editor import Editor, WorkflowState, create_editor
from act.editor.exceptions import InfrastructureError


class TestScoutInfraError:
    """Test INFRA_ERROR from scout queries."""

    @pytest.mark.asyncio
    async def test_scout_a_llm_error_triggers_infra_error(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
    ) -> None:
        """Scout A LLM error triggers INFRA_ERROR state."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.side_effect = InfrastructureError(
                message="LLM API unavailable",
                source="scout_a",
            )

            await editor.start_task("Fix authentication bug")

            with pytest.raises(InfrastructureError) as exc_info:
                await editor.analyze_codebase()

            assert exc_info.value.source == "scout_a"

    @pytest.mark.asyncio
    async def test_scout_b_llm_error_triggers_infra_error(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
    ) -> None:
        """Scout B LLM error triggers INFRA_ERROR state."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.side_effect = InfrastructureError(
                message="Rate limit exceeded",
                source="scout_b",
            )

            await editor.start_task("Fix bug")

            with pytest.raises(InfrastructureError) as exc_info:
                await editor.analyze_codebase()

            assert exc_info.value.source == "scout_b"

    @pytest.mark.asyncio
    async def test_scout_api_timeout_triggers_infra_error(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
    ) -> None:
        """Scout API timeout triggers INFRA_ERROR."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.side_effect = InfrastructureError(
                message="API request timed out after 60s",
                source="scout_a",
            )

            await editor.start_task("Fix bug")

            with pytest.raises(InfrastructureError) as exc_info:
                await editor.analyze_codebase()

            assert "timed out" in str(exc_info.value)


class TestScoutInfraErrorRecovery:
    """Test recovery scenarios from scout errors."""

    @pytest.mark.asyncio
    async def test_scout_error_preserves_task_state(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
    ) -> None:
        """Scout error preserves task description."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        task_description = "Fix authentication bug in login flow"

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.side_effect = InfrastructureError(
                message="LLM API unavailable",
                source="scout_a",
            )

            await editor.start_task(task_description)

            try:
                await editor.analyze_codebase()
            except InfrastructureError:
                pass

        # Task description should be preserved
        assert editor._context.task is not None
        assert editor._context.task.raw_description == task_description

    @pytest.mark.asyncio
    async def test_scout_error_allows_retry(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Scout error allows retry after recovery."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        call_count = 0

        async def mock_analysis_fn(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise InfrastructureError(
                    message="Temporary LLM error",
                    source="scout_a",
                )
            return mock_scout_results

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.side_effect = mock_analysis_fn

            await editor.start_task("Fix bug")

            # First attempt fails
            with pytest.raises(InfrastructureError):
                await editor.analyze_codebase()

            # Retry succeeds
            await editor.analyze_codebase()
            assert call_count == 2


class TestScoutInfraErrorDetails:
    """Test INFRA_ERROR detail preservation."""

    @pytest.mark.asyncio
    async def test_infrastructure_error_has_source(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
    ) -> None:
        """InfrastructureError includes source component."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.side_effect = InfrastructureError(
                message="API error",
                source="scout_a",
            )

            await editor.start_task("Fix bug")

            with pytest.raises(InfrastructureError) as exc_info:
                await editor.analyze_codebase()

            error = exc_info.value
            assert hasattr(error, "source")
            assert error.source == "scout_a"

    @pytest.mark.asyncio
    async def test_infrastructure_error_has_message(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
    ) -> None:
        """InfrastructureError includes detailed message."""
        editor = create_editor(
            repo_root=integration_repo,
            agent_config=mock_agent_config,
            llm_config=mock_llm_config,
            env_config=mock_env_config,
        )

        error_message = "Authentication failed: Invalid API key"

        with patch.object(
            editor._coordinator, "initial_analysis", new_callable=AsyncMock
        ) as mock_analysis:
            mock_analysis.side_effect = InfrastructureError(
                message=error_message,
                source="scout_b",
            )

            await editor.start_task("Fix bug")

            with pytest.raises(InfrastructureError) as exc_info:
                await editor.analyze_codebase()

            assert error_message in str(exc_info.value)
