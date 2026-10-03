"""Retry policy and backoff calculation for transient network and upstream errors."""

from __future__ import annotations

import asyncio
import email.utils
import logging
import random
import time
from typing import Callable, Coroutine, Optional, Set, TypeVar
import httpx

logger = logging.getLogger("woocommerce_connector.retry")

# HTTP status codes eligible for automatic bounded retry
RETRYABLE_STATUS_CODES: Set[int] = {429, 500, 502, 503, 504}

# HTTP status codes that must NEVER be retried
NON_RETRYABLE_STATUS_CODES: Set[int] = {400, 401, 403, 404}

# Exceptions eligible for retry
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.NetworkError,
)

T = TypeVar("T")


def parse_retry_after(header_value: Optional[str]) -> Optional[float]:
    """Parse HTTP 'Retry-After' header value.

    Supports both:
    1. Integer seconds (e.g. '120')
    2. HTTP date format (RFC 2822 / RFC 7231, e.g. 'Wed, 21 Oct 2026 07:28:00 GMT')

    Returns:
        Optional[float]: Delay in seconds, or None if unparseable/missing.
    """
    if not header_value:
        return None

    cleaned = header_value.strip()

    # Try integer seconds first
    if cleaned.isdigit():
        return float(cleaned)

    # Try HTTP date
    try:
        parsed_time = email.utils.parsedate_to_datetime(cleaned)
        diff = (parsed_time.timestamp() - time.time())
        return max(0.0, diff)
    except Exception:
        return None


def calculate_backoff(
    attempt: int,
    base: float = 0.5,
    max_delay: float = 10.0,
    retry_after: Optional[float] = None,
) -> float:
    """Calculate backoff duration with exponential progression and jitter.

    Args:
        attempt: Zero-based retry attempt number (0, 1, 2, ...).
        base: Base backoff multiplier in seconds.
        max_delay: Maximum allowed backoff sleep in seconds.
        retry_after: Explicit delay specified in Retry-After header.

    Returns:
        float: Calculated delay in seconds, bounded by max_delay.
    """
    if retry_after is not None and retry_after > 0:
        # Respect server-provided Retry-After, capped by max_delay to prevent hanging
        return min(retry_after, max_delay)

    # Exponential backoff: base * 2^attempt
    exp_delay = base * (2 ** attempt)

    # Full jitter between 0 and exp_delay to distribute concurrent load
    jittered = random.uniform(0.5 * exp_delay, exp_delay)

    return min(jittered, max_delay)


async def execute_with_retry(
    func: Callable[[], Coroutine[Any, Any, httpx.Response]],
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
) -> httpx.Response:
    """Execute an HTTP request coroutine with bounded retries for transient failures.

    Retries on:
    - HTTP 429 (Rate Limited)
    - HTTP 500, 502, 503, 504 (Server Errors)
    - Network timeouts and connection drops

    Does NOT retry:
    - HTTP 400, 401, 403, 404 (Client/Auth/Not-Found errors)

    Args:
        func: Async zero-arg callable returning an httpx.Response.
        max_retries: Max number of retry attempts.
        base_delay: Base backoff in seconds.
        max_delay: Max backoff in seconds.

    Returns:
        httpx.Response: Final HTTP response.

    Raises:
        httpx.TimeoutException: If retries exhausted on timeout.
        httpx.NetworkError: If retries exhausted on connection error.
    """
    attempt = 0
    last_response: Optional[httpx.Response] = None
    last_exception: Optional[Exception] = None

    while attempt <= max_retries:
        try:
            response = await func()
            last_response = response

            # If success or non-retryable status, return immediately
            if response.status_code < 400 or response.status_code in NON_RETRYABLE_STATUS_CODES:
                return response

            # If status code is not retryable, return immediately
            if response.status_code not in RETRYABLE_STATUS_CODES:
                return response

            # If we reached maximum retries, break loop and return response
            if attempt >= max_retries:
                logger.warning(
                    "Exhausted retries (%d/%d) for HTTP status %d",
                    attempt,
                    max_retries,
                    response.status_code,
                )
                return response

            # Retryable status code (429, 500, 502, 503, 504)
            retry_after_val = parse_retry_after(response.headers.get("retry-after"))
            delay = calculate_backoff(attempt, base_delay, max_delay, retry_after_val)

            logger.info(
                "Upstream status %d on attempt %d/%d; retrying in %.2fs",
                response.status_code,
                attempt + 1,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)
            attempt += 1

        except RETRYABLE_EXCEPTIONS as exc:
            last_exception = exc
            if attempt >= max_retries:
                logger.warning(
                    "Exhausted retries (%d/%d) for transient exception: %s",
                    attempt,
                    max_retries,
                    type(exc).__name__,
                )
                raise exc

            delay = calculate_backoff(attempt, base_delay, max_delay)
            logger.info(
                "Transient error '%s' on attempt %d/%d; retrying in %.2fs",
                type(exc).__name__,
                attempt + 1,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)
            attempt += 1

    if last_exception is not None:
        raise last_exception
    assert last_response is not None
    return last_response
