"""Integration test: INFRA_ERROR from Verifier (6.1.4).

Tests infrastructure errors from the verifier:
- Docker failure triggers INFRA_ERROR
- State transitions correctly
- InfrastructureError raised with source="verifier"
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from act.editor.coordinator import ScoutResults
from act.editor.debug_loop import LoopAction
from act.editor.editor import Editor, WorkflowState, create_editor
from act.editor.exceptions import InfrastructureError
from act.verifier.exceptions import InfraErrorType

from .conftest import make_fail_response, make_infra_error_response, make_pass_response


class TestVerifierInfraError:
    """Test INFRA_ERROR from verifier."""

    @pytest.mark.asyncio
    async def test_docker_unavailable_triggers_infra_error(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Docker unavailable triggers INFRA_ERROR state."""
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

        # Simulate Docker unavailable error
        infra_response = make_infra_error_response(
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_msg="Docker daemon is not running",
        )
        action = editor.handle_verification_result(infra_response)

        assert action == LoopAction.INFRA_ERROR
        assert editor.state == WorkflowState.INFRA_ERROR

    @pytest.mark.asyncio
    async def test_container_build_failure_triggers_infra_error(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Container build failure triggers INFRA_ERROR state."""
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

        # Simulate container creation error
        infra_response = make_infra_error_response(
            error_type=InfraErrorType.CONTAINER_CREATION,
            error_msg="Failed to create container",
        )
        action = editor.handle_verification_result(infra_response)

        assert action == LoopAction.INFRA_ERROR
        assert editor.state == WorkflowState.INFRA_ERROR

    @pytest.mark.asyncio
    async def test_resource_exhaustion_triggers_infra_error(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """Resource exhaustion triggers INFRA_ERROR state."""
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

        # Simulate resource exhaustion error
        infra_response = make_infra_error_response(
            error_type=InfraErrorType.RESOURCE_EXHAUSTION,
            error_msg="Out of disk space",
            run_id="run_resource_error",
        )
        action = editor.handle_verification_result(infra_response)

        assert action == LoopAction.INFRA_ERROR
        assert editor.state == WorkflowState.INFRA_ERROR


class TestVerifierInfraErrorState:
    """Test state behavior after INFRA_ERROR."""

    @pytest.mark.asyncio
    async def test_infra_error_prevents_further_operations(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """INFRA_ERROR state prevents further verification."""
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

        # Trigger INFRA_ERROR
        infra_response = make_infra_error_response(
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_msg="Docker not available",
        )
        editor.handle_verification_result(infra_response)

        # Try another verification - should remain in INFRA_ERROR
        pass_response = make_pass_response("run_after_infra")
        action = editor.handle_verification_result(pass_response)

        assert action == LoopAction.INFRA_ERROR
        assert editor.state == WorkflowState.INFRA_ERROR

    @pytest.mark.asyncio
    async def test_infra_error_does_not_count_as_failure(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """INFRA_ERROR does not increment failure counters."""
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

        # Some failures first
        fail_response = make_fail_response("run_fail", "Test error")
        editor.handle_verification_result(fail_response)

        initial_failures = editor._debug_loop.state.consecutive_failures
        initial_loops = editor._debug_loop.state.total_verify_loops

        # Trigger INFRA_ERROR
        infra_response = make_infra_error_response(
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_msg="Docker not available",
        )
        editor.handle_verification_result(infra_response)

        # Counters should not have changed
        assert editor._debug_loop.state.consecutive_failures == initial_failures
        assert editor._debug_loop.state.total_verify_loops == initial_loops


class TestVerifierInfraErrorRecovery:
    """Test INFRA_ERROR recovery scenarios."""

    @pytest.mark.asyncio
    async def test_infra_error_preserves_work_done(
        self,
        integration_repo: Path,
        mock_agent_config: MagicMock,
        mock_llm_config: MagicMock,
        mock_env_config: MagicMock,
        mock_scout_results: ScoutResults,
    ) -> None:
        """INFRA_ERROR preserves work done before error."""
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

        # Record some modifications
        editor.record_file_modification("src/main.py")
        editor.record_file_modification("src/utils.py")

        # Trigger INFRA_ERROR
        infra_response = make_infra_error_response(
            error_type=InfraErrorType.DOCKER_UNAVAILABLE,
            error_msg="Docker not available",
        )
        editor.handle_verification_result(infra_response)

        # Work should be preserved
        assert "src/main.py" in editor._context.files_modified
        assert "src/utils.py" in editor._context.files_modified
