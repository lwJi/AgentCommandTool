"""LLM client for Scout queries.

Provides a unified interface for querying LLMs from different backends
(Anthropic, OpenAI, or custom OpenAI-compatible endpoints).
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from act.config.env import LLMBackend, LLMConfig
from act.scouts.exceptions import LLMError, SchemaError, ScoutErrorType
from act.scouts.retry import DEFAULT_MAX_RETRIES, RetryConfig, retry_async

# Default timeout for LLM queries in seconds
DEFAULT_TIMEOUT_SECONDS = 60

# Default models for each backend
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_OPENAI_MODEL = "gpt-4o"


@dataclass
class LLMMessage:
    """A message in an LLM conversation."""

    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM query."""

    content: str
    raw_response: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class LLMClient:
    """Client for making LLM queries with retry support."""

    def __init__(
        self,
        config: LLMConfig,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize LLMClient.

        Args:
            config: LLM configuration from environment.
            timeout_seconds: Timeout for each query in seconds.
            retry_config: Configuration for retry behavior.
        """
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.retry_config = retry_config or RetryConfig()
        self._anthropic_client: Any = None
        self._openai_client: Any = None

    def _get_anthropic_client(self) -> Any:
        """Get or create Anthropic client.

        Returns:
            Anthropic client instance.

        Raises:
            LLMError: If Anthropic SDK is not available.
        """
        if self._anthropic_client is None:
            try:
                import anthropic

                self._anthropic_client = anthropic.Anthropic(
                    api_key=self.config.api_key,
                )
            except ImportError as e:
                raise LLMError(
                    "Anthropic SDK not installed",
                    ScoutErrorType.LLM_UNAVAILABLE,
                ) from e
        return self._anthropic_client

    def _get_openai_client(self) -> Any:
        """Get or create OpenAI client.

        Returns:
            OpenAI client instance.

        Raises:
            LLMError: If OpenAI SDK is not available.
        """
        if self._openai_client is None:
            try:
                import openai

                kwargs: dict[str, Any] = {"api_key": self.config.api_key}
                if self.config.base_url:
                    kwargs["base_url"] = self.config.base_url

                self._openai_client = openai.OpenAI(**kwargs)
            except ImportError as e:
                raise LLMError(
                    "OpenAI SDK not installed",
                    ScoutErrorType.LLM_UNAVAILABLE,
                ) from e
        return self._openai_client

    def _get_model(self) -> str:
        """Get the model to use for queries.

        Returns:
            Model identifier.
        """
        if self.config.model:
            return self.config.model

        if self.config.backend == LLMBackend.ANTHROPIC:
            return DEFAULT_ANTHROPIC_MODEL
        return DEFAULT_OPENAI_MODEL

    async def _query_anthropic(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Query Anthropic API.

        Args:
            messages: List of messages in the conversation.
            system_prompt: Optional system prompt.

        Returns:
            LLM response.

        Raises:
            LLMError: On API errors.
        """
        client = self._get_anthropic_client()
        model = self._get_model()

        # Convert messages to Anthropic format (excluding system messages)
        anthropic_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.role != "system"
        ]

        # Build system prompt from system messages + explicit system_prompt
        system_parts = [msg.content for msg in messages if msg.role == "system"]
        if system_prompt:
            system_parts.append(system_prompt)
        system = "\n\n".join(system_parts) if system_parts else None

        try:

            def _call() -> Any:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "max_tokens": 8192,
                    "messages": anthropic_messages,
                }
                if system:
                    kwargs["system"] = system

                return client.messages.create(**kwargs)

            # Run synchronous API call in thread pool
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call),
                timeout=self.timeout_seconds,
            )

            content = ""
            if response.content:
                content = response.content[0].text

            return LLMResponse(
                content=content,
                raw_response=response.model_dump(),
                model=response.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

        except TimeoutError as e:
            raise LLMError(
                f"Anthropic query timed out after {self.timeout_seconds}s",
                ScoutErrorType.LLM_TIMEOUT,
            ) from e
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                raise LLMError(str(e), ScoutErrorType.LLM_RATE_LIMIT) from e
            if "connection" in error_str or "network" in error_str:
                raise LLMError(str(e), ScoutErrorType.LLM_UNAVAILABLE) from e
            raise LLMError(str(e), ScoutErrorType.UNKNOWN) from e

    async def _query_openai(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Query OpenAI or OpenAI-compatible API.

        Args:
            messages: List of messages in the conversation.
            system_prompt: Optional system prompt to prepend.

        Returns:
            LLM response.

        Raises:
            LLMError: On API errors.
        """
        client = self._get_openai_client()
        model = self._get_model()

        # Convert messages to OpenAI format
        openai_messages = []

        # Add system prompt first if provided
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})

        try:

            def _call() -> Any:
                return client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                    max_tokens=8192,
                )

            # Run synchronous API call in thread pool
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call),
                timeout=self.timeout_seconds,
            )

            content = ""
            if response.choices:
                content = response.choices[0].message.content or ""

            usage = {}
            if response.usage:
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                }

            return LLMResponse(
                content=content,
                raw_response=response.model_dump(),
                model=response.model,
                usage=usage,
            )

        except TimeoutError as e:
            raise LLMError(
                f"OpenAI query timed out after {self.timeout_seconds}s",
                ScoutErrorType.LLM_TIMEOUT,
            ) from e
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                raise LLMError(str(e), ScoutErrorType.LLM_RATE_LIMIT) from e
            if "connection" in error_str or "network" in error_str:
                raise LLMError(str(e), ScoutErrorType.LLM_UNAVAILABLE) from e
            raise LLMError(str(e), ScoutErrorType.UNKNOWN) from e

    async def query(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Query the LLM.

        Args:
            messages: List of messages in the conversation.
            system_prompt: Optional system prompt.

        Returns:
            LLM response.

        Raises:
            LLMError: On API errors.
        """
        if self.config.backend == LLMBackend.ANTHROPIC:
            return await self._query_anthropic(messages, system_prompt)
        else:
            # OpenAI or Custom (OpenAI-compatible)
            return await self._query_openai(messages, system_prompt)

    async def query_with_retry(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Query the LLM with automatic retry on transient failures.

        Args:
            messages: List of messages in the conversation.
            system_prompt: Optional system prompt.

        Returns:
            LLM response.

        Raises:
            RetryExhaustedError: When all retries have been exhausted.
            LLMError: On non-retryable errors.
        """

        async def _query() -> LLMResponse:
            return await self.query(messages, system_prompt)

        return await retry_async(
            _query,
            max_retries=self.retry_config.max_retries,
            initial_delay=self.retry_config.initial_delay,
            backoff_multiplier=self.retry_config.backoff_multiplier,
            max_delay=self.retry_config.max_delay,
        )

    async def query_json(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Query the LLM and parse JSON response.

        Args:
            messages: List of messages in the conversation.
            system_prompt: Optional system prompt.

        Returns:
            Parsed JSON response.

        Raises:
            SchemaError: If response is not valid JSON.
            RetryExhaustedError: When all retries have been exhausted.
            LLMError: On API errors.
        """
        response = await self.query_with_retry(messages, system_prompt)

        # Try to extract JSON from the response
        content = response.content.strip()

        # Handle markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            result: dict[str, Any] = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            raise SchemaError(
                f"Invalid JSON in LLM response: {e}",
                payload={"raw_content": response.content},
            ) from e


def create_llm_client(
    config: LLMConfig,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> LLMClient:
    """Create an LLM client with the given configuration.

    Args:
        config: LLM configuration from environment.
        timeout_seconds: Timeout for each query.
        max_retries: Maximum retry attempts.

    Returns:
        Configured LLM client.
    """
    retry_config = RetryConfig(max_retries=max_retries)
    return LLMClient(config, timeout_seconds, retry_config)
