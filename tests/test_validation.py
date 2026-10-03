"""Unit tests for input validation policies."""

import pytest
from woocommerce_connector.validation import (
    MAX_PAGE_LIMIT,
    ValidationError,
    validate_iso8601_date,
    validate_order_status,
    validate_pagination,
    validate_positive_int,
    validate_search_fields,
)


class TestValidatePositiveInt:
    def test_valid_integer(self):
        assert validate_positive_int(1, "id") == 1
        assert validate_positive_int(42, "id") == 42
        assert validate_positive_int("100", "id") == 100

    def test_zero_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_positive_int(0, "id")
        assert "must be a strictly positive integer" in str(exc.value)

    def test_negative_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_positive_int(-10, "id")
        assert "must be a strictly positive integer" in str(exc.value)

    def test_non_integer_string_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_positive_int("hello", "order_id")
        assert "must be a valid integer" in str(exc.value)

    def test_boolean_rejected(self):
        # In Python True is an instance of int, but logically invalid for an ID
        with pytest.raises(ValidationError) as exc:
            validate_positive_int(True, "order_id")
        assert "got boolean" in str(exc.value)


class TestValidatePagination:
    def test_valid_pagination(self):
        p, l = validate_pagination(1, 20)
        assert p == 1
        assert l == 20

    def test_boundary_limit(self):
        p, l = validate_pagination(1, MAX_PAGE_LIMIT)
        assert l == 100

    def test_excessive_limit_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_pagination(1, 1000)
        assert "exceeds connector maximum" in str(exc.value)

    def test_zero_page_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_pagination(0, 20)
        assert "must be a strictly positive integer" in str(exc.value)

    def test_negative_limit_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_pagination(1, -5)
        assert "must be a strictly positive integer" in str(exc.value)


class TestValidateOrderStatus:
    def test_valid_status_case_insensitive(self):
        assert validate_order_status("COMPLETED") == "completed"
        assert validate_order_status("processing") == "processing"
        assert validate_order_status("on-hold") == "on-hold"

    def test_none_or_empty(self):
        assert validate_order_status(None) is None
        assert validate_order_status("") is None

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_order_status("shipped_in_space")
        assert "Invalid order status" in str(exc.value)


class TestValidateISO8601Date:
    def test_valid_iso_dates(self):
        assert validate_iso8601_date("2026-03-15", "after") == "2026-03-15"
        assert validate_iso8601_date("2026-03-15T10:30:00Z", "before") == "2026-03-15T10:30:00Z"
        assert validate_iso8601_date("2026-03-15T10:30:00+00:00", "after") == "2026-03-15T10:30:00+00:00"

    def test_none_is_valid(self):
        assert validate_iso8601_date(None, "after") is None

    def test_invalid_date_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_iso8601_date("yesterday", "after")
        assert "must be an ISO 8601 compliant" in str(exc.value)


class TestValidateSearchFields:
    def test_valid_search_fields(self):
        fields = validate_search_fields(["title", "sku"])
        assert fields == ["title", "sku"]

    def test_none_is_valid(self):
        assert validate_search_fields(None) is None

    def test_unsupported_field_rejected(self):
        with pytest.raises(ValidationError) as exc:
            validate_search_fields(["title", "credit_card_number"])
        assert "Unsupported search field" in str(exc.value)
