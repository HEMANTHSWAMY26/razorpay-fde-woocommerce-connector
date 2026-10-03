"""WooCommerce Private MCP Connector package."""

from woocommerce_connector.client import WooCommerceClient
from woocommerce_connector.config import ConfigurationError, Settings
from woocommerce_connector.models import (
    BaseResponse,
    ErrorCode,
    ErrorDetail,
    OrderItem,
    OrderSummary,
    PaginationMetadata,
    ProductCategory,
    ProductSummary,
)
from woocommerce_connector.server import create_server

__all__ = [
    "WooCommerceClient",
    "Settings",
    "ConfigurationError",
    "BaseResponse",
    "ErrorCode",
    "ErrorDetail",
    "OrderItem",
    "OrderSummary",
    "PaginationMetadata",
    "ProductCategory",
    "ProductSummary",
    "create_server",
]
