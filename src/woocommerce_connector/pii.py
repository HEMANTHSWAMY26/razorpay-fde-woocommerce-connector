"""PII and Data Minimization module for WooCommerce MCP Connector.

Enforces strict data minimization by design:
1. Strips customer identifying details (names, emails, phone numbers, addresses, IP)
   from order payloads before exposure to LLMs/MCP clients.
2. Sanitizes logs to prevent sensitive credentials or PII from leaking into logs.
"""

from __future__ import annotations

from typing import Any, Mapping


# Keys containing customer PII in raw WooCommerce responses
CUSTOMER_PII_KEYS = {
    "billing",
    "shipping",
    "customer_ip_address",
    "customer_user_agent",
    "customer_note",
}

# Sensitive keys that must NEVER be written to logs or error messages
LOG_SENSITIVE_KEYS = {
    "consumer_secret",
    "consumer_key",
    "authorization",
    "password",
    "secret",
    "token",
    "api_key",
    "email",
    "phone",
    "first_name",
    "last_name",
}


def strip_customer_pii(raw_order: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of the order dict with sensitive customer PII removed.

    This implements structural data minimization: rather than transmitting
    customer contact information and physical addresses across the MCP boundary,
    only operational order metadata and line items are retained.
    """
    return {k: v for k, v in raw_order.items() if k not in CUSTOMER_PII_KEYS}


def sanitize_for_logging(obj: Any) -> Any:
    """Recursively redact sensitive keys from objects before logging.

    Args:
        obj: Dict, list, or primitive value to sanitize.

    Returns:
        Sanitized copy with sensitive values replaced with '[REDACTED]'.
    """
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            key_lower = str(k).lower()
            if any(sensitive in key_lower for sensitive in LOG_SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_for_logging(v)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_for_logging(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_for_logging(item) for item in obj)
    return obj
