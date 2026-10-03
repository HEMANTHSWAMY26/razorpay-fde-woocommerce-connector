"""Unit tests for response normalization and pagination header extraction."""

from woocommerce_connector.normalization import (
    extract_pagination,
    normalize_order,
    normalize_order_item,
    normalize_product,
)


def test_normalize_order_and_items(sample_raw_order):
    """Verify that a raw WooCommerce order is correctly transformed into OrderSummary."""
    summary = normalize_order(sample_raw_order)

    assert summary.id == 1042
    assert summary.order_number == "1042"
    assert summary.status == "processing"
    assert summary.currency == "USD"
    assert summary.total == "89.99"
    assert summary.subtotal == "80.00"
    assert summary.total_tax == "9.99"
    assert summary.shipping_total == "0.00"
    assert summary.payment_method_title == "Credit Card (Razorpay)"
    assert summary.items_count == 1
    assert len(summary.items) == 1

    item = summary.items[0]
    assert item.id == 1
    assert item.name == "Travel Backpack"
    assert item.product_id == 501
    assert item.quantity == 1
    assert item.total == "80.00"
    assert item.sku == "BP-001"


def test_normalize_product(sample_raw_product):
    """Verify that a raw WooCommerce product is correctly transformed into ProductSummary."""
    product = normalize_product(sample_raw_product)

    assert product.id == 501
    assert product.name == "Travel Backpack"
    assert product.slug == "travel-backpack"
    assert product.sku == "BP-001"
    assert product.price == "80.00"
    assert product.regular_price == "99.00"
    assert product.sale_price == "80.00"
    assert product.on_sale is True
    assert product.status == "publish"
    assert product.stock_status == "instock"
    assert product.stock_quantity == 25
    assert len(product.categories) == 1
    assert product.categories[0].name == "Bags & Luggage"


def test_extract_pagination_headers():
    """Verify extraction of standard WooCommerce pagination headers."""
    headers = {
        "X-WP-Total": "125",
        "X-WP-TotalPages": "7",
    }
    meta = extract_pagination(headers, page=1, limit=20)
    assert meta.page == 1
    assert meta.limit == 20
    assert meta.total == 125
    assert meta.total_pages == 7


def test_extract_pagination_headers_missing():
    """Verify fallback behavior when WooCommerce pagination headers are absent."""
    meta = extract_pagination({}, page=2, limit=10)
    assert meta.page == 2
    assert meta.limit == 10
    assert meta.total is None
    assert meta.total_pages is None
