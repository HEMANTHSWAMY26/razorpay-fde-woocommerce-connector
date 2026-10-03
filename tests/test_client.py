"""Mocked HTTP tests for WooCommerceClient covering all status codes and network scenarios."""

import httpx
import pytest

from woocommerce_connector.client import WooCommerceClient
from woocommerce_connector.config import Settings
from woocommerce_connector.models import ErrorCode


@pytest.fixture
def make_mock_client():
    """Helper to create WooCommerceClient with a mock transport."""
    def _create(handler, max_retries=1):
        settings = Settings(
            woocommerce_url="https://mock-wc.example.com",
            woocommerce_consumer_key="ck_test_key",
            woocommerce_consumer_secret="cs_test_secret",
            timeout_seconds=2.0,
            max_retries=max_retries,
            retry_backoff_base=0.001,
            retry_backoff_max=0.01,
        )
        transport = httpx.MockTransport(handler)
        http_client = httpx.AsyncClient(transport=transport)
        return WooCommerceClient(settings=settings, http_client=http_client)
    return _create


@pytest.mark.asyncio
async def test_list_orders_success_200(make_mock_client, sample_raw_order):
    """Test 200 OK retrieving paginated orders with pagination headers."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wc/v3/orders"
        assert request.headers.get("authorization") is not None
        return httpx.Response(
            200,
            json=[sample_raw_order],
            headers={"X-WP-Total": "1", "X-WP-TotalPages": "1"},
        )

    client = make_mock_client(handler)
    resp = await client.list_orders(page=1, limit=20)

    assert resp.success is True
    assert resp.data is not None
    assert len(resp.data) == 1
    assert resp.data[0]["id"] == 1042
    assert resp.data[0]["status"] == "processing"
    assert resp.pagination.total == 1
    assert resp.pagination.total_pages == 1


@pytest.mark.asyncio
async def test_get_order_success_200(make_mock_client, sample_raw_order):
    """Test 200 OK retrieving a single order."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wc/v3/orders/1042"
        return httpx.Response(200, json=sample_raw_order)

    client = make_mock_client(handler)
    resp = await client.get_order(order_id=1042)

    assert resp.success is True
    assert resp.data["id"] == 1042
    assert resp.data["total"] == "89.99"


@pytest.mark.asyncio
async def test_authentication_failed_401(make_mock_client):
    """Scenario A: Wrong API key or invalid secret returns 401."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"code": "woocommerce_rest_cannot_view", "message": "Consumer secret is invalid."},
        )

    client = make_mock_client(handler)
    resp = await client.list_orders()

    assert resp.success is False
    assert resp.error.code == ErrorCode.AUTHENTICATION_FAILED
    assert "authentication failed" in resp.error.message.lower()


@pytest.mark.asyncio
async def test_permission_denied_403(make_mock_client):
    """Test 403 Forbidden maps to PERMISSION_DENIED."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Forbidden"})

    client = make_mock_client(handler)
    resp = await client.get_order(order_id=1042)

    assert resp.success is False
    assert resp.error.code == ErrorCode.PERMISSION_DENIED


@pytest.mark.asyncio
async def test_not_found_404(make_mock_client):
    """Scenario B: Nonexistent order returns 404 mapped to NOT_FOUND."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Order not found"})

    client = make_mock_client(handler)
    resp = await client.get_order(order_id=999999)

    assert resp.success is False
    assert resp.error.code == ErrorCode.NOT_FOUND
    assert "999999 was not found" in resp.error.message


@pytest.mark.asyncio
async def test_rate_limited_429_exhausted(make_mock_client):
    """Test 429 Too Many Requests exhausting retries returns RATE_LIMITED."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0.001"})

    client = make_mock_client(handler, max_retries=1)
    resp = await client.list_products()

    assert resp.success is False
    assert resp.error.code == ErrorCode.RATE_LIMITED


@pytest.mark.asyncio
async def test_server_error_500_exhausted(make_mock_client):
    """Scenario F: Persistent 500 error returns UPSTREAM_ERROR."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = make_mock_client(handler, max_retries=1)
    resp = await client.list_orders()

    assert resp.success is False
    assert resp.error.code == ErrorCode.UPSTREAM_ERROR


@pytest.mark.asyncio
async def test_bad_gateway_502(make_mock_client):
    """Test 502 Bad Gateway returns UPSTREAM_UNAVAILABLE."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    client = make_mock_client(handler, max_retries=0)
    resp = await client.list_products()

    assert resp.success is False
    assert resp.error.code == ErrorCode.UPSTREAM_UNAVAILABLE


@pytest.mark.asyncio
async def test_gateway_timeout_504(make_mock_client):
    """Test 504 Gateway Timeout returns TIMEOUT."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(504, text="Gateway Timeout")

    client = make_mock_client(handler, max_retries=0)
    resp = await client.get_product(product_id=501)

    assert resp.success is False
    assert resp.error.code == ErrorCode.TIMEOUT


@pytest.mark.asyncio
async def test_network_timeout_exception(make_mock_client):
    """Scenario G: Network timeout exception returns TIMEOUT."""
    def handler(request: httpx.Request):
        raise httpx.ReadTimeout("Mocked read timeout", request=request)

    client = make_mock_client(handler, max_retries=1)
    resp = await client.list_orders()

    assert resp.success is False
    assert resp.error.code == ErrorCode.TIMEOUT
    assert "timed out" in resp.error.message.lower()


@pytest.mark.asyncio
async def test_network_connect_error(make_mock_client):
    """Test network connection error returns UPSTREAM_UNAVAILABLE."""
    def handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused", request=request)

    client = make_mock_client(handler, max_retries=0)
    resp = await client.list_products()

    assert resp.success is False
    assert resp.error.code == ErrorCode.UPSTREAM_UNAVAILABLE


@pytest.mark.asyncio
async def test_malformed_json_response(make_mock_client):
    """Test 200 response with malformed non-JSON body returns UPSTREAM_ERROR."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Invalid PHP Fatal error</html>")

    client = make_mock_client(handler, max_retries=0)
    resp = await client.list_orders()

    assert resp.success is False
    assert resp.error.code == ErrorCode.UPSTREAM_ERROR
    assert "unparseable" in resp.error.message.lower()


@pytest.mark.asyncio
async def test_search_products_with_single_search_field(make_mock_client, sample_raw_product):
    """Verify search_products passes single search_fields parameter to WooCommerce."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wc/v3/products"
        assert request.url.params["search"] == "BP-001"
        assert request.url.params["page"] == "1"
        assert request.url.params["per_page"] == "20"
        search_fields = request.url.params.get_list("search_fields")
        assert "sku" in search_fields
        assert search_fields == ["sku"]
        return httpx.Response(200, json=[sample_raw_product])

    client = make_mock_client(handler)
    resp = await client.search_products(
        query="BP-001",
        search_fields=["sku"],
        page=1,
        limit=20,
    )

    assert resp.success is True
    assert resp.data is not None
    assert len(resp.data) == 1
    assert resp.data[0]["id"] == 501


@pytest.mark.asyncio
async def test_search_products_with_multiple_search_fields(make_mock_client, sample_raw_product):
    """Verify search_products passes multiple search_fields as repeated query parameters."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wc/v3/products"
        assert request.url.params["search"] == "backpack"
        assert request.url.params["page"] == "1"
        assert request.url.params["per_page"] == "20"
        search_fields = request.url.params.get_list("search_fields")
        assert set(search_fields) == {"sku", "name"}
        assert len(search_fields) == 2
        return httpx.Response(200, json=[sample_raw_product])

    client = make_mock_client(handler)
    resp = await client.search_products(
        query="backpack",
        search_fields=["sku", "name"],
        page=1,
        limit=20,
    )

    assert resp.success is True
    assert resp.data is not None
    assert len(resp.data) == 1


@pytest.mark.asyncio
async def test_search_products_omits_search_fields_when_none_or_empty(make_mock_client, sample_raw_product):
    """Verify search_products does not send search_fields when None or empty."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wc/v3/products"
        assert "search_fields" not in request.url.params
        return httpx.Response(200, json=[sample_raw_product])

    client = make_mock_client(handler)
    resp_none = await client.search_products(query="backpack", search_fields=None)
    assert resp_none.success is True

    resp_empty = await client.search_products(query="backpack", search_fields=[])
    assert resp_empty.success is True
