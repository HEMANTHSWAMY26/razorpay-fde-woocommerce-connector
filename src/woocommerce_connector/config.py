"""Configuration management for WooCommerce MCP Connector."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""
    pass


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables."""

    woocommerce_url: str
    woocommerce_consumer_key: str
    woocommerce_consumer_secret: str
    mcp_server_host: str = "0.0.0.0"
    mcp_server_port: int = 8000
    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_base: float = 0.5
    retry_backoff_max: float = 10.0

    @classmethod
    def from_env(
        cls,
        env_dict: Optional[dict[str, str]] = None,
        require_credentials: bool = True,
    ) -> Settings:
        """Create Settings from environment or explicit dictionary.

        Args:
            env_dict: Optional dict overriding os.environ.
            require_credentials: If True, raises ConfigurationError when credentials are missing.
        """
        env = env_dict if env_dict is not None else os.environ

        raw_url = env.get("WOOCOMMERCE_URL", "").strip()
        consumer_key = env.get("WOOCOMMERCE_CONSUMER_KEY", "").strip()
        consumer_secret = env.get("WOOCOMMERCE_CONSUMER_SECRET", "").strip()

        if require_credentials:
            missing = []
            if not raw_url:
                missing.append("WOOCOMMERCE_URL")
            if not consumer_key:
                missing.append("WOOCOMMERCE_CONSUMER_KEY")
            if not consumer_secret:
                missing.append("WOOCOMMERCE_CONSUMER_SECRET")

            if missing:
                raise ConfigurationError(
                    f"Missing required WooCommerce configuration: {', '.join(missing)}. "
                    "Ensure these are set in your environment or .env file."
                )

        # Validate URL format if provided
        sanitized_url = ""
        if raw_url:
            parsed = urlparse(raw_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ConfigurationError(
                    f"Invalid WOOCOMMERCE_URL '{raw_url}'. Must be a valid URL with http or https scheme."
                )
            sanitized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

        # Parse numerical settings with fallbacks
        try:
            port = int(env.get("MCP_SERVER_PORT", "8000"))
        except ValueError:
            port = 8000

        try:
            timeout = float(env.get("WOOCOMMERCE_TIMEOUT_SECONDS", "15.0"))
            if timeout <= 0:
                timeout = 15.0
        except ValueError:
            timeout = 15.0

        try:
            max_retries = int(env.get("WOOCOMMERCE_MAX_RETRIES", "3"))
            if max_retries < 0:
                max_retries = 3
        except ValueError:
            max_retries = 3

        try:
            backoff_base = float(env.get("WOOCOMMERCE_RETRY_BACKOFF_BASE", "0.5"))
            if backoff_base <= 0:
                backoff_base = 0.5
        except ValueError:
            backoff_base = 0.5

        try:
            backoff_max = float(env.get("WOOCOMMERCE_RETRY_BACKOFF_MAX", "10.0"))
            if backoff_max <= 0:
                backoff_max = 10.0
        except ValueError:
            backoff_max = 10.0

        host = env.get("MCP_SERVER_HOST", "0.0.0.0").strip() or "0.0.0.0"

        return cls(
            woocommerce_url=sanitized_url,
            woocommerce_consumer_key=consumer_key,
            woocommerce_consumer_secret=consumer_secret,
            mcp_server_host=host,
            mcp_server_port=port,
            timeout_seconds=timeout,
            max_retries=max_retries,
            retry_backoff_base=backoff_base,
            retry_backoff_max=backoff_max,
        )

    def __repr__(self) -> str:
        """Safely mask credentials in string representations."""
        masked_key = (
            f"{self.woocommerce_consumer_key[:6]}..."
            if len(self.woocommerce_consumer_key) > 6
            else "***"
        )
        return (
            f"Settings(url='{self.woocommerce_url}', "
            f"consumer_key='{masked_key}', consumer_secret='***', "
            f"host='{self.mcp_server_host}', port={self.mcp_server_port})"
        )
