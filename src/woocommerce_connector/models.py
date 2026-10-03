"""Pydantic data models and schemas for WooCommerce MCP connector."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(str, Enum):
    """Standardized error codes returned by the connector."""

    INVALID_INPUT = "INVALID_INPUT"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    """Normalized error details."""

    model_config = ConfigDict(extra="ignore")

    code: ErrorCode
    message: str


class PaginationMetadata(BaseModel):
    """Pagination tracking information for list queries."""

    model_config = ConfigDict(extra="ignore")

    page: int
    limit: int
    total: Optional[int] = None
    total_pages: Optional[int] = None


class OrderItem(BaseModel):
    """Normalized line item within an order."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    product_id: int
    variation_id: int = 0
    quantity: int
    subtotal: str = "0.00"
    total: str = "0.00"
    sku: Optional[str] = None


class OrderSummary(BaseModel):
    """Normalized, privacy-preserving summary of a WooCommerce order.
    
    Customer personal identifying information (billing address, shipping address,
    email, and phone) is intentionally excluded in accordance with the
    connector's data minimization security policy.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    order_number: str
    status: str
    currency: str
    total: str
    subtotal: Optional[str] = None
    total_tax: Optional[str] = None
    shipping_total: Optional[str] = None
    payment_method_title: Optional[str] = None
    created_at: Optional[str] = None
    date_modified: Optional[str] = None
    items_count: int = 0
    items: list[OrderItem] = Field(default_factory=list)


class ProductCategory(BaseModel):
    """Product category information."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    slug: str


class ProductSummary(BaseModel):
    """Normalized, structured representation of a WooCommerce product."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    slug: str
    sku: Optional[str] = None
    price: Optional[str] = None
    regular_price: Optional[str] = None
    sale_price: Optional[str] = None
    on_sale: bool = False
    status: str
    stock_status: Optional[str] = None
    stock_quantity: Optional[int] = None
    categories: list[ProductCategory] = Field(default_factory=list)
    created_at: Optional[str] = None


class BaseResponse(BaseModel):
    """Root response envelope used by all MCP tools."""

    model_config = ConfigDict(extra="ignore")

    success: bool
    data: Optional[Any] = None
    pagination: Optional[PaginationMetadata] = None
    error: Optional[ErrorDetail] = None

    @classmethod
    def ok(
        cls,
        data: Any,
        pagination: Optional[PaginationMetadata] = None,
    ) -> BaseResponse:
        """Create a successful response."""
        return cls(success=True, data=data, pagination=pagination, error=None)

    @classmethod
    def fail(cls, code: ErrorCode, message: str) -> BaseResponse:
        """Create an error response."""
        return cls(
            success=False,
            data=None,
            pagination=None,
            error=ErrorDetail(code=code, message=message),
        )
