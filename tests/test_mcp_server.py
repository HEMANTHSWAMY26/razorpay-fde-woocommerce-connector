"""In-process integration tests for MCPServer and tool discovery."""

import json
import httpx
import pytest
from starlette.testclient import TestClient

from woocommerce_connector.client import WooCommerceClient
from woocommerce_connector.config import Settings
from woocommerce_connector.models import ErrorCode
from woocommerce_connector.server import create_server

EXPECTED_TOOLS = {
    "list_orders",
    "get_order",
    "search_orders",
    "list_products",
    "get_product",
    "search_products",
}

FORBIDDEN_TOOLS = {
    "create_order",
    "update_order",
    "delete_order",
    "create_product",
    "update_product",
    "delete_product",
    "generic_woocommerce_api",
    "call_endpoint",
    "raw_http_request",
}


@pytest.fixture
def mock_wc_client(mock_settings, sample_raw_order, sample_raw_product):
    """Fixture providing a mock-backed WooCommerceClient."""
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/wp-json/wc/v3/orders":
            return httpx.Response(200, json=[sample_raw_order], headers={"X-WP-Total": "1"})
        elif path == "/wp-json/wc/v3/orders/1042":
            return httpx.Response(200, json=sample_raw_order)
        elif path == "/wp-json/wc/v3/orders/999":
            return httpx.Response(404, json={"message": "Not found"})
        elif path == "/wp-json/wc/v3/products":
            return httpx.Response(200, json=[sample_raw_product], headers={"X-WP-Total": "1"})
        elif path == "/wp-json/wc/v3/products/501":
            return httpx.Response(200, json=sample_raw_product)
        return httpx.Response(404, json={"message": "Not found"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return WooCommerceClient(settings=mock_settings, http_client=http_client)


@pytest.fixture
def mcp_server(mock_settings, mock_wc_client):
    """Create test MCPServer instance with injected mock client."""
    return create_server(settings=mock_settings, client=mock_wc_client)


@pytest.mark.asyncio
async def test_tool_discovery_and_exact_six_tools(mcp_server):
    """Verify tool discovery: exactly the 6 defined read-only tools exist."""
    tools = await mcp_server.list_tools()
    discovered_names = {t.name for t in tools}

    assert discovered_names == EXPECTED_TOOLS
    assert len(discovered_names) == 6


@pytest.mark.asyncio
async def test_no_write_or_arbitrary_tools_exist(mcp_server):
    """Verify security boundary: no write tools or generic API callers exist."""
    tools = await mcp_server.list_tools()
    discovered_names = {t.name for t in tools}

    for forbidden in FORBIDDEN_TOOLS:
        assert forbidden not in discovered_names, f"Security violation: {forbidden} was exposed!"


@pytest.mark.asyncio
async def test_tool_input_schemas(mcp_server):
    """Verify that tool input schemas are properly constructed."""
    tools = {t.name: t for t in await mcp_server.list_tools()}

    # Check list_orders schema
    list_orders_schema = tools["list_orders"].input_schema
    assert "properties" in list_orders_schema
    assert "page" in list_orders_schema["properties"]
    assert "limit" in list_orders_schema["properties"]
    assert "status" in list_orders_schema["properties"]

    # Check get_order schema
    get_order_schema = tools["get_order"].input_schema
    assert "order_id" in get_order_schema["properties"]


@pytest.mark.asyncio
async def test_call_list_orders_valid(mcp_server):
    """Test invoking list_orders with valid parameters."""
    res = await mcp_server.call_tool("list_orders", {"page": 1, "limit": 10})
    payload = json.loads(res.content[0].text)

    assert payload["success"] is True
    assert payload["data"] is not None
    assert len(payload["data"]) == 1
    assert payload["data"][0]["id"] == 1042


@pytest.mark.asyncio
async def test_call_get_order_invalid_id_rejected(mcp_server):
    """Scenario C: Invalid order ID (e.g. negative or 0) rejected as INVALID_INPUT."""
    res = await mcp_server.call_tool("get_order", {"order_id": -5})
    payload = json.loads(res.content[0].text)

    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.INVALID_INPUT.value
    assert "strictly positive integer" in payload["error"]["message"]


@pytest.mark.asyncio
async def test_call_list_orders_limit_overflow_rejected(mcp_server):
    """Scenario H: limit = 100000 rejected by connector policy as INVALID_INPUT."""
    res = await mcp_server.call_tool("list_orders", {"page": 1, "limit": 100000})
    payload = json.loads(res.content[0].text)

    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.INVALID_INPUT.value
    assert "exceeds connector maximum" in payload["error"]["message"]


@pytest.mark.asyncio
async def test_call_search_products_empty_query_rejected(mcp_server):
    """Verify that search_products with empty string is rejected before upstream call."""
    res = await mcp_server.call_tool("search_products", {"query": "   "})
    payload = json.loads(res.content[0].text)

    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.INVALID_INPUT.value
    assert "cannot be empty" in payload["error"]["message"]


@pytest.mark.asyncio
async def test_call_get_product_success(mcp_server):
    """Verify get_product invocation with valid product ID."""
    res = await mcp_server.call_tool("get_product", {"product_id": 501})
    payload = json.loads(res.content[0].text)

    assert payload["success"] is True
    assert payload["data"]["id"] == 501
    assert payload["data"]["name"] == "Travel Backpack"


@pytest.mark.asyncio
async def test_call_search_orders_valid(mcp_server):
    """Test invoking search_orders with filters."""
    res = await mcp_server.call_tool("search_orders", {
        "query": "Backpack",
        "status": "processing",
        "after": "2026-01-01T00:00:00Z",
        "page": 1,
        "limit": 10,
    })
    payload = json.loads(res.content[0].text)
    assert payload["success"] is True
    assert len(payload["data"]) == 1


@pytest.mark.asyncio
async def test_call_search_orders_invalid_status_rejected(mcp_server):
    """Test search_orders with invalid status filter fails validation."""
    res = await mcp_server.call_tool("search_orders", {"status": "invalid_status_xyz"})
    payload = json.loads(res.content[0].text)
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.INVALID_INPUT.value
    assert "Invalid order status" in payload["error"]["message"]


@pytest.mark.asyncio
async def test_call_get_product_invalid_id_rejected(mcp_server):
    """Test get_product with invalid negative or zero ID fails validation."""
    res = await mcp_server.call_tool("get_product", {"product_id": 0})
    payload = json.loads(res.content[0].text)
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.INVALID_INPUT.value
    assert "strictly positive integer" in payload["error"]["message"]


@pytest.mark.asyncio
async def test_call_nonexistent_or_write_tool_rejected(mcp_server):
    """Scenario J: Verify that attempting to call a write tool is impossible."""
    with pytest.raises(Exception):
        await mcp_server.call_tool("create_order", {"name": "Hacked Order"})


def test_health_check_endpoint(mcp_server):
    """Verify GET /health on the streamable HTTP app."""
    app = mcp_server.streamable_http_app()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {
            "status": "ok",
            "service": "woocommerce-mcp-connector",
            "version": "1.0.0",
        }

