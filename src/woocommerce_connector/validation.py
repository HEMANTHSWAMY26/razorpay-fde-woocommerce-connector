"""Input validation module for WooCommerce MCP tools."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional


# Official WooCommerce order statuses (WC REST API v3)
VALID_ORDER_STATUSES = {
    "any",
    "pending",
    "processing",
    "on-hold",
    "completed",
    "cancelled",
    "refunded",
    "failed",
    "trash",
}

# Maximum pagination limit enforced by our connector safety policy
MAX_PAGE_LIMIT = 100
MIN_PAGE_LIMIT = 1
MIN_PAGE_NUMBER = 1


class ValidationError(ValueError):
    """Raised when an input parameter fails validation."""
    pass


def validate_positive_int(value: Any, field_name: str) -> int:
    """Validate that a value is a strictly positive integer (> 0).

    Args:
        value: The value to validate.
        field_name: The name of the parameter for error reporting.

    Returns:
        int: The validated positive integer.

    Raises:
        ValidationError: If value is not a positive integer.
    """
    if isinstance(value, bool):
        # In Python, bool is a subclass of int, so True == 1. Explicitly reject bools.
        raise ValidationError(f"Parameter '{field_name}' must be an integer, got boolean.")

    try:
        # If string, verify it consists only of digits
        if isinstance(value, str):
            value = value.strip()
            if not value.isdigit():
                raise ValueError()
            int_val = int(value)
        elif isinstance(value, int):
            int_val = value
        else:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError(
            f"Parameter '{field_name}' must be a valid integer, got {type(value).__name__} ({value!r})."
        )

    if int_val <= 0:
        raise ValidationError(
            f"Parameter '{field_name}' must be a strictly positive integer (> 0), got {int_val}."
        )

    return int_val


def validate_pagination(page: Any = 1, limit: Any = 20) -> tuple[int, int]:
    """Validate pagination parameters according to connector safety policy.

    Args:
        page: Requested page number (must be >= 1).
        limit: Requested result count (must be between 1 and MAX_PAGE_LIMIT).

    Returns:
        tuple[int, int]: Validated (page, limit).

    Raises:
        ValidationError: If page or limit are invalid.
    """
    validated_page = validate_positive_int(page, "page")
    validated_limit = validate_positive_int(limit, "limit")

    if validated_limit > MAX_PAGE_LIMIT:
        raise ValidationError(
            f"Parameter 'limit' exceeds connector maximum of {MAX_PAGE_LIMIT} (got {validated_limit}). "
            "Please request 100 or fewer items per page."
        )

    return validated_page, validated_limit


def validate_order_status(status: Optional[str]) -> Optional[str]:
    """Validate that the status is a supported WooCommerce order status.

    Args:
        status: Order status string or None.

    Returns:
        Optional[str]: Normalized lowercase status string, or None.

    Raises:
        ValidationError: If status is unknown.
    """
    if status is None:
        return None

    cleaned = str(status).strip().lower()
    if not cleaned:
        return None

    if cleaned not in VALID_ORDER_STATUSES:
        valid_list = ", ".join(sorted(VALID_ORDER_STATUSES))
        raise ValidationError(
            f"Invalid order status '{status}'. Must be one of: {valid_list}."
        )

    return cleaned


def validate_iso8601_date(date_str: Optional[str], field_name: str) -> Optional[str]:
    """Validate that a date string conforms to ISO 8601 standard.

    Args:
        date_str: Date string or None.
        field_name: Parameter name for error reporting.

    Returns:
        Optional[str]: Validated ISO 8601 string, or None.

    Raises:
        ValidationError: If format is invalid.
    """
    if date_str is None:
        return None

    cleaned = str(date_str).strip()
    if not cleaned:
        return None

    # Handle standard ISO formats, including trailing 'Z'
    try:
        # Python's fromisoformat in 3.11+ handles Z and offsets
        normalized = cleaned.replace("Z", "+00:00")
        datetime.fromisoformat(normalized)
        return cleaned
    except ValueError:
        raise ValidationError(
            f"Parameter '{field_name}' must be an ISO 8601 compliant date/timestamp "
            f"(e.g., '2024-01-01T00:00:00Z' or '2024-01-01'), got '{date_str}'."
        )


def validate_search_fields(fields: Optional[list[str]]) -> Optional[list[str]]:
    """Validate search fields parameter against WooCommerce product search capabilities."""
    if fields is None:
        return None

    if not isinstance(fields, (list, tuple)):
        raise ValidationError("Parameter 'search_fields' must be a list of field names.")

    allowed_fields = {
        "name",
        "sku",
        "global_unique_id",
        "description",
        "short_description",
    }
    cleaned_fields = []
    for f in fields:
        clean = str(f).strip().lower()
        if clean not in allowed_fields:
            raise ValidationError(
                f"Unsupported search field '{f}'. Supported fields: {', '.join(sorted(allowed_fields))}."
            )
        cleaned_fields.append(clean)

    return cleaned_fields
