"""Unit tests for Editor Scout coordination."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from act.config.env import LLMBackend, LLMConfig
from act.editor.coordinator import (
    ScoutCoordinator,
    ScoutResults,
    create_scout_coordinator,
)
from act.editor.exceptions import InfrastructureError, ScoutCoordinationError
from act.scouts import RetryExhaustedError, ScoutAResponse, ScoutBResponse, ScoutError


# Mock LLM config for testing
@pytest.fixture
def mock_llm_config() -> LLMConfig:
    """Create a mock LLM config."""
    return LLMConfig(
        backend=LLMBackend.ANTHROPIC,
        api_key="test-key",
        model="test-model",
    )


class TestScoutResults:
    """Tests for ScoutResults dataclass."""

    def test_empty_results(self) -> None:
        """Test empty results."""
        results = ScoutResults()
        assert results.scout_a_response is None
        assert results.scout_b_response is None
        assert not results.has_scout_a()
        assert not results.has_scout_b()

    def test_with_scout_a_response(self) -> None:
        """Test results with Scout A response."""
        mock_response = MagicMock(spec=ScoutAResponse)
        results = ScoutResults(scout_a_response=mock_response)
        assert results.has_scout_a()
        assert not results.has_scout_b()

    def test_with_scout_b_response(self) -> None:
        """Test results with Scout B response."""
        mock_response = MagicMock(spec=ScoutBResponse)
        results = ScoutResults(scout_b_response=mock_response)
        assert results.has_scout_b()
        assert not results.has_scout_a()

    def test_to_dict_empty(self) -> None:
        """Test to_dict with empty results."""
        results = ScoutResults()
        d = results.to_dict()
        assert d == {}

    def test_to_dict_with_responses(self) -> None:
        """Test to_dict with responses."""
        mock_a = MagicMock(spec=ScoutAResponse)
        mock_a.to_dict.return_value = {"type": "scout_a"}
        mock_b = MagicMock(spec=ScoutBResponse)
        mock_b.to_dict.return_value = {"type": "scout_b"}

        results = ScoutResults(
            scout_a_response=mock_a,
            scout_b_response=mock_b,
            conflict_resolution="Chose Scout A",
        )
        d = results.to_dict()

        assert "scout_a" in d
        assert "scout_b" in d
        assert d["conflict_resolution"] == "Chose Scout A"


class TestScoutCoordinator:
    """Tests for ScoutCoordinator class."""

    def test_initialization(self, mock_llm_config: LLMConfig, tmp_path: Path) -> None:
        """Test coordinator initialization."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)
        assert coordinator.repo_root == tmp_path
        assert coordinator.llm_config == mock_llm_config

    def test_reset(self, mock_llm_config: LLMConfig, tmp_path: Path) -> None:
        """Test coordinator reset."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)
        # Mock some state
        coordinator._last_results = ScoutResults()

        coordinator.reset()

        assert coordinator._last_results is None

    @pytest.mark.asyncio
    async def test_query_scout_a(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test querying Scout A only."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        mock_response = MagicMock(spec=ScoutAResponse)
        coordinator._scout_a.query = AsyncMock(return_value=mock_response)
        coordinator._scout_a.get_raw_response = MagicMock(return_value={"test": True})

        results = await coordinator.query_scout_a("Test question")

        assert results.has_scout_a()
        assert not results.has_scout_b()
        assert results.scout_a_raw == {"test": True}

    @pytest.mark.asyncio
    async def test_query_scout_a_with_file_contents(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test querying Scout A with file contents."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        mock_response = MagicMock(spec=ScoutAResponse)
        coordinator._scout_a.analyze_files = AsyncMock(return_value=mock_response)
        coordinator._scout_a.get_raw_response = MagicMock(return_value={})

        results = await coordinator.query_scout_a(
            "Test question",
            file_contents={"test.py": "content"},
        )

        assert results.has_scout_a()
        coordinator._scout_a.analyze_files.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_scout_b(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test querying Scout B only."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        mock_response = MagicMock(spec=ScoutBResponse)
        coordinator._scout_b.query = AsyncMock(return_value=mock_response)
        coordinator._scout_b.get_raw_response = MagicMock(return_value={"test": True})

        results = await coordinator.query_scout_b("Test question")

        assert results.has_scout_b()
        assert not results.has_scout_a()

    @pytest.mark.asyncio
    async def test_query_scouts_parallel(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test querying both scouts in parallel."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        mock_a_response = MagicMock(spec=ScoutAResponse)
        mock_b_response = MagicMock(spec=ScoutBResponse)

        coordinator._scout_a.query = AsyncMock(return_value=mock_a_response)
        coordinator._scout_a.get_raw_response = MagicMock(return_value={})
        coordinator._scout_b.query = AsyncMock(return_value=mock_b_response)
        coordinator._scout_b.get_raw_response = MagicMock(return_value={})

        results = await coordinator.query_scouts_parallel(
            "Scout A question",
            "Scout B question",
        )

        assert results.has_scout_a()
        assert results.has_scout_b()

    @pytest.mark.asyncio
    async def test_scout_a_retry_exhausted_raises_infra_error(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test that Scout A retry exhaustion raises InfrastructureError."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        coordinator._scout_a.query = AsyncMock(
            side_effect=RetryExhaustedError("Exhausted", 3)
        )

        with pytest.raises(InfrastructureError) as exc_info:
            await coordinator.query_scout_a("Test")

        assert exc_info.value.source == "scout_a"

    @pytest.mark.asyncio
    async def test_scout_b_retry_exhausted_raises_infra_error(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test that Scout B retry exhaustion raises InfrastructureError."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        coordinator._scout_b.query = AsyncMock(
            side_effect=RetryExhaustedError("Exhausted", 3)
        )

        with pytest.raises(InfrastructureError) as exc_info:
            await coordinator.query_scout_b("Test")

        assert exc_info.value.source == "scout_b"

    @pytest.mark.asyncio
    async def test_scout_error_raises_coordination_error(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test that Scout errors raise ScoutCoordinationError."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        coordinator._scout_a.query = AsyncMock(
            side_effect=ScoutError("Scout error")
        )

        with pytest.raises(ScoutCoordinationError) as exc_info:
            await coordinator.query_scout_a("Test")

        assert exc_info.value.scout_name == "Scout A"

    @pytest.mark.asyncio
    async def test_analyze_failure(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test analyze_failure method."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        mock_response = MagicMock(spec=ScoutBResponse)
        coordinator._scout_b.analyze_failure = AsyncMock(return_value=mock_response)
        coordinator._scout_b.get_raw_response = MagicMock(return_value={})

        results = await coordinator.analyze_failure("Error log content")

        assert results.has_scout_b()
        coordinator._scout_b.analyze_failure.assert_called_once_with(
            "Error log content", tmp_path
        )

    @pytest.mark.asyncio
    async def test_initial_analysis(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test initial_analysis method."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        mock_a_response = MagicMock(spec=ScoutAResponse)
        mock_b_response = MagicMock(spec=ScoutBResponse)

        coordinator._scout_a.query = AsyncMock(return_value=mock_a_response)
        coordinator._scout_a.get_raw_response = MagicMock(return_value={})
        coordinator._scout_b.query = AsyncMock(return_value=mock_b_response)
        coordinator._scout_b.get_raw_response = MagicMock(return_value={})

        results = await coordinator.initial_analysis("Fix the login bug")

        assert results.has_scout_a()
        assert results.has_scout_b()

    def test_resolve_conflict_test_context(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test conflict resolution in test context."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)
        coordinator._last_results = ScoutResults()

        resolution = coordinator.resolve_conflict(
            scout_a_suggestion="Change file A",
            scout_b_suggestion="Change file B",
            context="Test suite is failing",
        )

        # Should prefer Scout B for test context
        assert "file B" in resolution or "Scout B" in resolution

    def test_resolve_conflict_code_context(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test conflict resolution in code context."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)
        coordinator._last_results = ScoutResults()

        resolution = coordinator.resolve_conflict(
            scout_a_suggestion="Change file A",
            scout_b_suggestion="Change file B",
            context="Import structure needs update",
        )

        # Should prefer Scout A for code context
        assert "file A" in resolution or "Scout A" in resolution

    def test_get_last_results(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test getting last results."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        assert coordinator.get_last_results() is None

        coordinator._last_results = ScoutResults()
        assert coordinator.get_last_results() is not None

    def test_scout_properties(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test scout property access."""
        coordinator = ScoutCoordinator(mock_llm_config, tmp_path)

        assert coordinator.scout_a is coordinator._scout_a
        assert coordinator.scout_b is coordinator._scout_b


class TestCreateScoutCoordinator:
    """Tests for create_scout_coordinator factory."""

    def test_creates_coordinator(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test factory creates coordinator."""
        coordinator = create_scout_coordinator(mock_llm_config, tmp_path)
        assert coordinator.repo_root == tmp_path

    def test_custom_timeout(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test factory with custom timeout."""
        coordinator = create_scout_coordinator(
            mock_llm_config,
            tmp_path,
            timeout_seconds=120.0,
        )
        assert coordinator.timeout_seconds == 120.0

    def test_custom_retries(
        self, mock_llm_config: LLMConfig, tmp_path: Path
    ) -> None:
        """Test factory with custom retries."""
        coordinator = create_scout_coordinator(
            mock_llm_config,
            tmp_path,
            max_retries=5,
        )
        assert coordinator.max_retries == 5
