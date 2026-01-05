"""Unit tests for Scout retry logic."""

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from act.scouts.exceptions import LLMError, RetryExhaustedError, ScoutErrorType
from act.scouts.retry import (
    DEFAULT_BACKOFF_MULTIPLIER,
    DEFAULT_INITIAL_DELAY_SECONDS,
    DEFAULT_MAX_DELAY_SECONDS,
    DEFAULT_MAX_RETRIES,
    RetryConfig,
    calculate_delay,
    is_retryable_error,
    retry_async,
    retry_sync,
)


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    def test_first_attempt_delay(self) -> None:
        """Test delay for first attempt."""
        delay = calculate_delay(0)
        assert delay == DEFAULT_INITIAL_DELAY_SECONDS

    def test_exponential_backoff(self) -> None:
        """Test exponential backoff pattern."""
        delays = [calculate_delay(i) for i in range(3)]
        # With default settings: 1s, 2s, 4s
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0

    def test_max_delay_cap(self) -> None:
        """Test that delay is capped at max_delay."""
        delay = calculate_delay(10, max_delay=5.0)
        assert delay == 5.0

    def test_custom_parameters(self) -> None:
        """Test with custom parameters."""
        delay = calculate_delay(
            2,
            initial_delay=0.5,
            multiplier=3.0,
            max_delay=100.0,
        )
        # 0.5 * 3^2 = 4.5
        assert delay == 4.5


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_retryable_llm_errors(self) -> None:
        """Test that transient LLM errors are retryable."""
        retryable_types = [
            ScoutErrorType.LLM_TIMEOUT,
            ScoutErrorType.LLM_RATE_LIMIT,
            ScoutErrorType.LLM_UNAVAILABLE,
        ]
        for error_type in retryable_types:
            error = LLMError("Error", error_type)
            assert is_retryable_error(error) is True

    def test_non_retryable_llm_errors(self) -> None:
        """Test that non-transient LLM errors are not retryable."""
        non_retryable_types = [
            ScoutErrorType.LLM_RESPONSE_INVALID,
            ScoutErrorType.SCHEMA_VALIDATION,
        ]
        for error_type in non_retryable_types:
            error = LLMError("Error", error_type)
            assert is_retryable_error(error) is False

    def test_generic_errors_with_keywords(self) -> None:
        """Test generic errors with retryable keywords."""
        retryable_messages = [
            "Connection timeout occurred",
            "Network error",
            "Service temporarily unavailable",
            "Rate limit exceeded (429)",
            "503 Service Unavailable",
        ]
        for msg in retryable_messages:
            error = Exception(msg)
            assert is_retryable_error(error) is True

    def test_non_retryable_generic_errors(self) -> None:
        """Test generic errors without retryable keywords."""
        error = Exception("Invalid input provided")
        assert is_retryable_error(error) is False


class TestRetrySyncSuccess:
    """Tests for retry_sync with successful execution."""

    def test_succeeds_immediately(self) -> None:
        """Test that successful function returns immediately."""
        mock_func = MagicMock(return_value="success")

        result = retry_sync(mock_func)

        assert result == "success"
        assert mock_func.call_count == 1

    def test_succeeds_after_failures(self) -> None:
        """Test success after initial failures."""
        call_count = 0

        def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise LLMError("Timeout", ScoutErrorType.LLM_TIMEOUT)
            return "success"

        # Use minimal delays for testing
        result = retry_sync(
            flaky_func,
            initial_delay=0.01,
            max_delay=0.01,
        )

        assert result == "success"
        assert call_count == 3


class TestRetrySyncFailure:
    """Tests for retry_sync with failures."""

    def test_exhausted_retries(self) -> None:
        """Test that RetryExhaustedError is raised after max retries."""

        def always_fail() -> None:
            raise LLMError("Timeout", ScoutErrorType.LLM_TIMEOUT)

        with pytest.raises(RetryExhaustedError) as exc_info:
            retry_sync(
                always_fail,
                max_retries=3,
                initial_delay=0.01,
            )

        assert exc_info.value.attempts == 3
        assert exc_info.value.last_error is not None

    def test_non_retryable_error_raises_immediately(self) -> None:
        """Test that non-retryable errors raise immediately."""
        call_count = 0

        def fail_with_non_retryable() -> None:
            nonlocal call_count
            call_count += 1
            raise LLMError("Invalid", ScoutErrorType.LLM_RESPONSE_INVALID)

        with pytest.raises(LLMError):
            retry_sync(fail_with_non_retryable)

        assert call_count == 1  # No retries


class TestRetryAsync:
    """Tests for retry_async function."""

    @pytest.mark.asyncio
    async def test_succeeds_immediately(self) -> None:
        """Test that successful async function returns immediately."""
        call_count = 0

        async def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(success_func)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_after_failures(self) -> None:
        """Test success after initial failures."""
        call_count = 0

        async def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise LLMError("Timeout", ScoutErrorType.LLM_TIMEOUT)
            return "success"

        result = await retry_async(
            flaky_func,
            initial_delay=0.01,
            max_delay=0.01,
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries(self) -> None:
        """Test that RetryExhaustedError is raised after max retries."""

        async def always_fail() -> None:
            raise LLMError("Timeout", ScoutErrorType.LLM_TIMEOUT)

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry_async(
                always_fail,
                max_retries=3,
                initial_delay=0.01,
            )

        assert exc_info.value.attempts == 3

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(self) -> None:
        """Test that non-retryable errors raise immediately."""
        call_count = 0

        async def fail_with_non_retryable() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            await retry_async(fail_with_non_retryable)

        assert call_count == 1


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_retries == DEFAULT_MAX_RETRIES
        assert config.initial_delay == DEFAULT_INITIAL_DELAY_SECONDS
        assert config.backoff_multiplier == DEFAULT_BACKOFF_MULTIPLIER
        assert config.max_delay == DEFAULT_MAX_DELAY_SECONDS

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            backoff_multiplier=3.0,
            max_delay=30.0,
        )
        assert config.max_retries == 5
        assert config.initial_delay == 0.5
        assert config.backoff_multiplier == 3.0
        assert config.max_delay == 30.0

    def test_calculate_total_wait_time(self) -> None:
        """Test total wait time calculation."""
        config = RetryConfig(
            max_retries=3,
            initial_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=10.0,
        )
        # 3 retries means 2 waits: 1s + 2s = 3s
        total = config.calculate_total_wait_time()
        assert total == 3.0

    def test_calculate_total_wait_time_with_cap(self) -> None:
        """Test total wait time with max_delay cap."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=3.0,
        )
        # 5 retries means 4 waits: 1, 2, 3 (capped), 3 (capped) = 9s
        total = config.calculate_total_wait_time()
        assert total == 9.0


class TestRetryTiming:
    """Tests for retry timing behavior."""

    def test_sync_retry_timing(self) -> None:
        """Test that sync retries have expected delays."""
        call_times: list[float] = []

        def record_time() -> None:
            call_times.append(time.time())
            if len(call_times) < 3:
                raise LLMError("Timeout", ScoutErrorType.LLM_TIMEOUT)

        retry_sync(
            record_time,
            max_retries=3,
            initial_delay=0.1,
            backoff_multiplier=2.0,
        )

        assert len(call_times) == 3
        # Check delays (with some tolerance)
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        assert 0.08 <= delay1 <= 0.15  # ~0.1s
        assert 0.15 <= delay2 <= 0.30  # ~0.2s
