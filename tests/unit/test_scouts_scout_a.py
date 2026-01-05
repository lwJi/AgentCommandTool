"""Unit tests for Scout A (Codebase Mapper)."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from act.config.env import LLMBackend, LLMConfig
from act.scouts.schemas import SCHEMA_VERSION, ScoutAResponse
from act.scouts.scout_a import (
    MAX_FILE_CONTENT_SIZE,
    MAX_FILES_IN_CONTEXT,
    SCOUT_A_SYSTEM_PROMPT,
    ScoutA,
    create_scout_a,
)


class TestScoutAConstants:
    """Tests for Scout A constants."""

    def test_max_files_in_context(self) -> None:
        """Test MAX_FILES_IN_CONTEXT is reasonable."""
        assert MAX_FILES_IN_CONTEXT > 0
        assert MAX_FILES_IN_CONTEXT <= 1000

    def test_max_file_content_size(self) -> None:
        """Test MAX_FILE_CONTENT_SIZE is reasonable."""
        assert MAX_FILE_CONTENT_SIZE > 0
        assert MAX_FILE_CONTENT_SIZE <= 100000

    def test_system_prompt_contains_schema_version(self) -> None:
        """Test system prompt contains schema version."""
        assert SCHEMA_VERSION in SCOUT_A_SYSTEM_PROMPT

    def test_system_prompt_contains_key_instructions(self) -> None:
        """Test system prompt contains key instructions."""
        assert "read-only" in SCOUT_A_SYSTEM_PROMPT.lower()
        assert "json" in SCOUT_A_SYSTEM_PROMPT.lower()
        assert "repo_map" in SCOUT_A_SYSTEM_PROMPT
        assert "risk_zones" in SCOUT_A_SYSTEM_PROMPT


class TestScoutAInit:
    """Tests for Scout A initialization."""

    def test_init_with_config(self) -> None:
        """Test Scout A initialization."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config)
        assert scout.llm_client is not None
        assert scout._conversation_history == []

    def test_init_with_custom_timeout(self) -> None:
        """Test initialization with custom timeout."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config, timeout_seconds=120.0)
        assert scout.llm_client.timeout_seconds == 120.0

    def test_init_with_custom_retries(self) -> None:
        """Test initialization with custom retries."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config, max_retries=5)
        assert scout.llm_client.retry_config.max_retries == 5


class TestScoutAResetContext:
    """Tests for Scout A context reset."""

    def test_reset_clears_history(self) -> None:
        """Test that reset_context clears conversation history."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config)

        # Add some mock history
        from act.scouts.llm_client import LLMMessage

        scout._conversation_history = [
            LLMMessage(role="user", content="test"),
            LLMMessage(role="assistant", content="response"),
        ]

        scout.reset_context()
        assert scout._conversation_history == []


class TestScoutAQuery:
    """Tests for Scout A query method."""

    @pytest.mark.asyncio
    async def test_query_returns_scout_a_response(self) -> None:
        """Test that query returns ScoutAResponse."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "repo_map": {
                "relevant_files": [
                    {"path": "main.py", "purpose": "Entry point", "relevance": "primary"}
                ],
                "entry_points": ["main.py"],
                "dependency_graph": {},
            },
            "risk_zones": [],
            "change_boundaries": {"safe_slices": [], "ordering_constraints": []},
            "conventions": {"naming": "snake_case", "patterns": [], "anti_patterns": []},
            "prior_art": [],
            "verification_tips": [],
            "hypotheses": [],
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                Path(tmpdir, "main.py").write_text("print('hello')")

                response = await scout.query(
                    "What files are important?",
                    tmpdir,
                )

        assert isinstance(response, ScoutAResponse)
        assert response.schema_version == SCHEMA_VERSION
        assert len(response.repo_map.relevant_files) == 1

    @pytest.mark.asyncio
    async def test_query_adds_to_conversation_history(self) -> None:
        """Test that queries are added to conversation history."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "repo_map": {},
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                await scout.query("Test question", tmpdir, include_file_list=False)

        # Should have user message and assistant response
        assert len(scout._conversation_history) == 2
        assert scout._conversation_history[0].role == "user"
        assert scout._conversation_history[1].role == "assistant"


class TestScoutAAnalyzeFiles:
    """Tests for Scout A analyze_files method."""

    @pytest.mark.asyncio
    async def test_analyze_files_with_content(self) -> None:
        """Test analyzing specific files with content."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "repo_map": {},
            "risk_zones": [
                {
                    "file": "auth.py",
                    "start_line": 10,
                    "end_line": 50,
                    "risk_level": "high",
                    "complexity": "medium",
                }
            ],
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                file_contents = {
                    "auth.py": "def authenticate(user): pass",
                    "utils.py": "def helper(): pass",
                }

                response = await scout.analyze_files(
                    "Analyze risk zones",
                    tmpdir,
                    file_contents,
                )

        assert isinstance(response, ScoutAResponse)
        assert len(response.risk_zones) == 1


class TestScoutAFindRelevantFiles:
    """Tests for Scout A find_relevant_files method."""

    @pytest.mark.asyncio
    async def test_find_relevant_files(self) -> None:
        """Test finding relevant files for a task."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "repo_map": {
                "relevant_files": [
                    {"path": "auth.py", "purpose": "Authentication", "relevance": "primary"},
                    {"path": "db.py", "purpose": "Database", "relevance": "secondary"},
                ],
            },
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                response = await scout.find_relevant_files(
                    "Fix login bug",
                    tmpdir,
                )

        assert len(response.repo_map.relevant_files) == 2


class TestScoutAIdentifyConventions:
    """Tests for Scout A identify_conventions method."""

    @pytest.mark.asyncio
    async def test_identify_conventions(self) -> None:
        """Test identifying code conventions."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "repo_map": {},
            "conventions": {
                "naming": "camelCase for functions, PascalCase for classes",
                "patterns": ["Factory pattern", "Dependency injection"],
                "anti_patterns": ["Global state", "Circular imports"],
            },
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                response = await scout.identify_conventions(tmpdir)

        assert "camelCase" in response.conventions.naming
        assert len(response.conventions.patterns) == 2


class TestScoutAGetRawResponse:
    """Tests for Scout A get_raw_response method."""

    @pytest.mark.asyncio
    async def test_get_raw_response_after_query(self) -> None:
        """Test getting raw response after query."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "repo_map": {},
            "extra_field": "should be preserved",
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                await scout.query("Test", tmpdir, include_file_list=False)

        raw = scout.get_raw_response()
        assert raw is not None
        assert raw["extra_field"] == "should be preserved"

    def test_get_raw_response_no_queries(self) -> None:
        """Test getting raw response with no queries."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutA(config)

        assert scout.get_raw_response() is None


class TestCreateScoutA:
    """Tests for create_scout_a factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating Scout A with defaults."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = create_scout_a(config)

        assert isinstance(scout, ScoutA)
        assert scout.llm_client.timeout_seconds == 60.0

    def test_create_with_custom_settings(self) -> None:
        """Test creating Scout A with custom settings."""
        config = LLMConfig(
            backend=LLMBackend.OPENAI,
            api_key="test-key",
        )
        scout = create_scout_a(config, timeout_seconds=120.0, max_retries=5)

        assert scout.llm_client.timeout_seconds == 120.0
        assert scout.llm_client.retry_config.max_retries == 5
