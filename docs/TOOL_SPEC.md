# WooCommerce MCP Connector — Tool Specification

This document provides the formal interface specification for all 6 Model Context Protocol (MCP) tools provided by the WooCommerce Private Connector.

---

## Response Envelope Standard

Every tool returns a consistent JSON envelope adhering to either a success or error structure.

### Success Response Envelope
```json
{
  "success": true,
  "data": { ... } | [ ... ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 125,
    "total_pages": 7
  },
  "error": null
}
```
*(Note: `pagination` is present for collection queries and `null` for single-entity queries.)*

### Error Response Envelope
```json
{
  "success": false,
  "data": null,
  "pagination": null,
  "error": {
    "code": "INVALID_INPUT",
    "message": "Parameter 'order_id' must be a strictly positive integer (> 0), got -5."
  }
}
```

### Standard Error Codes
* `INVALID_INPUT`: Connector-side input validation failed before making an upstream request.
* `AUTHENTICATION_FAILED`: WooCommerce credentials rejected (HTTP 401).
* `PERMISSION_DENIED`: API key lacks required read permissions (HTTP 403).
* `NOT_FOUND`: Order or product resource not found (HTTP 404).
* `RATE_LIMITED`: WooCommerce rate limits exhausted after retry attempts (HTTP 429).
* `UPSTREAM_UNAVAILABLE`: Store offline, connection failed, or HTTP 502/503.
* `UPSTREAM_ERROR`: Store internal failure (HTTP 500) or unparseable response.
* `TIMEOUT`: Upstream connection or read timeout exceeded.
* `INTERNAL_ERROR`: Unexpected internal connector exception.

---

## 1. `list_orders`

### Purpose
Retrieve a paginated list of WooCommerce orders with optional status filtering. Customer PII (billing, shipping, email, phone) is stripped by design.

### Inputs
| Parameter | Type | Required | Default | Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `page` | `integer` | No | `1` | Must be an integer $\ge 1$. |
| `limit` | `integer` | No | `20` | Must be an integer between $1$ and $100$ (connector safety cap). |
| `status` | `string` | No | `None` | Must be one of: `any`, `pending`, `processing`, `on-hold`, `completed`, `cancelled`, `refunded`, `failed`, `trash`. Case-insensitive. |

### WooCommerce API Mapping
* **HTTP Method**: `GET`
* **Upstream Endpoint**: `/wp-json/wc/v3/orders`
* **Query Parameters**:
  * `page` $\leftarrow$ `page`
  * `per_page` $\leftarrow$ `limit`
  * `status` $\leftarrow$ `status` (if provided)
* **Response Headers Processed**: `X-WP-Total`, `X-WP-TotalPages`

### Output Structure
Array of `OrderSummary` objects containing:
* `id` (`int`): Unique WooCommerce order ID.
* `order_number` (`string`): Customer-facing order reference number.
* `status` (`string`): Current order lifecycle state.
* `currency` (`string`): Currency code (e.g., `USD`, `INR`).
* `total` (`string`): Total order monetary amount.
* `subtotal` (`string | null`): Item subtotal.
* `total_tax` (`string | null`): Calculated taxes.
* `shipping_total` (`string | null`): Shipping charges.
* `payment_method_title` (`string | null`): Payment gateway title.
* `created_at` (`string | null`): Order creation timestamp.
* `date_modified` (`string | null`): Last update timestamp.
* `items_count` (`int`): Number of distinct line items.
* `items` (`array[OrderItem]`): List of line items (`id`, `name`, `product_id`, `quantity`, `subtotal`, `total`, `sku`).

### Example Call
**Request**:
```json
{
  "page": 1,
  "limit": 2,
  "status": "processing"
}
```
**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1042,
      "order_number": "1042",
      "status": "processing",
      "currency": "USD",
      "total": "89.99",
      "subtotal": "80.00",
      "total_tax": "9.99",
      "shipping_total": "0.00",
      "payment_method_title": "Razorpay",
      "created_at": "2026-03-15T10:30:00",
      "date_modified": "2026-03-15T11:00:00",
      "items_count": 1,
      "items": [
        {
          "id": 1,
          "name": "Travel Backpack",
          "product_id": 501,
          "variation_id": 0,
          "quantity": 1,
          "subtotal": "80.00",
          "total": "80.00",
          "sku": "BP-001"
        }
      ]
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 2,
    "total": 14,
    "total_pages": 7
  },
  "error": null
}
```

---

## 2. `get_order`

### Purpose
Retrieve detailed, privacy-minimized information for a single order by its ID.

### Inputs
| Parameter | Type | Required | Default | Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `order_id` | `integer` | Yes | *None* | Must be a strictly positive integer ($> 0$). Strings with non-digits or floats are rejected. |

### WooCommerce API Mapping
* **HTTP Method**: `GET`
* **Upstream Endpoint**: `/wp-json/wc/v3/orders/{order_id}`

### Output Structure
Single `OrderSummary` object (see `list_orders`).

### Example Call
**Request**:
```json
{
  "order_id": 1042
}
```
**Response**:
```json
{
  "success": true,
  "data": {
    "id": 1042,
    "order_number": "1042",
    "status": "processing",
    "currency": "USD",
    "total": "89.99",
    "subtotal": "80.00",
    "total_tax": "9.99",
    "shipping_total": "0.00",
    "payment_method_title": "Razorpay",
    "created_at": "2026-03-15T10:30:00",
    "date_modified": "2026-03-15T11:00:00",
    "items_count": 1,
    "items": [
      {
        "id": 1,
        "name": "Travel Backpack",
        "product_id": 501,
        "variation_id": 0,
        "quantity": 1,
        "subtotal": "80.00",
        "total": "80.00",
        "sku": "BP-001"
      }
    ]
  },
  "pagination": null,
  "error": null
}
```

---

## 3. `search_orders`

### Purpose
Search and filter orders using controlled, supported criteria (search query text, status, and ISO 8601 date ranges).

### Inputs
| Parameter | Type | Required | Default | Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `query` | `string` | No | `None` | Freeform search string matching order attributes. |
| `status` | `string` | No | `None` | Valid WooCommerce status (see `list_orders`). |
| `after` | `string` | No | `None` | Must be an ISO 8601 date/timestamp (e.g., `2026-01-01T00:00:00Z` or `2026-01-01`). |
| `before` | `string` | No | `None` | Must be an ISO 8601 date/timestamp. |
| `page` | `integer` | No | `1` | Integer $\ge 1$. |
| `limit` | `integer` | No | `20` | Integer between $1$ and $100$. |

### WooCommerce API Mapping
* **HTTP Method**: `GET`
* **Upstream Endpoint**: `/wp-json/wc/v3/orders`
* **Query Parameters**:
  * `search` $\leftarrow$ `query`
  * `status` $\leftarrow$ `status`
  * `after` $\leftarrow$ `after`
  * `before` $\leftarrow$ `before`
  * `page` $\leftarrow$ `page`
  * `per_page` $\leftarrow$ `limit`

### Example Call
**Request**:
```json
{
  "status": "completed",
  "after": "2026-01-01T00:00:00Z",
  "page": 1,
  "limit": 10
}
```

---

## 4. `list_products`

### Purpose
Retrieve a paginated list of catalog products from the WooCommerce store.

### Inputs
| Parameter | Type | Required | Default | Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `page` | `integer` | No | `1` | Must be an integer $\ge 1$. |
| `limit` | `integer` | No | `20` | Must be an integer between $1$ and $100$. |

### WooCommerce API Mapping
* **HTTP Method**: `GET`
* **Upstream Endpoint**: `/wp-json/wc/v3/products`
* **Query Parameters**:
  * `page` $\leftarrow$ `page`
  * `per_page` $\leftarrow$ `limit`

### Output Structure
Array of `ProductSummary` objects containing:
* `id` (`int`): Unique product ID.
* `name` (`string`): Product display title.
* `slug` (`string`): URL-friendly slug.
* `sku` (`string | null`): Stock Keeping Unit.
* `price` (`string | null`): Active sales price.
* `regular_price` (`string | null`): Standard list price.
* `sale_price` (`string | null`): Discounted price if applicable.
* `on_sale` (`boolean`): Whether the item is currently on sale.
* `status` (`string`): Publishing status (`publish`, `draft`, etc.).
* `stock_status` (`string | null`): Stock state (`instock`, `outofstock`, `onbackorder`).
* `stock_quantity` (`int | null`): Available inventory count.
* `categories` (`array[ProductCategory]`): Product taxonomy categories (`id`, `name`, `slug`).
* `created_at` (`string | null`): Creation timestamp.

### Example Call
**Request**:
```json
{
  "page": 1,
  "limit": 1
}
```
**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": 501,
      "name": "Travel Backpack",
      "slug": "travel-backpack",
      "sku": "BP-001",
      "price": "80.00",
      "regular_price": "99.00",
      "sale_price": "80.00",
      "on_sale": true,
      "status": "publish",
      "stock_status": "instock",
      "stock_quantity": 25,
      "categories": [
        {
          "id": 12,
          "name": "Bags & Luggage",
          "slug": "bags-luggage"
        }
      ],
      "created_at": "2026-01-10T08:00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 1,
    "total": 45,
    "total_pages": 45
  },
  "error": null
}
```

---

## 5. `get_product`

### Purpose
Retrieve catalog details for a single product by its ID.

### Inputs
| Parameter | Type | Required | Default | Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `product_id` | `integer` | Yes | *None* | Must be a strictly positive integer ($> 0$). |

### WooCommerce API Mapping
* **HTTP Method**: `GET`
* **Upstream Endpoint**: `/wp-json/wc/v3/products/{product_id}`

### Output Structure
Single `ProductSummary` object (see `list_products`).

### Example Call
**Request**:
```json
{
  "product_id": 501
}
```
**Response**:
```json
{
  "success": true,
  "data": {
    "id": 501,
    "name": "Travel Backpack",
    "slug": "travel-backpack",
    "sku": "BP-001",
    "price": "80.00",
    "regular_price": "99.00",
    "sale_price": "80.00",
    "on_sale": true,
    "status": "publish",
    "stock_status": "instock",
    "stock_quantity": 25,
    "categories": [
      {
        "id": 12,
        "name": "Bags & Luggage",
        "slug": "bags-luggage"
      }
    ],
    "created_at": "2026-01-10T08:00:00"
  },
  "pagination": null,
  "error": null
}
```

---

## 6. `search_products`

### Purpose
Search the product catalog for matching keywords across title, description, or SKU.

### Inputs
| Parameter | Type | Required | Default | Validation Rules |
| :--- | :--- | :--- | :--- | :--- |
| `query` | `string` | Yes | *None* | Search text; cannot be empty or whitespace. |
| `search_fields` | `list[string]` | No | `None` | Allowed fields: `name`, `sku`, `global_unique_id`, `description`, `short_description`. |
| `page` | `integer` | No | `1` | Integer $\ge 1$. |
| `limit` | `integer` | No | `20` | Integer between $1$ and $100$. |

### WooCommerce API Mapping
* **HTTP Method**: `GET`
* **Upstream Endpoint**: `/wp-json/wc/v3/products`
* **Query Parameters**:
  * `search` $\leftarrow$ `query`
  * `page` $\leftarrow$ `page`
  * `per_page` $\leftarrow$ `limit`
  * `search_fields` $\leftarrow$ `search_fields` (if provided)

### Example Call
**Request**:
```json
{
  "query": "backpack",
  "page": 1,
  "limit": 5
}
```
