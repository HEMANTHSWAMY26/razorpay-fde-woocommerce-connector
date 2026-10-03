"""Response normalization module for WooCommerce MCP Connector.

Transforms raw WooCommerce JSON payloads into clean, minimized, structured
data models conforming to the connector's schema.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional
from woocommerce_connector.models import (
    OrderItem,
    OrderSummary,
    PaginationMetadata,
    ProductCategory,
    ProductSummary,
)
from woocommerce_connector.pii import strip_customer_pii


def normalize_order_item(raw_item: Mapping[str, Any]) -> OrderItem:
    """Normalize a raw WooCommerce line item."""
    return OrderItem(
        id=int(raw_item.get("id", 0)),
        name=str(raw_item.get("name", "Unknown Item")),
        product_id=int(raw_item.get("product_id", 0)),
        variation_id=int(raw_item.get("variation_id", 0)),
        quantity=int(raw_item.get("quantity", 1)),
        subtotal=str(raw_item.get("subtotal", "0.00")),
        total=str(raw_item.get("total", "0.00")),
        sku=raw_item.get("sku") or None,
    )


def normalize_order(raw_order: Mapping[str, Any]) -> OrderSummary:
    """Normalize a raw WooCommerce order into OrderSummary.

    Applies PII stripping and data minimization.
    """
    cleaned = strip_customer_pii(raw_order)
    raw_items = cleaned.get("line_items", [])
    normalized_items = [normalize_order_item(item) for item in raw_items]

    return OrderSummary(
        id=int(cleaned.get("id", 0)),
        order_number=str(cleaned.get("number") or cleaned.get("id", "")),
        status=str(cleaned.get("status", "unknown")),
        currency=str(cleaned.get("currency", "USD")),
        total=str(cleaned.get("total", "0.00")),
        subtotal=str(cleaned.get("subtotal")) if cleaned.get("subtotal") is not None else None,
        total_tax=str(cleaned.get("total_tax")) if cleaned.get("total_tax") is not None else None,
        shipping_total=str(cleaned.get("shipping_total")) if cleaned.get("shipping_total") is not None else None,
        payment_method_title=cleaned.get("payment_method_title") or None,
        created_at=cleaned.get("date_created") or cleaned.get("date_created_gmt") or None,
        date_modified=cleaned.get("date_modified") or cleaned.get("date_modified_gmt") or None,
        items_count=len(normalized_items),
        items=normalized_items,
    )


def normalize_product_category(raw_cat: Mapping[str, Any]) -> ProductCategory:
    """Normalize a single product category."""
    return ProductCategory(
        id=int(raw_cat.get("id", 0)),
        name=str(raw_cat.get("name", "")),
        slug=str(raw_cat.get("slug", "")),
    )


def normalize_product(raw_product: Mapping[str, Any]) -> ProductSummary:
    """Normalize a raw WooCommerce product into ProductSummary."""
    raw_categories = raw_product.get("categories", [])
    categories = [normalize_product_category(cat) for cat in raw_categories]

    raw_stock_qty = raw_product.get("stock_quantity")
    stock_quantity = int(raw_stock_qty) if raw_stock_qty is not None else None

    return ProductSummary(
        id=int(raw_product.get("id", 0)),
        name=str(raw_product.get("name", "")),
        slug=str(raw_product.get("slug", "")),
        sku=raw_product.get("sku") or None,
        price=str(raw_product.get("price")) if raw_product.get("price") is not None else None,
        regular_price=str(raw_product.get("regular_price")) if raw_product.get("regular_price") is not None else None,
        sale_price=str(raw_product.get("sale_price")) if raw_product.get("sale_price") is not None else None,
        on_sale=bool(raw_product.get("on_sale", False)),
        status=str(raw_product.get("status", "publish")),
        stock_status=raw_product.get("stock_status") or None,
        stock_quantity=stock_quantity,
        categories=categories,
        created_at=raw_product.get("date_created") or raw_product.get("date_created_gmt") or None,
    )


def extract_pagination(
    headers: Mapping[str, str],
    page: int,
    limit: int,
) -> PaginationMetadata:
    """Extract pagination metadata from WooCommerce response headers.

    WooCommerce REST API exposes:
      X-WP-Total: Total number of resources
      X-WP-TotalPages: Total number of pages
    """
    total: Optional[int] = None
    total_pages: Optional[int] = None

    # HTTP header lookup case-insensitively
    headers_lower = {k.lower(): v for k, v in headers.items()}

    total_str = headers_lower.get("x-wp-total")
    if total_str and total_str.isdigit():
        total = int(total_str)

    pages_str = headers_lower.get("x-wp-totalpages")
    if pages_str and pages_str.isdigit():
        total_pages = int(pages_str)

    return PaginationMetadata(
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
    )
