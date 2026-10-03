"""MCP Server definition and tool registrations for WooCommerce."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from typing import Any, List, Optional
import uvicorn
from starlette.responses import JSONResponse
from starlette.requests import Request

from mcp.server import MCPServer
from woocommerce_connector.client import WooCommerceClient
from woocommerce_connector.config import ConfigurationError, Settings
from woocommerce_connector.models import (
    BaseResponse,
    ErrorCode,
    OrderSummary,
    PaginationMetadata,
    ProductSummary,
)
from woocommerce_connector.validation import (
    ValidationError,
    validate_iso8601_date,
    validate_order_status,
    validate_pagination,
    validate_positive_int,
    validate_search_fields,
)

logger = logging.getLogger("woocommerce_connector.server")


def create_server(
    settings: Optional[Settings] = None,
    client: Optional[WooCommerceClient] = None,
) -> MCPServer:
    """Factory function to build and configure the WooCommerce MCPServer.

    Supports dependency injection for testing.
    """
    server = MCPServer(
        name="woocommerce-connector",
        version="1.0.0",
        description="Private read-only MCP connector for WooCommerce store information.",
    )

    # In lazy/test scenarios, settings might be loaded on first tool execution
    _client_holder: list[Optional[WooCommerceClient]] = [client]
    _settings_holder: list[Optional[Settings]] = [settings]

    def _get_active_client() -> WooCommerceClient:
        if _client_holder[0] is not None:
            return _client_holder[0]

        if _settings_holder[0] is None:
            _settings_holder[0] = Settings.from_env()

        _client_holder[0] = WooCommerceClient(settings=_settings_holder[0])
        return _client_holder[0]

    # -------------------------------------------------------------------------
    # Health Endpoint
    # -------------------------------------------------------------------------
    @server.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint for container orchestrators and monitoring."""
        return JSONResponse(
            {
                "status": "ok",
                "service": "woocommerce-mcp-connector",
                "version": "1.0.0",
            }
        )

    # -------------------------------------------------------------------------
    # TOOL 1: list_orders
    # -------------------------------------------------------------------------
    @server.tool()
    async def list_orders(
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> BaseResponse:
        """Retrieve a paginated list of orders from WooCommerce.

        Inputs:
            page: Positive integer page number (default 1).
            limit: Positive integer items per page (1 to 100, default 20).
            status: Optional order status filter ('pending', 'processing', 'on-hold', 'completed', 'cancelled', 'refunded', 'failed', 'trash', 'any').
        """
        start_time = time.monotonic()
        logger.info("Tool invoked: list_orders (page=%s, limit=%s, status=%s)", page, limit, status)

        try:
            val_page, val_limit = validate_pagination(page, limit)
            val_status = validate_order_status(status)
        except ValidationError as err:
            logger.warning("Validation failed for list_orders: %s", err)
            return BaseResponse.fail(ErrorCode.INVALID_INPUT, str(err))

        try:
            wc_client = _get_active_client()
            response = await wc_client.list_orders(
                page=val_page,
                limit=val_limit,
                status=val_status,
            )
            elapsed = time.monotonic() - start_time
            logger.info("Tool finished: list_orders success=%s (%.2fs)", response.success, elapsed)
            return response
        except ConfigurationError as err:
            logger.error("Configuration error in list_orders: %s", err)
            return BaseResponse.fail(ErrorCode.AUTHENTICATION_FAILED, str(err))
        except Exception as exc:
            logger.exception("Internal error executing list_orders")
            return BaseResponse.fail(ErrorCode.INTERNAL_ERROR, "An internal error occurred executing list_orders.")

    # -------------------------------------------------------------------------
    # TOOL 2: get_order
    # -------------------------------------------------------------------------
    @server.tool()
    async def get_order(order_id: int) -> BaseResponse:
        """Retrieve a single WooCommerce order by its positive integer ID.

        Inputs:
            order_id: Strictly positive integer representing the order ID.
        """
        start_time = time.monotonic()
        logger.info("Tool invoked: get_order (order_id=%s)", order_id)

        try:
            val_order_id = validate_positive_int(order_id, "order_id")
        except ValidationError as err:
            logger.warning("Validation failed for get_order: %s", err)
            return BaseResponse.fail(ErrorCode.INVALID_INPUT, str(err))

        try:
            wc_client = _get_active_client()
            response = await wc_client.get_order(order_id=val_order_id)
            elapsed = time.monotonic() - start_time
            logger.info("Tool finished: get_order success=%s (%.2fs)", response.success, elapsed)
            return response
        except ConfigurationError as err:
            logger.error("Configuration error in get_order: %s", err)
            return BaseResponse.fail(ErrorCode.AUTHENTICATION_FAILED, str(err))
        except Exception:
            logger.exception("Internal error executing get_order")
            return BaseResponse.fail(ErrorCode.INTERNAL_ERROR, "An internal error occurred executing get_order.")

    # -------------------------------------------------------------------------
    # TOOL 3: search_orders
    # -------------------------------------------------------------------------
    @server.tool()
    async def search_orders(
        query: Optional[str] = None,
        status: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> BaseResponse:
        """Search and filter orders using controlled parameters.

        Inputs:
            query: Optional search string.
            status: Optional order status filter.
            after: Optional ISO 8601 date to retrieve orders created after.
            before: Optional ISO 8601 date to retrieve orders created before.
            page: Positive integer page number (default 1).
            limit: Positive integer items per page (1 to 100, default 20).
        """
        start_time = time.monotonic()
        logger.info("Tool invoked: search_orders (page=%s, limit=%s, status=%s)", page, limit, status)

        try:
            val_page, val_limit = validate_pagination(page, limit)
            val_status = validate_order_status(status)
            val_after = validate_iso8601_date(after, "after")
            val_before = validate_iso8601_date(before, "before")
            clean_query = str(query).strip() if query else None
        except ValidationError as err:
            logger.warning("Validation failed for search_orders: %s", err)
            return BaseResponse.fail(ErrorCode.INVALID_INPUT, str(err))

        try:
            wc_client = _get_active_client()
            response = await wc_client.search_orders(
                query=clean_query,
                status=val_status,
                after=val_after,
                before=val_before,
                page=val_page,
                limit=val_limit,
            )
            elapsed = time.monotonic() - start_time
            logger.info("Tool finished: search_orders success=%s (%.2fs)", response.success, elapsed)
            return response
        except ConfigurationError as err:
            logger.error("Configuration error in search_orders: %s", err)
            return BaseResponse.fail(ErrorCode.AUTHENTICATION_FAILED, str(err))
        except Exception:
            logger.exception("Internal error executing search_orders")
            return BaseResponse.fail(ErrorCode.INTERNAL_ERROR, "An internal error occurred executing search_orders.")

    # -------------------------------------------------------------------------
    # TOOL 4: list_products
    # -------------------------------------------------------------------------
    @server.tool()
    async def list_products(
        page: int = 1,
        limit: int = 20,
    ) -> BaseResponse:
        """Retrieve a paginated list of products from WooCommerce.

        Inputs:
            page: Positive integer page number (default 1).
            limit: Positive integer items per page (1 to 100, default 20).
        """
        start_time = time.monotonic()
        logger.info("Tool invoked: list_products (page=%s, limit=%s)", page, limit)

        try:
            val_page, val_limit = validate_pagination(page, limit)
        except ValidationError as err:
            logger.warning("Validation failed for list_products: %s", err)
            return BaseResponse.fail(ErrorCode.INVALID_INPUT, str(err))

        try:
            wc_client = _get_active_client()
            response = await wc_client.list_products(
                page=val_page,
                limit=val_limit,
            )
            elapsed = time.monotonic() - start_time
            logger.info("Tool finished: list_products success=%s (%.2fs)", response.success, elapsed)
            return response
        except ConfigurationError as err:
            logger.error("Configuration error in list_products: %s", err)
            return BaseResponse.fail(ErrorCode.AUTHENTICATION_FAILED, str(err))
        except Exception:
            logger.exception("Internal error executing list_products")
            return BaseResponse.fail(ErrorCode.INTERNAL_ERROR, "An internal error occurred executing list_products.")

    # -------------------------------------------------------------------------
    # TOOL 5: get_product
    # -------------------------------------------------------------------------
    @server.tool()
    async def get_product(product_id: int) -> BaseResponse:
        """Retrieve a single WooCommerce product by its positive integer ID.

        Inputs:
            product_id: Strictly positive integer representing the product ID.
        """
        start_time = time.monotonic()
        logger.info("Tool invoked: get_product (product_id=%s)", product_id)

        try:
            val_product_id = validate_positive_int(product_id, "product_id")
        except ValidationError as err:
            logger.warning("Validation failed for get_product: %s", err)
            return BaseResponse.fail(ErrorCode.INVALID_INPUT, str(err))

        try:
            wc_client = _get_active_client()
            response = await wc_client.get_product(product_id=val_product_id)
            elapsed = time.monotonic() - start_time
            logger.info("Tool finished: get_product success=%s (%.2fs)", response.success, elapsed)
            return response
        except ConfigurationError as err:
            logger.error("Configuration error in get_product: %s", err)
            return BaseResponse.fail(ErrorCode.AUTHENTICATION_FAILED, str(err))
        except Exception:
            logger.exception("Internal error executing get_product")
            return BaseResponse.fail(ErrorCode.INTERNAL_ERROR, "An internal error occurred executing get_product.")

    # -------------------------------------------------------------------------
    # TOOL 6: search_products
    # -------------------------------------------------------------------------
    @server.tool()
    async def search_products(
        query: str,
        search_fields: Optional[List[str]] = None,
        page: int = 1,
        limit: int = 20,
    ) -> BaseResponse:
        """Search products using official WooCommerce search queries.

        Inputs:
            query: Search text to match against products (title, content, sku).
            search_fields: Optional list of fields ('title', 'content', 'sku', 'name', 'description').
            page: Positive integer page number (default 1).
            limit: Positive integer items per page (1 to 100, default 20).
        """
        start_time = time.monotonic()
        logger.info("Tool invoked: search_products (page=%s, limit=%s)", page, limit)

        clean_query = str(query).strip() if query else ""
        if not clean_query:
            return BaseResponse.fail(ErrorCode.INVALID_INPUT, "Parameter 'query' cannot be empty.")

        try:
            val_page, val_limit = validate_pagination(page, limit)
            val_fields = validate_search_fields(search_fields)
        except ValidationError as err:
            logger.warning("Validation failed for search_products: %s", err)
            return BaseResponse.fail(ErrorCode.INVALID_INPUT, str(err))

        try:
            wc_client = _get_active_client()
            response = await wc_client.search_products(
                query=clean_query,
                search_fields=val_fields,
                page=val_page,
                limit=val_limit,
            )
            elapsed = time.monotonic() - start_time
            logger.info("Tool finished: search_products success=%s (%.2fs)", response.success, elapsed)
            return response
        except ConfigurationError as err:
            logger.error("Configuration error in search_products: %s", err)
            return BaseResponse.fail(ErrorCode.AUTHENTICATION_FAILED, str(err))
        except Exception:
            logger.exception("Internal error executing search_products")
            return BaseResponse.fail(ErrorCode.INTERNAL_ERROR, "An internal error occurred executing search_products.")

    return server


def setup_logging(level: str = "INFO") -> None:
    """Configure secure, clean console logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """CLI Entrypoint for running the WooCommerce MCP Server."""
    parser = argparse.ArgumentParser(
        description="Private Read-Only WooCommerce MCP Server for Razorpay FDE Assignment."
    )
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "stdio"],
        default="streamable-http",
        help="Transport mechanism to use (default: streamable-http)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host address to bind HTTP server (overrides MCP_SERVER_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind HTTP server (overrides MCP_SERVER_PORT)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    try:
        settings = Settings.from_env(require_credentials=True)
    except ConfigurationError as err:
        logger.error("Configuration Error: %s", err)
        print(f"\nConfiguration Error: {err}\n", file=sys.stderr)
        print("Please configure .env with WOOCOMMERCE_URL, WOOCOMMERCE_CONSUMER_KEY, and WOOCOMMERCE_CONSUMER_SECRET.", file=sys.stderr)
        sys.exit(1)

    host = args.host or settings.mcp_server_host
    port = args.port or settings.mcp_server_port

    server = create_server(settings=settings)

    if args.transport == "streamable-http":
        logger.info(
            "Starting WooCommerce MCP Server with Streamable HTTP on %s:%d (MCP endpoint: /mcp, Health: /health)",
            host,
            port,
        )
        app = server.streamable_http_app()
        uvicorn.run(app, host=host, port=port, log_level=args.log_level.lower())
    elif args.transport == "stdio":
        logger.info("Starting WooCommerce MCP Server with stdio transport")
        asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
