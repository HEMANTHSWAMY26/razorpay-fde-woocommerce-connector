"""Unit tests for configuration loading and validation."""

import pytest
from woocommerce_connector.config import ConfigurationError, Settings


def test_valid_configuration():
    """Verify that a valid configuration dictionary builds Settings properly."""
    env = {
        "WOOCOMMERCE_URL": "https://mystore.example.com/",
        "WOOCOMMERCE_CONSUMER_KEY": "ck_test123",
        "WOOCOMMERCE_CONSUMER_SECRET": "cs_test456",
        "MCP_SERVER_HOST": "127.0.0.1",
        "MCP_SERVER_PORT": "9000",
        "WOOCOMMERCE_TIMEOUT_SECONDS": "20.5",
        "WOOCOMMERCE_MAX_RETRIES": "5",
        "WOOCOMMERCE_RETRY_BACKOFF_BASE": "1.0",
        "WOOCOMMERCE_RETRY_BACKOFF_MAX": "15.0",
    }
    settings = Settings.from_env(env)
    assert settings.woocommerce_url == "https://mystore.example.com"
    assert settings.woocommerce_consumer_key == "ck_test123"
    assert settings.woocommerce_consumer_secret == "cs_test456"
    assert settings.mcp_server_host == "127.0.0.1"
    assert settings.mcp_server_port == 9000
    assert settings.timeout_seconds == 20.5
    assert settings.max_retries == 5
    assert settings.retry_backoff_base == 1.0
    assert settings.retry_backoff_max == 15.0


def test_missing_credentials_raises_error():
    """Verify that missing credentials raise a clear ConfigurationError."""
    with pytest.raises(ConfigurationError) as exc_info:
        Settings.from_env({}, require_credentials=True)

    err = str(exc_info.value)
    assert "WOOCOMMERCE_URL" in err
    assert "WOOCOMMERCE_CONSUMER_KEY" in err
    assert "WOOCOMMERCE_CONSUMER_SECRET" in err


def test_invalid_url_scheme_raises_error():
    """Verify that non-http/https URLs raise ConfigurationError."""
    env = {
        "WOOCOMMERCE_URL": "ftp://ftp.example.com",
        "WOOCOMMERCE_CONSUMER_KEY": "ck_123",
        "WOOCOMMERCE_CONSUMER_SECRET": "cs_456",
    }
    with pytest.raises(ConfigurationError) as exc_info:
        Settings.from_env(env)
    assert "Must be a valid URL with http or https" in str(exc_info.value)


def test_credentials_masked_in_repr():
    """Verify that secrets are never leaked in string representation."""
    settings = Settings(
        woocommerce_url="https://mystore.example.com",
        woocommerce_consumer_key="ck_super_secret_key_12345",
        woocommerce_consumer_secret="cs_top_secret_value_67890",
    )
    rep = repr(settings)
    assert "cs_top_secret_value_67890" not in rep
    assert "ck_super_secret_key_12345" not in rep
    assert "***" in rep
