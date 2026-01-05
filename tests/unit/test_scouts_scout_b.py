"""Unit tests for Scout B (Build/Test Detective)."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from act.config.env import LLMBackend, LLMConfig
from act.scouts.schemas import (
    SCHEMA_VERSION,
    BuildSystem,
    ScoutBResponse,
    TestFramework,
)
from act.scouts.scout_b import (
    BUILD_CONFIG_FILES,
    MAX_LOG_SIZE,
    SCOUT_B_SYSTEM_PROMPT,
    ScoutB,
    create_scout_b,
)


class TestScoutBConstants:
    """Tests for Scout B constants."""

    def test_build_config_files_list(self) -> None:
        """Test BUILD_CONFIG_FILES contains expected files."""
        assert "package.json" in BUILD_CONFIG_FILES
        assert "pyproject.toml" in BUILD_CONFIG_FILES
        assert "Cargo.toml" in BUILD_CONFIG_FILES
        assert "go.mod" in BUILD_CONFIG_FILES
        assert "Makefile" in BUILD_CONFIG_FILES

    def test_max_log_size(self) -> None:
        """Test MAX_LOG_SIZE is reasonable."""
        assert MAX_LOG_SIZE > 0
        assert MAX_LOG_SIZE <= 100000

    def test_system_prompt_contains_schema_version(self) -> None:
        """Test system prompt contains schema version."""
        assert SCHEMA_VERSION in SCOUT_B_SYSTEM_PROMPT

    def test_system_prompt_contains_key_instructions(self) -> None:
        """Test system prompt contains key instructions."""
        assert "read-only" in SCOUT_B_SYSTEM_PROMPT.lower()
        assert "json" in SCOUT_B_SYSTEM_PROMPT.lower()
        assert "build" in SCOUT_B_SYSTEM_PROMPT.lower()
        assert "test" in SCOUT_B_SYSTEM_PROMPT.lower()
        assert "failure_analysis" in SCOUT_B_SYSTEM_PROMPT


class TestScoutBInit:
    """Tests for Scout B initialization."""

    def test_init_with_config(self) -> None:
        """Test Scout B initialization."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)
        assert scout.llm_client is not None
        assert scout._conversation_history == []

    def test_init_with_custom_timeout(self) -> None:
        """Test initialization with custom timeout."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config, timeout_seconds=120.0)
        assert scout.llm_client.timeout_seconds == 120.0


class TestScoutBFindBuildConfigFiles:
    """Tests for Scout B _find_build_config_files method."""

    def test_finds_package_json(self) -> None:
        """Test finding package.json."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = Path(tmpdir, "package.json")
            package_json.write_text('{"name": "test"}')

            configs = scout._find_build_config_files(tmpdir)

        assert "package.json" in configs
        assert '"name": "test"' in configs["package.json"]

    def test_finds_pyproject_toml(self) -> None:
        """Test finding pyproject.toml."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir, "pyproject.toml")
            pyproject.write_text('[project]\nname = "test"')

            configs = scout._find_build_config_files(tmpdir)

        assert "pyproject.toml" in configs

    def test_finds_multiple_configs(self) -> None:
        """Test finding multiple config files."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "package.json").write_text("{}")
            Path(tmpdir, "jest.config.js").write_text("module.exports = {}")

            configs = scout._find_build_config_files(tmpdir)

        assert "package.json" in configs
        assert "jest.config.js" in configs

    def test_empty_directory(self) -> None:
        """Test with empty directory."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            configs = scout._find_build_config_files(tmpdir)

        assert configs == {}


class TestScoutBResetContext:
    """Tests for Scout B context reset."""

    def test_reset_clears_history(self) -> None:
        """Test that reset_context clears conversation history."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        from act.scouts.llm_client import LLMMessage

        scout._conversation_history = [
            LLMMessage(role="user", content="test"),
        ]

        scout.reset_context()
        assert scout._conversation_history == []


class TestScoutBQuery:
    """Tests for Scout B query method."""

    @pytest.mark.asyncio
    async def test_query_returns_scout_b_response(self) -> None:
        """Test that query returns ScoutBResponse."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "build": {
                "detected_system": "npm",
                "commands": {
                    "install": "npm install",
                    "build": "npm run build",
                },
            },
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                Path(tmpdir, "package.json").write_text("{}")

                response = await scout.query(
                    "How do I build this?",
                    tmpdir,
                )

        assert isinstance(response, ScoutBResponse)
        assert response.build is not None
        assert response.build.detected_system == BuildSystem.NPM

    @pytest.mark.asyncio
    async def test_query_with_log_content(self) -> None:
        """Test query with log content."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "failure_analysis": {
                "root_cause": "Test timeout",
                "affected_files": ["test.py"],
            },
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                response = await scout.query(
                    "What failed?",
                    tmpdir,
                    log_content="Error: Test timed out",
                )

        assert response.failure_analysis.root_cause == "Test timeout"


class TestScoutBDiscoverBuildCommands:
    """Tests for Scout B discover_build_commands method."""

    @pytest.mark.asyncio
    async def test_discover_build_commands(self) -> None:
        """Test discovering build commands."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "build": {
                "detected_system": "cargo",
                "commands": {
                    "install": None,
                    "build": "cargo build",
                    "clean": "cargo clean",
                },
                "prerequisites": ["Rust 1.70+"],
                "notes": "Uses Cargo",
            },
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                response = await scout.discover_build_commands(tmpdir)

        assert response.build is not None
        assert response.build.detected_system == BuildSystem.CARGO
        assert response.build.commands.build == "cargo build"


class TestScoutBDiscoverTestCommands:
    """Tests for Scout B discover_test_commands method."""

    @pytest.mark.asyncio
    async def test_discover_test_commands(self) -> None:
        """Test discovering test commands."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "test": {
                "detected_framework": "pytest",
                "commands": {
                    "all": "pytest",
                    "unit": "pytest tests/unit",
                    "integration": "pytest tests/integration",
                },
                "coverage_command": "pytest --cov",
            },
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                response = await scout.discover_test_commands(tmpdir)

        assert response.test is not None
        assert response.test.detected_framework == TestFramework.PYTEST
        assert response.test.commands.all == "pytest"


class TestScoutBAnalyzeFailure:
    """Tests for Scout B analyze_failure method."""

    @pytest.mark.asyncio
    async def test_analyze_failure(self) -> None:
        """Test analyzing a failure."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "failure_analysis": {
                "root_cause": "TypeError: Cannot read property 'x' of undefined",
                "affected_files": ["src/app.js", "src/utils.js"],
                "suggested_investigation": [
                    "Check null handling in app.js",
                    "Add defensive checks",
                ],
                "is_flaky": False,
            },
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                response = await scout.analyze_failure(
                    "TypeError: Cannot read property 'x' of undefined\n  at app.js:42",
                    tmpdir,
                )

        assert "TypeError" in response.failure_analysis.root_cause
        assert len(response.failure_analysis.affected_files) == 2

    @pytest.mark.asyncio
    async def test_analyze_flaky_failure(self) -> None:
        """Test analyzing a potentially flaky failure."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "failure_analysis": {
                "root_cause": "Network timeout",
                "affected_files": ["src/api.js"],
                "is_flaky": True,
                "flaky_reason": "Network-dependent test without mocking",
            },
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                response = await scout.analyze_failure(
                    "Error: ETIMEDOUT",
                    tmpdir,
                )

        assert response.failure_analysis.is_flaky is True
        assert response.failure_analysis.flaky_reason is not None


class TestScoutBDetectEnvironmentIssues:
    """Tests for Scout B detect_environment_issues method."""

    @pytest.mark.asyncio
    async def test_detect_environment_issues(self) -> None:
        """Test detecting environment issues."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "environment_issues": [
                {
                    "issue": "Node.js version too old",
                    "severity": "blocking",
                    "suggested_fix": "Upgrade to Node.js 18+",
                },
                {
                    "issue": "Optional peer dependency warning",
                    "severity": "warning",
                    "suggested_fix": "Install optional deps if needed",
                },
            ],
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                response = await scout.detect_environment_issues(
                    "error: node version 14 is not supported",
                    tmpdir,
                )

        assert len(response.environment_issues) == 2
        assert response.environment_issues[0].severity.value == "blocking"


class TestScoutBFullDiscovery:
    """Tests for Scout B full_discovery method."""

    @pytest.mark.asyncio
    async def test_full_discovery(self) -> None:
        """Test full build/test discovery."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "build": {
                "detected_system": "npm",
                "commands": {
                    "install": "npm ci",
                    "build": "npm run build",
                    "clean": "npm run clean",
                },
            },
            "test": {
                "detected_framework": "jest",
                "commands": {
                    "all": "npm test",
                    "unit": "npm run test:unit",
                },
                "coverage_command": "npm run test:coverage",
            },
            "environment_issues": [],
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                response = await scout.full_discovery(tmpdir)

        assert response.build is not None
        assert response.test is not None
        assert response.build.detected_system == BuildSystem.NPM
        assert response.test.detected_framework == TestFramework.JEST


class TestScoutBGetRawResponse:
    """Tests for Scout B get_raw_response method."""

    @pytest.mark.asyncio
    async def test_get_raw_response_after_query(self) -> None:
        """Test getting raw response after query."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        mock_response = {
            "schema_version": SCHEMA_VERSION,
            "custom_field": "preserved",
        }

        with patch.object(
            scout.llm_client, "query_json", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response

            with tempfile.TemporaryDirectory() as tmpdir:
                await scout.query("Test", tmpdir, include_build_configs=False)

        raw = scout.get_raw_response()
        assert raw is not None
        assert raw["custom_field"] == "preserved"

    def test_get_raw_response_no_queries(self) -> None:
        """Test getting raw response with no queries."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = ScoutB(config)

        assert scout.get_raw_response() is None


class TestCreateScoutB:
    """Tests for create_scout_b factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating Scout B with defaults."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        scout = create_scout_b(config)

        assert isinstance(scout, ScoutB)
        assert scout.llm_client.timeout_seconds == 60.0

    def test_create_with_custom_settings(self) -> None:
        """Test creating Scout B with custom settings."""
        config = LLMConfig(
            backend=LLMBackend.OPENAI,
            api_key="test-key",
        )
        scout = create_scout_b(config, timeout_seconds=90.0, max_retries=4)

        assert scout.llm_client.timeout_seconds == 90.0
        assert scout.llm_client.retry_config.max_retries == 4
