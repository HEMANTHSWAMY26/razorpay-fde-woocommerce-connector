# WooCommerce MCP Connector — Capabilities

This document details the functional capabilities implemented and validated in the WooCommerce Private MCP Connector.

---

## 1. Supported Resource Capabilities

### Orders
* **`list_orders`**:
  * Paginated retrieval of orders from WooCommerce store.
  * Controlled status filtering (`pending`, `processing`, `completed`, `cancelled`, etc.).
  * Response normalization to `OrderSummary`.
  * Safe pagination metadata extraction (`page`, `limit`, `total`, `total_pages`).
* **`get_order`**:
  * Retrieval of an individual order by strictly positive integer ID.
  * Explicit validation rejecting non-positive numbers or malformed ID strings before external transmission.
  * Structured output containing line items, currency, status, order number, and monetary totals.
* **`search_orders`**:
  * Query-based searching across orders.
  * Multi-dimensional filtering by lifecycle status and date ranges (`after`, `before`).
  * Enforces ISO 8601 compliance for all timestamp filters.

### Products
* **`list_products`**:
  * Paginated retrieval of store catalog products.
  * Extracts product pricing (`price`, `regular_price`, `sale_price`), stock status, inventory count, and category metadata.
* **`get_product`**:
  * Direct lookup of a single product by positive integer ID.
  * Rejects invalid or out-of-range IDs before network execution.
* **`search_products`**:
  * Text search across product titles, descriptions, and SKU entries.
  * Optional validation against supported search fields (`name`, `sku`, `global_unique_id`, `description`, `short_description`).

---

## 2. Authentication Capabilities
* **WooCommerce REST API v3 Authentication**:
  * Utilizes standard HTTP Basic Authentication with `WOOCOMMERCE_CONSUMER_KEY` and `WOOCOMMERCE_CONSUMER_SECRET`.
  * Credentials transmitted over TLS/HTTPS headers (`Authorization: Basic ...`), preventing credentials from appearing in URL query logs.
  * Credentials masked automatically in string representations, logs, and diagnostic errors.

---

## 3. Reliability & Resilience Capabilities
* **Strict Input Validation Policy**:
  * Every MCP tool executes connector-side validation prior to making network requests.
  * Enforces positive integer IDs, bounded pagination (1 to 100 items per page), valid WooCommerce order statuses, and ISO 8601 datetime strings.
* **Bounded Retries with Exponential Backoff & Jitter**:
  * Retries transient failures: HTTP 429, 500, 502, 503, 504, connection drops, and network timeouts.
  * Protects against thundering herd problems using randomized jitter ($0.5 \times \text{delay}$ to $\text{delay}$).
  * Respects upstream `Retry-After` headers (both integer seconds and RFC 2822 / RFC 7231 HTTP dates), bounded by a configurable `max_delay`.
  * Non-retryable status codes (400, 401, 403, 404) fail immediately without wasteful retries.
* **Standardized Error Normalization**:
  * Converts all HTTP statuses and network exceptions into a clean envelope: `{"success": false, "error": {"code": "...", "message": "..."}}`.
  * Python stack traces and sensitive connection details are never surfaced to MCP clients.

---

## 4. Privacy & Data Minimization Capabilities
* **Structural PII Stripping**:
  * Raw WooCommerce customer information (`billing`, `shipping`, `customer_ip_address`, `customer_user_agent`, `customer_note`) is removed before JSON serialization.
  * LLM agents access only business-critical order metadata (totals, item names, SKU, quantities, timestamps, status).
* **Safe Log Sanitization**:
  * All loggers redact authorization headers, consumer secrets, and customer fields (`[REDACTED]`).

---

## 5. MCP Architecture Capabilities
* **Official MCP Python SDK v2 (`MCPServer`)**:
  * Implemented using the current stable MCP v2 specification.
  * Automatic JSON schema generation for tool parameter discovery.
  * Dual output format: standard text content for MCP v1 compatibility and `structured_content` for MCP v2 clients.
* **Multi-Transport Support**:
  * **Streamable HTTP**: Runs as an ASGI Starlette application with `/mcp` streamable endpoint, suitable for network deployment.
  * **Health Check**: Native `/health` GET endpoint for Docker/Kubernetes container orchestration.
  * **stdio**: Supported for direct local CLI and desktop client integration (e.g. Claude Desktop, MCP Inspector).
