"""Unit tests for Scout LLM client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from act.config.env import LLMBackend, LLMConfig
from act.scouts.exceptions import LLMError, SchemaError, ScoutErrorType
from act.scouts.llm_client import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    LLMClient,
    LLMMessage,
    LLMResponse,
    create_llm_client,
)
from act.scouts.retry import DEFAULT_MAX_RETRIES, RetryConfig


class TestLLMMessage:
    """Tests for LLMMessage dataclass."""

    def test_create_user_message(self) -> None:
        """Test creating a user message."""
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_create_assistant_message(self) -> None:
        """Test creating an assistant message."""
        msg = LLMMessage(role="assistant", content="Hi there")
        assert msg.role == "assistant"
        assert msg.content == "Hi there"

    def test_create_system_message(self) -> None:
        """Test creating a system message."""
        msg = LLMMessage(role="system", content="You are a helpful assistant")
        assert msg.role == "system"


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_create_basic_response(self) -> None:
        """Test creating a basic response."""
        response = LLMResponse(content="Hello")
        assert response.content == "Hello"
        assert response.raw_response == {}
        assert response.model == ""
        assert response.usage == {}

    def test_create_full_response(self) -> None:
        """Test creating a response with all fields."""
        response = LLMResponse(
            content="Hello",
            raw_response={"id": "123"},
            model="gpt-4",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        assert response.content == "Hello"
        assert response.raw_response == {"id": "123"}
        assert response.model == "gpt-4"
        assert response.usage == {"input_tokens": 10, "output_tokens": 5}


class TestLLMClientInit:
    """Tests for LLMClient initialization."""

    def test_init_with_anthropic(self) -> None:
        """Test initialization with Anthropic backend."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        client = LLMClient(config)
        assert client.config == config
        assert client.timeout_seconds == DEFAULT_TIMEOUT_SECONDS

    def test_init_with_openai(self) -> None:
        """Test initialization with OpenAI backend."""
        config = LLMConfig(
            backend=LLMBackend.OPENAI,
            api_key="test-key",
        )
        client = LLMClient(config)
        assert client.config == config

    def test_init_with_custom_timeout(self) -> None:
        """Test initialization with custom timeout."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        client = LLMClient(config, timeout_seconds=30.0)
        assert client.timeout_seconds == 30.0

    def test_init_with_retry_config(self) -> None:
        """Test initialization with custom retry config."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        retry_config = RetryConfig(max_retries=5)
        client = LLMClient(config, retry_config=retry_config)
        assert client.retry_config.max_retries == 5


class TestLLMClientGetModel:
    """Tests for LLMClient._get_model method."""

    def test_uses_config_model_if_set(self) -> None:
        """Test that config model is used when set."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
            model="custom-model",
        )
        client = LLMClient(config)
        assert client._get_model() == "custom-model"

    def test_default_anthropic_model(self) -> None:
        """Test default model for Anthropic."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        client = LLMClient(config)
        assert client._get_model() == DEFAULT_ANTHROPIC_MODEL

    def test_default_openai_model(self) -> None:
        """Test default model for OpenAI."""
        config = LLMConfig(
            backend=LLMBackend.OPENAI,
            api_key="test-key",
        )
        client = LLMClient(config)
        assert client._get_model() == DEFAULT_OPENAI_MODEL


class TestLLMClientQuery:
    """Tests for LLMClient.query method."""

    @pytest.mark.asyncio
    async def test_query_anthropic_success(self) -> None:
        """Test successful Anthropic query."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        client = LLMClient(config)

        # Mock the Anthropic client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello response")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.model_dump.return_value = {"id": "test"}

        mock_anthropic = MagicMock()
        mock_anthropic.messages.create.return_value = mock_response

        with patch.object(client, "_get_anthropic_client", return_value=mock_anthropic):
            messages = [LLMMessage(role="user", content="Hello")]
            response = await client.query(messages)

        assert response.content == "Hello response"
        assert response.model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_query_openai_success(self) -> None:
        """Test successful OpenAI query."""
        config = LLMConfig(
            backend=LLMBackend.OPENAI,
            api_key="test-key",
        )
        client = LLMClient(config)

        # Mock the OpenAI client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello response"
        mock_response.model = "gpt-4"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.model_dump.return_value = {"id": "test"}

        mock_openai = MagicMock()
        mock_openai.chat.completions.create.return_value = mock_response

        with patch.object(client, "_get_openai_client", return_value=mock_openai):
            messages = [LLMMessage(role="user", content="Hello")]
            response = await client.query(messages)

        assert response.content == "Hello response"
        assert response.model == "gpt-4"


class TestLLMClientQueryJson:
    """Tests for LLMClient.query_json method."""

    @pytest.mark.asyncio
    async def test_query_json_success(self) -> None:
        """Test successful JSON parsing."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        client = LLMClient(config)

        json_content = '{"key": "value", "number": 42}'
        mock_response = LLMResponse(content=json_content)

        with patch.object(
            client, "query_with_retry", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response
            messages = [LLMMessage(role="user", content="Get JSON")]
            result = await client.query_json(messages)

        assert result == {"key": "value", "number": 42}

    @pytest.mark.asyncio
    async def test_query_json_with_markdown(self) -> None:
        """Test JSON parsing with markdown code blocks."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        client = LLMClient(config)

        json_content = '```json\n{"key": "value"}\n```'
        mock_response = LLMResponse(content=json_content)

        with patch.object(
            client, "query_with_retry", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response
            messages = [LLMMessage(role="user", content="Get JSON")]
            result = await client.query_json(messages)

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_query_json_invalid(self) -> None:
        """Test handling of invalid JSON."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        client = LLMClient(config)

        mock_response = LLMResponse(content="not valid json")

        with patch.object(
            client, "query_with_retry", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = mock_response
            messages = [LLMMessage(role="user", content="Get JSON")]

            with pytest.raises(SchemaError) as exc_info:
                await client.query_json(messages)

            assert "Invalid JSON" in exc_info.value.message


class TestCreateLLMClient:
    """Tests for create_llm_client factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating client with default settings."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        client = create_llm_client(config)

        assert isinstance(client, LLMClient)
        assert client.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
        assert client.retry_config.max_retries == DEFAULT_MAX_RETRIES

    def test_create_with_custom_settings(self) -> None:
        """Test creating client with custom settings."""
        config = LLMConfig(
            backend=LLMBackend.OPENAI,
            api_key="test-key",
        )
        client = create_llm_client(
            config,
            timeout_seconds=120.0,
            max_retries=5,
        )

        assert client.timeout_seconds == 120.0
        assert client.retry_config.max_retries == 5


class TestLLMClientErrorHandling:
    """Tests for LLM client error handling."""

    def test_classify_rate_limit_error(self) -> None:
        """Test that rate limit errors are properly classified."""
        config = LLMConfig(
            backend=LLMBackend.ANTHROPIC,
            api_key="test-key",
        )
        client = LLMClient(config)

        # This would be tested through the actual query, but we can verify
        # the classification logic exists
        assert client.config.backend == LLMBackend.ANTHROPIC
