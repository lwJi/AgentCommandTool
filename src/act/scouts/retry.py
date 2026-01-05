"""Retry logic with exponential backoff for Scout queries."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from act.scouts.exceptions import (
    LLMError,
    RetryExhaustedError,
    ScoutErrorType,
)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY_SECONDS = 1.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_MAX_DELAY_SECONDS = 10.0

T = TypeVar("T")


def calculate_delay(
    attempt: int,
    initial_delay: float = DEFAULT_INITIAL_DELAY_SECONDS,
    multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
) -> float:
    """Calculate delay for a given retry attempt using exponential backoff.

    Delay pattern: 1s, 2s, 4s (with default settings).

    Args:
        attempt: The retry attempt number (0-indexed).
        initial_delay: Initial delay in seconds.
        multiplier: Multiplier for each subsequent attempt.
        max_delay: Maximum delay in seconds.

    Returns:
        Delay in seconds.
    """
    delay = initial_delay * (multiplier**attempt)
    return min(delay, max_delay)


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable.

    Args:
        error: The exception that occurred.

    Returns:
        True if the error should trigger a retry.
    """
    if isinstance(error, LLMError):
        # Retry on transient errors
        retryable_types = {
            ScoutErrorType.LLM_TIMEOUT,
            ScoutErrorType.LLM_RATE_LIMIT,
            ScoutErrorType.LLM_UNAVAILABLE,
        }
        return error.error_type in retryable_types

    # Retry on generic network/connection errors
    error_str = str(error).lower()
    retryable_keywords = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "unavailable",
        "rate limit",
        "rate_limit",
        "429",
        "503",
        "504",
    ]
    return any(keyword in error_str for keyword in retryable_keywords)


def retry_sync(
    func: Callable[[], T],
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY_SECONDS,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
) -> T:
    """Execute a function with retry logic (synchronous).

    Implements exponential backoff: 1s, 2s, 4s delay pattern.

    Args:
        func: Function to execute.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        backoff_multiplier: Multiplier for exponential backoff.
        max_delay: Maximum delay between retries.

    Returns:
        Result of the function.

    Raises:
        RetryExhaustedError: When all retries have been exhausted.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e

            # Check if error is retryable
            if not is_retryable_error(e):
                raise

            # If this was the last attempt, don't sleep, just exit loop
            if attempt == max_retries - 1:
                break

            # Calculate delay and sleep
            delay = calculate_delay(
                attempt,
                initial_delay,
                backoff_multiplier,
                max_delay,
            )
            time.sleep(delay)

    raise RetryExhaustedError(
        message=f"Scout query failed after {max_retries} attempts",
        attempts=max_retries,
        last_error=last_error,
    )


async def retry_async(
    func: Callable[[], Awaitable[T]],
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY_SECONDS,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
) -> T:
    """Execute an async function with retry logic.

    Implements exponential backoff: 1s, 2s, 4s delay pattern.

    Args:
        func: Async function to execute.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        backoff_multiplier: Multiplier for exponential backoff.
        max_delay: Maximum delay between retries.

    Returns:
        Result of the function.

    Raises:
        RetryExhaustedError: When all retries have been exhausted.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_error = e

            # Check if error is retryable
            if not is_retryable_error(e):
                raise

            # If this was the last attempt, don't sleep, just exit loop
            if attempt == max_retries - 1:
                break

            # Calculate delay and sleep
            delay = calculate_delay(
                attempt,
                initial_delay,
                backoff_multiplier,
                max_delay,
            )
            await asyncio.sleep(delay)

    raise RetryExhaustedError(
        message=f"Scout query failed after {max_retries} attempts",
        attempts=max_retries,
        last_error=last_error,
    )


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_delay: float = DEFAULT_INITIAL_DELAY_SECONDS,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
    ) -> None:
        """Initialize RetryConfig.

        Args:
            max_retries: Maximum number of retry attempts.
            initial_delay: Initial delay in seconds.
            backoff_multiplier: Multiplier for exponential backoff.
            max_delay: Maximum delay between retries.
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_multiplier = backoff_multiplier
        self.max_delay = max_delay

    def calculate_total_wait_time(self) -> float:
        """Calculate the maximum total wait time for all retries.

        Returns:
            Total wait time in seconds.
        """
        total = 0.0
        for attempt in range(self.max_retries - 1):  # No wait after last attempt
            total += calculate_delay(
                attempt,
                self.initial_delay,
                self.backoff_multiplier,
                self.max_delay,
            )
        return total
