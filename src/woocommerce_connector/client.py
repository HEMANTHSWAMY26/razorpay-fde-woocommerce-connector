"""WooCommerce REST API v3 HTTP client with authentication, retry, and normalization."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Tuple
import httpx

from woocommerce_connector.config import Settings
from woocommerce_connector.models import (
    BaseResponse,
    ErrorCode,
    OrderSummary,
    PaginationMetadata,
    ProductSummary,
)
from woocommerce_connector.normalization import (
    extract_pagination,
    normalize_order,
    normalize_product,
)
from woocommerce_connector.retry import execute_with_retry

logger = logging.getLogger("woocommerce_connector.client")


class WooCommerceClient:
    """Read-only HTTP client for WooCommerce REST API v3."""

    def __init__(
        self,
        settings: Settings,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Initialize the client with configuration settings.

        Args:
            settings: Validated application configuration.
            http_client: Optional pre-configured httpx.AsyncClient (useful for testing).
        """
        self.settings = settings
        self._custom_client = http_client
        self._client: Optional[httpx.AsyncClient] = http_client

        # Base endpoint prefix for WooCommerce REST API v3
        self.base_url = f"{settings.woocommerce_url}/wp-json/wc/v3"

        self._auth = httpx.BasicAuth(
            settings.woocommerce_consumer_key,
            settings.woocommerce_consumer_secret,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the reusable httpx.AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.timeout_seconds),
                auth=self._auth,
                headers={
                    "User-Agent": "WooCommerce-MCP-Connector/1.0.0",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._client and not self._client.is_closed and self._client != self._custom_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> WooCommerceClient:
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Tuple[BaseResponse, Mapping[str, str]]:
        """Execute a GET request against WooCommerce with retries and normalized error mapping.

        Security Note: Only GET requests are executed. Write methods (POST, PUT, DELETE)
        are prohibited by design.

        Returns:
            Tuple[BaseResponse, Mapping[str, str]]: Normalized response envelope and raw headers.
        """
        client = await self._get_client()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}

        async def _call() -> httpx.Response:
            return await client.get(
                url,
                params=clean_params,
                auth=self._auth,
                headers={"User-Agent": "WooCommerce-MCP-Connector/1.0.0", "Accept": "application/json"},
            )

        try:
            response = await execute_with_retry(
                _call,
                max_retries=self.settings.max_retries,
                base_delay=self.settings.retry_backoff_base,
                max_delay=self.settings.retry_backoff_max,
            )
        except httpx.TimeoutException:
            logger.error("Request to WooCommerce %s timed out after retries", endpoint)
            return (
                BaseResponse.fail(
                    ErrorCode.TIMEOUT,
                    "Request to WooCommerce store timed out.",
                ),
                {},
            )
        except (httpx.ConnectError, httpx.NetworkError) as err:
            logger.error("Network connectivity failure to WooCommerce %s: %s", endpoint, type(err).__name__)
            return (
                BaseResponse.fail(
                    ErrorCode.UPSTREAM_UNAVAILABLE,
                    "Unable to connect to WooCommerce store. Please verify store URL and network connectivity.",
                ),
                {},
            )
        except Exception as exc:
            logger.exception("Unexpected error communicating with WooCommerce %s", endpoint)
            return (
                BaseResponse.fail(
                    ErrorCode.INTERNAL_ERROR,
                    "An unexpected internal error occurred while communicating with WooCommerce.",
                ),
                {},
            )

        envelope = self._handle_response(response, endpoint)
        return envelope, response.headers

    def _handle_response(self, response: httpx.Response, endpoint: str) -> BaseResponse:
        """Map HTTP status codes to standardized BaseResponse."""
        status = response.status_code

        if status == 200:
            try:
                payload = response.json()
                return BaseResponse(
                    success=True,
                    data=payload,
                    pagination=None,
                    error=None,
                )
            except Exception:
                return BaseResponse.fail(
                    ErrorCode.UPSTREAM_ERROR,
                    "WooCommerce returned an unparseable response body.",
                )

        if status == 400:
            return BaseResponse.fail(
                ErrorCode.UPSTREAM_ERROR,
                "WooCommerce rejected the request as invalid.",
            )
        elif status == 401:
            return BaseResponse.fail(
                ErrorCode.AUTHENTICATION_FAILED,
                "WooCommerce authentication failed. Please verify WOOCOMMERCE_CONSUMER_KEY and WOOCOMMERCE_CONSUMER_SECRET.",
            )
        elif status == 403:
            return BaseResponse.fail(
                ErrorCode.PERMISSION_DENIED,
                "Permission denied. Verify that your WooCommerce REST API key has read permissions.",
            )
        elif status == 404:
            return BaseResponse.fail(
                ErrorCode.NOT_FOUND,
                f"Requested resource at '{endpoint}' was not found.",
            )
        elif status == 429:
            return BaseResponse.fail(
                ErrorCode.RATE_LIMITED,
                "WooCommerce rate limit reached. The store temporarily rejected further requests.",
            )
        elif status == 500:
            return BaseResponse.fail(
                ErrorCode.UPSTREAM_ERROR,
                "WooCommerce store encountered an internal server error (HTTP 500).",
            )
        elif status in (502, 503):
            return BaseResponse.fail(
                ErrorCode.UPSTREAM_UNAVAILABLE,
                f"WooCommerce store is temporarily unavailable (HTTP {status}).",
            )
        elif status == 504:
            return BaseResponse.fail(
                ErrorCode.TIMEOUT,
                "WooCommerce upstream gateway timed out (HTTP 504).",
            )
        else:
            return BaseResponse.fail(
                ErrorCode.UPSTREAM_ERROR,
                f"WooCommerce returned unexpected HTTP status {status}.",
            )

    # -------------------------------------------------------------------------
    # High-level Resource Methods
    # -------------------------------------------------------------------------

    async def list_orders(
        self,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> BaseResponse:
        """Retrieve paginated orders from WooCommerce."""
        params: dict[str, Any] = {
            "page": page,
            "per_page": limit,
        }
        if status:
            params["status"] = status

        raw_resp, headers = await self._request("orders", params)
        if not raw_resp.success:
            return raw_resp

        raw_data = raw_resp.data if isinstance(raw_resp.data, list) else []
        normalized_orders = [normalize_order(order) for order in raw_data]
        pagination = extract_pagination(headers, page=page, limit=limit)

        return BaseResponse.ok(
            data=[o.model_dump() for o in normalized_orders],
            pagination=pagination,
        )

    async def get_order(self, order_id: int) -> BaseResponse:
        """Retrieve a single order by ID."""
        raw_resp, _ = await self._request(f"orders/{order_id}")
        if not raw_resp.success:
            if raw_resp.error and raw_resp.error.code == ErrorCode.NOT_FOUND:
                return BaseResponse.fail(
                    ErrorCode.NOT_FOUND,
                    f"Order {order_id} was not found.",
                )
            return raw_resp

        if not isinstance(raw_resp.data, dict):
            return BaseResponse.fail(
                ErrorCode.UPSTREAM_ERROR,
                f"Unexpected response format for order {order_id}.",
            )

        order_summary = normalize_order(raw_resp.data)
        return BaseResponse.ok(data=order_summary.model_dump())

    async def search_orders(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> BaseResponse:
        """Search and filter orders using controlled parameters."""
        params: dict[str, Any] = {
            "page": page,
            "per_page": limit,
        }
        if query:
            params["search"] = query
        if status:
            params["status"] = status
        if after:
            params["after"] = after
        if before:
            params["before"] = before

        raw_resp, headers = await self._request("orders", params)
        if not raw_resp.success:
            return raw_resp

        raw_data = raw_resp.data if isinstance(raw_resp.data, list) else []
        normalized_orders = [normalize_order(order) for order in raw_data]
        pagination = extract_pagination(headers, page=page, limit=limit)

        return BaseResponse.ok(
            data=[o.model_dump() for o in normalized_orders],
            pagination=pagination,
        )

    async def list_products(
        self,
        page: int = 1,
        limit: int = 20,
    ) -> BaseResponse:
        """Retrieve paginated products from WooCommerce."""
        params = {
            "page": page,
            "per_page": limit,
        }
        raw_resp, headers = await self._request("products", params)
        if not raw_resp.success:
            return raw_resp

        raw_data = raw_resp.data if isinstance(raw_resp.data, list) else []
        normalized_products = [normalize_product(p) for p in raw_data]
        pagination = extract_pagination(headers, page=page, limit=limit)

        return BaseResponse.ok(
            data=[p.model_dump() for p in normalized_products],
            pagination=pagination,
        )

    async def get_product(self, product_id: int) -> BaseResponse:
        """Retrieve a single product by ID."""
        raw_resp, _ = await self._request(f"products/{product_id}")
        if not raw_resp.success:
            if raw_resp.error and raw_resp.error.code == ErrorCode.NOT_FOUND:
                return BaseResponse.fail(
                    ErrorCode.NOT_FOUND,
                    f"Product {product_id} was not found.",
                )
            return raw_resp

        if not isinstance(raw_resp.data, dict):
            return BaseResponse.fail(
                ErrorCode.UPSTREAM_ERROR,
                f"Unexpected response format for product {product_id}.",
            )

        product_summary = normalize_product(raw_resp.data)
        return BaseResponse.ok(data=product_summary.model_dump())

    async def search_products(
        self,
        query: str,
        search_fields: Optional[list[str]] = None,
        page: int = 1,
        limit: int = 20,
    ) -> BaseResponse:
        """Search products using official WooCommerce search query."""
        params: dict[str, Any] = {
            "search": query,
            "page": page,
            "per_page": limit,
        }
        raw_resp, headers = await self._request("products", params)
        if not raw_resp.success:
            return raw_resp

        raw_data = raw_resp.data if isinstance(raw_resp.data, list) else []
        normalized_products = [normalize_product(p) for p in raw_data]
        pagination = extract_pagination(headers, page=page, limit=limit)

        return BaseResponse.ok(
            data=[p.model_dump() for p in normalized_products],
            pagination=pagination,
        )
