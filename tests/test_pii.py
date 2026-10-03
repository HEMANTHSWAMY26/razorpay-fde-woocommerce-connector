"""Unit tests for PII data minimization and log sanitization."""

from woocommerce_connector.pii import sanitize_for_logging, strip_customer_pii


def test_strip_customer_pii_removes_sensitive_fields(sample_raw_order):
    """Verify that customer names, addresses, emails, IP and notes are stripped."""
    cleaned = strip_customer_pii(sample_raw_order)

    # Sensitive fields MUST NOT be present
    assert "billing" not in cleaned
    assert "shipping" not in cleaned
    assert "customer_ip_address" not in cleaned
    assert "customer_user_agent" not in cleaned
    assert "customer_note" not in cleaned

    # Non-sensitive operational fields MUST be preserved
    assert cleaned["id"] == 1042
    assert cleaned["number"] == "1042"
    assert cleaned["status"] == "processing"
    assert cleaned["total"] == "89.99"
    assert len(cleaned["line_items"]) == 1


def test_sanitize_for_logging_redacts_credentials_and_pii():
    """Verify recursive sanitization of credentials and sensitive customer fields."""
    log_data = {
        "event": "client_request",
        "consumer_secret": "cs_secret_abc123",
        "nested": {
            "api_key": "key_xyz",
            "safe_field": 42,
            "email": "customer@example.com",
            "phone": "+1234567890",
        },
        "list_items": [
            {"password": "mypassword", "name": "Item 1"}
        ]
    }

    sanitized = sanitize_for_logging(log_data)

    assert sanitized["consumer_secret"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["email"] == "[REDACTED]"
    assert sanitized["nested"]["phone"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == 42
    assert sanitized["list_items"][0]["password"] == "[REDACTED]"
    assert sanitized["list_items"][0]["name"] == "Item 1"
