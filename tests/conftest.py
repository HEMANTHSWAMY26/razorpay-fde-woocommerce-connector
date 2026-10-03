"""Pytest fixtures and test doubles for WooCommerce connector test suite."""

import pytest
from woocommerce_connector.config import Settings


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture providing valid mock configuration settings."""
    return Settings(
        woocommerce_url="https://mock-store.example.com",
        woocommerce_consumer_key="ck_mock_test_key_1234567890",
        woocommerce_consumer_secret="cs_mock_test_secret_1234567890",
        mcp_server_host="127.0.0.1",
        mcp_server_port=8000,
        timeout_seconds=2.0,
        max_retries=2,
        retry_backoff_base=0.01,  # Fast retries for testing
        retry_backoff_max=0.05,
    )


@pytest.fixture
def sample_raw_order() -> dict:
    """Fixture providing a raw WooCommerce order response with customer PII."""
    return {
        "id": 1042,
        "number": "1042",
        "status": "processing",
        "currency": "USD",
        "date_created": "2026-03-15T10:30:00",
        "date_modified": "2026-03-15T11:00:00",
        "total": "89.99",
        "subtotal": "80.00",
        "total_tax": "9.99",
        "shipping_total": "0.00",
        "payment_method_title": "Credit Card (Razorpay)",
        # Sensitive customer PII that MUST be stripped:
        "billing": {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+15551234567",
            "address_1": "123 Private St",
            "city": "Metropolis",
            "state": "NY",
            "postcode": "10001",
            "country": "US",
        },
        "shipping": {
            "first_name": "John",
            "last_name": "Doe",
            "address_1": "123 Private St",
            "city": "Metropolis",
            "state": "NY",
            "postcode": "10001",
            "country": "US",
        },
        "customer_ip_address": "192.168.1.100",
        "customer_user_agent": "Mozilla/5.0 ...",
        "customer_note": "Please leave at back door",
        "line_items": [
            {
                "id": 1,
                "name": "Travel Backpack",
                "product_id": 501,
                "variation_id": 0,
                "quantity": 1,
                "subtotal": "80.00",
                "total": "80.00",
                "sku": "BP-001",
            }
        ],
    }


@pytest.fixture
def sample_raw_product() -> dict:
    """Fixture providing a raw WooCommerce product response."""
    return {
        "id": 501,
        "name": "Travel Backpack",
        "slug": "travel-backpack",
        "sku": "BP-001",
        "price": "80.00",
        "regular_price": "99.00",
        "sale_price": "80.00",
        "on_sale": True,
        "status": "publish",
        "stock_status": "instock",
        "stock_quantity": 25,
        "date_created": "2026-01-10T08:00:00",
        "categories": [
            {
                "id": 12,
                "name": "Bags & Luggage",
                "slug": "bags-luggage",
            }
        ],
    }
