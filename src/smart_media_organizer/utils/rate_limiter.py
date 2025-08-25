"""Async rate limiting utilities for API calls.

This module provides rate limiting functionality to ensure we don't
exceed API rate limits for external services like TMDB and Hugging Face.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class TokenBucketRateLimiter:
    """Token bucket rate limiter for controlling API request rates.

    This limiter uses the token bucket algorithm to allow bursts of requests
    up to the bucket capacity, while maintaining a steady refill rate.
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        *,
        initial_tokens: int | None = None,
    ) -> None:
        """Initialize the token bucket rate limiter.

        Args:
            capacity: Maximum number of tokens in the bucket
            refill_rate: Number of tokens to add per second
            initial_tokens: Initial number of tokens (defaults to capacity)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

        logger.debug(
            "TokenBucket rate limiter initialized",
            capacity=capacity,
            refill_rate=refill_rate,
            initial_tokens=self.tokens,
        )

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire

        Raises:
            RateLimitExceeded: If not enough tokens are available
        """
        async with self._lock:
            await self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(
                    "Tokens acquired",
                    requested=tokens,
                    remaining=self.tokens,
                    capacity=self.capacity,
                )
            else:
                # Calculate how long to wait for enough tokens
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.refill_rate

                logger.warning(
                    "Rate limit exceeded",
                    requested=tokens,
                    available=self.tokens,
                    wait_time=wait_time,
                )

                raise RateLimitExceeded(retry_after=wait_time)

    async def acquire_wait(self, tokens: int = 1) -> None:
        """Acquire tokens from the bucket, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire
        """
        while True:
            try:
                await self.acquire(tokens)
                return
            except RateLimitExceeded as e:
                if e.retry_after:
                    logger.info(
                        "Rate limited, waiting",
                        wait_time=e.retry_after,
                        tokens=tokens,
                    )
                    await asyncio.sleep(e.retry_after)
                else:
                    # Fallback wait time
                    await asyncio.sleep(1.0)

    async def _refill(self) -> None:
        """Refill the token bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        if elapsed > 0:
            tokens_to_add = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now

    @property
    def available_tokens(self) -> int:
        """Get the current number of available tokens."""
        return int(self.tokens)

    def reset(self) -> None:
        """Reset the rate limiter to full capacity."""
        self.tokens = self.capacity
        self.last_refill = time.time()
        logger.debug("Rate limiter reset", capacity=self.capacity)


class SlidingWindowRateLimiter:
    """Sliding window rate limiter.

    This limiter tracks requests in a sliding time window and ensures
    the request rate doesn't exceed the specified limit.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        """Initialize the sliding window rate limiter.

        Args:
            max_requests: Maximum number of requests per window
            window_seconds: Time window duration in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

        logger.debug(
            "SlidingWindow rate limiter initialized",
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

    async def acquire(self) -> None:
        """Acquire permission to make a request.

        Raises:
            RateLimitExceeded: If the rate limit would be exceeded
        """
        async with self._lock:
            now = time.time()
            self._cleanup_old_requests(now)

            if len(self.requests) >= self.max_requests:
                # Calculate when the oldest request will expire
                oldest_request = self.requests[0]
                retry_after = oldest_request + self.window_seconds - now

                logger.warning(
                    "Rate limit exceeded",
                    current_requests=len(self.requests),
                    max_requests=self.max_requests,
                    retry_after=retry_after,
                )

                raise RateLimitExceeded(retry_after=retry_after)

            self.requests.append(now)
            logger.debug(
                "Request acquired",
                current_requests=len(self.requests),
                max_requests=self.max_requests,
            )

    async def acquire_wait(self) -> None:
        """Acquire permission to make a request, waiting if necessary."""
        while True:
            try:
                await self.acquire()
                return
            except RateLimitExceeded as e:
                if e.retry_after and e.retry_after > 0:
                    logger.info("Rate limited, waiting", wait_time=e.retry_after)
                    await asyncio.sleep(e.retry_after)
                else:
                    await asyncio.sleep(0.1)

    def _cleanup_old_requests(self, now: float) -> None:
        """Remove requests that are outside the current window."""
        cutoff = now - self.window_seconds
        while self.requests and self.requests[0] <= cutoff:
            self.requests.popleft()

    @property
    def current_requests(self) -> int:
        """Get the current number of requests in the window."""
        return len(self.requests)

    def reset(self) -> None:
        """Reset the rate limiter."""
        self.requests.clear()
        logger.debug("Rate limiter reset")


class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts based on API response patterns.

    This limiter monitors API responses and automatically adjusts the rate
    when it detects rate limiting responses from the server.
    """

    def __init__(
        self,
        initial_rate: float,
        *,
        min_rate: float = 0.1,
        max_rate: float = 100.0,
        increase_factor: float = 1.1,
        decrease_factor: float = 0.5,
    ) -> None:
        """Initialize the adaptive rate limiter.

        Args:
            initial_rate: Initial requests per second
            min_rate: Minimum requests per second
            max_rate: Maximum requests per second
            increase_factor: Factor to increase rate on success
            decrease_factor: Factor to decrease rate on rate limit
        """
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.increase_factor = increase_factor
        self.decrease_factor = decrease_factor
        self.last_request = 0.0
        self.consecutive_successes = 0
        self._lock = asyncio.Lock()

        logger.debug(
            "Adaptive rate limiter initialized",
            initial_rate=initial_rate,
            min_rate=min_rate,
            max_rate=max_rate,
        )

    async def acquire(self) -> None:
        """Acquire permission to make a request."""
        async with self._lock:
            now = time.time()
            time_since_last = now - self.last_request

            # Calculate required delay based on current rate
            required_delay = 1.0 / self.current_rate
            remaining_delay = required_delay - time_since_last

            if remaining_delay > 0:
                await asyncio.sleep(remaining_delay)

            self.last_request = time.time()
            logger.debug(
                "Request acquired",
                current_rate=self.current_rate,
                delay=remaining_delay,
            )

    async def report_success(self) -> None:
        """Report a successful API call to potentially increase rate."""
        async with self._lock:
            self.consecutive_successes += 1

            # Increase rate after several consecutive successes
            if self.consecutive_successes >= 10:
                old_rate = self.current_rate
                self.current_rate = min(
                    self.max_rate, self.current_rate * self.increase_factor
                )

                if self.current_rate != old_rate:
                    logger.info(
                        "Rate increased",
                        old_rate=old_rate,
                        new_rate=self.current_rate,
                        successes=self.consecutive_successes,
                    )

                self.consecutive_successes = 0

    async def report_rate_limited(self) -> None:
        """Report a rate-limited response to decrease rate."""
        async with self._lock:
            old_rate = self.current_rate
            self.current_rate = max(
                self.min_rate, self.current_rate * self.decrease_factor
            )
            self.consecutive_successes = 0

            logger.warning(
                "Rate decreased due to rate limiting",
                old_rate=old_rate,
                new_rate=self.current_rate,
            )

    @property
    def rate(self) -> float:
        """Get the current request rate."""
        return self.current_rate


class RateLimitedClient:
    """A wrapper that adds rate limiting to any async function.

    This can be used to wrap API client functions to automatically
    apply rate limiting.
    """

    def __init__(
        self,
        rate_limiter: TokenBucketRateLimiter
        | SlidingWindowRateLimiter
        | AdaptiveRateLimiter,
        *,
        auto_retry: bool = True,
        max_retries: int = 3,
    ) -> None:
        """Initialize the rate-limited client wrapper.

        Args:
            rate_limiter: Rate limiter to use
            auto_retry: Whether to automatically retry on rate limits
            max_retries: Maximum number of retries
        """
        self.rate_limiter = rate_limiter
        self.auto_retry = auto_retry
        self.max_retries = max_retries

    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Call a function with rate limiting applied.

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RateLimitExceeded: If rate limit exceeded and auto_retry is False
        """
        retries = 0

        while retries <= self.max_retries:
            try:
                # Acquire rate limit permission
                if hasattr(self.rate_limiter, "acquire_wait") and self.auto_retry:
                    await self.rate_limiter.acquire_wait()
                else:
                    await self.rate_limiter.acquire()

                # Call the function
                result = await func(*args, **kwargs)

                # Report success to adaptive rate limiter
                if isinstance(self.rate_limiter, AdaptiveRateLimiter):
                    await self.rate_limiter.report_success()

                return result

            except RateLimitExceeded:
                if not self.auto_retry or retries >= self.max_retries:
                    raise

                retries += 1
                logger.info(
                    "Rate limited, retrying",
                    attempt=retries,
                    max_retries=self.max_retries,
                )

                # Report rate limiting to adaptive rate limiter
                if isinstance(self.rate_limiter, AdaptiveRateLimiter):
                    await self.rate_limiter.report_rate_limited()

                # Wait before retry
                await asyncio.sleep(2**retries)  # Exponential backoff

        raise RateLimitExceeded("Max retries exceeded")


# Predefined rate limiters for common APIs
def create_tmdb_rate_limiter() -> TokenBucketRateLimiter:
    """Create a rate limiter suitable for TMDB API.

    TMDB allows 40 requests per 10 seconds.
    """
    return TokenBucketRateLimiter(capacity=40, refill_rate=4.0)


def create_huggingface_rate_limiter() -> AdaptiveRateLimiter:
    """Create a rate limiter suitable for Hugging Face API.

    Hugging Face has variable rate limits depending on the model and plan.
    An adaptive limiter works well here.
    """
    return AdaptiveRateLimiter(initial_rate=1.0, min_rate=0.1, max_rate=10.0)


def create_general_api_rate_limiter(
    requests_per_minute: int = 60,
) -> SlidingWindowRateLimiter:
    """Create a general-purpose rate limiter.

    Args:
        requests_per_minute: Maximum requests per minute

    Returns:
        Configured rate limiter
    """
    return SlidingWindowRateLimiter(
        max_requests=requests_per_minute, window_seconds=60.0
    )
