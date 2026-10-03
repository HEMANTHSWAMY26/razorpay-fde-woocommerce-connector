"""Unit tests for retry policies, backoff calculation, and Retry-After handling."""

import asyncio
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from woocommerce_connector.retry import (
    calculate_backoff,
    execute_with_retry,
    parse_retry_after,
)


def test_parse_retry_after_integer():
    assert parse_retry_after("120") == 120.0
    assert parse_retry_after("  5  ") == 5.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("invalid") is None


def test_calculate_backoff_bounds():
    # Base = 0.5, attempt 0 -> [0.25, 0.5]
    delay = calculate_backoff(attempt=0, base=0.5, max_delay=10.0)
    assert 0.25 <= delay <= 0.5

    # Capped by max_delay
    delay_large = calculate_backoff(attempt=10, base=0.5, max_delay=5.0)
    assert delay_large == 5.0


def test_calculate_backoff_respects_retry_after():
    delay = calculate_backoff(attempt=0, base=0.5, max_delay=10.0, retry_after=3.5)
    assert delay == 3.5

    # Capped if Retry-After exceeds max_delay
    delay_capped = calculate_backoff(attempt=0, base=0.5, max_delay=10.0, retry_after=60.0)
    assert delay_capped == 10.0


@pytest.mark.asyncio
async def test_non_retryable_status_codes_not_retried():
    """Verify that 400, 401, 403, 404 return immediately without retry."""
    for status in [400, 401, 403, 404]:
        call_count = 0

        async def _call():
            nonlocal call_count
            call_count += 1
            req = httpx.Request("GET", "https://mock.example.com")
            return httpx.Response(status_code=status, request=req)

        resp = await execute_with_retry(_call, max_retries=3, base_delay=0.001)
        assert resp.status_code == status
        assert call_count == 1  # No retries!


@pytest.mark.asyncio
async def test_retry_on_500_twice_then_succeed():
    """Scenario E: WooCommerce returns 500 twice, then succeeds on 3rd attempt."""
    call_count = 0

    async def _call():
        nonlocal call_count
        call_count += 1
        req = httpx.Request("GET", "https://mock.example.com")
        if call_count < 3:
            return httpx.Response(status_code=500, request=req)
        return httpx.Response(status_code=200, json={"status": "ok"}, request=req)

    resp = await execute_with_retry(_call, max_retries=3, base_delay=0.001, max_delay=0.01)
    assert resp.status_code == 200
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_exhaustion_on_persistent_500():
    """Scenario F: WooCommerce keeps returning 500 until retries are exhausted."""
    call_count = 0

    async def _call():
        nonlocal call_count
        call_count += 1
        req = httpx.Request("GET", "https://mock.example.com")
        return httpx.Response(status_code=500, request=req)

    resp = await execute_with_retry(_call, max_retries=2, base_delay=0.001, max_delay=0.01)
    assert resp.status_code == 500
    assert call_count == 3  # Initial try + 2 retries = 3 calls


@pytest.mark.asyncio
async def test_retry_on_429_with_retry_after():
    """Scenario D: 429 returns with Retry-After header."""
    call_count = 0

    async def _call():
        nonlocal call_count
        call_count += 1
        req = httpx.Request("GET", "https://mock.example.com")
        if call_count == 1:
            return httpx.Response(status_code=429, headers={"Retry-After": "0.01"}, request=req)
        return httpx.Response(status_code=200, json={"result": "success"}, request=req)

    resp = await execute_with_retry(_call, max_retries=2, base_delay=0.001, max_delay=0.05)
    assert resp.status_code == 200
    assert call_count == 2
