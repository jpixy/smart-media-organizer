"""Async retry utilities with exponential backoff.

This module provides robust retry mechanisms for handling transient failures
in API calls and other operations that might fail temporarily.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import random
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""

    def __init__(self, attempts: int, last_exception: Exception) -> None:
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(
            f"Operation failed after {attempts} attempts. Last error: {last_exception}"
        )


class RetryStrategy:
    """Base class for retry strategies."""

    async def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determine if we should retry based on the attempt and exception.

        Args:
            attempt: Current attempt number (0-based)
            exception: Exception that occurred

        Returns:
            True if we should retry, False otherwise
        """
        raise NotImplementedError

    async def get_delay(self, attempt: int, exception: Exception) -> float:
        """Get the delay before the next retry attempt.

        Args:
            attempt: Current attempt number (0-based)
            exception: Exception that occurred

        Returns:
            Delay in seconds
        """
        raise NotImplementedError


class ExponentialBackoffStrategy(RetryStrategy):
    """Exponential backoff retry strategy with jitter."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> None:
        """Initialize exponential backoff strategy.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential calculation
            jitter: Whether to add random jitter to delay
            retryable_exceptions: Tuple of exception types that should trigger retries
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (Exception,)

    async def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if we should retry based on attempt count and exception type."""
        if attempt >= self.max_attempts:
            return False

        return isinstance(exception, self.retryable_exceptions)

    async def get_delay(self, attempt: int, exception: Exception) -> float:
        """Calculate delay with exponential backoff and optional jitter."""
        delay = self.base_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Add jitter: ±25% of the delay
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


class LinearBackoffStrategy(RetryStrategy):
    """Linear backoff retry strategy."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        increment: float = 1.0,
        max_delay: float = 60.0,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> None:
        """Initialize linear backoff strategy.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay in seconds
            increment: Delay increment per attempt
            max_delay: Maximum delay in seconds
            retryable_exceptions: Tuple of exception types that should trigger retries
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.increment = increment
        self.max_delay = max_delay
        self.retryable_exceptions = retryable_exceptions or (Exception,)

    async def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if we should retry based on attempt count and exception type."""
        if attempt >= self.max_attempts:
            return False

        return isinstance(exception, self.retryable_exceptions)

    async def get_delay(self, attempt: int, exception: Exception) -> float:
        """Calculate delay with linear backoff."""
        delay = self.base_delay + (self.increment * attempt)
        return min(delay, self.max_delay)


class FixedDelayStrategy(RetryStrategy):
    """Fixed delay retry strategy."""

    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> None:
        """Initialize fixed delay strategy.

        Args:
            max_attempts: Maximum number of retry attempts
            delay: Fixed delay in seconds
            retryable_exceptions: Tuple of exception types that should trigger retries
        """
        self.max_attempts = max_attempts
        self.delay = delay
        self.retryable_exceptions = retryable_exceptions or (Exception,)

    async def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Check if we should retry based on attempt count and exception type."""
        if attempt >= self.max_attempts:
            return False

        return isinstance(exception, self.retryable_exceptions)

    async def get_delay(self, attempt: int, exception: Exception) -> float:
        """Return fixed delay."""
        return self.delay


class RetryContext:
    """Context object for tracking retry state."""

    def __init__(self, strategy: RetryStrategy) -> None:
        self.strategy = strategy
        self.attempt = 0
        self.exceptions: list[Exception] = []
        self.total_delay = 0.0

    async def should_retry(self, exception: Exception) -> bool:
        """Check if we should retry and update state."""
        self.exceptions.append(exception)
        should_retry = await self.strategy.should_retry(self.attempt, exception)

        if should_retry:
            delay = await self.strategy.get_delay(self.attempt, exception)
            self.total_delay += delay

            logger.warning(
                "Operation failed, retrying",
                attempt=self.attempt + 1,
                max_attempts=self.strategy.max_attempts,
                delay=delay,
                exception=str(exception),
                exception_type=type(exception).__name__,
            )

            await asyncio.sleep(delay)
            self.attempt += 1

        return should_retry

    def get_final_exception(self) -> RetryError:
        """Get the final exception to raise after all retries are exhausted."""
        last_exception = (
            self.exceptions[-1] if self.exceptions else Exception("Unknown error")
        )
        return RetryError(self.attempt, last_exception)


async def retry_async(
    func: Callable[..., Any],
    *args,
    strategy: RetryStrategy | None = None,
    **kwargs,
) -> Any:
    """Retry an async function with the specified strategy.

    Args:
        func: Async function to retry
        *args: Function arguments
        strategy: Retry strategy to use (defaults to exponential backoff)
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        RetryError: If all retry attempts are exhausted
    """
    if strategy is None:
        strategy = ExponentialBackoffStrategy()

    context = RetryContext(strategy)

    while True:
        try:
            result = await func(*args, **kwargs)

            if context.attempt > 0:
                logger.info(
                    "Operation succeeded after retries",
                    attempts=context.attempt + 1,
                    total_delay=context.total_delay,
                )

            return result

        except Exception as e:
            if not await context.should_retry(e):
                logger.error(
                    "Operation failed after all retries",
                    attempts=context.attempt + 1,
                    total_delay=context.total_delay,
                    final_exception=str(e),
                )
                raise context.get_final_exception() from e


def retry(
    strategy: RetryStrategy | None = None,
    *,
    max_attempts: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable:
    """Decorator for adding retry logic to async functions.

    Args:
        strategy: Retry strategy to use
        max_attempts: Maximum retry attempts (creates default strategy if None)
        base_delay: Base delay for default strategy
        max_delay: Maximum delay for default strategy
        retryable_exceptions: Exceptions that should trigger retries

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(*args, **kwargs) -> Any:
            nonlocal strategy

            # Create default strategy if none provided
            if strategy is None:
                strategy_kwargs = {}
                if max_attempts is not None:
                    strategy_kwargs["max_attempts"] = max_attempts
                if base_delay is not None:
                    strategy_kwargs["base_delay"] = base_delay
                if max_delay is not None:
                    strategy_kwargs["max_delay"] = max_delay
                if retryable_exceptions is not None:
                    strategy_kwargs["retryable_exceptions"] = retryable_exceptions

                strategy = ExponentialBackoffStrategy(**strategy_kwargs)

            return await retry_async(func, *args, strategy=strategy, **kwargs)

        return wrapper

    return decorator


# Predefined strategies for common use cases
def create_api_retry_strategy() -> ExponentialBackoffStrategy:
    """Create a retry strategy suitable for API calls.

    Returns:
        Configured retry strategy for API calls
    """
    from aiohttp import ClientError
    from httpx import HTTPError

    return ExponentialBackoffStrategy(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
        retryable_exceptions=(ConnectionError, TimeoutError, ClientError, HTTPError),
    )


def create_file_operation_retry_strategy() -> ExponentialBackoffStrategy:
    """Create a retry strategy suitable for file operations.

    Returns:
        Configured retry strategy for file operations
    """
    return ExponentialBackoffStrategy(
        max_attempts=3,
        base_delay=0.5,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
        retryable_exceptions=(OSError, IOError, PermissionError),
    )


def create_network_retry_strategy() -> ExponentialBackoffStrategy:
    """Create a retry strategy suitable for network operations.

    Returns:
        Configured retry strategy for network operations
    """
    return ExponentialBackoffStrategy(
        max_attempts=5,
        base_delay=1.0,
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True,
        retryable_exceptions=(
            ConnectionError,
            TimeoutError,
            OSError,
        ),
    )


# Example usage decorator with common configurations
def retry_api_call(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> Callable:
    """Decorator for retrying API calls with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Decorator function
    """
    strategy = create_api_retry_strategy()
    strategy.max_attempts = max_attempts
    strategy.base_delay = base_delay
    strategy.max_delay = max_delay

    return retry(strategy=strategy)


def retry_file_operation(
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
) -> Callable:
    """Decorator for retrying file operations with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Decorator function
    """
    strategy = create_file_operation_retry_strategy()
    strategy.max_attempts = max_attempts
    strategy.base_delay = base_delay
    strategy.max_delay = max_delay

    return retry(strategy=strategy)
